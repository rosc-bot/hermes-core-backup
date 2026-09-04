# Callback freshness and release evidence

## Why this matters

Telegram callback queries can arrive long after the message was rendered, can be replayed, and can race with a newer draft from the same user. A callback is therefore an external command with stale-input risk, not a continuation that may blindly read mutable FSM state.

## Freshness contract

For every side-effecting confirmation:

1. Create a draft revision or cryptographically opaque nonce.
2. Bind it to the authenticated user, chat/message context, intended operation, and an immutable snapshot or server-side draft row.
3. Put only the opaque identifier in callback data; do not trust client-supplied amounts, titles, episode lists, or administrator identity.
4. On callback, atomically verify that the identifier is current, unexpired, belongs to the caller, and has not been consumed.
5. Consume the revision in the same transaction as the request/charge/state mutation.
6. Reject stale, mismatched, expired, and repeated callbacks without creating a request or changing balance/state.

If the flow must survive process restart or multiple workers, store the draft/revision in the database and protect consumption with a row lock or conditional update. In-memory FSM storage is suitable only for ephemeral UI state, not for durable authorization or exactly-once business transitions.

## Minimum regression matrix

- Draft A rendered, then replaced by draft B; invoking A must produce zero mutations.
- Invoking B once must produce exactly one request and one charge, with B's immutable values.
- Invoking B again must be rejected idempotently.
- A callback from another user/chat must be rejected.
- An expired revision must be rejected.
- Concurrent invocations of the same revision must have one winner.

Test the handler-to-service boundary and inspect both return values and database state. A test that only asserts the callback string is insufficient.

## Exact media selections

Keep one canonical target-set function downstream of parsing:

- `NULL` means legacy `start_episode..total_episodes`.
- A non-NULL list is sorted, deduplicated, range-validated, and never expanded into a contiguous range.
- Movie requests reject episode selection and preserve empty episode fields.
- The canonical set must be reused for cost, missing-item calculation, submission validation, moderation, publication, and transfer verification.

Parse episode syntax before title normalization and remove the consumed selection token from the title source. Otherwise a fast `/seek` path can leave punctuation or an episode fragment in the persisted title even though the selection itself parsed correctly.

## Release evidence vocabulary

Record each gate separately:

- **synced** — the explicit allowlist was copied to the target and the target files were read back or hash-compared.
- **migrated** — the expected Alembic revision, columns, and indexes were read back.
- **tested** — targeted and full suites passed in the target runtime environment.
- **restarted** — the service process was restarted after the preceding gates and loaded the intended code version.
- **live-verified** — service status, logs, health/WebUI, polling, and a safe user-facing path were checked.

Never collapse these into “deployed.” A passing test suite does not prove that the running process loaded the tested files. If execution is interrupted by a tool/runtime limit, report only the evidence already observed and list the remaining gates; do not infer success from an attempted command.

## External transfer proof

For cloud-drive integrations, treat HTTP 200 and provider success codes as intermediate evidence. Fail closed on token/API errors, ambiguous or incorrect directory lookup, title-only shares, empty shares, cycles, and unimplemented adapters. Before marking success, enumerate the destination and verify every expected video artifact; mocked transfer tests must still exercise the destination-coverage predicate. Keep real cloud copies out of tests unless explicitly authorized.
