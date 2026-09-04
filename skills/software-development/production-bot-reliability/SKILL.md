---
name: production-bot-reliability
description: "Use when repairing stateful bots. Test, lock, verify."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [production, bots, reliability, transactions, concurrency, migrations, integrations]
    related_skills: [test-driven-development, systematic-debugging, media-resource-submission-bot]
---

# Production Bot Reliability

## Purpose

Use this class-level skill when repairing or extending a production bot or web service whose behavior spans Telegram handlers, database state, balances/credits, asynchronous jobs, external storage providers, or an administrative WebUI.

The objective is not merely to make a unit test pass. A reliable change preserves invariants under concurrency, remains compatible with existing rows, fails closed when an external provider is ambiguous, and is not called released until the target runtime has been read back and verified.

## Operating principles

1. **State the invariant first.** Express the bug as a falsifiable rule: one winner for an exclusive claim, no negative balance, no approval after cancellation, complete destination coverage before transfer success, or exact preservation of a sparse episode list.
2. **Use TDD for every behavior change.** Write one focused regression test, run it and confirm the expected behavioral failure, implement the smallest fix, run it green, then run the relevant regression set. Do not replace a meaningful failure with a changed assertion merely to get green.
3. **Enforce races at the database boundary.** Application-level pre-checks are optimizations, not concurrency control. Lock or atomically update the contested row, re-check the state after acquiring the lock, and commit the state transition and related rows together.
4. **Make side effects fail closed.** A provider's HTTP success response is provisional. Verify the resulting artifacts, and never let an unimplemented adapter return a success-shaped placeholder.
5. **Preserve old data deliberately.** New columns and new selection semantics need explicit compatibility rules and migration tests. Avoid broad defaults that silently reinterpret invalid or legacy input.
6. **Verify the release, not just the copy.** Backup the scoped production files, transfer an explicit allowlist, migrate before restarting code that reads a new column, run tests in the target environment, then verify the service and user-facing paths.

## Standard repair workflow

### 0. Docker Compose 容器化与运维迁移规范 (Containerization Operations)

当将系统原生 systemd 服务（如 Telegram Bot、API 渲染微服务、监控脚本等）迁移至 Docker Compose 容器化编排时，必须严格遵守以下关键规范：
1. **命名规范与中文字符限制**：
   - Docker 守护进程严格禁止在容器名称 (`container_name`) 中使用非 ASCII / 中文字符，仅允许 `[a-zA-Z0-9][a-zA-Z0-9_.-]`。
   - 若用户需要中文标识，应在 Compose 文件中使用 `labels`（如 `name: "emos签到机器人"`）或拼音/易读短名，不可直接在 `container_name` 中填入中文。
2. **构建缓存与磁盘管理 (Build Cache Pruning)**：
   - 在内存/磁盘受限的 VPS 上使用 BuildKit 多阶段构建带有复杂原生依赖（如 Canvas、Cairo、Pango、字体包）的镜像时，会迅速生成数 GB 的临时构建切片。
   - 部署验证后，必须检查磁盘容量（`df -h`），必要时执行 `docker builder prune -a -f` 回收未引用的 Build Cache，严禁让构建缓存占满根分区。
3. **依赖完整性 (PTB JobQueue 与原生模块)**：
   - 使用 `python-telegram-bot` 20+ 的定时任务功能时，容器内必须安装 `python-telegram-bot[job-queue]`（携带 `APScheduler` 与 `pytz`），否则初始化时 `app.job_queue` 会静默为 `None`。
   - Node.js 原生 C++ 扩展（如 `canvas`）必须在匹配的 Node 主版本下编译安装，避免宿主机 node_modules 跨版本挂载导致 `ERR_DLOPEN_FAILED`。
4. **旧服务完全清理与防冲突**：
   - 容器启动验证就绪后，必须立即停止并彻底删除旧的 systemd 单元文件（`/etc/systemd/system/<unit>.service`），并执行 `systemctl daemon-reload`，避免双重轮询或端口冲突。

### 1. Discover before editing

- Identify the service entrypoint, database/session layer, state enums, ledger tables, external-provider adapters, migration head, test command, and health endpoints.
- Inspect the current runtime without exposing tokens, passwords, cookies, private share URLs, database dumps, or secret-bearing test fixtures.
- Reproduce the defect against an isolated database or disposable records. Do not mutate production business data during reproduction.
- Record the current service state and prepare a rollback backup before any production file replacement.

### 2. Build an acceptance matrix

Cover the happy path, the boundary, an invalid input, a terminal parent state, a concurrent invocation, and an external-provider partial-success case. Include downstream consumers, not only the handler that accepts the input.

For a media/request workflow, the matrix should include task creation, missing-item calculation, duplicate detection, contributor submission, moderation, automatic transfer, display, and cancellation/refund behavior.

### 3. Reproduce concurrency with real transactions

Use two independent sessions/connections and synchronize the contenders at the contested operation. Assert both return values and the final row. For a balance, also assert successful operation count and ledger sum.

The safe shape is:

```text
BEGIN
SELECT contested row FOR UPDATE
re-check current state/balance
apply state transition and dependent changes
COMMIT
```

For an exclusive task claim, exactly one caller succeeds and the stored claimant matches that winner. For spending, the locked balance is checked and deducted once; a penalty is capped at the available balance and the ledger records the actual deduction, never the requested deduction when it exceeds the balance.

### 4. Guard state transitions at every entry point

A UI check is not a business rule. Enforce parent-state checks in creation, submission, review, approval, retry, and background-job paths. When a request is cancelled, invalidate or reject dependent `PENDING`/`REVIEW` records in the same transaction. Approval must re-check that the parent is still active immediately before changing state.

### 5. Canonicalize exact selections once

If a workflow supports both legacy ranges and exact sparse selections, define the representation explicitly:

- `requested_episodes == NULL`: legacy full range `start_episode..total_episodes`.
- A list: deduplicate, validate against `1..total_episodes`, preserve only the listed episodes, and use that same canonical list everywhere.
- A movie: reject episode selection and keep season/episode fields empty.

Never convert `[1, 3, 5]` into `1..5`, silently turn invalid input into a default such as 24 episodes, or let different layers calculate different target sets.

### 6. Validate external transfers by outcome

Parse share IDs and access codes independently. Paginate every relevant listing and recurse where the provider exposes nested directories. Locate the intended destination directory explicitly; if lookup fails, stop rather than falling back to a root or guessed parent.

Before setting a transfer to successful, compare the destination with the complete expected target set. A provider API response, folder ID, or task submission response is not sufficient by itself. Keep partial/ambiguous results failed or pending. Adapters without a real provider implementation must fail closed.

When synchronous HTTP or SDK work is called from an async bot, move the blocking portion off the event loop and test both the parser and the async boundary.

### 7. Include security in the acceptance criteria

- Derive authorization from the authenticated server-side identity; do not trust a client-supplied administrator ID.
- Escape user-controlled text before Telegram HTML or browser HTML rendering.
- Prefer text APIs or DOM text assignment over `innerHTML` for untrusted values.
- Sanitize every user-controlled path component and reject traversal/control characters.
- Keep credentials and private provider links out of logs, diffs, test output, commits, and transfer manifests.

### 8. Release gates

Run the following in order:

1. Back up only the production files in scope and record a verifiable backup path.
2. Sync an explicit allowlist of code, tests, and migrations; exclude `.env`, credentials, cookies, database exports, and historical secret-bearing scripts.
3. Run syntax checks and targeted tests, including the newly added regression tests.
4. Apply the schema migration and verify the migration revision and required columns before starting new code.
5. Run the complete test suite in the same environment used by the service.
6. Restart only after the prior gates pass.
7. Read back service status, process/log health, listening endpoint, WebUI health, Telegram polling, and the migrated schema.
8. If a gate fails, keep the old service running when possible, restore from the backup if necessary, and report the exact observed failure. A successful file copy or restart is not proof of a successful release.

If a test runner exits without a usable failure/pass report, rerun with the project's configured virtualenv or CI command and capture the actual output; do not treat an unexplained exit code as a test result.

## Verification checklist

- [ ] A regression test existed before the implementation change.
- [ ] The regression test was observed failing for the intended reason.
- [ ] Concurrent behavior was tested with independent transactions where relevant.
- [ ] Read-modify-write operations are protected by database locking or an atomic conditional update.
- [ ] Balance and ledger invariants are asserted together.
- [ ] Terminal parent states are enforced in every mutation path.
- [ ] Legacy and exact-selection semantics are explicit and tested downstream.
- [ ] External success is based on complete artifact verification.
- [ ] Invalid provider lookup and unimplemented adapters fail closed.
- [ ] Security tests cover authorization, HTML escaping, and path traversal.
- [ ] Migration was applied before restart.
- [ ] Targeted tests, full tests, and live runtime checks all passed.
- [ ] No secret value or complete private link appears in output or version control.

## Media-submission hardening addendum

For media-submission bots, treat an exact selection as a data contract rather than a UI feature: audit and test propagation from the admin/request handler through task creation, missing-item calculation, submission, moderation, automatic transfer, channel notices, and WebUI. Keep the legacy `NULL` meaning explicit, and keep movie episode fields empty. A passing handler test is insufficient if a downstream service reconstructs a range.

### Bind confirmation cards to immutable draft revisions

A Telegram confirmation message is a delayed, replayable input, not a trusted continuation of the current FSM state. Never let a fixed callback such as `confirm_submit` read whatever draft happens to be in mutable per-user storage. Bind each confirmation to an opaque, one-time nonce or monotonically increasing draft revision, and validate the nonce against the current user/chat/draft before charging, creating a request, or mutating state. Reject stale, expired, mismatched, and already-consumed confirmations without side effects. Prefer a server-side immutable draft record when the flow can span restarts or workers; `MemoryStorage` alone is not a durable coordination mechanism.

The regression test must create draft A, replace it with draft B, invoke A's callback, and assert that no request or balance mutation uses B's data. Then invoke B once and assert exactly one mutation; repeat B and assert idempotent rejection. Test this at the handler/service boundary rather than only checking the callback string. When introducing such a test, implement and export the validator in the same change and run a compile check immediately—an imported-but-absent helper is a test wiring failure, not evidence about business behavior.

Use separate evidence labels during release: **synced** means files were copied, **migrated** means the schema revision and columns were read back, **tested** means the target environment passed the suites, **restarted** means the running process loaded the new code, and **live-verified** means user-facing health and polling paths were checked. Never report the earlier label as the later one. In particular, full tests passing while the service has not been restarted is a pending release, not a deployment.

When cancellation, expiry, approval, retry, and transfer workers can race, document one lock order and exercise the competing transactions with independent sessions. Re-check the parent task after acquiring its lock immediately before mutating a dependent submission. For external transfers, keep tests mocked and prove artifact verification without performing a real cloud-side copy unless explicitly authorized.

For production synchronization, use an explicit allowlist and stage named files; never use `git add .` in a repository containing historical debug scripts, database exports, or local artifacts. Audit the diff and staged file list for credentials and private links before committing. If an async bot still contains legacy `urllib`/SDK calls, audit every call site after introducing an executor helper—adding a wrapper that is not actually used everywhere does not remove event-loop blocking.

When applying targeted text patches, run a syntax/compile check immediately and re-read the surrounding function before copying the file. A partial replacement can leave a syntactically valid-looking but truncated function declaration, and a successful patch response is not a code-validation result. If the source tree is an archive without Git metadata, use it for code/test comparison only; perform Git status, selective staging, and commit checks in the actual repository tree rather than inventing local history.

See `references/database-backed-repair-runbook.md` for the compact invariant examples, concurrency test shape, exact-selection contract, provider verification rules, and release sequence. See `references/media-submission-hardening-lessons.md` for the detailed acceptance matrix and release evidence checklist. See `references/remote-copy-integrity.md` for the explicit transfer-manifest, hash-comparison, and fresh-process evidence pattern.

### Multi-version movie naming normalization

When one movie submission contains multiple encodes, evaluate naming per file rather than treating the share as one all-or-nothing filename. A correctly named file, the task title, and trusted TMDB titles/aliases can provide a title anchor for files whose prefixes are merely abbreviated or otherwise repairable. Do not let one repairable `tnzm`-style prefix veto otherwise matching versions, but do not use a naming repair to override a content, identity, year, media-type, or TMDB mismatch.

Keep the decision and the mutation separate:

1. The review result must distinguish `filename_issues_repairable` from content/identity failures and must emit an explicit, structured list of rename candidates.
2. The transfer layer may rename only those candidates; it must never scan and rewrite every file in a folder or infer a title from an ambiguous filename.
3. Preserve every version's quality, source, codec, audio, frame-rate, bit-depth, extension, and other meaningful tags while replacing only the unsafe title portion with the canonical movie format.
4. Recompute the expected destination manifest after normalization. Success requires every retained target file to be found in the exact destination directory under its final name; an API success response, task ID, or folder ID alone is not evidence of completion.
5. Persist the final expected names and the transfer state before the remote side effect. Once a restore request may have been submitted, restart recovery must perform read-only destination verification and must not replay the remote restore. The crash boundary between restore and rename is a release blocker until both pre-rename and post-rename recovery behavior are explicitly tested.

The regression matrix should include: one valid and one repairable movie version; all files repairable; no trustworthy title anchor; content mismatch despite repairable naming; duplicate versions that must remain distinct; exact final-name verification; rename count reporting; and a restart after the remote request boundary. Record release evidence separately as synced, tested, restarted, and live-verified—passing tests or copying files does not prove that the running container loaded the change.

See `references/movie-multiversion-normalization.md` for the decision matrix, safe rename-plan shape, recovery boundary, and release-evidence checklist.
