# Media-submission hardening lessons

This reference records reusable lessons from a stateful Telegram media-submission bot repair. It is intentionally provider-agnostic and contains no credentials, private share URLs, or production identifiers.

## Acceptance matrix for exact episode selection

The canonical contract should be tested at every boundary:

| Boundary | Required assertion |
|---|---|
| Input/parser | Accept full range and sparse lists; deduplicate and sort; reject malformed or out-of-range values; reject episode selection for movies |
| Persistence | Store the exact list; `NULL` retains legacy `start_episode..total_episodes` behavior |
| Task/request creation | The handler passes the canonical list into the service; the service does not silently rebuild a contiguous range |
| Missing calculation | Only requested episodes are considered; a sparse request such as `[1, 3, 5]` never becomes `1..5` |
| Submission | Every submitted episode is checked against the task's season and requested set |
| Moderation | Re-check task state and requested set while holding the required lock; do not trust an earlier UI check |
| Auto-transfer | Select only accepted resources belonging to the active task and requested set; update only resources actually accepted |
| Display | Channel, Telegram review text, and WebUI show sparse selections without implying missing episodes were requested |

A focused test of one layer is not propagation proof. Add at least one end-to-end service-level test that starts with the input representation and asserts the persisted task, missing set, moderation decision, and transfer candidate set.

## Concurrency scenarios

Use two independent database sessions/connections, a barrier around the contested operation, and assertions on both return values and the final rows.

1. **Exclusive claim:** exactly one caller succeeds and the stored claimant is that caller.
2. **Balance spend:** the balance is deducted once and the ledger sum equals the actual deduction.
3. **Cancellation versus review:** cancellation cannot refund and leave a reviewable submission that can later be approved. Approval must re-read the parent state after obtaining the agreed lock.
4. **Expiry/release versus claim:** a worker cannot release or expire a task based on a stale unlocked read.
5. **Duplicate creation:** application pre-checks may improve messages, but a database uniqueness constraint is the final guard; handle the integrity error without exposing a traceback.

Keep lock ordering consistent across these paths. Write down the order in the skill/test comments so a future change does not introduce a deadlock while fixing a race.

## Provider and parser tests

For a share-based cloud provider, test separately:

- share identifier extraction and access-code extraction, including access codes placed after a URL;
- boolean query parameters represented as strings (`"false"` must not become Python truthy);
- pagination across all pages and nested directory traversal;
- directory lookup failure as a hard failure, not a fallback to a parent/root directory;
- partial file matches as failure or pending, never complete success;
- byte-size units such as `B`, `KB`, `MB`, and `GB`;
- unimplemented adapters returning failure rather than success-shaped placeholders.

A provider HTTP 2xx, task ID, or destination folder ID is only provisional evidence. Final success requires reading the destination and proving the complete expected file set is present.

## Release evidence checklist

Record these as separate gates:

1. **Backup:** scoped production files have a verifiable backup path.
2. **Sync:** an explicit allowlist was copied; `.env`, database dumps, cookies, and historical secret-bearing scripts were excluded.
3. **Migration:** the database revision, required columns, and indexes were read back.
4. **Targeted tests:** new regression tests pass in the target virtualenv.
5. **Full tests:** the complete suite passes in the same environment.
6. **Reload:** the service was restarted and its new process was confirmed.
7. **Live checks:** service status/logs, listening WebUI, Telegram polling, and schema are healthy.
8. **Version control:** only intended files are staged; the diff and staged names were inspected for secrets and unrelated deletions.

If gates 1–5 pass but 6–7 have not happened, report “code and schema validated; release pending reload/live verification.” Do not call it deployed.

## Async boundary audit

Moving one legacy blocking call behind `asyncio.to_thread` is only complete after all synchronous network/SDK call sites in async paths use the wrapper or are otherwise isolated. Search for direct `urlopen`, synchronous HTTP clients, filesystem scans, and blocking subprocesses, then test the async method with a stubbed provider. Do not claim event-loop safety from the existence of a helper alone.
