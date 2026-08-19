# 多节点连通性测试与 NAT VPS 诊断

## 适用场景

- 一台 NAT VPS / 容器在面板显示 `running`，但 SSH 端口 `No route to host` 或 `Timed out`。
- 需要区分是"服务器本身离线"还是"宿主机 NAT 转发异常"。
- 需要探测宿主机上还有哪些端口开放（可能端口映射发生了变化）。

## 多节点测试策略

### 原理
从三个不同地理位置的节点同时测试目标服务器，可以区分：
- **全部超时** → 目标服务器本身或宿主机关机/网络断开。
- **部分节点通、部分超时** → 中间路由问题，或目标服务器所在区域网络波动。
- **本机超时、其他节点通** → 本机到目标路由被墙或防火墙拦截。
- **端口段中个别端口通** → 宿主机 NAT 规则正常，但当前容器映射端口可能变化。

### 命令模板

```bash
# 从本机测试
nc -zv -w 3 <TARGET_IP> <PORT>

# 从香港🐔测试（通过 SSH 跳板）
ssh -o StrictHostKeyChecking=no root@<HONGKONG_IP> "nc -zv -w 3 <TARGET_IP> <PORT>"

# 从荷兰🐔测试
ssh -p <PORT> -o StrictHostKeyChecking=no root@<NETHERLANDS_IP> "nc -zv -w 3 <TARGET_IP> <PORT>"
```

### Python 端口扫描（绕过 iptables rate-limit）

```python
import socket

target = '<TARGET_IP>'
ports_to_check = [14895, 14896, 14897, 14898, 14899]  # 待测端口段

for p in ports_to_check:
    s = socket.socket()
    s.settimeout(0.5)
    res = s.connect_ex((target, p))
    if res == 0:
        print(f"Port {p}: OPEN")
    elif res == 11:  # EAGAIN / ECONNREFUSED 的另一种表现
        print(f"Port {p}: Timed out (宿主机存活但转发未就绪)")
    else:
        print(f"Port {p}: {res}")
    s.close()
```

### 大范围快速扫描

```python
import socket, concurrent.futures

target = '<TARGET_IP>'
def check(p):
    s = socket.socket()
    s.settimeout(0.8)
    res = s.connect_ex((target, p))
    s.close()
    return p, res

with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
    futures = [ex.submit(check, p) for p in range(14800, 15000)]
    for f in concurrent.futures.as_completed(futures):
        p, res = f.result()
        if res == 0:
            print(f"OPEN PORT: {p}")
```

## NAT VPS 诊断清单

### 阶段 1：确认宿主机在不在线
```bash
ping -c 3 <TARGET_IP>          # ICMP 通 = 宿主机在线
curl -s ip.sb                  # 获取本机公网 IP
```

### 阶段 2：确定端口段范围
NAT VPS 通常按 5 个端口为一组分配（如 `14895~14899`）。扫描宿主机确认端口段：

```bash
# 从第三方节点扫描
ssh <跳板机> "python3 -c \"
import socket
for p in range(14890, 14950):
    s = socket.socket()
    s.settimeout(0.5)
    if s.connect_ex(('<TARGET_IP>', p)) == 0:
        print(f'OPEN: {p}')
    s.close()
\""
```

### 阶段 3：判断容器状态

| 现象 | 判断 | 对策 |
|------|------|------|
| ICMP ping 通，端口 Timed out | 宿主机 NAT 规则存在，但容器内部系统未启动 | 面板 Force Stop → 等待 30s → Start |
| ICMP 通，端口 No route to host | 宿主机 NAT 规则未配置或已删除 | 面板检查端口映射配置 |
| 同宿主机其他端口通（如 14900） | 宿主机正常，当前容器异常 | 查看面板 VNC/Console，或重装系统 |
| 全部端口不通，ping 不通 | 宿主机离线或关机 | 面板先开机 |

## 常见陷阱

- `No route to host` vs `Connection timed out` 含义不同：
  - `No route to host`：宿主机 iptables 没有该端口的规则（或端口映射被移除）。
  - `Timed out`：宿主机有规则，但容器内部未响应（SYN 包进了容器但没回 SYN-ACK）。
- 面板显示 `running` 不代表容器内部网络已就绪，尤其是刚重启后（系统启动慢、DHCP 未完成）。
- 重装系统（Reinstall/Rebuild）是最后手段，但通常是解决容器卡死状态最有效的方式。对于 256MB 内存的 VPS，推荐使用 Debian 12 Minimal 或 Alpine Linux。避免重装 Ubuntu Desktop 等大系统。
- 部分 NAT VPS 面板在重启后可能重新分配端口段，如果端口全不通，先检查面板上的端口映射是否变了。