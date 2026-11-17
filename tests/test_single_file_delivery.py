"""通过原 shell 入口测试一次性交付，只使用临时素材与回环连接。"""

import base64
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from urllib.parse import urlsplit


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inject-large-file.sh"
WECHAT = "https://channels.weixin.qq.com"
DOUYIN = "https://creator.douyin.com"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGPg4OAAAAA0ABl8aCr0AAAAAElFTkSuQmCC")


class SingleFileDelivery(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "试片 '一' #1.PnG"
        self.file.write_bytes(PNG)

    @contextmanager
    def serving(self, *extra, origin=WECHAT):
        command = [SCRIPT, self.file, "--serve-only", "--origin", origin, "--timeout", "6", *extra]
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            try:
                first_line = proc.stdout.readline()
                if not first_line:
                    self.fail(proc.stderr.read())
                yield proc, json.loads(first_line)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=3)

    def request(self, url, method, headers, path=None):
        conn = http.client.HTTPConnection(url.hostname, url.port, timeout=3)
        try:
            conn.request(method, path or url.path, headers=headers)
            reply = conn.getresponse()
            return reply.status, reply.headers, reply.read()
        finally:
            conn.close()

    def test_exact_recipient_and_file(self):
        sibling = self.file.with_name("other.png")
        sibling.write_bytes(PNG)
        with self.serving() as (proc, data):
            url = urlsplit(data["url"])
            self.assertEqual((url.scheme, url.hostname), ("http", "127.0.0.1"))
            self.assertGreater(url.port, 0)
            self.assertEqual(data, {"url": url.geturl(), "origin": WECHAT, "name": self.file.name,
                                    "size": len(PNG), "type": "image/png"})
            for path, method, extra, status in [
                (url.path, "GET", {}, 403),
                (url.path, "GET", {"Origin": DOUYIN}, 403),
                (url.path, "GET", {"Origin": WECHAT, "Host": "localhost"}, 403),
                ("/", "GET", {"Origin": WECHAT}, 404),
                ("/other.png", "GET", {"Origin": WECHAT}, 404),
                (url.path, "HEAD", {"Origin": WECHAT}, 405),
                (url.path, "GET", {"Origin": WECHAT, "Range": "bytes=0-0"}, 416),
                (url.path, "OPTIONS", {"Origin": WECHAT, "Access-Control-Request-Method": "POST"}, 403),
                (url.path, "OPTIONS", {"Origin": WECHAT, "Access-Control-Request-Method": "GET",
                                       "Access-Control-Request-Headers": "X-Custom"}, 403),
            ]:
                with self.subTest(method=method, path=path, headers=extra):
                    code, headers, body = self.request(url, method, extra, path)
                    self.assertEqual(code, status)
                    self.assertNotIn("Access-Control-Allow-Origin", headers)
                    self.assertEqual(body, b"")
            code, headers, _ = self.request(url, "OPTIONS", {
                "Origin": WECHAT, "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Accept", "Access-Control-Request-Private-Network": "true",
            })
            self.assertEqual(code, 204)
            self.assertEqual(headers["Access-Control-Allow-Origin"], WECHAT)
            self.assertEqual(headers["Access-Control-Allow-Methods"], "GET")
            self.assertEqual(headers["Access-Control-Allow-Headers"], "Accept")
            self.assertEqual(headers["Access-Control-Allow-Private-Network"], "true")
            code, headers, body = self.request(url, "GET", {"Origin": WECHAT})
            self.assertEqual((code, body), (200, PNG))
            self.assertEqual(headers["Access-Control-Allow-Origin"], WECHAT)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["Content-Type"], data["type"])
            self.assertEqual(int(headers["Content-Length"]), data["size"])
            self.assertEqual(proc.wait(timeout=3), 0)
            with self.assertRaises(ConnectionRefusedError):
                self.request(url, "GET", {"Origin": WECHAT})

    def test_timeout_releases_an_idle_connection(self):
        with self.serving("--timeout", "1") as (proc, data):
            url = urlsplit(data["url"])
            with socket.create_connection((url.hostname, url.port), timeout=3):
                self.assertNotEqual(proc.wait(timeout=3), 0)
                self.assertIn("超时", proc.stderr.read())

    def test_origins_and_random_paths(self):
        paths = set()
        for origin in (WECHAT, DOUYIN, "https://creator.xiaohongshu.com", "https://member.bilibili.com"):
            with self.serving(origin=origin) as (proc, data):
                url = urlsplit(data["url"])
                self.assertNotIn(url.path, paths)
                paths.add(url.path)
                code, headers, _ = self.request(url, "GET", {"Origin": origin})
                self.assertEqual((code, headers["Access-Control-Allow-Origin"]), (200, origin))
                self.assertEqual(proc.wait(timeout=3), 0)

    def test_invalid_inputs_and_legacy_migration(self):
        link = self.file.with_name("link.png")
        link.symlink_to(self.file)
        directory = self.file.with_name("directory.png")
        directory.mkdir()
        empty = self.file.with_name("empty.png")
        empty.touch()
        other = self.file.with_name("other.txt")
        other.write_text("不是素材", encoding="utf-8")
        common = ["--serve-only", "--origin", WECHAT]
        for args in ([link, *common], [directory, *common], [empty, *common], [other, *common],
                     [self.file.with_name("missing.png"), *common], [self.file, "--serve-only"],
                     [self.file, "--serve-only", "--origin", WECHAT + "/"],
                     [self.file, *common, "--port", "65536"], [self.file, *common, "--port"],
                     [self.file, *common, "--timeout", "0"]):
            with self.subTest(args=args):
                result = subprocess.run([SCRIPT, *args], capture_output=True, text=True, timeout=3)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr and "Traceback" not in result.stderr)
        result = subprocess.run([SCRIPT, self.file, "input.upload-input", "--session", "example",
                                 "--tab-id", "1", "--port", "8899"], capture_output=True, text=True, timeout=3,
                                env={"PATH": os.defpath, "DSH_SESSION_ID": "test"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--serve-only --origin", result.stderr)
        self.assertIn("--port 8899", result.stderr)
        self.assertEqual(result.stdout, "")


    def test_bound_cli(self):
        # 假 CLI 只返回合成的标签页与回执。它的网络操作仅为读取测试服务的回环地址。
        fake = self.file.with_name("mock-bsk")
        fake.write_text(r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
from urllib.request import Request, urlopen

args = sys.argv[1:]
def arg(key): return args[args.index(key) + 1]
assert arg('--session') == 'unit-session' and '--json' in args
log = Path(os.environ['TEST_LOG'])
events = log.read_text().splitlines() if log.exists() else []
case = os.environ['TEST_CASE']
if args[:2] == ['cooperate', 'sync']:
    count = events.count('sync') + 1
    if case == 'ready' and count == 1:
        assert '--tab-id' not in args
    else:
        assert arg('--tab-id') == '7'
    data = dict(tab_id=7, context_id='other' if count > 1 and case == 'handover' else 'ctx',
                observation_id=str(count), state=dict(mode='ready', editing=False))
    event = 'sync'
elif args[:2] == ['tab', 'list']:
    assert arg('--scope') == 'agent'
    path = '/other' if case == 'route' else '/publish/publish'
    data = dict(tabs=[dict(tab_id=7, url='https://creator.xiaohongshu.com' + path)])
    event = 'list'
else:
    assert args[0] == 'evaluate' and arg('--context') == 'ctx' and arg('--tab-id') == '7'
    assert arg('--observation') == str(events.count('sync'))
    payload, _ = json.JSONDecoder().raw_decode(args[1].split('})(', 1)[1])
    assert payload['selector'] == 'input.upload-input' and payload['kind'] == 'cover'
    event = payload['phase']
    ticket = payload['ticket']
    if event == 'prepare' and case != 'already':
        with urlopen(Request(ticket['url'], headers={'Origin': ticket['origin']}), timeout=2) as response:
            assert len(response.read()) == ticket['size']
    state = 'already_selected' if case == 'already' else {'prepare':'prepared','select':'selected'}[event]
    data = dict(ok=True, tab_id=7, value=dict(state=state, name=ticket['name'], size=ticket['size']))
with log.open('a') as out: print(event, file=out)
print(json.dumps(data))
''', encoding="utf-8")
        fake.chmod(0o700)
        for case, expected in [
            ("ready", ["sync", "list", "prepare", "sync", "list", "select"]),
            ("already", ["sync", "list", "prepare"]),
            ("handover", ["sync", "list", "prepare", "sync"]),
            ("route", ["sync", "list"]),
        ]:
            with self.subTest(case=case):
                log = self.file.with_name(case)
                env = {"PATH": os.defpath, "BSK": str(fake), "TEST_CASE": case, "TEST_LOG": str(log)}
                tab_args = [] if case == "ready" else ["--tab-id", "7"]
                proc = subprocess.run([SCRIPT, self.file, "input.upload-input", "--session", "unit-session", *tab_args],
                                      capture_output=True, text=True, env=env, timeout=6)
                self.assertEqual(log.read_text().splitlines(), expected, proc.stderr)
                if case in ("ready", "already"):
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout.strip(), "已选择，需平台验收")
                else:
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn("--serve-only", proc.stderr)


if __name__ == "__main__":
    unittest.main()
