# Emby Multi-Site Dual-Route Reverse Proxy Architecture & Performance Tuning

## 1. Background & Core Architectural Shift
In low-spec NAT VPS cluster environments (e.g. Taiwan 122MB LXC + Netherlands 512MB VPS + AWS Master Panel on port 3000):
- **Never attempt cross-node daisy-chain relays**: Routing traffic `Client -> TW -> NL -> Origin` adds extra cross-continental RTT (~80ms+) and halves effective throughput.
- **Dual-Route Concurrent Deployment**: Each Emby route is deployed synchronously to BOTH nodes (Taiwan + Netherlands) simultaneously via the master panel.
- **Direct Independent Endpoints**: Clients receive two permanent endpoint URLs (e.g., `http://45.207.153.154:29759/path/` and `http://199.47.241.137:35087/path/`) so users can test and switch directly in their media player (Hills, VidHub, Infuse) without re-configuring or copying URLs again.

## 2. Server Profile-Matched Buffer Sizing (Avoid OOM & BDP Choke)

| Node | RAM / Bandwidth / RTT | Buffer Sizing | Rationale |
|---|---|---|---|
| **🇹🇼 Taiwan (LXC)** | 122MB RAM / 215Mbps / 34ms RTT | `proxy_buffers 8 512k;` (4MB total)<br>`proxy_buffer_size 256k;`<br>`proxy_busy_buffers_size 1m;` | Low BDP (34ms). A 4MB pool uses only 4.5% of available RAM (88MB), avoiding LXC OOM killer while fully saturating 215Mbps for 4K. |
| **🇳🇱 Netherlands (VPS)** | 512MB RAM / 1000Mbps / 190ms RTT | `proxy_buffers 16 1m;` (16MB total)<br>`proxy_buffer_size 256k;`<br>`proxy_busy_buffers_size 2m;` | High BDP (190ms cross-continental). 16MB is the sweet spot: prevents the TCP window from stalling on trans-Eurasian links while avoiding first-frame delivery delays caused by oversized buffers (>32MB). |

> **Warning on Buffer Overflow Math**:
> In Nginx, `proxy_busy_buffers_size` MUST be strictly less than `(number of buffers - 1) * buffer_size`. For example, with `buffers 4 256k` (total 1024k), `busy_buffers_size` must be `<= 768k` (e.g. 512k), otherwise `nginx -t` fails with `[emerg] proxy_busy_buffers_size must be less than the size of all proxy_buffers minus one buffer`.

## 3. Path Normalization & Regex Location Traps
1. **Nginx Location Priority Bug (`^~` vs `~*`)**:
   - Using `location ^~ /prefix/` causes Nginx to match prefix and **completely suppress all regex (`~*`) evaluation**, meaning video stream rules, 302 handlers, and path rewriting below it are never evaluated.
   - **Fix**: Use standard prefix `location /prefix/` or ensure all sub-rules use exact or regex match.
2. **Duplicate Subpath & Slashes from Clients (Hills/VidHub)**:
   - When a client is configured with `http://host:port/prefix/`, players often request `/prefix//emby/prefix/Videos/...` or `/prefix/emby/Videos/...`.
   - If Nginx proxies this uncleaned to the origin, the origin returns empty JSON `{}` (12 bytes, HTTP 200), causing mobile players (e.g. ExoPlayer) to throw:
     `"Exo播放器不支持此格式视频，切换至mpv播放器进行播放"`.
   - **Fix**: Use `rewrite` in regex locations:
     ```nginx
     location ~* ^/prefix/+(emby/)?prefix/(videos|Videos)/(.+)$ {
         rewrite ^/prefix/+(emby/)?prefix/(videos|Videos)/(.*)$ /Videos/$3 break;
         proxy_pass http://base_origin;
     }
     location ~* ^/prefix/+(emby/)?(videos|Videos)/(.+)$ {
         rewrite ^/prefix/+(emby/)?(videos|Videos)/(.*)$ /Videos/$3 break;
         proxy_pass http://base_origin;
     }
     ```
3. **No URI Part inside Regex `proxy_pass`**:
   - In Nginx, inside `location ~*`, you cannot write `proxy_pass http://upstream/subpath/`. It throws:
     `"proxy_pass" cannot have URI part in location given by regular expression`.
   - Always split the target into base origin (`$scheme://$host`) and use `rewrite ... break` before `proxy_pass`.

## 4. Origin Server Characteristics & Route Selection
- **TerminusC (`c.emby.wtf`)**: Enforces strict geo-blocking on Asian IPs (HTTP 403 Forbidden). Must be proxied through European IPs (Netherlands).
- **Wenjian (`m.wenjian.de`)**: Origin storage servers in Europe (Germany/Hetzner). NL node pulls slices in <0.2s; TW pulls in 4-6s. Recommend Netherlands route.
- **Feiyue / SFCJ (`cf.sfcj.org`)**:
  - Emby returns HTTP 302 redirecting to external media storage (`media.emby.pro`).
  - `media.emby.pro` throttles or blackholes raw Asian datacenter/residential IPs (180s connect timeout), but delivers >40MB/s to European IPs (NL node). Recommend Netherlands route.
- **MeowFly (`gy.meowfly.de`)**: European German origin. NL node achieves 45ms RTT and >50MB/s throughput. Recommend Netherlands route.
- **Lightting (`ey.lightting.net`)**: Asia-Pacific edge CDN. TW node achieves 34ms RTT. Recommend Taiwan route.

## 5. Non-Blocking Master Panel Architecture
- **Avoid Synchronous SSH in HTTP Handlers**:
  - Pushing Nginx configs to multiple remote nodes via SSH inside a POST request takes 3-6s.
  - Mobile browsers terminate idle POST requests after 3s with `"Network request failed: Failed to fetch"`.
  - **Solution**: Decouple API response from deployment. Persist JSON locally, respond `{"ok": true}` immediately in <2ms, and dispatch node deployment via background thread (`threading.Thread(target=sync_all_nodes, args=(sites,), daemon=True).start()`).
