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
- **DO NOT SPECULATIVELY INJECT DOMAINS:** Never automatically extract domains from past chat history (e.g., from `tg_messages.db`) or external sources and blindly add them to the user's config (like `force-domain` or `rules`). Only add domains the user *explicitly* requests.
- **ConnectionException / No address associated with hostname in redir-host:** See `references/redir-host-dns-failures.md`. When using `redir-host` and an app reports `[ConnectionException] error:failed to lookup address information: No address associated with hostname` (specifically from proxy-reliant media apps like Emby clients or TeleDrive), it indicates local DNS resolution failed outright. Fix this by ensuring the domain isn't slipping through `nameserver-policy` gaps, adding `default-nameserver` and `fallback` DNS layers, or checking if the domain itself is dead. Do not confuse this with a Cloudflare 403 (which happens *after* DNS resolution when SNI routing fails).
- **Runtime Error Classification (`failed to dial WebSocket: 403 Forbidden`):** See `references/runtime-proxy-diagnostics.md`. Distinguish between startup pre-validation fatal errors (`[Error]` in `check.log`) vs runtime node warnings (`[WARN]` in `run.log`). A `failed to dial WebSocket: unexpected status: 403 Forbidden` indicates Mihomo is healthy and running, but a specific remote proxy node (typically VLESS/VMess+WS over CDN) was blocked or died. Automatic failover (`url-test`) will isolate it; never confuse this with configuration syntax errors.
- **Telegram Media Infinite Spin & Background 'Connecting...' Loops:** See `references/telegram-transparent-proxy-troubleshooting.md`. Never route Telegram through `load-balance` (breaks multi-stream media downloads) or `url-test` containing Cloudflare (CF) VLESS nodes (100s idle WebSocket timeout and Google 204 false-positives). FCM notifications succeed via Google while Telegram hangs on dead DC IPs. Bind Telegram to a dedicated, static non-CF node and disable 'Prefer IPv6' in TG settings.
- **SurfingTile Custom Anchor Stripping vs. Inline Definitions:** See `references/yaml-syntax-and-anchor-pitfalls.md`. When users add subscriptions or modify settings via the SurfingTile App UI, the app generator strips any custom, non-standard YAML anchors (like `&TG_Use`) while leaving references (`<<: *TG_Use`) intact, causing `yaml: unknown anchor referenced`. Never invent custom anchors for SurfingTile configs; use **inline** `use:` and `filter:` blocks directly inside strategy groups. Also remember that newly imported providers in `proxy-providers` must have their name explicitly added to the group's `use:` list to appear in proxy groups.
