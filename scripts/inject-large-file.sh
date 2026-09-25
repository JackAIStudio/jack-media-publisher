#!/usr/bin/env bash
#
# inject-large-file.sh —— 把大文件投递进浏览器页面，绕开 bsk 的 512MB 限制
#
# 原理：起一个带 CORS 的本地 HTTP 服务，让页面自己 fetch 成 File 对象再注入。
#      文件字节完全不经过 bsk 的传输通道，因此没有大小上限，也不消耗会话额度。
#
# 用法：
#   ./inject-large-file.sh <file> <selector> [--session <id>] [--tab-id <id>] [--port 8899]
#
# 示例：
#   ./inject-large-file.sh ~/video.mp4 'input.upload-input'
#   ./inject-large-file.sh ~/video.mp4 '.bcc-upload-wrapper input[type=file]' --session abc
#
set -euo pipefail

FILE=""; SELECTOR=""; SESSION=""; TAB_ID=""; PORT=8899
while [ $# -gt 0 ]; do
  case "$1" in
    --session) SESSION="$2"; shift 2 ;;
    --tab-id)  TAB_ID="$2";  shift 2 ;;
    --port)    PORT="$2";    shift 2 ;;
    -*)        echo "未知参数: $1" >&2; exit 2 ;;
    *)         if [ -z "$FILE" ]; then FILE="$1"; else SELECTOR="$1"; fi; shift ;;
  esac
done

[ -n "$FILE" ] && [ -n "$SELECTOR" ] || {
  echo "用法: $0 <file> <selector> [--session <id>] [--tab-id <id>] [--port 8899]" >&2; exit 2
}
[ -f "$FILE" ] || { echo "文件不存在: $FILE" >&2; exit 1; }

FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"
BASENAME="$(basename "$FILE")"
SIZE="$(stat -f%z "$FILE")"

# 按扩展名猜 MIME
case "${BASENAME##*.}" in
  mp4|m4v) MIME="video/mp4" ;;
  mov)     MIME="video/quicktime" ;;
  png)     MIME="image/png" ;;
  jpg|jpeg) MIME="image/jpeg" ;;
  *)       MIME="application/octet-stream" ;;
esac

echo "文件    : $BASENAME"
echo "大小    : $SIZE 字节 ($(echo "scale=1; $SIZE/1048576" | bc) MiB)"
echo "MIME    : $MIME"
echo "选择器  : $SELECTOR"

if [ "$SIZE" -gt 536870912 ]; then
  echo "提示    : 超过 512 MiB，bsk 原生 upload 会拒绝 —— 正是本脚本的用武之地"
fi

# ---- 1. 起本地服务（只服务该文件所在目录）----
SERVE_DIR="$(dirname "$FILE")"
python3 - "$SERVE_DIR" "$PORT" <<'PY' &
import http.server, socketserver, os, sys
os.chdir(sys.argv[1])
port = int(sys.argv[2])
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", port), H) as h:
    h.serve_forever()
PY
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

sleep 1.5
if ! curl -sI --max-time 5 "http://127.0.0.1:$PORT/$BASENAME" | head -1 | grep -q 200; then
  echo "❌ 本地服务未就绪" >&2; exit 1
fi
echo "服务    : http://127.0.0.1:$PORT/$BASENAME ✅"

# ---- 2. 页面内注入 ----
# URL 编码文件名（中文 / 空格）
URL_PATH="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$BASENAME")"

JS="$(cat <<JS
(async () => {
  const t0 = Date.now();
  try {
    const r = await fetch('http://127.0.0.1:$PORT/$URL_PATH');
    if (!r.ok) return JSON.stringify({ ok: false, step: 'fetch', status: r.status });
    const b = await r.blob();
    const inp = document.querySelector('$SELECTOR');
    if (!inp) return JSON.stringify({ ok: false, step: 'find-input' });
    const dt = new DataTransfer();
    dt.items.add(new File([b], '$BASENAME', { type: '$MIME' }));
    inp.files = dt.files;
    const size = inp.files[0].size, attached = inp.files.length;
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    inp.dispatchEvent(new Event('input',  { bubbles: true }));
    return JSON.stringify({ ok: true, ms: Date.now() - t0, size, attached });
  } catch (e) {
    return JSON.stringify({ ok: false, err: String(e).slice(0, 140) });
  }
})()
JS
)"

BSK="${BSK:-bsk}"
ARGS=()
[ -n "$SESSION" ] && ARGS+=(--session "$SESSION")
[ -n "$TAB_ID" ]  && ARGS+=(--tab-id "$TAB_ID")

echo "注入中   ..."
RESULT="$("$BSK" evaluate "${ARGS[@]}" --timeout 240s "$JS" 2>&1 | tail -1)"
echo "结果    : $RESULT"

case "$RESULT" in
  *'"ok":true'*) echo "✅ 注入完成 —— 立刻独立验收页面状态，不要只看这个回执" ;;
  *)             echo "❌ 注入失败" >&2; exit 1 ;;
esac
