# Repair, Security-Hardening, and Staged Oracle Rollout Reference

This reference records reusable techniques validated while maintaining `tg-media-submission-bot`. It is intentionally free of credentials, tokens, cookies, private URLs, database contents, and real cloud-side effects.

## 1. Safe staged rollout

1. Work in an isolated source copy; preserve unrelated production worktree changes.
2. Maintain an explicit allowlist of source files. Never synchronize `.env`, database exports, private keys, historical token/debug scripts, caches, or unrelated deletions.
3. For a green batch, compare SHA-256 hashes before and after explicit file synchronization. Run the matching focused suite in the target virtualenv.
4. If the operator requests “successful first,” restart immediately after the green batch and verify all of:
   - old/new MainPID differ;
   - `systemctl is-active` is `active`;
   - the configured WebUI port is listening;
   - authenticated `/health` and `/api/tasks/full` return HTTP 200;
   - the API shape/count is parseable without printing business records;
   - fresh journal entries show Telegram polling and no new import/schema/startup failures.
5. Continue unfinished fixes only after this intermediate release is verified. After later changes, perform a separate final test/commit/restart gate; the intermediate process must never be described as the final release.

## 2. Exact episode and FSM checks

- Use `requested_episodes is not None` rather than truthiness. `None` means the legacy `start_episode..total_episodes` range; a present list remains exact.
- Normalize exact lists by integer coercion, sorting, deduplication, positivity, and upper-bound validation. Use adjacent grouping only for display; never turn `[1, 3, 5]` into `1-5`.
- Reuse the canonical allowed-episode helper in request creation, missing calculations, review creation, approval, transfer filtering, channel messages, and WebUI progress.
- Generate a cryptographically random nonce for every seek confirmation card. Store it in FSM data and encode it in both submit and cancel callback data, for example `seek_confirm_submit:<nonce>` and `seek_cancel:<nonce>`.
- Reject callbacks whose prefix, separator, or nonce is missing or does not match the current FSM nonce. A stale callback must not clear or mutate a newer draft. Fixed-format callbacks from pre-nonce cards should fail closed.

## 3. Telegram HTML audit method

Search handlers and services for `parse_mode="HTML"` and inspect both direct f-strings and helper-returned strings. Every untrusted dynamic field must use the shared escape helper, including:

- titles, usernames, display names, cloud hashtags, share URLs, folder/file names;
- AI summaries, reasons, risk values, parser errors and exception text;
- database/config strings and leaderboard values.

Keep trusted bot fragments such as a previously generated review-card `html_text` intact when they intentionally contain markup. Add regression inputs containing `<script>`, `<b>`, `<u>`, `&`, and malformed URLs; assert raw tags never survive while intentional static tags still do.

## 4. Identity migration pattern

When application duplicate logic groups TV and ANIME together, the active-task index must do the same. Before migration, count normalized active duplicates with a read-only query. Use a PostgreSQL expression index shaped like:

```sql
CREATE UNIQUE INDEX uq_tasks_active_identity
ON tasks (
    lower(btrim(title)),
    (CASE
        WHEN upper(media_type) IN ('TV', 'ANIME') THEN 'SERIES'
        ELSE upper(media_type)
    END),
    year,
    coalesce(season, 0)
)
WHERE status = 'ACTIVE';
```

Post-migration, read `alembic current` and `pg_indexes.indexdef`, then recount normalized duplicate groups. A migration failure must be treated as unverified until the head and index definition are read back.

## 5. Cloud safety and async boundary

All blocking Guangya URL opening and response reads must be awaited through `asyncio.to_thread()`. Tests should assert the wrappers exist and that call sites await them. Parse explicit API success codes only; fail closed for authorization errors, empty/title-only shares, incomplete pagination, directory cycles, directory-as-file matches, non-video entries, missing target-file proof, and restore replay after side effects begin. No real transfer is needed for these tests.

## 6. Final evidence checklist

Run target-side focused tests for each repaired class, then the full `.venv/bin/pytest -q`, Python compile checks, `git diff --check`, migration revision/head checks, and JavaScript syntax checks. Stage only named intended files. Verify the commit, restart the service, confirm a new MainPID and authenticated WebUI responses, inspect fresh polling/error classifications, and report GitHub synchronization separately from local/production success. Never expose secret values while collecting evidence.
