# Multi-version Movie Filename Normalization

## Scope

This reference captures the reusable workflow for a media-submission bot that accepts a movie share containing several encodes and must preserve all matching versions while repairing only safe filename defects during transfer.

## Decision matrix

| Situation | Review result | Transfer behavior |
|---|---|---|
| At least one file has a trusted full title and another has only a conservative, repairable abbreviation | Pass with explicit filename repair candidates | Keep every version; normalize only listed candidates |
| All files have clear titles but omit the TMDB marker | Apply the configured naming score; do not invent an ID | Preserve files; add the ID only when the canonical destination policy permits it |
| No file, task title, or trusted TMDB alias gives a reliable title | Fail closed | Do not rename or transfer |
| Filename is repairable but the actual work, year, media type, or TMDB identity conflicts | Fail closed | Naming repair must not mask identity failure |
| A file is ambiguous, malformed, an advertisement, or lacks enough technical structure to map safely | Fail closed for that file/group according to policy | Never guess a replacement name |
| Multiple encodes differ by quality/source/audio/etc. | Keep them as separate targets | Preserve the distinguishing technical tags and extensions |

A valid file is a title anchor, not permission to rewrite unrelated content. The implementation should carry the distinction in structured fields rather than infer it later from a free-form rejection message.

## Safe review output

A movie review result should carry, at minimum:

- the overall content/identity decision;
- per-file valid and invalid naming results;
- `filename_issues_repairable` (or equivalent) as a positive, structured signal;
- `filename_normalization_required`;
- an explicit mapping/list of source candidates that may be renamed;
- the canonical title source and aliases used for matching;
- the final canonical movie filename format and any preserved technical suffix.

The repairable signal must be narrow. Generic words such as “not standard” are insufficient if the same explanation could describe a content mismatch. Conversely, adding more content-mismatch phrases to a heuristic is only a defense-in-depth measure; the primary decision should be structured and fail closed when uncertain.

## Rename-plan shape

Build a plan from explicit candidate metadata, not from a directory-wide search:

```text
for candidate in review.filename_repair_candidates:
    require source path/name is present and uniquely identified
    require candidate is known to match the submitted movie
    derive canonical title from task/TMDB/trusted valid file
    preserve year, quality, source, codec, audio, fps, bit-depth, extension
    reject empty, duplicate, traversal, control-character, or ambiguous names
    add {source, final_name} to plan
```

Do not delete a non-matching file to make the set pass. Do not collapse two encodes merely because their repaired names share a title. If the final names would collide, stop and require an explicit disambiguator rather than silently overwriting either version.

## Transfer and verification contract

The transfer job should persist:

1. the source/share identity;
2. the exact destination folder ID;
3. the complete final expected-name manifest, including normalized names;
4. a state before the remote request;
5. a `RESTORE_SUBMITTED`-style fence before calling the provider when the request can have side effects.

After restore, enumerate the exact destination directory and verify every expected file. Do not fall back to a root, ancestor, guessed parent, or another folder when lookup is incomplete. A provider task ID, HTTP success, or destination folder ID is only an intermediate fact. Update resources and user-facing status only after artifact verification succeeds.

The post-restore rename boundary needs an explicit recovery design. Either persist enough state to verify both the original provider-produced names and final normalized names after a crash, or perform the operations in an implementation that has a proven idempotent state machine. Until that behavior has a restart test, do not call the release complete.

## Regression checklist

- [ ] Mixed movie versions: one valid name and one repairable abbreviation.
- [ ] All retained versions are represented in the final manifest.
- [ ] A correct filename supplies the title anchor without authorizing unrelated rewrites.
- [ ] Task/TMDB title aliases are used conservatively.
- [ ] Content mismatch still fails even when filename repair is possible.
- [ ] Ambiguous or malformed names fail closed.
- [ ] Distinct encodes remain distinct and no file is deleted.
- [ ] Final destination names, not source names, are verified.
- [ ] Rename count equals the number of successful candidate renames.
- [ ] Missing, partial, or ambiguous provider listings cannot produce success.
- [ ] Recovery after the remote-request fence never replays the side effect.
- [ ] Recovery behavior across the restore/rename crash boundary is tested.
- [ ] HTML status text escapes dynamic title, filename, and count values.
- [ ] Targeted, full-suite, and live-runtime evidence are reported separately.

## Release evidence vocabulary

Use precise labels:

- **synced**: the explicit source files reached the target tree;
- **tested**: the target environment passed the relevant test suites;
- **restarted**: the service process/container was restarted after the change;
- **live-verified**: the running process, health endpoint, polling path, and relevant user-facing status were read back;
- **released**: all required gates above are complete.

A local commit, a successful upload, or a passing test suite is not a live release. If deployment or remote synchronization is incomplete, report that state plainly instead of implying that users can already rely on the new behavior.
