#!/bin/sh
# Single-command local EventLens + official Harness startup.
# Read the API key from macOS Keychain only into this process environment.
# Never kill unrelated processes, print credentials, or write a .env file.
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "该一键脚本暂仅支持 macOS。" >&2
  exit 1
fi
if [ ! -x ".venv/bin/uvicorn" ] || [ ! -x ".venv/bin/python" ]; then
  echo "没有找到当前项目的 .venv，请先完成 README 中的环境安装。" >&2
  exit 1
fi
for tool in /usr/bin/security /usr/sbin/lsof /usr/bin/curl; do
  if [ ! -x "$tool" ]; then
    echo "缺少系统工具：$tool" >&2
    exit 1
  fi
done

check_port() {
  if /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "端口 $1 已被占用：不会结束现有进程。" >&2
    /usr/sbin/lsof -nP -iTCP:"$1" -sTCP:LISTEN >&2 || true
    echo "请先停止现有 EventLens/Harness，确认端口释放后再启动。" >&2
    return 1
  fi
}
check_port 8765
check_port 3080

ACCOUNT="$(id -un)"
SERVICE="com.eventlens.deepseek.api-key"
if ! DEEPSEEK_API_KEY="$(/usr/bin/security find-generic-password -a "$ACCOUNT" -s "$SERVICE" -w 2>/dev/null)"; then
  echo "未能读取 DeepSeek Key。首次使用先运行：sh scripts/setup_keychain.sh" >&2
  echo "如果 macOS 弹出钥匙串授权窗口，请在本机允许访问。" >&2
  exit 1
fi
if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "钥匙串中的 DeepSeek Key 为空，请重新运行初始化脚本。" >&2
  exit 1
fi
export DEEPSEEK_API_KEY

eventlens_pid=""
harness_pid=""
cleanup() {
  trap - EXIT INT TERM
  echo ""
  echo "正在停止本次启动的 EventLens 和 Harness……"
  if [ -n "$harness_pid" ]; then kill -TERM "$harness_pid" 2>/dev/null || true; fi
  if [ -n "$eventlens_pid" ]; then kill -TERM "$eventlens_pid" 2>/dev/null || true; fi
  if [ -n "$harness_pid" ]; then wait "$harness_pid" 2>/dev/null || true; fi
  if [ -n "$eventlens_pid" ]; then wait "$eventlens_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "启动 EventLens（127.0.0.1:8765）……"
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8765 &
eventlens_pid=$!

count=0
while [ "$count" -lt 45 ]; do
  if ! kill -0 "$eventlens_pid" 2>/dev/null; then
    echo "EventLens 意外退出，请查看上面的服务日志。" >&2
    exit 1
  fi
  if /usr/bin/curl --silent --fail --max-time 2 --output /dev/null http://127.0.0.1:8765/api/health; then
    break
  fi
  count=$((count + 1))
  sleep 1
done
if [ "$count" -ge 45 ]; then
  echo "EventLens 未在 45 秒内启动完成。" >&2
  exit 1
fi

echo "启动 DeepSeek Harness（127.0.0.1:3080）……"
sh scripts/start_harness.sh &
harness_pid=$!

count=0
registered=0
while [ "$count" -lt 60 ]; do
  if ! kill -0 "$harness_pid" 2>/dev/null; then
    echo "Harness 启动失败，请查看上方日志（尤其是端口3080）。" >&2
    exit 1
  fi
  code="$(/usr/bin/curl --silent --max-time 3 --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8765/harness/open || true)"
  if [ "$code" = "307" ]; then
    registered=1
    break
  fi
  count=$((count + 1))
  sleep 1
done
if [ "$registered" -ne 1 ]; then
  echo "Harness 未在 60 秒内登记成功，请检查上方日志。" >&2
  exit 1
fi

echo ""
echo "EventLens + Harness 已连接：http://127.0.0.1:8765/workstation"
echo "请保持本终端打开；要停止两项服务，在这里按 Control + C。"
while kill -0 "$harness_pid" 2>/dev/null && kill -0 "$eventlens_pid" 2>/dev/null; do
  sleep 2
done
echo "其中一项服务已退出；正在清理本次启动的进程。" >&2
exit 1
