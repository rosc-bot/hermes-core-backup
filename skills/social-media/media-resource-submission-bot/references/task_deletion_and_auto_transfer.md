# Task Deletion & Auto-Transfer Lifecycle Specifications

## 1. Full Auto-Transfer Lifecycle & 2-Level Directory Routing

### 1.1 Root to Leaf Folder Hierarchy
Auto-transfer organizes transferred media into a strict 3-tier hierarchy on target cloud drives:
```text
[Cloud Root]
  └── 📁 影视转存总目录 (Master Folder ID: target_folder_id)
        ├── 📁 电视剧 (Level 1)
        │     ├── 📁 国漫 (Level 2)
        │     │     └── 📁 师兄啊师兄(2023)第一季 4K {tmdbid-218642} (Standard Media Folder)
        │     │           ├── S01E151.4K.mp4
        │     │           └── S01E152.4K.mp4
        │     └── ... (其他9个电视剧二级目录)
        └── 📁 电影 (Level 1)
              ├── 📁 动画电影 (Level 2)
              │     └── 📁 疯狂动物城(2016) 4K {tmdbid-269149}
              └── ... (其他5个电影二级目录)
```

### 1.2 Pipeline Steps (`CloudTransferService.process_auto_transfer`)
1. **Metadata Resolution & Classification**:
   - Fetches TMDB details (`TMDBService.get_tmdb_details`) for genres, country of origin, and language.
   - Maps to exact Level 1 (`电视剧`/`电影`) and Level 2 (16 subcategories) via `MediaClassifier.classify`.
2. **Directory Tree Auto-Creation**:
   - Ensures Level 1 folder exists under master folder (`master_parent_id`).
   - Ensures Level 2 folder exists under Level 1 folder (`parent_for_sub`).
   - Ensures standard media folder exists under Level 2 folder (`parent_for_media`).
3. **Episode-Level Deduplication**:
   - Queries existing files in the destination media folder via cloud list API.
   - Compares incoming files against existing filenames.
   - Skips duplicate episodes and transfers only incremental new files.
4. **Cloud-Side File Transfer**:
   - Invokes cloud adapter (e.g. Guangya `POST /nd.bizuserres.s/v1/restore_share`) targeting the standard media folder ID as `parentId`.
   - Media files are never dropped into the root folder.
5. **Database Resource Sync**:
   - Updates `Resource.transferred_folder_id` with the destination media folder ID.
   - Optionally updates `Resource.transferred_share_url` if auto-sharing is enabled.
6. **Muted Delivery Policy**:
   - Channel publishing (`ChannelService.publish_submission`) is suppressed.
   - Submitter private notification is suppressed.
   - Admin review message is edited in-place with transfer summary, and a dedicated admin push card is sent.

### 1.3 Historical Submissions Backfill & Dynamic Share Resolution Invariant
When backfilling or re-running auto-transfer on existing database records (e.g. `status = 'ACCEPTED'` but `transferred_folder_id IS NULL`):
1. **Empty File List Fallback**:
   - In early or historical submissions, `Resource.file_names` in DB may be `None` or `video_files` may be empty.
   - `GuangyaTransferAdapter.transfer` must dynamically resolve `share_items` via `_get_share_access_token` and `_get_share_file_list` as the effective incoming file list (`effective_incoming = video_files if video_files else share_items`).
2. **Recursive Subdirectory Share Traversal**:
   - Cloud shares frequently contain nested subdirectories (e.g. a share containing `消失的人(2026)/` with `resType=2`).
   - The recursive share file scanner must traverse nested folders to find leaf files, and if the subfolder list is empty, retain the directory item so `restore_share` receives valid `fileIds` targeting the destination 2-level media folder.
3. **TMDB ID Accuracy & Classification**:
   - Ensure `task.tmdb_id` is updated with authentic TMDB IDs (e.g. via `TMDBService.search_tmdb`) rather than mock IDs before executing transfer, allowing `MediaClassifier` to route works to accurate subcategories (e.g. `电视剧/国漫`, `电视剧/日番`, `电影/华语电影`).
4. **Post-Transfer Metadata Backfill**:
   - After executing transfer, invoke `scripts/download_metadata.py --all` to scrape Emby NFOs, posters, fanarts, and `.actors/` avatars for all newly backfilled media.

### 1.4 Dual-Channel Admin Notification Architecture & Backfill Push Discipline
1. **Dual-Channel Push on Submission Review**:
   - In-place review card update: `call.message.edit_text` to show status change.
   - Local chat reply: `call.message.answer(admin_notice_text)`.
   - Out-of-band admin private message: Iterate over `settings.ADMIN_TG_ID` and execute `call.bot.send_message(chat_id=aid, text=admin_notice_text, parse_mode="HTML")` for any admin not in the current chat. Guarantees alerts are delivered to private Telegram chats even during group audits.
2. **Backfill Report Direct Push**:
   - When running batch backfill or transfer scripts outside Telegram interaction, always instantiate `Bot(token=settings.BOT_TOKEN)` and push a structured summary card to administrators so operations are never silent.

---

## 2. Manual Task Deletion & Cascading Rollback (`/deltask`)

### 2.1 Invocation Channels
- Admin slash command: `/deltask [task_id | title_keyword]` (aliases: `/rmtask`, `/taskdel`).
- Empty argument: Renders paginated inline keyboard list of active/completed tasks (`[🗑 #ID 《标题》 规格]`).
- Quick management button: In `/tasks` list card, admins see `[🗑️ 管理 / 下架删除任务]`, opening the delete picker.

### 2.2 Confirmation Card & Safety Warning
Selecting a task presents a confirmation card with:
- Task ID, Title, Year, Spec, Media Type.
- Attribute badge: `📢 官方征集` or `🌟 群友求片`.
- Bounty points and associated submission record count.
- Clear warning describing cancellation impacts.
- Interactive action buttons: `[🗑️ 确认彻底删除]` / `[🔙 返回任务列表]` / `[❌ 取消]`.

### 2.3 Cascading Rollback Invariants (`TaskService.delete_task`)
1. **Community Request Refund (`is_request=True`)**:
   - When a requested task is deleted, the original requester's points must be refunded in full (`user.points += task.cost_points`).
   - Writes an audit row in `point_logs` with `action='MEDIA_REQUEST_REFUND'`, recording `delta=+cost_points`, `reason=f"下架求片任务 #{task_id} 退回积分"`.
2. **Revocation of Accepted Points**:
   - If any submitted resources under the task reached `ACCEPTED` status, system sums points awarded for those submissions.
   - Deducts points from submitter accounts: `user.points = max(0.0, user.points - revoked_points)`.
   - Writes an audit row in `point_logs` with `action='SUBMISSION_REVOKE'`.
3. **Database Resource & Task Deletion**:
   - Deletes all `Resource` rows linked to `task_id`.
   - Deletes the `Task` row itself.
   - Commits transaction atomically.
4. **Local Metadata Directory Cleanup**:
   - If metadata files (NFO, poster, fanart, actor avatars) were downloaded for the deleted task under `data/metadata/<一级>/<二级>/<影视目录>/`, remove the corresponding local folder (via `shutil.rmtree`) to prevent stale metadata accumulation.

---

## 3. Cloud Adapter Token Lifecycle & Authentication Invariants

### 3.1 Guangya JWT Token Expiration & Error Handling
- **JWT Lifetime**: Guangya Pan JWT tokens (issued by `https://account.guangyapan.com`) typically carry an expiration duration (`exp`) of ~2 hours from issue time (`iat`).
- **HTTP 401 Unauthorized**: When a token expires, cloud API calls (`get_file_list`, `create_dir`, `restore_share`, `move_file`) return `HTTP Error 401: Unauthorized`.
- **Token Update**: When updated, the new Bearer JWT token should be stored in `cloud_configs.auth_token` for `guangya` via `/setcloud` or direct SQL update. Adapters automatically format `Authorization: Bearer <token>` for all subsequent operations.
