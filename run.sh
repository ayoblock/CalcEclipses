#!/usr/bin/env bash
# CalcEclipses 一键启动（Linux / macOS）
#   1. 检查本地 Cesium，缺失则调用 tools/fetch_cesium.sh 获取（约 20MB，一次性）
#   2. 起本地静态服务（默认端口 8123，被占用时自动换空闲端口）
#   3. 自动打开浏览器
# 停止：Ctrl+C
set -euo pipefail
cd "$(dirname "$0")"

PORT_DEFAULT=8123

# ── 1. Cesium ──
if [ ! -f lib/cesium/Cesium.js ]; then
  echo "[run] 首次运行：获取本地 Cesium（约 20MB）..."
  command -v npm >/dev/null 2>&1 || {
    echo "[run] 需要 npm（Node.js）来获取 Cesium，请先安装：https://nodejs.org/" >&2
    exit 1
  }
  bash tools/fetch_cesium.sh
fi

# ── 2. Python ──
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || {
  echo "[run] 未找到 Python，请先安装：https://www.python.org/downloads/" >&2
  exit 1
}

# ── 3. 端口：默认 8123，被占用则取空闲端口 ──
port_free() { "$PY" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',$1))" >/dev/null 2>&1; }
if port_free "$PORT_DEFAULT"; then
  PORT=$PORT_DEFAULT
else
  PORT=$("$PY" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
  echo "[run] 端口 $PORT_DEFAULT 被占用，改用 $PORT"
fi

URL="http://127.0.0.1:$PORT/"

# ── 4. 延迟打开浏览器（等服务就绪），服务前台运行 ──
(
  sleep 1.5
  xdg-open "$URL" >/dev/null 2>&1 \
    || open "$URL" >/dev/null 2>&1 \
    || echo "[run] 请手动打开浏览器访问 $URL"
) &

echo "[run] 服务已启动：$URL（Ctrl+C 停止）"
exec "$PY" -m http.server "$PORT" --bind 127.0.0.1
