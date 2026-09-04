# Reality & Telegram SOCKS5 Optimization & Kernel Tuning

## 1. Reality Instability: SNI Target Selection & QoS Throttling
When deploying VLESS-REALITY, certain default SNI masquerade targets encounter severe throttling or periodic timeout from domestic provincial ISPs (e.g. Jiangsu, Guangdong):
- **High-Risk Targets**: `www.apple.com`, `www.microsoft.com` frequently experience targeted QoS throttling, TCP reset bursts, or latency flapping during peak hours.
- **Resilient, Fast Alternatives (TLS 1.3 + CDN)**:
  - `swdist.apple.com` (Apple global software delivery CDN — prioritized by domestic ISPs, lowest latency/jitter).
  - `gateway.icloud.com` (iCloud push/gateway, persistent TLS 1.3 handshake).
  - `teams.live.com` (Microsoft global conferencing CDN).
- **Multi-SNI Fallback**: Always configure multiple domains in Xray/Sing-box `serverNames` (e.g. `["swdist.apple.com", "gateway.icloud.com", "www.apple.com"]`) so client and server can negotiate resilient paths.

## 2. Kernel-Level TCP Tuning for Long-Lived Proxy Connections
By default, standard Linux distributions (Ubuntu/Debian) configure conservative TCP keepalive and legacy congestion controls that severely impair long-lived SOCKS5/MTProto connections (especially for Telegram on mobile devices):
- **The 7200-Second Idle Trap**: Default `net.ipv4.tcp_keepalive_time = 7200` means Linux waits 2 hours before probing idle sockets. However, mobile carrier NAT gateways and home routers drop idle TCP mappings after **60 ~ 120 seconds**. When the user re-opens Telegram, the connection is already dead on the carrier side, resulting in an indefinite "Connecting..." spin.
- **Remediation**:
  1. **Google BBR Congestion Control**:
     ```bash
     cat << 'EOF' | sudo tee /etc/sysctl.d/99-bbr-tcp.conf > /dev/null
     net.core.default_qdisc = fq
     net.ipv4.tcp_congestion_control = bbr
     net.ipv4.tcp_keepalive_time = 300
     net.ipv4.tcp_keepalive_intvl = 15
     net.ipv4.tcp_keepalive_probes = 5
     EOF
     sudo sysctl --system
     ```
  2. **Application-Level Socket Options in Inbounds**:
     In Xray / Sing-box stream settings, explicitly enforce `tcpNoDelay: true` and a short `tcpKeepAliveInterval` (e.g. 15s) on both SOCKS5 and Reality inbounds:
     ```json
     "sockopt": {
       "tcpNoDelay": true,
       "tcpKeepAliveInterval": 15
     }
     ```

## 3. Node Naming Conventions & Regex Routing
For proxy clients (Clash/Mihomo/Sing-box) to automatically categorize nodes into appropriate regional policy groups (e.g. `ALL·狮城地区`):
- Embed standard country emojis and Chinese regional names in the proxy `name:` field:
  - e.g. `🇸🇬 新加坡-AWS-REALITY[极速强化]`
- This directly matches regional filter regexes like `(?i)(新加坡|坡|狮城|🇸🇬|(?<![A-Za-z])SG(?![A-Za-z])|SIN|sin|singapore|SGP)`.

## 4. Multi-Protocol Subscription Aggregation Service (Sing-box / Xray)
When providing subscription URLs for multi-protocol node packages without third-party converters:
- Host a lightweight Python HTTP server on an open, dedicated port (e.g. `24633`).
- **Endpoint mapping**:
  - `/clash` or `/clash.yaml` -> returns formatted Clash YAML (`proxies:` list).
  - `/sub` or `/v2ray` -> returns Base64-encoded URL list (for Shadowrocket/v2rayN/Nekobox).
- **Socket binding robustness**:
  Always set `allow_reuse_address = True` on `socketserver.TCPServer` subclass to avoid `OSError: [Errno 98] Address already in use` upon service restart.

## 5. Multi-in-One Script Pitfalls: Why 4 of 5 Protocols Fail on Fresh Installs
When users run popular "5-in-1" or all-in-one Sing-box / Xray install scripts without a custom domain, usually only **VLESS-Reality** works while Hysteria2, TUIC5, VMess-WS, and AnyTLS fail. Here is the exact technical diagnosis and remediation:

| Protocol | Why It Fails by Default | Working Fix & Remediation |
| :--- | :--- | :--- |
| **VLESS-Reality** | ✅ **Works out of the box** because it steals real TLS 1.3 certificates (e.g. `apple.com` / `swdist.apple.com`) without needing a domain or local CA. | Ensure the TCP port is opened in the cloud firewall. |
| **Hysteria 2** | ❌ **Self-signed certificate rejection (`pinSHA256` / `insecure=0`)**: The script generates a self-signed certificate for `www.bing.com` and hardcodes `insecure=0` + `pinSHA256=...`. Client strict TLS checks reject the untrusted CA and terminate the connection immediately. Also requires **UDP** port forwarding. | 1. In the client link/config, set `insecure=1` / `allowInsecure=1` / `skip-cert-verify: true` and remove restrictive `pinSHA256`.<br>2. Ensure the **UDP** port is opened in the cloud firewall. |
| **TUIC v5** | ❌ **Self-signed certificate + missing UDP firewall rule**: Like Hy2, it relies on TLS over QUIC (UDP). Strict clients reject the self-signed cert unless explicitly told to skip verification. | Set `allow_insecure=1` / `skip-cert-verify: true` and open the **UDP** port in cloud security groups. |
| **VMess-WS** | ❌ **Unencrypted plaintext HTTP + non-standard port**: The script sets `tls: false` on an arbitrary high port (e.g. 2082). Plaintext WebSocket headers are easily fingerprinted and dropped by active probing/GFW. | Only usable if proxied behind a legitimate CDN (like Cloudflare on port 80/8080/8880) with a domain. |
| **AnyTLS** | ❌ **Experimental protocol lacking client support**: Very few mainstream client apps parse `anytls://` schemes. | Stick to standard VLESS-Reality or Hysteria2. |
