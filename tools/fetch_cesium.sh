#!/usr/bin/env bash
# 一次性获取本地 Cesium 1.120 构建产物到 lib/cesium/（约 20MB）。
# 依据：npm 包 cesium@1.120 的 Build/Cesium（压缩版，含 Workers/Assets/Widgets/ThirdParty）。
# 项目禁止回退 CDN：Cesium Workers 动态导入在 CDN 下会失败导致渲染循环停止。
set -euo pipefail
cd "$(dirname "$0")/.."

VER="1.120"
DEST="lib/cesium"

if [ -f "$DEST/Cesium.js" ]; then
  echo "lib/cesium 已存在，跳过（如需重装请先删除 $DEST）"
  exit 0
fi

command -v npm >/dev/null 2>&1 || { echo "需要 npm（Node.js）"; exit 1; }

echo "下载 cesium@$VER ..."
TGZ="$(npm pack cesium@$VER --silent | tail -1)"
echo "解压 $TGZ ..."
tar -xzf "$TGZ" package/Build/Cesium
mkdir -p lib
rm -rf "$DEST"
mv package/Build/Cesium "$DEST"
rm -rf package "$TGZ"

echo "完成：$DEST"
ls "$DEST"
