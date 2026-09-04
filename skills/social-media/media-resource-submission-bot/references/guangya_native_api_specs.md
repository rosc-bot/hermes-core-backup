# Guangya Pan (光鸭网盘) Native API Specifications & Protocol Invariants

This reference documents the verified, live-tested API endpoints, payloads, and quirks for direct cloud transfer, deduplication, and file organization on Guangya Pan (`api.guangyapan.com`).

---

## 1. Authentication & Base URL

- **API Base**: `https://api.guangyapan.com`
- **Account Base**: `https://account.guangyapan.com`
- **Headers**:
  ```python
  headers = {
      "Accept": "application/json, text/plain, */*",
      "Content-Type": "application/json",
      "Origin": "https://www.guangyapan.com",
      "Referer": "https://www.guangyapan.com/",
      "Authorization": f"Bearer {token}",  # Or raw JWT if already prefixed
  }
  ```

---

## 2. Critical Protocol Quirks & Invariants

### 2.1 User Drive File Listing: `pageNum` vs `page` (CRITICAL)
- Endpoint: `POST https://api.guangyapan.com/userres/v1/file/get_file_list`
- **QUIRK**: Passing `"page": 1` returns `{"data": {"total": N}}` without the `list` field!
- **MANDATORY**: You MUST pass `"pageNum": 1` instead:
  ```json
  {
    "parentId": "<folder_id_or_empty_for_root>",
    "pageNum": 1,
    "pageSize": 100,
    "orderBy": 3,
    "sortType": 1
  }
  ```
  Returns:
  ```json
  {
    "code": 200,
    "msg": "success",
    "data": {
      "total": 10,
      "list": [
        {
          "fileId": "1942305989699285071",
          "fileName": "影视转存总目录",
          "resType": 2
        }
      ]
    }
  }
  ```

### 2.2 Public Share File Listing: `resType` vs `dirType` (CRITICAL)
- Endpoint: `POST https://api.guangyapan.com/nd.bizuserres.s/v1/get_share_page_files_list`
- Payload:
  ```json
  {
    "accessToken": "<share_access_token>",
    "parentId": "<folder_file_id_if_nested>",
    "page": 1,
    "pageSize": 100
  }
  ```
- **QUIRK**: Files in a share often have `"dirType": 1`!
  - `resType == 2` -> Directory / Folder
  - `resType == 1` -> File
- **MANDATORY**: Evaluate folder status strictly via `item.get("resType") == 2`. NEVER check `dirType == 1` as a directory flag, or regular video files will be treated as subdirectories, breaking recursive traversal.

### 2.3 Recursive Traversal of Shared Folders
Public shares created by users or release channels almost always wrap video files in an outer folder (e.g. `《师兄啊师兄 第一季 (2023)》`).
- `get_share_page_files_list` without `parentId` only returns root items of the share (the outer folder).
- To transfer actual media, the adapter MUST recursively traverse `resType == 2` folders until leaf video files (`resType == 1`) are collected with their `fileId`s.

### 2.4 Restoring / Transferring Files (`restore_share`)
- Endpoint: `POST https://api.guangyapan.com/nd.bizuserres.s/v1/restore_share`
- Payload:
  ```json
  {
    "accessToken": "<share_access_token>",
    "fileIds": ["1942243369285783643", "1942243369285783645"],
    "parentId": "<target_folder_id>"
  }
  ```
- Response:
  ```json
  {
    "msg": "success",
    "data": {
      "taskId": "1942311200371269719"
    }
  }
  ```
  The transfer executes asynchronously on Guangya's backend. Files appear in the target folder within seconds.

### 2.5 Share Summary & Share ID Payload Type (CRITICAL UPDATE)\n- Endpoint: `POST https://api.guangyapan.com/userres/v1/get_share_summary`\n- **QUIRK**: Guangya recently changed their backend parameter validation for this endpoint.\n  - Previously, `shareId` was expected to be an `integer` (e.g., `{"shareId": 1942436442083659779}`).\n  - Passing an integer now throws a hard 400 error: `Mismatch type string with value number`.\n- **MANDATORY**: `shareId` MUST be passed as a **string**. Furthermore, for new links with a shortcode suffix (e.g. `1942436442083659779_ad0FOY8EdLN`), the entire composite string MUST be passed as the `shareId`.\n  - Stripping the suffix and passing just the numeric part as a string returns `{"code": 112, "msg": "参数错误"}`.\n  - Payload must be: `{"shareId": "1942436442083659779_ad0FOY8EdLN"}` (along with `"extractionCode": "..."` if a password exists).\n\n---\n\n## 3. Directory Creation (`create_dir`)

- Endpoint: `POST https://api.guangyapan.com/userres/v1/file/create_dir`
- Payload:
  ```json
  {
    "parentId": "<parent_folder_id_or_empty>",
    "dirName": "剧名(年份)第X季 4K {tmdbid-ID}"
  }
  ```
- Returns `{"data": {"fileId": "<new_folder_id>"}}`.

---

## 4. File Movement & Reorganization (`move_file`)

- Endpoint: `POST https://api.guangyapan.com/userres/v1/file/move_file`
  *(Note: `/userres/v1/file/move` returns 404; `/userres/v1/file/move_file` is the verified working endpoint)*
- Payload:
  ```json
  {
    "fileIds": ["1942311201377800271"],
    "toParentId": "1942311575178448945",
    "parentId": "1942311575178448945"
  }
  ```
- Response:
  ```json
  {
    "msg": "success",
    "data": {
      "taskId": "1942313388032110641"
    }
  }
  ```

---

## 5. File & Folder Deletion (`delete_file`)

- Endpoint: `POST https://api.guangyapan.com/userres/v1/file/delete_file`
  *(Note: `/userres/v1/file/delete` returns 404; `/userres/v1/file/delete_file` is the verified working endpoint)*
- Payload:
  ```json
  {
    "fileIds": ["1942321417746141267", "1942321463732473922"]
  }
  ```
- Response:
  ```json
  {
    "msg": "success",
    "data": {
      "taskId": "1942518576831701033"
    }
  }
  ```

---

## 6. Strict Two-Level Directory Hierarchy Invariant

- **Structure**:
  ```text
  📁 网盘根目录 (0)
     └── 📁 影视转存总目录 (master_parent_id, e.g. 1942305989699285071)
            └── 📁 师兄啊师兄(2023)第一季 4K {tmdbid-218231} (target_folder_id)
                   ├── 🎬 师兄啊师兄 (2023)S01E151 ... .mp4
                   ├── 🎬 师兄啊师兄 (2023)S01E152 ... .mp4
                   └── 🎬 师兄啊师兄 (2023)S01E153 ... .mp4
  ```
- **Rule**: Transfers MUST NEVER save leaf video files directly into `master_parent_id` (总目录). Every transfer must resolve or create the TMDB standard subfolder `target_folder_id`, ensuring all files are neatly contained inside their respective media folders.

---

## 6. Token Lifespan, Expiration (HTTP 401) & SSO Automatic Refresh

- **Token Lifespan**: Guangya `access_token` (JWT) is issued with a strict 2-hour TTL (`exp - iat = 7200s`). Direct API calls after 2 hours immediately fail with `HTTP Error 401: Unauthorized`.
- **Refresh Token Pitfall (One-Time Use/Rotation)**: The `refresh_token` (starting with `gy.`) is strictly single-use. If a user extracts it from the browser's Network tab but then refreshes the page, logs in again, or continues interacting with the web UI, the browser will consume it and Guangya will issue a new one, invalidating the extracted token. Using an invalidated token returns `HTTP Error 400: invalid refresh token for it may be has been refreshed by other process`. Users must extract it and *immediately* pass it to the bot without further browser interaction.
- **SSO Refresh Endpoint**: `POST https://account.guangyapan.com/v1/auth/token`
  - Payload:
    ```json
    {
      "client_id": "aMe-8VSlkrbQXpUR",
      "grant_type": "refresh_token",
      "refresh_token": "<refresh_token_string_usually_starting_with_gy.>"
    }
    ```
  - Response:
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "gy.WU0...",
      "expires_in": 7200,
      "token_type": "Bearer"
    }
    ```
- **Automated Lifecycle Invariant**:
  1. `GuangyaTransferAdapter` parses stored credentials supporting JSON `{"access_token": "...", "refresh_token": "..."}`, plain JWT, or `refresh_token` (`gy.xxx`).
  2. Prior to any transfer operation, checks JWT expiration (`exp <= now + 60s`).
  3. If expired, calls SSO endpoint, updates memory, and persists the newly generated token pair back to `cloud_configs` table in PostgreSQL automatically.

