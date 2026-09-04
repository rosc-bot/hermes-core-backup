# Cloud Drive Link Inspection & AI Audit Specifications

This reference provides technical protocol specifications for the cloud share link inspection, AI audit schema, and manual review pipeline in `tg-media-submission-bot`.

## 1. Guangya Pan (光鸭云盘) Share Inspection Protocol

Guangya Cloud uses an internal REST API for share link access:

### 1.1 Summary & Access Token
- Extract `share_id` from URL: e.g. `https://www.guangyapan.com/s/1942205903573098532_ak9yyEfSSiOov9MT` -> `shareId = "1942205903573098532_ak9yyEfSSiOov9MT"`
- **Step 1: Check Share Validity**:
  - `POST https://api.guangyapan.com/userres/v1/get_share_summary`
  - Body: `{"shareId": "<share_id>"}`
  - Returns `title`, `nickName`, `shareStatus` (1 = active).
- **Step 2: Acquire Share Access Token**:
  - `POST https://api.guangyapan.com/userres/v1/get_share_access_token`
  - Body: `{"shareId": "<share_id>", "code": "<extraction_code_or_empty>"}`
  - Returns `accessToken` (JWT).

### 1.2 Recursive File Enumeration
- **Step 3: List Files in Share / Subfolders**:
  - `POST https://api.guangyapan.com/userres/v1/get_share_page_files_list`
  - Body: `{"accessToken": "<jwt>", "parentId": "<folder_id_or_empty>", "pageSize": 100, "orderBy": 0, "sortType": 0}`
  - Folder entries: `resType == 2` (recurse with `parentId = item.fileId`).
  - File entries: `resType != 2` (inspect `fileName`, `fileSize`).

### 1.3 Video Filtering & Formatting
- Filter against video extensions: `.mp4`, `.mkv`, `.ts`, `.iso`, `.flv`, `.avi`, `.mov`, `.wmv`, `.m4v`, `.rmvb`.
- Total size calculation: Sum `fileSize` bytes -> format as `MB` / `GB`.

---

## 2. AI Audit Expert Protocol & Schema Contract

### 2.1 Request Structure & Emby Standard Naming Formats
Calls OpenAI-compatible endpoint (e.g. `http://127.0.0.1:8317/v1/chat/completions` via Local CPA / Gemini / Claude / DeepSeek):
- System Prompt: Defines strict media audit rules with Emby standard formats:
  - **Folder Naming Standard (Chinese Template + TMDB ID)**:
    - **TV / Anime Series**: `剧名(年份)第X季 分辨率 {tmdbid-ID}` (e.g. `不良一族寻爱记(2025)第二季 1080P {tmdbid-218231}`, `聪明镇(2026)第一季 4K {tmdbid-208392}`, `二十世纪电气目录(2026)第一季 1080P {tmdbid-102938}`)
    - **Movie**: `片名(年份) 分辨率 {tmdbid-ID}` (e.g. `怒火(2026) 4K {tmdbid-1363974}`, `消失的人(2026) 4K {tmdbid-1363974}`)
  - **Video File Naming Standard**:
    1. **Movie**: `片名 (年份) {tmdbid-ID}.画质.来源.编码.ext` (e.g. `消失的人 (2026) {tmdbid-1363974}.2160p.WEB-DL.DDP5.1.H.265.mp4`)
  2. **TV Single**: `剧名 (年份) {tmdbid-ID}.SxxExx.画质.来源.编码.ext` (e.g. `庆余年 (2019) {tmdbid-93811}.S02E01.2160p.WEB-DL.DDP5.1.H.265.mkv`)
  3. **TV Multi-Episode**: `剧名 (年份) {tmdbid-ID}.SxxExx-Exx.画质.来源.编码.ext` (e.g. `庆余年 (2019) {tmdbid-93811}.S02E01-E06.2160p.WEB-DL.H265.mkv`)
  4. **TV Special (SP)**: `剧名 (年份) {tmdbid-ID}.S00Exx.画质.来源.编码.ext` (e.g. `庆余年 (2019) {tmdbid-93811}.S00E01.2160p.WEB-DL.H265.mkv`)
  5. **Mandatory Title Presence Rule (Rule #0)**: Every video file's own filename **MUST** contain a valid drama or movie title. Nameless files (e.g. `S01E01.mp4`, `S01E01.1080p.mkv`, `4K.S01E01.mp4`, `1080p.mp4`, `(2026).S01E01.mp4`) or generic placeholders (`movie.mp4`, `video.mp4`, `正片.mp4`) are strictly rejected upfront (`is_valid=False, 0 pts`).
  6. **Series/Anime Mandatory Season Rule**: **MUST contain `S0几` (e.g. `S01`, `S02`, `第01季`) season tag in every video file's own filename**. Outer directory names do NOT substitute for filename naming.
  7. **Tiered Scoring System (3 Criteria, up to +1.5 pts)**:
     - Non-standard naming: Direct auto-rejection (0 pts).
     - **3 Independent Naming Criteria (0.5 pts each)**:
       1. Standard media naming format specification: +0.5 pts.
       2. Cloud folder or share title contains `{tmdbid-ID}`: +0.5 pts.
       3. Video filename contains `{tmdbid-ID}`: +0.5 pts.
     - Total score = 0.5, 1.0, or 1.5 pts (+ any difficult task bounty 1~15 pts).

### 2.2 Expected Response JSON Schema (Passing Sample)
```json
{
  "passed": true,
  "confidence": 95,
  "risk_level": "LOW",
  "audit_summary": "资源符合征集要求，作品名称、季数及目标集数完全匹配。",
  "detected_title": "师兄啊师兄",
  "detected_season": 1,
  "has_season_tag": true,
  "detected_episodes": [151, 152, 153, 154, 155, 156, 157],
  "version_spec": "4K HEVC AAC",
  "total_size": "3.28 GB",
  "reasons": [
    "作品名称与征集任务 100% 匹配",
    "每个视频文件名自身均包含标准季数标识（如 S01E151）",
    "文件提取集数与目标集数完全吻合，无缺失或断集"
  ]
}
```

### 2.3 Non-Standard Filename Rejection Sample (Deterministic / LLM Rejection)
```json
{
  "passed": false,
  "confidence": 98,
  "risk_level": "HIGH",
  "audit_summary": "视频文件名自身缺失 S0几 季数规范标识 (如: 151~4K [HEVC.AAC].mp4)",
  "detected_title": "师兄啊师兄",
  "detected_season": 1,
  "has_season_tag": false,
  "detected_episodes": [151, 152, 153, 154, 155, 156, 157],
  "version_spec": "4K",
  "total_size": "3.28 GB",
  "reasons": [
    "非标准剧集命名：文件 '151~4K [HEVC.AAC][2026.07.22].mp4' 缺少 S01/S02 季数前缀，无法满足 Emby/自动化媒体库入库标准",
    "严禁纯数字/纯集数命名，必须规范为 e.g. '师兄啊师兄.S01E151.4K.mp4'"
  ]
}
```

### 2.4 Dynamic Model Discovery & Picker Protocol
- **Endpoint**: `GET <AI_API_BASE>/models` with Bearer auth.
- **Model Filtering**: Filters out non-chat models containing `embed`, `tts`, `whisper`, `audio`, `dall-e`, `moderation`.
- **Pagination & Layout**: 2 models per row, 6 models per page with `[⬅️ 上一页] [📄 1/N] [下一页 ➡️]` navigation.
- **Active Model Highlighting**: Current model prefixed with `✔ <model_name>`.
- **Fallback Models**: If `/models` endpoint fails or returns empty: `['gemini-3-flash', 'gemini-3.7-flash-high', 'claude-sonnet-4-6', 'gemini-3.1-flash-lite', 'gpt-4o-mini', 'deepseek-chat']`.

---

## 3. Review Pipeline & Gate State Machine

1. **User Submits Share Link**:
   - `CloudParserService.inspect_share_link(share_url)` -> extracts file list & total size.
   - Failures (empty/invalid/expired) -> rejected immediately to user in chat.
2. **Deterministic Rules & AI Pre-Audit (`AIReviewService.review_submission`)**:
   - Runs deterministic regex pre-check: `r'(?:[Ss]\d{1,2}|第\s*\d{1,2}\s*季)'` against all video filenames for TV/Anime.
   - Runs LLM structured audit.
3. **Branch A: Format Failure -> Upfront Direct Rejection**:
   - If `passed == False` or `risk_level == "HIGH"`:
     - Mark submission status as `REJECTED` in database for audit trail.
     - Immediately notify submitter via bot message with specific rejection reasons and formatting guide (e.g. `S01E151`).
     - **DO NOT** create a `REVIEW` card, and **DO NOT** notify administrators.
4. **Branch B: Format Passed -> Admin Review Gate**:
   - If `passed == True`:
     - Save resource rows with `status = 'REVIEW'` (no points awarded, no task completion, no channel post).
     - Send Telegram card with file inspection breakdown, AI audit verdict, and inline buttons:
       - `review_accept_{group_id}`: Calls `SubmissionService.approve_and_award_points(db, group_id, admin_tg_id)`. Transitions to `ACCEPTED`, adds points to user, updates missing episodes, and broadcasts to channel.
       - `review_reject_{group_id}`: Calls `SubmissionService.reject_submission(db, group_id, admin_tg_id)`. Transitions to `REJECTED`, notifies submitter with reason.

---

## 4. TMDB Query Lifecycle & Verification Boundaries

- **Rate Limit Boundary**: All TMDB requests pass through `TMDBRateLimiter` (sliding-window $\le 35$ req/s) to prevent 429 penalties.
- **Task Publishing Stage (`/add`)**: Queries `https://api.themoviedb.org/3/search/` (movie or tv) to auto-bind `tmdb_id`.
- **User Submission Stage**:
  - If `task.tmdb_id` is already populated: Bot **directly reuses** `task.tmdb_id` without sending a new search request.
  - If `task.tmdb_id` is null: Bot queries TMDB and offers candidate buttons to the submitter (+1 bonus point incentive).
- **AI Review Stage**: Currently reviews against task metadata (`title`, `year`, `season`, `requested_episodes`) and cloud file lists. Season episode range verification via TMDB season detail API (`/tv/{id}/season/{season_number}`) can be optionally chained for deep episode metadata validation.

---

## 5. Channel-Bound Auto-Transfer & Smart Deduplication Protocol

### 5.1 Architecture & Adapters
- **Orchestrator**: `CloudTransferService` maps the submission's `cloud_cfg.name` and dedicated `channel_id` to the appropriate adapter:
  - `guangya` / `gypan`: `GuangyaTransferAdapter`
  - `mobile` / `139`: `MobileTransferAdapter`
  - `quark`, `ali`, `baidu`, `115`, `xunlei`, `tianyi`: `AlistTransferAdapter` / Generic API

### 5.2 Guangya Auto-Transfer Endpoints
1. **Target Folder Resolution / Creation**:
   - `POST https://api.guangyapan.com/userres/v1/get_user_file_list` with `{"parentId": "<root_id>", "pageSize": 100}`
   - If folder `剧名(年份)第X季 分辨率 {tmdbid-ID}` does not exist:
     - `POST https://api.guangyapan.com/userres/v1/create_folder` with `{"parentId": "<root_id>", "folderName": "<standard_name>"}`
2. **File & Episode Deduplication (`_deduplicate_files`)**:
   - Lists existing items in the destination folder.
   - Extracts existing episode numbers (regex `[Ee](\d{1,4})`).
   - Filters incoming video files: skips any file whose episode number or filename already exists in the destination folder.
3. **Batch Save Execution**:
   - `POST https://api.guangyapan.com/userres/v1/save_share_files`
   - Body: `{"shareId": "<share_id>", "sharePwd": "<pwd>", "targetParentId": "<target_folder_id>", "fileIds": ["<id1>", ...]}`
4. **Official Share Link Generation**:
   - `POST https://api.guangyapan.com/userres/v1/create_share` (or `/nd.bizuserres.s/v1/share_file`)
   - Body: `{"fileIds": ["<target_folder_id>"], "title": "<standard_name>", "expireDay": 0, "sharePwd": "<pwd>"}`
   - Returns official URL -> saved to `Resource.transferred_share_url` and broadcast to the channel.

### 5.3 Verified Guangya API Protocol & Browser Token Retrieval Guide
- **Base Endpoints**:
  - Account API: `https://account.guangyapan.com` (Auth verify: `GET /v1/user/me`)
  - Resource API: `https://api.guangyapan.com` (Create Dir: `POST /nd.bizuserres.s/v1/file/create_dir` or `/userres/v1/file/create_dir`)
  - Share Save: `POST /nd.bizuserres.s/v1/restore_share` or `/userres/v1/save_share_files`
- **JWT Header Format**: `Authorization: Bearer <JWT_TOKEN>` with `scope: user profile sso offline`.
- **Browser Token Extraction Troubleshooting (Edge/Chrome)**:
  - If the "Network" (网络) tab is missing from DevTools:
    1. Click the `+` icon on the toolbar -> select `Network` (网络).
    2. Or press shortcut: `Ctrl + Shift + E`.
    3. Or extract directly via DevTools Console: `localStorage.getItem('token')`.

