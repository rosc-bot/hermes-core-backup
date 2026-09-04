# Review-to-transfer filename candidate propagation

## Failure pattern

A movie review can correctly use a matching share-folder title as the safe title anchor for a title-less release filename, for example:

```text
猎虎贰 (2026) {tmdbid-1745149}/2026.2160p.WEB-DL.H265.10bit.DDP5.1.mp4
```

The review stage may persist `filename_normalization_candidates`, while the transfer stage independently revalidates each candidate with the strict single-file validator. If the transfer validator does not receive the repairable-title flag, approval succeeds but transfer fails before `restore_share`; the destination folder can already exist and remain empty.

## Required propagation rule

- Treat the persisted candidate list as an explicit, deterministic approval output—not as permission to rename arbitrary files.
- When `_build_movie_rename_plan()` validates a selected filename that is present in that candidate list, pass the repairable-title mode (`allow_repairable_movie_title=True`).
- Keep the candidate set restricted to exact selected source names. Files not in the candidate list must not be renamed or relaxed by this path.
- The matching folder/task anchor, year, release specs, video extension, spam checks, content review, collision checks, and final post-rename verification remain mandatory.
- Build and persist final expected names before the remote side-effect boundary. The canonical form is `片名 (年份) {tmdbid-ID}.规格.ext`, omitting TMDB when unavailable and retaining resolution/source/frame-rate/codec/audio tokens.

## Diagnosis checklist

1. Compare the review report's `filename_normalization_candidates` with the transfer job's `expected_file_names`.
2. If `restore_started_at` is empty and expected names are empty, the failure occurred before remote restore; a newly created target folder may therefore be empty.
3. If the job is `RESTORE_SUBMITTED` or a restore request timed out, do not call `restore_share` again. Verify the exact target directory first. For a movie with a persisted `filename_normalization_candidates` list, the remote directory may temporarily expose the approved source filename instead of the final filename; when exactly one approved source file is visible, the adapter may call only the official idempotent rename endpoint, then re-list the same file ID and require the final name to be visible exactly once before committing database/channel success. A rename timeout must be re-verified by listing, not treated as permission to replay `restore_share`.
4. Channel publication is independent from cloud transfer: a published channel message is not proof that the remote files were transferred.

## Regression cases

Cover both the positive path (matching folder + title-less file produces a rename plan) and the negative path (mismatched folder rejects). Also cover the actual transfer adapter path so the review-stage allowance is not lost at `_build_movie_rename_plan()`.
