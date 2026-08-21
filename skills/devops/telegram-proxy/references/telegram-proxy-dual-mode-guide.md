# Telegram SOCKS5 与 MTProto 客户端链接格式及双模部署实战

## 1. Telegram 客户端原生链接协议规范

在 Telegram 移动端与桌面端生成可直接点击添加的代理链接时，必须严格遵守以下协议参数：

### SOCKS5 链接规范
* **协议 scheme**: `tg://socks`（推荐，全客户端无缝调起）或 `https://t.me/socks`（Web 中转跳转）。
* **必填与可选参数**:
  - `server`: 节点公网 IPv4 地址或域名。
  - `port`: 代理监听端口。
  - `user` 或 `username`: 认证用户名（`user` 兼容性最好，部分第三方客户端接受 `username`）。
  - `pass` 或 `password`: 认证密码。
* **标准范例**:
  ```text
  tg://socks?server=69.33.212.139&port=10808&user=tgsocks&pass=tgpass888
  https://t.me/socks?server=69.33.212.139&port=10808&user=tgsocks&pass=tgpass888
  ```

### MTProto 链接规范
* **协议 scheme**: `tg://proxy` 或 `https://t.me/proxy`。
* **参数要求**:
  - `server`: 服务器 IP。
  - `port`: 端口（通常为 `443` 或放通的高位端口）。
  - `secret`: mtg 生成的 16 字节密钥（带 `ee` 前缀 + 域名十六进制编码，如 `eed072e09ebe59fdfe455d26d03577b76e636c6f7564666c6172652e636f6d`）。
* **标准范例**:
  ```text
  https://t.me/proxy?server=69.33.212.139&port=443&secret=eed072e09ebe59fdfe455d26d03577b76e636c6f7564666c6172652e636f6d
  ```

---

## 2. 为什么需要“直连 + 开启梯子双模双端口”设计？

在实际使用 Telegram 时，用户的网络环境经常在“直连国内网络”与“开启全局梯子/VPN”之间切换：

1. **直连国内网络时（无梯子）**：
   - 普通 SOCKS5 是明文裸协议，海外非标端口极易被 GFW 检测到特征并下发 TCP RST 阻断，导致“关闭代理无法连接”。
   - **最优解**：使用 `mtg`（MTProto Fake-TLS 伪装 `cloudflare.com`，运行在 `443` 端口），过墙能力极强，直连秒连。

2. **开启梯子/VPN 时**：
   - 梯子客户端（如 Clash、Shadowrocket、Surge）通常接管系统 DNS 并对流量进行 MITM/TUN 劫持。
   - 当梯子接管 MTProto 的 Fake-TLS 流量时，伪造的证书与 SNI 经常与梯子内部规则冲突或被拦截，导致用户感觉“开梯子反而连不上 MTProto”。
   - **最优解**：额外在服务器配置一个标准 Xray SOCKS5 入口（如 `10808` 或 `35087`），通过梯子内网转发至服务器，完全无兼容性冲突。

---

## 3. 单台 VPS 多协议多端口共存标准配置

以 Debian 13 VPS（如 DEG🐔）为例，实现三节点并存：

1. **MTProto 服务 (`mtg.service`)**：
   - 监听：`0.0.0.0:443`
   - 伪装域名：`cloudflare.com`
2. **SOCKS5 服务 (`xray.service`)**：
   - 监听：`0.0.0.0:10808`
   - 认证：`tgsocks / tgpass888`
3. **VLESS-REALITY 服务 (`xray-reality.service`)**：
   - 监听：`0.0.0.0:30810`
   - 伪装目标：`www.cloudflare.com:443`

三者使用独立的 systemd unit 运行，互不干扰，开机自启。
