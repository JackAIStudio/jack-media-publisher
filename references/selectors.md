# 选择器与操作机制

按当前快照定位可见控件。字段应填什么、结果算到哪一步，分别见[平台字段](platforms.md)和[验收](verification.md)。

---

## 文件上传

先按卡片名称确认是**本条视频的上传区**，或**正在编辑的那一张封面**，再取卡内可见按钮或投放区的 ref。文件输入框常是隐藏的，直接指向它可能报 `target element has no visible geometry`。遇到用户拒绝、权限不足或真人占用页面，立即停手，保留现场交给用户。

| 平台 | 视频上传区 | 定位时核对 |
|---|---|---|
| 小红书 | 视频上传卡内的 `div.drag-over` | `input.upload-input` 可能没有可见尺寸 |
| 抖音 | 当前快照中「点击上传 或直接将视频文件拖入此区域」的按钮 ref | 2026-11-18 实测 `div.drag-over` 已匹配不到 |
| B站 | `.bcc-upload-wrapper div.upload-area` | 同页还有 1×1 旧 input 和接收 `.txt` 的字幕 input，仅凭 `name=buploader` 会误选 |
| 微信视频号 | 发布表单中可见的视频上传卡片内的选文件入口 ref | 封面从本张卡片的「编辑」进入，在当前编辑区选图 |

### 微信视频号的 wujie 组件

发布表单位于当前页面 `wujie-app` 的 shadow root。正常从可见界面选完文件后，在对应卡片或其编辑弹窗内定位 `input[type=file]`，核对 `accept` 和文件类型，区分视频与图片。主文档的查询可能只读到导航栏。

同页外层窗口与 wujie 子组件的 `File`、`DataTransfer`、`Event` 类型可以不同。曾有一次 `files[0]` 有文件名和字节数，按控件所属窗口检查却返回 `false`，主卡仍显示视频首帧。正常选图后可做以下只读检查。

```js
// input 已在当前封面编辑区内定位，所选文件来自正常界面。
const file = input.files?.[0];
const componentWindow = input.ownerDocument.defaultView;
const sameRealmFile = !!file && file instanceof componentWindow.File;
```

该次使用控件所属窗口的类型后，编辑区才显示用户来图，点「确认」后主卡也换图。验收看这两处实际画面。

---

## 填写字段

| 平台 | 字段 | 选择器 |
|---|---|---|
| 小红书 | 标题 | `input.d-text[placeholder*="填写标题"]` |
| 小红书 | 正文 | `div.tiptap.ProseMirror`（contenteditable） |
| 抖音 | 标题 | `input.semi-input[placeholder*="作品标题"]` |
| 抖音 | 简介 | `div.zone-container.editor-kit-container` |
| B站 | 标题 | `input.input-val[placeholder*="稿件标题"]` |
| B站 | 简介 | `div.ql-editor`（Quill，**需先 click 聚焦**） |
| B站 | 标签 | `input.input-val[placeholder*="回车键Enter"]` |
| 微信视频号 | 短标题 | 发布表单中「短标题」标签对应的文本输入框 |
| 微信视频号 | 视频描述 | 同一表单里的 `div.input-editor` |

### 内容声明控件

小红书读内容类型声明行 `.d-select` 的显示区。抖音在自主声明弹窗内选定并点「确定」，回读表单上 `.selectBox-buZRzi` 的文本。微信视频号读「视频标注」行收起后的按钮。本条成片对应的值见[内容声明](platforms.md#内容声明)。

B站在「创作声明」下拉的六个 `.bcc-option` 中核对带选中标记的项，收起后回读该行 `input.bcc-select-input-inner` 的显示值。下方「是否添加内容授权声明（非必选）」内的 `.auth-content` 是自制授权文案，需另读对应勾选控件。若输入框显示授权文案，仍按两处实际选中状态记录，无法确认的项注明待核实。

各平台在实际显示的「原创」「自制」或内容授权行，回读对应控件的 `checked`、`aria-checked` 或选中标记。

按钮的可访问名称可能合并了 `textContent` 中的空格或换行。按当前快照的角色、名称和所属字段取 ref，同名控件需在当前卡片或弹窗内区分。

### Quill 编辑器（B站简介）不接受 fill

`fill` 会报 `fill_target_changed`。用 `execCommand`：

```js
const ed = document.querySelector('div.ql-editor');
ed.focus();
const sel = window.getSelection();
const r = document.createRange();
r.selectNodeContents(ed); r.collapse(false);
sel.removeAllRanges(); sel.addRange(r);
document.execCommand('insertText', false, '要填的内容');
```

**清空同理**，把 `insertText` 换成 `document.execCommand('delete', false, null)`。

---

## 话题

### 小红书

1. 点 `button.contentBtn.topic-btn`（原生话题按钮）→ 编辑器插入 `#`
2. 用 `fill --no-clear` 输入查询词
3. 等本轮查询的候选返回。先出现的可能是旧建议，精确核对话题名后取当前项的 ref
4. 点击后回读编辑器内的 `a.tiptap-topic`。若候选重排或 ref 失效，重新快照核对后再选

### 抖音

每轮从当前快照取 `button "#添加话题"` 的 ref，点它插入 `#` 后输入查询词。候选按钮可能带浏览量，核对本轮话题名后点选。面板开关或重排后重新取 ref，回读编辑器内的 `[data-mention="#"]` 文本。

### B站

标签框输入后按 Enter，回读 `.label-item-v2-content`。删除无关标签用该标签 `.label-item-v2-container` 里的 `svg.close`，在空输入框按 Backspace 会删除末项。

有些词只可作为话题加入。若回车后词被清空而标签未增加，走「参与话题 → 搜索更多话题」，精确选词并确认，再核对标签区。实测 `WorkBuddy` 通过此入口落成标签。仍未落地时按原词报告待补。

选择投稿分区时，先打开「分区」行，在该下拉当前可见的 `.drop-list-v2-item .item-cont-main` 内读取候选，点本条所需项。下拉收起后回读分区字段。同名词也可能出现在 `.tag-pre-wrp` 标签区。

### 微信视频号

在描述编辑器里直接写 `#话题`，可在同一编辑器的 `span.hl.topic` 回读识别结果。

---

## 封面

### 小红书：hover-only 入口

悬停主封面卡，待 `.cover-edit-entry` 可见后从当前快照点选。编辑器 `.main-cover-editor-modal` 有时只显示「上传」和「完成」。从该弹窗的可见入口选图，图片输入框可按 `input.upload-input[accept*="image"]` 核对。

### B站：两个独立面板

```
.cover-editor-panel-canvas-title     ← 两个面板的标题
  ├─ #editor_4_3    首页推荐封面（4:3）
  └─ #editor_16_9   个人空间封面（16:9）
```

**⚠️ 面板 id 就是 `#editor_4_3` / `#editor_16_9`，而 `active` 类在它们的【父元素】上**，不在面板自己身上。

2026-09-29 实测（这正是当时验证错的地方）：

```js
// ❌ 错：查面板自己的 className —— 永远拿不到 active
// ✅ 对：查父元素的 class token
const tok = el => el.parentElement.className.split(/\s+/);
tok(document.querySelector('#editor_4_3'));    // ["active"]
tok(document.querySelector('#editor_16_9'));   // ["inactive"]
```

⚠️ 用 `/active/.test(className)` 会**误判** —— 它会匹配上 `inactive`。必须按空格切成 token 再比。

点目标面板，回读父元素的 `active` token 后在该面板选图。编辑器里的「完成」控件是 `div.button.submit`。确认后可在主表单 `.cover-content` 的 `cover-list` 回读两份绑定，`extra` 对应 4:3，`main` 对应 16:9。每槽和用户来图的核对方法见[封面验收](verification.md#封面)。

### 抖音：横竖两个 tab

```
@e button "设置横封面" / "设置竖封面"
上传区：button "点击上传文件或拖拽文件到这里"
```

切换 tab 时可能弹「使用此素材作为封面？」→ 点「直接编辑」。

2026-11-18 实测，发布页的两张卡片各自标有「竖封面3:4」和「横封面4:3」。重新进草稿后，从各卡片内的 `img.currentSrc` 回读平台接受的两份图片。卡片父元素的 `background-image` 可以仍是 `none`。

### 微信视频号的封面编辑入口

在主页面「封面预览」按名称和比例找到本张卡片，再取卡内「编辑」（如 `.edit-btn`）的 ref。处理后实际卡片与用图见[微信视频号封面](platforms.md#视频号封面)。

在当前编辑区点「上传封面」选对应来图，核对画面后重新快照取「确认」的 ref。确认后回到同一张主卡片核对，再处理下一张有来图的卡片。
