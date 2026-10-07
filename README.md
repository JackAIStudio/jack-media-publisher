# jack-media-publisher

把一条视频准备成 **小红书 / 抖音 / B站 / 微信视频号** 的发布草稿。

上传视频 → 填标题与真实话题实体 → 设内容声明（默认「无需标注」）→ 传多比例封面 → 逐平台独立验收 → **停在最终发布按钮之前**，由人工确认发布。

---

## 它做什么 / 不做什么

| ✅ 做 | ❌ 不做 |
|---|---|
| 上传视频到四个平台后台 | 剪辑、转码 |
| 填标题、话题（落成平台真实实体） | 制作封面（只上传已有封面） |
| 设内容声明（默认一律「无需标注」/ 不选） | 点击最终发布 |
| 上传多比例封面并验收 | 绕过登录、验证码、风控 |
| 保存草稿、逐平台交付证据 | 预测流量、承诺过审 |

---

## 关键设计

### 1. 停在发布前

**这个工具永远不点最终发布按钮。** 它把草稿准备到可复核状态就停，四个平台的最终发布都由人来做。

### 1.5 只由人手打斜杠命令唤起

SKILL.md frontmatter 里带一行：

```yaml
disable-model-invocation: true
```

效果（DSH / Claude Code 都认这个键）：

| 面 | 行为 |
|---|---|
| 模型可见的技能目录 | **不出现** —— Agent 根本看不见它，也就不会"顺手"加载 |
| `skill` 工具 | 拒绝加载（`not available for model invocation`） |
| 输入框 `/` 菜单 | 照常列出，标注「仅用户 · …」 |
| 用户打 `/jack-media-publisher` | 正常注入执行 |

**为什么需要它**：这个 skill 一旦被 Agent 自行判断触发，就会往上下文里灌进整篇平台字段表 + 选择器 + 踩坑记录，而用户当时可能只是在聊"要不要发个视频"。

**别把这行删掉**——描述里的触发词（"发布视频""四个平台都发一下"）是给人和斜杠菜单看的，不是给模型做路由的。

### 2. 不轻信动作回执

> **"执行过动作" ≠ "成功"。**

打开弹窗不算数、上传返回成功不算数、下拉列表里出现目标文本不算数。
**只有平台自己吐出的、绑定了这次操作的回执才算数**——例如封面的接受 URL、话题的实体节点。

细节见 [`references/verification.md`](references/verification.md)。

### 3. 大文件绕开 bsk 的 512 MB 限制

`bsk upload` 会把文件**复制一份再分块传输**，因此有单文件 512 MB + 会话累计 512 MB 两道硬限制。

超过时改用本地 HTTP 服务 + 页面内注入——**没有大小上限，也不消耗 bsk 额度**：

```bash
./scripts/inject-large-file.sh ~/video.mp4 'input.upload-input' --session <id>
```

实测 1.1 GB 注入耗时约 1.5 秒。细节见 [`references/gotchas.md`](references/gotchas.md)。

### 4. 隐藏 Chrome 的调试横幅

BrowserSkill 挂调试器时，Chrome 会在所有窗口显示「已开始调试此浏览器」。

```
setup/chrome-silent/build.sh   →  产出 ~/Applications/Chrome Silent.app
```

图标是 Chrome + 右下角绿点，和真 Chrome 区分开。**日常上网不受影响**。

---

## 安装

本仓库**直接放在 agent 通用技能目录里**，不需要软链：

```bash
git clone <repo> ~/.agents/skills/jack-media-publisher
```

然后按 [`setup/prerequisites.md`](setup/prerequisites.md) 过一遍环境清单（三件事：bsk 空闲超时、扩展文件访问权限、静默启动器）。

---

## 目录

```
.
├── SKILL.md                      Agent 入口
├── references/
│   ├── platforms.md              四平台字段映射（最核心）
│   ├── selectors.md              选择器 + 为什么是它
│   ├── verification.md           可信信号 vs 陷阱
│   └── gotchas.md                踩坑记录
├── scripts/
│   └── inject-large-file.sh      大文件注入
└── setup/
│   ├── prerequisites.md          环境前置清单
│   └── chrome-silent/            静默启动器（源码 + 构建脚本）
```

---

## 依赖

```
BrowserSkill (bsk)     浏览器操控层
Google Chrome          实测 153.x
Node.js                ≥ 20
ffmpeg                 ≥ 6（探测视频 + 构建图标）
```

**不依赖任何平台的 API key**——全部走浏览器登录态。
**不依赖 DSH**——这是 agent 通用能力。

---

## 保鲜期

**平台会改版。** 本项目里的选择器都是实测得出，但都有保鲜期。

失效时先怀疑平台改版，不要怀疑自己的操作。发现改版后请更新 `references/selectors.md`，并把改版记录追加到 `references/gotchas.md`。
