# Guangya Live Transfer Verification Runbook

This reference records a reusable, tested verification pattern for `tg-media-submission-bot` on the Oracle host. It deliberately contains no access or refresh token.

## 1. Credential preflight

1. Read the `guangya` row from `cloud_configs` without printing token values.
2. Parse `auth_token` as either:
   - JSON: `{"access_token": "...", "refresh_token": "..."}`;
   - a plain JWT; or
   - a plain `gy.*` refresh token.
3. If the access JWT is expired or within the refresh threshold, call:

```text
POST https://account.guangyapan.com/v1/auth/token
{"client_id":"aMe-8VSlkrbQXpUR","grant_type":"refresh_token","refresh_token":"gy..."}
```

Persist both returned values. Guangya may rotate the refresh token; always save the returned `refresh_token` instead of assuming the old one remains valid. Validate the new access token with an authenticated account endpoint such as `/v1/user/me` and only print status code/length/prefix metadata.

## 2. Strict transfer selection

When a share contains multiple seasons or extra episodes, construct `video_files` from the inspected resource metadata and call the adapter with both constraints:

```python
accepted_episodes = [3, 4, 5, 6, 7, 8]
await CloudTransferService.process_auto_transfer(
    db=db,
    task=task,
    cloud_cfg=cloud_cfg,
    share_url=share_url,
    video_files=video_files,
    accepted_episodes=accepted_episodes,
    submission_group_id=submission_group_id,
)
```

The adapter's internal deduplication call must include `task_season=task.season`. For a task requesting season 2 and episodes 3–8, the expected candidate set is exactly `S02E03` through `S02E08`; `S01*`, `S02E01-02`, and other seasons must be skipped before `restore_share`.

## 3. Directory safety

The destination must be resolved in this order:

```text
影视转存总目录/<一级分类>/<二级分类>/<标准媒体目录>
```

Folder lookup/create calls must retry bounded transient timeouts. If any level cannot be confirmed, return a failed result and do not use the master folder as a fallback parent. A timeout fallback can create a plausible-looking but wrong root-level category; this is a data-placement bug, not a harmless warning.

If a test creates a wrong empty folder, the verified Guangya operations are:

- Move an existing folder: `POST /userres/v1/file/move_file` with `{"fileIds":["<id>"],"parentId":"<destination_id>"}`.
- Delete an empty test folder: `POST /userres/v1/file/delete_file` with `{"fileIds":["<id>"]}`.
- `recycle_file` is the restore-from-recycle-bin operation, not deletion.

After each state-changing call, read the relevant parent listing back. Do not accept an HTTP success response as proof that the state changed.

## 4. Asynchronous transfer proof

`restore_share` runs asynchronously. After receiving a task ID/result:

1. Poll `POST /userres/v1/file/get_file_list` with `parentId` and `pageNum` (not `page`).
2. Wait until the target folder is visible and the expected file count stabilizes.
3. Assert every expected filename is present.
4. Assert wrong-season filenames are absent.
5. Assert the folder's parent chain is the intended two-level taxonomy.
6. Assert all accepted `Resource` rows share the target `transferred_folder_id`.

A robust verification report should state the expected set, actual set, missing set, unexpected set, target folder ID, and hierarchy check without exposing credentials or private share tokens.

## 5. Idempotence proof

Run the same accepted group once more after the first verification. Expected behavior:

```text
success = true
transferred_files_count = 0
skipped_files_count >= number of already present candidates
same target_folder_id
no new root-level category/folder
```

This catches both duplicate-transfer bugs and accidental path recreation. A live test is complete only after both the first-run file-set check and the second-run idempotence check pass.