# Cloudflare Worker Emby Proxy & DNS 优选部署与排障指南

## 背景与架构
本项目基于 Cloudflare Workers 边缘计算实现 Emby / Jellyfin 视频反代、分片边缘缓存（KV）与前端可视化管理台（CF-EMBY-PROXY-UI / MakaMaka）。

## 核心部署要点

### 1. 必需环境变量（Runtime Variables & Secrets）
- `ADMIN_PASS`：后台管理密码（**注意：代码严格匹配 `ADMIN_PASS`，不可拼写为 `ADMIN_PASSWORD`**）。
- `JWT_SECRET`：用于 Session 签名的随机字符串（建议 32 位随机字符）。
- **Cloudflare 控制台保存陷阱**：在 Cloudflare Dashboard 添加环境变量后，必须往下滑动到底部点击 **「部署 / Save and Deploy」**，否则变量仅驻留在草稿状态，Worker 启动时会报 `系统未初始化：缺少 ADMIN_PASS、JWT_SECRET`。

### 2. 前端静态页面初始化（Index Source 上传）
- 项目将 Vue 前端 (`index.html`) 与边缘代理代码分离以精简 Worker 体积。
- 首次进入 `/admin` 会展示「管理台壳层正在处理中」，需上传编译好的 `index.html`（写入 KV 缓存）后方可进入图形化大面板。

### 3. API Token 权限与资源配置（DNS 工作台与流量统计）
在 Cloudflare 创建自定义 API Token 时，必须满足以下条件，否则保存 DNS 会报 403 权限不足或保存失败：
- **权限 (Permissions)**：
  1. `区域 (Zone)` - `DNS` - `编辑 (Edit)`
  2. `区域 (Zone)` - `区域 (Zone)` - `读取 (Read)`（**关键！缺少此权限无法校验 Zone 信息，直接拦截**）
  3. `区域 (Zone)` - `Analytics` - `读取 (Read)`（用于仪表盘拉取实时流量与请求分析）
- **区域资源 (Zone Resources)**：
  - 必须选择 **「包含 - 账户中的所有区域 (All zones from an account)」**，或者选择顶级根域名（如 `ccwu.cc`）。
  - **严重陷阱**：**切勿在特定区域中选择二级域名（如 `ruxi666.ccwu.cc`）**。Cloudflare 的 Zone 只能是顶级托管域名，选二级域名会导致 Token 作用域为空，所有 API 调用均返回权限不足。
- **客户端 IP 筛选**：必须留空，不可填本地 IP，因为 Worker 发起 API 请求的来源是 Cloudflare 边缘机房节点。

### 4. 常见报错与排障
- **Error 1034: Edge IP Restricted**：
  - **原因**：将外部域名直接 CNAME 到了第三方 Cloudflare for SaaS 优选节点（如 `saas.sin.fan`），但未在对应 SaaS 回退源完成 Custom Hostname 授权。
  - **解决**：删除 CNAME 记录，改用优选 A 记录（直接解析到 IPv4 优选 IP）。
- **DNS points to prohibited IP (403)**：
  - **原因**：开启了小云朵代理的 DNS 记录直接指向了 Cloudflare 自身的节点 IP 或保留地址，触发死循环自保护。
  - **解决**：在 Worker 设置中的「Domains & Routes」绑定 Custom Domain，由系统接管解析。
- **同一反代地址电脑有速度、手机 WiFi 没速度/卡死**：
  1. **IPv6 拥堵（首要元凶）**：手机 WiFi 默认激进走 IPv6，国内访问 Cloudflare IPv6 丢包率高。关闭路由器/手机 IPv6 或切手机 5G 流量可恢复。
  2. **服务端转码 (Transcode)**：电脑端能直接硬解（Direct Play），手机端因字幕（ASS 特效字幕）或音轨不支持触发 VPS 实时转码，CPU 满载卡死。解决方法为关闭字幕或强制原始画质。
  3. **客户端并发与缓存**：手机使用官方客户端单线程拉流受限，建议更换第三方内核播放器（iOS: VidHub/Infuse/SenPlayer，Android: Yamby/MPV）。
