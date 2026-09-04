# Oracle Cloud Infrastructure (OCI) Deployment & Firewall Optimization Guide

## 1. Instance Creation Best Practices (Always Free / PAYG)
- **OS Selection**: Prefer `Canonical Ubuntu 22.04 LTS` (or `Minimal aarch64` for Ampere A1). Avoid 24.04 (due to breaking netplan/systemd-resolved changes) and 20.04 (outdated libraries). For ARM instances, ALWAYS ensure the image has `aarch64` in the name.
- **Shielded Instance (受防护实例)**: ALWAYS keep DISABLED. Enabling Secure Boot / Measured Boot prevents BBRplus installation, custom kernel loading, WireGuard/TUN modules, and DD reinstallations due to strict TPM/UEFI signature enforcement.
- **Boot Volume Performance**: Always choose `Balanced (10 VPU)`. `Lower Cost (0 VPU)` suffers from heavy I/O throttling. `Higher Performance (20 VPU)` incurs recurring extra costs that exceed Always Free allowances.
- **Subnet Assignment**: In the networking step, MUST select `Public Subnet`. Selecting `Private Subnet` disables public IPv4 and IPv6 assignment.
- **Always Free Policy (2026)**: Free-tier accounts may have Ampere A1 allowances revoked or restricted in popular regions (e.g. Singapore, Tokyo). Upgraded accounts (Pay As You Go / PAYG) retain full 4 OCPU / 24GB RAM / 200GB storage without deletion or idle reclamation risk.

## 2. Two-Layer Firewall Rules for OCI
OCI instances have two layers of firewall that MUST both be opened:

### Layer 1: Cloud Web Console (Security Lists / VCN)
In OCI Console -> Networking -> Virtual Cloud Networks -> Subnet -> Security Lists -> Ingress Rules:
- **Stateless**: Unchecked (Stateful tracking)
- **Source Type**: CIDR (`0.0.0.0/0`)
- **IP Protocol & Destination Port Syntax Trap**:
  - **CRITICAL UI PITFALL**: OCI console's `Destination Port Range` field **DOES NOT support comma-separated discrete port lists** (e.g. `22,80,443` will fail validation). It only accepts:
    1. A single port (e.g. `443`)
    2. A contiguous range using hyphen (e.g. `80-443` or `3000-3001`)
    3. **Blank / Empty**: Leave it blank to open all ports (1-65535) for that protocol.
  - *Option A (Universal/Recommended for dev)*: IP Protocol = `All Protocols` (or leave Destination Port Range blank under TCP & UDP), allowing full host-level management via iptables.
  - *Option B (Strict)*: Add separate ingress rules for each discrete port or contiguous port range.

### Layer 2: Host Operating System (iptables-persistent)
Oracle Ubuntu images pre-seed blocking rules in `/etc/iptables/rules.v4`. Running raw `iptables -F` flushes memory only and resets on reboot. To permanently disable local blocking:
```bash
sudo iptables -P INPUT ACCEPT && sudo iptables -P FORWARD ACCEPT && sudo iptables -P OUTPUT ACCEPT && sudo iptables -F
sudo apt-get install -y iptables-persistent && sudo netfilter-persistent save
```

## 3. SSH Authentication Troubleshooting on OCI
When connecting to a newly created OCI instance via SSH:
- **Public Key vs Private Key**: The `.pub` file is the public key (only uploaded to OCI console at creation time). The private key (without `.pub`) MUST be used by the SSH client. Connecting with `.pub` will fail with `invalid format` or `Permission denied (publickey)`.
- **Default Usernames (Critical Pitfall)**:
  - Ubuntu images: `ubuntu` (Logging in as `root` directly fails with publickey refusal/handshake timeout).
  - Debian images: `admin` or `debian`.
  - Oracle Linux: `opc`.
- **`Timed out while waiting for handshake` / `USERAUTH_PK_OK` Hang**:
  If the log shows `Inbound: Received USERAUTH_PK_OK` followed by `Outbound: Sending USERAUTH_REQUEST (publickey)` and times out:
  1. Verify the username is `ubuntu` (not `root`).
  2. Check MTU / packet fragmentation on client network (large pubkey payload drop by ISP/proxies; try disabling local VPN/proxy).
  3. Avoid buggy embedded web SSH clients; test via standard OpenSSH (`ssh -i key ubuntu@<IP>`).
- **`SSH shell channel open timed out after 30000 ms`**:
  Common in Electron-based web/GUI SSH clients (1Panel, Tabby). Occurs when authentication succeeds but the remote PTY allocation hangs because the instance is busy with initial `cloud-init` / `unattended-upgrades`. Wait 2-3 minutes, reboot the instance via OCI console, or connect using native OpenSSH.
- **SSH Connection Drops & Freezes (Idle Timeout)**:
  OCI VCN and intermediate ISP NAT firewalls drop idle TCP sessions after 30-60s. Enable keepalive on the server:
  ```bash
  sudo bash -c 'cat >> /etc/ssh/sshd_config.d/keepalive.conf << EOF
  ClientAliveInterval 30
  ClientAliveCountMax 10
  EOF' && sudo systemctl restart ssh
  ```

## 4. Standard Service Ports Matrix
When migrating or restoring services across servers, standard ports include:
- `22`: SSH remote admin
- `80, 443`: Web (HTTP/HTTPS) & reality node masquerade
- `8648, 4888`: Hermes Web UI & assistant dashboard
- `8317`: CLIProxyAPI (CPA) management portal
- `3000, 3001`: Web apps / Uptime Kuma monitoring
- `5244, 15244`: AList file service
- `8096, 18096, 18097`: Emby / Jellyfin media streaming
- `8024, 18024`: NPS / FRP reverse proxy tunnels
- `9208, 12366`: Custom proxy / data relay ports
- `48640, 48648` (UDP): Hermes Web UI internal node broadcast
