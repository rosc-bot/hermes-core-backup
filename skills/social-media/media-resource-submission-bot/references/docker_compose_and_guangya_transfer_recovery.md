# Docker Compose Cutover and Guangya Transfer Recovery

This reference records a tested, reusable deployment and recovery pattern for `tg-media-submission-bot`. It intentionally contains no credentials, private share URLs, database contents, or token values.

## 1. Container deployment shape

The validated Oracle layout containerizes only the application process:

```text
Compose service: tg-media-bot
  app.runner -> Telegram polling + FastAPI WebUI
  network: host (required because PostgreSQL remains on host loopback)
  user: non-root UID 1001
  root filesystem: read-only
  writable bind mount: /home/ubuntu/tg-media-submission-bot/data/metadata -> /app/data/metadata
  WebUI: existing port 12082
PostgreSQL: existing host service, not moved or recreated
systemd tg-media-bot.service: disabled after cutover, retained for rollback only
```

Build-context rules:

- Keep `.env` on the host and provide it through Compose; never copy it into the image.
- Exclude `.env`, database exports, private keys, tests, caches, and historical debug/token scripts in `.dockerignore`.
- Do not use `git add .` during a deployment commit. Stage only the named Dockerfile, Compose, ignore, documentation, or application files intended for the batch.

## 2. Tested cutover gate

1. Read-only inventory: record the current systemd PID, WebUI listener, PostgreSQL listener, Docker/Compose versions, and persistent data ownership. Do not print secret values.
2. Prepare `Dockerfile`, `compose.yaml`, and `.dockerignore`; run `docker compose config` before touching the old service.
3. Build the image without the old container being stopped. Run an image smoke check that imports the application, compiles source in memory or with bytecode disabled, verifies UID/non-root behavior, checks the data mount, and executes a read-only database `SELECT 1`.
4. Back up the systemd unit and any existing intended files. Stop and disable the old service, then verify its PID is gone and port 12082 is free. Do not stop PostgreSQL.
5. Start one Compose service with a bounded healthcheck. Verify `running/healthy`, a new container ID/image, port 12082, Basic Auth response, FastAPI startup, Telegram command registration, polling, and absence of new runtime faults.
6. Keep a rollback image tag and unit backup until the runtime gate is complete. If the container fails, restore the previous image/unit rather than leaving both pollers active.

A Compose deployment is complete only after the live container, not merely the image build, passes the gate. A local commit, GitHub synchronization, and live container rollout are separate claims and must be verified separately.

## 3. Guangya user-directory response contract

There are two different pagination APIs and they must not be conflated:

- User-drive directory listing: `POST /userres/v1/file/get_file_list` with `parentId`, `pageNum`, and `pageSize`. Do **not** include `page`; the API can return a response without `list` when the wrong field is supplied.
- Public-share listing: `POST /nd.bizuserres.s/v1/get_share_page_files_list`, whose pagination uses the public-share contract and may include `page`.

For the user-drive endpoint:

- `data: {"list": [...], "total": N}` is a normal non-empty/list response.
- An existing empty directory was observed to return exactly `data: {}`. Treat that exact empty object as `[]` so a newly created or empty destination folder can proceed to source resolution.
- Continue to reject `data: null`, non-dict data, and objects such as `{"total": 0}` without `list`; these are incomplete or ambiguous responses and must remain fail-closed.
- Use bounded request timeouts and retries for pre-side-effect directory reads. A transient TLS/read timeout is not proof that a transfer occurred.

Regression tests should assert both sides: empty `{}` is accepted, while total-only/incomplete data is rejected and the request body contains `pageNum` but not `page`.

## 4. Authorized real-transfer recovery

When the user explicitly asks to retry one failed transfer:

1. Identify one exact submission group from the latest failure, not every accepted resource lacking transfer metadata.
2. Preflight the task and resources: all selected rows are `ACCEPTED`; the accepted episode set equals the task's allowed set; media type/season match; source URL and file metadata are present; target transfer metadata is still unset; auto-transfer is enabled.
3. Let the adapter resolve the full hierarchy `影视转存总目录/<top category>/<sub category>/<standard media folder>`. Never fall back to an ancestor or root directory.
4. Do not call `restore_share` until directory resolution and complete source-share listing succeed. If an error happens before restore (no transfer task ID and no destination files), inspect the destination and use a bounded retry. Do not run an unbounded loop.
5. Once restore may have started, do not blindly replay on a network error. First read the target directory and use filename/season/episode deduplication; the replay is safe only when the destination state proves which expected files are already present.
6. Claim success only after the asynchronous destination listing contains every expected video filename, excludes wrong-season/unselected files, and the accepted database rows all persist the same verified `transferred_folder_id`. A task ID or HTTP success by itself is insufficient.
7. A transient verification timeout may be retried as a read, but the final report must use the actual destination file set and database readback. Never expose access/refresh tokens or private share URLs in logs or reports.

## 5. Evidence from the validated maintenance cycle

- Compose image build, non-root/read-only-rootfs checks, host-PostgreSQL `SELECT 1`, and healthcheck passed.
- The `pageNum`-only directory contract was reproduced against the live API; the target empty-directory response was `data={}`.
- After the empty-directory fix, the authorized exact transfer completed with 12 files transferred, 12 files remotely verified, and 12 accepted resource rows updated. One transient verification handshake warning occurred, but the final readback passed.
- The corresponding regression/full suite gate reached 167 passed before the live retry.
