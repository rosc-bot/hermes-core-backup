---
name: ssh-server-access
description: Use when SSHing into a remote server given IP+password.
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [ssh, devops, remote-server, sshpass, keyless-login]
    related_skills: [github-auth]
---

# SSH Server Access

Connect to a remote Linux server given IP (+ password, maybe username), gather system info, and enable passwordless key login.

## When to Use
- User drops an IP (+ password, maybe username) and says "链接ssh" / "connect to server" / "连一下这台服务器"
- Need to administer a remote box: recon, install, config, monitoring, deploy

## Steps

1. **Check tooling**: `which sshpass || sudo apt-get install -y sshpass` (Ubuntu/Debian).
2. **Port check before connecting** (fast fail, no noise):
   `timeout 5 bash -c 'echo > /dev/tcp/<IP>/22' && echo open || echo closed`
3. **Password login** — suppress host-key prompt and force password auth so sshpass works:
   ```
   sshpass -p '<PASS>' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
     -o PreferredAuthentications=password -o PubkeyAuthentication=no root@<IP> '<cmd>'
   ```
   Username defaults to root; try `ubuntu` / `admin` / `ec2-user` if refused.
4. **Recon in one shot**: `cat /etc/os-release` (name+version), `nproc` + cpu model, `free -h`, `df -h /`, `curl -s ifconfig.me` (public IP), `timedatectl` (timezone), `uptime`. Report concisely in the user's language.
5. **Passwordless key setup**:
   - Generate if none: `ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -q`
   - Push idempotently (mkdir 700, file 600):
     ```
     PUB=$(cat ~/.ssh/id_ed25519.pub)
     sshpass -p '<PASS>' ssh -o StrictHostKeyChecking=no root@<IP> \
       "mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
        grep -qF '$PUB' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUB' >> ~/.ssh/authorized_keys; \
        chmod 600 ~/.ssh/authorized_keys"
     ```
6. **Verify key login WITHOUT sshpass**:
   `ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 root@<IP> 'echo ok'`

## Pitfall: SSH may listen on a non-standard port

`/dev/tcp/<IP>/22` can show **open** and even answer with an SSH banner while the actual target daemon listens on a custom port (e.g. 20022). Port 22 can be a *different* host/daemon entirely — observed: banner on 22 claimed Ubuntu, the real box on 20022 was Debian 13. The provided credentials will fail on 22 with a clean `Permission denied, please try again` for every common username (root/ubuntu/admin/ec2-user...).

Symptom → action: when port-22 auth is denied, do NOT cycle through more usernames first. Ask the user for the correct port (or check provider defaults), then redo the whole flow with `-p <port>`:

```
sshpass -p '<PASS>' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no -p 20022 root@<IP> '<cmd>'
```

Key-push and keyless-verify steps also need `-p <port>` (`scripts/ssh-keyless-setup.sh` takes the port as its 3rd argument). Save port + user + hostname to memory so later sessions connect directly.

## Pitfall: key auth fails right after installing the key

Symptom: `Permission denied (publickey)` — authorized_keys content/permissions look correct on the server. Cause is often the VPS image disabling public-key auth entirely.

Diagnose (check BOTH main config and drop-in dir — Debian/Ubuntu put overrides in `/etc/ssh/sshd_config.d/`):
```
grep -E "^(PubkeyAuthentication|PasswordAuthentication|PermitRootLogin)" \
  /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf
```
If `PubkeyAuthentication no`: flip it in whichever file declares it, then restart:
```
sed -i 's/^PubkeyAuthentication no/PubkeyAuthentication yes/' /etc/ssh/sshd_config   # or the drop-in file
systemctl restart ssh || systemctl restart sshd || service ssh restart
```
Then retest. **`BatchMode=yes` in the test is essential** — without it ssh falls back to an interactive password prompt and masks the key result with a confusing hang/denial. Service name differs by distro: `ssh` (Debian/Ubuntu) vs `sshd` (RHEL); try both.

## Known servers
Session-known servers (IP, user, password, hostname) are stored in agent memory. Check memory before asking the user to repeat credentials.

## Automate
`scripts/ssh-keyless-setup.sh <user@host> <password> [port]` — full end-to-end: install sshpass, generate+push key, enable PubkeyAuthentication if disabled, verify key login.