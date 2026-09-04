# Checkpoint runbook: tested production change to private repository

This is a reusable runbook for a repair that spans an isolated source copy, a
live production worktree, a service manager, and a private GitHub repository.
It intentionally contains placeholders only; never place real tokens, cookies,
private URLs, or database contents in a runbook or transcript.

## A. Preflight manifest

Create a small manifest containing:

- source copy and authoritative production worktree;
- exact intended file allowlist;
- forbidden paths: `.env`, token files, private keys, database dumps,
  cookies, debug exports, and unrelated historical files;
- test command and focused test scope;
- production service unit, health route, and listening port;
- current commit, migration revision, PID, and rollback backup path.

A dirty production worktree is not automatically a blocker, but its unrelated
entries must remain untouched and absent from the staged file list.

## B. Test checkpoint

Use the sequence:

1. Add a focused failing regression test.
2. Run the focused test and retain the real failure.
3. Implement the fix with the file-edit tool.
4. Run focused tests, compile checks, and `git diff --check`.
5. Copy only the allowlisted application/test files to production.
6. Re-run the focused test in the target environment.

Do not skip the red test merely because the defect looks obvious. For security
fixes, use values such as `<bad>&`, malformed URLs, stale callback data, wrong
season/episode, unauthorized API codes, and concurrency barriers.

## C. Commit and service checkpoint

Before committing:

- stage explicit paths, never `git add .`;
- assert the staged names equal the allowlist;
- run `git diff --cached --check`;
- ensure no token-like or forbidden path is staged;
- record the new commit ID and subject.

Restart through the service's authorized non-interactive mechanism. Capture the
old and new PID. Wait for readiness rather than treating a changed PID as
sufficient. Verify:

- service is `active/running`;
- expected TCP port is listening;
- authenticated health/API routes return the expected status without printing
  credentials;
- fresh logs contain startup and normal worker/polling signals;
- new-PID logs contain no startup/import/schema/database failure;
- an old-process `CancelledError` during graceful shutdown is not confused with
  a new-process failure.

Only after this checkpoint should another independent repair batch begin. Do
not create a production restart checkpoint for every small intermediate patch;
keep related fixes together and checkpoint the completed batch once, unless an
incident or dependency requires an earlier restart.

## D. Safe GitHub API synchronization

Use a fine-grained token limited to the target repository. If the host already
has an authorized credential that the user has asked to retain, reuse it and do
not delete it after synchronization. Check only presence and mode (normally
`0600`); never print its value, place it in a URL or shell argument, or commit
it. Send API headers in memory:

- `Accept: application/vnd.github+json`
- `X-GitHub-Api-Version: 2022-11-28`
- `Authorization: Bearer <in-memory-token>`

Preflight with authenticated reads:

1. `GET /user` and `GET /repos/{owner}/{repo}`;
2. `GET /repos/{owner}/{repo}/git/matching-refs/heads/`;
3. `GET /repos/{owner}/{repo}/git/ref/heads/{branch}`;
4. `GET /repos/{owner}/{repo}/git/commits/{sha}` and its tree.

Do not infer branch existence from a local remote name. Compare the remote tip
with local HEAD, merge base, ancestry, file counts, remote-only paths, and the
allowlist. If the remote branch is not an ancestor of local HEAD, do not force
push.

For a reviewed non-rewriting fallback:

1. Optionally create a backup ref at the old remote SHA with `POST /git/refs`.
2. Upload only reviewed file blobs with `POST /git/blobs`.
3. Create a tree with `POST /git/trees`, passing the old tree as `base_tree` and
   explicit changed entries. A deletion requires explicit review.
4. Create a commit with `POST /git/commits`, the new tree, and the old remote tip
   as parent.
5. Update the branch using `PATCH /git/refs/heads/{branch}` with `force: false`.
   Stop on conflict; never automatically retry with `force: true`.

If ordinary Git HTTPS works, a normal non-force push is acceptable, but still
read the ref back. If Smart HTTP rejects a valid API credential, switch to this
API sequence rather than embedding the token in the remote URL.

## E. Mandatory read-back

After the write, read and compare:

- branch ref SHA;
- new commit SHA, parent SHA, and tree SHA;
- tree entries and changed paths;
- repository privacy/protection state when relevant.

The operation is complete only when the ref points at the intended commit, the
parent is the expected old tip, the changed paths equal the allowlist, and no
forbidden entry was uploaded. Retain a configured credential for later batches;
credential rotation or deletion requires an explicit user request.
