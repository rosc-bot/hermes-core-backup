# Mihomo/Clash Runtime Log Diagnostics & Error Classification

When troubleshooting Mihomo / Clash.Meta in Android root environments (SurfingTile, Box for Magisk) or desktop/server daemons, always classify log messages by their layer before taking action.

---

## 1. Error Layer Hierarchy

| Log Level & Layer | Example Log Pattern | Root Cause | Action Required |
| :--- | :--- | :--- | :--- |
| **Startup / Pre-validation (`[Error]`)** | `level=error msg="yaml: ..."`<br>`configuration file ... test failed` | Fatal YAML syntax, unknown anchor, or invalid data types. Mihomo **fails to start entirely**. | Fix `config.yaml` immediately. Core is dead until fixed. |
| **Local DNS / Resolution Failure** | `error: failed to lookup address information: No address associated with hostname` | Local `redir-host` DNS failed to resolve domain before outbound dialing. | Fix `dns:` configuration (`default-nameserver`, `nameserver-policy`, or `respect-rules`). |
| **Node Transport Warning (`[WARN]`)** | `[WARN] [TCP] ... --> ... using <Node>`<br>`error: failed to dial WebSocket: unexpected status: 403 Forbidden` | Core is healthy and running. An individual proxy node failed handshake at remote server / CDN. | Normal for free/airport subscriptions. Automatic failover (`url-test`/`fallback`) will handle it. No config syntax edit needed. |
| **Normal Traffic / Routing (`[INFO] / [DEBUG]`)** | `[TCP] ... --> ... match Match(...) using ...` | Normal routing decision matching rules. | Informational only. |

---

## 2. Diagnosing `failed to dial WebSocket: unexpected status: 403 Forbidden`

### What It Means
- **The Core is Operating Normally**: This is **NOT** a configuration syntax error or module crash. The Mihomo core is actively routing traffic.
- **Node-level Handshake Failure**: The outbound proxy node uses WebSocket transport (e.g. VLESS+WS+TLS or VMess+WS+TLS, common with Cloudflare CDN or reverse proxies). When dialing the WebSocket endpoint, the remote server or Cloudflare edge returned `HTTP 403 Forbidden`.

### Common Triggers
1. **Dead or Expired Free/Airport Node**: A public subscription node's backend server is offline or revoked.
2. **Cloudflare WAF / Bot Management**: The CDN intercepted the WebSocket upgrade request with a managed challenge or IP block.
3. **Mismatched Host / Path**: The node's WebSocket path or SNI header does not match the server's backend configuration.
4. **Health Check Probing**: A strategy group (`url-test` or `fallback`) tested the node against `https://www.gstatic.com/generate_204`, caught the 403, and marked the node unhealthy.

### Resolution & Best Practices
- **No syntax changes needed**: Do not attempt to edit `config.yaml` syntax to fix a remote 403.
- **Ensure `tolerance` and `max-failed-times` are set**: In `url-test` groups, keep `tolerance: 50` and `max-failed-times: 3` so Mihomo quickly isolates dead nodes without flapping.
- **Update Subscription**: If all nodes in a group fail with 403, trigger a subscription update via UI or API.
