#!/usr/bin/env bash
# ==============================================================================
# ✨ Hermes Agent (楪祈) 全生态一键克隆安装脚本
# 包含: Hermes Agent 核心 + 95技能 + 长期记忆花名册 + 定时任务 + CPA代理面板 + TG全天候监听
# ==============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}    ✨ 正在启动 Hermes Agent (楪祈) 全生态一键克隆部署 ✨${NC}"
echo -e "${BLUE}================================================================${NC}"

if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

# 1. 基础系统依赖
echo -e "\n${YELLOW}[1/6] 安装系统基础运行环境与依赖...${NC}"
$SUDO apt-get update -y
$SUDO apt-get install -y curl wget git tar gzip jq sqlite3 python3 python3-pip python3-venv

# 2. 安装 Hermes Agent 官方核心
echo -e "\n${YELLOW}[2/6] 部署 Hermes Agent 官方最新核心...${NC}"
if ! command -v hermes &> /dev/null; then
    echo "正在拉取并安装 Hermes CLI..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
fi

# 3. 克隆并恢复楪祈大脑、记忆、技能、定时任务与工具链
echo -e "\n${YELLOW}[3/6] 从 GitHub 克隆楪祈灵魂、记忆、95个技能与定时任务...${NC}"
TEMP_DIR=$(mktemp -d)
git clone --depth 1 https://github.com/rosc-bot/hermes-core-backup.git "$TEMP_DIR"

mkdir -p "$HOME/.hermes/memories"
mkdir -p "$HOME/.hermes/skills"
mkdir -p "$HOME/.hermes/cron"
mkdir -p "$HOME/.hermes/telegram-monitor"
mkdir -p "$HOME/cliproxyapi"/{auths,logs,package}

# 注入灵魂、记忆、技能
cp -r "$TEMP_DIR/SOUL.md" "$HOME/.hermes/" 2>/dev/null || true
cp -r "$TEMP_DIR/memories/"* "$HOME/.hermes/memories/" 2>/dev/null || true
cp -r "$TEMP_DIR/skills/"* "$HOME/.hermes/skills/" 2>/dev/null || true
cp -r "$TEMP_DIR/telegram_scripts/"* "$HOME/.hermes/telegram-monitor/" 2>/dev/null || true

# 注入 Cron 定时任务 (每日安全检查、垃圾清理、Hermes自动更新)
if [ -f "$TEMP_DIR/cron/jobs.json" ]; then
    cp "$TEMP_DIR/cron/jobs.json" "$HOME/.hermes/cron/jobs.json"
    echo "✓ 3个每日定时任务（01:00安全检查/更新、02:00垃圾清理、Hermes自动升级）已恢复"
fi

# 4. 部署 Telegram 监听环境与守护服务
echo -e "\n${YELLOW}[4/6] 配置 Telegram 50+群聊监听虚拟环境与自启动守护...${NC}"
cd "$HOME/.hermes/telegram-monitor"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install telethon python-telegram-bot python-dotenv

cat << TGSERVICE | $SUDO tee /etc/systemd/system/tg-monitor.service > /dev/null
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
TGSERVICE

# 5. 部署 CPA (CLIProxyAPI) 代理面板
echo -e "\n${YELLOW}[5/6] 部署 CPA (CLIProxyAPI) 代理面板与服务...${NC}"
cd "$TEMP_DIR"
if [ -d "cpa_deploy" ]; then
    bash cpa_deploy/install_cpa.sh || true
fi
rm -rf "$TEMP_DIR"

$SUDO systemctl daemon-reload

echo -e "\n${BLUE}================================================================${NC}"
echo -e "${GREEN}🎉 恭喜爸爸！Hermes (楪祈) + CPA 面板 + TG 监听 + 定时任务 全量克隆完毕！${NC}"
echo -e "${BLUE}================================================================${NC}"
echo -e "${YELLOW}👉 快速启用指引：${NC}"
echo -e "1. 【Hermes 配置】: 运行 ${GREEN}hermes setup${NC} 填入 TG Bot Token 与 API Key，然后运行 ${GREEN}hermes gateway install --system --start-now${NC}"
echo -e "2. 【TG 群聊监听】: 首次运行 ${GREEN}cd ~/.hermes/telegram-monitor && .venv/bin/python tg_monitor.py --test${NC} 登录监听账号，然后 ${GREEN}sudo systemctl enable --now tg-monitor.service${NC}"
echo -e "3. 【CPA 代理面板】: 浏览器访问 ${GREEN}http://<新服务器IP>:8317/management.html${NC} 管理多账号与额度！"
echo -e "4. 【定时任务状态】: 运行 ${GREEN}hermes cron list${NC} 即可查看已恢复的 3 个每日定时任务！"
echo -e "${BLUE}================================================================${NC}"
