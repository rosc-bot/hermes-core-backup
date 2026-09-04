---
name: media-resource-submission-bot
description: "Use when managing or extending tg-media-submission-bot."

---

# Telegram Media Resource Submission Bot (tg-media-submission-bot)

Use for administering, troubleshooting, extending, or testing `@zhuancun001_bot` on Docker Compose.

Refs: `references/transfer-notification-reconciliation.md`; the existing movie-folder and transfer-stage references remain available.

## 1. System Architecture & Components

- **Directory**: `/home/ubuntu/tg-media-submission-bot`
- **Virtualenv**: Python 3.11 (`.venv/bin/python`)
- **Systemd fallback unit**: `tg-media-bot.service`
  - Production baseline: keep `inactive` and `disabled` so it cannot create a second Telegram polling process.
  - Only use `sudo systemctl status|restart|stop tg-media-bot` for an explicitly selected rollback or legacy deployment; logs are available with `journalctl -u tg-media-bot -f`.
- **Database**: PostgreSQL 18 (`media_bot_db`, user: `mediabot`)
  - Test DB: `media_bot_test_db`
- **GitHub Repository**: `rosc-bot/tg-media-submission-bot` (Private, branch: `main`)
- **ORM & Migrations**: SQLAlchemy 2.0 (asyncpg) + Alembic
- **Bot Engine**: `aiogram` 3.31 with `MemoryStorage`
- **WebUI Dashboard & API**: FastAPI running on port 12082 (on Oracle Cloud) or 2082 (previously on AWS), providing real-time stats, task progress bars, missing episode counters, and type/status filters. (Configurable via `WEB_PORT` in `.env`).
- **Process Runner**: `app.runner` orchestrates both the Telegram polling loop and FastAPI WebUI under `asyncio.gather` inside the active Compose service `tg-media-bot`; do not start a parallel systemd copy.
- **Current Oracle deployment baseline**: Telegram polling and FastAPI run in Docker Compose service `tg-media-bot` (non-root UID 1001, host networking, read-only root filesystem, and only `data/metadata` bind-mounted writable). PostgreSQL remains on the host loopback; the systemd unit is disabled to prevent a second polling process and is retained only as a rollback path.

## 2. Core Deduplication & Database Invariants

### 2.1 Dual Partial Unique Indexes (Mandatory)
PostgreSQL treats `NULL != NULL` under standard unique indexes. Therefore, TV episodes and movies **MUST NOT** share a single composite index:
1. **TV / Anime Index**:
   ```sql
   CREATE UNIQUE INDEX uq_resources_episode_accepted
   ON resources (task_id, season, episode)
   WHERE status = 'ACCEPTED' AND season IS NOT NULL;
   ```
2. **Movie Index**:
   ```sql
   CREATE UNIQUE INDEX uq_resources_movie_accepted
   ON resources (task_id)
   WHERE status = 'ACCEPTED' AND season IS NULL;
   ```
*Never combine these into a single index with NULL columns, as duplicate movie ACCEPTED rows would bypass validation.*

### 2.2 Independent Savepoints for Batch Submissions
When a user submits multiple episodes (e.g. `E15-E18`):
- Do **NOT** execute the batch as an all-or-nothing single transaction.
- Use `async with db.begin_nested():` per episode.
- If one episode triggers unique constraint conflict (`uq_resources_episode_accepted`), record it as `CONFLICT` ("已被其他用户抢先收录"), roll back only that savepoint, and proceed with remaining episodes.

### 2.3 Partial Episode Range Invariant (`start_episode` vs `total_episodes`)
For ongoing serial media (anime, weekly web dramas like 《师兄啊师兄》, 《完美世界》):
- Admin task creation often targets a **specific episode segment** (e.g. `S01E151-S01E157` or `151-157集`).
- **NEVER** treat `157` as total episodes starting from episode 1 (i.e. do not mark 1..150 as missing).
- The `tasks` table stores `start_episode` (default 1) and `total_episodes` (target end episode).
- Missing episode calculation: `set(range(task.start_episode or 1, task.total_episodes + 1)) - accepted_episodes`.
- Card preview & `/tasks` display: If `start_episode > 1`, display `▫️ 征集集数: E{start_episode:02d}-E{total_episodes:02d} (共 N 集)`.
- Completion criteria: When all episodes within `[start_episode, total_episodes]` have status `ACCEPTED`, `task.status = COMPLETED`.

### 2.4 Active Task Deduplication Invariant
To prevent administrators or batch inputs from publishing duplicate collection tasks into `/tasks`:
- `TaskService.find_duplicate_task` checks whether an `ACTIVE` task already exists with the same title (trimmed, case-insensitive) and the same media type / season (`season == S` for TV/ANIME, `media_type == MOVIE` for single movies).
- `/add` (`cmd_quick_add`) and `/addtask` wizards check for existing duplicates before presenting confirmation and upon button submission:
  - If all candidate tasks exist: directly prompts `⚠️ 已存在相同的征集任务，请勿重复发布！` with the existing task's ID, title, spec, and status, and clears the FSM without creating duplicate rows.
  - In batch inputs: existing tasks are automatically filtered out, informing the admin which tasks were skipped and proceeding only with new items.
  - `TaskService.create_task` enforces `check_duplicate=True` by default.

### 2.5 Cloud Content Inspection & Admin Review Workflow
Shallow regex matching of cloud URLs (e.g. checking if a domain contains `guangya` or `quark`) is insufficient:
1. **Cloud Link Deep Inspection & Emby Standard Naming**：
   - Submissions must be inspected to verify internal files: video file count (filtering `.txt`, `.nfo`, etc.), individual file sizes, total size, and encoding/spec metadata.
   - Naming must strictly match Emby/Jellyfin scraping standards:
     - **Movie (Most Standard)**: `片名 (年份) {tmdbid-ID}.画质.来源.编码.ext` (e.g. `消失的人 (2026) {tmdbid-1363974}.2160p.WEB-DL.DDP5.1.H.265.mp4`)
     - **TV Single (Most Standard)**: `剧名 (年份) {tmdbid-ID}.SxxExx.画质.来源.编码.ext` (e.g. `庆余年 (2019) {tmdbid-93811}.S02E01.2160p.WEB-DL.DDP5.1.H.265.mkv`)
     - **TV Multi-Episode (Most Standard)**: `剧名 (年份) {tmdbid-ID}.SxxExx-Exx.画质.来源.编码.ext` (e.g. `庆余年 (2019) {tmdbid-93811}.S02E01-E06.2160p.WEB-DL.H265.mkv`)
     - **TV Special / SP (Most Standard)**: `剧名 (年份) {tmdbid-ID}.S00Exx.画质.来源.编码.ext` (e.g. `庆余年 (2019) {tmdbid-93811}.S00E01.2160p.WEB-DL.H265.mkv`)
     - **TV Standard (Without TMDB ID)**: `剧名 (年份).SxxExx.画质.来源.编码.ext` (MUST have S0几 season prefix in every filename).
2. **Tiered Points System (3 Criteria) & Task Bounty (+1~5 pts) & Direct Auto-Rejection Gate**：
   - **Non-Standard Naming** (pure numbers, missing `S0几` in filename itself): **Direct upfront rejection** in user session; 0 points; does NOT notify admin.
   - **3 Independent Naming Criteria (0.5 pts per met criterion, up to +1.5 pts)**:
     1. **Standard format specification**: File matches Emby standard naming format (Movie/TV/Anime) -> **+0.5 pts**;
     2. **Folder contains valid TMDB ID**: Cloud parent folder or share title contains `{tmdbid-ID}` matching target media -> **+0.5 pts**;
     3. **Video filename contains valid TMDB ID**: Video file itself contains `{tmdbid-ID}` matching target media -> **+0.5 pts**;
     - *Scoring*: 1 criterion met = **0.5 pts**, 2 criteria met = **1.0 pt**, 3 criteria met = **1.5 pts**.
   - **Difficult Resource Task Bounty (`bounty_points`: 0.0 ~ 15.0 pts) & Interactive Buttons**：
     - Admin can publish hard-to-find resource tasks with extra bounty points up to **15.0 pts** (e.g. `/add 狂飙 +10分` or `/add 庆余年 困难:15分` or via `/addtask`).
     - Both `/add` quick preview and `/addtask` provide interactive button matrices (`0分`, `+1分`, `+2分`, `+3分`, `+5分`, `+8分`, `+10分`, `+15分`) with live in-place updating.
     - Tasks in `/tasks` list highlight `[🔥+N分]`.
     - Upon approval, the submitter receives `naming_points (0.5~1.5) + bounty_points (1~15)`, fully itemized in admin cards and `point_logs` audit trail.
   - **Exclusive Timed Task & 30-Minute Claim Timeout Penalty Gate**：
     - **Mode Choice**: Tasks can be created as `普通开放` (anyone submits freely) or `⚡ 限时抢单` (exclusive 30-minute lock, "谁先完成算谁的").
     - **Exclusive Claiming**: Users tap `[⚡ 立即领取并开始]` in `/tasks` to lock the task for 30 minutes. Other users see `[⏳ @用户名 抢单中/剩N分]` and cannot claim concurrently.
     - **Timeout Penalty & Auto-Release**: Background watcher (`timed_task_expiry_watcher`) polls active claims every 20s. If a user holds a claim for >30 minutes without submitting valid resources, the system automatically deducts 1.0 point (`TIMED_TASK_TIMEOUT_PENALTY`), logs to `point_logs`, notifies the user via DM, and unlocks the task for others.
   - **Dedicated Group Membership Authorization Gate (`GroupMembershipMiddleware`)**：
     - **Scope & Protection**: Restricts bot usage exclusively to members of the designated Telegram group (e.g. `@shangpian888` / `-1003758628375`) to prevent spam, malicious bot farming, and abuse.
     - **Admin Bypass**: Configured administrators dynamically parsed from `ADMIN_TG_ID` automatically bypass this check.
     - **Non-Member Handling**: Intercepts private messages and callback queries with an interactive restriction card:
       - Link button `[👉 点击加入群聊]` (e.g. `https://t.me/shangpian888`);
       - Real-time verification button `[🔄 我已加入，点击验证]`.
     - **In-Memory TTL Caching**: Verified memberships are cached in memory for 5 minutes (`CACHE_TTL_SECONDS = 300`) to guarantee zero-latency response without flooding the Telegram Bot API. Explicit verification requests bypass cache for instant feedback.
   - **Community Media Request & Point Deduction System (`/seek`, `/request`, `/myrequests`)**：
     - **Shared Point Ledger Economy**: Point balances are shared across the system. Users spend earned submission points to request wanted movies or TV shows.
     - **Pricing Standard**:
       - **Movie**: 2.0 points flat.
       - **TV / Anime series**: 0.5 points per episode (e.g. 20 eps = 10.0 pts, 39 eps = 19.5 pts, 1 ep = 0.5 pt).
     - **Atomic Deduction & Ledger Audit**:
       - Checks user's available points. If balance < cost, rejects with clear guidance.
       - If sufficient, deducts points and records `PointLog` with `action='MEDIA_REQUEST_DEDUCT'`.
       - Creates an active `Task` marked with `is_request=True`, `requester_tg_id`, `cost_points`.
       - Displays in `/tasks` list as `[🌟群友求片]`.
     - **Cancel & Refund**: Users can view their requests via `/myrequests` and cancel ACTIVE requests with 0 accepted submissions to receive a 100% point refund (`MEDIA_REQUEST_REFUND`).
     - **Completion Notification**: When another user submits and an admin approves the requested media to `COMPLETED`, the bot automatically notifies the requester via private message.
     - **Full Statistical Aggregation ("加了减了 数据库统计")**:
       - Automatically aggregates `total_earned`, `total_spent_request`, `total_penalized`, `total_refunded`, and recent 5 transaction logs with human-readable timestamps and reasons in `/points` and `/user <tg_id>`.
3. **Admin Human Review Gate (No Automatic Acceptance)**：
   - Successful link inspections transition resources to `REVIEW`, NOT `ACCEPTED`.
   - The bot delivers a detailed review card with inline buttons to the admin, highlighting format badge and expected points.
   - Only when an admin clicks `[✅ 通过并加分]` does the system:
     - Set status to `ACCEPTED`;
     - Increment the user's contribution points (+0.5 or +1.0);
     - Decrement task missing episodes (and mark `COMPLETED` if all episodes are met);
     - Broadcast the formatted resource announcement to the Telegram channel.
   - Rejecting `[❌ 驳回]` marks the resource `REJECTED` and notifies the submitter without adjusting points or task state.

### 2.6 User Daily Quota Limits (Anti-Farming & Quality Gate)
To eliminate low-quality spamming and point farming (submitting small files or fragmented links to farm rewards):
- **Daily Storage Cap**: `DAILY_USER_GB_LIMIT` (default: 100.0 GB per user per Beijing natural day).
- **Daily Count Cap**: `DAILY_USER_SUBMISSION_LIMIT` (default: 20 submission groups per user per Beijing natural day).
- **Quota Calculation**: Calculated from 00:00:00 UTC+8 (Beijing time) natural day start across all submission records.
- **Double Gate Interception**:
  1. Prompt-level: When clicking a task in `/tasks`, if user already reached $\ge$ 20 submissions, immediately stop before input.
  2. Inspection-level: When parsing cloud links, calculate parsed GB (`total_size / 1024^3`); if `today_total_gb + incoming_gb > 100 GB` or `today_count >= 20`, reject upfront with detailed usage summary.
- **Admin Exemption**: Administrators dynamically parsed from `ADMIN_TG_ID` bypass all daily quotas.

### 2.7 Point Ledger Audit Trail & Manual Admin Penalties
To handle malicious submitters, blank links, and trolls:
- **`point_logs` Table**:
  Every point alteration logs `tg_user_id`, `delta`, `balance_after`, `action` (`SUBMISSION_APPROVE`, `SUBMISSION_REVOKE`, `ADMIN_DEDUCT`, `ADMIN_CLEAR`, `ADMIN_ADD`), `reason`, `operator_tg_id`, and `created_at`.
- **Admin Review Card Quick Actions**:
  - `[✅ 审核通过并加分]`: +0.5 or +1.0 pts + channel publish.
  - `[❌ 正常驳回]`: Marks REJECTED, 0 pt change.
  - `[⚠️ 驳回并扣1分]`: Marks REJECTED, deducts 1.0 pt, sends penalty DM to user.
  - `[🚫 驳回并扣2分]`: Marks REJECTED, deducts 2.0 pts, sends severe violation DM.
  - `[👤 查用户画像/管理]`: Opens interactive user console.
- **Targeting by TG ID or @Username**:
  Commands (`/deduct`, `/clearpoints`, `/addpoints`, `/user`) resolve both numeric IDs and @usernames. Point balances cannot drop below 0.0 (`max(0.0, balance)`).


## 3. Dynamic Cloud Configurations & Channel Routing

The `cloud_configs` table governs domain matching, channel routing, and auto-transfer flags without code changes.

| Field | Purpose & Behavior |
| :--- | :--- |
| `name` | Unique cloud identifier (e.g. `guangya`, `mobile`, `quark`, `ali`, `baidu`, `115`) |
| `domain_pattern` | Regex for matching share links (e.g. `guangya\|gypan\|guangyapan\|guangya\.com`) |
| `hashtag` | Telegram hashtag added to post (e.g. `#光鸭`, `#移动`) |
| `channel_id` | Dedicated TG broadcast channel. If `NULL`, resources are stored in DB but not posted to a channel. |
| `auto_process` | `False` = `link_only` (V1 baseline); `True` = dispatch to automated transfer API. |
| `process_type` | Processor type (default `link_only`). |

### 3.1 Adding a New Cloud or Updating Routing
Run via SQL against `media_bot_db`:
```sql
-- Example: Add PikPak
INSERT INTO cloud_configs (name, domain_pattern, hashtag, channel_id, auto_process, process_type, enabled)
VALUES ('pikpak', 'mypikpak\.com|pikpak\.me', '#PikPak', '-100xxxxxxx', false, 'link_only', true);

-- Example: Set dedicated channel
UPDATE cloud_configs SET channel_id = '-1004387965244' WHERE name = 'guangya';
UPDATE cloud_configs SET channel_id = '-1004410413711' WHERE name = 'mobile';
```

## 4. Admin Management & Command Workflows

In `.env`:
```bash
ADMIN_TG_ID=8586984520,7898049885
```
Supports comma-separated IDs parsed dynamically.

### Commands:
- `/tasks`: User lists active uncompleted tasks and views missing episodes.
- `/points`: User views contribution points ledger, today's used submission quota (count & GB), and community guidelines.
- `/cancel`: Resets current FSM conversation state.
- `/add <title>`: [Admin] Intelligent one-click task creation with automatic TMDB detection, year/region extraction, interactive bounty buttons (`0~15分`), timed task mode toggle, and preview confirmation.
  - **Auto-Selection Pitfall**: To support rapid batching, `/add` queries TMDB in the background and silently locks in the Top 1 result. If TMDB's top hit is inaccurate, it will misclassify the task.
  - Supports multi-season range auto-expansion: e.g. `/add 庆余年 S01-S03` or `/add 权力的游戏 1-8季` (creates discrete task per season in compliance with schema).
  - Supports batch creation: `/add 繁花 | 漫长的季节 | 狂飙` or multi-line title lists.
  - Supports difficulty bounty parameters: `/add 庆余年 +2分` or `/add 狂飙 困难15` or `限时` (adds `bounty_points` & `is_timed`).
- `/addtask`: [Admin] Step-by-step interactive task creation wizard (supports multi-season ranges, per-season episode lists, difficulty/bounty point buttons `[0分/无]` ~ `[🔥 +15分]`, and timed task mode selection). **Use this instead of `/add` for 100% precision, as it strictly follows user input and does NOT auto-guess via TMDB.**
- `/deltask [id/title]`: [Admin] Interactive and targeted task unpublishing & deletion (supports interactive button list, direct ID/title lookup, two-step safety confirmation card, automatic requester point refund for `/seek` tasks, and cascade resource cleanup).
- `/del [id/batch]`: [Admin] Interactive submission management & revocation. Browse recent submissions with pagination or directly target an ID/batch to delete erroneous submissions with two-step confirmation.
- `/user [user_id/@username] [action/points] [reason]`: [Admin] Unified user directory, profile inspector, and reward/penalty control console:
  - `/user`: Paginated directory of every account present in the `users` table, with configured administrators and regular users rendered in separate sections and total counts. Use inline previous/next/refresh buttons when the directory exceeds one page.
  - `/user <user_id/@username>`: Full user profile card with live stats, today's quota, submission history, recent 5 point logs, and interactive quick action buttons (`[➖ 扣0.5]`, `[➖ 扣1]`, `[➖ 扣2]`, `[➕ 奖1]`, `[➕ 奖2]`, `[🔄 一键清零]`, `[🔃 刷新]`).
  - Keep the directory rows readable: show display name, optional `@username`, Telegram ID, and points; escape all stored identity fields before inserting them into Telegram HTML.
  - `/user <user> -<points> [reason]` (or `扣1`): Direct deduction with reason and user PM notification.
  - `/user <user> +<points> [reason]` (or `加1`): Direct reward addition with reason and user PM notification.
  - `/user <user> clear [reason]` (or `清零`): Direct point wipeout with reason and severe warning notification.
  - *Note: Legacy command aliases (`/deduct`, `/clearpoints`, `/addpoints`) seamlessly route to this unified handler, while the Telegram command menu is kept minimal and clutter-free.*
- `/setai` / `/ai`: [Admin] Unified AI review & model picker control center (interactive paginated inline model selector querying `/models` with `✔` active indicator, quick `/setai <model>` switching, preset/custom base/key configuration, connectivity ping tests, and review toggle).

*Note: The bot calls `set_my_commands` automatically on startup using dual-scope registration (`BotCommandScopeDefault` + per-admin `BotCommandScopeChat`) to ensure instant client-side menu refresh.*

## 5. Router Order, Parser & Handler Pitfalls

1. **Dispatcher Router Priority**:
   - `admin.router` and specific command routers MUST be attached before generic or catch-all text routers (e.g. `common.router`).
   - Generic text fallback handlers must filter out command messages using `~F.text.startswith("/")` and ensure `current_state is None` so commands and FSM transitions are never swallowed.
49. **WebUI Task Dashboard Categorized Accordion & Click-to-Expand Resource Invariant (网页端折叠分类与资源详情规范)**:
   - Flat grid views for active tasks become unmanageable and cluttered when the task count grows.
   - **MANDATORY**: The FastAPI WebUI (`app/templates/index.html`) MUST render tasks grouped by `media_type` (`MOVIE`, `SERIES` -> MUST explicitly map back to enum `TV` for series/dramas, `ANIME`) using an accordion (collapsible) layout.
   - Each accordion group header displays the category icon, name, and task count. By default, task grids inside are hidden until expanded, mimicking the nested folder logic of the cloud drives and ensuring visual cleanliness even with hundreds of tasks.
   - **Click-to-Expand Resource Details**: Task cards must be clickable (using cursor-pointer). When clicked, the card expands to show a detailed list of accepted `Resource` submissions joined with `User` data. Each resource row MUST display the submitter's identity (e.g., `@username`) as a clickable link that opens their Telegram profile (use `https://t.me/${r.username}` if `username` exists, otherwise fallback to `tg://user?id=${r.user_tg_id}`). It must also display the target cloud tag, and an actionable external link button (`[直达网盘]`/`[用户链接]`) binding to `transferred_share_url` or `orig_share_url`. If no share URL exists, gracefully fall back to displaying the standard 2-level directory path.
   - **Click Event Propagation Fix (Physical Isolation)**: Binding `onclick` to the entire card and trying to stop propagation (e.g., `e.target.closest('a')`) is unreliable on mobile/complex interactions. **MANDATORY**: Physically split the card HTML into two distinct parts: an upper \"header\" section (title, tags) with the `onclick` handler, and a lower \"body\" section (resource list) without any click handlers. This guarantees interactions inside the expanded details never trigger an accidental collapse.
   - **Manual Refresh over Auto-Refresh (No Periodic DOM Wiping)**: Do NOT use `setInterval` to forcefully re-fetch data and wipe `innerHTML` in accordion layouts, as this severely degrades UX (discards scroll position, wipes text selection, and causes layout flickers even if expanded state is meticulously restored). **MANDATORY**: Provide a manual `[刷新]` (Refresh) button instead, giving the user absolute control over when the data updates.
   - **2-Level Taxonomy Dashboard Matching**: The WebUI task categorization must not just use the basic 3 top-level types (MOVIE/TV/ANIME). It MUST consume `MediaClassifier.classify(task)` and group tasks directly into the 16-level detailed taxonomy (e.g. \"电影 / 科幻电影\" or \"电视剧 / 日番\"), matching exactly how the files are grouped in the cloud drive. The inline directory path must also reflect this matched taxonomy. Furthermore, the type filter buttons must be dynamically generated from the unique taxonomy categories actually present in the fetched data, rather than hardcoded.
   - **Strict Cloud Storage Verification & Status Badges**: Do not assume a resource failed to transfer just because `transferred_share_url` is missing (the cloud might be configured not to auto-generate shares). **MANDATORY**: The UI MUST check for `transferred_folder_id` as the definitive proof of successful cloud storage. Display an explicit badge (`[✓ 已入库]` vs `[⏳ 待转存]`) based on this dual-check so administrators can immediately identify silent transfer failures or expired links.
   - **Mobile Flexbox Overflow & Truncation Prevention**: When adding multiple inline badges (e.g., transfer status, file size) into a flex container, applying `truncate` to the parent flex container causes text elements (like `@submitter` names) to silently disappear on narrow mobile screens. **MANDATORY**: Use `flex-wrap items-center min-w-0` on the container, and apply `truncate max-w-[120px]` directly to the specific text anchor tags, ensuring elements gracefully flow to a new line rather than being cut off.
   - **TMDB Animation Genre to ANIME Enforced Extraction**: The rigid parsing logic defaults to mapping domestic/regional series to 'TV', bypassing the 'ANIME' designation even when TMDB explicitly tags it as Animation (Genre ID: 16). **MANDATORY**: When fetching `candidates` from `search_tmdb`, strictly retain `genre_ids`. During task creation and auto-detection, explicitly interrogate `candidates[0].get("genre_ids", [])`. If `16` (Animation) is present, forcefully override the `media_type` to `"ANIME"`. This ensures correct 2-level taxonomy mapping (e.g., '国漫', '日番') in subsequent categorization layers.
   - **Partial Task Completion UI Progress Calculation**: When rendering task progress bars for partial episode batches (e.g., S01E151-E157), do NOT calculate `acceptedCount = total_episodes - missing_episodes`. If the task starts at 151 and ends at 157, `missing_episodes=0` means 7 episodes were uploaded, not 157. **MANDATORY**: Calculate the task's true block size: `taskTotalCount = Math.max(1, (total_episodes - start_episode + 1))`, then `acceptedCount = taskTotalCount - missing_episodes.length`. Render the specific range `(第 {start_episode}-{total_episodes} 集)` to prevent falsely signaling that the entire show is completed.
2. **Chinese Media Title & Range Parsing Invariants**:
   - **Episode vs Season Range Isolation**: Numbers followed by `集`, `话`, `ep`, or `EP` (e.g. `152-157集`, `更新至180集`, `1-250集`) MUST be parsed as `total_episodes`. Season range regexes MUST strictly require `季` or `S` and MUST NOT match numbers followed by episode indicators, otherwise long-running anime/dramas (e.g. `152-157集`) will falsely generate dozens of non-existent seasons (e.g. S15–S57).
   - **Regex Stripping Sequence Invariant**: When stripping metadata from input strings during title cleaning, 3-4 digit episode ranges (e.g. `\b\d{1,4}[-~]\d{1,4}\b`) and composite tokens (e.g. `S01E151-S01E157`) MUST be stripped BEFORE 2-digit season range regexes (`\b\d{1,2}[-~]\d{1,2}\b`). Otherwise, a generic `\d{1,2}-\d{1,2}` pattern will match the suffix of the start episode and prefix of the end episode in `151-157` (matching `51-15` as a false season range).
   - **Composite Input Parsing in Interactive Prompts (`/addtask`)**: When prompted for "Season", users frequently paste full episode tags (e.g. `S01E152-S01E157`, `S1 152-157集`). The season handler MUST strip out episode markers (`E...`, `集`) before evaluating season ranges. If both a single season (e.g. `S01`) and an episode range (e.g. `E152-E157`) are extracted in that turn, immediately set both and transition directly to confirmation, skipping the redundant episode prompt.
   - **Range Tolerance in Episode Prompts**: The episode prompt handler must accept ranges like `152-157` or `E152-E157` and extract the maximum episode number (`max(e1, e2)`) rather than failing on non-digit strings.
   - **Multi-Line Metadata Grouping**: When users paste multi-line input (e.g. Line 1: `师兄啊师兄 2023`, Line 2: `国产动漫 152-157集`), detect lines that are pure metadata/tags without a distinct title, and merge them with the preceding title line into a single work item instead of creating fragmented or duplicate tasks.
   - **Title Cleaning**: Strip all category tags (`国产动漫`, `4K`, `完结`, `更新至`), years, season ranges, episode ranges, AND Chinese numerals (e.g. `第一季`, `第二季`) before querying TMDB. TMDB's strict query matching will fail completely (returning 0 results) if '第二季' is left in the title string.
   - **TMDB Media Type Search Fallback**: If a TMDB search for a specific `media_type` (e.g., `MOVIE`) yields 0 candidates, the parser MUST automatically fallback and retry the search as the opposite type (`TV`). User inputs are often ambiguous (e.g. `杀人者的购物中心2`), and failing to fallback results in silent TMDB disambiguation failures.
   - **Interactive TMDB Disambiguation (`/add`)**: While batch `/add A | B` should silently pick the Top 1 TMDB result for speed, a single `/add Title` MUST render an interactive inline keyboard displaying the top 5 TMDB candidates (with year and overview) if candidates are found. This prevents TMDB from hijacking ambiguous titles with incorrect metadata.
3. **Dynamic Admin Parsing**:
   - Parse `settings.ADMIN_TG_ID` dynamically by splitting on commas `[int(x.strip()) for x in str(settings.ADMIN_TG_ID).split(",") if x.strip().isdigit()]` to support hot-adding admins via `.env`.
4. **Clean URL Extraction from Free-Form Text**:
   - Users often paste descriptive strings (e.g. `国产电影/2026/光鸭云盘：https://...`). Handlers must regex extract `https?://[^\s]+` rather than storing or validating the raw message string directly.
5. **Channel Delivery Routing**:
   - `target_channel = cloud_cfg.channel_id or settings.CHANNEL_ID`.
   - In `ChannelService.publish_submission`, always pass `chat_id=target_channel` instead of hardcoding `settings.CHANNEL_ID`, ensuring dedicated channel routing per cloud drive.
6. **Strict Delivery Discipline (Zero-Defect Quality Gate)**:
   - After writing or editing code, ALWAYS run full test suite (`pytest tests/ -v`), execute standalone Python sanity checks on edge cases, restart service, and verify `systemctl status` uptime/PID plus `journalctl -u tg-media-bot -n 30` before reporting completion to the user. Never assume a restart or patch succeeded without verifying the live process state.
7. **Port Allocation & Cloud Security Group Invariant**:
   - When deploying web dashboards, APIs, or any service requiring a network port, **NEVER** unilaterally invent and bind an unconfirmed port (e.g. 8090) without consulting the user.
   - In cloud hosting environments (AWS EC2, OCI, GCP), cloud security groups block all unopened inbound ports by default.
   - **Procedure**:
     1. Always ask the user first before picking or opening a port.
     2. Enumerate currently open ports on the security group/firewall.
     3. Prioritize reusing already opened but unused/idle ports where appropriate.
     4. If a new port is genuinely necessary, explicitly inform the user of the exact port number and protocol (TCP) so they can configure their security group rules cleanly.
     5. **Cross-Server Migration Port Collision Avoidance**: When migrating the bot to a new server and the user provides a list of pre-allowed firewall ports, **MANDATORY**: explicitly select a port that is NOT currently active on the old server (e.g. if AWS uses 8648, pick 12082 for Oracle). This prevents port collisions if the user later consolidates services or migrates back.
   - See `references/aws_ports_and_routing.md` for the verified host security group open/idle port roster and probe invariants.
8. **Interactive FSM State Variable Propagation & Verification Discipline**:
   - In multi-step Telegram FSM wizards (like `/addtask`), when an early step (e.g. `process_task_season`) detects composite input (e.g. `S01E151-S01E157`) and fast-tracks directly to confirmation, it MUST fully populate every single required state key (`start_episode`, `total_episodes`, `season`, `year`, `region`, `media_type`, `title`). Forgetting `start_episode` in an early-jump branch will silently cause the confirmation card to fall back to `1..N` (all episodes).
   - **Simulated FSM Handler Verification Gate**: Never declare an FSM fix complete based on standalone helper/service tests alone. Always write and run a Python script that instantiates mock `Message` and `FSMContext` instances, executes the actual handler coroutine (`await process_task_season(...)`), and verifies the exact text rendered into `message.answer()` to guarantee zero-defect user-facing cards before reporting completion.
9. **Graceful Signal Handling in Combined Bot & WebUI Runners (`app.runner`)**:
   - When co-hosting aiogram polling and uvicorn in a single process under systemd, attach explicit `SIGTERM` and `SIGINT` signal handlers to the event loop. The handler must set `server.should_exit = True` and cancel the bot polling task immediately.
   - Without explicit signal handling, systemd reloads/restarts wait for the 90-second timeout before issuing `SIGKILL`, giving the false appearance of a frozen or unresponsive system.
10. **Proactive Entrypoint Deduplication vs Downstream Deduplication**:
   - Even when architecture documents only emphasize downstream deduplication (e.g. resource submission uniqueness and partial unique indexes), always guard admin task creation (`/add`, `/addtask`) with proactive duplicate checks (`find_duplicate_task`). Never allow duplicate active collection tasks for the same title, season, year, and media type to enter the database.
11. **Frontend Static Asset Delivery & Zero-Spinning Invariant (Domestic Network Accessibility)**:
   - When building WebUIs or admin dashboards (e.g. FastAPI Jinja2 / HTML templates on port 2082) accessed from mainland China (such as Telecom/Unicom domestic networks):
   - **NEVER** use overseas runtime JIT compiler scripts (e.g. `cdn.tailwindcss.com`) or slow CDNs (`cdnjs.cloudflare.com`). These domains experience severe packet loss, throttling, or timeouts in China, causing browsers to hang indefinitely with a spinning wheel or blank screen before rendering.
   - **MANDATORY**: Use precompiled CSS and JS assets hosted on reliable multi-region CDNs such as `cdn.jsdelivr.net` (e.g. `https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css` and `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css`), or serve them locally from `app/static/`.
   - Always load CSS via `<link rel="stylesheet">`, never via `<script src="...">`. Verify instant load times (<500ms) from local and external probes without blocking.
12. **Internal Punctuation Preservation in Media Titles vs Batch Delimiters**:
   - Chinese and international movie/TV titles frequently contain legitimate internal punctuation (e.g. 《我,许可 我许可》, 《你好，李焕英》, 《爱，死亡和机器人》, 《蜘蛛侠：平行宇宙》).
   - **NEVER** split single-line media inputs using generic commas (`,`, `，`) or semicolons (`;`, `；`), as this shatters titles into invalid fragmented tasks (e.g. `我` and `许可 我许可`).
   - **MANDATORY**: Preserve all commas, colons, and hyphens inside `title`. Require batch multi-item input to be separated by **newlines** (`\n`) or explicit pipe (`|`) symbols (e.g. `/add 繁花 | 漫长的季节 | 狂飙`).
13. **Cloud Link Content Deep Inspection vs Shallow Regex Matching**:
   - **NEVER** rely solely on domain regex patterns (e.g. `guangya`, `quark`, `mobile`) to validate resource submissions. Shallow regex only verifies link format; it cannot verify whether the link points to an empty folder, an expired share, non-media junk, or an entirely incorrect movie/show.
   - **MANDATORY**: Submissions must invoke a cloud content probe service that queries the share API/page to extract the true internal file list. The probe must verify:
     - Effective video count (filtering `.txt`, `.nfo`, `.jpg`, `.html` noise);
     - File naming structure: For movies, strict `中文名.年份` or `英文名.年份` matching the task record; for series/anime, MUST strictly enforce **`S0几` season identifier (e.g. `S01`, `S02`)** and episode tags (`E01`, `E151`) matching the submission claim.
     - File size and media metadata (4K/1080p, H265/H264, HDR/DV, Atmos/DDP5.1 audio, release group).
     - Empty, expired, password-mismatched, or non-matching shares must be rejected upfront during the user's submission turn.
14. **AI-Powered Intelligent Review & Dynamic API Switcher (`/setai`)**:
   - Complex release group filenames (bracket tags, romanized names, mixed languages) easily trip rigid regex parsers.
   - **MANDATORY**: Employ an AI Review Expert service (`AIReviewService`) that parses probed share metadata against task requirements:
     - Detects mismatches between submitted content and task target (flags high-risk title swaps);
     - Enforces `S0几` season tag presence for TV/Anime;
     - Summarizes video resolution, audio codecs, and file sizes;
     - Generates structured JSON verdicts (`passed`, `risk_level`, `confidence`, `audit_summary`, `reasons`).
   - **Dynamic API Switching (`/setai`)**: Provide Telegram admin commands/buttons to switch AI providers (Local CPA, Gemini, Claude, DeepSeek, custom OpenAI-compatible endpoints) and test connectivity in real-time with zero-downtime hot reloading.
15. **Human Review & Manual Scoring Gate (Strict No Unchecked Auto-Accept)**:
   - **NEVER** automatically set resources to `ACCEPTED`, decrement missing episodes, or award user contribution points immediately upon URL receipt. Unchecked auto-acceptance corrupts channel archives with bogus submissions.
   - **MANDATORY**: Validated submissions enter `REVIEW` state. The bot forwards a structured review card to administrators with inline approval buttons (`[✅ 审核通过并加分]`, `[❌ 驳回]`).
   - Only upon an explicit admin button press does the system transition to `ACCEPTED`, apply points, update missing episode counters, and broadcast the release card to the official Telegram channel.
16. **Telegram Bot Menu Dual-Scope Synchronization & Client Invalidation**:
   - Calling `bot.set_my_commands` with only `scope=BotCommandScopeDefault()` is insufficient for immediate admin client updates because Telegram clients aggressively cache menus locally per private chat.
   - **MANDATORY**: Whenever adding, modifying, or deleting bot commands, register to `BotCommandScopeDefault()` AND simultaneously iterate through all administrator IDs in `settings.ADMIN_TG_ID` registering to `BotCommandScopeChat(chat_id=admin_id)`. This forces the Telegram client to instantly invalidate local chat menu caches and render new commands upon entering `/` without requiring a client restart.
17. **Dynamic Schema Expansion & Application Startup Auto-Migration Invariant**:
   - When introducing new models or database tables (e.g. `SystemSetting`), never rely solely on ad-hoc CLI creation scripts or assume migrations were applied in all environments.
   - **MANDATORY**: The FastAPI / runner lifespan startup hook MUST include `async with async_engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)` to guarantee all newly declared tables and columns exist in live production on boot.
   - A missing table in production causes asyncpg `UndefinedTableError`, which crashes handler coroutines unhandled and causes commands (e.g. `/setai`) to appear unresponsive without any feedback message to the user.
18. **Command Consolidation & Anti-Duplication Principle**:
   - Do NOT create separate, redundant top-level bot commands (e.g. `/model`) when an existing unified command (e.g. `/setai`) already manages that domain.
   - Consolidate interactive pickers, paginated buttons, and parameter shortcuts inside the primary command to keep the Telegram menu clean, focused, and intuitive. Always remove redundant aliases from `setup_bot_commands` to prevent user menu clutter.
19. **TMDB Rate Limiting & Strict Request Boundary (<= 40 req/s)**:
   - The TMDB API enforces strict limits on query volume and concurrent spikes. System queries MUST enforce a hard rate limit boundary strictly $\le$ 40 requests per second.
   - **MANDATORY**: Implement an asynchronous sliding-window rate limiter (`TMDBRateLimiter`) with `asyncio.Lock` and timestamp deque to meter requests. Set default operational threshold to 35 req/s to provide safety headroom against clock drift.
   - **Graceful 429 Backoff**: When receiving HTTP 429, inspect the `Retry-After` header and await before retrying; do not flood the upstream API.
20. **TMDB Dual Authentication & Flexible Query Fallbacks**:
   - Support both TMDB v4 Bearer Access Tokens (`Authorization: Bearer <token>`) and v3 API Keys (`api_key=<key>`). Prioritize v4 bearer headers for enhanced query security.
   - **Year Filter Fallback**: TMDB year matching is strict. If searching with a release year (e.g. `2024`) returns 0 results, automatically retry once without the year parameter before failing over to manual review, mitigating mislabeled year discrepancies in upstream submissions.
21. **Pydantic Settings `.env` Working-Directory Independence**:
   - Specifying `env_file=".env"` in Pydantic `SettingsConfigDict` resolves relative to the current execution directory (`os.getcwd()`), causing settings to silently fail to load if Python scripts, tests, or sub-processes run from outside the repository root.
   - **MANDATORY**: Anchor the `.env` path using `Path(__file__).resolve().parent.parent / ".env"` so configuration is consistently loaded across CLI scripts, pytest fixtures, and systemd units.
22. **Submission Deletion, Points Revocation & Task State Rollback Invariant**:
   - When administrators identify an erroneous, fraudulent, or malformed submission (whether still in `REVIEW` or already `ACCEPTED` and published):
   - A dedicated deletion capability (`/del`, direct `/del <id/batch_id>`, inline `[🗑️ 彻底删除]` / `[🗑️ 撤销并删除此投稿]`, and REST API `/api/submissions/{target}/delete`) is mandatory.
   - **Transaction-Safe Rollback**:
     - Deleting an accepted submission MUST automatically revoke awarded points from the submitter user's account (`user.points = max(0, user.points - revoked_points)`).
     - If the task was previously marked `COMPLETED` due to this submission, recalculate missing episodes (or movie accepted status); if gaps now exist, **automatically revert `task.status` from `COMPLETED` back to `ACTIVE`** so the community can resume collecting the missing media.
23. **Deterministic Filename Season Format Pre-Check & Upfront Direct Rejection**:
   - **LLM Context Pitfall**: When inspecting cloud share contents, an LLM reviewer may falsely pass a non-standard submission if the outer folder contains a season title (e.g. `《师兄啊师兄 第一季 (2023)》`), even if internal video files are named with non-standard pure numbers (e.g. `151~4K [HEVC.AAC]...mp4`, `151.mp4`, `第151集.mp4`).
   - **MANDATORY**: For TV / ANIME submissions, every individual video file's **own filename** MUST contain a standard season tag (e.g. `S01`, `S02`, `第01季`).
   - **Deterministic Pre-Validation**: Enforce a deterministic regex check (`r'(?:[Ss]\d{1,2}|第\s*\d{1,2}\s*季)'`) on all probed video filenames. If any file lacks a season tag, mark `passed=False`, `has_season_tag=False`, and `risk_level="HIGH"` deterministically before/alongside the LLM audit.
   - **Upfront Direct Rejection (Noise-Free Admin Queue)**: Submissions that fail AI/deterministic format validation MUST be rejected immediately in the submitter's Telegram session with explicit rejection reasons and standard naming guidelines. Do NOT create `REVIEW` records or send review cards to administrators for non-standard formats.
24. **User Daily Quota Verification & Timezone Boundary (Beijing UTC+8)**:
   - When calculating daily limits (100 GB / 20 submissions), always calculate the start of the day anchored to **Beijing Time (`UTC+8`)**: `now_beijing.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)`.
   - Never use naive UTC midnight, as that shifts the user's natural day boundary to 08:00 AM CST and confuses community members.
25. **User Precision Targeting by Numeric ID or @Username with Points Audit Trail**:
   - For administrative commands (`/deduct`, `/clearpoints`, `/addpoints`, `/user`), always support both raw numeric Telegram ID (e.g. `8586984520`) and @username (e.g. `@testuser`).
   - Every single balance mutation MUST log to `point_logs` with the actor (`operator_tg_id`), action type, and reason. Point balances must never underflow below `0.0`.
26. **PostgreSQL Manual Table Creation & Application User Ownership Invariant**:
   - When executing raw DDL or psql scripts on `media_bot_db` outside Alembic migrations (e.g. `CREATE TABLE point_logs`), the default owner is `postgres`.
   - **MANDATORY**: Always explicitly transfer table ownership and sequence permissions to the application user (`mediabot`):
     ```sql
     ALTER TABLE <table_name> OWNER TO mediabot;
     GRANT ALL PRIVILEGES ON TABLE <table_name> TO mediabot;
     GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mediabot;
     ```
   - Failing to do so causes asyncpg `InsufficientPrivilegeError: permission denied for table ...`, which silently crashes bot command handlers without returning an error message to the Telegram chat.
27. **Administrative Command Parameter Tolerance & Interactive Auto-Fallback**:
   - Administrators frequently send shorthand commands without secondary arguments (e.g. `/deduct 7898049885` without a numeric score, or `/user` without a target ID).
   - **MANDATORY**:
     - For queries like `/user`, if invoked without an argument, default to querying the caller's own admin profile (`message.from_user.id`).
     - For mutations like `/deduct <target_user>`, if the score argument is omitted, do NOT merely reply with syntax help. Instead, locate the target user and present interactive inline buttons (`[➖ 扣0.5分]`, `[➖ 扣1分]`, `[➖ 扣2分]`, `[🔄 一键清零]`) so the administrator can complete the action in one tap.
     - Always wrap command handlers with top-level `try...except` blocks that send actionable Telegram error messages, preventing unhandled exceptions from resulting in apparent bot unresponsiveness.
28. **Telegram User Identification Dual-Track Invariant (`full_name` vs `username`)**:
   - Many Telegram users only set a Display Name (`first_name` / `last_name`) and do NOT configure a public `@username`. Storing or querying only `username` causes user inspection cards to display a false `未设置用户名`.
   - **MANDATORY**:
     - The `users` table MUST persist both `username` and `full_name`.
     - Whenever handling submissions or rendering admin inspect cards (`/user`), invoke `bot.get_chat(target_uid)` to dynamically probe the latest Telegram nickname (`chat.first_name + chat.last_name`) and handle (`chat.username`), updating the `users` record on-the-fly.
     - Card rendering format:
       - Both present: `<b>{full_name}</b> (@{username})`
       - Only display name: `<b>{full_name}</b> <i>(未设置@用户名)</i>`
       - Fallback: `ID: <code>{user_id}</code>`
29. **Admin Command Consolidation & Inline Interactive Card Architecture (命令精简与统一入口)**:\n   - Spreading related administrative actions across multiple disjoint commands (e.g. `/deduct`, `/clearpoints`, `/addpoints`, `/user`, or `/ai` and `/setai`) creates user cognitive load, command menu (`set_my_commands`) clutter, and interaction conflicts.\n   - **MANDATORY**:
     - Consolidate all user inspection, penalty, reward, and reset workflows into a single unified `/user` command.
     - Consolidate all AI configuration, testing, and model switching into a single unified `/ai` command.
     - Keep legacy command aliases (`/deduct`, `/clearpoints`, `/addpoints`, `/setai`) routed seamlessly to their unified handler via `@router.message(Command("user", "u", ...))` or `@router.message(Command("setai", "ai"))` to preserve muscle memory, but **NEVER** expose the redundant aliases in the `bot.set_my_commands` menu list.
     - Provide both zero-tap inline keyboard operations (`[➖ 扣分]`, `[➕ 奖分]`, `[🔄 清零]`, `[🔃 刷新]`) with in-place card editing (`edit_text`), and instant CLI argument parsing (`/user <target> -1 [reason]`, `/user <target> +2 [reason]`, `/user <target> clear [reason]`).
30. **Three-Tier Independent Counting Standard, Task Difficulty Bounty & Exclusive Timed Task Invariant**:\n   - **3 Orthogonal Criteria (0.5 pts each, up to 1.5 pts base)**:\n     1. Standard naming format: +0.5 pts\n     2. Folder contains verified TMDB ID: +0.5 pts\n     3. Video file contains verified TMDB ID: +0.5 pts\n     - Combination mapping: 1 met = 0.5, 2 met = 1.0, 3 met = 1.5 pts. Non-standard naming format is rejected upfront with 0 pts.\n   - **Chinese Folder Standard Specification & Tap-to-Copy Prompt (`build_standard_folder_name`)**:\n     - **TV / Anime Series**: `剧名(年份)第X季 分辨率 {tmdbid-ID}`\n       - Examples:\n         - `不良一族寻爱记(2025)第二季 1080P {tmdbid-218231}`\n         - `聪明镇(2026)第一季 4K {tmdbid-208392}`\n         - `飞到我心上(2026)第一季 4K {tmdbid-283921}`\n         - `师兄太稳健(2026)第一季 4K {tmdbid-192837}`\n         - `二十世纪电气目录(2026)第一季 1080P {tmdbid-102938}`\n     - **Movie**: `片名(年份) 分辨率 {tmdbid-ID}`\n       - Examples:\n         - `怒火(2026) 4K {tmdbid-1363974}`\n         - `消失的人(2026) 4K {tmdbid-1363974}`\n     - **Tap-to-Copy Interactive Prompt**: Upon TMDB confirmation during submission, the bot immediately outputs the pre-rendered standard folder name inside a `<code>` block so submitters on mobile can tap once to copy and paste directly into their cloud drive, ensuring 100% compliant folder names and effortless +0.5 point bonuses.\n   - **Task Difficulty Bounty (`bounty_points`: 0.0 ~ 15.0)**:\n     - Admin can assign extra bounties during task creation (via `/add <title> +<points>` or interactive inline buttons in `/add` and `/addtask`).\n     - Tasks in `/tasks` list highlight `[🔥+N分]`.\n     - Upon approval, the submitter receives `naming_points (0.5~1.5) + bounty_points (1~15)`, fully itemized across admin review cards, user notifications, channel announcements, and `point_logs` audit trail.\n   - **Timed Task Locking & Expiration Penalty**:\n     - Tasks flagged with `is_timed=True` require exclusive claiming from `/tasks` (`[⚡ 立即领取并开始]`).\n     - Once claimed, the task is locked for 30 minutes (`claimed_by_tg_id`, `claim_expires_at`).\n     - If the user fails to submit valid resources before `claim_expires_at`, background worker penalizes them by deducting 1.0 point (`TIMED_TASK_TIMEOUT_PENALTY`), sends a warning DM, and unlocks the task for others.
31. **Group Membership Authorization Middleware & ID Normalization Invariant**:
   - **Protection Boundary**: To protect the bot from spamming, multi-account farming, and unauthorized public abuse, all private chat commands and callback queries must pass through an outer middleware (`GroupMembershipMiddleware`) verifying membership in the designated community group.
   - **Telegram Supergroup ID Normalization Invariant**:
     - Community group IDs provided by administrators/users often come as positive 10-digit numbers (e.g. `3758628375` or `4431514859`).
     - Telegram Bot API requires 64-bit signed chat IDs with the `-100` prefix for supergroups (e.g. `-1003758628375`).
     - **MANDATORY**: Implement robust normalization `normalize_group_id`: if an integer or numeric string is positive, prepend `-100`; preserve already prefixed negative IDs and `@usernames`.
   - **Admin Bypass & Zero-Latency TTL Caching**:
     - Administrators dynamically parsed from `ADMIN_TG_ID` bypass group checks unconditionally.
     - Verified regular members are cached in memory with a 5-minute TTL (`300s`) to ensure 0-latency interactive response across `/tasks` pagination and submission dialogs without exhausting Telegram Bot API rate limits.
   - **Interactive Gate Card & Instant Re-verification**:
     - Intercepted non-members receive an explanatory card with direct group link (`[👉 点击加入群聊]`) and an instant re-verification callback button (`[🔄 我已加入，点击验证]`).
     - Clicking the verification button bypasses in-memory cache to execute a real-time `get_chat_member` probe, instantly unlocking all bot commands upon successful joining.
32. **Community Media Request, Point Deduction & Balance Ledger Invariant (`/seek`, `/myrequests`)**:
   - **Shared Economy Standard**: Points earned from submissions are universally spendable to request desired media content.
   - **Pricing Formula**:
     - Movie: Flat `2.0` points.
     - TV / Anime series: `0.5` points per requested episode (`0.5 * (total_episodes - start_episode + 1)`).
   - **Atomic Balance Deduction**: Check user's available balance before creating task. Deduct points inside the database transaction and record a `PointLog` with `action='MEDIA_REQUEST_DEDUCT'`.
   - **Zero-Accepted Cancellation & 100% Refund**: Allow users to cancel active requested tasks via `/myrequests` only if no submissions have been `ACCEPTED` yet, issuing an instant 100% point refund (`MEDIA_REQUEST_REFUND`).
   - **Task Completion DM Alert**: When all episodes or movies of a requested task reach `ACCEPTED` and the task transitions to `COMPLETED`, automatically dispatch a Telegram private message to `requester_tg_id`.
   - **Full Database Ledger Audit & Statistical Breakdown ("加了减了 数据库统计")**:
     - Aggregate all-time points income (`total_earned`: `SUBMISSION_APPROVE` + `ADMIN_ADD`), request expenses (`total_spent_request`: `MEDIA_REQUEST_DEDUCT`), refund returns (`total_refunded`: `MEDIA_REQUEST_REFUND`), and penalties (`total_penalized`: `ADMIN_DEDUCT` + `TIMED_TASK_TIMEOUT_PENALTY` + `SUBMISSION_REVOKE`).
     - Expose these aggregated statistics along with recent transaction log entries in user-facing `/points` and admin `/user <id>` cards.
33. **Command Precedence & FSM Escape Hatch Invariant**:
   - **Root Cause & Anti-Pattern**: If stateful text message handlers (e.g. `SubmissionFSM.share_url`, `episodes`, `SeekMediaFSM.title`, `AddTaskFSM.title`) consume arbitrary messages without filtering slash commands, user commands like `/cancel`, `/tasks`, `/points`, `/seek` get trapped and processed as invalid links ("无法识别该网盘链接") or bad episode inputs, completely breaking escape paths.
   - **Mandatory 4-Layer Safeguard Architecture**:
     1. **Router Registration Priority**: `common.router` (containing `/cancel`, `/tasks`, `/points`, `/start`) MUST be registered before submission and stateful wizard routers (`dp.include_router(common.router)` -> `admin.router` -> `seek.router` -> `submission.router`).
     2. **Magic Command Filter on FSM Handlers**: All FSM text input handlers MUST include `~F.text.startswith("/")` so that slash commands automatically bypass the state handler and fall through to top-level command handlers.
     3. **State Cleanup in Command Entrypoints**: All top-level command handlers (`cmd_cancel`, `cmd_tasks`, `cmd_points`, `cmd_start`, `cmd_seek`, `cmd_myrequests`, `cmd_quick_add`, `cmd_addtask`, `cmd_del`, `cmd_user`) MUST clear active FSM state (`await state.clear()`).
     4. **Defensive In-Handler Command Guard**: Every FSM handler must defensively inspect `if raw_text.startswith("/")`: if it is `/cancel`/`/exit`/`/quit`, immediately clear state and answer `"❌ 已取消当前操作"`, preventing any infinite loop.
34. **Cloud Platform Selection Interface Separation Invariant ("接单后接口分开，用户选择网盘后投稿")**:
   - **Step Separation**: After claiming a task and resolving TMDB binding/episodes, the bot must NOT directly dump a raw link prompt. It transitions to `SubmissionFSM.cloud_choice` (`proceed_to_cloud_choice_step`).
   - **Interactive Platform Grid**: Renders an inline keyboard displaying all enabled cloud storage platforms (🦆 光鸭, 📱 移动, ⚡ 夸克, 📦 阿里, 🐾 百度, 📁 115, 🚀 迅雷, ☁️ 天翼).
   - **Targeted Prompt & Re-selection**: Clicking a cloud platform locks `chosen_cloud` into state data, prompts with targeted instructions for that specific cloud, and provides `[🔄 重新选择网盘]` (`reselect_cloud`) and `[❌ 取消投稿]` (`cancel_submission`) escape buttons.
   - **Smart Auto-Adjustment & Resilience**: When a link is submitted, if it matches the selected cloud, it proceeds to inspection. If the link belongs to another supported cloud, the system gracefully auto-adjusts (`chosen_cloud=cloud_cfg.name`), notifies the user, and proceeds smoothly without failing. If invalid, it displays an error card with the `[🔄 重新选择网盘]` button.
35. **Channel-Bound Auto-Transfer & Master Folder Architecture ("一号方案：对应频道原生直连转存")**:
   - **Zero-Daemon Native API Pipeline**: When the user only needs auto-transfer, deduplication, and official share generation, **NO external mounting service (OpenList/AList) is required**. The bot connects directly to cloud drive APIs (Guangya, Mobile 139, etc.) using configured tokens. This eliminates daemon memory overhead, keeps ports clean, and executes transfers in the cloud without server bandwidth consumption.
   - **Per-Channel Routing**: Submissions approved in a bound channel automatically route to the user's corresponding cloud drive account (Guangya channel -> user's Guangya drive; Mobile channel -> user's Mobile drive).
   - **Master Folder Hierarchy ("影视转存总目录")**: Automatically creates a root master folder (`影视转存总目录`, configurable via `/setcloud`) on the user's cloud drive.
   - **Folder-Level Deduplication**: Target directory inside the master folder is unified to `影视转存总目录/剧名(年份)第X季 分辨率 {tmdbid-ID}`. Reuses existing directory on subsequent batches.
   - **File/Episode-Level Deduplication**: Probes destination folder, skips already existing episodes, and transfers only incremental new episodes.
   - **Auto-Transfer & Decoupled Notification**: Background transfer saves media to the master folder and filters duplicates; channel announcement is published with the original submission share link and transfer status without generating new public share links (`auto_share=False`).
36. **Option 1 (Native Direct Transfer) vs Option 2 (OpenList Mount for Emby Streaming)**:
   - **Option 1 (Active Baseline - 一号方案)**: Direct Python cloud adapter transfer. Best for channel archiving, cloud collection, and automated link sharing. Minimalist, zero local storage, zero port allocation.
   - **Option 2 (Emby Mount & Streaming - 挂载方案)**: OpenList (AList fork on port `12666` or `39637`) is deployed ONLY when Emby needs to read cloud drives as local directories / WebDAV for direct streaming. If streaming is not required, OpenList should remain stopped and uninstalled to adhere to the host's minimalist, zero-waste operational principles.
37. **Channel Broadcasting & Contributor Notifications upon Ingestion Approval (审核收录全自动多频道广播与投稿者通知规范)**:
   - **Dedicated Cloud Channel Broadcasting**: When submissions are accepted by administrators (`admin_approve`), the system automatically invokes `ChannelService.publish_submission`:
     - Routes the formatted announcement card to the dedicated cloud storage channel (e.g. Guangya channel `-1004387965244`, Mobile channel `-1004410413711`).
     - Renders rich metadata: title, year, season/episodes, cloud hashtag, official transfer link / original share link, resolution/encoding, size, and `@submitter` credit.
   - **Submitter DM Notification**: Sends private message to `submitter_id` announcing approval (+points awarded) and confirming publication.
   - **Admin In-Place Status Update**: Admin review card updates in-place to `• 状态: 📢 已收录并广播到【#网盘】频道`.
48. **Mandatory Filename Title Presence Check & AI Review Rule #0 (文件名剧名/片名强制存在性与防无名文件误放行规范)**:
   - **Root Cause & Vulnerability**: Rigid regexes that only look for `SxxExx` or resolution tags (`1080p`) risk approving nameless files such as `S01E01.mp4`, `S01E01.1080p.mkv`, `4K.S01E01.mp4`, `1080p.mp4`, `(2026).S01E01.mp4`, or generic placeholders (`movie.mp4`, `video.mp4`).
   - **MANDATORY Multi-Layer Validation**:
     1. **Deterministic Pre-Validation (`MediaNamingValidator.validate_single_file`)**:
        - Strips TMDB IDs, years, quality tags, and delimiters via `clean_title_candidate`.
        - For TV/Anime: The prefix before `SxxExx` MUST contain a valid alphanumeric or Chinese title.
        - For Movies: The base filename stripped of year/specs MUST contain a valid movie title and NOT match `GENERIC_TITLES` (`movie`, `video`, `film`, `test`, `demo`, `正片`, `完整版`, `高清`, `未命名`).
        - Nameless or generic placeholder files are immediately rejected upfront with `is_valid=False`, `points_tier=0.0`, and an explicit rejection reason.
     2. **AI Review Prompt Rule #0**:
        - Explicitly marks title presence as Rule #0. Files without clear show/movie titles matching the task must be rejected (`passed=false, risk_level="HIGH"`).
38. **Daily 20:00 CST Submission Leaderboard Broadcast to Bound Group Chats (每晚北京时间20:00定时推送群聊投稿排行榜，取消频道推送)**:
   - **Target Dedicated Community Group**: Pushes daily consolidated leaderboard directly to the authorized community group (e.g. `@shangpian888` / `-1003758628375` from `REQUIRED_GROUP_ID`). Does NOT push to individual media storage channels, keeping storage channels clean and focused.
   - **4-Section High-Density Leaderboard Card Structure**:
     1. 👑 **【今日投稿先锋】**: Top daily contributors (00:00 ~ 20:00 CST) with accepted submission counts and earned points.
     2. 🌟 **【累计贡献荣誉总榜】**: All-time top contributors across the platform with total accepted counts and current point balance.
     3. 📊 **【专区收录概况】**: Today's new additions (`+N 部/集`), historical total archives, and unique contributing member count.
     4. 💡 **【参与指引】**: Friendly prompt guiding members to `/tasks` to claim tasks and earn points.
   - **Timezone & Deduplication Lock (`Asia/Shanghai` + `system_settings`)**:
     - System background worker `daily_leaderboard_worker` monitors CST time every 20s.
     - Triggers at `hour == 20` (20:00 CST) and writes the current date (`daily_leaderboard_pushed_YYYY-MM-DD`) to the `system_settings` table, guaranteeing exactly-once delivery even across service restarts.
   - **Admin Instant Push Command (`/pushleaderboard`)**:
     - Provides `/pushleaderboard` command (synced via `set_my_commands`) allowing administrators to manually trigger, test, and inspect leaderboard distribution to bound group chats anytime.
39. **Strict Two-Level Directory Routing & Cloud File Moving Invariant (两级目录严格路由与零散文件归位)**:
   - **Strict Subdirectory Enclosure**: Media files must NEVER be saved directly in the master folder root (`📁 影视转存总目录`). Cloud transfer adapters MUST first find or create the standard TMDB subfolder (`剧名(年份)第X季 分辨率 {tmdbid-ID}`) and pass its ID as the destination `parentId`.
   - **Guangya Pan File Moving API**: If files need to be relocated or reorganized into standard subdirectories, call `POST /userres/v1/file/move_file` with `{"fileIds": [...], "toParentId": "<dest_folder_id>", "parentId": "<dest_folder_id>"}` (Note: `/userres/v1/file/move` returns HTTP 404).
47. **Guangya Pan 2-Hour JWT Expiration & SSO Automatic Refresh Invariant (光鸭Token 2小时过期与SSO无感自动续期规范)**:\n   - **401 Failure Root Cause**: Guangya access tokens are short-lived JWTs with a strict 2-hour lifespan (`exp - iat = 7200s`). Storing a static `access_token` causes subsequent auto-transfers to fail with `HTTP Error 401: Unauthorized`.\n   - **MANDATORY SSO Refresh Pipeline**:\n     - `cloud_configs.auth_token` supports storing a long-lived `refresh_token` (typically starting with `gy.`) or full token JSON (`{\"access_token\": \"...\", \"refresh_token\": \"...\"}`).\n     - Prior to executing transfers or folder probes, `GuangyaTransferAdapter` decodes the JWT payload to inspect `exp`. If the token is missing, non-existent, or expires in <60s, it invokes `POST https://account.guangyapan.com/v1/auth/token` with `client_id=aMe-8VSlkrbQXpUR` and `grant_type=refresh_token`.\n     - Upon receiving the refreshed token pair, the adapter updates both its runtime config and commits the new credentials to the `cloud_configs` database table asynchronously, guaranteeing uninterrupted zero-touch background transfers without manual intervention.\n     - Users can provide the `refresh_token` string manually or it can be automatically fetched if they authenticate fully. Do not confuse `access_token` with `refresh_token`. The `refresh_token` string for GuangyaPan typically starts with `gy.`.
40. **Emby/Jellyfin 2-Level Subfolder Taxonomy & TMDB Classification Invariant (`MediaClassifier`)**:
   - The master transfer directory (`📁 影视转存总目录`) contains 2 top-level categories: `电视剧` (10 subcategories: 儿童, 国产剧, 国漫, 纪录片, 欧美动漫, 欧美剧, 其他剧, 日番, 日韩剧, 综艺) and `电影` (6 subcategories: 动画电影, 华语电影, 欧美电影, 其他电影, 日韩电影, 外语电影).
   - Auto-transfer resolves TMDB details (`genres`, `origin_country`, `original_language`) and routes media directly into its 2-level destination folder (e.g. `电视剧/国漫/师兄啊师兄(2023)第一季 4K {tmdbid-218642}`).
41. **Metadata Downloader, Strict <= 30 req/s Rate Limit & Zero-Conflict Review Lock Invariant (`download_metadata.py` & `TaskReviewLock`)**:
   - Downloads Kodi/Emby standard `nfo` (`tvshow.nfo` / `movie.nfo`), `poster.jpg`, `fanart.jpg`, and actor avatars into `.actors/*.jpg` under each media folder.
   - Strictly throttled $\le$ 30 requests/second using async sliding-window limiter.
   - Protected by `TaskReviewLock` (`/tmp/media_bot_task_review.lock`): Task submission & admin review have absolute priority; scraping yields/defers during review, guaranteeing zero competition.
   - Admin command `/metadata [id/all]` is registered to Telegram command menu via `set_my_commands`.
42. **Manual Task Deletion & Cascading Refund/Revocation Invariant (`/deltask` & `TaskService.delete_task`)**:
   - Administrators can manually unpublish and delete active or obsolete collection tasks via `/deltask [id/title]` or an interactive inline button menu.
   - **Community Request Refund**: If the deleted task was initiated via user request (`is_request=True`), automatically refund deducted points to the requester and record `MEDIA_REQUEST_REFUND` in `point_logs`.
   - **Cascade Points Revocation & Resource Deletion**: If any submitted resources under the task reached `ACCEPTED`, automatically revoke awarded points from submitters (`SUBMISSION_REVOKE`), delete all associated `Resource` rows, and remove the `Task` record to prevent orphan data.
   - **Interactive Shortcut in `/tasks`**: For administrators, the `/tasks` list view provides an immediate `[🗑️ 管理 / 下架删除任务]` button to streamline task management.
43. **Historical Submissions Backfill & Share Content Fallback Invariant**:
   - When executing batch backfills of existing accepted submissions into cloud drives, transfer adapters must dynamically fall back to querying public share file lists when `Resource.file_names` is missing or empty.
   - Recursive directory traversal in share APIs must gracefully preserve folder/file IDs, and authentic TMDB IDs must be linked so `MediaClassifier` routes works to their exact 2-level destination directory before invoking `download_metadata.py --all`.
44. **Silent In-Place Transfer Status & Zero Extraneous Push Notifications (审核卡片静默就地更新，取消额外转存推送)**:
   - When submissions are approved and auto-transferred into private cloud storage, do NOT generate redundant push messages to either review chats or administrator private DMs ("取消转存成功推送，用不上了").
   - **MANDATORY**: Keep the review feedback minimalist and clean:
     1. The review card in the chat updates in-place (`edit_text`) to display `• 状态: 🔒 静默转存入库完成 (无额外推送消息)`.
     2. The inline button callback answers with a lightweight toast (`call.answer("✅ 审核通过！已完成转存入库")`), generating zero additional message noise.
45. **Group Chat Complete Silence & Private Chat Interactive Boundary Invariant (群聊完全静默只发榜单，私聊独立交互)**:
   - **Complete Group Silence ("在群聊静默只发送排行榜")**:
     - In all group, supergroup, and channel chats (e.g. `@shangpian888` / `-1003758628375`), the bot drops all incoming messages, commands (`/tasks`, `/points`, `/seek`, `/add`, `/start`, etc.), fallback text, and callback queries without replying. It NEVER speaks, chats, or responds to user messages in groups.
     - **Only Allowed Group Activity**: Pushing the daily consolidated leaderboard card at 20:00 CST (`daily_leaderboard_worker`), or admin manual push (`/pushleaderboard` triggered from private chat).
     - **Passive Member Presence Cache**: When a member sends a message in the required group, `GroupMembershipMiddleware` updates `_MEMBERSHIP_CACHE[user_id] = time.time() + CACHE_TTL_SECONDS` in memory (saving redundant Telegram Bot API calls when the user later interacts in private chat) and returns immediately (`return`) without dispatching to any handler.
   - **Telegram Command Scope Hygiene**:
     - `BotCommandScopeAllGroupChats` commands are deleted via `delete_my_commands` so typing `/` in group chats never shows bot commands in the autocomplete menu.
     - `BotCommandScopeAllPrivateChats` and admin `BotCommandScopeChat` scopes hold the active command set.
   - **Private Chat Exclusivity ("在私聊进行交互")**:
     - All user and admin workflows (browsing `/tasks`, submitting cloud links, `/seek` requests, checking `/points`, `/user` management, AI/cloud configuration) take place strictly in private chat. Non-members attempting to use the bot in private chat are gated by `GroupMembershipMiddleware` and prompted to join the designated group.
46. **FSM Text Message Fallback Swallowing Pitfall & `default_state` Filter Invariant (FSM状态机文本被兜底静默吞噬排查与过滤规范)**:
   - **Root Cause & Dispatcher Bug**: When declaring a catch-all plain text handler (e.g. `fallback_text_handler` offering tips when a user types random text), registering `@router.message(F.text, ~F.text.startswith("/"))` without an explicit state filter will cause aiogram to match the message regardless of whether the user is in an active FSM conversation.
   - **Silent Handler Halting**: Even if the handler checks `if current_state is None:` and immediately returns `None` on active states, aiogram marks the update as handled by that handler. Propagation stops, preventing subsequent routers or state handlers (e.g. `AddTaskFSM.title`, `SubmissionFSM.episodes` processing `醒来` or `1-22`) from receiving the message, creating the false appearance of an unresponsive bot.
   - **Mandatory 2-Fold Fix**:
     1. **Explicit `default_state` Filter**: All generic text fallback handlers MUST be constrained with `default_state`: `@router.message(default_state, F.text, ~F.text.startswith("/"))`, guaranteeing they are strictly evaluated ONLY when no FSM state is active.
     2. **Router Registration Sequence**: `dp.include_router(common.router)` containing fallback handlers MUST be registered LAST after all domain-specific routers (`admin.router`, `seek.router`, `submission.router`).

50. **Guangya Pan Refresh Token Retrieval vs Access Token & Opaque Composite Share-ID Parsing**:
   - The token fetched using the devtools payload from `account.guangyapan.com/v1/auth/token` with `"expires_in": 7200` is the `access_token` and expires in 2 hours.
   - The true `refresh_token` is also in the same JSON response under the `refresh_token` key (starts with `gy.`). Ensure you instruct the user to specifically extract this `refresh_token` field from the Network tab (Fetch/XHR responses) when providing token credentials, not the whole payload or just the access token.
   - **Opaque Composite Share-ID Contract (Current Web Client)**: Guangyapan's current web client sends the complete `/s/<path-segment>` as a string `shareId` (for example, `数字ID_中间短码_末段`).
     - **MANDATORY**: Preserve the entire path segment, including the final underscore component. Do not infer that the last component is a password and do not strip it before calling `get_share_summary` or `get_share_access_token`.
     - A code is supplied only when it is explicit in a `code`/`pwd` query parameter or in adjacent text such as `提取码: XXXX`; `#/share/` URL fragments are ignored by URL parsing.
     - Sending only the numeric prefix or an inferred split ID can return HTTP 200 with a business message such as `分享链接错误`; validate that the response contains a dictionary `data` object (and, for access-token calls, a non-empty `accessToken`) before proceeding.
     - Keep the original URL intact for user-facing records, but pass the cleaned URL—not a free-form description—to the parser/API. See `references/guangya_share_link_and_user_directory.md` for the reproducible protocol probe and regression contract.
   - **API Read and Directory-Response Contract**: Guangya reads can have transient TLS/read timeouts, so use bounded timeouts and bounded retries for operations that occur before any cloud-side side effect; do not treat one handshake/read timeout as a completed transfer failure, but never blindly replay after a restore request may have been accepted. The user-drive `get_file_list` request must send `parentId`, `pageNum`, and `pageSize` only (never `page`). An existing empty directory may legitimately return exactly `data={}`; interpret only that exact empty object as an empty list. Reject `data=None` or a payload containing `total` without `list`, preserving fail-closed behavior for incomplete responses. Public-share listing is a separate contract and may use `page`.
   - **AI Review Over-Failing on Extra Episodes**: Submitting a link that contains MORE episodes than the task requested (e.g. the link contains S01E01-E16, but the task only requested E03-E08) or even FULL MULTI-SEASON BUNDLES (e.g., S01 and S02 combined when the task only wants S02) is completely valid. The AI Review prompt MUST instruct the model to accept the submission (extract the full list of detected episodes, `passed=true`) rather than failing it for a length mismatch or having extraneous content. The backend deduplication script is responsible for extracting the needed pieces.
   - **Strict Target Season Requirement (Anti-Spam)**: While multi-season bundles are allowed, the AI Review prompt MUST strictly enforce that the requested task season IS ACTUALLY PRESENT in the bundle. If a task requests `S02`, and the user submits a bundle that ONLY contains `S01`, the AI MUST instantly reject it (`passed=false, risk_level="HIGH"`) as "挂羊头卖狗肉" (bait and switch).
   - **Transfer Deduplication with Strict Episode/Season Filtering**: When auto-transferring (`cloud_transfer_service.py`), the adapter MUST parse the file's season and episode from its name. If the file belongs to a DIFFERENT season than the task requested, or an episode outside the `accepted_episodes` set, it MUST be skipped (`skipped_files.append(f)`). This prevents polluting the destination cloud drive with unwanted seasons/episodes when a user submits a massive multi-season bundle.

51. **Oracle Cloud (OCI) VCN Port Exposure**:
   - When migrating to Oracle Cloud (OCI) or provisioning services on it, opening ports via `iptables` locally on the Ubuntu host is insufficient.
   - Oracle Cloud imposes an external hardware/VPC firewall layer called the "Security List" (VCN Security List / 安全列表).
   - Instruct the user to log into the Oracle Cloud web console and manually add an Ingress Rule (`0.0.0.0/0` -> Target TCP Port) to allow inbound traffic to reach the WebUI or APIs.

52. **Oracle Cloud Server Migration Safety & Git Initialization Invariant**:
   - When migrating a project from one server to another using `rsync`, DO NOT blanket exclude `.git` unless you intend to completely break version control on the new host.
   - If migrating to a fresh host and completely destroying the old host, omitting `.git` requires you to immediately run `git init`, `git remote add origin`, and a commit on the new host to restore tracking. Otherwise, the project is left untracked.
   - Run tests (`pytest`) and verify databases/services on the new host BEFORE deleting the old host to prevent data or source loss.

53. **WebUI Authentication & Security (网页控制台安全)**:
   - When deploying WebUI dashboards or APIs via FastAPI, they MUST NOT be publicly accessible without authentication.
   - Even if the interface is read-only, exposing sensitive data (user telegram IDs, original share links) to the internet is a severe vulnerability.
   - **MANDATORY**: Implement HTTP Basic Auth (via `fastapi.security.HTTPBasic`) on the root FastAPI application or sensitive `/api` routes.
   - Provide a default secure credential (e.g., `admin`:`admin888`) and document it in the deployment guide or `.env` configuration.

54. **Guangya Real Transfer Verification & Fail-Closed Routing (光鸭真实转存核验与失败熔断规范)**:
   - **Credential Lifecycle**: Store Guangya credentials as a JSON pair (`access_token` + `refresh_token`) when possible. Before transfer, decode the JWT and refresh through `POST https://account.guangyapan.com/v1/auth/token` when missing/expired; persist the returned pair, including a rotated refresh token. Never log or paste either token into test output.
   - **Strict Selection Contract**: For a multi-season or superset share, the adapter MUST pass `task.season` into `_deduplicate_files` as `task_season=task.season`, together with the accepted episode set. Only files matching the requested season and accepted episodes may reach `restore_share`; files from other seasons or unapproved episodes must be skipped.
   - **Fail Closed on Directory Lookup**: `_find_or_create_folder` must retry transient Guangya API/SSL/read timeouts (bounded retries, e.g. three attempts). If the master, top-level, sub-level, or media folder cannot be confirmed, stop with a failed transfer result. NEVER fall back to the master folder or another parent, because that silently creates a wrong taxonomy path.
   - **Post-Transfer Proof**: `restore_share` is asynchronous. A successful HTTP response/result object is not enough. Poll `get_file_list` using `pageNum` (not `page`) until the target folder is visible, then verify the exact expected filenames, target hierarchy, absence of wrong-season files, and `Resource.transferred_folder_id` persistence.
   - **Idempotence Test**: Re-run the same accepted group after verification. The second run should transfer zero new files and skip the already-present candidates, without creating another folder or changing the target path.
   - **Guangya File Operations**: Relocate a wrongly placed folder with `POST /userres/v1/file/move_file` and `{"fileIds": [...], "parentId": "<destination_id>"}`. `recycle_file` restores items from the recycle bin; it is not the delete operation. Use `delete_file` to move an empty test folder to the recycle bin, then read back the parent listing to verify removal.
   - **Immediate Telegram Status Lifecycle**: During `admin_approve`, save the original review-card HTML, edit it immediately to `⏳ 正在转存` before the cloud call, and edit that same card again from the saved base text only after the destination-directory verification finishes. Do not build the final card from a progress-edited message, or stale/duplicated/error status lines can remain visible. Submitter DMs and callback toasts must reflect the actual transfer result; never claim cloud synchronization when transfer failed. Channel publication status must be reported separately from cloud-transfer status.
   - **Restart-Safe Transfer Lifecycle & Stale Progress Detection**: A progress-card edit is not a durable job record. If `admin_approve` awaits `process_auto_transfer` inline, a Compose/systemd restart or process kill can leave an `ACCEPTED` resource with `transferred_folder_id IS NULL` while Telegram still says `⏳ 正在转存`; a healthy container only proves the service is alive, not that the transfer is running. Before any rollout, drain or persist every in-flight transfer. Prefer a durable `transfer_jobs`/outbox row keyed by `submission_group_id` with explicit states (`QUEUED`, `RUNNING`, `RESTORE_STARTED`, `VERIFYING`, `SUCCEEDED`, `FAILED`, `INTERRUPTED`), lease/heartbeat, and startup reconciliation. The progress message must be tied to that row, and startup must mark abandoned jobs interrupted and resume only after a read-only destination/idempotency check. If legacy code has no durable job record, compare `accepted_at` with the container start/restart time, query transfer fields, inspect provider connections/log markers, and read the exact target folder without creating or restoring anything; report a stale card rather than claiming an active transfer. Never blindly replay a request whose `restore_share` boundary may have been crossed. See `references/transfer_interruption_recovery.md`.
   - **Pre-Restore Network Retry**: Guangya directory/share authorization/listing failures that return with `restore_started=False` may be retried at most once by the orchestration layer. Add an explicit `restore_started` flag to `TransferResult`; set it before calling `restore_share`, preserve it on post-restore verification/401 errors, and never replay when it is true or a remote transfer task ID exists. A timeout at the restore boundary is potentially side-effecting even if no response/task ID was received.
   - **Truthful Transfer Status Text**: `skipped_files_count` can include files filtered because they are outside the exact requested episode set, so never label that count as duplicate episodes in a success message. Report the independently verified destination count (for example, `✅ 转存成功（已确认 2 个文件入库）`) and leave detailed filtering out unless it is classified explicitly.
   - **401 Recovery Boundary**: If a Guangya destination API call returns HTTP 401, use the stored `gy.` refresh token to obtain and persist the rotated access/refresh pair, then retry the complete transfer exactly once. If refresh or the retry fails, return a visible failure instead of claiming success.
   - **Target Folder Naming Normalization**: Always compute the desired archive name with `MediaNamingValidator.build_standard_folder_name`. Reuse an exact standard folder first. If exactly one existing nonstandard media folder matches the same TMDB ID, or a strong title/year/season identity, rename it through `POST /userres/v1/file/rename` with `{"fileId": "...", "newName": "..."}` and verify the result. Never rename ambiguous candidates or taxonomy/category folders.
   - **Strict Share-ID Selection**: When source filenames differ, match share items by exact filename or `(season, episode)` key only. Never fall back to every share `fileId`, because that can transfer other seasons or unapproved episodes. Missing share authorization or unresolved file IDs must fail closed.
   - **Deployment & Regression Gate**: For transfer-flow changes, first run `py_compile` and `git diff --check`, then targeted tests, the full suite, and a no-write edge-case probe. Back up remote files before synchronization and verify deployed hashes. For systemd use, restart `tg-media-bot.service` only after tests pass; for Compose use a rebuilt image and one controlled `up -d --force-recreate` cutover. Then verify the new process/container, WebUI HTTP behavior, startup/polling logs, and one safe idempotence/readback check. Do not report success from the `restore_share` response alone.
   - **Reference**: Use `references/guangya_transfer_verification.md` for the repeatable live probe, expected assertions, and timeout/cleanup pitfalls; use `references/guangya_progress_and_naming_deployment.md` for the verified progress-card, normalization, test-compatibility, and Oracle deployment details from the latest rollout.

## 5.6 Crash-Safe Auto-Transfer Recovery (Restart Resume)

A Telegram progress-card edit is only presentation state; it is not proof that an auto-transfer coroutine is still running. Any approval path that performs cloud I/O inline MUST create a durable recovery job before the first slow or side-effecting operation.

- Persist one unique `TransferJob` keyed by `submission_group_id` with at least `task_id`, `cloud_name`, `status`, `target_folder_id`, `target_folder_name`, exact `expected_file_names`, remote task ID, attempt count, timestamps, and last error.
- The approval handler must commit the `PENDING` job before editing the progress card or calling the cloud adapter. The adapter must commit the target folder identity before share-listing/restore work, then commit a `RESTORE_SUBMITTED` fence and exact expected filenames immediately before `restore_share`.
- If a process dies while status is `PENDING`/`RUNNING`, startup may resume the exact job. If the `RESTORE_SUBMITTED` fence exists, startup MUST perform read-only destination verification and database reconciliation only; it must never replay `restore_share`, even when the provider returned no task ID or timed out.
- On verified reconciliation, update only the exact accepted resources, mark the job `SUCCEEDED`, and then edit an already-persisted channel publication. Resource/database proof must precede Telegram status updates.
- Run the startup sweep after bot initialization and before Telegram polling. Recover only explicitly persisted active jobs (`PENDING`, `RUNNING`, `RESTORE_SUBMITTED`); do not synthesize jobs by scanning every historical `ACCEPTED` row, or a config change/restart can unexpectedly transfer unrelated legacy submissions. Legacy stale progress cards require a read-only manual preflight and an explicit user-scoped retry.
- Keep pre-restore failures retryable on a later restart without creating a same-process retry loop. Preserve the side-effect fence on all post-restore verification, authentication, and timeout failures. Add regression tests for persisted-job recovery, no legacy-row synthesis, fence-before-remote ordering, and “reconcile without replay”.
- See `references/restart_recovery_runbook.md` for the durable-state contract, startup ordering, recovery matrix, and verification checklist.

## 5.7 Movie Multi-Version Filename Normalization & Canonical Naming

When a movie share contains multiple release versions, do not reject the whole group merely because one version uses an abbreviation or an old naming prefix. A clear Chinese title or official multi-word English title in at least one video is a trusted title anchor; other files may enter the repair path only when the deterministic/AI review explicitly identifies them as safe filename-normalization candidates. A single short all-lowercase acronym (for example `tnzm`) is not an anchor by itself.

- **Canonical file contract**: use `片名 (年份) {tmdbid-ID}.分辨率.来源.编码.音轨.ext`. Include the year when it is known. Include `{tmdbid-ID}` when the task has a verified TMDB ID; omit it when unavailable rather than inventing a value. A notation such as `名字/年份/tmdbID` describes fields, not a literal slash—`/` is forbidden inside a filename.
- **Version preservation**: replace only the non-standard title prefix. Retain resolution, source, frame rate, HDR/EDR, codec, bit depth, audio, release-group, and extension suffixes so distinct versions cannot collapse into one name.
- **Strict review boundary**: the candidate list must come from the persisted review report (`filename_normalization_candidates` / equivalent explicit field). Never infer candidates by scanning every filename or by trusting a locally merged explanation. Content mismatch, wrong movie, advertising/noise, no trusted title anchor, or an unsafe reconstruction remains a rejection.
- **Safe operation order**: resolve the exact selected share files → submit the cloud transfer → poll until every original expected file is visible in the exact target folder → call the provider's rename endpoint only for explicit candidates → list the folder again and verify every final filename and file ID → only then update `Resource`, `TransferJob`, and the persisted channel publication.
- **Collision and recovery behavior**: if a target name collides with an existing file or another selected version, fail closed and never overwrite. A `RESTORE_SUBMITTED` recovery fence means the remote side effect may exist: startup recovery performs read-only destination reconciliation and must not replay `restore_share` or guess a rename. TV/ANIME strict season/episode filename rules are unchanged.
- **Reference**: use `references/movie_multi_version_filename_normalization.md` for the acceptance matrix, examples, test coverage, and deployment/readback checklist.

## Docker Compose Deployment & Safe Cutover Invariant

- Containerize the bot/WebUI without moving PostgreSQL unless the user explicitly requests a database migration. When PostgreSQL listens on host loopback, use host networking or an explicitly verified host-gateway route; do not guess a container-local database address.
- Keep secrets and business data outside the image: pass the existing `.env` through the deployment environment, exclude `.env`, database exports, keys, tests, and historical debug/token scripts from the build context, and bind-mount only the required persistent data directories.
- Run the application as a non-root UID, prefer a read-only root filesystem with a temporary writable `/tmp`, and add a bounded healthcheck. Preserve the existing WebUI port rather than opening a new firewall port.
- Before cutover, validate `docker compose config`, build the image, compile/import the application without writing pyc files, confirm the container can execute a read-only `SELECT 1` against the existing database, and run a no-write feature smoke test.
- Prevent double polling: back up the systemd unit, stop and disable the old unit, confirm its PID is gone and the WebUI port is free, then start exactly one Compose service. Verify `running/healthy`, the new container ID/image, port listening, Basic Auth behavior, FastAPI startup, Telegram command registration, polling, and zero new runtime faults.
- Keep a rollback image tag and the systemd unit backup until the new container passes its runtime gate. Do not run `docker compose down` or an application restart for every small follow-up; batch related fixes, test once, and perform one controlled replacement.
- A real cloud transfer requires explicit user authorization and exact target scoping. Preflight that every selected resource is `ACCEPTED`, the exact episode set matches the task, source URL/file metadata exists, and transfer metadata is unset. If a pre-`restore_share` read times out, inspect the target and use only bounded retries; after a restore may have begun, inspect actual destination files and deduplicate instead of blindly replaying.
- The transfer success claim requires the destination proof, not merely an API task ID: every expected filename must be visible in the target folder, wrong-season/unselected files must be absent, and the corresponding accepted `Resource` rows must share the verified target folder ID.
- See `references/docker_compose_and_guangya_transfer_recovery.md` for the tested container cutover sequence, Guangya empty-directory/pagination contract, and live-transfer readback checklist.

## 5.5 Verified Precision, Concurrency, Security & Staged-Release Practices

### Exact episode contract
- Treat `Task.requested_episodes is None` as the legacy range `start_episode..total_episodes`; never reinterpret it as `1..total_episodes`.
- A non-NULL list is an exact selection: coerce to integers, sort and deduplicate, reject non-positive or out-of-range values, and never compress a non-contiguous list such as `[1, 3, 5]` into `1-5`.
- Keep one canonical helper (for this project, `TaskService.allowed_episodes_for`) for missing-episode, submission, approval, transfer, UI, and notification checks. Movies keep empty season/episode fields and reject episode selection.

### FSM confirmation-card freshness
- Any destructive or point-deducting confirmation card must carry a random per-card nonce in its callback data and store the same nonce in the user's FSM data.
- Validate the callback prefix and nonce against the current FSM state before reading the draft or mutating the database. Reject stale, fixed-format, missing, or mismatched callbacks without clearing a newer draft; bind cancellation callbacks as well as submit callbacks.

### Telegram HTML output audit
- Every dynamic value in a message sent with `parse_mode="HTML"` must pass the shared HTML escape helper, including user names, titles, file names, URLs, cloud labels, AI output, exceptions, and database/config values. Escaping only `<`/`>` is insufficient; `&` must be handled too.
- Preserve only deliberately trusted bot-generated fragments (for example an existing review-card `html_text` containing intentional `<b>`, `<i>`, or `<code>` tags). Do not escape an entire trusted fragment a second time.
- Audit both direct f-strings and helper-returned message variables. Button labels without HTML parse mode are a separate concern and must not be incorrectly entity-escaped for display.

### Admin user-directory presentation
- `/user` with no target is a directory view, not the caller's own profile: query all recorded `User` rows, split them by dynamically parsed `ADMIN_TG_ID`, show administrators before regular users, and include total counts.
- Use a bounded page size and inline navigation/refresh callbacks so large user tables do not exceed Telegram message limits. Keep `/user <id/@username>` and point mutations unchanged.
- Each visible directory row MUST include an explicit inline `👤 管理 ID:<tg_user_id>` button with callback data bound to that exact user ID. The callback opens the existing profile console, where reward, deduction, clear, and refresh actions remain available. Keep navigation/refresh controls in a separate row; never render a text-only `/user` directory that hides the management workflow.
### Database identity and migration safety
- Application duplicate semantics and the database unique index must describe the same identity. If TV and ANIME are intentionally treated as one series class, normalize both to `SERIES` in the PostgreSQL expression index rather than leaving the index keyed by raw `media_type`.
- PostgreSQL expression indexes require parenthesized expressions such as `(CASE ... END)`; validate the migration on a non-production/test database before applying it. Check for normalized duplicate groups before the migration and read back both Alembic head and `pg_indexes.indexdef` afterward.

### Guangya async/fail-closed boundary
- Keep blocking URL open and response-read operations behind awaited `asyncio.to_thread()` wrappers; preserve mockability by patching the wrapper or its underlying `urllib` call in tests.
- Accept only explicit API success codes (`0`/`200`); reject title-only, empty, incomplete, unauthorized, cyclic, directory-only, non-video, or unverified results. A successful HTTP response or restore response alone is never proof of transfer.

### Staged release discipline
- Default to a deliberate green-batch release: finish the related repair set, add regression tests first, run focused and full gates, explicitly stage only intended files, commit once, synchronize GitHub once through the configured REST API, and restart/verify production once.
- Do not commit or restart for every small follow-up edit. If a production emergency genuinely requires an intermediate release, document that exception and still perform a complete target-side verification before proceeding; otherwise accumulate the batch and avoid repeated service disruption.
- Treat local commit, remote GitHub synchronization, and production rollout as three separate claims. Verify each one by reading back its exact evidence; a successful local commit or an SSH/API exit code does not prove the remote ref or live service changed.
- Keep the GitHub API credential as a long-lived, mode-600 deployment secret at the configured Oracle path. Verify only presence and permissions, never print its contents, never put it in a URL/log/history, and do not delete it after a successful synchronization.
- If a private GitHub API request returns `404` while no safe authentication source is configured, classify the remote sync as incomplete. Never reuse a previously exposed PAT, guess credentials, put tokens in URLs/logs/history, or report local completion as GitHub synchronization.
- For the exact green-batch handoff and remote-verification checklist, use `references/remote_sync_truthfulness.md`.
- For the final service rollout gate—PID/timestamp change, WebUI listener, polling markers, Basic Auth `401` interpretation, and graceful-shutdown traceback classification—use `references/batched_release_runtime_verification.md`.
- Keep secrets, `.env` values, database exports, private keys, tokens, cookies, and real cloud-transfer side effects outside synchronization, tests, logs, commits, and reports.

See `references/repair_rollout_and_security_hardening.md` for the repeatable audit, nonce, migration, and staged Oracle rollout checklist.

## 6. Testing & Verification Guide

All verification tests run under the target environment's test command (the suite count evolves; the latest production-bound maintenance-cycle run validated 185 passed, including the movie multi-version normalization coverage):
- `test_stage_a_database.py`: Verifies both partial unique indexes exist and block duplicate ACCEPTED rows.
- `test_stage_b_tasks.py`: Verifies task models, episode range parsing, and missing set calculation.
- `test_stage_b_deduplication.py`: Verifies duplicate task detection and avoidance in `/add` and `/addtask`.
- `test_stage_b_multiseason.py`: Verifies multi-season auto expansion, range tokenizing, and punctuation preservation (e.g. 《我,许可 我许可》).
- `test_stage_b_start_episode.py`: Verifies partial episode range (`start_episode` -> `total_episodes`) invariants.
- `test_stage_cde_submission.py`: Tests real multi-session concurrency for TV episodes and movies, partial success batching, TMDB binding, and point rules.
- `test_stage_f_channel.py`: Tests channel message rendering and multi-channel dedicated routing.
- `test_stage_g_ai_and_review.py`: Tests `CloudParserService`, `AIReviewService`, reviewer scoring, and manual approval/rejection workflows.
- `test_stage_h_deletion.py`: Tests submission deletion, points revocation calculation, movie rollback, and TV missing episode task reopening.
- `test_stage_i_strict_rejection.py`: Tests deterministic filename season pre-check and upfront rejection for non-standard pure-number video filenames.
- `test_stage_j_naming_and_points.py`: Tests Emby 4-format naming validation (Movie, TV single, multi-episode, SP), TMDB ID matching, tiered point rewards (+0.5 / +1.0), and rejection tiers.
- `test_stage_k_quota_and_penalty.py`: Tests daily user quota limits (100GB/20 items), quota calculation, admin penalty deduction/clearing, and point ledger logging.
- `test_stage_l_timed_tasks.py`: Tests difficulty task bounties (+1~15 pts), mode switching, exclusive 30-minute locking, and timeout deduction/auto-release.
- `test_stage_m_group_auth.py`: Tests designated group membership verification (`@shangpian888`), admin bypass, member TTL caching, and join/verify workflows.
- `test_stage_n_media_request.py`: Tests media request system (Movie 2 pts, TV 0.5/ep), atomic point deduction, shared PointLog audit, refund on cancellation, and completion notice.
- `test_stage_o_cancel_and_command_precedence.py`: Tests `/cancel` command precedence, FSM state clearing, slash-command bypass, and preventing command trapping across all submission/wizard states.
- `test_stage_p_cloud_choice_workflow.py`: Tests interactive cloud platform selection step, state transitions, re-selection, cross-cloud auto-adjustment, and error cards.
- `test_stage_q_auto_transfer_and_dedup.py`: Tests channel-bound auto-transfer, multi-cloud adapter selection, folder & episode deduplication, strict season/episode selection, asynchronous destination visibility, exact share-file matching, one-time 401 retry, conservative folder normalization, Resource DB field updates, ChannelService post formatting with official share link, and admin `/clouds` & `/setcloud` commands.
- `test_stage_r_daily_leaderboard.py`: Tests daily 20:00 CST submission leaderboard data aggregation, 4-section card formatting, channel delivery, `system_settings` once-per-day lock, and `/pushleaderboard` admin command.
- `test_stage_s_media_classification.py`: Tests 2-level taxonomy mapping (TV 10 subcategories, Movie 6 subcategories) across TMDB genres, country codes, and animation rules.
- `test_stage_t_metadata_and_review_lock.py`: Tests metadata scraping, strict $\le$ 30 req/s rate limiting, NFO XML generation, and zero-conflict review lock.
- `test_stage_u_manual_task_deletion.py`: Tests `/deltask` manual task deletion, interactive cards, community request refund, and cascading resource/points cleanup.
- `test_tmdb_rate_limit.py`: Tests sliding-window rate limiter under high-concurrency bursts (50 parallel requests), verifying requests stay strictly bounded <= 40 req/s.

See `references/cloud_and_ai_review_specs.md`, `references/openlist_transfer_and_dedup.md`, `references/guangya_native_api_specs.md`, `references/guangya_refresh_verification.md`, `references/aws_ports_and_routing.md`, `references/tmdb_classification_and_metadata_specs.md`, and `references/task_deletion_and_auto_transfer.md` for cloud API probe mechanisms, OpenList auto-transfer & deduplication architecture, Guangya Pan native API specifications and protocol quirks, refresh-token recovery and live verification, verified host port invariants, TMDB 2-level taxonomy & scraper rate limiting, and task deletion/rollback specifications.

