# jack-media-publisher

把一条视频准备成 **小红书 / 抖音 / B站 / 微信视频号** 的发布草稿。

上传视频后判断本条作品的主旨、自制来源和 AI 生成素材，再填分区、原创、内容声明、标题与话题，按各入口配置封面。逐平台验收草稿后交给用户确认发布。

---

## 它做什么 / 不做什么

| ✅ 做 | ❌ 不做 |
|---|---|
| 上传视频到四个平台后台 | 剪辑、转码 |
| 填标题、话题（落成平台真实实体） | 制作封面（只上传已有封面） |
| 自制稿选原创，按成片中使用的生成素材设置 AI 声明 | 点击最终发布 |
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

每个平台分别记开始上传、平台接收、人工等待起止和草稿入箱的时间及回执。并行任务按平台看耗时，缺失的时间标为「未观测」。详见[验收标准](references/verification.md)。

自制模型实测中展示生成结果时，选原创和对应平台的含 AI 声明；实拍生活 vlog 选原创。B站分区按观众看到的主线匹配投稿页选项，分别核对分区、内容声明和自制授权。见[声明字段](references/platforms.md#内容声明)与[B站真实分区清单](references/bilibili-categories.md)。

### 3. 把用户指定的文件交给平台编辑器

优先使用 BrowserSkill 的原生文件上传。本地暂存的单文件和会话累计限额均为 512 MiB。需要本机交付时，指定一份素材和一个官方编辑页来源，从仓库根目录运行：

```bash
./scripts/inject-large-file.sh "$FILE" --serve-only --origin https://channels.weixin.qq.com
```

助手在回环地址临时提供该文件。DSH 用 `--serve-only` 配合注入的 `bsk_*`；独立 CLI 可沿用 `./scripts/inject-large-file.sh "$FILE" "$SELECTOR" --session "$SESSION" --tab-id "$TAB"`，选择器对应原草稿内已确认的文件框。两种入口共用同一份文件交付与选中回执。视频或封面是否生效，再在编辑页和草稿箱分别核对。见[视频号上传排查](references/gotchas.md#视频号上传排查)。

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

首次使用时按[环境前置](setup/prerequisites.md)核对浏览器连接与文件选择权限。长任务空闲时间和静默启动器按需配置。

本机斜杠命令读取安装目录的工作区内容，未提交的文档也可能影响下一次调用。维护时用 `git status --short` 和 `git diff` 核对已有改动，按平台或修复主题分别提交；当前期望值以[平台字段表](references/platforms.md)为准。

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
│   ├── inject-large-file.sh      限定素材和平台来源的本机交付入口
│   └── media-file-input.js       编辑器文件准备与选择，使用控件所属窗口的类型
├── tests/                        本机交付、组件兼容和平台规则回归
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
Python 3               单文件本机交付（标准库）
```

页面操作复用浏览器登录态。DSH 使用已绑定的浏览器工具，独立 CLI 的调用参数见 `./scripts/inject-large-file.sh --help`。

## 本机回归检查

从仓库根目录运行。测试使用临时素材、回环连接和模拟编辑器。

```bash
python3 -IB -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/media-file-input.test.mjs
```

---

## 保鲜期

**平台会改版。** 本项目里的选择器都是实测得出，但都有保鲜期。

选择器失效时核对现场的可见控件。发现改版后，在平台字段表更新当前规则，在选择器和验收文档更新相应定位与回执，最后在踩坑记录注明适用条件与日期。
