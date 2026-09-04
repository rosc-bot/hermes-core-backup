---
name: mihomo-clash-config-optimization
description: "Optimize Mihomo and Clash proxy configs and fix 403 errors."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, android, macos, windows]
metadata:
  hermes:
    tags: [Mihomo, Clash.Meta, SurfingTile, Proxy, DNS, KeepAlive, QUIC, Fake-IP]
    related_skills: [telegram-proxy, cliproxyapi]
---

# Mihomo / Clash.Meta Configuration & Optimization

When authoring, auditing, or troubleshooting proxy configurations for **Mihomo (Clash.Meta)** and module managers like **SurfingTile**, follow these validated performance directives and architectural principles.

## 1. Top 6 High-Impact Performance & Stability Directives

| Parameter / Directive | Optimal Configuration | Impact & Problem Solved |
| :--- | :--- | :--- |
| **Connection Keep-Alive** | `disable-keep-alive: false`<br>`keep-alive-interval: 60`<br>`keep-alive-idle: 60` | Prevents frequent TCP/TLS handshakes; drastically reduces latency when browsing social feeds (X/Twitter, Web). |
| **Load Balancing Session** | `strategy: sticky-sessions` | Replaces `round-robin` to fix login dropouts, account bans, and repetitive captcha challenges across web services. |
| **Smooth URL Testing** | `tolerance: 50` (or `200` for high stability)<br>`lazy: true`<br>`max-failed-times: 3` | `tolerance` sets the minimum latency delta (ms) required to trigger automatic switching. `200` is very conservative (e.g. 172ms won't switch to 71ms); `50` is the recommended sweet spot for responsiveness without excessive flapping. **DO NOT place these inside `health-check:`**; place them directly inside `type: url-test` or `fallback` groups. |
| **QUIC GSO Guard** | `quic-go-disable-gso: true` | Prevents driver-level packet dropping and thermal throttling on Android/Linux kernels during YouTube 4K / QUIC streaming. |
| **DNS Cache Algorithm** | `cache-algorithm: arc` | Uses Adaptive Replacement Cache to achieve ~0ms response times for frequently visited domain lookups. |
| **DoH Bootstrap Pre-Resolution** | Explicit IP mapping in `hosts:` | Maps `dns.alidns.com`, `doh.pub`, `dns.google` to direct IPs, resolving recursive DNS deadlocks on cold starts. |

## 2. Redir-Host vs Fake-IP Selection & Troubleshooting

### Why Android Root Modules Must Avoid Fake-IP
In Android Magisk/KernelSU root module environments (SurfingTile, Box for Magisk), **Fake-IP breaks system App bypass features**. 
- Fake-IP injects `198.18.x.x` addresses directly into the kernel's iptables and UID routing tables.
- Thus, application-level blacklists/whitelists (`exclude-package` / `include-package`) break or route incorrectly, causing banking, government, or domestic apps to fail.
- **Verdict for Root Modules**: Stick to `enhanced-mode: redir-host` alongside `sniffer: true`. 

### Advanced `redir-host` Mitigations for 403 Forbidden & App Loading
When running `redir-host`, Cloudflare and AI endpoints often block requests because the CDN receives SNI requests originating from node IPs, yet carrying locally-resolved domestic DNS records. 
Fix this by enforcing target-domain re-resolution at the proxy node:
```yaml
sniffer:
  enable: true
  force-dns-mapping: true
  parse-pure-ip: true
  override-destination: true
  force-domain:
    - "+.cloudflare.com"
    - "+.openai.com"
    - "+.emby.wtf" # Include user's Emby or media proxy domains
    - "+.xying1314.xyz"
    - "+.aixj.de"
    - "+.dremby.com"
    - "+.lightting.net"
    - "+.bbqwq.com"
```

### Critical DNS Syntax Rules
1. **Never omit `default-nameserver`**: Even with `hosts` hardcoded, Mihomo will deadlock and fail to initialize outbound network queries if the base pure-IP `default-nameserver` list is missing. 
2. **Never use comma-separated `RULE-SET` in `nameserver-policy`**: A syntax like `"RULE-SET:CN_域,Microsoft_域"` is illegal in Mihomo. It looks for a literal single ruleset named exactly that and fails. Each ruleset MUST be declared on its own distinct line:
   ```yaml
   "RULE-SET:CN_域":
     - https://223.5.5.5/dns-query
   "RULE-SET:Microsoft_域":
     - https://223.5.5.5/dns-query
   ```
3. **Respect Rules**: Add `respect-rules: true` under `dns:`. This enforces routing evaluation *before* DNS resolution, preventing massive local DNS leakage for proxy-bound domains.

## 3. Robust Regex Patterns for Node Filtering

Avoid single-character ambiguities (e.g. matching `US` inside `PLUS` or `TRUST`). Use emoji flags, case-insensitivity `(?i)`, and word-boundary assertions `(?<![A-Za-z])XX(?![A-Za-z])`:

```yaml
# Hong Kong (香港)
filter: "(?i)(港|🇭🇰|(?<![A-Za-z])HK(?![A-Za-z])|HKG|hkg|hong ?kong)"

# Taiwan (台湾)
filter: "(?i)(台|🇹🇼|新北|彰化|(?<![A-Za-z])TW(?![A-Za-z])|taiwan|taipei|TPE|tpe)"

# Japan (日本)
filter: "(?i)(日|🇯🇵|川日|东京|NRT|nrt|大阪|泉日|埼玉|沪日|深日|[^-]日|(?<![A-Za-z])JP(?![A-Za-z])|japan|JPN)"

# Singapore (狮城/新加坡)
filter: "(?i)(新加坡|坡|狮城|🇸🇬|(?<![A-Za-z])SG(?![A-Za-z])|SIN|sin|singapore|SGP)"

# United States (美国)
filter: "(?i)(美|🇺🇸|(?<![A-Za-z])US(?![A-Za-z])|USA|LAX|lax|SJC|sjc|波特兰|达拉斯|俄勒冈|凤凰城|费利蒙|硅谷|拉斯维加斯|洛杉矶|圣何塞|圣克拉拉|西雅图|芝加哥|united ?states)"

# Netherlands (荷兰)
filter: "(?i)(荷兰|🇳🇱|Netherlands|Nederland|(?<![A-Za-z])NL(?![A-Za-z])|Amsterdam|阿姆斯特丹|AMS|ams)"
```

## 4. Pitfalls & User Preferences
- **URL-Test Node Switching Sensitivity (`tolerance` Trap):** When a user asks why an automatic `url-test` group remains on a higher-latency node (e.g., 172ms) despite faster nodes (e.g., 71ms) being available:
  - Check `tolerance:` in the group config. Clash/Mihomo requires the difference between the new node and current node to exceed `tolerance` before switching. If `tolerance: 200` is set, a 101ms improvement (172ms vs 71ms) will NOT trigger a switch.
  - Recommended fix: Lower `tolerance` to `50` (or `20`-`30` for ultra-sensitivity) and verify `store-selected` / `lazy` interaction.
- **User-Agent in Proxy-Providers:** When declaring custom User-Agent in proxy-providers header (`p: &p`), Mihomo strictly requires Go `http.Header` slice format (`map[string][]string`). It MUST be a YAML list (e.g. `User-Agent: ["Mihomo"]` or multi-line `- "Mihomo"`), never a bare scalar string `User-Agent: "Mihomo"`, otherwise it crashes with `'header[User-Agent]' is not a slice` (see `references/yaml-syntax-and-anchor-pitfalls.md`).
- **CRITICAL WORKFLOW RULE: Never Speculatively Apply Changes Without Prior Confirmation:** When reviewing, diagnosing, or suggesting optimizations for proxy configs, NEVER unilaterally generate a modified file and tell the user it is done. Always enumerate the proposed modification points, explain the technical reasons/trade-offs (e.g., Fake-IP vs. redir-host, logging levels, specific policy group changes like Emby node allowances), ask for the user's explicit preference, and only apply the confirmed changes upon receiving explicit approval.
- **DO NOT SPECULATIVELY INJECT DOMAINS:** Never automatically extract domains from past chat history (e.g., from `tg_messages.db`) or external sources and blindly add them to the user's config (like `force-domain` or `rules`). Only add domains the user *explicitly* requests.
- **ConnectionException / No address associated with hostname in redir-host:** See `references/redir-host-dns-failures.md`. When using `redir-host` and an app reports `[ConnectionException] error:failed to lookup address information: No address associated with hostname` (specifically from proxy-reliant media apps like Emby clients or TeleDrive), it indicates local DNS resolution failed outright. Fix this by ensuring the domain isn't slipping through `nameserver-policy` gaps, adding `default-nameserver` and `fallback` DNS layers, or checking if the domain itself is dead. Do not confuse this with a Cloudflare 403 (which happens *after* DNS resolution when SNI routing fails).
- **Runtime Error Classification (`failed to dial WebSocket: 403 Forbidden`):** See `references/runtime-proxy-diagnostics.md`. Distinguish between startup pre-validation fatal errors (`[Error]` in `check.log`) vs runtime node warnings (`[WARN]` in `run.log`). A `failed to dial WebSocket: unexpected status: 403 Forbidden` indicates Mihomo is healthy and running, but a specific remote proxy node (typically VLESS/VMess+WS over CDN) was blocked or died. Automatic failover (`url-test`) will isolate it; never confuse this with configuration syntax errors.
- **Telegram Media Infinite Spin & Background 'Connecting...' Loops:** See `references/telegram-transparent-proxy-troubleshooting.md`. Never route Telegram through `load-balance` (breaks multi-stream media downloads) or `url-test` containing Cloudflare (CF) VLESS nodes (100s idle WebSocket timeout and Google 204 false-positives). FCM notifications succeed via Google while Telegram hangs on dead DC IPs. Bind Telegram to a dedicated, static non-CF node and disable 'Prefer IPv6' in TG settings.
- **SurfingTile Custom Anchor Stripping vs. Inline Definitions:** See `references/yaml-syntax-and-anchor-pitfalls.md`. When users add subscriptions or modify settings via the SurfingTile App UI, the app generator strips any custom, non-standard YAML anchors (like `&TG_Use`) while leaving references (`<<: *TG_Use`) intact, causing `yaml: unknown anchor referenced`. Never invent custom anchors for SurfingTile configs; use **inline** `use:` and `filter:` blocks directly inside strategy groups. Also remember that newly imported providers in `proxy-providers` must have their name explicitly added to the group's `use:` list to appear in proxy groups.
- **Subscription Server `EOF` & HEAD Probing:** See `references/subscription-server-and-eof-troubleshooting.md`. When mobile clients (Surfing, Mihomo) fail to fetch a self-hosted subscription URL with `Get "...": EOF`, it is caused by the HTTP server failing to handle `HEAD` requests, omitting `Content-Length`, or lacking `Connection: close`. Also ensure long VMess base64 strings delivered over chat are not truncated.
- **Standalone Proxy Client vs. Transparent Root Module (Surfing/Box):** When a user notices that standalone proxy apps (Clash Verge, v2rayN, Shadowrocket) yield lower latency and higher stability than Magisk/KernelSU transparent modules (Surfing/Box for Magisk):
  - **Virtual Network Layer**: Standalone apps run over Android's native `VpnService`, enjoying system priority, smooth cellular/Wi-Fi handover, and exemption from aggressive OS battery doze/freezing. Root modules use raw Linux `iptables / TPROXY` packet hijacking, incurring heavy conntrack table churn and instant dead connections upon cell tower shifts.
  - **Loopback Latency Overhead**: Transparent proxies loop traffic through local DNS redirect sockets before hitting the core, adding 30ms-80ms artificial round-trip overhead in synthetic latency tests.
  - **Doze / Tombstone Desync**: Android freezes the client app (Telegram, browser) but the root background core keeps TCP open. Upon foreground wake, the app attempts to reuse stale sockets and hangs in "Connecting...".
  - **Remedy**: For daily social browsing and high reliability, standalone VPN-mode proxy apps outperform transparent root modules unless hard anti-VPN detection bypass is required.
- **Emby / Media Group Policy Restrictions:** In media proxy groups (like Emby / Jellyfin / CapyPlayer), be mindful of licensing, copyright geofencing, and server firewall bans. Many Emby servers strictly ban or geoblock Hong Kong (HK) and Japan (JP) node IPs. Always verify and respect explicit restrictions (e.g. excluding HK and JP from Emby groups) rather than assuming all low-latency regions should be included.
- **Emby Reverse Proxy & High-Bitrate Streaming Tuning:** On reverse proxy nodes (e.g., Linux/NAT VPS running Nginx), high-bitrate media (4K/HEVC) over transcontinental routes suffers severe TCP degradation. Optimize with:
  1. Pipeline buffers for video streams: `proxy_buffering on; proxy_buffer_size 512k; proxy_buffers 16 1m; proxy_max_temp_file_size 0;`.
  2. Edge static caching: 200MB-300MB cache zone (`proxy_cache`) for poster/backdrop images and Web UI assets.
  3. Client heartbeat pass-through: explicitly route `/emby/system/info/public` and stub `/System/Ext/ServerDomains` to prevent client connection drops and ping timeout errors.
- **DNS Acceleration & Advanced SNI Anti-403 Tuning:**
  - **Direct DNS Bootstrap**: Avoid relying on LAN routers (`192.168.1.1`) inside `direct-nameserver`; align with pure high-speed Anycast IPs (`223.5.5.5`, `119.29.29.29`, `1.12.12.12`, `223.6.6.6`).
  - **Pre-Resolve Upstream DoH**: Explicitly hardcode DoH hostnames (`dns.alidns.com`, `doh.pub`, `cloudflare-dns.com`, `dns.google`, `dns.quad9.net`) in `hosts:` to break cold-boot bootstrap loops.
  - **Modern AI & Rich Media Force-Domain**: In `sniffer.force-domain`, always include modern AI endpoints (`+.anthropic.com`, `+.claude.ai`, `+.generativeai.google`, `+.ai.google.dev`, `+.cloudflare.com`) to enforce node-level SNI re-resolution, preventing Cloudflare 403 blocks and Captcha loops.
- **Windows 系统与网络驱动排障 (Windows Update & Intel Wi-Fi BSOD)**: 见 `references/windows-update-policy-and-wifi-bsod.md`，记录 Windows 自动更新策略被管理员/注册表锁定 (`AUOptions: 3`) 的命令行解封与 PowerShell 语法注意事项，以及 Intel 无线网卡驱动 `Netwbw02.sys` 引发 `KMODE_EXCEPTION_NOT_HANDLED (0x1E)` 蓝屏死机的定位与处置。
- **Top 4 Core Mihomo Syntax & Routing Rules (Surfing/Meta):**
  1. **Dashboard Security**: If `external-controller` binds to `0.0.0.0:9090`, a strong password MUST be defined under `secret:` to prevent unauthorized remote scans or routing hijacking.
  2. **QUIC GSO Nesting**: `quic-go-disable-gso: true` must NOT be placed at root level in modern Mihomo configs; it must be nested under `experimental:` (`experimental:\n  quic-go-disable-gso: true`).
  3. **MPTCP Removal**: Strip `mptcp: true` unless kernel/network stack explicitly supports it, as it frequently causes handshake failures, RST resets, and parse errors on mobile/root modules.
  4. **CN_IP `no-resolve`**: Always append `,no-resolve` to `RULE-SET,CN_IP,🌐 本机·本地直连,no-resolve`. Without it, domain queries falling through to this IP rule will force unnecessary local DNS resolution, causing domestic DNS leakage and latency lag.
  5. **No Anchor Inheritance on Groups (`*proxy_groups`)**: Avoid YAML anchor references (`<<: *proxy_groups`) in SurfingTile/mobile module configs, as UI generators frequently strip anchor definitions while leaving references, causing `yaml: unknown anchor referenced`. Use inline declarations or `use:` lists directly.
- **VPS Node Multi-Proxy Traffic Burn Pitfall (Emby & Public UDP):**
  - **Emby 4K Relay Doubled Traffic**: High-bitrate 4K streaming relays through a VPS consume double bandwidth (ingress from source + egress to client). A single 40GB movie consumes ~80GB quota. Small-quota (500GB-1TB) VPS nodes (e.g. NL/EU nodes) will burn out in 2-3 days under active streaming. Keep high-bitrate media off capped VPS nodes.
  - **Public UDP Abuse**: Binding open UDP proxies without source whitelists or authentication exposes the node to UDP DNS/NTP reflection attacks, burning gigabytes per hour unnoticed. Strip unnecessary `udp: true` on public proxy inbounds.
  - **Traffic-Limited Host Auto-Shutdown (LXC/shlii.io)**: When container VPS instances show `已停止` and immediately shut down seconds after starting, check the host logs for `Queued automatic stop task for traffic-limited instance`. Host daemons enforce instant container termination upon bandwidth quota exhaustion. Check disk space (`df -h` on 1GB disks vs Debian 13 bloat) and monthly bandwidth reset dates.
