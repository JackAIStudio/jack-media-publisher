#!/usr/bin/env bash
#
# build.sh —— 重建「Chrome Silent.app」
#
# 用途：带 --silent-debugger-extension-api 启动 Chrome，隐藏调试横幅。
# 产物：~/Applications/Chrome Silent.app
#
# 依赖：iconutil / sips / ffmpeg（都是 macOS 自带或已装）、Google Chrome
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Chrome Silent"
APP="$HOME/Applications/$APP_NAME.app"
CHROME="/Applications/Google Chrome.app"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> 工作目录: $WORK"

# ---------- 1. 取 Chrome 图标 ----------
[ -d "$CHROME" ] || { echo "❌ 找不到 $CHROME" >&2; exit 1; }
ICNS_SRC="$CHROME/Contents/Resources/app.icns"
[ -f "$ICNS_SRC" ] || { echo "❌ 找不到 Chrome 的 icns" >&2; exit 1; }

echo "==> 提取 Chrome 图标"
iconutil -c iconset "$ICNS_SRC" -o "$WORK/chrome.iconset"

# 取可用的最大尺寸作为母版
BASE=""
for cand in icon_512x512@2x icon_256x256@2x icon_128x128@2x; do
  if [ -f "$WORK/chrome.iconset/$cand.png" ]; then BASE="$WORK/chrome.iconset/$cand.png"; break; fi
done
[ -n "$BASE" ] || BASE="$(ls -S "$WORK"/chrome.iconset/*.png | head -1)"
BASE_PX="$(sips -g pixelWidth "$BASE" | awk '/pixelWidth/{print $2}')"
echo "    母版: $(basename "$BASE")  ${BASE_PX}px"

# ---------- 2. 合成徽章 ----------
echo "==> 合成绿点徽章"
BADGE="$HERE/badge.png"
[ -f "$BADGE" ] || { echo "❌ 缺少 badge.png" >&2; exit 1; }

# 徽章按母版尺寸等比缩放（占约 34%）
BADGE_PX=$(( BASE_PX * 34 / 100 ))
sips -z "$BADGE_PX" "$BADGE_PX" "$BADGE" --out "$WORK/badge_scaled.png" >/dev/null
OFFSET=$(( BASE_PX - BADGE_PX - BASE_PX / 32 ))

ffmpeg -y -i "$BASE" -i "$WORK/badge_scaled.png" \
  -filter_complex "[0][1]overlay=${OFFSET}:${OFFSET}" \
  "$WORK/silent.png" -loglevel error

# ---------- 3. 生成各尺寸 ----------
echo "==> 生成图标尺寸"
mkdir -p "$WORK/silent.iconset"
for spec in "16 icon_16x16" "32 icon_16x16@2x" "32 icon_32x32" "64 icon_32x32@2x" \
            "128 icon_128x128" "256 icon_128x128@2x" "256 icon_256x256" \
            "512 icon_256x256@2x" "512 icon_512x512" "1024 icon_512x512@2x"; do
  px="${spec%% *}"; name="${spec##* }"
  sips -z "$px" "$px" "$WORK/silent.png" --out "$WORK/silent.iconset/$name.png" >/dev/null 2>&1
done
iconutil -c icns "$WORK/silent.iconset" -o "$WORK/AppIcon.icns"

# ---------- 4. 组装 .app ----------
echo "==> 组装 $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$HERE/Info.plist"            "$APP/Contents/Info.plist"
cp "$HERE/ChromeSilent"          "$APP/Contents/MacOS/ChromeSilent"
cp "$WORK/AppIcon.icns"          "$APP/Contents/Resources/AppIcon.icns"
chmod +x "$APP/Contents/MacOS/ChromeSilent"

# ---------- 5. 注册 ----------
touch "$APP"
LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREG" ] && "$LSREG" -f "$APP" 2>/dev/null || true

echo
echo "✅ 完成: $APP"
echo "   把它拖到 Dock 上即可使用。"
echo "   图标 = Chrome + 右下角绿点（用来和真 Chrome 区分）。"
