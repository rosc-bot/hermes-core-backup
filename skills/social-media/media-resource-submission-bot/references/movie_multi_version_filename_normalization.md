# Movie Multi-Version Filename Normalization

## Scope

Use this reference when a movie share contains several releases and at least one file has a trustworthy title while another uses a pinyin/acronym or legacy prefix. The goal is conservative normalization after a real transfer, not broad filename guessing.

## Canonical filename

```text
片名 (年份) {tmdbid-ID}.分辨率.来源.编码.音轨.ext
```

Examples:

```text
灵魂摆渡·天女之梦 (2026) {tmdbid-1754100}.2160p.EDR.60fps.WEB-DL.H265.10bit.DDP5.1.mp4
无TMDB示例 (2026).1080p.WEB-DL.H264.AAC.mp4
```

`/` is only a conceptual field separator in a request; never place a literal slash in a filename. Include a verified year and TMDB ID when available, and omit unknown metadata instead of fabricating it.

## Review acceptance matrix

- At least one video has a clear Chinese title or official multi-word English title matching the task: keep that file as the naming anchor.
- A second file with the same verified movie identity but a short abbreviation/legacy prefix may be an explicit normalization candidate if year, video extension, and enough release metadata remain recoverable.
- A lone short lowercase acronym with no trusted anchor remains rejected.
- Content mismatch, wrong movie, serial/advertising noise, generic nameless files, missing unrecoverable metadata, or ambiguous identity remains rejected.
- TV and ANIME do not inherit this relaxation: every video still requires strict season and episode markers.

## Candidate and transfer contract

1. Persist the review report before the slow cloud operation; consume only its explicit `filename_normalization_candidates` list.
2. Restrict the candidate map to the exact selected share files. Do not batch-rename every file in the share or infer candidates from a filename-only scan.
3. Build final expected names before the restore-side-effect fence so recovery knows the intended end state.
4. After `restore_share`, verify every expected file is visible in the exact destination folder.
5. Rename only explicit candidates through the provider's official rename API.
6. Re-list the destination and verify each renamed `fileId/name` pair. Any missing file, duplicate target, ambiguous match, API failure, or post-rename mismatch fails closed.
7. Persist accepted resource folder IDs and edit an already-persisted channel publication only after all final checks pass.

If the process restarts after the `RESTORE_SUBMITTED` fence, reconcile the destination read-only. Never replay `restore_share`; do not guess or attempt a speculative rename during that recovery path. A collision must never overwrite an existing version.

## Verified regression and rollout gates

- The focused production code file `tests/test_stage_y_movie_filename_normalization.py` passed 8 tests in the Oracle environment.
- The complete Oracle suite passed 185 tests after the normalization and recovery changes.
- Deployment verification must confirm the new Compose image imports the naming helper, the container is `running/healthy`, rootfs remains read-only with only the metadata mount writable, Telegram polling has started, WebUI unauthenticated access remains `401`, the systemd fallback is `inactive/disabled`, and `transfer_jobs` has no unexpected active rows.
- A successful cloud API response or task ID alone is never evidence of a successful rename or transfer; the destination readback is the acceptance proof.
