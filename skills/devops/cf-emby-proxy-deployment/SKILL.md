---
name: cf-emby-proxy-deployment
description: Use when deploying or troubleshooting CF-EMBY-PROXY-UI.
---

# CF-EMBY-PROXY-UI 部署与运维指南

本项目基于 Cloudflare Workers 边缘中继（Headless Edge Relay），用于 Emby/Jellyfin 视频流反代加速、图片与元数据缓存、多线路分流及 DNS 优选。

## 1. 核心架构与依赖

| 资源 / 变量 | 作用 | 说明 |
|---|---|---|
| `ENI_KV` (或 `KV`) | 核心配置与状态存储 | **必须绑定** KV Namespace，用于持久化路由与节点数据 |
| `ADMIN_PASS` | 管理台登录密码 | 环境变量/机密（必填），用于 `/admin` 访问鉴权 |
| `JWT_SECRET` | Token / Cookie 签名密匙 | 环境变量/机密（必填），随机字符串 |
| `DB` (或 `D1`) | 日志与安全事件库 | 可选绑定 D1 数据库（缺失仅影响日志统计） |

## 2. 部署流程

1. **创建 KV**：在 Cloudflare Dashboard 创建命名空间（如 `emby-proxy-kv`）。
2. **部署 Worker**：新建 Worker 并粘贴打包后的 `worker.js` 代码。
3. **绑定与变量**：
   - 绑定 KV：Variable name 必须大写填写 `ENI_KV`。
   - 环境变量：设置 `ADMIN_PASS` 和 `JWT_SECRET`。
   - **注意**：在 Cloudflare 控制台添加变量后，必须滑到最下方点击 **Save and Deploy (保存并部署)**，否则环境变量处于草稿状态，页面会报“系统未初始化”。
4. **前端面板初始化**：
   - 首次访问 `https://你的域名/admin` 会进入 Admin Shell 上传页。
   - 从 GitHub 官方仓库获取编译好的 `frontend/dist/index.html`（约 750KB）并上传，系统会自动写入 KV 缓存。

## 3. 节点与路由配置

- **节点路径**：如 `alpha` 或 `emby`，播放入口对应 `https://域名/alpha`。
- **线路目标**：填真实源站（如 `http://IP:8096` 或 `https://域名:8920`）。若源站未配置 SSL 必须填 `http://`，避免 525/526 握手失败。
- **验证连通性**：在浏览器访问 `https://域名/节点路径/System/Info/Public`，返回 JSON 即表示线路畅通。

## 4. 常见排查与避坑点

### ① 域名报 DNS_PROBE_FINISHED_NXDOMAIN
- **原因**：自定义域名刚绑定，本地运营商 DNS 或移动端浏览器 Socket 缓存未刷新。
- **解决**：使用手机无痕模式访问，或在 Wi-Fi 中将 DNS 改为 `223.5.5.5` / `119.29.29.29`。

### ② 今日视频流量显示“CF 查询失败: 缺少 analytics.read”
- **原因**：创建的 Cloudflare API Token 缺少分析数据读取权限。
- **解决**：在 API Token 权限中追加 `Zone - Analytics - Read` 权限。

### ③ DNS 保存失败 (Cloudflare DNS 保存失败)
- **原因 1：API Token 权限不足或资源范围错误（最常见）**：
  - 缺少 `Zone - Zone - Read`（区域 - 区域 - 读取）权限：代码在修改 DNS 前必须先调用 `GET /zones/{id}` 校验域名归属，缺少该权限直接返回 403。
  - 缺少 `Zone - DNS - Edit`（区域 - DNS - 编辑）权限。
  - 资源范围误选为二级域名：在 Cloudflare 中 Zone 必须是顶级根域名（如 `ccwu.cc`），不能在“特定区域”填二级域名；最稳妥的做法是选择“账户中的所有区域 (All zones from an account)”。
  - 误将客户端 IP 地址筛选（Client IP Filtering）填成了个人 IP：Worker 边缘节点访问 API 会被 IP 阻断，该配置必须留空。
- **原因 2：全局设置缓存了旧 Token**：
  - 面板默认设置“计划缓存时间：60 分钟”，更新 Token 后必须前往【全局设置】拉到最下方点击 **【一键清理全站缓存】** 并重新点击 **【保存账号设置】**，否则仍使用旧凭证。
- **原因 3：CNAME 记录冲突**：
  - 在 CNAME 模式下保存时，该子域名已存在 A/AAAA 记录或已作为 Worker 自定义域名绑定，触发 Cloudflare 冲突限制（1004 / 81044）。
- **终极保底方案**：
  - 若自定义 Token 权限排查困难，可直接使用 Cloudflare 账户的 **Global API Key**（全局 API 密钥），无任何权限阻碍。

### ④ 推荐优选 IP / 域名抓取源
- `https://raw.githubusercontent.com/hubbylei/bestcf/main/bestcf.txt` (GitHub 稳定优选源)
- `https://api.uouin.com/cloudflare.html` (国内第三方测速源)

### ⑥ 轻量多站点子路径反代面板（NAT VPS / 低配小鸡场景）
- **适用场景**：512MB 内存、无公网 IPv4 或外部端口受限的 NAT VPS，无法运行 NPM / 宝塔等重量级面板。
- **架构方案**：
  1. **极简 Python3 管理服务**：利用原生 `http.server`，零依赖，内存占用仅约 15MB。
  2. **单端口多站点子路径分流**：共用一个开放端口（如 `35087`），通过 `/zdz/`、`/wj/` 等子路径反代不同源站。
  3. **自动化 Nginx 配置生成与热重载**：面板保存站点时自动生成 `emby_sites.conf` 并执行 `nginx -t && nginx -s reload`。
  4. **关键避坑点**：
     - **API 分流隔离**：前端请求 `/api/sites` 必须在 Nginx 中显式代理至本地面板端口，防止误将管理 API 转发给 Emby 源站导致 404。
     - **HTTP HEAD 方法支持**：部分移动端浏览器在访问前会发起 HEAD 预检，后端必须实现 `do_HEAD` 响应 200，否则会触发 `501 Unsupported method` 导致打不开面板。
     - **精确根路径重定向**：根路径跳转必须使用 `location = / { return 302 /panel/; }`，避免宽泛匹配导致循环重定向（`ERR_TOO_MANY_REDIRECTS`）。
     - **客户端 Ping 测速与探测放行**：Hills 等客户端在测速时会请求 `/prefix/emby/system/info/public` 计算延迟。必须配置专属直通 location 并透传 HTTPS 协议头，否则客户端将显示 `ping: -1ms`（超时标红）。
     - **终点站/部分公益服特殊接口兜底**：登录时会探测 `/System/Ext/ServerDomains` 与 `/Sessions`，需在 Nginx 中对这些接口配置 `@empty_json` 空数组（`[]`）拦截兜底，避免 404 导致登录断开。

### ⑧ GitHub Fork 仓库与 Cloudflare Pages 联动自动更新
- **Fork 仓库默认禁用 Actions**：GitHub 为防滥用默认暂停 Fork 仓库的工作流。若上游仓库自带 `sync.yml`，必须在 GitHub 仓库的 **Actions** 标签页点击 **`Enable workflows`** 才能激活每日自动同步。
- **Cloudflare Pages 全自动持续集成**：将 Cloudflare Pages 绑定至个人 GitHub 仓库后，每次 Actions 自动同步上游最新 commit，Cloudflare 会在 30 秒内自动触发构建并部署上线，实现节点与反代版本永久自动跟随。

### ⑨ 订阅聚合控制台与自动化优选 IP 注入 (Joey / CF-Cyberpunk 架构)
- **动态优选源接入 (`yxURL`)**：在订阅中心后台直接配置 `yxURL` 为高频更新的 Clean IP 文本源（如 `https://raw.githubusercontent.com/ymyuuu/IPDB/main/bestcf.txt`），客户端更新订阅时会自动拉取最新的优质低延迟 IP。
- **API 自动化回填**：支持通过 `POST /api/config` 传入 JSON 配置，实现与本地 `CloudflareSpeedTest` 测速脚本联动并自动刷新优选列表。
- **地区分流与模块匹配规范（节点命名）**：
  - 客户端（Clash / Subconverter / Surge 等分流规则模块）依赖**标准国旗 Emoji 与国家中文名**进行正则匹配与自动归类。
  - 优选节点命名规范必须对齐：`IP:443#🇺🇸 美国 01 [电信优化]`、`IP:443#🇯🇵 日本 01 [联通优化]`。若缺少国家标识或误写为纯省份名称，分流策略组将无法识别。
- **协议兼容性与避坑点**：
  - **Trojan 协议超时**：Cloudflare 免费 CDN 架构通常不原生支持标准 Trojan 握手，开启后易导致全线节点超时（-02 节点）；若非必要建议关闭（`et: no`），主力使用兼容性最好的 `Vless + WebSocket`。
  - **ECH 阻断**：国内部分省级运营商（电信/移动）会对 ECH 加密握手直接重置丢包导致超时，国内环境下建议关闭 ECH（`ech: no`）。
  - **XHTTP (SPLITHTTP) 兼容性**：需要客户端内核支持（如 v2rayNG 最新版、Sing-box 1.10+），旧版 Clash 内核不识别 `type=xhttp` 会导致节点无反应。
  - **7890 端口冲突 (`bind: address already in use`)**：移动端代理软件提示该错误时，说明后台有其他代理应用残留占用端口，需彻底划掉后台进程或重启手机。

### ⑩ Master-Agent 多服务器集群集中反代架构 (多节点统一管理)
- **业务痛点**：多台 VPS（如欧洲高延迟小鸡 + 亚太超低延迟小鸡）需同时反代多个 Emby，单独部署多个面板难以统一维护与分发。
- **架构方案**：
  1. **Master 中心控制台**：运行在任一可用机器（如荷兰 NAT VPS），维护全部节点与站点的统一配置（`sites.json`），提供多节点切换 UI。
  2. **Agent 同步代理端**：在其他小鸡（如香港优化 VPS）运行极简轻量 Agent（监听独立端口如 `18091`），对外开放专属 Emby 反代端口（如 `18096`）。
  3. **自动化跨机同步**：Master 每次添加/修改站点，自动按照节点归属（`node: "nl" | "hk"`）对本地执行 `apply_nginx`，并通过 HTTP API 将配置推送至目标 Agent 的 `/api/sites`，由 Agent 自动写入 Nginx 并执行 `systemctl reload nginx`。
  - **极速分流价值与硬件带宽陷阱**：
    - 高码率/4K 原画 Emby 分流至亚太节点（30ms 延迟，解除长肥管道 TCP 瓶颈），常规境外 Emby 保留在欧洲节点，实现单面板管理全网多节点加速。
    - **实测带宽陷阱**：香港等亚太小鸡虽然延迟极低（20ms），但部分商家存在严格的**小带宽限速（如 18~20Mbps）**，播放 4K 原盘大片（码率 20~50Mbps）仍会打满卡顿；而欧洲/荷兰千兆大水管小鸡虽然延迟高（280ms），但大带宽吞吐更足。**最佳高码率方案是采用高带宽亚太优化机（如台湾 200M+ 节点）或在客户端主动调降码率至 1080P**。
  - **AWS 中央主控架构与零流量损耗原理 (控制流与数据流彻底解耦)**：
    - 将 Master 总控面板部署在 AWS 或独立稳定云主机上（如挂载在已放行的 3000 端口），仅作为管理与规则分发入口（控制流，单次同步仅数 KB 纯文本）。
    - 客户端播放视频时直接与各个执行小鸡（台湾、香港、荷兰）直连传输海量视频切片（数据流，数十 GB），**完全不经过 AWS 主机，实现中央主控 0 业务流量消耗**。
  - **NAT VPS 端口转发映射机制 (Shlii 等平台实战)**：
    - LXC 容器展示的“SSH 端口：22”仅为内部监听端口，外部必须通过母机分配的公网 NAT 映射端口（如 58085）连接，否则会报 `Permission denied`。
    - 新增 Emby 反代端口时，内部端口填写 18096，公网端口建议留空让平台随机分配高位端口（如 29759），避免端口冲突。
  - **前端多节点渲染与 IP 绑定健壮性**：
    - 前端在根据站点所选节点（`s.node`）渲染客户端连接地址时，必须在 `NODE_IPS` / `NODE_INFO` 字典中完整注册所有纳管小鸡的公网映射 IP 与端口，避免因字典缺失回退至默认节点 IP 导致界面地址未更新。
  - **开源交付与隐私脱敏铁律**：
- **Nginx 调优关键指令**：
  1. **独立视频流大缓冲区**：对 `(videos|audio|sync|Videos/.+/stream)` 开启 `proxy_buffering on; proxy_buffer_size 512k; proxy_buffers 16 1m; proxy_max_temp_file_size 0;`，内存流水线推流，避免小磁盘频繁换页。
  2. **系统资源解除上限**：设置 `worker_rlimit_nofile 65535; worker_connections 8192;`，并在 `/etc/security/limits.d/` 调大 `nofile`。
  3. **静态资源边缘缓存**：使用 `proxy_cache_path` 为图片、海报、封面分配 200~300MB 磁盘缓存（`inactive=7d`），减轻频繁拉取元数据的网络开销。
  4. **长连接与套接字优化**：开启 `tcp_nodelay on; tcp_nopush on; keepalive_timeout 300s; keepalive_requests 100000;`。
### ⑪ 固定客户端地址与动态后端热切换架构 (Dynamic Upstream & DNS 智能调度)
- **业务痛点**：若客户端直接使用小鸡 IP+端口，一旦切换服务器（如从荷兰切到台湾/香港），全家所有手机/电视设备都必须手动修改服务器地址并重新登录，体验极繁琐。
- **解法一：统一固定接入网关 + 多站点精准分流 (最推荐 👑)**：
  1. **固定接入网关 (Fixed Gateway Endpoint)**：全家客户端永久固定填写同一套地址（如 `http://45.207.153.154:29759/子路径/` 或固定二级域名），**终身不换**。
  2. **单站点独立选择出海节点 (Per-Site Upstream Routing)**：
     - 在控制台为每个 Emby 站点单独设置 `upstream_node`（例如：【稳健】选台湾 215M 本地极速看 4K，【终点站】选荷兰千兆大水管，其他服选香港 20ms）。
     - 网关 Nginx 内部根据子路径（`/wj/`、`/zdz/`）将流量分别反代至真实源站或对应的小鸡代理端口，实现**“线路永远不变，不同服务器自由选择不同出海节点”**。
     - 切换出海节点仅需在面板点击并触发网关 `nginx -s reload`，毫秒级热重载，客户端 0 感知、无需更改任何配置。
- **解法二：自定义二级域名 + Cloudflare API 动态热切换**：
  1. 为 Emby 反代分配固定的专用二级域名（如 `ruxi666.ccwu.cc`）。
  2. 客户端永久填写：`http://ruxi666.ccwu.cc:端口/路径/`。
  3. 面板内集成 Cloudflare API Token（`Zone - DNS - Edit` 权限），点击节点时后台通过 `PATCH /dns_records/{id}` 自动更新 A 记录 IP（关闭小云朵保留 DNS 直连），实现全球客户端无感漂移。
- **与已在运行节点的二级域名前缀隔离**：
  - 切勿将正在运行订阅/Worker 的现有二级域名（如 `ruxi20260516.ccwu.cc`）直接改 A 记录指向小鸡，否则会导致原订阅中心瞬间失效；必须为 Emby 反代派生全新的独立前缀（如 `ruxi666.ccwu.cc` 或 `emby.ccwu.cc`）。

### ⑫ 多节点出海节点最优匹配实测 (同一套架构，节点配错速度天壤之别)
- **黄金铁律：源站机房物理位置决定最优出海节点，不能靠直觉猜**：
  - 任何一台 Emby 公益服，其视频文件可能存放在欧洲、北美或亚洲，必须实测各个小鸡到源站的延迟再决定。
  - **实战测速方法**（在每台小鸡上执行）：
    ```bash
    curl -4 -s -o /dev/null -w 'connect: %{time_connect}s total: %{time_total}s\n' https://源站域名/emby/system/info/public
    ```
### ⑫ 三节点 × 两源站实测对比（参考基准）**：

  | 节点 | → 欧洲存储源站 (如稳健 m.wenjian.de) | → 欧洲 CDN 源站 (如终点站 c.emby.wtf) |
  |---|---|---|
  | 🇹🇼 台湾 (34ms) | 连接 5ms, 总 **224ms** (IPv6路由更快) | 连接 30ms, 总 **248ms ✅** |
  | 🇳🇱 荷兰 (千兆) | 连接 54ms, 总 **143ms ✅ 最快!** | 连接 295ms, 总 **1114ms ❌ 极慢** |
  | 🇭🇰 香港 (20ms) | 连接 13ms, 总 **612ms ❌ 慢** | 连接 182ms, 总 **419ms** |

  **最优分配规则（稳定节约规律）**：
  - 欧洲存储源站（如 m.wenjian.de）→ 荷兰千兆最快（同洲物理就近）
  - CF CDN 全球加速源站（如 c.emby.wtf）→ 台湾最快（亚洲 CDN 命中率高）
  - **节点配反时速度差高达 6 倍以上**，必须依实测数据配，不能靠直觉猜！

- **结论**：稳健（欧洲存储）最优走荷兰；终点站（CF CDN）最优走台湾。节点配反速度差6倍以上，必须依据实测数据配置！
- **NAT 小鸡 Nginx 缓冲区与内存规格匹配**：
  - LXC 容器内存极小（128MB 量级）时，`proxy_buffers 16 1m`（=16MB）占总内存 12%，高负载下可能触发 OOM Kill；
  - **小内存机器推荐**：`proxy_buffers 4 256k; proxy_buffer_size 64k; proxy_busy_buffers_size 512k;`
  - **大内存机器（512MB+）**：沿用 `proxy_buffers 16 1m; proxy_buffer_size 512k;`

### ⑫ 关键避坑与起播/连接性能调优 (终点站403与起播慢实战)
- **终点站等源站地区风控阻断 (403 Forbidden)**：
  - 部分 Emby 公益源站（如 `c.emby.wtf`）针对亚洲/香港/台湾部分数据中心 IP 实施了严格的 IP 属地防火墙风控，直连或反代会返回 `403 Forbidden`。
  - **排查与解决**：在多节点反代架构中，必须将风控严格的站点出海节点精准指派给欧洲原生/千兆小鸡（如荷兰 `199.47.241.137`）出海，即可稳定返回 `200 OK` 并恢复连接。
- **起播慢与首屏卡顿核心诱因（DNS 与 IPv6 握手超时）**：
  - 台湾/香港等 VPS 的系统默认 DNS 常常优先解析出 Cloudflare 的 IPv6 地址并尝试握手，当 IPv6 路由不畅时会经历 3~5 秒的握手超时重试后才回退至 IPv4，导致客户端起播严重卡顿。
  - **解决方案（Nginx 强制 IPv4 极速解析）**：在 Nginx 反代配置的 `server` 块中加入：
    ```nginx
    resolver 1.1.1.1 8.8.8.8 valid=300s ipv6=off;
    resolver_timeout 3s;
    ```
    强制关闭 IPv6 解析并缓存 DNS，结合 TCP Fast Open 和 Keepalive 长连接，彻底消除起播等待时间。
- **Nginx 正则 location 中 proxy_pass 带 URI 语法报错**：
  - 在 `location ~* ^/prefix/...` 正则匹配块中，`proxy_pass` 末尾绝对不能携带 URI 路径（如 `proxy_pass http://IP:PORT/path;` 会触发 `[emerg] "proxy_pass" cannot have URI part in location given by regular expression` 导致 Nginx 重载失败）；必须使用纯 `proxy_pass http://IP:PORT;` 或在 `location ^~ /prefix/` 前缀匹配块中携带 URI。

### ⑬ 4K 高码率流媒体吞吐调优与测速实战 (内核+Nginx+播放器三维优化)
- **千兆小鸡速度只有“十几兆”的认知误区与排查**：
  1. **单位混淆 (MB/s vs Mbps)**：播放器上显示的 `10MB/s` 对应的是 `80Mbps` 网络带宽，已完全能满足常规 4K（20~60Mbps）流畅播放；若显示 `10Mbps`，主要是播放器按片拉流（预充缓存后主动休眠），瞬时速度不代表链路带宽上限。
  2. **源站单线程限速与晚高峰运营商 QoS**：Emby 公益/商业服上游 CDN 普遍开启单线程限速（20~50Mbps）；跨海国际出口在晚高峰可能受运营商 QoS 限速。
- **Linux 内核网络栈参数解锁 (TCP 64MB 滑动窗口与 BBR)**：
  ```bash
  # 开启 BBR 拥塞控制并放宽 TCP 窗口（解除跨海长肥管道的长距离 RTT 吞吐压制）
  net.ipv4.tcp_congestion_control = bbr
  net.ipv4.tcp_rmem = 4096 1048576 67108864
  net.ipv4.tcp_wmem = 4096 1048576 67108864
  net.ipv4.tcp_fastopen = 3
  net.ipv4.tcp_tw_reuse = 1
  ```
- **Nginx 4K 视频流缓冲策略避坑 (proxy_buffering off vs on 的重大陷阱)**：
  - **严重陷阱**：在反向代理分片视频流时，若无节制地全局关闭 `proxy_buffering`（`proxy_buffering off;`），会导致像 Hills、VidHub 这类按 Range 字节分片发包的移动端播放器**失去 Nginx 的多级分段预读管道**，引发播放器单字节阻塞，导致起播严重卡死、速度直接跌至几 KB/s！
  - **黄金标准配置**：流媒体分片反代必须保持 `proxy_buffering on;` 并配合合理的内存分段池（如 `proxy_buffers 16 1m; proxy_buffer_size 512k;`），严禁盲目粗暴关闭 buffering！
- **源站真实地理位置与节点匹配铁律 (为什么亚洲机下不动欧洲源站)**：
  - **实战案例**：如“稳健”等服其视频文件实际存放在欧洲源站。若误用台湾/香港等亚洲节点去拉流，需跨越大半个地球，单切片下载耗时高达 4.8~5.7 秒（速度仅 1~2 MB/s），导致移动端频繁超时无法起播；而改用荷兰千兆小鸡拉同一切片仅需 0.84 秒（速度 12.5 MB/s，提升 6 倍以上！）。
  - **智能调度原则**：多节点反代系统中，必须根据源站机房真实归属地分配同洲/近距离小鸡进行出海拉流，不可盲目迷信所有站点都一刀切走亚太小鸡。
- **播放器端设置 (VidHub / Hills / SenPlayer / Infuse)**：
  - 将播放器的“缓存大小 / 缓冲区 (Buffer Size)”从“自动”改为**“极大”或“500MB”**，强迫播放器在起播第 1 秒利用大 TCP 窗口激进预吞数据，提升秒开与拖拽体验。
- **协议选型权衡（HTTP vs HTTPS）**：
  - **HTTP**：起播最快、无 TLS 握手开销（少 1~2 个 RTT 往返），无证书过期维护烦恼，最适合纯 TV 盒子与本地播放器。
  - **HTTPS**：防止部分国内省份宽带运营商进行明文流量嗅探劫持或限速，满足特定平台（iOS ATS / 浏览器 PWA）的强制加密安全要求。

### ⑭ AWS EC2 安全组入站端口带实际监听状态排查 (将面板挂载到已放行端口)
- **场景**：将 AWS 主控面板挂载到 EC2 实例时，需先确认安全组已放行端口中哪些活跃、哪些空闲（避免新建放行规则）。
- **快速排查指令**：
  ```bash
  # 检查实际在监听的服务（与安全组对照）
  ss -lntp | awk '{print $4}' | grep -oP ':\\K\\d+' | sort -n | uniq
  ```
- **典型 AWS 端口状态分类（当前实例基准）**：

  | 端口 | 协议 | 实际状态 | 对应服务 |
  |---|---|---|---|
  | 22 | TCP | 🟢 在用 | SSH 远程管理 |
  | 8648 | TCP | 🟢 在用 | Hermes Web UI 面板 |
  | 8317 | TCP | 🟢 在用 | CLI Proxy API |
  | 35087 | TCP | 🟢 在用 | SOCKS5 代理服务 |
  | 3000 | TCP | ⚪ 空闲 | 适合挂载新面板 |
  | 80/443/2082 | TCP | ⚪ 空闲 | 备用 |

- **择不新建安全组规则、直接复用空闲端口的原则**：\n  - 想展开新项目时，优先检查安全组已放行中有哪些端口实际是空闲的（`ss -lntp` 无输出），直接占用，不必再叠加安全组放行清单。
- **AWS EC2 + 0 业务流量主控架构经验（控制流与数据流彻底解耦）**：
  - 面板只处理管理指令与配置同步（控制流，单次同步仅 KB 级），视频播放切片流量全部由各小鸡直连处理（数据流）；
  - AWS 主机 **0 字节**视频传输消耗，彻底避免 AWS EC2 按量计费的高带宽费用。

### ⑯ 架构演进与反思：极简主控 vs 过度工程化（杜绝“屎山”与套娃中转）
- **过度工程化惨痛教训（屎山代码与连环事故）**：
  - **跨节点套娃中转陷阱**：在多小鸡架构中，切勿将“固定域名指向的小鸡（如台湾）”当成中转跳板再去反代另一台小鸡（如荷兰），这样不仅导致流量白白多绕一圈地球（延时增加 80ms+，速度直接腰斩），还会在各小鸡之间产生混乱的互相反代死循环。
  - **节点与线路物理分离原则**：线路（Route）是“源站 + 单一最优小鸡直连”的绑定关系。每个小鸡各跑独立的干净 Nginx 直连上游；主控面板仅做统一的配置存储与 SSH 推送，绝不搞跨机级联中转。
  - **端口与小鸡绑定认知**：客户端填写的访问端口直接对应物理小鸡的入口端口（如台湾为 `29759`，荷兰为 `35087`）；在单域名场景下，通过**不同端口天然路由到不同物理机器**，实现各自直连、0 额外延迟。
- **架构极简主义标准（重构推倒准则）**：
  1. **主控面板职责单一**：仅维护 `sites.json` 纯数据，下发 Nginx 模板，不搞花哨的动态多层反向代理。
  2. **小鸡配置干净无状态**：每台小鸡仅保留一个统一的 `emby.conf`，主控推送时直接全量覆盖并 `nginx -t && systemctl reload nginx`，杜绝历史残留配置堆叠。
  3. **精简节点集群**：不需要的节点（如小带宽/非必要香港机）坚决下线拔除，收敛至最核心的双节点（如亚太 4K 极速台湾 + 欧洲千兆荷兰），运维成本和排查复杂度直接降低 80%。

### ⑰ Emby 302 外部媒体重定向与流中断避坑 (unexpected end of stream 实战)
- **业务场景与报错特征**：
  - 类似“非越”等部分 Emby 公益/商业服，媒体文件不存放在主服务器，而是通过 302 重定向至独立媒体 CDN（如 `media.emby.pro`）。
  - 客户端（如 Hills / VidHub）播放或拖拽进度条时，弹错：`unexpected end of stream on http://...` 并中断播放。
- **根本原因**：
  - 默认的反代通用 location 缺少针对流媒体分片传输的长超时与专用缓冲池配置；遇到 30Mbps+ 高码率视频或 302 直链跟随拉取时，由于默认超时时间过短或连接被过早切断，导致播放器接收到不完整的分段数据流。
- **黄金标准 Nginx 视频专用 location 配置**：
  ```nginx
  location ~* ^/{prefix}/(emby/)?(videos|audio|sync|Items/.+/Download|Videos/.+/stream) {
      proxy_pass {target};
      proxy_set_header Host {parsed.netloc};
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Range $http_range;
      proxy_set_header If-Range $http_if_range;
      proxy_http_version 1.1;
      proxy_set_header Connection '';
      proxy_ssl_server_name on;
      proxy_ssl_name {host};
      proxy_ssl_protocols TLSv1.2 TLSv1.3;
      proxy_redirect off;
      proxy_buffering on;
      proxy_buffer_size 128k;
      proxy_buffers 4 256k;
      proxy_busy_buffers_size 512k;
      proxy_temp_file_write_size 512k;
      proxy_max_temp_file_size 0;
      proxy_read_timeout 7200s;
      proxy_send_timeout 7200s;
  }
  ```
  - **关键点解析**：
    - `proxy_buffering on;` + 适配小内存的紧凑缓冲池（128k / 4*256k），确保按 Range 请求的播放器能获得持续预充，杜绝几 KB 限速与空流。
    - `proxy_read_timeout 7200s;` 延长长视频流拉取超时。
    - `proxy_redirect off;` 允许 302 重定向头正常透传回客户端跟随。

### ⑲ Emby 302 网盘直链服国内卡顿终极解法：Nginx 自动拦截截胡中转 (@relay_302)
- **业务痛点**：
  - 许多 Emby 公益服/挂载服（如“非越”）采用 302 网盘架构，Emby 只提供目录，播放时通过 `302 Found` 将客户端重定向到外部 Cloudflare 网盘（如 `media.emby.pro`）。
  - 普通反代直接将 302 抛回给手机，手机必须跨海直连 Cloudflare 公共免费节点（`104.21.x.x`），被国内宽带（电信/联通）严重限速 QoS（仅 1~2MB/s）。若遇到 30Mbps+ 高码率视频，即使搭建了反代也“毫无用处”，依然疯狂转圈卡顿。
- **核心解决方案（Nginx 302 截胡中转黑科技）**：
  - 在加速小鸡（如拥有 215Mbps 狂暴大水管且直连 Cloudflare 仅 2~3ms 的台湾小鸡）的 Nginx 视频流 location 中，开启 `proxy_intercept_errors on;`，截获上游的 301/302/307 重定向状态码；
  - 重定向不返回给手机客户端，而是由小鸡内部命名的 `@relay_302` location 提取 `$upstream_http_location`，由小鸡亲自代拉网盘切片，再通过 215Mbps 高速管道直接喂饱手机！
- **生产验证标准 Nginx 配置**：
  ```nginx
  location ~* ^/{prefix}/(emby/)?(videos|audio|sync|Items/.+/Download|Videos/.+/stream) {
      proxy_pass {target};
      proxy_set_header Host {parsed.netloc};
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Range $http_range;
      proxy_set_header If-Range $http_if_range;
      proxy_http_version 1.1;
      proxy_set_header Connection '';
      proxy_ssl_server_name on;
      proxy_ssl_name {host};
      proxy_ssl_protocols TLSv1.2 TLSv1.3;
      proxy_buffering on;
      proxy_buffer_size 128k;
      proxy_buffers 4 256k;
      proxy_busy_buffers_size 512k;
      proxy_temp_file_write_size 512k;
      proxy_max_temp_file_size 0;
      proxy_read_timeout 7200s;
      proxy_send_timeout 7200s;

      # 核心拦截：截获源站 301/302/307 重定向，小鸡亲自代拉网盘数据
      proxy_intercept_errors on;
      error_page 301 302 307 = @relay_302_{prefix};
  }

  location @relay_302_{prefix} {
      set $redirect_url $upstream_http_location;
      proxy_pass $redirect_url;
      proxy_set_header Host $proxy_host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Range $http_range;
      proxy_set_header If-Range $http_if_range;
      proxy_http_version 1.1;
      proxy_set_header Connection '';
      proxy_ssl_server_name on;
      proxy_ssl_protocols TLSv1.2 TLSv1.3;
      proxy_buffering on;
      proxy_buffer_size 128k;
      proxy_buffers 4 256k;
      proxy_busy_buffers_size 512k;
      proxy_temp_file_write_size 512k;
      proxy_max_temp_file_size 0;
      proxy_read_timeout 7200s;
      proxy_send_timeout 7200s;
  }
  ```
- **实际收益**：
  - 彻底将“看似无用的 302 摆设反代”转变为“满速代理通道”；
  - 手机端 0 感知、无需在播放器开启复杂的“忽略 302/强制中转”开关，所有 302 网盘服全部自动吃到小鸡的大带宽加速！

### ㉑ 多小鸡反代域名分配与串台避坑：单域名跨机器冲突 vs 独立专线二级域名
- **“套了域名反而不如不套”的根本原因（单域名共享端口冲突）**：
  - **故障现象**：配置了全局统一域名（如 `ruxi666.ccwu.cc`），DNS 解析至小鸡 A（如台湾 `45.207.153.154`）；当用户访问分配给小鸡 B（如荷兰 `199.47.241.137:35087`）的站点时，生成的客户端地址成了 `http://ruxi666.ccwu.cc:35087/path/`。
  - **底层灾难**：手机发起 DNS 解析得到的是小鸡 A 的 IP，带着小鸡 B 的专属映射端口（`35087`）去连接小鸡 A；小鸡 A 根本没有监听该端口，导致客户端陷入反复 TCP 握手超时、起播卡死几十秒甚至报 Connection Refused。
  - **对比直接填 IP**：直接填各自机器的公网 IP 反而直截了当、绝不串台，且省去 DNS 查询耗时。
- **最佳生产解法（独立二级专线域名隔离）**：
  - 为不同物理小鸡分配明确归属的二级专线域名（通过 Cloudflare DNS 解析，关闭小云朵仅保留 DNS）：
    - 🇹🇼 台湾专线：`tw.ruxi666.ccwu.cc` ➔ 对应台湾真实 IP + 端口（如 `29759`）
    - 🇳🇱 荷兰专线：`nl.ruxi666.ccwu.cc` ➔ 对应荷兰真实 IP + 端口（如 `35087`）
  - **收益**：既保留了“全家设备永久固定域名、换机无需改配置”的优雅体验，又在物理层面彻底杜绝了跨机端口串台与超时报错，达到与直填 IP 相同的极速直达效果。
- **HTTP 环境移动端剪贴板静默失败 (Navigator.clipboard 坑)**：
  - 现代手机浏览器（Chrome / Safari）在非安全上下文（未开启 HTTPS 的 HTTP 网页，如 `http://IP:3000`）下，出于安全沙箱限制会**静默禁用 `navigator.clipboard` API**，导致用户在手机上点击“复制”没有任何反应。
  - **全平台兼容降级复制函数（必须内置）**：
    ```javascript
    function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('📋 地址已复制到剪贴板！');
            }).catch(() => fallbackCopy(text));
        } else {
            fallbackCopy(text);
        }
    }
    function fallbackCopy(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            const successful = document.execCommand('copy');
            showToast(successful ? '📋 地址已复制到剪贴板！' : '复制失败，请手动长按复制');
        } catch (err) {
            showToast('复制失败，请手动长按复制');
        }
        document.body.removeChild(textArea);
    }
    ```
- **服务端直出 (SSR) 杜绝跨海 fetch 首屏白屏转圈**：
  - 管理面板若依赖前端打开后 `fetch('/api/sites')` 异步加载，跨海延迟高时手机端会长时间停留在骨架/空白页。
  - **准则**：Python 原生后端在返回 `index.html` 时直接在模板层完成 HTML 拼接输出（SSR 0ms 首屏），仅在用户主动点击“保存 / 删除 / 热重载”等交互动作时才发起异步 API 请求。
### ㉒ 源站自身故障（502 Bad Gateway / 404）与节点“背锅”快速诊断法
- **典型误判场景**：
  - 用户反馈反代小鸡“突然没速度”、“起播卡死半天”、“速度极不稳定”，直觉往往怀疑是小鸡网络挂了、Nginx 配置被改崩了，或者域名套错了。
- **排查黄金法则（优先直测源站健康度）**：
  - 在大动干戈排查反代小鸡或重写配置前，**第一件事必须用 curl 多地直连 Emby 官方源站**：
    ```bash
    curl -I -s https://源站域名/web/index.html | head -10
    curl -I -s https://源站域名/emby/system/info/public | head -10
    ```
  - 若源站直接返回 `HTTP/2 502 Bad Gateway`、`504 Gateway Time-out` 或 `404 Not Found`，说明是源站自身服务器正在崩溃、重启或维护！
  - **现象对照**：此时客户端虽然连着反代小鸡，但由于反代在持续等待已宕机源站的响应，播放器必然卡在首帧转圈，此情况与反代节点配置毫无关系，切勿盲目推倒重构正常工作的代理小鸡。

### ㉓ 双线路同步全量并发架构与智能感知推荐机制 (免换地址与自由测速)
- **业务痛点**：
  - 单线路指派模式下，用户若想切线路必须到后台编辑修改并重新复制地址，客户端无法同时测速；且用户无法直观得知该源站究竟走哪个节点更快。
- **双线路全量并发架构 (Dual-Route Synchronous)**：
  1. **配置全量下发**：每个 Emby 站点添加后，主控系统同时在所有纳管节点（如台湾专线 + 荷兰专线）上同步部署相同子路径规则并重载。
  2. **双地址并行输出**：管理面板卡片同时展示两个节点的专属直连地址（各带独立一键复制按钮），客户端（如 Hills / VidHub）可同时保存两条线路（如“站点-台湾”与“站点-荷兰”），想测哪个点哪个、哪条快看哪条。
### ㉔ 移动端保存阻塞与异步并发下发 (Failed to fetch 终极避坑)
- **故障现象**：
  - 手机移动端在面板点击“保存并全量部署”时，长时间卡在“部署中...”，随后弹窗报错：`网络请求失败: Failed to fetch`。
- **根本原因**：
  - 同步阻塞架构缺陷：后端在收到 HTTP POST `/api/sites/save` 请求后，在同一请求线程中依次对所有远程小鸡发起 SSH 连接、写入配置、执行 `nginx -t` 和 `reload`；
  - 跨国两台小鸡（台湾 + 荷兰）的连续 SSH 执行总耗时常达 3~5 秒以上；
  - 手机端移动浏览器（Safari / Chrome）对长时间挂起的 POST 连接有极严格的保活与节能策略，超过几秒即主动切断 TCP Socket，抛出前端 `Failed to fetch` 异常。
- **黄金标准架构改造（异步并发下发）**：
  1. **主控毫秒级响应**：后端接收到 sites 配置并写入本地 `sites.json` 磁盘后，**在 0.001 秒内立即向前端返回 `HTTP 200 OK`**；
  2. **后台多线程并发分发**：调用 `threading.Thread(target=push_to_node, ...).start()` 在独立后台守护线程中同时向台湾和荷兰小鸡并发推送，前端零等待、零卡顿；
  3. **完整 CORS 响应**：后端必须在每个响应头输出 `Access-Control-Allow-Origin: *`、`Access-Control-Allow-Methods: GET, POST, OPTIONS`，并在 `do_OPTIONS` 响应 204，杜绝任何移动端跨域拦截。

### ㉖ Emby 嵌套子路径视频流解析失败与 Exo 播放器报错排查 (Path 重复拼接与 Nginx 优先级坑)
- **报错特征与故障现象**：
  - 手机 Hills / VidHub 播放器连接反代小鸡后，点开视频弹窗报错：`Exo播放器不支持此格式视频，切换至mpv播放器进行播放`，切换后仍转圈卡死或提示网络错误；而在 Cloudflare Worker 反代上却正常。
- **根本原因与排查**：
  1. **嵌套子路径源站的重复前缀陷阱**：
     - 部分特殊 Emby 源站（如“飞了个喵” `gy.meowfly.de`）其原站视频请求路径本身嵌入了子路径（如 `/emby/flgm/Videos/...`）；
     - 客户端通过反代（`/flgm/`）连接时，播放器发出的真实请求会叠加上自身的前缀，变成：`/flgm//emby/flgm/Videos/...`（出现双层重复前缀）；
     - 若反代未对重复前缀做清洗，原样请求源站，源站找不到资源返回 `12 字节的空 JSON {}`（HTTP 200）；
     - Exo 播放器读取这 12 字节的空数据流无法识别多媒体容器，误以为是未知损坏格式而弹窗崩溃。
  2. **Nginx `^~` 修饰符阻塞正则的致命语法陷阱**：
     - 在 Nginx 中，前缀匹配 `location ^~ /prefix/` 的优先级高于所有正则表达式 `location ~*`；
     - 若配置了 `location ^~ /prefix/`，其下方的所有正则清洗规则（包括 `videos`、`rewrite`、`302 relay`）将被 Nginx **全量无视跳过**！
- **标准解决方案（Nginx 正则清洗 + location 优先级修正）**：
  1. **将基础前缀改为普通匹配**：使用 `location /prefix/` 替代 `location ^~ /prefix/`，确保下方正则能被正常执行；
  2. **使用 `rewrite ... break` 剥离重复路径**：
     ```nginx
     # 匹配并剥离重复嵌套的 /flgm/ 前缀
     location ~* ^/{prefix}/+(emby/)?{prefix}/(videos|Videos)/(.+)$ {
         rewrite ^/{prefix}/+(emby/)?{prefix}/(videos|Videos)/(.*)$ /Videos/$3 break;
         proxy_pass {target};
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
         proxy_read_timeout 7200s;
         proxy_send_timeout 7200s;
     }
     ```
  3. **实测收益**：请求 `/flgm//emby/flgm/Videos/...` 瞬间被重写为源站标准的 `/Videos/...`，5GB+ 蓝光原盘流瞬间毫秒级吐出，彻底解决 Exo 报错。

### ㉗ 欧洲大带宽小鸡跨海单线程 4.5MB/s 限制与 8MB 内存并发切片缓冲调优
- **故障现象与误区**：
  - 荷兰等欧洲原生/千兆大水管小鸡（`199.47.241.137`）直连欧洲源站拉流高达 40MB/s+，但国内手机端拉流最高却只有 4.5MB/s，无法跑满带宽。
- **根本原因**：
  - 跨海高延迟（欧洲至国内 RTT 约 180ms）长肥管道（BDP）物理限制：在长距离下若关闭缓冲（`proxy_buffering off`），单个 TCP 窗口来回等待 ACK 确认，物理吞吐会被死死锁在 3~5MB/s。
- **解决方案（为欧洲 512MB 内存小鸡开启 8MB 内存并发切片缓冲）**：
  ```nginx
  proxy_buffering on;
  proxy_buffer_size 256k;
  proxy_buffers 32 256k;  # 8MB 内存级并发缓冲池
  proxy_busy_buffers_size 2m;
  proxy_temp_file_write_size 2m;
  proxy_max_temp_file_size 0;
  ```
  - 实测收益：单切片下载速度直接从 4.5MB/s 突破至 7.1MB/s+（57Mbps 真实带宽），4K HDR 秒开秒拖拽。

### ㉘ 6 大真实 Emby 公益源站物理归属与节点最优匹配速查表
- 基于全链路多地实测与风控规则固化的黄金基准：
  1. **飞了个喵 (`gy.meowfly.de`)**：欧洲德国机房，走**荷兰专线 (45ms)** 极速秒开；
  2. **终点站 (`c.emby.wtf`)**：亚洲 IP 有严格 403 拦截，必须走**荷兰专线**绕过封锁；
  3. **稳健 (`m.wenjian.de`)**：欧洲机房本土源站，走**荷兰专线 (185ms)** 相比台湾跨洲快 6 倍；
  4. **msky (`wcf.3msky.com`)**：欧洲本土平稳，走**荷兰专线 (572ms)** 优于台湾；
  5. **非越 (`cf.sfcj.org`)**：亚太 CDN 节点，走**台湾专线 (34ms / 215M)** 4K 极速；但注意其 302 网盘源 `media.emby.pro` 对亚洲有黑洞限速，若 302 未被小鸡截胡代拉，播放大码率需切至荷兰；
  6. **拾光 (`ey.lightting.net`)**：亚太边缘节点，走**台湾专线 (34ms)** 极速握手。

### ㉚ 跨洲与亚太反代节点 Nginx 缓冲池精算调优：16MB 黄金极限池 vs 4MB 轻量防爆池
- **核心认知误区：缓冲池绝非越大越好！**
  - **盲目调大的严重负效应**：
    1. **起播首帧延迟变长**：Nginx 倾向于在内存中填满超大 buffer 才向客户端整块下发，导致播放器按播放后多等数秒；
    2. **拖动进度条卡死**：快进/快退时已缓冲在巨型内存池中的数据全部作废丢弃，Nginx 重新建连缓冲引发剧烈转圈；
    3. **小内存 VPS 触发 OOM 崩溃**：多客户端或多请求并发时，超大缓冲池会瞬间耗尽机器内存，被 Linux OOM Killer 强杀 Nginx 进程。
- **双规格精准精算矩阵（依据内存与物理延迟 RTT 分配）**：
  1. **欧洲大带宽节点（如 512MB 内存 / 190ms 跨洲长肥管道，荷兰小鸡）**：
     - **16MB 黄金极限并发缓冲池**：
       ```nginx
       proxy_buffering on;
       proxy_buffer_size 256k;
       proxy_buffers 16 1m;            # 16MB 内存预吞吐池
       proxy_busy_buffers_size 2m;     # 2MB 极速发送窗口
       proxy_temp_file_write_size 2m;
       proxy_max_temp_file_size 0;
       ```
     - **效果**：解决长距离跨海单 TCP 连接速度被限制在 4.5MB/s 的物理瓶颈，实测拉升至 7~12MB/s（60~100Mbps），看 4K 原盘稳定流畅。
  2. **亚太小内存节点（如 125MB 内存 LXC / 34ms 超低延迟，台湾小鸡）**：
     - **4MB 轻量极速防爆池**：
       ```nginx
       proxy_buffering on;
       proxy_buffer_size 256k;
       proxy_buffers 8 512k;           # 4MB 紧凑缓冲池，仅占可用内存约 4.5%
       proxy_busy_buffers_size 1m;     # 1MB 瞬间推流窗口
       proxy_temp_file_write_size 512k;
       proxy_max_temp_file_size 0;
       ```
     - **效果**：超低延迟下无需过大 TCP 窗口，4MB 既能保证按 Range 分段请求的播放器获得连贯喂养，又 100% 杜绝 125MB 极小内存容器发生 OOM 崩溃。

### ㉛ 7 步落地法深度融合实战：Host 透传动态化与长视频会话保持
- **`proxy_set_header Host $proxy_host;` 的决定性优势**：
  - 传统手动配置容易将 Host 写死为固定域名；当上游源站涉及多级重定向、动态 CDN 或带非标准端口时，写死 Host 极易引发源站 403 阻断或 Host 不匹配；
  - 严格采用 `$proxy_host` 动态继承 `proxy_pass` 指向的 Host 与端口，具备最强通用性与防封锁能力。
- **全量注入 WebSocket 保持与超长拉流保活**：
  - 配置 `proxy_set_header Upgrade $http_upgrade;` 与 `proxy_set_header Connection "upgrade";` 确保 Emby 弹幕、多端播放进度同步 WebSocket 绝不断线；
  - 设置 `proxy_connect_timeout 15s;`（极速熔断死机源站，杜绝无限转圈）与 `proxy_send/read_timeout 3600s;`（保障 2~3 小时超长 4K 电影暂停不掉线）。

### ㉜ Go 语言单二进制反代系统架构 (EmbyProxy - hkfires 模式)
- **项目定位与特征**：
  - 基于 Go 语言编写的单文件轻量 Emby 反代管理系统（如 `https://github.com/hkfires/EmbyProxy`，前身为 `chenhr454/emby---worker`）；
  - 单一二进制程序自带 Web UI（默认监听 `8787`，后台 `/admin`，使用 `ADMIN_TOKEN` 鉴权与 TOTP 2FA），SQLite (`proxy.db`) 存储配置与播放统计；
  - 核心特色：多服务器反代管理、客户端身份伪装、Telegram 定期保号通知、前端一键调起各平台播放器（`Sen`、`Capy`、`Epx`、`Hills(Win)`、`小幻(Win)`、`Forward`）。
- **与 Nginx 架构的核心区别**：
  - Go 原生网络栈代理，无需额外配置 Nginx 或 Python 后端；
  - 适合希望一键运行、开箱即用并自带保号提醒的单机 Docker / VPS 场景。

### ㉝ Cloudflare Worker + D1 数据库原版反代架构 (chenhr454/emby---worker 极速落地)
- **项目定位与架构核心**：
  - 开源地址：`https://github.com/chenhr454/emby---worker`；
  - 纯 Serverless 边缘架构，运行在 Cloudflare Workers 上，零服务器成本，天然具备全球 CDN 与抗封锁能力；
  - 存储后端：使用 Cloudflare 原生 D1 SQL 数据库（代替传统 KV），通过 `proxy_kv` 表持久化存储全部节点数据。
- **标准化 3 步落地流水线**：
  1. **创建并初始化 D1 数据库**：
     - 在 Cloudflare Dashboard ➔【存储和数据库】➔【D1 SQL】新建名为 `emby-proxy` 的数据库；
     - 在 Console 控制台执行初始化建表 SQL：
       ```sql
       CREATE TABLE IF NOT EXISTS proxy_kv (
         k TEXT PRIMARY KEY,
         v TEXT NOT NULL,
         updated_at INTEGER NOT NULL
       );
       CREATE INDEX IF NOT EXISTS idx_proxy_kv_k ON proxy_kv(k);
       ```
  2. **部署 Worker 代码**：
     - 新建 Worker（如 `emby-proxy`），粘贴 `chenhr454/emby---worker` 官方发布的最新完整 `worker.js` 并保存部署。
  3. **绑定 D1 与鉴权密钥（关键必做）**：
     - 在 Worker 设置 ➔【变量和机密】中添加 `ADMIN_TOKEN`（作为后台访问鉴权口令）；
     - 在【绑定 (Bindings)】中添加 D1 数据库绑定，**变量名务必填写 `DB`**（代码支持 `DB` 或 `D1`），关联第一步创建的 `emby-proxy` 数据库；
     - 点击【保存并部署】。
  4. **访问与使用**：
     - 打开 `https://你的Worker域名/admin`，输入 `ADMIN_TOKEN` 即可登录并使用完整的 Emby 反代管理系统后台；
     - 支持为节点配置自定义路径别名，一键调起 SenPlayer / CapyPlayer / Hills 等第三方播放器。

### ㉟ 7步落地版反代精要比对与生产优化准则
- **核心对齐清单**：
  1. **Host 动态继承**：强制 `proxy_set_header Host $proxy_host;`，严禁写死域名，确保上游带端口/重定向时透传一致。
  2. **协议与升级头**：全量开启 `proxy_http_version 1.1;`、`Upgrade $http_upgrade;`、`Connection "upgrade";` 保障播放器 WebSocket 进度同步与长连接会话不中断。
  3. **超时控制**：严格配置 `proxy_connect_timeout 15s;` 实现源站宕机秒级熔断；配置 `proxy_send_timeout 3600s;`、`proxy_read_timeout 3600s;` 确保高码率 4K 超长电影暂停时不被服务端掐断。
  4. **SSL 规范**：始终保持 `proxy_ssl_server_name on;`，支持 HTTPS/SNI 握手。
- **与单站配置的区别（多站点场景演进）**：
  - 《7步落地版》面向单端口/单站点直推（`location /`）；在多站点子路径管理中，必须将上述标准头注入至每个子路径的反代与视频分块块中，兼顾多站点隔离与 7 步规范标准。

### ㊲ Nginx 反代 HTTPS 源站 SSL 握手失败排查 (SSL alert number 40 / 502 Bad Gateway)
- **故障现象**：
  - 客户端（如 Windows / iOS Hills、VidHub）连接反代小鸡后，提示无法连接服务器或返回 `502 Bad Gateway`；
  - 检查小鸡 Nginx 错误日志（`tail -n 30 /var/log/nginx/error.log`），出现致命报错：
    `SSL_do_handshake() failed (SSL: error:0A000410:SSL routines::ssl/tls alert handshake failure:SSL alert number 40) while SSL handshaking to upstream`
- **根本原因（SNI 扩展缺失）**：
  - 许多 Emby 源站部署在 Cloudflare CDN 或具备多域名 SNI（Server Name Indication）证书的服务器后面；
  - Nginx 作为客户端向上游发起 HTTPS 握手时，若某个 `location` 块中**漏掉了 `proxy_ssl_server_name on;`**，Nginx 就不会在 TLS 客户端 Hello 包中携带目标域名的 SNI 扩展；
  - 源站 Cloudflare 防火墙无法获知反代请求的是哪个虚拟主机，直接向反代小鸡发出 `SSL alert 40 (Handshake Failure)` 并切断连接，Nginx 随即向客户端返回 `502 Bad Gateway`。
- **排查与根治方案**：
  1. **全局在 `server` 块或每个匹配 location 中强制配置**：
     ```nginx
     proxy_ssl_server_name on;
     proxy_ssl_name $proxy_host; # 或指定域名
     proxy_ssl_protocols TLSv1.2 TLSv1.3;
     ```
  2. **避免局部覆盖**：当 Nginx 包含多个正则 location（如 `System/Info/Public`、`Videos/.../stream`）时，确保每个包含 `proxy_pass https://...` 的 location 都完整继承或显式声明了 `proxy_ssl_server_name on;`。

### ㊳ Cloudflare Worker 前端 URL 拼接缺陷与复制末尾斜杠缺失避坑
- **故障现象**：
  - 在 `chenhr454/emby---worker` 等反代管理面板中点击“复制代理地址”，复制出的链接末尾缺少斜杠 `/`（例如：`https://emby.ruxi666.ccwu.cc/flgm`）；
  - 移动端或电脑端播放器（Hills、SenPlayer、VidHub）连接该地址时，在拼接 Emby API 请求路径时出错，导致服务器测速离线或无法起播。
- **源码根因与热修复**：
  - 原版 `worker.js` 前端生成 `normalUrl` 时漏掉了末尾斜杠：
    ```javascript
    // 错误写法
    const normalUrl = location.origin + '/' + encodeURIComponent(n.name);
    // 修复写法（必须强制带末尾 /）
    const normalUrl = location.origin + '/' + encodeURIComponent(n.name) + '/';
    ```
  - 确保复制、卡片展示以及第三方播放器一键唤醒（Sen/Capy/Epx/Hills/Forward）传入的 URL 均带有标准 `/`。

### ㊵ 用户指令铁律：代码必须严格原汁原味对齐《7步落地版》，严禁私自画蛇添足
- **用户核心诉求与纪律红线**：
  - 当用户明确指定“参考/改成《全新VPS_Nginx反代Emby_7步落地版_修订.md》代码”时，**必须 100% 纯粹、严格采用文档中第 4 步给出的标准 Nginx 参数块**：
    ```nginx
    location /prefix/ {
        proxy_pass https://你的Emby地址/;
        proxy_http_version 1.1;

        proxy_set_header Host $proxy_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_ssl_server_name on;

        proxy_connect_timeout 15s;
        proxy_send_timeout 3600s;
        proxy_read_timeout 3600s;

        proxy_buffering off;
    }
    ```
  - **严禁擅自加入复杂的正则切片缓存、自作主张修改 buffering 或引入多层嵌套 rewrite 逻辑**；
  - 无论是单站点直推还是多站点子路径管理，生成的基础代理 location 必须完全平移这套经过官方验证的干净标准参数，保障全平台客户端（Windows/iOS/Android Hills、VidHub、SenPlayer）连接稳定。
  - **全局 SNI 约束**：针对 HTTPS 源站，必须确保每个代理块都拥有 `proxy_ssl_server_name on;`，防止 Cloudflare 防火墙抛出 `SSL alert 40` 导致 502 握手失败。

### ㊶ NAT 小鸡无 IPv6 路由导致 Nginx upstream disabled 偶发断连排查
- **故障现象**：
  - 客户端请求反代时偶发卡顿或报 502/504，查看 Nginx 日志出现：
    `connect() to [2606:4700:...]:443 failed (101: Network is unreachable / 113: No route to host)`
    伴随 `upstream server temporarily disabled while connecting to upstream`。
- **根本原因**：
  - Nginx 在启动/重载时通过系统 libc DNS（`/etc/resolv.conf`）解析源站域名，获取到了 Cloudflare AAAA IPv6 地址；
  - 若 VPS 未分配公网 IPv6 或 IPv6 默认路由不可达，Nginx 轮询到 IPv6 地址发起握手时直接被内核阻断，并将该 upstream 暂时熔断拉黑，导致客户端请求抖动。
- **解决与排查方案**：
  1. **检查 IPv6 路由**：`ip -6 route` 或 `ping6 -c 2 2606:4700::`；
  2. **若小鸡无 IPv6 通道**：在系统级禁用 IPv6 解析优先（如 `/etc/gai.conf` 中开启 `precedence ::ffff:0:0/96 100` 优先 IPv4），或在 Nginx 动静态 upstream 中确保纯 IPv4 解析通道。

### ㊷ “小鸡反代怎么噶了” 快速定界与全链路体检流水线
- **核心原则**：严格区分“小鸡反代服务宕机”与“上游 Emby 源站崩溃/开启 WAF 拦截”。
- **一键全链路诊断脚本**：
  ```python
  import urllib.request, json
  # 遍历 sites.json 同时测试【源站直连】与【各小鸡反代节点】
  # 1. 源站 502 -> 源站后端宕机
  # 2. 源站 520 / 403 -> 源站 CF 5秒盾/人机拦截或地区封锁
  # 3. 源站 200 但小鸡超时/拒绝 -> 小鸡 Nginx/端口/NAT 映射故障
  ```

### ㊴ Cloudflare 免费节点国内单线程限速与优选 IP 提速机制
- **速度慢核心诱因**：
  - Cloudflare 免费分配的 Anycast IP（如 `104.21.x.x` / `172.67.x.x`）在国内晚高峰受运营商 QoS 限速，单线程往往被物理压制在 1~3MB/s；
- **提速手段**：
  1. **播放器端 IP 覆盖 (Override IP)**：在 Hills / VidHub 高级设置中，保持 Host 域名不变，将连接 IP 强制改写为电信/联通实测优质 Anycast IP（如 `162.159.192.1`、`198.41.214.162`、`104.16.160.1`），瞬间突破跨海限速；
  2. **高码率 4K 建议走独立专线 VPS**：对于 30Mbps+ 的大码率 4K 原盘，纯 VPS 直连专线（如台湾 215M/荷兰千兆）比免费 CDN Worker 更加稳定。

- **核心理念**：抛弃过度复杂的嵌套与套娃代理，回归最纯粹、最稳健的标准反代架构。
### ㊱ Cloudflare 5秒盾 / Turnstile 人机验证阻断与测速“离线”排查
- **故障现象与误判**：
  - 在 Cloudflare Worker 反代面板（如 `chenhr454/emby---worker`）中添加新 Emby 节点（如“拾光” `ey.lightting.net`）后，点击“检测”状态指示灯变红显示 **`离线`**，或测速报错无法连接；
  - 用户常误以为是反代配置错误、D1 数据库失效或 Worker 代码有 bug。
- **根本原因（Cloudflare 5秒盾拦截探针）**：
  - 部分 Emby 公益源站近期开启了全站级 **Cloudflare 5秒盾（`cf-mitigated: challenge` / Turnstile 验证码）**；
  - 测速探针由 Worker 发起纯 HTTP 请求，无法执行浏览器 JavaScript 完成人机挑战，源站直接返回 `HTTP 520` 或 `HTTP 403` 拦截挑战页；
  - Worker 判定节点不可达并标记为红灯离线。
- **排查与应对策略**：
  1. **直测源站验证 5秒盾**：
     ```bash
     curl -I -s "https://源站域名/emby/system/info/public" | grep -E 'cf-mitigated|challenge'
     ```
     若返回 `cf-mitigated: challenge`，确认为源站人机盾拦截。
  2. **应对解法**：
     - 开启 5 秒盾的源站，任何纯 Serverless / Worker 反代都会被阻断；
     - 需使用自建 VPS（台湾/荷兰小鸡）运行的 Nginx 直通反代，或等待源站关闭人机验证。
  1. **测试上游连通性**：
     ```bash
     curl -I --connect-timeout 10 https://你的Emby地址
     ```
     必须返回 200/302/401/403 等 HTTP 状态码方可继续；超时或拒绝连接先排查网络。
  2. **安装并启用 Nginx**：
     ```bash
     apt update && apt install -y nginx
     systemctl enable --now nginx
     ```
  3. **标准反代核心模板 (`/etc/nginx/conf.d/emby.conf`)**：
     ```nginx
     server {
         listen 18096;
         server_name _;

         location / {
             proxy_pass https://你的Emby地址;
             proxy_http_version 1.1;

             proxy_set_header Host $proxy_host;
             proxy_set_header X-Real-IP $remote_addr;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
             proxy_set_header X-Forwarded-Proto $scheme;

             proxy_set_header Upgrade $http_upgrade;
             proxy_set_header Connection "upgrade";

             proxy_ssl_server_name on;

             proxy_connect_timeout 15s;
             proxy_send_timeout 3600s;
             proxy_read_timeout 3600s;

             proxy_buffering off;
         }
     }
     ```
  4. **配置语法检查与加载**：
     ```bash
     nginx -t && systemctl reload nginx
     ```
  5. **一键快速验收流水线**：
     ```bash
     nginx -t && systemctl reload nginx && ss -lntp | grep ':18096 ' && curl -I --connect-timeout 10 http://127.0.0.1:18096
     ```
  6. **多 Emby 站点端口扩展规则**：
     - 单一端口映射单一站点：`18096 → 第一个 Emby`，`18097 → 第二个 Emby`，`18098 → 第三个 Emby`...
     - 配置文件物理隔离：`/etc/nginx/conf.d/emby-18096.conf`、`/etc/nginx/conf.d/emby-18097.conf`，避免单站配置错误导致全局重载失败。
  7. **故障三大黄金定位点**：
     - `502 Bad Gateway` ➔ 优先排查 VPS 到源站的单点连通性 (`curl -I`)；
     - 本机可访问但公网打不开 ➔ 排查 UFW、云厂商防火墙及 AWS EC2 Security Group 入站规则；
     - 报错排查 ➔ 严禁全量拉取日志，使用 `tail -n 30 /var/log/nginx/error.log` 精准定位。









