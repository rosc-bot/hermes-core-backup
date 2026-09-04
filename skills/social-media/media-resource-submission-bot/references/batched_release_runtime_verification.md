# Batched Release and Runtime Verification

Use this reference when a related batch of changes has already been tested and must be released to a Telegram-polling bot that also hosts a FastAPI WebUI under systemd.

## Release boundary

Treat these as three separate claims and verify each one independently:

1. **Local/target source**: intended files, migrations, tests, and commit are present.
2. **Remote repository**: the exact intended tree and commit were read back from the private remote; a successful API or SSH exit code alone is not proof.
3. **Live process**: the systemd service started a new process from the intended production worktree and both polling and WebUI recovered.

Accumulate related fixes into one green batch. The normal order is:

1. Add regression tests first and run focused tests.
2. Run the full suite, compilation, and `git diff --check`.
3. Explicitly stage only intended files; never use `git add .` in a dirty production worktree.
4. Commit once and verify the exact commit/tree.
5. Synchronize the private repository once through the configured safe API path and read back the branch, commit, tree, and parent.
6. Restart the service once, then perform the runtime gate below.

Do not restart after every small follow-up edit. A user-facing emergency exception must be explicit and still requires the same target-side verification.

## Runtime restart gate

Before the restart, record the current `MainPID` and `ActiveEnterTimestamp`. Use the service-scoped command with non-interactive privilege on the target host:

```bash
sudo -n systemctl restart tg-media-bot.service
```

Afterward, require all of the following:

```bash
systemctl is-active tg-media-bot.service
systemctl show -p MainPID -p ActiveEnterTimestamp -p ExecMainStartTimestamp -p Result tg-media-bot.service
ps -o pid=,lstart=,cmd= -p <new_pid>
ss -ltnH '( sport = :12082 )'
```

`active/running` by itself is insufficient: systemd can report an old healthy process after a restart command failed or never ran. The new PID and start timestamp must differ from the pre-restart values. Also confirm the process command and working directory point at the intended production application.

For a service combining aiogram polling and Uvicorn/FastAPI, inspect only the journal interval beginning at the new start time and verify:

- FastAPI/Uvicorn startup completed;
- Telegram command registration completed;
- polling/getUpdates started and continued;
- no non-cancellation startup, import, schema, or polling traceback exists.

A single `401` from an unauthenticated `/health` or `/` request is expected when WebUI Basic Auth is enabled. Pair it with the listener check and, when credentials are already safely available, an authenticated probe; never print or read secret values merely to make the probe.

## Traceback classification

A combined runner may emit `asyncio.exceptions.CancelledError` while the previous process is being gracefully stopped. Do not call that a deployment failure when the new PID is healthy and its startup/polling markers are present. Parse traceback blocks rather than counting the word `Traceback`: classify blocks containing `CancelledError` separately, and require the count of other traceback blocks to be zero.

If the PID did not change, the timestamp did not advance, or the new-process log gate is incomplete, report the rollout as **unverified** and have the operator run the service-scoped command directly on the target host. Do not substitute a machine reboot, alter systemd policy, or claim the new code is live.

## Safety boundaries

- Do not read or print `.env`, API tokens, cookies, private keys, database exports, or sensitive database rows.
- Do not perform a real cloud transfer as part of a code rollout; use mocks or read-only probes.
- Do not treat a restart command's textual success, an unchanged `active` state, or a successful `restore`/HTTP response as proof of the intended live effect.
