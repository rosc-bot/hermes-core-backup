---
name: cloudflare-workers-media-proxy
description: "Deploy and troubleshoot Cloudflare Workers media proxies."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Cloudflare, Workers, Emby, Jellyfin, Streaming, Proxy, DNS, KV, D1]
---

# Cloudflare Workers Media Proxy (CF-EMBY-PROXY-UI / MakaMaka)

When deploying, configuring, or troubleshooting media proxy systems built on Cloudflare Workers (such as CF-EMBY-PROXY-UI / Emby Proxy V19.x or MakaMaka Emby Proxy):

## 1. Core Architecture & Prerequisites

| Resource | Variable / Key | Purpose | Critical Notes |
| :--- | :--- | :--- | :--- |
| **KV Namespace** | `ENI_KV` or `KV` or `EMBY_KV` | Route caching, config storage, HTML shell | Must be uppercase. Required for V19.x. |
| **Admin Secret** | `ADMIN_PASS` (V19.x) / `ADMIN_TOKEN` (MakaMaka) | Web admin authentication | Case-sensitive. Must deploy/save in CF dashboard. |
| **JWT Secret** | `JWT_SECRET` | Session encryption (V19.x) | 32+ character random string. |
| **D1 Database** | `DB` / `D1` / `PROXY_LOGS` | Access logs, traffic analysis | Optional for core streaming; required for full charts. |

## 2. Cloudflare API Token & Permissions

When connecting the proxy admin panel to Cloudflare for DNS management, preferred IP scraping, and analytics:

- **Required Permissions**:
  - `Zone -> DNS -> Edit` (Modify DNS records)
  - `Zone -> Zone -> Read` (Verify zone identity; without this, DNS save fails with 403)
  - `Zone -> Analytics -> Read` (Display traffic analytics on dashboard)
- **Zone Resources Scoping**:
  - **CRITICAL**: Select `Include -> All zones from an account` OR select the **root apex domain** (e.g. `example.com`).
  - **NEVER** select a subdomain (e.g. `sub.example.com`) as a "Specific Zone" — Cloudflare only treats apex domains as zones. Subdomain scoping renders the token invalid (0 accessible zones).
- **Client IP Filtering**: Keep completely EMPTY. Workers execute on global edge nodes with arbitrary egress IPs.

## 3. Common Errors & Pitfalls

### Emby Worker Proxy (chenhr454/emby---worker) Trailing Slash & Format Issues
- **Problem**: In player clients (Hills, SenPlayer, VidHub, etc.), entering proxy URL without a trailing slash (`https://domain.com/prefix`) causes playback/info failures or ExoPlayer fallback errors (`Exo 不支持此格式，切换至 mpv`).
- **Cause**: Upstream worker UI constructs proxy URL as `${origin}/${nodeName}` without trailing slash. When clients concatenate `/emby/system/info`, path resolution breaks or matches redundant double paths (`/prefix//emby/prefix/Videos/...`).
- **Fix**:
  1. Always ensure client URL ends with a slash: `https://domain.com/prefix/`.
  2. In `worker.js`, patch UI copy logic to append trailing slash:
     ```javascript
     const normalUrl = location.origin + '/' + encodeURIComponent(n.name) + '/';
     ```

### Origin Cloudflare 5-Second Challenge / Shield (cf-mitigated: challenge / HTTP 520 / 403)
- **Problem**: A target Emby origin (e.g. `ey.lightting.net`) shows red "Offline" / "离线" status in Worker proxy test and fails playback immediately.
- **Cause**: The origin server enabled Cloudflare "Under Attack" mode or JavaScript challenge. CF Workers cannot solve JS Turnstile/Challenge headless and get blocked with HTTP 403 / 520.
- **Fix**: Use a standalone VPS (NAT or direct VPS) with native Nginx reverse proxy instead of CF Workers, or whitelist the Worker egress IPs on the origin.

### Error 1034: Edge IP Restricted
- **Cause**: An external domain has a CNAME pointing to an unverified/unauthorized Cloudflare for SaaS fallback origin (e.g. `saas.sin.fan`).
- **Fix**: Remove the CNAME and switch to direct preferred A records (IPv4 addresses), or configure the domain properly under Cloudflare Custom Hostnames.

### Error: DNS points to prohibited IP (HTTP 403)
- **Cause**: A proxied DNS record (orange cloud enabled) points directly to Cloudflare's own anycast IPs (e.g. 104.21.x.x, 172.67.x.x) or loopback (127.0.0.1).
- **Fix**: Add the domain via Worker `Custom Domains` (Settings -> Domains & Routes), which automatically provisions certificates and correct routing.

### DNS Save Failed in Web UI
- **Cause 1**: API Token missing `Zone:Read` permission or improperly scoped to a subdomain.
- **Cause 2**: Account metadata cached in KV (default 60m TTL). Clear site cache in Global Settings and re-save account credentials.
- **Cause 3**: CNAME conflict with existing A/AAAA records on the same subdomain. Switch to A mode or delete preexisting A records in Cloudflare DNS first.

### "System uninitialized / Missing ADMIN_PASS"
- **Cause**: Environment variables entered in Cloudflare Dashboard were left in draft mode.
- **Fix**: Scroll down to the bottom of the Cloudflare settings page and click `Deploy` / `Save and Deploy`.
