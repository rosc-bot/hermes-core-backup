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

## 常见陷阱

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
