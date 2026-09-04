# Distributed Emby Reverse Proxy Cluster: Master-Agent Architecture

## Architecture Overview
When managing multiple proxy VPS nodes (e.g. Netherlands NAT VPS + Hong Kong high-speed VPS) for Emby reverse proxying:
1. **Master Control Node (e.g. NL VPS)**:
   - Hosts the central Web UI management panel.
   - Provides node switching tabs in the frontend (`All Servers`, `HK Node`, `NL Node`).
   - Dispatches site configuration payloads via REST API (`POST /api/sites`) to remote Agents.
2. **Worker Agent Node (e.g. HK VPS)**:
   - Runs a lightweight background daemon (`emby-agent.service`, ~10MB RAM).
   - Listens on an internal/management port (e.g. `18091`).
   - Receives JSON site definitions, writes local Nginx configurations (`/etc/nginx/conf.d/emby_hk_sites.conf`), validates with `nginx -t`, and reloads `systemctl reload nginx`.

## Key Implementation Details

### 1. Agent Daemon Implementation (`/opt/emby-agent/agent.py`)
- Python 3 built-in `http.server` (zero external dependencies).
- Handles `/api/sites` (GET & POST) and `/api/status`.
- Automatically executes Nginx reload upon saving new configurations.

### 2. Stream & Bitrate Optimization for 4K Playback
For high-bitrate 4K HEVC/Remux files (20Mbps+), standard `proxy_buffering off;` causes stuttering across high-latency or cross-border connections.
Apply pipeline buffering for streaming endpoints:
```nginx
location ~* ^/{prefix}/(emby/)?(videos|audio|sync|Items/.+/Download|Videos/.+/stream) {
    proxy_pass {target};
    proxy_set_header Host {upstream_host};
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Range $http_range;
    proxy_set_header If-Range $http_if_range;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_ssl_server_name on;
    proxy_ssl_name {upstream_host};
    proxy_ssl_protocols TLSv1.2 TLSv1.3;
    proxy_redirect off;
    proxy_buffering on;
    proxy_buffer_size 512k;
    proxy_buffers 16 1m;
    proxy_busy_buffers_size 2m;
    proxy_temp_file_write_size 2m;
    proxy_max_temp_file_size 0;
    proxy_read_timeout 7200s;
    proxy_send_timeout 7200s;
}
```

### 3. Client Ping Latency & Emby Probing Fix
Mobile clients (e.g. Hills, VidHub, Infuse) verify node reachability using specific public endpoints.
Sub-path reverse proxies MUST include exact bypass locations:
```nginx
location ^~ /{prefix}/emby/system/info/public {
    proxy_pass {target}/emby/system/info/public;
    proxy_set_header Host {upstream_host};
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_ssl_server_name on;
    proxy_ssl_name {upstream_host};
}
location ^~ /{prefix}/System/Info/Public {
    proxy_pass {target}/System/Info/Public;
    proxy_set_header Host {upstream_host};
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_ssl_server_name on;
    proxy_ssl_name {upstream_host};
}
```
Without these rules, clients show `ping: -1ms` (red status) and failover logic may reject the proxy.
