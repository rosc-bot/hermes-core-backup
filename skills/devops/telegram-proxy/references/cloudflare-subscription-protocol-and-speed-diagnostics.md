# Cloudflare 订阅协议兼容性与带宽瓶颈排查指南

## 1. 协议兼容性与陷阱

### Trojan 协议在 Cloudflare 免费 Worker 上的不兼容性
- **现象**：VLESS 节点正常（全绿 80~180ms），但生成的 Trojan 节点在客户端 100% 报错 `Timeout` 或握手拒绝。
- **原因**：
  1. Trojan 协议标准要求客户端将密码进行 `SHA-224` 哈希后发送。当 `tp`（Trojan 密码）留空时，部分订阅生成器与客户端客户端哈希不一致。
  2. Cloudflare 边缘环境没有原生 Trojan 监听器，纯靠 WS 伪装模拟时与大量 Clash/Flclash 内核存在兼容性冲突。
- **最佳实践**：在 Cloudflare 订阅聚合器中，优先使用 `VLESS + WebSocket (WS)`，直接关闭 Trojan 协议生成（`et: no`），避免生成无效的幽灵节点。

### ECH (Encrypted Client Hello) 在国内网络环境的阻断陷阱
- **现象**：开启 ECH（`ech: yes`）后，节点在电信/移动网络下大面积超时或丢包率极高。
- **原因**：国内部分省份运营商（如电信、移动）对 ECH 握手流量进行强制 RST 阻断或深度丢包。
- **最佳实践**：在中国大陆环境下，关闭 ECH（`ech: no`），走成熟的 TLS 1.3 / WebSocket 握手。

### XHTTP (SPLITHTTP) 客户端内核兼容性门槛
- **现象**：开启 xhttp 后，Clash 客户端完全无响应或提示不支持。
- **原因**：XHTTP 是较新的协议，Clash Meta 内核需 >= v1.18.9 或使用最新版 Sing-box / v2rayNG。普通客户端建议保持标准 WebSocket。

---

## 2. 跨地域 VPS 反代 Emby 测速与吞吐瓶颈诊断

### 香港 (HK) vs 荷兰 (NL) 反代 Emby 的延迟与带宽权衡
在实际测试高码率 4K 视频（如 20GB+ / 19.1Mbps）播放时：
- **香港小鸡**：
  - **优势**：物理延迟低（~20ms-30ms），点开海报、目录交互秒开。
  - **瓶颈**：商家通常对出口带宽进行硬限速（如 20Mbps / 2.3MB/s）。当 4K 视频瞬时码率飙升至 30~50Mbps 时，由于带宽饱和导致无限转圈。
- **荷兰小鸡**：
  - **优势**：母机通常提供千兆大带宽（900Mbps+），大文件吞吐量充足。
  - **瓶颈**：物理跨洋延迟高（~300ms），起播需要等待 2~3 秒。
- **诊断命令**：
  ```bash
  curl -sL https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 - --simple
  ```
- **选型策略**：
  - 1080P/常规剧集（<=10Mbps）：优先走香港 30ms 节点，实现“点哪秒哪”。
  - 4K 原盘/超高码率大片（>=20Mbps）：走荷兰/美西千兆大带宽节点，或在香港节点下开启客户端降码率转码。
