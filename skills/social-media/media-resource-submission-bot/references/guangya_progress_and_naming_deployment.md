# Guangya Transfer Progress, Naming, and Deployment Verification

This reference captures the reusable lessons from the latest Oracle rollout of `tg-media-submission-bot`. It contains no access or refresh token.

## 1. Status lifecycle invariant

The approval callback has two different user-visible phases:

1. `SubmissionService.approve_submission` completes the database approval.
2. Before any potentially slow Guangya operation, save the original review-card HTML (`review_html`) and edit the same Telegram message to show `⏳ 正在确认目标目录并转存对应文件，请稍候…`.
3. Run directory resolution, exact share-file selection, `restore_share`, and asynchronous destination verification.
4. Build the final card from the saved `review_html`, never from the progress-edited message. This prevents duplicate progress lines or stale inline markup.
5. Use the actual `TransferResult`: only `success=True` after every expected filename is visible may render `已通过审核并转存入库`; a timeout or failed transfer must render `审核已通过，但转存未完成`.
6. Submitter DMs and callback toasts must use the same truth source. Channel publication status must be reported separately from cloud-transfer status.

Persist `Resource.transferred_folder_id` only after the destination proof succeeds. A successful `restore_share` response or task ID alone is not proof of storage.

## 2. Conservative destination-folder normalization

Compute the target name only through `MediaNamingValidator.build_standard_folder_name`, and resolve the path as:

```text
影视转存总目录/<一级分类>/<二级分类>/<标准媒体目录>
```

Resolution order:

- Reuse an exact standard media-folder name first.
- If no exact match exists, inspect only media-folder candidates in the correct second-level parent.
- Rename at most one candidate, then re-list the parent and verify that the same folder ID now has the desired name.

The matching gate must fail closed:

- TV/anime: title compatibility plus the requested season, or a compatible exact TMDB ID; if a year is present and conflicts, reject the candidate.
- Movies: title compatibility plus matching year, or a compatible exact TMDB ID; reject a season folder.
- Never rename a title-only or ambiguous candidate, a taxonomy folder, or a candidate with a conflicting TMDB ID/year/season.

If any master, top-level, sub-level, or media-folder listing cannot be confirmed after bounded retries, return failure and never use an ancestor as a fallback parent.

## 3. Strict selection and auth boundaries

For a multi-season share, pass `task.season` into `_deduplicate_files` and compare `(season, episode)` keys. `S01E01` must not make a requested `S02E01` look duplicated. When `accepted_episodes` is supplied, an unparseable episode is ineligible. For a season-scoped transfer, an unparseable season is also ineligible.

Match selected database filenames to share items by exact filename first, then by a controlled `(season, episode)` fallback. Never fall back to all share IDs when matching fails. Share authorization/listing errors must fail closed; HTTP 401 must propagate to the single outer refresh-and-retry boundary instead of being swallowed as an empty/partial listing.

## 4. Verified deployment gate

For production changes on the Oracle host:

1. Keep patched files in a staging copy and run `py_compile` locally.
2. Back up the current remote files before copying; synchronize only the intended source and test files and compare SHA-256 hashes.
3. On the remote host run `py_compile`, `git diff --check`, the focused transfer tests, and then the complete `tests/` suite.
4. Run deterministic no-write probes for strict season filtering, standard-name generation, and the normalization safety gate.
5. Restart `tg-media-bot.service` only after tests pass. Verify `active/running`, the new PID, FastAPI/WebUI HTTP 200, `Application startup complete`, and Telegram polling startup in `journalctl`.
6. Perform one safe idempotence check against an already verified group. The expected result is `success=True`, `transferred_files=0`, all existing candidates skipped, the same target folder ID, and no new root-level taxonomy folder.

A real new transfer is not required merely to validate a code rollout when it would award points, publish a channel post, or mutate archive content; use mocks for the asynchronous-success and naming-rename branches, and use an already-complete group for the live idempotence proof.

## 5. Test-contract maintenance pitfalls

New transfer parameters and post-restore verification change mocks as well as production code. Existing `_find_or_create_folder` mocks should accept the new optional keyword arguments (for example, `**kwargs`), and tests that exercise the transfer path should mock `_wait_for_transferred_files` with the expected filename set. A legacy `/add` test that expected an immediate preview must be updated to expect the single-title TMDB disambiguation keyboard; do not remove the interactive behavior just to satisfy an outdated assertion.

## 6. Latest verified evidence

The rollout validated the following without exposing credentials:

- Focused transfer/status/normalization tests and related legacy tests: 20 passed.
- Complete repository test suite: 96 passed.
- An already-complete season-2 group was rerun live: `success=True`, `transferred_files=0`, `skipped_files=16`, target folder ID remained `1942660980482084923`, and all six accepted resource rows retained that folder ID.
- The service restarted cleanly into `active/running`; WebUI returned HTTP 200 and the bot entered Telegram polling.
