# NAT VPS 节点与 Emby 反代端口隔离及多协议排错指南

## 1. 核心教训：严禁端口冲突
在 NAT VPS（如荷兰🐔、各类共享 IP 小鸡）上部署多种服务时，**每个公网映射端口必须严格独占单一业务**：
- 严禁将 Nginx Web/Emby 反代配置到正在运行 VLESS-REALITY 或 MTProto 的端口上（如 `30810`）。
- 否则会导致原本可用的科学上网节点或代理完全瘫痪失效。

## 2. Emby Nginx 反代配置规范（支持纯 IP 直连与 SNI 伪装）

### (1) HTTP 端口反代 (推荐，无客户端证书告警)
```nginx
server {
    listen <NAT_HTTP_PORT> default_server;
    listen [::]:<NAT_HTTP_PORT> default_server;
    server_name _;

    client_max_body_size 500M;

    location = / {
        return 302 /web/;
    }

    location / {
        proxy_pass https://c.emby.wtf;
        proxy_set_header Host c.emby.wtf;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;

        # WebSocket 必配 (播放心跳与弹幕同步)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 向上游源站做 SNI 握手
        proxy_ssl_server_name on;
        proxy_ssl_name c.emby.wtf;
        proxy_ssl_protocols TLSv1.2 TLSv1.3;

        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

### (2) HTTPS 端口反代 (自签名证书配置)
```bash
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/emby.key \
  -out /etc/nginx/ssl/emby.crt \
  -subj "/CN=199.47.241.137"
```

## 3. 常见排错与排查特征

| 客户端报错 / 现象 | 真实根因 | 解决排错手段 |
|---|---|---|
| 日志出现 `\x16\x03\x01` 报 400 | 客户端勾选了 HTTPS，却请求了纯 HTTP 端口 | 指引用户在 Emby 客户端中关闭 SSL / HTTPS 选项，或者提供独立的 SSL 监听端口 |
| 访问根路径白屏或 404 | Emby 默认 Web 根目录为 `/web/` | 在 Nginx 中配置 `location = / { return 302 /web/; }` |
| 节点导入提示不可用 | REALITY 端口被本地 Web 服务抢占 | 恢复 Xray 独占监听，将 Web 反代转移到独立分配端口 |
