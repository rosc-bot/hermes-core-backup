# Transfer Interruption and Restart Recovery

Use this reference when an admin review card remains at `⏳ 正在转存` longer than expected, especially after a container/systemd deployment or process restart.

## Failure pattern

The unsafe legacy shape is:

1. `admin_approve` edits the review card to a progress message.
2. The same handler awaits `process_auto_transfer` inline.
3. A rollout kills the process before the adapter verifies the destination and commits `Resource.transferred_folder_id`.
4. Telegram keeps the old progress text, while the database contains an accepted resource with no transfer metadata. A new healthy process does not automatically resume that coroutine.

A `running/healthy` service, a Telegram polling connection, or a successful approval callback is not evidence that the cloud transfer is still active.

## Read-only incident probe

For the exact task/submission group, collect only non-sensitive facts:

- `Task.status`, `Resource.status`, `accepted_at`, `submission_group_id`, and whether `transferred_folder_id`/`transferred_share_url` are present;
- cloud configuration flags (`auto_process`, `process_type`, target configured), never credential contents;
- container/process start time, restart count, and recent logs after approval;
- whether the current process has a provider connection (corroborating evidence only);
- a read-only listing of the exact master/category/media target folder using a valid access token. Do not call `restore_share`, create a directory, rename a candidate, move a file, or refresh/persist credentials merely to diagnose unless separately authorized.

Compare the approval/acceptance timestamp with the process start/restart timestamp. If the process started immediately after acceptance, transfer fields are still empty, no provider activity is present, and the exact target folder is absent, classify the card as **stale/interrupted**, not “still transferring.” If the access token is expired, record that the cloud readback is incomplete instead of guessing; credential refresh is a separate action.

## Safe recovery gate

Before retrying an interrupted item:

1. Obtain explicit scope for the exact task/resource or `submission_group_id`; do not process other accepted submissions.
2. Re-check the target hierarchy and expected file set read-only. A folder/file that already exists may mean the restore had a side effect even if the database was not committed.
3. If the restore boundary may have been crossed, do not automatically replay. Deduplicate against the actual destination and use a provider task-status/readback path when available.
4. If the readback proves no side effect and the failure was before `restore_share`, one bounded retry is allowed by the transfer policy. Match only the exact movie or season/episode set.
5. After the restore, poll the exact target folder and verify every expected filename. Only then commit the accepted `Resource` transfer fields and edit a uniquely persisted original channel/review message. A Telegram edit failure must not turn a verified cloud transfer into a false failure.

Do not use a manually edited success field, task ID alone, or a progress-card timestamp as proof of transfer.

## Durable implementation requirement

The preferred fix is a persistent transfer outbox/job table:

- insert the job and its exact selection/idempotency key before publishing the progress state;
- claim with a lease/heartbeat so only one worker can run a group;
- persist `restore_started` before the provider restore boundary;
- on startup, reconcile `RUNNING`/`RESTORE_STARTED` jobs against the destination before resuming or marking them failed;
- make final success atomic with verified resource metadata, then update the existing message using persisted `channel_id`/`message_id`;
- render an explicit `转存中断，等待恢复` or failure state when no worker owns the job, never an indefinitely optimistic `正在转存`.

## Regression tests

Add tests for:

- progress edit followed by cancellation/restart before transfer starts;
- restart after `restore_started=True`, proving no automatic replay;
- stale `ACCEPTED` rows with empty transfer fields being discovered by startup reconciliation;
- destination already containing the expected file while the database is stale;
- healthy service with no active transfer being reported as idle/stale rather than active;
- final database/message updates occurring only after per-file destination verification.
