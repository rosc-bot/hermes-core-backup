# AWS Security Group Inbound Ports & External Probing Invariants

## 1. Confirmed Open Ports on Host Security Group

All rules specify `0.0.0.0/0` (global IPv4 ingress):

| Port | Protocol | Status | Bound Service / Purpose |
| :---: | :---: | :---: | :--- |
| **22** | TCP | In Use | OpenSSH Server (remote administrative login) |
| **80** | TCP | **Idle (Available)** | Standard HTTP |
| **443** | TCP | **Idle (Available)** | Standard HTTPS / TLS termination |
| **2082** | TCP | **In Use** | Media Submission Bot WebUI Dashboard (`http://<ip>:2082/`) |
| **3000** | TCP | In Use | Emby Multi-Proxy Master Controller |
| **8317** | TCP | In Use | CLIProxyAPI (CPA) |
| **8648** | TCP | In Use | Hermes Web UI |
| **12666** | TCP | **In Use** | OpenList Service (`http://<ip>:12666/`) |
| **35087** | TCP | In Use | Xray SOCKS Proxy / Reality |
| **39637** | TCP | **Idle (Available)** | High-port custom TCP |
| **29657** | UDP | **Idle (Available)** | Custom UDP |
| **61242** | UDP | **Idle (Available)** | Custom UDP |

## 2. Invariant: Port Allocation Workflow

1. **Never Invent Arbitrary Ports**: Do not bind services to new random ports (e.g. 8090, 8080) that require cloud security group alterations.
2. **Consult Before Allocating**: When launching new web UIs, HTTP APIs, or listeners, check the list above and ask the user to pick from the **Idle (Available)** ports (`2082`, `12666`, `39637`, `80`, `443`).
3. **External Probing Pitfall**:
   - Probing an unopened local port with `curl` or `nc -z` from an external server will time out or fail when **no daemon is listening on that port locally**, even if the cloud security group actually permits it!
   - Do NOT assume a timed-out external probe means the cloud security group is blocked if `ss -tulpn` shows no process listening on that port. First bind a dummy listener or check the verified security group rule list.
