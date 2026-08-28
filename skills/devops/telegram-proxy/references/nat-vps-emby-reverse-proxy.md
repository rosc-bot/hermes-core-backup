# NAT VPS 节点与 Emby 反向代理部署实战排障指南

## 背景与核心难点
在 NAT 架构的 VPS（如荷兰 199.47.241.137）上同时部署科学上网（Xray REALITY / SOCKS5）和 Emby 反代时，存在两大核心陷阱：
1. **外部端口映射受限且不连续**：商家分配给本小鸡的公网外部端口有限（如仅 `30810` 和 `35087` 通畅），探测到的其他端口属于同母机的邻居小鸡，盲目配置会导致 404 或流量串号。
2. **端口资源冲突**：若 Emby 反代占用了 REALITY 端口（如 30810），会导致梯子节点瞬间失效断连。

---

## 真实端口排查与嗅探方案

切勿盲目猜测可用端口，必须使用双端握手嗅探器：
1. **服务端（小鸡内部）**：启动临时 Python 脚本监听常用区间的所有端口。
2. **客户端（控制机）**：从外部向目标 IP 发送带有特定标记（如 `PROBE_EXT_{port}`）的 TCP 探测包。
3. **确认映射**：只有服务端真实收到对应数据包的端口，才是真正分配给本小鸡的可用外部端口。

---

## Emby 反代 Nginx 最佳配置模板（纯 IP 直连 + 域名 SNI 伪装）

目标站通常启用了 Cloudflare 防护，直连 IP 访问必须在 Nginx 中注入正确的 Host 与 SNI：

```nginx
server {
    listen 35087 default_server;
    listen [::]:35087 default_server;
    server_name _;

    client_max_body_size 1024M;

    location / {
        proxy_pass https://c.emby.wtf;
        proxy_set_header Host c.emby.wtf;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;

        # WebSocket 关键配置
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # SNI 域名伪装
        proxy_ssl_server_name on;
        proxy_ssl_name c.emby.wtf;
        proxy_ssl_protocols TLSv1.2 TLSv1.3;

        # 流媒体必须关闭缓冲，确保拖拽进度条不卡顿
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

---

## 客户端连接指南 (TerminusC / Hills)
- **服务器 (Host)**：填入 VPS 真实公网 IP（如 `199.47.241.137`）
- **端口 (Port)**：填入反代专属端口（如 `35087`）
- **HTTPS / SSL**：**必须关闭 / 取消勾选**（避免因自签名或无证书触发 SSL 证书校验阻断）。
