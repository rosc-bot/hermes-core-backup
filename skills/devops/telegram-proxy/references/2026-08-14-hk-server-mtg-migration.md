# 香港🐔 从 mtprotoproxy 迁移到 mtg

**日期：** 2026-08-14
**服务器：** 156.245.245.172（香港，Debian 13，2核/2G/79G）
**主机名：** serBnTOjmSJtG

## 背景

原始代理使用 `mtprotoproxy`（Python），用户反馈"还是不可用"——代理运行正常但连接数为 0，怀疑被 GFW 屏蔽。

## 迁移清单

### 停止旧服务
```bash
systemctl stop mtprotoproxy
systemctl disable mtprotoproxy
```

### 安装 mtg
```bash
wget -q https://github.com/9seconds/mtg/releases/download/v2.2.8/mtg-2.2.8-linux-amd64.tar.gz -O /tmp/mtg.tar.gz
tar xzf /tmp/mtg.tar.gz -C /tmp
cp /tmp/mtg-2.2.8-linux-amd64/mtg /usr/local/bin/mtg
chmod +x /usr/local/bin/mtg
```

### 生成密钥
```bash
SECRET=$(mtg generate-secret cloudflare.com)
# 输出: 7tkjmFklmcDmqY_ZzzPOgs5jbG91ZGZsYXJlLmNvbQ
# 十六进制: eed92398592599c0e6a98fd9cf33ce82ce636c6f7564666c6172652e636f6d
```

### 配置（关键：secret 和 bind-to 在根级别，不能嵌套在 [mtg] 下）
```toml
debug = false
secret = "7tkjmFklmcDmqY_ZzzPOgs5jbG91ZGZsYXJlLmNvbQ"
bind-to = "0.0.0.0:443"
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

### 验证
```bash
mtg doctor /etc/mtg/config.toml
# 输出应包含所有 ✅ 检查通过
```

### 最终代理链接
```
tg://proxy?server=156.245.245.172&port=443&secret=eed92398592599c0e6a98fd9cf33ce82ce636c6f7564666c6172652e636f6d
```

### 一键打开
https://t.me/proxy?port=443&secret=7tkjmFklmcDmqY_ZzzPOgs5jbG91ZGZsYXJlLmNvbQ&server=156.245.245.172

## 调试经验

### "secret is empty" 错误
配置文件中 `secret` 和 `bind-to` 放在了 `[mtg]` 节下面，但 mtg 要求它们在根级别。

### HTTP 400 Bad Request 测试
从外部测试时，发送原始密钥字节后得到 HTTP 400 响应——这是正常的，因为 mtproto 协议需要完整的握手流程，不能只发密钥。

### 连接数为 0 的排查
- ✅ 服务运行中监听 443
- ✅ TLS 握手正常（cloudflare.com SNI）
- ✅ 服务器到 Telegram DC 全部可达
- ✅ 端口从外部可达
- ⚠️ 问题可能在 GFW 层面

## 当前状态
- mtg 2.2.8 已安装，systemd 开机自启（mtg.service）
- 监听 443 端口，TLS 模式，伪装 cloudflare.com
- 旧 mtprotoproxy 已停用并禁用