# Cloudflare 订阅聚合系统定向优选与客户端模块识别指南

## 1. 适用场景与系统背景
- **适用系统**：基于 Cloudflare Workers / Pages 搭建的订阅管理与聚合中心（如 Joey Cyberpunk 风格面板、EdgeTunnel 衍生版）。
- **用户痛点**：
  1. 订阅中的优选 IP 缺乏清晰规范的地区与国旗标注，导致 Clash Meta、Sing-box、Loon、Surge 等客户端的订阅转换模块（如 Subconverter 规则组、国家分组规则）无法自动识别国家/地区，无法自动归类到对应策略组。
  2. 泛用型优选 IP 未结合用户真实的省份网络运营商（电信、联通、移动）进行区分，导致出海路由绕路、晚高峰高丢包、高码率视频与日常浏览卡顿。
  3. 订阅更新后部分节点（特别是 Trojan 协议或故障 IP）全部报红色 Timeout 超时，影响客户端测速与自动选择。

## 2. 三网运营商定向路由特性与优选原则
国内三网出海网络骨干与国际链路差异显著，必须针对用户所在省份/城市与主力网络组合进行过滤配置：

| 运营商 | 核心出海骨干网 | 最佳对端节点推荐 | 典型优化网段/节点 |
| :--- | :--- | :--- | :--- |
| **中国电信 (China Telecom)** | 163 骨干 (AS4134) / CN2 (AS4809) | 美西（圣何塞/洛杉矶）、亚太特选优化节点 | `104.16.0.0/12`、`104.17.0.0/12`、`198.41.214.0/24`、`188.114.96.0/24` |
| **中国联通 (China Unicom)** | 169 骨干 (AS4837) / 9929 优质网 | 欧洲（德国法兰克福/英国伦敦）、日本东京、美西 | `104.18.0.0/12`、`104.20.0.0/12`、`172.64.0.0/13`、`190.93.247.0/24` |
| **中国移动 (China Mobile)** | CMI 国际出口 (AS58453) | 香港、新加坡、日本东京优化 IP | `104.21.0.0/16`、`172.67.0.0/16` 等移动直连 BGP |

### 针对性过滤策略：
- 若用户的主力网络为**「电信宽带 + 电信/联通手机卡」**（如江苏常州等华东沿海地区）：
  - 必须在订阅面板中设置 `ispTelecom: yes` 和 `ispUnicom: yes`。
  - **明确关闭 `ispMobile: no`**，彻底剔除移动劣化节点，防止混入导致整体测速与分流延迟波动。
  - 强制开启 `ipv4: yes`，关闭 `ipv6: no`，规避国内运营商晚高峰对 Cloudflare 边缘 IPv6 严重限速及丢包（30%~50%）问题。

## 3. 客户端规则模块对齐的通用节点命名规范
Clash、Sing-box 以及 Subconverter 正则表达式对节点名称的分组识别依赖两类关键标记：**国家/地区 Flag Emoji** 和 **国家中文全称**。

### 规范命名格式：
```text
<Flag Emoji> <国家中文全称> <编号> [<运营商优化标注>]
```

### 推荐标准节点示例列表：
```text
104.16.160.1:443#🇺🇸 美国 01 [电信优化]
104.17.127.110:443#🇺🇸 美国 02 [电信优化]
198.41.214.141:443#🇺🇸 美国 03 [电信优化]
188.114.96.125:443#🇭🇰 香港 01 [电信优化]
104.25.105.1:443#🇸🇬 新加坡 01 [电信优化]
104.18.228.35:443#🇩🇪 德国 01 [联通优化]
104.20.255.53:443#🇬🇧 英国 01 [联通优化]
172.64.156.155:443#🇯🇵 日本 01 [联通优化]
104.16.243.158:443#🇯🇵 日本 02 [联通优化]
190.93.247.169:443#🇸🇬 新加坡 02 [联通优化]
```

### 效果：
- Clash Meta 等分流规则自动精准归入 `🇺🇸 美国节点`、`🇭🇰 香港节点`、`🇯🇵 日本节点`、`🇸🇬 狮城节点`、`🇪🇺 欧洲节点`。
- 手机/电脑客户端通过 User-Agent 访问订阅时，可自动按地区策略组进行延迟测速和故障转移。

## 4. 常见排错与协议调优（Trojan、XHTTP、ECH 与本地端口冲突）

### 1. Trojan 节点全线 Timeout 超时排查
若客户端测速时出现 **Vless 全绿、Trojan 全红 (Timeout)** 的现象：
- **密码与 SHA-224 校验机制**：Trojan 协议标准要求对密码进行 SHA-224 哈希计算。若控制台中 `tp`（Trojan 密码）留空，部分客户端在缺少密码时无法正确校验 UUID，应明确设置自定义密码（如与 UUID 一致或填入显式密码字符串）。
- **协议裁剪建议**：在 Cloudflare Worker/Pages 环境中，Vless+WS 兼容性与稳定性最优；若无需 Trojan，直接关闭 `et: no` 可保持订阅列表 100% 全绿高可用。

### 2. ECH (Encrypted Client Hello) 阻断陷阱
- **国内环境建议关闭**：若订阅 URL 附带 `ech=...` 参数（如 `ech: yes`），国内部分省份运营商（特别是电信/移动）在 TLS 握手阶段会对无法解密 SNI 的 ECH 包进行强行丢包或发送 TCP RST 复位包，导致节点无法建连。关闭控制台中的 `启用 ECH` (`ech: no`) 即可恢复秒开。

### 3. XHTTP / SPLITHTTP 开启无反应排查
- **内核版本门槛**：XHTTP 是 Xray 新增协议，若客户端（如部分老版 Clash 内核、旧版移动端代理）低于相应支持版本，会直接忽略 `type=xhttp` 参数或报错。日常多设备主力使用建议保持稳定成熟的 `Vless + WebSocket`。

### 4. 客户端本地 `7890 bind: address already in use` 报错排查
- **原因**：手机后台存在残留的多任务代理进程，或同时开启了两个代理软件（如 Clash for Android 与 Flclash）抢占本地 7890 端口。
- **解决**：在手机多任务列表中强制杀掉所有代理进程后重新打开应用，或重启手机。

## 5. API 远程注入与自动化同步实战
在前端控制台支持配置 API 时（如 `/api/config`），可直接通过 Python 脚本实现配置自动化注入：
```python
import json
import urllib.request

url = "https://your-domain.com/<secret_token>/api/config"

# 1. 获取现有配置
req_get = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req_get) as resp:
    cfg = json.loads(resp.read().decode("utf-8"))

# 2. 注入符合规范的优选节点与运营商策略
cfg["yx"] = "104.16.160.1:443#🇺🇸 美国 01 [电信优化],188.114.96.125:443#🇭🇰 香港 01 [电信优化]..."
cfg["yxURL"] = "https://raw.githubusercontent.com/ymyuuu/IPDB/main/bestcf.txt"
cfg["ispTelecom"] = "yes"
cfg["ispUnicom"] = "yes"
cfg["ispMobile"] = "no"
cfg["ipv4"] = "yes"
cfg["ipv6"] = "no"

# 3. 提交持久化存储 (写入 KV)
req_post = urllib.request.Request(
    url,
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    data=json.dumps(cfg).encode("utf-8"),
    method="POST"
)
with urllib.request.urlopen(req_post) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    assert result.get("success") is True
```
