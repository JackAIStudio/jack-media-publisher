#!/bin/sh
# 保留原入口。前台 Python 进程持有文件与监听端口，退出即释放。
set -eu
command -v python3 >/dev/null 2>&1 || { echo '需要 Python 3 才能交付素材。' >&2; exit 1; }
exec python3 -EsB "$(dirname "$0")/serve_media.py" "$@"
