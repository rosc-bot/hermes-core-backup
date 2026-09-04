# NAT VPS 轻量级多站点 Emby Nginx 反代面板实战架构

## 1. 适用场景与硬件约束
- **适用环境**：小内存 NAT VPS（如 512MB RAM、1GB 磁盘，Debian/Ubuntu，无独立公网 IPv4/仅分配部分固定外部端口）。
- **痛点**：Nginx Proxy Manager (NPM)、1Panel、宝塔等传统面板需要 Node.js/MySQL/Docker 依赖，启动需 600MB~1GB 内存，会导致 512M 小鸡瞬间 OOM 宕机。
- **解决方案**：Python 标准库原生 `http.server.ThreadingHTTPServer` + Nginx 动态模板热重载架构（常驻内存仅 15~18MB）。

## 2. 架构设计与实现要点

### 2.1 端口与子路径复用（NAT 外部端口受限的最佳解法）
由于 NAT VPS 外部公网端口极其稀缺（通常仅 2~3 个通畅端口如 `35087`、`20022`、`30810`）：
- **单端口多站点（子路径分流）**：
  - 根路径 `/` ➔ 默认 Emby 站点（如终点站 `c.emby.wtf`）
  - `/emby2/` ➔ 私有服 2（如 `https://myemby.org`）
  - `/emby3/` ➔ 公益服 3
  - `/panel/` ➔ Web 可视化管理后台（反代到本地后台服务 `http://127.0.0.1:18090/`）
- **客户端地址格式**：
  - 默认站点：`http://<VPS_IP>:<Port>`
  - 扩展站点：`http://<VPS_IP>:<Port>/<path_prefix>/`
  - 管理面板：`http://<VPS_IP>:<Port>/panel/`

### 2.2 Nginx 流媒体与 WebSocket 反代关键参数
生成反代配置时必须包含流媒体专用优化指令：
```nginx
location / {
    proxy_pass https://target.emby.domain;
    proxy_set_header Host target.emby.domain;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Range $http_range;
    proxy_set_header If-Range $http_if_range;

    # WebSocket 长连接支持
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;

    # SNI 伪装（必须开启，防止 Cloudflare 403）
    proxy_ssl_server_name on;
    proxy_ssl_name target.emby.domain;
    proxy_ssl_protocols TLSv1.2 TLSv1.3;

    # 关闭缓冲，保证视频切片零延迟推流与秒开
    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

### 2.3 Systemd 守护进程与热重载
- 将 Python 后台保存至 `/opt/emby-panel/panel.py`，配置存为 `/opt/emby-panel/sites.json`。
- 每次在网页端增删改站点后，面板自动生成 `/etc/nginx/conf.d/emby_sites.conf` 并执行 `nginx -t && systemctl reload nginx`。

### 2.4 Nginx 路由冲突陷阱与一键复制优化
- **API 路由误伤反代**：
  - 前端面板发起 `fetch('/api/sites')` 获取站点列表时，若 Nginx 仅配置了 `location /panel/`，`/api/sites` 会被 `location /` 兜底规则匹配并误转给上游 Emby 源站，导致前端报「加载失败，请刷新重试」。
  - **修复**：必须在 Nginx 模板中显式增加面板 API 路由转发：
    ```nginx
    location /panel/ {
        proxy_pass http://127.0.0.1:18090/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:18090/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    ```
- **根路径 302 重定向死循环 (ERR_TOO_MANY_REDIRECTS)**：
  - 当未配置根路径站点时，若使用前缀匹配 `location / { return 302 /panel/; }`，浏览器在请求 `/panel/` 时仍会命中 `location /`，导致自己在跟自己死循环重定向。
  - **修复**：必须使用精确匹配语法 `location = / { return 302 /panel/; }`。
- **移动端一键复制兼容性**：
  - 手机浏览器在非 HTTPS（HTTP 明文 IP 访问）环境下，`navigator.clipboard.writeText` 通常因非安全上下文（Secure Context）被浏览器安全策略禁用。
  - **实现方案**：必须实现降级复制（创建临时不可见 `<textarea>` 元素通过 `document.execCommand('copy')` 选中文本执行复制），并在 UI 上提供即时反馈气泡（如高亮变换显示「✅ 已复制!」）。

### 2.5 Hills / TerminusC 客户端测速探测与子路径 404 / ping:-1ms 排障
- **现象**：在 Emby 客户端（如 Hills / TerminusC）中添加子路径反代线路（如 `http://<IP>:<Port>/zdz/`）后，服务器线路显示 `ping: -1ms`（红色超时），无法正常握手与播放。
- **底层原因**：
  1. **测速探活接口**：Hills 客户端测速并非请求根路径或常规网页，而是定向请求 `/emby/system/info/public` 或 `/System/Info/Public` 计算 ping 延迟。在子路径反代下，客户端发出的探测路径形如 `/<prefix>/emby/system/info/public`。
  2. **双斜杠与特殊扩展接口**：部分第三方 Emby 客户端拼接 URL 时容易产生多余斜杠（如 `/<prefix>//emby/Sessions`），且终点站等服务会请求 `/System/Ext/ServerDomains` 等扩展路由。若 Nginx 未对这部分做正则兜底匹配，上游返回 404 会直接导致客户端中断连接。
- **Nginx 精准放行与兜底配置**：
  ```nginx
  # 1. 终点站等特殊扩展接口空数组兜底（支持多斜杠容错）
  location ~* ^/{prefix}/+(emby/)?(System/Ext/ServerDomains|Sessions)$ {
      proxy_pass {target};
      proxy_set_header Host {parsed.netloc};
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_ssl_server_name on;
      proxy_ssl_name {host};
      proxy_intercept_errors on;
      error_page 404 = @empty_json_{prefix};
  }
  location @empty_json_{prefix} {
      default_type application/json;
      return 200 '[]';
  }

  # 2. Emby 客户端 ping 测速探活接口放行（Hills / TerminusC）
  location ^~ /{prefix}/emby/system/info/public {
      proxy_pass {target}/emby/system/info/public;
      proxy_set_header Host {parsed.netloc};
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_ssl_server_name on;
      proxy_ssl_name {host};
  }
  location ^~ /{prefix}/System/Info/Public {
      proxy_pass {target}/System/Info/Public;
      proxy_set_header Host {parsed.netloc};
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_ssl_server_name on;
      proxy_ssl_name {host};
  }

  # 3. 常规业务与流媒体子路径代理
  location ^~ /{prefix}/ {
      proxy_pass {target}/;
      proxy_set_header Host {parsed.netloc};
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Range $http_range;
      proxy_set_header If-Range $http_if_range;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection $http_connection;
      proxy_ssl_server_name on;
      proxy_ssl_name {host};
      proxy_ssl_protocols TLSv1.2 TLSv1.3;
      proxy_redirect off;
      proxy_buffering off;
      proxy_read_timeout 3600s;
      proxy_send_timeout 3600s;
  }
  ```

### 2.6 Emby 源站 Cloudflare 防刷盾与客户端测速 Ping 误判排障
- **现象**：在 Emby 客户端（如 Hills / TerminusC）中添加源站（如终点站 `c.emby.wtf`）反代线路后，线路列表测速显示红色 `ping: -1ms`，但其他源站（如稳健）正常显示延迟。
- **底层原因**：
  1. **Cloudflare 盾拦截空头探测**：部分大型 Emby 公益服源站（如终点站）开启了极高等级的 Cloudflare 5 秒盾与爬虫拦截策略。当客户端测速发出的轻量级 Ping 探活包缺少完整浏览环境或签名时，源站直接返回 `403 Forbidden`。
  2. **线路实际畅通**：虽然 Ping 探活被 Cloudflare 拦截导致客户端报 `-1ms`，但实际音视频切片拉取与播放 API（带完整播放会话 Token 和 Emby Authorization Header）完全正常，点击播放视频依然可以秒开。
- **排障与处置建议**：
  - 不必被客户端列表中的红色 `ping: -1ms` 误导，直接选中该线路进入媒体库点开视频测试真实播放能力。
  - 面板后台的【⚡ 测通】按钮实现时应直接捕获上游返回的 HTTP Status Code（如 403/200/301 均视为 TCP/HTTP 连通已建立，并返回真实 RTT 毫秒数），避免前端将正常的安全拦截错误误判为线路断网。

### 2.7 Python WebUI 处理 HEAD 预检方法缺失致使移动端报 501 故障
- **现象**：在手机浏览器（Chrome / Safari / 微信内置浏览器等）中打开管理面板时，页面白屏或提示错误，Nginx 日志显示 `HTTP/1.1 501 Unsupported method ('HEAD')`。
- **原因**：部分移动端浏览器在真正发起 `GET` 导航前，会先发出 `HEAD` 请求做连接预检和缓存协商。Python 标准库 `BaseHTTPRequestHandler` / `SimpleHTTPRequestHandler` 默认未定义 `do_HEAD()`，导致直接抛出 501 错误。
- **修复**：在 Web 处理器类中显式实现 `do_HEAD()`：
  ```python
  def do_HEAD(self):
      self.send_response(200)
      self.send_header("Content-Type", "text/html; charset=utf-8")
      self.end_headers()
  ```

### 2.8 跨洋高延迟小鸡高码率（4K / 原盘）视频流畅播放极限调优
- **痛点**：欧洲/美洲等高延迟 VPS（往返 RTT > 250ms）反代 Emby 时，由于 TCP 长肥管道效应与拥塞窗口限制，遇到 20Mbps~50Mbps 的 4K / 原画高码率视频切片极易发生缓冲转圈。
- **核心调优方案**：
  1. **Nginx 全局并发与句柄释放**：
     - 系统级配置 `/etc/security/limits.d/99-emby-proxy.conf`（`* soft/hard nofile 65535`）。
     - Nginx 全局配置：`worker_processes auto; worker_rlimit_nofile 65535; events { use epoll; worker_connections 8192; multi_accept on; }`。
     - 启用连接池长复用：`keepalive_timeout 300s; keepalive_requests 100000;` 与多线程端口复用 `listen <Port> reuseport;`。
  2. **专属视频切片大管道流水线 (Video Streaming Buffer Pipeline)**：
     - 针对 `location ~* ^/<prefix>/(emby/)?(videos|audio|sync|Items/.+/Download|Videos/.+/stream)` 独立开启大流缓冲：
       ```nginx
       proxy_buffering on;
       proxy_buffer_size 512k;
       proxy_buffers 16 1m;
       proxy_busy_buffers_size 2m;
       proxy_temp_file_write_size 2m;
       proxy_max_temp_file_size 0;  # 禁用磁盘临时写入，纯内存高速推流，防止小鸡磁盘 IO 瓶颈
       proxy_read_timeout 7200s;
       proxy_send_timeout 7200s;
       ```
  3. **边缘静态资源高速缓存池**：
     - 为图片、剧照、封面等静态资源建立缓存池：
       ```nginx
       proxy_cache_path /var/cache/nginx/emby levels=1:2 keys_zone=emby_static:20m max_size=300m inactive=7d use_temp_path=off;
       ```
     - 匹配 `(Items/.+/Images|web/.*\.(js|css|html|png|jpg|jpeg|gif|ico|woff|woff2)|favicon)` 开启 `proxy_cache emby_static; proxy_cache_valid 200 7d;`，实现海报列表秒开。
  4. **Linux 内核 TCP 协议栈调优**：
     - `/etc/sysctl.d/99-emby-proxy-speed.conf` 中开启 BBR 拥塞控制、`tcp_window_scaling = 1`、`tcp_sack = 1`，将 `tcp_rmem` 与 `tcp_wmem` 最大缓冲区扩大至 16MB。
