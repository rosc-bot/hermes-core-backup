---
name: cliproxyapi
description: "Use when deploying or managing CLIProxyAPI (CPA) proxy."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cliproxyapi, cpa, proxy, api, systemd, deployment]
    related_skills: [telegram-proxy, hermes-web-ui-panel]
---

# CLIProxyAPI (CPA) 部署与管理

## 适用场景

- 在 Linux 服务器上安装 CLIProxyAPI（CPA，OpenAI 兼容 API 代理/路由）。
- 配置 CPA 面板（/management.html）、管理密钥、开机自启。
- 排查 CPA 端口不通、面板打不开、systemd 服务异常退出等问题。

## 常见接口调用报错排查：API 验证/认证错误 (401/403)
当你使用 Hermes 工具发起 `curl` 探测 CPA 提供给客户端的内部调用接口（例如 `/v1/images/generations`、`/v1/chat/completions`）却遇到鉴权错误时：
- **永远检查 CPA API Key 配置**。`cliproxyapi/config.yaml` 文件中的 `api-keys` 列表（例如 `['sk-dd0...']`）必须与你发起的请求 Header `Authorization: Bearer <key>` 匹配。
- **不要混淆 API Key 与 Hermes 框架配置**。如果你在测试一个代理了模型或图像生成的 custom_provider，CPA 作为“底座服务”需要校验其下发的 Key，而并不是 Hermes Web UI 面板的 Key（例如 `~/.hermes-web-ui/.token`）。确认客户端代码里 `Authorization` Header 是填入的 CPA Key。
- **确认底层 Custom Provider 状态**。如果 CPA 后端配置的供应商挂了、不可用，CPA 可能会直接透传上游的 403 或 503 等报错信息（比如：提示没有权限或暂无适用账户）。此时需查看 CPA 配置所代理的底座服务，并根据日志确认其自身额度及状态。

## 模型请求 400/上游错误排查：error log 原样重放二分法

客户端（Hermes 等）报 "model provider failed after retries" / 400 / 401 / 403，且模型走 CPA 转发时，按此流程排查：

1. **定位请求路径**：先看 `~/.hermes/logs/errors.log` / `gateway.log`，找到 `provider=... base_url=... model=...` 与原始错误（确认确实是走本地 CPA，如 `base_url: http://127.0.0.1:8317/v1`）。
2. **读 CPA 错误日志**：`~/cliproxyapi/logs/error-v1-chat-completions-<时间>-<hash>.log`（同名文件还有 `error-api-show-*.log` 等）。每份含 `=== REQUEST BODY ===`（客户端请求原文 JSON）、`=== API REQUEST ===`（上游 URL、使用的 Auth 账号、请求头）、`=== API RESPONSE ===`（上游响应）、`=== RESPONSE ===`（最终返回）。
3. **原样重放**：提取 REQUEST BODY 用 `curl -d @replay.json` 直打 `http://127.0.0.1:8317/v1/chat/completions`（Bearer 用 `keys.txt` 里的 sk- 开头 key）。用脚本 `scripts/extract_cpa_request.py` 一键提取并输出诊断摘要。
   - **能复现** → 继续二分定位（见下）。
   - **不复现** → 上游间歇性故障：连打 3~6 次同一请求，若全 200 即判定为上游抖动（如 Google Antigravity `daily-cloudcode-pa.googleapis.com` 的瞬时 400 INVALID_ARGUMENT），重试即可，**不要改任何配置**。
4. **二分定位**：从失败请求逐步删减（或从最小请求逐步加回）——去掉全部 `tools`；去掉历史消息里的 `assistant.tool_calls`/`tool` 消息；把 `user` 消息内容换成 `"hi"`。任一删除使 200 即定位到该成分。
   - ⚠ 注意：`assistant.tool_calls` 与 `tool` 消息**不配对**时上游必 400，这是正常行为，不是 bug。
5. **Antigravity 账号状态检查**：`auths/antigravity-<email>.json` 字段 `timestamp`（**毫秒**，勿当秒解析） + `expires_in`（秒）算到期时间；`expired`/`disabled` 标志。routing 为 round-robin 时多账号轮询，坏账号会造成间歇性报错（排查可临时把嫌疑账号 `disabled: true` 剔除验证，改前需用户确认）。
6. **main.log 的 "bind: address already in use" 循环**：⚠ 不是可忽略的噪音！实测（2026-08-31）main.log 累积 1859 次、每 5-6 秒一次的 bind 失败 = wrapper/systemd 在反复拉起新实例而旧实例占着端口（僵尸循环）。期间请求间歇异常（与上游 400 并发出现）、日志爆炸（几小时数 GB）。修复：`systemctl stop cpa` → 杀残留 → 确认端口释放 → `systemctl start cpa`；重启后 `grep -c "address already in use" main.log` 计数应停止增长。注意 pkill 坑见下。

详细案例（2026-08-31 gemini-3.7-flash-high 间歇 400 全量复现记录）见 `references/antigravity-400-debug.md`；一键提取脚本见 `scripts/extract_cpa_request.py`。

## 一键安装脚本

典型安装脚本流程（`~/cliproxyapi` 为目标目录，默认端口 8317）：

1. 检测架构（amd64/arm64），`uname -m` 映射。
2. 从 GitHub `router-for-me/CLIProxyAPI` latest release 下载，优先 `_linux_<arch>_no-plugin.tar.gz`（沙盒兼容），回退普通版。
3. 解压并找到可执行文件（`cli-proxy-api`），`--help` 验证可执行。
4. 生成密钥：`API_KEY="sk-$(openssl rand -hex 24)"`、`MANAGEMENT_KEY="$(openssl rand -hex 24)"`，写入 `keys.txt`（chmod 600）。
5. 生成 `config.yaml`：host `""`、port、`remote-management.secret-key`、`auth-dir`、`api-keys` 列表。
6. `nohup` 启动，写 `cpa.pid`，`curl /v1/models` 验证。

安装后检查 `keys.txt` 拿 API_KEY 和 MANAGEMENT_KEY。

## 面板与登录

- 面板地址：`http://<服务器IP>:8317/management.html`（服务自动从 GitHub 下载托管，`static/management.html`）。
- 登录凭据：管理密钥（`CPA_MANAGEMENT_KEY`），不是 API key。
- API 端点：`/v1/chat/completions`、`/v1/completions`、`/v1/models`（Bearer API key）。
- 管理 API：`/v0/management/config` 等（Bearer 管理密钥），`/v0/management/` 前缀。
- 服务器公网 IP 变化时面板地址随之变化；先 `curl https://api.ipify.org` 确认新 IP。
- **Docker 容器内访问 CPA（跨命名空间）**：当客户端（如 Bemby 等）运行在 Docker 容器内，不能使用 `http://127.0.0.1:8317/v1`（会指向容器自身回环）。推荐填入 Docker 宿主机网关 `http://172.17.0.1:8317/v1`（走内部虚拟网桥，延迟低且免公网路由），或使用服务器公网 IP `http://<服务器公网IP>:8317/v1`。

## 两个独立发布物：面板 vs 核心二进制（重要）

CPA 有**两个独立的上游仓库**，更新时必须分别检查，缺一不可：

| 发布物 | 仓库 | release 资产 | 更新方式 |
|---|---|---|---|
| 管理面板 | `router-for-me/Cli-Proxy-API-Management-Center` | 仅 `management.html` | 服务启动时自动拉取，通常已最新 |
| 核心二进制 | `router-for-me/CLIProxyAPI` | `CLIProxyAPI_<ver>_linux_<arch>_no-plugin.tar.gz` 等 | **手动下载替换**，最容易落后 |

**教训**：用户说「更新 CPA 面板」时，若只检查面板文件就宣布「已是最新」，可能被质疑——核心二进制可能落后十几个版本（例如面板 v1.22.10 已最新，但二进制停在 7.2.132 而最新是 7.2.146）。**每次更新前两个仓库的 latest release 都必须查**：

```bash
# 面板仓库（management.html 资产）
curl -s https://api.github.com/repos/router-for-me/Cli-Proxy-API-Management-Center/releases/latest | grep tag_name
# 二进制主仓库（tar.gz 资产）
curl -s https://api.github.com/repos/router-for-me/CLIProxyAPI/releases/latest | grep tag_name
# 本地二进制版本
cd ~/cliproxyapi && ./cli-proxy-api --version
```

## 面板自动更新机制

CPA 服务启动时会**自动从 GitHub 拉取最新版 `management.html`** 托管到 `static/` 目录，通常无需手动更新。

验证面板是否已是最新（三步）：

```bash
# 1. 查 GitHub 最新 release（asset 即 management.html）
curl -s https://api.github.com/repos/router-for-me/Cli-Proxy-API-Management-Center/releases/latest
#   → tag: v1.22.10

# 2. 下载最新版，与本地文件及运行中服务实际返回的内容对比 md5
curl -sL -o /tmp/cpa_latest.html https://github.com/router-for-me/Cli-Proxy-API-Management-Center/releases/download/<TAG>/management.html
md5sum /tmp/cpa_latest.html ~/cliproxyapi/static/management.html
curl -s http://127.0.0.1:8317/management.html | md5sum   # 运行中实际提供的内容

# 3. 快速查版本号（⚠ 会混入 React 内部版本如 19.2.7 / v24.3.0，需看 tileValue 上下文或用 md5 为准）
curl -s http://127.0.0.1:8317/management.html | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | sort -u
```

- 面板文件 mtime 与 GitHub release 发布时间几乎同步（差约 15 秒）是自动更新的正常表现，不必惊讶。
- 用户反馈面板仍是旧版时，先让浏览器强刷（Ctrl+F5）清缓存，再怀疑面板文件本身。

## 关键陷阱：CPA 是 daemon 程序

**CPA 二进制启动后主进程立即退出（exit 0），实际服务在 fork 出的子进程里运行**。直接作为 systemd `Type=simple` 的 ExecStart 会导致 systemd 认为服务已退出（`inactive (dead)`），但端口仍被残留子进程监听。验证方法：`timeout 5 cli-proxy-api -config config.yaml` 前台运行，观察主进程退出但端口仍在监听。

正确做法：写一个 **wrapper 脚本**，启动 CPA 后从 `ss -tlnp` 抓取监听端口的真实 PID 并持续跟踪：

```bash
#!/usr/bin/env bash
CPA_BIN="/home/ubuntu/cliproxyapi/cli-proxy-api"
CPA_CONFIG="/home/ubuntu/cliproxyapi/config.yaml"
LOG="/home/ubuntu/cliproxyapi/logs/cpa.log"

cleanup() { [ -n "${CPA_PID:-}" ] && kill "$CPA_PID" 2>/dev/null; }
trap cleanup EXIT INT TERM

"$CPA_BIN" -config "$CPA_CONFIG" >>"$LOG" 2>&1 &
for i in $(seq 1 15); do
  CPA_PID=$(ss -tlnp 2>/dev/null | grep ':8317 ' | grep -oP 'pid=\K[0-9]+' | head -1)
  [ -n "${CPA_PID:-}" ] && break
  sleep 1
done
[ -z "${CPA_PID:-}" ] && { tail -50 "$LOG"; exit 1; }
while kill -0 "$CPA_PID" 2>/dev/null; do sleep 5; done
```

systemd 单元（Type=simple + wrapper）：

```ini
[Service]
Type=simple
User=<运行用户>
WorkingDirectory=/home/<user>/cliproxyapi
ExecStart=/home/<user>/cliproxyapi/cpa-wrapper.sh
Restart=on-failure
RestartSec=5
```

## 升级核心二进制流程（含 daemon 坑）

升级步骤（实测有效）：

```bash
# 0. 对比版本（见上节），确认需要升级
# 1. 停服务——注意：systemctl stop 只杀 wrapper，fork 出的真实进程会成为孤儿继续跑！
sudo systemctl stop cpa.service
# 2. 找到并杀死孤儿进程（否则端口占着、二进制文件被占用）
ps aux | grep -iE 'cli-proxy' | grep -v grep   # 找到孤儿 PID
sudo kill -9 <ORPHAN_PID>
sleep 2
ss -tlnp | grep 8317 || echo "端口已释放"
# 3. 备份旧二进制（可回滚）
cd ~/cliproxyapi && cp cli-proxy-api cli-proxy-api.bak-<旧版本号>
# 4. 下载并替换（优先 no-plugin 版）
curl -sL -o /tmp/CPA.tar.gz https://github.com/router-for-me/CLIProxyAPI/releases/download/<TAG>/CLIProxyAPI_<TAG>_linux_amd64_no-plugin.tar.gz
mkdir -p /tmp/cpa_new && tar -xzf /tmp/CPA.tar.gz -C /tmp/cpa_new
cp /tmp/cpa_new/cli-proxy-api ./cli-proxy-api && chmod +x cli-proxy-api
./cli-proxy-api --version   # 确认新版本号
# 5. 启动并验证
sudo systemctl start cpa.service && sleep 5
systemctl is-active cpa.service   # active
ss -tlnp | grep 8317             # 监听中
```

**关键坑：`Text file busy`**——若 `cp` 替换二进制时报 `Text file busy`，说明仍有 CPA 进程在运行（通常是 `systemctl stop` 后残留的孤儿，`systemctl is-active` 可能显示 `inactive` 但进程还活着）。此时 `fuser -v cli-proxy-api` 看占用者，`kill -9` 后重试。千万不要带着残留进程直接替换。

## Antigravity 通道间歇性 400 排查（实测经验 2026-08-31）

### 现象
- Hermes 切 gemini（antigravity 专属模型如 gemini-3.7-flash-high）请求偶发 `400 INVALID_ARGUMENT: Request contains an invalid argument`，重试后仍失败，切 deepseek 正常。

### 关键结论
- **根因在 Google Antigravity 免费 OAuth 通道（daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent），与 CPA 版本无关**（7.2.132 / 7.2.146 均复现）。Google 对免费账号做隐藏限流：用 400 代替 429 拒绝（无 Retry-After 头），令牌桶式随机拒绝 → 同一请求 200/400/200 交替。
- 空 body `{}` 打该端点也返回一模一样的 400 → 判定是上游拒单而非请求格式问题。
- 正确上游格式为 `{"request": {GenerateContentRequest}}`（裸 contents/generationConfig 报 Unknown name）。
- 两个 project（radiant-lattice-qds98 / crypto-aleph-kc9s2）均报 "Cloud Code Private API 未启用" 403；cloudcode-pa 端点报 429 配额耗尽 → 免费通道不可靠是常态。

### 修复（需用户确认后执行）
1. `config.yaml`：`max-retry-credentials: 0 → 2`（重试换账号）、新增 `quota-exceeded.antigravity-credits: true`（额度超限自动切换），改后管理 API `/v0/management/config` 可验证。
2. 干净重启：`systemctl stop cpa` → 杀残留进程 → 确认 8317 释放 → `systemctl start cpa`。
3. 验证：原样重放大请求连打 6 次全 200。

### 排查工具链
- 失败请求原样重放：CPA `logs/error-v1-chat-completions-*.log` 含完整 REQUEST BODY（可能被截断，用 `=== REQUEST BODY ===` 到 `=== API REQUEST` 之间的行拼 JSON）。
- 上游格式探测：向 `daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse` 发 `{}`（看是否同错）、发含大量候选字段的对象（Google 报 Unknown name 列差异）。
- 管理 API：`GET /v0/management/config`，Header `Authorization: Bearer $CPA_MANAGEMENT_KEY`（keys.txt 中 `CPA_MANAGEMENT_KEY=` 值）。
- 模型映射表：`raw.githubusercontent.com/router-for-me/models/refs/heads/main/models.json`，`owned_by: antigravity` 的模型走 antigravity 通道。
- 二进制行为线索：`strings cli-proxy-api | grep antigravity`（可见 "rate limited on base url, retrying with fallback" 等逻辑）。

### 注意
- `pkill -f cli-proxy-api` 会匹配执行命令的 shell 自身（命令行含关键字）→ 自杀！用精确 PID 或 `pkill -f '^/home/ubuntu/cliproxyapi/cli-proxy-api'` 之类规避。

## 常见陷阱

- CPA 僵尸重启循环（main.log 每 5-6 秒一次 `bind: address already in use`，cpa.log 大量重复启动）：说明 wrapper/systemd 在反复拉起新实例而旧实例占着端口。修复：干净重启（stop → 杀残留 → start）。期间请求可能间歇异常，且日志会爆炸（几小时数 GB）。
- `systemctl is-active cpa.service` 显示 `inactive` 但端口还在监听 → daemon 化残留，杀掉残留 PID 后用 wrapper 方案。
- 面板 404：确认访问的是 `/management.html` 而非 `/panel`、`/admin` 等路径（那些都是 404）。
- 忘记 `sudo systemctl daemon-reload` 就 restart → 服务仍用旧配置。
- 配置文件 `config.yaml` 和 `keys.txt` 权限应为 600（含密钥）。
- 更换运行用户或目录后要同步改 wrapper 里的路径。

## 验证清单

- `ss -tlnp | grep 8317` → cli-proxy-api 监听
- `systemctl is-active cpa.service` → `active`
- `systemctl is-enabled cpa.service` → `enabled`
- `curl http://127.0.0.1:8317/` → `{"endpoints":[...]}` 200
- `curl http://127.0.0.1:8317/management.html` → 200
- `./cli-proxy-api --version` → 二进制版本号与目标一致
- `curl -s http://127.0.0.1:8317/management.html | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+'` → 面板版本号与 GitHub latest 一致
