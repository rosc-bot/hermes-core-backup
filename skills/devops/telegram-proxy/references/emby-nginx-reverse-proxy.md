# Emby Nginx Reverse Proxy on Linux / NAT VPS

This guide documents how to set up an Nginx reverse proxy on a Linux server or NAT VPS to proxy an external HTTPS Emby server (such as Cloudflare-backed Emby services like `https://c.emby.wtf`) and allow client login via raw IP and port without domain/SSL errors.

## Core Nginx Configuration Pattern

```nginx
server {
    listen 30810 default_server;
    listen [::]:30810 default_server;
    server_name _;

    client_max_body_size 1024M;

    # Redirect root to Emby web UI
    location = / {
        return 302 /web/index.html;
    }

    location / {
        proxy_pass https://c.emby.wtf;
        proxy_set_header Host c.emby.wtf;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;

        # WebSocket support (vital for real-time progress, remote control & sync)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # SNI masking (essential for Cloudflare CDN upstream)
        proxy_ssl_server_name on;
        proxy_ssl_name c.emby.wtf;
        proxy_ssl_protocols TLSv1.2 TLSv1.3;

        # Disable buffering for live/video streaming
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

## Key Configuration Directives Explained

1. **SNI Masking (`proxy_ssl_server_name on; proxy_ssl_name <domain>;`)**
   - Upstream CDN/Cloudflare validates the SNI during TLS handshake. Without `proxy_ssl_name`, upstream returns `403 Forbidden` or `404 Not Found`.

2. **WebSocket Proxying (`Upgrade` and `Connection`)**
   - Emby uses WebSockets for player synchronization, remote playback control, and active session heartbeats.

3. **Stream Optimization (`proxy_buffering off;` and `Range` headers)**
   - Disabling buffering allows direct video chunks to stream immediately without Nginx caching multi-gigabyte video files in temporary disk buffers.

## Pitfalls & Troubleshooting on NAT VPS

### 1. Nginx `sched_setaffinity() failed` on LXC / NAT VPS
- **Symptom**: Nginx fails to start or spams error logs with `sched_setaffinity() failed (22: Invalid argument)`.
- **Fix**: Remove `worker_cpu_affinity auto;` from `/etc/nginx/nginx.conf`.

### 2. NAT Port Mapping Verification
- If binding to a NAT port, verify external reachability before troubleshooting Nginx config:
```bash
python3 -c "import socket; s=socket.socket(); s.connect(('199.47.241.137', 30810)); print('Port open')"
```

### 3. Port Conflicts with Xray/VLESS
- Ensure the port chosen for Nginx (e.g. `30810`) is not already claimed by Xray/VLESS or other inbound services. Move Xray to a secondary NAT port if needed.
