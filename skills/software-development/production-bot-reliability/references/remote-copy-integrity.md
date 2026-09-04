# Remote Copy and Runtime Evidence

This reference applies when a repair is developed in one tree and deployed to a different service host.

## Keep three trees conceptually separate

1. **Source tree:** the reviewed code and tests.
2. **Repository/deployment tree:** the files that will be committed and used by the service.
3. **Running process:** the code already loaded by the service.

A source edit, a copied file, a commit, and a restart are four different milestones. Report them separately.

## Build an allowlist

Write the relative paths that are intentionally part of the change. Include source, migration, and regression-test files only. Exclude environment files, private keys, cookies, tokens, database exports, debug scripts, generated caches, and unrelated worktree changes. Inspect the allowlist against both the diff and the staged name/status list.

## Copy without flattening paths

A multi-source `scp` command whose destination is a directory can place every basename at that directory rather than recreating each source subdirectory. Prefer one destination per file, an archive with an explicitly preserved relative root, or a path-preserving synchronization mode:

```text
scp <source>/app/services/example.py <host>:<project>/app/services/example.py
scp <source>/tests/test_example.py <host>:<project>/tests/test_example.py
```

After copying, compare fingerprints for every non-sensitive allowlist entry:

```text
sha256sum <source>/<relative-path>
ssh <host> sha256sum <project>/<relative-path>
```

Do not print, fingerprint, transfer, or stage secret-bearing files merely to make the manifest complete. A successful copy command without a destination-path check or fingerprint comparison is only a transport attempt.

## Validate before restart

In the deployment tree, run the focused regression, the complete suite, compile/syntax checks, and the migration/schema read-back. If a targeted patch reports success, immediately compile and inspect the surrounding function; patch tooling does not prove that a declaration or block was preserved.

For a database-backed bot, verify both the migration revision and the exact fields/indexes used by the new process. Do not restart code that reads a new column before the migration is confirmed.

## Restart and prove fresh code

Record the old process state, restart only after tests and commit, then record the new PID/start state. Verify service health, authenticated user-facing endpoints, schema-dependent API fields, and fresh startup/polling logs. Correlate log timestamps or PIDs so a normal old-process shutdown exception is not misreported as a new-process failure.

If any step is incomplete, label the release as pending and name the missing evidence. Never upgrade “copied” to “deployed” or “tested” to “live-verified” without the corresponding read-back.
