"""将明确选择的一个素材交付给一个创作者后台。仅使用 Python 标准库。"""

import argparse
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import socket
import stat
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


DRAFT_PATHS = {
    "https://channels.weixin.qq.com": ("/platform/post/create", "/platform/post/edit"),
    "https://creator.xiaohongshu.com": ("/publish/publish",),
    "https://creator.douyin.com": ("/creator-micro/content/upload", "/creator-micro/content/publish"),
    "https://member.bilibili.com": ("/platform/upload/video/frame",),
}
MEDIA_TYPES = {
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
    ".webm": "video/webm", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
    ".flv": "video/x-flv", ".ts": "video/mp2t", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}
USAGE = "inject-large-file.sh FILE --serve-only --origin ORIGIN [--port PORT] [--timeout SECONDS]"


class UsageError(ValueError):
    """启动参数需要用户修正。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError("参数有误，请检查文件、选项及其取值。用法：\n  " + USAGE)


def arguments():
    parser = Parser(prog="inject-large-file.sh", usage=USAGE, allow_abbrev=False,
                    description="前台交付一个本机素材。首行输出 JSON，一次完整 GET 后关闭。",
                    epilog="独立 CLI：FILE SELECTOR --session ID [--tab-id ID] [--origin ORIGIN]。可用 Origin："
                           + "、".join(DRAFT_PATHS))
    parser.add_argument("file", metavar="FILE", type=Path, help="明确选择的普通视频或图片文件")
    parser.add_argument("selector", nargs="?", help="独立 CLI 中已确认的文件输入框 CSS 选择器")
    parser.add_argument("--serve-only", action="store_true", help="仅启动本机单文件服务")
    parser.add_argument("--origin", help="已核对的创作者后台 HTTPS Origin，不带路径")
    parser.add_argument("--port", default="0", help="监听端口，默认 0（由系统分配）")
    parser.add_argument("--timeout", default="240", help="服务总时限（秒），1–600，默认 240")
    parser.add_argument("--session", help="旧版浏览器会话参数")
    parser.add_argument("--tab-id", help="旧版标签页参数")
    args = parser.parse_args() if "--" in sys.argv[1:] else parser.parse_intermixed_args()
    for key, low, high, label in (("port", 0, 65535, "端口"), ("timeout", 1, 600, "时限")):
        raw = getattr(args, key)
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 5 or not low <= int(raw) <= high:
            raise UsageError(f"{label}必须是 {low} 到 {high} 之间的整数。")
        setattr(args, key, int(raw))
    if args.origin is not None and args.origin not in DRAFT_PATHS:
        raise UsageError("请使用以下后台之一的确切 HTTPS Origin：\n  " + "\n  ".join(DRAFT_PATHS))
    if args.serve_only:
        if args.origin is None:
            raise UsageError("--serve-only 需要 --origin，并指定已授权后台的确切 HTTPS Origin。")
        if any(x is not None for x in (args.selector, args.session, args.tab_id)):
            raise UsageError("--serve-only 只接受素材、Origin、端口和时限。请在浏览器侧核对会话、标签页与控件。")
    return args


def migration(args):
    origin = args.origin or '"$ORIGIN"'
    path = str(args.file.absolute())
    file_arg = shlex.quote(path) if path.isprintable() else '"$FILE"'
    command = f'./scripts/inject-large-file.sh {file_arg} --serve-only --origin {origin}'
    if args.port:
        command += f" --port {args.port}"
    if args.timeout != 240:
        command += f" --timeout {args.timeout}"
    return ("请先人工核对草稿和文件选择状态。可在页面手动操作。若宿主要求 bsk_*，"
            "在确认可交付、取得授权后使用以下单文件入口：\n  " + command +
            "\n可用 ORIGIN：\n  " + "\n  ".join(DRAFT_PATHS))


class Handler(BaseHTTPRequestHandler):
    timeout = 5  # 空闲连接让出监听；整个服务另有总时限。

    def log_message(self, *args):
        pass  # 临时 URL 仅输出给调用方一次。

    def reply(self, status, length=0, **headers):
        self.send_response_only(status)
        if status != 204:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()

    def parse_request(self):
        if not super().parse_request():
            return False
        self.close_connection = True
        host = self.headers.get_all("Host")
        standard_port = self.server.server_port == 80 and host == ["127.0.0.1"]
        if host != [self.server.authority] and not standard_port:
            self.reply(403)
        elif self.headers.get_all("Origin") != [self.server.origin]:
            self.reply(403)
        elif self.requestline.split()[1] != self.server.path:
            self.reply(404)
        elif self.command not in ("GET", "OPTIONS"):
            self.reply(405, Allow="GET, OPTIONS")
        else:
            return True
        return False

    def do_OPTIONS(self):
        method = self.headers.get_all("Access-Control-Request-Method")
        headers = [v.lower() for v in self.headers.get_all("Access-Control-Request-Headers", [])]
        private = self.headers.get_all("Access-Control-Request-Private-Network", [])
        if method != ["GET"] or headers not in ([], ["accept"]) or private not in ([], ["true"]):
            self.reply(403)
            return
        cors = {"Access-Control-Allow-Origin": self.server.origin, "Access-Control-Allow-Methods": "GET",
                "Vary": "Origin, Access-Control-Request-Method, Access-Control-Request-Headers, Access-Control-Request-Private-Network"}
        if headers:
            cors["Access-Control-Allow-Headers"] = "Accept"
        if private:
            cors["Access-Control-Allow-Private-Network"] = "true"
        self.reply(204, **cors)

    def do_GET(self):
        if "Range" in self.headers:
            self.reply(416)
            return
        server = self.server
        current = os.fstat(server.asset.fileno())
        if (current.st_size, current.st_mtime_ns) != (server.info.st_size, server.info.st_mtime_ns):
            self.reply(409)
            return
        server.asset.seek(0)
        remaining = current.st_size
        self.reply(200, remaining, **{"Access-Control-Allow-Origin": server.origin, "Vary": "Origin",
                                      "Content-Type": server.mime})
        while remaining:
            chunk = server.asset.read(min(1024 * 1024, remaining))
            if not chunk:
                return  # 传输中素材被截短，客户端会看到不完整的响应。
            self.wfile.write(chunk)
            remaining -= len(chunk)
        self.wfile.flush()
        server.delivered = True

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass  # 未完整发送的连接不消耗这次交付。


def expired(signum, frame):
    raise SystemExit("单文件交付超时，服务已关闭。请先核对页面状态。")


def serve(args):
    mime = MEDIA_TYPES.get(args.file.suffix.lower())
    if not mime:
        raise UsageError("请选择支持的视频或图片：" + "、".join(MEDIA_TYPES))
    before = args.file.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise UsageError("请选择普通素材文件本身，目录、符号链接和特殊文件不能交付。")
    # 打开后固定这一份文件。即使原路径随后被替换，也不会重新按名字取文件。
    def open_asset(path, flags):
        return os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)

    with open(args.file, "rb", opener=open_asset) as asset:
        info = os.fstat(asset.fileno())
        if not stat.S_ISREG(info.st_mode) or not os.path.samestat(before, info) or not info.st_size:
            raise UsageError("素材已改变或为空，请重新选择。")
        with HTTPServer(("127.0.0.1", args.port), Handler) as server:
            server.asset, server.info, server.mime = asset, info, mime
            server.origin = args.origin
            server.authority = f"127.0.0.1:{server.server_port}"
            server.path = "/" + secrets.token_urlsafe(32)
            server.delivered = False
            signal.signal(signal.SIGALRM, expired)
            signal.alarm(args.timeout)
            try:
                print(json.dumps({"url": "http://" + server.authority + server.path, "origin": args.origin,
                                  "name": args.file.name, "size": info.st_size, "type": mime}), flush=True)
                while not server.delivered:
                    server.handle_request()
            finally:
                signal.alarm(0)


def terminate(signum, frame):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    try:
        options = arguments()
        if options.serve_only:
            serve(options)
        else:
            from media_cli import CliError, select_file

            try:
                select_file(options, DRAFT_PATHS)
            except CliError as exc:
                raise UsageError(f"{exc}\n{migration(options)}") from exc
    except UsageError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"无法读取素材或启动交付服务（{exc}）。", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit("交付已中止，服务已关闭。")
