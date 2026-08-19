---
name: telegram-proxy
description: Set up Telegram MTProto proxy on Linux servers.
version: 1.1.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [telegram, proxy, mtproto, devops, remote-server, systemd]
    related_skills: [ssh-server-access]
---

# Telegram MTProto Proxy Setup

Set up a click-to-connect Telegram proxy (MTProto) on a remote Linux server. The proxy generates a `tg://proxy?...` link that users tap to connect instantly.

## When to Use
- User says "搭个TG代理" / "搭建MTProto" / "setup telegram proxy" / "装个梯子"
- Need to proxy Telegram traffic through a specific server (e.g. Hong Kong, Netherlands)
- User wants a click-to-connect proxy link for Telegram

## Prerequisites
- SSH access to the target server (use `ssh-server-access` skill if keyless login isn't set up)
- Root or sudo access on the server
- Debian/Ubuntu recommended (commands are apt-based)

## Overview

Two main MTProto proxy implementations:

| Software | Language | Performance | Obfuscation | Recommendation |
|----------|----------|-------------|-------------|----------------|
| **mtg** | Go | ★★★★★ | ★★★★★ (domain fronting + doppelganger) | ⭐ **Recommended** |
| **mtprotoproxy** | Python | ★★★ | ★★★★ | Fallback |

**mtg** is preferred: resource-efficient, better anti-censorship, handles 10k+ concurrent connections. Only use `mtprotoproxy` if Go binaries aren't feasible.

---

## Option A: mtg (Recommended)

### 1. Install mtg binary
```bash
LATEST_URL=$(curl -sL https://api.github.com/repos/9seconds/mtg/releases/latest |
  python3 -c "import json,sys; d=json.load(sys.stdin)
for a in d['assets']:
  if 'linux' in a['name'] and 'amd64' in a['name'] and a['name'].endswith('.tar.gz'):
    print(a['browser_download_url'])")
wget -q "$LATEST_URL" -O /tmp/mtg.tar.gz
tar xzf /tmp/mtg.tar.gz -C /tmp
cp /tmp/mtg-*/mtg /usr/local/bin/mtg
chmod +x /usr/local/bin/mtg
```

### 2. Generate secret with TLS domain
```bash
SECRET=$(mtg generate-secret cloudflare.com)
echo "Secret: $SECRET"
```

### 3. Create config file
```bash
mkdir -p /etc/mtg
cat > /etc/mtg/config.toml << EOF
debug = false
secret = "${SECRET}"
bind-to = "0.0.0.0:443"
concurrency = 8192
auto-update = false
prefer-ip = "prefer-ipv4"
tolerate-time-skewness = "30s"

[network.timeout]
tcp = "5s"
idle = "5m"
handshake = "10s"

[defense.anti-replay]
enabled = true
max-size = "1mib"
error-rate = 0.001

[defense.blocklist]
enabled = false

[stats.prometheus]
enabled = false
EOF
```

**⚠️ CRITICAL: Config format** — `secret` and `bind-to` go at the **root level** of the TOML, NOT under a `[mtg]` section. mtg silently fails with "secret is empty" when nested.

### 4. Test the config
```bash
mtg doctor /etc/mtg/config.toml
```

### 5. Create systemd service
```bash
cat > /etc/systemd/system/mtg.service << 'SERVICE'
[Unit]
Description=MTProto Proxy (mtg)
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mtg run /etc/mtg/config.toml
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable --now mtg
```

### 6. Verify and get link
```bash
systemctl status mtg --no-pager
ss -tlnp | grep 443
mtg access /etc/mtg/config.toml | python3 -c "import json,sys; print(json.load(sys.stdin)['ipv4']['tg_url'])"
```

---

## Option B: mtprotoproxy (Python, Fallback)

### 1. Install and configure
```bash
ssh root@<SERVER_IP> "apt-get update -qq && apt-get install -y -qq python3-pip python3-venv curl git openssl"
ssh root@<SERVER_IP> "cd /opt && git clone https://github.com/alexbers/mtprotoproxy.git"
ssh root@<SERVER_IP> "cd /opt/mtprotoproxy && python3 -m venv venv && source venv/bin/activate && pip install cryptography"
```

### 2. Generate secret and configure
```bash
ssh root@<SERVER_IP> "SECRET=\$(openssl rand -hex 16); cat > /opt/mtprotoproxy/config.py << PYEOF
PORT = 443
USERS = { \"tg\": \"\${SECRET}\" }
MODES = { \"classic\": False, \"secure\": False, \"tls\": True }
TLS_DOMAIN = \"www.amazon.com\"
PYEOF"
```

### 3. Create systemd service and start
```bash
ssh root@<SERVER_IP> "cat > /etc/systemd/system/mtprotoproxy.service << 'PYEOF'
[Unit]
Description=MTProto Proxy for Telegram
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/mtprotoproxy
ExecStart=/opt/mtprotoproxy/venv/bin/python3 /opt/mtprotoproxy/mtprotoproxy.py
Restart=always
RestartSec=3
User=root
[Install]
WantedBy=multi-user.target
PYEOF
systemctl daemon-reload && systemctl enable mtprotoproxy && systemctl start mtprotoproxy"
journalctl -u mtprotoproxy --no-pager | grep 'tg://'
```

---

## The Proxy Link Format

**mtg** generates links in base64 format (default) or hex (`--hex`):
```
tg://proxy?server=<IP>&port=443&secret=ee<32-hex-secret><domain-in-hex>
```

- `ee` prefix = TLS mode
- Trailing hex encodes the TLS domain (e.g., `636c6f7564666c6172652e636f6d` = `cloudflare.com`)

---

## Troubleshooting: "Proxy not available" / "Still not working"

### 1. Verify basics
```bash
systemctl status mtg --no-pager
ss -tlnp | grep 443
systemctl status nginx 2>/dev/null  # check for port conflicts
```

### 2. Check firewall
```bash
ufw status 2>/dev/null || iptables -L -n | grep 443
```

### 3. Test TLS handshake from outside
```bash
echo | openssl s_client -connect <IP>:443 -servername cloudflare.com 2>&1 | head -5
```

### 4. Verify server can reach Telegram DCs
```bash
python3 -c "
import socket
for dc in ['149.154.175.50','149.154.167.51','149.154.175.100','149.154.167.91']:
    s=socket.socket(); s.settimeout(3)
    try: s.connect((dc,443)); print(f'OK DC {dc}')
    except Exception as e: print(f'FAIL DC {dc}: {e}')
    finally: s.close()
"
```

### 5. Check logs for connections
```bash
journalctl -u mtg --no-pager | grep -i "connect\|error\|fail"
```

### 6. Common causes
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 connects, TLS works | GFW blocking IP | Try different port, change TLS domain |
| HTTP 400 after TLS | Wrong secret format | Re-generate with `mtg generate-secret` |
| "secret is empty" in mtg | Config nested under `[mtg]` section | Move to root level |
| Service fails to start | TLS domain unreachable | Pick a different stable domain |

### 7. If still blocked (likely GFW)
- Try a different port (8443, 4443, 993)
- Change the TLS_DOMAIN to a different popular site
- Restart the proxy service to clear stale state

---

## Pitfalls

### mtg: Config format is strict
`secret` and `bind-to` at root level, not under `[mtg]`. Validate with `mtg doctor /etc/mtg/config.toml`.

### mtg: Secret format
- Config file: use **base64** format (default output of `mtg generate-secret`)
- Proxy link: both base64 and hex work; hex is more portable
- `--hex` flag outputs hex format

### Port 443 requires root
Both proxies bind to privileged port 443. Systemd service must run as root.

### Firewall may block port 443
```bash
ufw allow 443/tcp 2>/dev/null || iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### TLS domain must be reachable
Proxy fetches certificate from the domain on startup. Use well-known, stable CDN domains.

### Switching implementations
Stop old service before starting new one to avoid port conflicts.

## Verification
After setup, the proxy link should work when:
1. Pasted into any Telegram client's proxy settings
2. The client shows "connected" status
3. `journalctl -u mtg --no-pager` shows non-zero connection counts