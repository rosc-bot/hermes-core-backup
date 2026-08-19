---
name: hermes-web-ui-panel
description: "Use when the Hermes web panel is unreachable."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, web-ui, panel, systemd, cloudflared, tunnel]
    related_skills: [hermes-agent, telegram-gateway-operations]
---

# Hermes Web UI 面板管理（hermes-web-ui）

## 适用场景

- 用户报告"Hermes 面板打不开"，且通过隧道域名（如 `https://xxx.ccwu.cc`）访问。
- 服务器重启后面板失效，需要配置 systemd 开机自启。
- 需要区分两类"面板"服务并选用正确的启动方式。

## 关键区分：两个不同的服务

| 服务 | 技术栈 | 默认端口 | 默认凭据 |
|------|--------|----------|----------|
| `hermes dashboard`（Python） | FastAPI/uvicorn | 9119 | 需配置 auth provider |
| `hermes-web-ui`（npm 包） | Node.js | 8648 | `admin` / `123456` |

大多数场景用户访问的是 **hermes-web-ui**（Node 版），尤其当 cloudflared 隧道指向 `localhost:8648` 时。`hermes dashboard` 绑定 loopback 时对 Host header 有 DNS-rebinding 校验，经域名访问会返回 `400 Invalid Host header`——不要用 Python 版做域名隧道后端。

## 标准诊断流程

1. **查进程**：`ps aux | grep -E 'node.*hermes-web-ui.*dist/server'`（Node 主服务）+ `hermes dashboard --status`（Python 版）。
2. **查端口**：`ss -tlnp | grep 8648`。若 8648 无监听 → 服务没起，这是"重启后打不开"的最常见根因（hermes-web-ui 默认不是 systemd 服务，重启后不会自动拉起）。
3. **查隧道**：`systemctl status cloudflared` + `journalctl -u cloudflared -n 20`。token 模式（`/etc/cloudflared/token`）没有本地 config.yml，ingress 配置在 Cloudflare 面板；日志中 `Unable to reach the origin service ... localhost:8648` 即表示 origin 挂了。
4. **验证**：`curl -o /dev/null -w '%{http_code}' http://127.0.0.1:8648/` 和隧道域名都应返回 200。

## 启动方式陷阱

**`hermes-web-ui.mjs start` 会 daemonize**：它 spawn 一个 detached 子进程（`dist/server/index.js`）后父进程立即退出，因此**不能**直接作为 systemd `Type=simple` 的 ExecStart（systemd 会认为服务已退出）。正确做法是直接运行 server 入口，环境变量由服务文件提供：

```ini
[Service]
Type=simple
User=<运行用户>
Environment=NODE_ENV=production
Environment=PORT=8648
Environment=BIND_HOST=0.0.0.0
Environment=HERMES_WEB_UI_HOME=/home/<user>/.hermes-web-ui
EnvironmentFile=/home/<user>/.hermes-web-ui/env   # 含 AUTH_TOKEN=<token>
ExecStart=/home/<user>/.hermes/node/bin/node /home/<user>/.local/lib/node_modules/hermes-web-ui/dist/server/index.js
Restart=on-failure
RestartSec=5
```

`AUTH_TOKEN` 从 `~/.hermes-web-ui/.token` 读取（64 字符），写入 env 文件并 `chmod 600`。安装后 `systemctl enable --now hermes-web-ui.service`。

## 常见陷阱

- 服务器重启后面板打不开：几乎总是 hermes-web-ui 没配 systemd，先查 8648 端口，别急着怀疑隧道。
- `hermes dashboard`（Python 9119）经 cloudflared 域名访问报 400 `Invalid Host header`：是 DNS-rebinding 防护（loopback 绑定只接受 localhost/127.0.0.1/::1），换用 Node 版 hermes-web-ui。
- `hermes-web-ui.mjs start` 输出 `already running (PID: x)`：它有自己的 pid 文件（`~/.hermes-web-ui/server.pid`），daemon 方式启动时先 `hermes-web-ui stop` 或用服务文件直接跑入口。
- 隧道正常但 8648 拒连：确认 server entry 是否带了 `AUTH_TOKEN`（缺 token 时面板可能启动但鉴权异常）。
- 服务文件修改后必须 `sudo systemctl daemon-reload` 再 restart。

## 验证清单

- `systemctl is-active hermes-web-ui.service` → `active`
- `systemctl is-enabled hermes-web-ui.service` → `enabled`
- 本地 `curl http://127.0.0.1:8648/` → 200
- 隧道域名 `curl https://<域名>/` → 200
