"""独立 CLI 的兼容入口。只在调用方指定的现有会话、草稿和素材框上交付。"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


class CliError(ValueError):
    pass


# 选择器只作为数据传入，绝不作为脚本源码。panel 必须和用户指定的 input 是同一上传组件。
LOCATE = """
const { phase, kind, selector, href, ticket } = request;
if (location.href !== href) throw Error('草稿页已变化');
let root = document;
if (ticket.origin === 'https://channels.weixin.qq.com') {
  const hosts = document.querySelectorAll('wujie-app');
  if (hosts.length !== 1 || !hosts[0].shadowRoot) throw Error('无法确认视频号表单');
  root = hosts[0].shadowRoot;
}
const targets = root.querySelectorAll(selector);
if (targets.length !== 1 || !targets[0].matches('input[type=file]')) throw Error('需要唯一的素材文件框');
const input = targets[0];
let panel;
switch (location.hostname) {
  case 'channels.weixin.qq.com':
    panel = input.closest(kind === 'video' ? '.ant-upload-btn' : '.single-cover-uploader-wrap');
    break;
  case 'creator.xiaohongshu.com':
    panel = input.closest('.drag-over');
    if (kind === 'cover' && !input.closest('.main-cover-editor-modal')) throw Error('请核对当前封面编辑器');
    break;
  case 'member.bilibili.com': {
    const wrapper = input.closest('.bcc-upload-wrapper');
    const areas = wrapper?.querySelectorAll('.upload-area');
    if (kind !== 'video' || areas?.length !== 1) throw Error('请核对当前视频上传区');
    if (areas[0].contains(input)) panel = areas[0];
    else {
      // 两者可以是兄弟节点，此时 wrapper 的实际落点也必须在该上传区内。
      const r = wrapper.getBoundingClientRect();
      if (areas[0].contains(document.elementFromPoint(r.left + r.width/2, r.top + r.height/2))) panel = wrapper;
    }
    break;
  }
  case 'creator.douyin.com':
    for (let el = input.parentElement, i = 0; el && i < 4; el = el.parentElement, i++) {
      if (el.matches('body, html, main, [role=main], #root, #app')) break;
      if (/点击上传/.test(el.innerText) && /拖入|拖拽/.test(el.innerText)) { panel = el; break; }
    }
    break;
}
if (!panel) throw Error('无法核对当前上传区与素材框');
return await deliver(phase, kind, panel, ticket, input);
"""


def bsk(args, *command, timeout=15):
    try:
        proc = subprocess.run([os.environ.get("BSK", "bsk"), *command, "--session", args.session, "--json"],
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliError("BrowserSkill 未响应，请核对原会话和页面状态。") from exc
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        raise CliError("BrowserSkill 返回了无法核对的回执，请确认 CLI 支持上下文及观察守卫。") from exc
    if proc.returncode:
        code = data.get("code") if isinstance(data, dict) else None
        reason = f"（{code}）" if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,64}", code) else ""
        raise CliError(f"BrowserSkill 已拒绝或中断操作{reason}，请留在原页人工处理。")
    if not isinstance(data, dict) or data.get("ok") is False or data.get("session_id", args.session) != args.session:
        raise CliError("BrowserSkill 的回执或会话不匹配。")
    return data


def binding(args, tab=None):
    target = [] if tab is None else ["--tab-id", str(tab)]
    receipt = bsk(args, "cooperate", "sync", *target, "--max-tokens", "1200")
    current = receipt.get("tab_id")
    state = receipt.get("state", {})
    if (type(current) is not int or current <= 0 or (tab is not None and current != tab)
            or receipt.get("ready") is False or not isinstance(state, dict) or state.get("mode") != "ready"
            or state.get("editing") is not False or not all(isinstance(receipt.get(key), str) and receipt[key]
                                                           for key in ("context_id", "observation_id"))):
        raise CliError("原标签页的控制权或观察回执无法确认，请先检查是否有人接管或正在编辑。")
    return current, receipt["context_id"], receipt["observation_id"]


def draft(args, tab, paths):
    tabs = bsk(args, "tab", "list", "--scope", "agent").get("tabs")
    if not isinstance(tabs, list):
        raise CliError("无法核对当前会话的标签页。")
    found = [t.get("url") for t in tabs if isinstance(t, dict) and t.get("tab_id") == tab]
    if len(found) != 1 or not isinstance(found[0], str):
        raise CliError("目标标签页不属于当前会话。")
    page = urlsplit(found[0])
    origin = f"{page.scheme}://{page.netloc}"
    if page.path.removesuffix("/") not in paths.get(origin, ()) or (args.origin and args.origin != origin):
        raise CliError("当前页与授权的官方草稿入口不匹配。")
    return found[0], origin


def evaluate(args, bound, href, ticket, adapter, phase):
    tab, context, observation = bound
    request = {"phase": phase, "kind": "video" if ticket["type"].startswith("video/") else "cover",
               "selector": args.selector, "href": href, "ticket": ticket}
    expr = "(async (request, deliver) => {" + LOCATE + "})(" + json.dumps(request) + ",\n" + adapter + "\n)"
    data = bsk(args, "evaluate", expr, "--tab-id", str(tab), "--context", context, "--observation", observation,
               "--timeout", f"{args.timeout}s", timeout=args.timeout + 2)
    value = data.get("value")
    if (data.get("ok") is not True or data.get("tab_id") != tab or data.get("verified") is False
            or not isinstance(value, dict) or value.get("name") != ticket["name"] or value.get("size") != ticket["size"]):
        raise CliError("文件选择回执不明，请查看草稿，勿直接重试。")
    return value.get("state")


def select_file(args, paths):
    if "DSH_SESSION_ID" in os.environ or "DSH_SHELL" in os.environ:
        raise CliError("在 DSH 中请用注入的 bsk_* 工具绑定草稿。")
    if not args.session or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", args.session):
        raise CliError("请用 --session 指定实际已授权的 BrowserSkill 会话。")
    if not args.selector or len(args.selector) > 1024:
        raise CliError("请指定已在目标草稿中确认的文件输入框选择器。")
    if args.tab_id is not None and not re.fullmatch(r"[1-9][0-9]{0,9}", args.tab_id):
        raise CliError("--tab-id 需要实际的正整数标签页编号。")
    bound = binding(args, int(args.tab_id) if args.tab_id else None)
    tab = bound[0]
    href, origin = draft(args, tab, paths)
    args.origin = origin
    adapter = Path(__file__).with_name("media-file-input.js").read_text(encoding="utf-8")
    # 子进程直接复用前台服务。任何返回路径都回收它，完整 GET 会让它自行退出。
    command = [sys.executable, "-EsB", str(Path(__file__).with_name("serve_media.py")), str(args.file.absolute()),
               "--serve-only", "--origin", origin, "--port", str(args.port), "--timeout", str(args.timeout)]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as service:
        try:
            first = service.stdout.readline()
            if not first:
                raise CliError(service.stderr.read().strip() or "无法启动单文件服务。")
            ticket = json.loads(first)
            state = evaluate(args, bound, href, ticket, adapter, "prepare")
            if state != "already_selected":
                if state != "prepared" or service.wait(timeout=2) != 0:
                    raise CliError("本机素材没有完整交付，请核对页面状态。")
                fresh = binding(args, tab)
                if fresh[:2] != bound[:2] or fresh[2] == bound[2] or draft(args, tab, paths)[0] != href:
                    raise CliError("草稿、观察或控制权已变化，请重新确认。")
                state = evaluate(args, fresh, href, ticket, adapter, "select")
            if state not in ("already_selected", "selected"):
                raise CliError("文件选择结果不明，请查看草稿，勿直接重试。")
            print("已选择，需平台验收")
        except subprocess.TimeoutExpired as exc:
            raise CliError("未收到完整的文件交付回执，请查看草稿。") from exc
        finally:
            if service.poll() is None:
                service.terminate()
