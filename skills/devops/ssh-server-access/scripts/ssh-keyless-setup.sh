#!/usr/bin/env bash
# ssh-keyless-setup.sh <user@host> <password> [port]
# End-to-end passwordless SSH setup: install sshpass, generate+push ed25519 key,
# enable PubkeyAuthentication if the server disabled it, verify key login.
# Mirrors the workflow in SKILL.md (ssh-server-access).
set -euo pipefail

TARGET="${1:?Usage: $0 <user@host> <password> [port]}"
PASS="${2:?Usage: $0 <user@host> <password> [port]}"
PORT="${3:-22}"

# 1. Tooling
command -v sshpass >/dev/null || sudo apt-get install -y sshpass

# 2. Local key
[ -f "$HOME/.ssh/id_ed25519.pub" ] || ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -q
PUB="$(cat "$HOME/.ssh/id_ed25519.pub")"

SSHPASS_OPTS=(-p "$PASS" ssh -p "$PORT" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
  -o PreferredAuthentications=password -o PubkeyAuthentication=no)

# 3. Push pubkey (idempotent; dir 700, file 600)
sshpass "${SSHPASS_OPTS[@]}" "$TARGET" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
  (grep -qF '$PUB' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUB' >> ~/.ssh/authorized_keys) && \
  chmod 600 ~/.ssh/authorized_keys" >/dev/null

# 4. Enable PubkeyAuthentication if disabled (main config + drop-ins), restart ssh
sshpass "${SSHPASS_OPTS[@]}" "$TARGET" '
  FILES=$(grep -l "^PubkeyAuthentication no" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true)
  if [ -n "$FILES" ]; then echo "$FILES" | xargs sed -i "s/^PubkeyAuthentication no/PubkeyAuthentication yes/"; echo "enabled PubkeyAuthentication"; fi
  systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || service ssh restart 2>/dev/null || true
  echo sshd-ok' >/dev/null

# 5. Verify key login (BatchMode: fail fast, never prompt for password)
ssh -p "$PORT" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 "$TARGET" \
  'echo "KEY LOGIN OK: $(whoami)@$(hostname)"'