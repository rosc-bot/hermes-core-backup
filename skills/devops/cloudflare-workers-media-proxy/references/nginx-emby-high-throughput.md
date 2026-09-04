# Nginx Emby Reverse Proxy Reference: Multi-Node & High-Throughput Streaming

This reference document compiles production-tested rules, buffer sizing formulas, and path deduplication rewrites for reverse-proxying Emby/Jellyfin across NAT VPS clusters and Cloudflare Workers.

---

## 1. High-Throughput Streaming Buffer Sizing (Nginx)

Blindly maximizing buffer size degrades streaming: huge buffers delay first-frame playback (waiting for buffer to fill), cause scrubbing/seeking lag, and risk OOM on small containers.

| Node Spec | RAM Budget | Recommended Buffer Sizing | Target Workload |
| :--- | :--- | :--- | :--- |
| **Low-Memory NAT VPS (LXC)** | ~128MB RAM | `proxy_buffers 8 512k;`<br>`proxy_buffer_size 256k;`<br>`proxy_busy_buffers_size 1m;` | 30~50ms low latency (e.g. Taiwan NAT), 4K high bitrate, zero OOM risk. |
| **Medium VPS** | ~512MB RAM | `proxy_buffers 16 1m;`<br>`proxy_buffer_size 256k;`<br>`proxy_busy_buffers_size 2m;` | 180~200ms trans-continental latency (e.g. Europe/Netherlands NAT), high throughput. |

**Key Nginx Directives:**
```nginx
proxy_buffering on;
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_read_timeout 7200s;
proxy_send_timeout 7200s;
```

---

## 2. Path Deduplication & Multiple-Prefix Rewrites

Some players (e.g., Hills, VidHub, SenPlayer) or origin servers with pre-existing prefixes cause double-path requests like `/flgm//emby/flgm/Videos/123/stream.mkv`.
If Nginx proxies without stripping, the origin returns an empty JSON `{}` (12 bytes), triggering player errors like:
`"Exo播放器不支持此格式视频，切换至mpv播放器进行播放"`.

**Fix via Nginx rewrite in specific location:**
```nginx
location ~* ^/prefix/+(emby/)?prefix/(videos|Videos)/(.+)$ {
    rewrite ^/prefix/+(emby/)?prefix/(videos|Videos)/(.*)$ /Videos/$3 break;
    proxy_pass https://origin.domain;
    proxy_http_version 1.1;
    proxy_set_header Host $proxy_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Range $http_range;
    proxy_set_header If-Range $http_if_range;
    proxy_ssl_server_name on;
    proxy_ssl_name origin.domain;
    proxy_ssl_protocols TLSv1.2 TLSv1.3;
}
```

*Note: Never use `location ^~` before regex locations if regex rewriting is expected, as `^~` stops regex evaluation.*

---

## 3. 302 Media Stream Redirection (网盘直链) Pitfalls

Many public Emby servers return a `302 Found` pointing to external storage (e.g. `media.emby.pro`, Google Drive, Alist, Cloudflare R2).
- If the player directly follows 302, playback bypasses your proxy node and downloads straight from the storage host, which may be throttled or blocked by domestic ISPs.
- If storage signs requests bound to client IP, proxy interception may fail unless headers are properly forged.
- Testing: always inspect response headers via `curl -I` on the `/stream.mkv` endpoint to identify whether 200 (direct stream) or 302 (redirect stream) is returned.
