#!/usr/bin/env bash
# ==============================================================================
# ✨ Hermes Agent (楪祈) 一键极速克隆部署脚本
# 适用系统: Ubuntu 22.04+ / Debian 12+ (x86_64 / arm64)
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

if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

echo -e "\n${YELLOW}[1/5] 安装系统基础依赖...${NC}"
$SUDO apt-get update -y
$SUDO apt-get install -y curl wget git tar gzip jq sqlite3 python3 python3-pip python3-venv

echo -e "\n${YELLOW}[2/5] 安装 Hermes Agent 官方核心...${NC}"
if ! command -v hermes &> /dev/null; then
    echo "正在拉取并安装 Hermes CLI..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
fi

echo -e "\n${YELLOW}[3/5] 从 GitHub 克隆楪祈灵魂、长期记忆与 95 个专属技能库...${NC}"
TEMP_DIR=$(mktemp -d)
git clone --depth 1 https://github.com/rosc-bot/hermes-core-backup.git "$TEMP_DIR"

mkdir -p "$HOME/.hermes/memories"
mkdir -p "$HOME/.hermes/skills"
mkdir -p "$HOME/.hermes/telegram-monitor"

# 恢复灵魂与记忆
cp -r "$TEMP_DIR/SOUL.md" "$HOME/.hermes/" 2>/dev/null || true
cp -r "$TEMP_DIR/memories/"* "$HOME/.hermes/memories/" 2>/dev/null || true
cp -r "$TEMP_DIR/skills/"* "$HOME/.hermes/skills/" 2>/dev/null || true
cp -r "$TEMP_DIR/telegram_scripts/"* "$HOME/.hermes/telegram-monitor/" 2>/dev/null || true
rm -rf "$TEMP_DIR"

echo -e "\n${YELLOW}[4/5] 配置 Telegram 监听与 Python 虚拟环境...${NC}"
cd "$HOME/.hermes/telegram-monitor"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install telethon python-telegram-bot python-dotenv

# 配置 systemd 守护进程
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
