---
name: production-change-synchronization
description: "Use when deploying tested changes; verify runtime."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [production, deployment, synchronization, verification, rollback, GitHub, security]
    related_skills: [github-auth, github-pr-workflow, systematic-debugging, test-driven-development]
---

# Production Change Synchronization

Use this class-level workflow when a code repair must be tested, committed,
deployed to a live service, and optionally synchronized to a private external
repository. The goal is a working, verified runtime—not a plausible patch or a
successful file copy.

The detailed checkpoint runbook, including the non-rewriting GitHub REST
fallback, is in `references/checkpoint-runbook.md`.

## Core invariants

- Confirm authorization and scope before every external side effect: code
  writes, migrations, commits, service restarts, API writes, and cloud actions.
- Keep a precise allowlist of intended files. Never use `git add .` in a dirty
  production worktree; leave unrelated historical files untouched.
- Never expose secrets, private URLs, cookies, database exports, or private keys
  in chat, process arguments, logs, commits, or API payloads.
- Verify state-changing operations by reading back the exact target. A successful
  command, HTTP 200, or copied file is not proof that the requested state is
  active.
- Do not perform real external transfers or mutate production business records
  merely to test a code path; use mocks and read-only probes unless the user
  explicitly authorizes the real action.

## Required sequence

### 1. Establish the baseline

Record the current production commit, service state/PID, listening ports,
health behavior, migration head/current, and relevant invariants without reading
secret values. Identify the production directory, isolated development copy,
rollback location, service unit, and the exact files in scope.

If local development has no repository metadata, perform Git status, staging,
commit, and history operations in the authoritative production worktree only
after comparing the source files. Do not accidentally create a second history
or overwrite unrelated worktree entries.

### 2. Use TDD for each non-trivial repair

Add a focused regression test that fails for the reproduced bug, run it against
the target test environment, implement the smallest fix, and rerun the focused
suite. Include adversarial values and concurrency cases where relevant. Keep
migrations, output escaping, authorization, and external-adapter behavior
covered by tests rather than relying on visual inspection.

### 3. Treat a completed repair batch as a deployment checkpoint

For this user's multi-step production repair workflow, group related fixes into
one bounded batch. Run focused tests during development, but do not synchronize
or restart production after every small patch merely because an intermediate
check is green. When the batch is complete—and before the session risks running
out of tool-call budget—perform one explicit synchronization, one commit, one
service restart when required, and one full runtime verification. Start another
independent batch only after that checkpoint. Restart earlier only for an actual
production incident or a dependency that genuinely requires it.

At the batch checkpoint:

1. synchronize only the explicitly intended files to production;
2. run compile/format/diff checks and inspect the staged file list;
3. commit only those files with a clear conventional message;
4. restart the authorized production service using the host's approved
   non-interactive privilege mechanism when required;
5. verify that the PID changed when a restart was requested, the service is
   active, the port is listening, the health endpoint responds as expected, and
   fresh logs show startup/polling without new application errors;
6. record the exact result before beginning the next independent repair batch.

If restart or verification fails, stop and diagnose the live state before making
more changes. Classify expected old-process shutdown cancellation separately
from startup/runtime failures, but never suppress unexplained new tracebacks.

### 4. Handle schema changes conservatively

Before a migration, read the current revision and inspect conflicts with a
read-only database probe. Apply the migration transactionally, then verify the
revision, nullable/index/constraint definitions, and business invariants. Do
not rewrite or clean historical business data unless separately authorized.
Keep a rollback backup before synchronization; do not claim rollback readiness
without a verifiable path.

### 5. Containerized migrations and service deployment conventions

When migrating legacy systemd services to Docker Compose or deploying new containerized applications:
- **Port allocation**: Never guess or arbitrarily pick exposed ports. In constrained host environments with strict firewall rules, always inspect active listeners and query the user to select from verified, idle, open ports.
- **Container naming restrictions**: Docker container names reject non-ASCII characters (`[a-zA-Z0-9_.-]` only). Use semantic project names (e.g., `container_name: <project>-service`) and express descriptive or localized metadata via container labels (`labels:`).
- **Inter-service container-to-host routing**: Services running inside Docker bridge networks that call host-level daemons (e.g. CPA LLM reverse proxy on port 8317) cannot connect to `127.0.0.1`. Route to the Docker bridge gateway (`http://172.17.0.1:<port>/v1`) or the external public IP.
- **Build cache hygiene**: Docker multi-stage builds and heavy native compilation (Cairo, Pango, Node Canvas, Python build dependencies) generate large build caches (`Build Cache` can quickly exceed 4-5 GB). Run `docker builder prune -a -f` after verification to prevent sudden host disk saturation.
- **Legacy service teardown**: When migrating a systemd service into Docker Compose, stop and disable the service, delete `/etc/systemd/system/<unit>`, execute `systemctl daemon-reload`, and remove old standalone script files to prevent duplicate background runners and data conflicts.

### 6. Synchronize a private repository without rewriting history

Before any repository write, authenticate only through an already authorized
safe source. Prefer a fine-grained token scoped to the exact repository with
`Contents: Read and write` and required metadata read access. If a credential is
already configured and the user has said to retain it, reuse it as a long-lived
operational dependency; do not delete it after synchronization or ask for a new
setup merely because a later batch is starting. Check presence and restrictive
permissions (normally mode `0600`) without reading or printing its value. Never
place it in chat, a URL, a project `.env`, plaintext Git credentials, command
arguments, or logs. Credential rotation or removal requires a separate explicit
user request.

Read the real remote refs, branch tip, commit, tree, merge base, ancestry,
remote-only files, and sensitive-path allowlist first. If local and remote
histories diverge, do not `push --force`. If normal Git HTTPS authentication
fails while the API token is valid, use the GitHub Git Database API: upload only
reviewed blobs, create a tree from the remote tree with explicit changes,
create a commit whose parent is the remote tip, and update the ref with
`force=false`. On conflict, stop instead of retrying forcibly.

After a repository write, read back the branch ref, commit, parent, tree, and
tree entries. Confirm the branch points to the intended result and no sensitive
path entered the tree. For the exact API endpoints and payload boundaries, use
the linked checkpoint runbook and the `github-auth` skill.

## Verification and reporting

Use real command/API output for every completion claim. Report separately:

- tests and static checks, including the exact counts;
- migration/schema/index verification;
- commit IDs and explicitly synchronized paths;
- restart PID, service/port/health/log status;
- external repository ref and read-back verification;
- actions intentionally not performed, such as real cloud transfers or
  business-data mutation;
- unresolved security cleanup or credential rotation that needs authorization.

Never turn a partial result into a success summary by implication. If the
configured credential is absent or expired, request secure setup or rotation;
do not remove a valid retained credential as routine cleanup.
