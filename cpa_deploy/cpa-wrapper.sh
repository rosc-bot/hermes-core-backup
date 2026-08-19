#!/usr/bin/env bash
# CPA wrapper: 启动 CPA 并保持前台跟踪，让 systemd 能正确管理
set -u

CPA_BIN="/home/ubuntu/cliproxyapi/cli-proxy-api"
CPA_CONFIG="/home/ubuntu/cliproxyapi/config.yaml"
LOG="/home/ubuntu/cliproxyapi/logs/cpa.log"

cleanup() {
  echo "[wrapper] 停止 CPA..."
  if [ -n "${CPA_PID:-}" ] && kill -0 "$CPA_PID" 2>/dev/null; then
    kill "$CPA_PID" 2>/dev/null
  fi
}

trap cleanup EXIT INT TERM

# 若端口已被占用（残留进程），先清理
if ss -tln | grep -q ':8317 '; then
  echo "[wrapper] 8317 端口被占用，等待释放..."
  sleep 2
fi

echo "[wrapper] 启动 CPA..."
"$CPA_BIN" -config "$CPA_CONFIG" >>"$LOG" 2>&1 &

# CPA 会 fork，实际服务进程是它的子进程。找到监听 8317 的真实 PID
for i in $(seq 1 15); do
  REAL_PID=$(ss -tlnp 2>/dev/null | grep ':8317 ' | grep -oP 'pid=\K[0-9]+' | head -1)
  if [ -n "${REAL_PID:-}" ]; then
    echo "[wrapper] CPA 运行中 (PID $REAL_PID)"
    CPA_PID="$REAL_PID"
    break
  fi
  sleep 1
done

if [ -z "${CPA_PID:-}" ]; then
  echo "[wrapper] CPA 启动失败，查看日志：$LOG"
  tail -50 "$LOG"
  exit 1
fi

# 持续跟踪真实进程
while kill -0 "$CPA_PID" 2>/dev/null; do
  sleep 5
done

echo "[wrapper] CPA 进程退出"
exit 0
