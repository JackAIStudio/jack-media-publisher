# 环境前置

新机器先确认 BrowserSkill 能连接到指定的 Chrome，并用无业务内容的小文件验证原生文件选择。长任务可预设会话超时，静默启动器按需安装。

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

### 长任务的会话空闲时间

默认 5 分钟空闲可能关闭任务窗口。从草稿箱能找回已保存的字段，未保存的编辑可能丢失。需要调长时，在开始任务前确认 daemon 内所有窗口都可关闭，然后按需设置：

```bash
bsk daemon restart --session-idle 4h --daemon-idle 8h
```

已有上传、未保存草稿或待人工复核的页面时保留原会话。见[留页交接或关闭专用会话](../SKILL.md#7-留页交接或关闭专用会话)。

### ⚠️ 必做：给扩展开「允许访问文件网址」

**没有这个权限，文件上传一定失败。报错有三种措辞，都要认出来：**

```
cdp_failed: {"code":-32000,"message":"Not allowed"}          phase: set_files
error: the browser could not attach the staged file to the input
error: the browser could not complete the native file drop   {"code":-32602,...}
```

```
chrome://extensions  →  BrowserSkill  →  详情  →  打开「允许访问文件网址」
```

在当前浏览器配置的扩展列表里打开 BrowserSkill 详情页，由用户管理这个权限。`bsk status` 和 `bsk doctor` 可能仍显示正常，开工前按下方验证清单实测原生文件选择。

⚠️ **权限开完之后，已经存在的 bsk session 不会自动复活** —— 重新 `bsk session start` 再传。

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

1. 确认浏览器已连接到当前宿主，需要指定配置时核对实例。
2. 在独立测试页实测原生文件选择。可在 `https://the-internet.herokuapp.com/upload` 的文件框选择一份无业务内容的小探针。读取 `files[0].name` 和 `files[0].size`，和本地文件对照。测完关闭测试页即可。
3. 实际需要单文件本机交付时再启动助手；具体用法和回执见[单文件本机交付](../references/gotchas.md#单文件本机交付)。DSH 通过已绑定的 `bsk_*` 会话与页面交互。

---

## 不依赖什么

- ❌ 不依赖 DSH（这是 agent 通用能力，Claude Code / Codex / Cursor 都能用）
- ❌ 不依赖 Ego Lite（用 BrowserSkill，不是 oil-oil 那套）
- ❌ 不需要任何平台的 API key（全部走浏览器登录态）
