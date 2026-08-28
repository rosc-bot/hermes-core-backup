# Telegram in Transparent Proxy (Mihomo / TPROXY / Android Modules) Diagnostics

When troubleshooting Telegram issues under Android transparent proxy root environments (SurfingTile, Box for Magisk) or desktop Mihomo instances, follow this diagnostic guide.

---

## 1. Symptom 1: Photos / Videos / Files Spin Infinitely, But Text Works

### Root Cause:
1. **Load-Balancing Session Fragmentation (`load-balance`)**:
   - Telegram sends text messages over a single primary DC TCP connection.
   - Media (photos, videos, large files) is downloaded concurrently across 4–8 separate TCP streams to Telegram DC servers.
   - If the `Telegram` proxy group uses `type: load-balance`, different chunks are dispatched to different outbound node IPs. Telegram's security mechanism detects erratic IP jumping within the same media session and immediately sends a TCP `RST`, causing the download to hang indefinitely at 99% or spin forever.
2. **Automatic Node Flapping (`url-test`)**:
   - If `Telegram` is bound to a `url-test` group, latency jitters during file downloads trigger seamless node switches. Active TCP download sockets are cut, forcing restart loops.
3. **Node Concurrent Connection Caps**:
   - Free or budget proxy providers often cap maximum concurrent TCP connections per IP (e.g., 5–10). Multiple media streams instantly saturate the quota, dropping subsequent media packets.

### Fix:
- **Never use `load-balance` or aggressive `url-test` for Telegram.**
- In the Web dashboard (Zashboard), manually bind the `Telegram` strategy group to a **single, dedicated, stable node** (e.g., a specific Hong Kong, Singapore, or Japan direct/transit node).

---

## 2. Symptom 2: FCM Notification Pops Up, But Opening TG Hangs in "Connecting..."

### Root Cause:
1. **Separate Network Paths for FCM vs. Telegram DC**:
   - System push notifications travel via Google FCM (`mtalk.google.com:5228`), which routes through Google/domestic direct rules.
   - When tapping into Telegram, the app directly connects to Telegram's European/US Data Centers (pure IP ranges matched by `Telegram_IP` rules).
2. **The `url-test` False-Positive Trap (Google 204 vs. Telegram DC)**:
   - Strategy groups test latency against `https://www.gstatic.com/generate_204`.
   - A node may have lightning-fast ping to Google (100ms), but be completely blocked, rate-limited, or throwing `403 Forbidden` to Telegram DC IP ranges.
   - The automatic group selects this "fake alive" node, trapping Telegram in an unresolvable TCP timeout loop.
3. **Cloudflare (CF) VLESS 100-Second WebSocket Timeout**:
   - Public Cloudflare Workers / Pages VLESS nodes enforce a strict 100-second idle timeout on WebSockets.
   - In background, idle Telegram connections are terminated with TCP RST by Cloudflare edges. Telegram reawakens holding a dead socket, freezing in "Connecting..." until the socket times out.

### Fix:
- Keep Telegram away from Cloudflare CDN/Workers free nodes.
- Bind Telegram to a native TCP / Shadowsocks / Hysteria2 / direct node.

---

## 3. Architectural Pattern: Complete Config-Level Isolation of Telegram from Cloudflare Nodes

To prevent Telegram from ever touching problematic Cloudflare (CF) VLESS / CDN nodes (even under auto-selection), write properties **INLINE** (do NOT use custom anchors in SurfingTile, as SurfingTile's UI generator will wipe custom anchors when adding subscriptions, causing `Unknown anchor` errors):

```yaml
proxy-groups:
  # Dedicated non-CF Telegram group using inline filtering
  - name: Telegram
    icon: "https://cdn.jsdelivr.net/gh/GitMetaio/Surfing@main/app/icon/Telegram.svg"
    type: select
    proxies:
      - TG·延迟最低
      - ALL·香港地区
      - ALL·狮城地区
      - ALL·日本地区
      - ALL·中国台湾
      - ALL·美国地区
      - 🌐 本机·本地直连
    use:
      - "星河"
      - "聚合"
      - "顺畅"
    filter: "^(?!.*(CF|cf|Cloudflare|cloudflare|套餐|重置|剩余|到期|订阅|群|账户|流量|有效期|时间|官网|失联|余额)).*$"

  # Dedicated auto group selecting only from non-CF providers
  - name: TG·延迟最低
    icon: "https://cdn.jsdelivr.net/gh/GitMetaio/Surfing@main/app/icon/Telegram.svg"
    type: url-test
    tolerance: 50
    lazy: true
    interval: 600
    timeout: 3000
    max-failed-times: 3
    url: 'https://www.gstatic.com/generate_204'
    use:
      - "星河"
      - "聚合"
      - "顺畅"
    filter: "^(?!.*(CF|cf|Cloudflare|cloudflare|套餐|重置|剩余|到期|订阅|群|账户|流量|有效期|时间|官网|失联|余额)).*$"
```

---

## 4. Symptom 3: Messages Arrive, But Dashboard Shows 0 Active TG Connections

### Explanation:
- When Telegram operates under Google FCM on Android, it does not maintain a continuous live TCP socket while backgrounded.
- Upon receiving an FCM push notification, Telegram wakes up in the background for 1–2 seconds, performs a burst sync of new messages, and returns to sleep.
- By the time the user opens the Mihomo dashboard to check active connections, the temporary socket has already closed.
- **Verdict**: This is normal, healthy battery-saving behavior, not a connection drop.

---

## 5. Symptom 4: Android Mobile Data (5G/4G) IPv6 Deadlock

### Root Cause:
- Mobile carriers hand down IPv6 addresses.
- Telegram's Android client defaults to preferring IPv6 for DC handshakes.
- If Mihomo has `ipv6: false`, the local network stack may delay IPv4 fallback while waiting for dead IPv6 routes to expire (10–30s delay).

### Fix:
- Inside Telegram App: **Settings -> Data and Storage -> Proxy Settings / Connection Type -> Turn OFF "Prefer IPv6"**.
- In Android APN settings, set protocol to IPv4/IPv6 or IPv4-only if carrier IPv6 routing is unstable.

---

## 6. Summary Checklist for Rock-Solid Telegram Setup
1. **Strategy Group**: Use dedicated non-CF auto group (`TG·延迟最低`) or select a dedicated static non-CF node.
2. **Android Power Management**: Set Telegram battery usage to "Unrestricted" + Enable Autostart + Lock app in recents.
3. **TG App Settings**: Enable "Keep-Alive Service" & "Background Connection" under *Notifications and Sounds*; disable "Prefer IPv6".
