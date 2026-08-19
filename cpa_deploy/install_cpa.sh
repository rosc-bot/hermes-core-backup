#!/usr/bin/env bash
# ==========================================
# CPA (CLIProxyAPI) 极速独立部署脚本
# ==========================================
set -e
CPA_DIR="$HOME/cliproxyapi"
mkdir -p "$CPA_DIR"/{auths,logs,package}

# 下载 CPA 官方最新 Linux-x86_64 二进制 (或通过发布源安装)
echo "正在安装 CPA 代理引擎..."
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    ARCH_NAME="linux-amd64"
elif [ "$ARCH" = "aarch64" ]; then
    ARCH_NAME="linux-arm64"
else
    ARCH_NAME="linux-amd64"
fi

# 若本地有二进制则解压，否则拉取
if [ -f "$CPA_DIR/cli-proxy-api" ]; then
    chmod +x "$CPA_DIR/cli-proxy-api"
else
    echo "拉取 CPA 最新二进制程序..."
    # 官方发布源拉取
    wget -qO /tmp/cpa.tar.gz "https://github.com/router-for-all/cli-proxy-api/releases/latest/download/cli-proxy-api-${ARCH_NAME}.tar.gz" || true
    if [ -f /tmp/cpa.tar.gz ]; then
        tar -xzf /tmp/cpa.tar.gz -C "$CPA_DIR/"
        chmod +x "$CPA_DIR/cli-proxy-api"
    fi
fi

# 写入默认配置与包装脚本
cp cpa_deploy/config.yaml.template "$CPA_DIR/config.yaml" 2>/dev/null || true
cp cpa_deploy/cpa-wrapper.sh "$CPA_DIR/cpa-wrapper.sh" 2>/dev/null || true
chmod +x "$CPA_DIR/cpa-wrapper.sh" 2>/dev/null || true

# 配置 CPA systemd 守护进程
sudo tee /etc/systemd/system/cpa.service > /dev/null << SYSTEMD
[Unit]
Description=CLIProxyAPI (CPA) - API Proxy Server
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$CPA_DIR
ExecStart=$CPA_DIR/cpa-wrapper.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD

sudo systemctl daemon-reload
sudo systemctl enable --now cpa.service
echo "✓ CPA 服务部署成功，监听端口: 8317"
