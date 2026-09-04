# Movie folder-anchored filename repair

## Problem pattern

A movie share may have a correctly named folder while a selected video contains only release metadata, for example:

```text
猎虎贰 (2026) {tmdbid-1745149}/2026.2160p.WEB-DL.H265.10bit.DDP5.1.mp4
```

The strict single-file title check must not reject this before the repair path runs.

## Decision table

| Condition | Decision |
|---|---|
| Parsed folder title normalizes to the task title/alias; file has year + release specs + video extension | Allow AI/human content review; add only the exact original filename to normalization candidates |
| Folder title is absent, ambiguous, or does not match the task | Reject; do not infer a title from the file alone |
| File lacks year or release specs | Reject unless a separately verified rule can reconstruct the name safely |
| Advertising/garbage filename or content mismatch | Reject; rename repair never overrides content safety |
| TV/anime file lacks a valid season/episode marker | Keep strict TV rejection behavior |

A weak abbreviation such as `tnzm.2026.2160p...` is a rename candidate only when a trusted matching folder/task anchor exists. A lone abbreviation without an anchor remains rejected.

## Canonical output

```text
片名 (年份) {tmdbid-ID}.分辨率.来源.编码.音轨.ext
```

Include `{tmdbid-ID}` only when the task has a verified TMDB ID; never invent one. Preserve resolution, source, frame rate, codec, bit depth, audio, and group tokens so releases do not collide. `/` is not a safe filename separator, so use parentheses/braces and dots.

## Safe transfer order

1. Validate the folder anchor and build candidates from exact selected filenames.
2. Obtain human/AI content approval; naming repair is not content approval.
3. Persist the recovery fence and expected final names before the remote side-effect boundary.
4. Call remote restore only once when the request may have produced side effects.
5. Verify every selected file is visible in the exact target directory.
6. Rename only explicit candidates through the provider API; never guess or batch-rename all files.
7. Re-list the target directory and verify every final `fileId/name`; fail closed on ambiguity or collision.
8. Update resource/database/channel state only after all final checks succeed.

## Regression recipe

From the production worktree:

```bash
.venv/bin/pytest -q tests/test_stage_y_movie_filename_normalization.py
.venv/bin/pytest -q
.venv/bin/python -m compileall -q app tests
git diff --check
```

The regression must cover both the positive case (`猎虎贰 (2026) {tmdbid-1745149}` + `2026.2160p...mp4`) and the negative case (mismatched folder).