# 选择器与操作机制

每个选择器都标注了**为什么是它**——因为其中几个用错了会静默失败（不报错，但什么也没发生）。

---

## 文件上传

| 平台 | 选择器 | 说明 |
|---|---|---|
| 小红书 | `input.upload-input` | 视频口。带 `accept` 校验 |
| 抖音 | `input[type=file]`（页面唯一） | accept 含 `video/*` |
| **B站** | **`.bcc-upload-wrapper input[type=file]`** | ⚠️ 关键，见下 |
| 视频号 | **需穿透 wujie shadow root** | 见下 |

### ⚠️ B站：必须限定在 wrapper 里

B站 页面上有 **3 个 file input**，其中有个 1×1 的"僵尸 input"：

```
n:0  name=""          可见性 false   ← 混进来的干扰项
n:1  name="buploader" 可见性 true
n:2  name="buploader" 可见      accept=".txt"（字幕）
```

**用 `input[name=buploader]` 会失败**：框架消费了文件但不启动上传。
**必须用 `.bcc-upload-wrapper input[type=file]`。**

> 这条来自 oil-oil 的 `ego-browser-workflow.md`：
> *"Bilibili may keep detached 1×1 video inputs next to the active uploader. Scope upload to `.bcc-upload-wrapper input[type=file]`."*

### ⚠️ 视频号：wujie 微前端

视频号用 wujie，真实的编辑器在 `wujie-app` 的 **shadow root** 里。

**主文档的 `document.querySelectorAll` 找不到它**，`document.body.innerText` 也只返回导航栏（约 80 字符）。

穿透方式：

```js
function findInShadow(hostSelector, innerSelector) {
  const host = document.querySelector(hostSelector);
  if (!host?.shadowRoot) return null;
  let el = host.shadowRoot.querySelector(innerSelector);
  if (el) return el;
  // 递归
  for (const e of host.shadowRoot.querySelectorAll('*')) {
    if (e.shadowRoot) {
      const deep = e.shadowRoot.querySelector(innerSelector);
      if (deep) return deep;
    }
  }
  return null;
}
// 视频 input
findInShadow('wujie-app', 'input[type=file]');
// 描述编辑器
findInShadow('wujie-app', 'div.input-editor');
```

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
| B站 | 创作声明 | `input.bcc-select-input-inner` |
| 视频号 | 短标题 | shadow root 里的 `input` |
| 视频号 | 描述 | shadow root 里的 `div.input-editor` |

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
3. **轮询**建议面板，拿精确匹配项的 ref
4. 点击它 → 落成 `a.tiptap-topic` 实体

**⚠️ 建议面板出现得慢，而且会重渲染。**
「先标记元素 → 再按标记点击」会因为重渲染导致**坐标漂移，点错项**。
**必须用快照取 ref，再点 ref。**

**⚠️ 不要一次性注入 `#话题` 文本**——那只会产生一个空的 suggestion 装饰，不加载候选。

### 抖音

1. 动态解析 `button "#添加话题"` 的 ref（**它的 ref 会变**）
2. 点它 → 编辑器插入 `#`
3. 输入查询词
4. 轮询 `button "# <话题> <浏览量>"` 形式的面板项
5. 点击

**⚠️ `#添加话题` 的 ref 在面板开关后会变化。**
用固定 ref 会导致点击落空，文字被当**纯文本**打进编辑器。

### B站

标签框输入 → 按 Enter → 落成 `.label-item-v2-content`。

**⚠️ 空输入框时不要按 Backspace**——B站 会把它理解成"删除最后一个标签"。

### 视频号

**没有建议面板。** `#话题` 文本会被平台识别（`span.hl.topic`），直接写进描述即可。

---

## 封面

### 小红书：hover-only 入口

编辑器入口 `.cover-edit-entry` **只在 hover 时显示**，而且指针移动可能在 click 事件完成前把它移除。

**做法：直接调用它的 click handler**，不要用鼠标模拟。

```js
document.querySelector('.cover-edit-entry').click();
```

然后轮询 `.main-cover-editor-modal`，用其中的图片 input：

```
input.upload-input[accept*="image"]
```

**编辑器可能只显示「上传」和「完成」，没有单独的"上传封面"tab。**

### B站：两个独立面板

```
.cover-editor-panel-canvas-title     ← 两个面板的标题
  ├─ 首页推荐封面（4:3）   → [class*=editor_4_3]
  └─ 个人空间封面（16:9）  → [class*=editor_16_9]
```

**上传前必须先确认目标面板处于 active 状态**，否则图会进错的槽。

激活方式（mousedown → mouseup → click 三连，派发到目标面板元素）。

### 抖音：横竖两个 tab

```
@e button "设置横封面" / "设置竖封面"
上传区：button "点击上传文件或拖拽文件到这里"
```

切换 tab 时可能弹「使用此素材作为封面？」→ 点「直接编辑」。

### 视频号：两个编辑入口

```
button "编辑 个人主页卡片 3:4"
button "编辑 分享卡片 4:3"
```

进去后 `button "上传封面"` → 上传 → `button "确认"`。

**⚠️ 点上传后 refs 会整体位移，必须重新快照取「确认」的 ref，不能沿用上传前的。**

---

## 交互辅助

### 点击中性元素关下拉

自定义下拉不会自动关。给一个无语义的静态元素打标记再点：

```js
document.querySelectorAll('[data-bsk-neutral]').forEach(e => e.removeAttribute('data-bsk-neutral'));
const el = [...document.querySelectorAll('div,span,p')]
  .find(e => e.children.length === 0 && (e.innerText || '').trim() === '某段静态文本');
el.setAttribute('data-bsk-neutral', '1');
```

然后 `click '[data-bsk-neutral="1"]'`。

**比坐标点击可靠**——不受滚动和重排影响。
