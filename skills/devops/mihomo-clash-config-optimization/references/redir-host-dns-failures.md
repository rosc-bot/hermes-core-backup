# Mihomo/Clash `redir-host` DNS Failure Troubleshooting

## The `[ConnectionException] error:failed to lookup address information: No address associated with hostname` Error

### Symptom
An app (like TeleDrive, Emby clients, or Telegram webhook servers) throws this error inside an Android Magisk/KernelSU proxy module environment (like SurfingTile).

### Root Cause
This is a **DNS Resolution Failure** at the local client level, not a remote firewall block (unlike a Cloudflare 403). In `redir-host` mode, the client device MUST resolve a domain to an IP address locally before the proxy can intercept the TCP connection. If the proxy's DNS module is misconfigured and returns no IP, the app fails immediately.

### Key Culprits in `redir-host` Configurations
1. **Missing `default-nameserver`**: If this is absent, Mihomo cannot resolve the IPs of DoH servers (like `cloudflare-dns.com`) during cold boot, leading to a total DNS deadlock.
   *Fix*: Add a pure-IP bootstrap list.
   ```yaml
   dns:
     default-nameserver:
       - 223.5.5.5
       - 1.1.1.1
   ```
2. **Malformed `nameserver-policy` Syntax**: Using comma-separated `RULE-SET` names is illegal and causes rule parsing to fail, leaking domestic domains to slow/blocked foreign DNS servers.
   *Fix*: Split them onto separate lines.
   ```yaml
   nameserver-policy:
     "RULE-SET:CN_域":
       - https://223.5.5.5/dns-query
     "RULE-SET:Apple_域":
       - https://223.5.5.5/dns-query
   ```
3. **Missing `respect-rules: true`**: Without this, the DNS module won't check the `rules:` list first to bypass local resolution for proxied domains, leading to pollution or timeout.

### Summary
If you see `No address associated with hostname`, fix your local `dns` block configuration. If you see `403 Forbidden` for a specific domain, fix your `sniffer` configuration (`force-domain`) to ensure SNI re-resolution at the proxy node.