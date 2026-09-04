# Database-Backed Repair Runbook

This reference supports `production-bot-reliability` for bots and web services with workflow state, balances, schemas, and external storage providers.

## Invariant examples

Turn the defect into an assertion before implementation:

- Two concurrent claimers produce exactly one success; the final task row names that winner.
- A balance never becomes negative; two concurrent requests cannot spend one balance unit twice; the ledger sum equals the actual deductions.
- Cancelling a parent request makes old pending/review children ineligible for approval.
- A transfer is successful only when every expected selected file is present in the destination.
- A sparse selection such as `[1, 3, 5]` remains sparse at creation, missing-item calculation, moderation, transfer, and display.

## Concurrency reproduction

Use two independent database sessions/connections. Coordinate the contenders at the contested operation, then collect each return value and read the final row in a third read. A sequential test can validate basic behavior but cannot establish exclusivity.

For a read-modify-write, the durable pattern is:

```text
BEGIN
lock the contested row (for example, SELECT ... FOR UPDATE)
read the now-current state
if the operation is no longer allowed: return failure
apply state, balance, and dependent-row changes
COMMIT
```

Keep the lock and the guarded mutation in the same transaction. A check performed before the lock may optimize the common path, but must not decide correctness.

## Balance and ledger checks

When a penalty or charge exceeds the current balance, deduct `min(requested_amount, available_balance)` while holding the balance-row lock. Record the actual deduction in the ledger. Test zero balance, exact balance, insufficient balance, and two concurrent spenders. Never make a test pass by weakening the non-negative assertion.

## State invalidation

Treat cancellation as a transaction boundary: update the parent, refund or settle its accounting, and invalidate dependent pending/review rows together. Re-check the parent state in the approval service, because stale handlers, retries, or queued jobs can outlive the cancellation event.

## Exact episode contract

Use an explicit compatibility contract:

- `NULL` means a legacy full-range task and resolves to `start_episode..total_episodes`.
- A non-null list is deduplicated and bounds-checked against `1..total_episodes`; it is not expanded into a range.
- Movies reject episode selections and keep season/episode fields empty.

Test at least: full range, contiguous list, non-contiguous list, duplicates, zero, an upper-bound value, an out-of-range value, malformed input, and movie input. Then verify every consumer uses the same resolved target set.

## External provider verification

Keep the share identifier and trailing access code separate during parsing. Traverse all pages and nested directories that can contain source or destination files. If the intended destination directory cannot be found, fail closed instead of using the root or a guessed parent.

Treat API success as provisional. Compare destination artifacts with the complete expected set, including every selected episode/file, before persisting success. For a provider adapter whose API is not implemented, return a clear failure and do not create synthetic IDs or success records.

If a synchronous provider client is called by async code, run the blocking section in a worker thread and test that the event loop remains usable.

## Release checklist

1. Snapshot only the files in scope and record the backup location.
2. Transfer an explicit allowlist; exclude environment files, credentials, cookies, database exports, and secret-bearing historical scripts.
3. Run syntax checks and focused regression tests.
4. Apply the migration before restarting code that imports the new schema.
5. Verify the schema revision and new column by reading back the target database.
6. Run the full suite in the service's actual environment.
7. Restart only after all prior gates pass.
8. Read back service status, logs, endpoint health, bot polling, and schema state.
9. If a gate fails, leave the old process running where possible, restore from backup if required, and report the observed failure without claiming release success.

## Security checks

Authorization must come from authenticated server-side identity, not a request field such as `admin_id`. Escape untrusted text before Telegram/browser HTML rendering and avoid `innerHTML` for user-controlled values. Sanitize path components against traversal and control characters. Never print or commit tokens, passwords, cookies, database dumps, or complete private share URLs.
