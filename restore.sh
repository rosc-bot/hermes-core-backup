#!/usr/bin/env bash
# ==============================================================================
# ✨ 楪祈与 Hermes Agent 全系统一键无损迁移复原脚本 ✨
# 适用环境: Ubuntu / Debian (x86_64 / aarch64)
# 功能: 在全新服务器上一键还原全部技能、记忆、配置、TG群监听、emos签到机器人及面板服务
# ==============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(eval echo "~$TARGET_USER")"

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}       ✨ 正在启动 楪祈 (Hermes Agent) 一键全量复原 ✨${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. 基础系统依赖检测
echo -e "\n${YELLOW}[1/7] 检查并安装基础环境与工具链...${NC}"
if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

$SUDO apt-get update -y
$SUDO apt-get install -y curl wget git tar gzip jq sqlite3 rsync python3 python3-pip python3-venv

# 2. 检查或安装 Hermes Agent 官方核心
echo -e "\n${YELLOW}[2/7] 检查 Hermes 官方核心引擎...${NC}"
if ! command -v hermes &> /dev/null; then
    echo -e "${CYAN}正在安装 Hermes CLI...${NC}"
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
    export PATH="$TARGET_HOME/.hermes/bin:$TARGET_HOME/.local/bin:$PATH"
fi

# 3. 还原核心配置、灵魂人设与记忆库
echo -e "\n${YELLOW}[3/7] 注入楪祈核心灵魂、长期记忆与主配置...${NC}"
mkdir -p "$TARGET_HOME/.hermes/memories"
mkdir -p "$TARGET_HOME/.hermes/cron"
mkdir -p "$TARGET_HOME/.hermes/scripts"

[ -f "$SCRIPT_DIR/config.yaml" ] && cp "$SCRIPT_DIR/config.yaml" "$TARGET_HOME/.hermes/config.yaml"
[ -f "$SCRIPT_DIR/SOUL.md" ] && cp "$SCRIPT_DIR/SOUL.md" "$TARGET_HOME/.hermes/SOUL.md"
[ -d "$SCRIPT_DIR/memories" ] && cp -r "$SCRIPT_DIR/memories/"* "$TARGET_HOME/.hermes/memories/"
[ -f "$SCRIPT_DIR/cron/jobs.json" ] && cp "$SCRIPT_DIR/cron/jobs.json" "$TARGET_HOME/.hermes/cron/jobs.json"

# 4. 全量还原 80+ 核心技能库
echo -e "\n${YELLOW}[4/7] 全量同步核心技能库与专属定制插件...${NC}"
if [ -d "$SCRIPT_DIR/skills" ]; then
    mkdir -p "$TARGET_HOME/.hermes/skills"
    rsync -a "$SCRIPT_DIR/skills/" "$TARGET_HOME/.hermes/skills/"
fi

# 5. 还原群聊监听与人🐔局白嫖知识库套件
echo -e "\n${YELLOW}[5/7] 配置 Telegram 54群监听与白嫖知识库套件...${NC}"
mkdir -p "$TARGET_HOME/.hermes/telegram-monitor"
if [ -d "$SCRIPT_DIR/telegram-monitor" ]; then
    rsync -a "$SCRIPT_DIR/telegram-monitor/" "$TARGET_HOME/.hermes/telegram-monitor/"
fi
cd "$TARGET_HOME/.hermes/telegram-monitor"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install telethon python-telegram-bot python-dotenv requests || true

# 6. 还原 emos 签到机器人套件
echo -e "\n${YELLOW}[6/7] 还原 emos 官方 OAuth 签到机器人套件...${NC}"
if [ -d "$SCRIPT_DIR/emos_checkin" ]; then
    cp "$SCRIPT_DIR/emos_checkin/emos_bot.py" "$TARGET_HOME/emos_bot.py" 2>/dev/null || true
    cp "$SCRIPT_DIR/emos_checkin/emos_db.py" "$TARGET_HOME/emos_db.py" 2>/dev/null || true
    cp "$SCRIPT_DIR/emos_checkin/emos_sign.py" "$TARGET_HOME/emos_sign.py" 2>/dev/null || true
    cp "$SCRIPT_DIR/emos_checkin/emos_sign.py" "$TARGET_HOME/.hermes/scripts/emos_sign.py" 2>/dev/null || true
    chmod +x "$TARGET_HOME/.hermes/scripts/emos_sign.py"
fi

# 7. 注册并重载系统守护服务 (Systemd)
echo -e "\n${YELLOW}[7/7] 注册开机自启系统守护进程...${NC}"
if [ -d "$SCRIPT_DIR/systemd" ]; then
    $SUDO cp "$SCRIPT_DIR/systemd/"*.service /etc/systemd/system/
    $SUDO systemctl daemon-reload
    
    # 启用关键守护
    $SUDO systemctl enable emos-bot.service 2>/dev/null || true
    $SUDO systemctl enable tg-monitor.service 2>/dev/null || true
    $SUDO systemctl enable hermes-gateway.service 2>/dev/null || true
    $SUDO systemctl enable hermes-web-ui.service 2>/dev/null || true
fi

# 修正权限
chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.hermes" "$TARGET_HOME/emos_bot.py" "$TARGET_HOME/emos_db.py" 2>/dev/null || true

echo -e "\n${BLUE}======================================================${NC}"
echo -e "${GREEN}🎉 恭喜爸爸！楪祈全部记忆、技能与机器人已 100% 满血复原！${NC}"
echo -e "${BLUE}======================================================${NC}"
echo -e "${CYAN}提示：${NC}"
echo -e "1. 启动 emos 签到机器人:  ${YELLOW}sudo systemctl start emos-bot.service${NC}"
echo -e "2. 启动 Telegram 监听:    ${YELLOW}sudo systemctl start tg-monitor.service${NC}"
echo -e "3. 启动 Hermes 网关:       ${YELLOW}sudo systemctl start hermes-gateway.service${NC}"
echo -e "${BLUE}======================================================${NC}\n"

# 8. 还原 Docker 容器编排套件 (可选部署)
if command -v docker &> /dev/null && [ -d "$SCRIPT_DIR/docker_services" ]; then
    echo -e "\n${YELLOW}[8/8] 检测到 Docker 环境，准备同步容器化套件...${NC}"
    mkdir -p "$TARGET_HOME/emos-bot-docker"
    mkdir -p "$TARGET_HOME/telegram-monitor-docker"
    mkdir -p "$TARGET_HOME/quote-api"
    mkdir -p "$TARGET_HOME/bemby"

    rsync -a "$SCRIPT_DIR/docker_services/emos-bot-docker/" "$TARGET_HOME/emos-bot-docker/"
    rsync -a "$SCRIPT_DIR/docker_services/telegram-monitor-docker/" "$TARGET_HOME/telegram-monitor-docker/"
    rsync -a "$SCRIPT_DIR/docker_services/quote-api/" "$TARGET_HOME/quote-api/"
    rsync -a "$SCRIPT_DIR/docker_services/bemby/" "$TARGET_HOME/bemby/"
    echo -e "${GREEN}✓ Docker 服务配置文件已同步就绪${NC}"
fi
