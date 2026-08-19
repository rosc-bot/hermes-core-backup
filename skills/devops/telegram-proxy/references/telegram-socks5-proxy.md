# Telegram SOCKS5 Proxy Deployment Guide

## Overview
While MTProto (`mtg`) is ideal for raw direct connection to Telegram, standard **SOCKS5 with username/password authentication** is superior when:
1. User is already in a VPN / Proxy client (Clash, Sing-box, Surge) environment where TLS-obfuscated MTProto encounters TLS handshake/domain routing conflicts.
2. User needs low-latency Telegram voice/video calls (SOCKS5 natively forwards UDP).
3. Low memory footprint on constrained NAT VPS (Xray SOCKS5 runs in ~15MB RAM).

## Xray SOCKS5 Setup

### 1. Inbound Configuration (`/usr/local/etc/xray/config.json`)
```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 30810,
      "protocol": "socks",
      "settings": {
        "auth": "password",
        "accounts": [
          {
            "user": "tgsocks",
            "pass": "tgpass888"
          }
        ],
        "udp": true
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct",
      "settings": {
        "domainStrategy": "UseIPv4"
      }
    }
  ]
}
```

### 2. Service Management
```bash
systemctl restart xray
systemctl is-active xray
```

### 3. Click-to-Connect Telegram Link Formats
- Telegram App Deep Link:
  `tg://socks?server=<SERVER_IP>&port=<PORT>&user=<USERNAME>&pass=<PASSWORD>`
- Telegram Web Link:
  `https://t.me/socks?server=<SERVER_IP>&port=<PORT>&user=<USERNAME>&pass=<PASSWORD>`
