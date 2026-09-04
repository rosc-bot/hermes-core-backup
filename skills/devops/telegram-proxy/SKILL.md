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

### Long Link Truncation & Single-File Attachment Delivery
When sending long, continuous Base64 protocol URLs (such as 300+ character `vmess://` strings), chat platforms or LLM streaming filters may format/truncate them into `[...]`. To prevent delivery corruption, always write long proxy URLs into a discrete text file (`write_file`) and deliver it to the user via `MEDIA:/absolute/path/to/file.txt` alongside clean chunked/spaced fallback text.

### Multi-in-One Script Diagnosis
See `references/reality-and-socks5-performance-tuning.md` for Reality SNI anti-QoS domain selection, Linux BBR congestion control, TCP 15s keepalive tuning, and why popular 5-in-1 Sing-box scripts fail 4/5 protocols by default (Hysteria2/TUIC self-signed cert pin rejection vs VLESS-Reality).

### Standalone Proxy Apps vs. Android Transparent Root Modules
When users compare standalone VPN-mode clients (Clash Verge, v2rayN, Shadowrocket) with root transparent proxy modules (Surfing/Box for Magisk):
- Standalone clients use Android `VpnService` (system priority, battery optimization exemption, seamless Wi-Fi/cellular migration).
- Root modules use raw `iptables/TPROXY` packet hijacking (conntrack churn, local loopback latency inflation, tombstone/doze desync causing 'Connecting...' hangs).
- Recommend standalone VPN clients for high-stability daily social use unless strict anti-VPN detection bypass is required.

### Oracle Cloud (OCI) & Cloud Provider Firewall Dual-Layer Traps
See `references/reality-and-socks5-performance-tuning.md` for Reality SNI anti-QoS domain selection, Linux BBR congestion control, and TCP 15s keepalive tuning.
- **Dual Firewall Architecture**: Cloud VPS providers like Oracle Cloud (OCI) and AWS implement two independent firewall layers:
  1. **Platform Security Groups / Security Lists (External)**: Port 443 / SOCKS5 ports must be opened with Source `0.0.0.0/0`. Note that OCI Security List inputs DO NOT accept comma-separated lists (e.g. `22,443,80`); use single ports, contiguous ranges (e.g. `80-443`), or leave blank to permit all.
  2. **Guest OS iptables / ufw (Internal)**: Oracle Ubuntu images ship with default `iptables` drop rules that reload on boot. Always run:
     ```bash
     sudo iptables -P INPUT ACCEPT && sudo iptables -P FORWARD ACCEPT && sudo iptables -P OUTPUT ACCEPT && sudo iptables -F
     sudo apt-get install -y iptables-persistent && sudo netfilter-persistent save
     ```
- **SSH Keep-Alive**: NAT gateways and cloud routers silently terminate idle TCP SSH connections after 30-60s. Prevent dropouts by persisting `/etc/ssh/sshd_config.d/keepalive.conf` (`ClientAliveInterval 30`, `ClientAliveCountMax 10`).
- **SSH Key vs Public Key**: Public keys (`.pub`) are for server `authorized_keys` or cloud console instance creation. Clients connecting to servers must supply the private key (no `.pub`), and default cloud usernames (`ubuntu` for Ubuntu, `opc` for Oracle Linux, `admin`/`debian` for Debian, never `root` by default on Oracle Cloud).

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

### Cloudflare Worker Emby Proxy & Video Relay
See `references/cloudflare-worker-emby-proxy-troubleshooting.md` for Cloudflare Workers Emby proxy deployments (CF-EMBY-PROXY-UI), required API Token permissions (`Zone.Zone:Read`, `Zone.DNS:Edit`), SaaS Error 1034 bypass, and IPv6/transcoding fixes for mobile vs PC streaming.

### Open-Source Publishing & Privacy Sanitization
See `references/open-source-publishing-sanitization-guide.md` for zero-leak sanitization checklists, stripping private Emby/proxy endpoints and VPS IPs before pushing to public GitHub repositories, and clean git history force-overwrite techniques.

### Cloudflare Node Subscription Regional Optimization & Client Regex Tagging
See `references/cloudflare-subscription-regional-optimization.md` for ISP-directed Clean IP routing (China Telecom/Unicom/Mobile specific exit matching, IPv6 disabling), standard Flag Emoji + country naming syntax for Clash/Sing-box/Subconverter regex recognition, and automated API config injection.

### Distributed Emby Reverse Proxy Cluster (Master-Agent Architecture)
See `references/distributed-emby-proxy-cluster.md` for multi-server cluster orchestration (centralized UI master dispatching to remote node agents), 4K high-bitrate streaming pipeline buffer tuning (`proxy_buffers 16 1m; proxy_max_temp_file_size 0;`), and client ping probing route interception (`/emby/system/info/public`).

### Cloudflare Subscription Protocol Compatibility & Emby Reverse Proxy Bottlenecks
See `references/cloudflare-subscription-protocol-and-speed-diagnostics.md` for why Trojan fails 100% on Cloudflare Workers (`et: no` recommendation), ECH carrier reset traps in mainland China, XHTTP client kernel version thresholds, and the latency vs bandwidth trade-offs between HK (20ms/20Mbps cap) and NL (300ms/1Gbps pipe) when streaming 4K Emby.

### Lightweight Multi-Site Emby Reverse Proxy Panel on NAT VPS
See `references/nat-vps-lightweight-multi-emby-panel.md` for zero-overhead Python+Nginx multi-site Emby reverse proxy on resource-constrained NAT VPS (512MB RAM), sub-path multiplexing on a single external port, and automatic Nginx hot reload.

### Shlii NAT LXC Container & TW Server Diagnostics
See `references/shlii-nat-lxc-and-tw-server-guide.md` for Shlii NAT LXC container external SSH port mapping rules, and benchmark trade-offs between Taiwan (34ms/215Mbps 4K champion), Hong Kong (20ms/20Mbps bandwidth cap), and Netherlands (300ms/1Gbps pipe) nodes.

### Local Control Plane Zero-Bandwidth Architecture
When hosting the cluster master panel (`emby-multi-proxy`) on a central server (e.g. AWS EC2), control traffic (JSON sync payloads < 1KB) is decoupled from media data traffic (tens of gigabytes of 4K streams). Media players connect directly to edge nodes (TW/HK/NL), consuming **0 bytes** of the central master's transit bandwidth.

### Dynamic DNS Hot-Switching & Fixed Client Endpoint Architecture
See `references/dynamic-dns-hot-switch-architecture.md` for zero-relogin media proxy hot-switching: keeping client endpoints permanently fixed on a custom subdomain (`http://domain:port/path/`) while the AWS control panel dynamically updates Cloudflare DNS A records via API (60s TTL, `proxied: false`), switching between Taiwan (215M 4K), Hong Kong (20ms), and Netherlands nodes with zero client reconfiguration.

### Emby Dual-Route Concurrent Deployment, Buffer Sizing & Path Rewriting
See `references/emby-dual-route-tuning-and-pitfalls.md` for:
- Concurrent dual-route deployment (TW + NL) to avoid cross-node daisy-chain relay latency.
- Memory-matched buffer sizing: 4MB (`8 512k`) for 122MB Taiwan LXC vs 16MB (`16 1m`) for 512MB Netherlands VPS, and the Nginx `proxy_busy_buffers_size` calculation rule.
- Resolving ExoPlayer `"Unsupported format"` errors caused by duplicate subpath requests (`//emby/prefix/Videos/`) via Nginx regex rewrite.
- Origin-specific geo-blocking (TerminusC 403 on Asian IPs) and 302 media redirect handling.
- Non-blocking asynchronous SSH push to eliminate mobile browser `"Failed to fetch"` timeouts.

## Verification
After setup, the proxy link should work when:
1. Pasted into any Telegram client's proxy settings
2. The client shows "connected" status
3. `journalctl -u mtg --no-pager` shows non-zero connection counts

## Multi-Node Server Inventory & Deletion Cleanup Pitfalls
- **Accurate Geo-IP & Server Identification**:
  - Always verify node public IPs against authoritative Geo-IP lookup APIs (`ipinfo.io` / `ip-api.com`). Do not rely on loose historical chat nicknames which frequently conflate neighboring regions (e.g. confusing Oracle Tokyo NAT VPS `161.33.147.125` with Hong Kong VPS `156.245.245.172`).
  - When user requests deleting/decommissioning a VPS (e.g. "删除日本小鸡"):
    1. Clean up `~/.ssh/config` entries (`Host <name>`).
    2. Remove local deployment scripts and helper files (`deploy_<name>_proxy.sh`).
    3. Check client proxy configurations (`config*.yaml`, Surfing / Clash profiles) and strip dead proxy endpoints or upstream provider references.
    4. Verify port listening state and release mapped resources.
- **Port 443 Conflicts with Ghost/Isolated Nginx Instances**:
  - On servers running multi-service stacks (e.g. decommissioned proxy scripts, container managers, or provisioned web services like `uniproxy-nginx`), an isolated Nginx instance (`/usr/sbin/nginx -c /etc/uniproxy-nginx/nginx.conf`) may bind port `443` without appearing in standard `/etc/nginx` virtual hosts.
  - Symptom: Xray/SOCKS5 fails to bind port 443 with `listen tcp 0.0.0.0:443: bind: address already in use`, entering an infinite restart loop (exit status 255). External SOCKS5 probes return `curl: (97) Received invalid version in initial SOCKS5 response` because Nginx answers TLS/HTTP instead of SOCKS5.
  - Remedy: Locate conflicting processes with `ss -tlnp | grep 443` and `ps aux | grep nginx`. Stop and disable the ghost service (`systemctl stop uniproxy-nginx && systemctl disable uniproxy-nginx`), remove stale `@reboot` crontab entries, and restart Xray. Verify clean end-to-end SOCKS5 handshake (`curl --socks5 ... https://api.telegram.org/`).
- **Low-Memory NAT LXC Dual-Inbound (SOCKS5 + VLESS-Reality) on Port-Mapped VPS**:
  - On ultra-constrained NAT containers (e.g. 128MB RAM, shlii.io Incus LXC):
    1. Pre-existing reverse-proxy daemons (like Nginx on internal port `18096` mapped to external `29759`) cause port collisions (`curl: (97)`). Disable Nginx (`systemctl stop nginx && systemctl disable nginx`) before deploying Xray.
    2. When the hosting provider supports custom external port mapping (e.g. internal `36588` -> external `36709`), deploy independent inbounds within a single lightweight Xray daemon (<10MB RAM):
       - TG SOCKS5 on internal `18096` (mapped to external `29759` for Telegram click-to-connect `t.me/socks?server=...`).
       - VLESS-Reality on internal `36588` (mapped to external `36709` for Clash/Sing-box client proxy).
       - Both fully accessible over the shared public IPv4 with zero collision.
    3. Node naming convention: Client proxy links must embed standard Flag Emoji + Chinese country name (e.g. `#🇹🇼 台湾 | 原生直连`) for client subscription rule parsing.