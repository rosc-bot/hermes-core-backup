#!/usr/bin/env bash
# ==============================================================================
# Hermes Agent & 楪祈一键全量部署脚本
# 适用系统: Ubuntu 22.04 / 24.04 / Debian 12 / Debian 13 (x86_64 / aarch64)
# ==============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}       ✨ 正在启动 Hermes Agent (楪祈) 一键克隆安装 ✨${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. 基础环境检测与依赖安装
echo -e "\n${YELLOW}[1/6] 检查并安装系统基础依赖...${NC}"
if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

$SUDO apt-get update -y
$SUDO apt-get install -y curl wget git tar gzip jq sqlite3 python3 python3-pip python3-venv

# 2. 安装官方 Hermes Agent 核心
echo -e "\n${YELLOW}[2/6] 安装 Hermes Agent 官方核心...${NC}"
if ! command -v hermes &> /dev/null; then
    echo "正在拉取并安装 Hermes CLI..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
fi

# 3. 创建目录并恢复核心记忆与技能库
echo -e "\n${YELLOW}[3/6] 注入楪祈灵魂、长期记忆与 95 个专属技能库...${NC}"
mkdir -p "$HOME/.hermes/memories"
mkdir -p "$HOME/.hermes/skills"
mkdir -p "$HOME/.hermes/telegram-monitor"

# 从 GitHub 或指定源拉取核心包 (若为本地离线包则直接解压)
BUNDLE_URL="${BUNDLE_URL:-}"
if [ -n "$BUNDLE_URL" ]; then
    echo "从远程源下载核心资产包: $BUNDLE_URL"
    curl -fsSL "$BUNDLE_URL" -o /tmp/hermes_core_bundle.tar.gz
    tar -xzf /tmp/hermes_core_bundle.tar.gz -C "$HOME/.hermes/"
    # 移动 telegram 脚本
    if [ -d "$HOME/.hermes/telegram_scripts" ]; then
        mv "$HOME/.hermes/telegram_scripts/"* "$HOME/.hermes/telegram-monitor/" 2>/dev/null || true
        rm -rf "$HOME/.hermes/telegram_scripts"
    fi
fi

# 4. 配置 Python 虚拟环境与 TG 监听工具链
echo -e "\n${YELLOW}[4/6] 配置 Python 虚拟环境与工具链...${NC}"
cd "$HOME/.hermes/telegram-monitor"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install telethon python-telegram-bot python-dotenv

# 5. 配置 systemd 守护进程
echo -e "\n${YELLOW}[5/6] 配置自启动服务 (Telegram Gateway & 监听守护)...${NC}"
# 生成 tg-monitor 服务
cat << EOF | $SUDO tee /etc/systemd/system/tg-monitor.service > /dev/null
[Unit]
Description=Telegram Group Chat Monitor (user account)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/.hermes/telegram-monitor
ExecStart=$HOME/.hermes/telegram-monitor/.venv/bin/python $HOME/.hermes/telegram-monitor/tg_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload

# 6. 完成并提示
echo -e "\n${BLUE}======================================================${NC}"
echo -e "${GREEN}🎉 楪祈的核心大脑与技能已在新机器克隆部署完毕！${NC}"
echo -e "${BLUE}======================================================${NC}"
echo -e "${YELLOW}👉 接下来只需最后一步接入配置：${NC}"
echo -e "1. 执行 ${GREEN}hermes setup${NC} 或编辑 ${GREEN}~/.hermes/.env${NC} 填入你的 Telegram Bot Token 与 AI 模型 Key。"
echo -e "2. 启动网关服务: ${GREEN}hermes gateway install --system --start-now${NC}"
echo -e "3. 启动群监听:   ${GREEN}sudo systemctl enable --now tg-monitor.service${NC}"
echo -e "${BLUE}======================================================${NC}"
