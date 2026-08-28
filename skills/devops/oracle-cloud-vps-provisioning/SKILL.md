---
name: oracle-cloud-vps-provisioning
description: "Use when provisioning Oracle Cloud (OCI) VPS instances."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [OracleCloud, OCI, VPS, AlwaysFree, PAYG, Ubuntu, ARM, Networking, IPv6]
    related_skills: [ssh-server-access, telegram-proxy]
---

# Oracle Cloud Infrastructure (OCI) VPS Provisioning & Pitfalls

## When to Use
- User asks about Oracle Cloud (OCI / 甲骨文云) instance creation, PAYG (升级号) vs Always Free quotas.
- Selecting Ubuntu OS image versions (Ubuntu 22.04 LTS vs 24.04, ARM `aarch64` vs AMD `x86_64`).
- Configuring boot volume size and performance (10 VPU Balanced vs 20 VPU billable traps).
- Resolving VNIC networking issues: grayed-out public IPv4 / IPv6, private subnet traps, and disabling Shielded Instance (受防护实例).
- Ingress firewall rule and port exposure setup.

Use this skill when provisioning, configuring, or troubleshooting compute instances (VMs) on Oracle Cloud Infrastructure (OCI), specifically for Always Free and Pay-As-You-Go (PAYG / 升级号) accounts.

## 1. OCI Always Free & PAYG Quota Boundaries

| Resource Type | Always Free Allowance | Crucial Provisioning Rule |
| :--- | :--- | :--- |
| **ARM Ampere A1** | Up to **4 OCPU + 24 GB RAM** | Can be provisioned as 1 instance (4C/24G) or split (e.g. two 2C/12G). PAYG accounts get high scheduler priority and bypass out-of-capacity queueing. |
| **AMD Compute** | Up to 2 instances (`VM.Standard.E2.1.Micro`) | 1 OCPU + 1 GB RAM each. Useful for lightweight monitors or secondary proxies. |
| **Boot Volumes (Storage)** | **200 GB Total** across all instances | Default instance creation assigns ~46.6 GB. Set single instance boot volumes between 100 GB - 200 GB. Exceeding 200 GB total will incur billable charges. |
| **Boot Volume Performance** | **10 VPU (Balanced / 均衡)** | **ALWAYS select 10 VPU (Balanced)**. Never choose 20 VPU (Higher Performance), as VPU calculation above 10 incurs billable monthly fees even under 200 GB. |
| **Outbound Data Transfer** | **10 TB (10,240 GB)** / month | Free across all regions and compute shapes. |

## 2. OS Image Selection Guidelines

In the OCI Instance Creation Console, select the OS image matching the chosen CPU architecture:

- **For ARM (Ampere A1) Instances**:
  - **Recommended**: `Canonical Ubuntu 22.04 Minimal aarch64`.
  - *Why*: 22.04 LTS offers peak compatibility with Docker, BBR, Python venvs, and network tools. 20.04 is outdated; 24.04 has aggressive `netplan`/`systemd-resolved` changes that break common shell scripts.
  - *Critical*: Must contain `aarch64` in the image title, otherwise the ARM VM will fail to boot.
- **For AMD (x86_64) Instances**:
  - **Recommended**: `Canonical Ubuntu 22.04` (or `22.04 Minimal`).
  - *Critical*: Do NOT select `aarch64` for AMD machines.

## 3. High-Frequency Provisioning Traps & Pitfalls

### Pitfall 1: "Shielded Instance (受防护实例)" Must Be DISABLED
- **Symptom**: Custom kernel installations, BBRplus scripts, WireGuard modules, or DD reinstall scripts cause the VM to hang at GRUB with a black screen and complete network loss.
- **Root Cause**: Shielded Instance enforces UEFI `Secure Boot` and TPM measurement. Unsigned third-party kernels and custom network drivers fail cryptographic verification.
- **Action**: Always uncheck / disable **Shielded Instance (受防护实例)** during VM creation.

### Pitfall 2: Grayed-out "Assign public IPv4" & "Assign IPv6"
- **Symptom**: In the VNIC / Networking step, the switches for "Assign public IPv4 address" and "Assign IPv6 address" are disabled and show yellow warnings:
  - `必须选择公共子网才能分配公共 IPv4 地址`
  - `必须选择启用了 IPv6 的子网才能分配 IPv6 地址`
- **Root Cause**: The wizard defaulted to a **Private Subnet** (专用子网), which OCI forbids from holding public IPv4 addresses, and the default VCN lacked an IPv6 prefix. If created, the machine will have no public IP and will be unreachable via SSH.
- **Action**:
  1. Scroll up to **Subnet** selection and switch from `private-subnet` to **`public-subnet`**.
  2. Public IPv4 assignment will automatically illuminate and enable.
  3. For IPv6: Can be added post-boot by visiting OCI Console -> VCN -> IPv6 Prefixes -> Allocate Oracle-allocated IPv6 /56, assigning a /64 to the public subnet, and allocating an IPv6 to the VNIC.

### Pitfall 3: Ingress Firewall Security Lists
- By default, OCI security lists only allow incoming traffic on port 22 (SSH).
- All proxy ports (e.g. 443, 80, SOCKS5, Reality, Web UI 8648) will be dropped at the OCI hypervisor level unless explicitly added to the VCN's **Default Security List -> Ingress Rules** (CIDR: `0.0.0.0/0`, Protocol: All Protocols or specific TCP/UDP port ranges).
