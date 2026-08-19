# NAT VPS / Container Port Mapping Guidelines

When deploying MTProto proxy (`mtg`) on NAT VPS or container environments:

1. **Internal vs External Ports**:
   - NAT VPS maps public host ports to internal container ports (e.g. host `14897` -> container `443`).
   - `mtg` `config.toml` MUST bind to internal port: `bind-to = "0.0.0.0:443"`.
   - Client proxy URL MUST use the public mapped port: `tg://proxy?server=<IP>&port=14897&secret=<SECRET>`.

2. **Boot / Reboot Initialization Delays**:
   - Immediately after booting or rebooting a NAT container, host node iptables rules or internal `sshd`/services may take 1-2 minutes to settle.
   - Probing ports during this window often returns `No route to host` or `Timed out`. Wait 1-2 minutes or check internal VNC console before assuming the port is wrong.
