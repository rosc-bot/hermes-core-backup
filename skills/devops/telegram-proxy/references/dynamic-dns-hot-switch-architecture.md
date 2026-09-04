# 动态 DNS 热切换与客户端永久固定端点架构指南

## 业务痛点
在多节点/多小鸡反代流媒体（如 Emby / Jellyfin / 代理网关）时，各小鸡有不同的 IP 和外部 NAT 映射端口：
- 🇹🇼 台湾节点：`45.207.153.154:29759`（延迟 34ms，大带宽 215Mbps，看 4K 首选）
- 🇭🇰 香港节点：`156.245.245.172:18096`（延迟 20ms 超低延时，20Mbps 限速）
- 🇳🇱 荷兰节点：`199.47.241.137:35087`（延迟 300ms，千兆大水管备用）

如果每个节点使用独立 IP:端口，用户在电视盒子、手机平板上切换线路时，必须重新输入服务器地址、重新输入账号密码登录，体验极度繁琐。

---

## 核心解决方案：专属二级域名 + Cloudflare API 动态秒切

### 1. 架构拓扑
```text
📱 客户端（电视/手机/平板）
      │
      ▼ 永久固定连接: http://ruxi666.ccwu.cc:29759/wj/ (一次输入，终生不改)
Cloudflare DNS 解析
      │
      ▼ (由 AWS 控制面板在后台通过 API 毫秒级秒切目标 IP)
  ┌── 🇹🇼 台湾节点 (45.207.153.154)   [4K 极速首选]
  ├── 🇭🇰 香港节点 (156.245.245.172)  [低延时备用]
  └── 🇳🇱 荷兰节点 (199.47.241.137)   [大水管备用]
```

### 2. Cloudflare API 动态切换实现 (Python 核心逻辑)
```python
import json, urllib.request

CF_TOKEN = "cfut_..."
CF_ZONE_ID = "..."
CF_DOMAIN = "ruxi666.ccwu.cc"

def switch_dns_ip(target_ip):
    # 1. 查取当前 A 记录 ID
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?name={CF_DOMAIN}",
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        record_id = data["result"][0]["id"]

    # 2. PATCH 更新目标 IP (TTL 设为 60s, proxied 设为 False 保证直连极速)
    body = json.dumps({
        "type": "A",
        "name": "@",
        "content": target_ip,
        "ttl": 60,
        "proxied": False
    }).encode("utf-8")

    req_patch = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_id}",
        data=body,
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"},
        method="PATCH"
    )
    with urllib.request.urlopen(req_patch, timeout=8) as resp:
        res = json.loads(resp.read().decode())
        return res.get("success", False)
```

### 3. 常见陷阱与注意事项
1. **代理状态 (Proxied)**：必须设置为 `false`（灰色云朵）。开启橙色云朵（经过 CF CDN）会导致 4K 高码率视频被 CF 缓存策略和单线程缓冲限制，且非标准 HTTP 端口可能无法直通。
2. **TTL 设置**：设为 60 秒或自动，确保后台点击切换后，客户端在 1 分钟内无感切换到新小鸡。
3. **NAT 端口统一建议**：若多台 NAT 小鸡的外部端口不一致，可通过主控面板展示对应端口的完整链接，或在小鸡上尽量向服务商申请/映射相同或相近的固定业务端口。
