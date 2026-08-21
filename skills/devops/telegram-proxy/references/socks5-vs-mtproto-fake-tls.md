# SOCKS5 vs MTProto Fake-TLS 抗封锁实战经验与 NAT 高位端口避坑

## 核心背景与现象
在海外 VPS（如荷兰、美西等高延迟地区或 NAT 架构）上部署 Telegram 代理时，常出现：
- **开启全局梯子时 SOCKS5 可以连接，但关闭梯子/直接使用国内网络时无法连接**。

## 根因分析
1. **SOCKS5 是明文传输协议**：
   - 协议握手缺乏 TLS 强加密与混淆特征。
   - 国内运营商防火墙（GFW）对海外公网 IP 的高位端口 SOCKS5 流量具有灵敏的主动探测与 TCP RST 阻断策略。
   - 在高位 NAT 端口（如 30000+）运行 SOCKS5 时阻断尤为严重。
2. **MTProto Fake-TLS 的抗封锁优势**：
   - 使用 `mtg v2` 的 Fake-TLS 模式，将流量混淆伪装成与主流 CDN（如 `cloudflare.com`）的标准 TLS 1.3 握手流量。
   - 配合防重放攻击机制（`[defense.anti-replay]`），国内直连时无法被 DPI 识别为代理流量，从而实现免翻直连。

## 最佳迁移与部署实践（在已有 VLESS-REALITY 的机器上）
1. **避免端口冲突**：
   - 若机器上已有 Xray 监听 VLESS 端口，修改 Xray 配置文件，移除明文 SOCKS5 inbound 并释放端口。
2. **mtg 下载与安装命令**：
   ```bash
   wget -qO /tmp/mtg.tar.gz https://github.com/9seconds/mtg/releases/download/v2.2.8/mtg-2.2.8-linux-amd64.tar.gz
   mkdir -p /tmp/mtg-extract
   tar -xzf /tmp/mtg.tar.gz -C /tmp/mtg-extract
   cp /tmp/mtg-extract/mtg /usr/local/bin/mtg 2>/dev/null || cp /tmp/mtg-extract/mtg-*/mtg /usr/local/bin/mtg
   chmod +x /usr/local/bin/mtg
   ```
3. **配置文件模板 (`/etc/mtg/config.toml`)**：
   ```toml
   debug = false
   secret = "<GENERATED_BASE64_SECRET>"
   bind-to = "0.0.0.0:<PORT>"
   concurrency = 8192
   auto-update = false
   prefer-ip = "prefer-ipv4"
   tolerate-time-skewness = "30s"

   [network.timeout]
   tcp = "5s"
   idle = "5m"
   handshake = "10s"

   [defense.anti-replay]
   enabled = true
   max-size = "1mib"
   error-rate = 0.001

   [defense.blocklist]
   enabled = false

   [stats.prometheus]
   enabled = false
   ```
4. **获取分享链接**：
   ```bash
   # 获取 Hex 格式（兼容性最好）
   mtg access --hex /etc/mtg/config.toml
   ```
