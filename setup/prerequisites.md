# 环境前置

**这套流程依赖三样东西，缺任何一个都会跑不起来或跑一半崩。** 换新机器时先过一遍这份清单。

---

## 1. BrowserSkill（bsk）—— 浏览器操控层

```bash
# 检查
bsk status
```

需要满足：

```
✅ daemon running
✅ browsers connected    （Chrome 里装了 BrowserSkill 扩展并连上）
```

**扩展安装**：见 <https://github.com/Tencent/BrowserSkill> 的 Quick Start。

### ⚠️ 必做：调长会话空闲超时

**默认 5 分钟空闲就会关掉会话窗口**，导致你埋头调一个平台时，其他平台的页面被关、草稿丢失。

```bash
bsk daemon restart --session-idle 4h --daemon-idle 8h
```

**这不是优化项，是必需项。** 详见 `references/gotchas.md` 第二条。

### ⚠️ 必做：给扩展开「允许访问文件网址」

没有这个权限，文件上传会报 `cdp_failed: Not allowed`。

```
chrome://extensions  →  BrowserSkill  →  详情  →  打开「允许访问文件网址」
```

**注意是 BrowserSkill 那个扩展。**

---

## 2. Chrome 静默启动器 —— 去掉调试横幅

BrowserSkill 挂上调试器时，Chrome 会在**所有窗口**显示「BrowserSkill 已开始调试此浏览器」。

**这只是提示，不影响功能**，但很占空间。它在 Chrome 启动时由命令行开关控制：

```
--silent-debugger-extension-api
```

**⚠️ 关键限制**：`open -a "Google Chrome" --args ...` **只在 Chrome 未运行时才传参数**。已在运行的话，`open -a` 只是把它切到前台，**参数被忽略**。

所以需要一个启动器：Chrome 在跑 → 先退出 → 再带参数启动。

**重建启动器**：

```bash
./setup/chrome-silent/build.sh
```

装好后拖到 Dock 上。图标是 Chrome + 右下角绿点，用来和真 Chrome 区分。

**日常上网用原版 Chrome 不受影响**——横幅只在跑自动化（有会话）时出现。

---

## 3. Chrome 与 Node

```
Google Chrome   实测 153.x
Node.js         ≥ 20（bsk CLI 需要）
```

---

## 验证清单

跑完上面三步后，这套命令应该全部通过：

```bash
# 1) bsk 基本状态
bsk status | grep -E "browsers|sessions"

# 2) 浏览器连接
bsk browsers

# 3) 扩展权限（应无 cdp_failed 报错）
bsk session start
bsk navigate --session <id> "https://the-internet.herokuapp.com/upload"
echo '{"a":1}' > /tmp/t.txt
bsk upload --session <id> --file /tmp/t.txt --selector 'input[type=file]'
bsk evaluate --session <id> "JSON.stringify({n:document.querySelector('input[type=file]').files.length})"
# 期望：{"n":1}

# 4) 大文件注入
./scripts/inject-large-file.sh /path/to/big.mp4 'input[type=file]' --session <id>
```

---

## 不依赖什么

- ❌ 不依赖 DSH（这是 agent 通用能力，Claude Code / Codex / Cursor 都能用）
- ❌ 不依赖 Ego Lite（用 BrowserSkill，不是 oil-oil 那套）
- ❌ 不需要任何平台的 API key（全部走浏览器登录态）
