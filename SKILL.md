---
name: jack-media-publisher
description: 把一条视频准备成小红书 / 抖音 / B站 / 微信视频号的发布草稿——上传视频、填标题与真实话题实体、设内容声明（默认「无需标注」）、传多比例封面，每个平台独立验收，最后停在最终发布按钮之前交给人工确认。用户要求「发布视频」「传视频到几个平台」「准备发布草稿」「四个平台都发一下」时使用。不负责剪辑、转码、生成封面，也不点击最终发布。
---

# 多平台视频发布准备

把一条视频变成四个平台上**经过独立验收的草稿**，停在发布按钮前。

**这个 skill 永远不点最终发布。** 它只负责把草稿准备到可人工复核的状态。

## 必读

按任务类型读取，不要一次全读：

| 什么时候读 | 读哪个 |
|---|---|
| **动手前**（总是） | `references/platforms.md` —— 四平台字段映射 |
| **填标题 / 核字数时** | `references/title-limits.md` —— 小红书加权 20、抖音 30 怎么算；配套计数页 `tools/title-counter.html` |
| 需要精确选择器 | `references/selectors.md` |
| **每次验收**（总是） | `references/verification.md` |
| 遇到失败或平台改版 | `references/gotchas.md` |
| 新机器 / 环境报错 | `setup/prerequisites.md` |

---

## 硬边界

- **绝不点击任何最终发布按钮**：`发布` / `发布笔记` / `发表` / `立即投稿` / `发布`（抖音）。任何平台都不行。
- **绝不点「安排时间」「定时发布」。**
- **不要从视频内容自行推断是否勾选原创/自制声明**——只按用户的明确指示。
- **内容声明**（小红书的「内容类型声明」/ 抖音的「自主声明」/ B站的「创作声明」/ 视频号的「视频标注」）：**一律「无需标注」/ 不选**。
  ⚠️ 2026-09-29 起翻转：Jack 不再用 AI 做封面，这条从「默认勾选 AI 声明」改成「默认无需标注」。**四个平台字段名和值都不一样，别拿一个平台的值去套另一个**（映射表见 `references/platforms.md`）。
- **不使用平台推荐封面当成品**——只有用户给了封面文件才用；没有就保持默认，不要自作主张。
- **小红书标题上限是加权 20，且有进位**——不是 20 个字符。填之前按 [`references/title-limits.md`](references/title-limits.md) 算；**未超限时必须保留原标题，不要自作聪明截断**。
- 遇到「用户接管浏览器」类中断信号，**立即停止全部浏览器操作**，问用户如何处理，不自行重试。

---

## 用户偏好（Jack）

```
1. 小红书封面     默认 3:4 竖屏；只有明确说"上传横屏"才用横版
2. 视频号短标题   默认不写；明确让写才写
3. B站简介        默认不写
4. 小红书正文     默认不写（只放话题）
5. 视频号位置     默认设为「不显示位置」；短标题禁中文逗号
6. 原创声明       默认不开
7. 内容声明       一律「无需标注」/ 不选（2026-09-29 起；此前默认勾选 AI 声明）
```

---

## 标准流程

### 0. 环境自检

```bash
bsk status                      # daemon 与浏览器连接
bsk browsers                    # 应有 chrome 连着
```

**⚠️ 光看状态不够 —— 必须实测「上传通路」再开工。**

扩展缺「允许访问文件网址」时，`bsk status` / `bsk doctor` **全绿**，但真正上传文件才炸。2026-09-29 实测：一路绿到小红书上传才发现，白跑一趟。

用 1 KB 小文件先打一发（10 秒）：

```bash
echo '{"probe":1}' > /tmp/bsk-upload-probe.txt
S=$(bsk session start --json | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
bsk navigate --session $S "https://the-internet.herokuapp.com/upload"
bsk upload --session $S --file /tmp/bsk-upload-probe.txt --selector 'input[type=file]'
```

- 期望：`upload ok`
- 报 `could not attach the staged file to the input` 或 `{"code":-32000,"message":"Not allowed"}` → **去开权限**（`setup/prerequisites.md` 第 1 节），别硬着头皮往下做
- **用大文件和小文件报同一个错**，就能排除"文件太大"，直接锁定权限问题

**如果会话容易中断**，检查 daemon 是否带了长空闲超时（见 `setup/prerequisites.md`）。

### 1. 接收内容包

向用户确认：

```
视频文件绝对路径
四个平台各自的标题与话题（或由你生成后经用户过目）
封面文件（按比例映射）——可选
内容声明：默认一律「无需标注」/ 不选
原创声明：默认不开
```

**视频时长与编码先探测**：

```bash
ffprobe -v error -show_entries format=duration,size,bit_rate \
        -show_entries stream=codec_type,codec_name,width,height \
        -of default=noprint_wrappers=1 "$VIDEO"
```

### 2. 上传视频（四平台）

**先判断文件大小：**

```
≤ 512 MiB  → bsk 原生 upload（走可信事件，最稳）
> 512 MiB  → 必须用注入法   scripts/inject-large-file.sh
```

**⚠️ bsk 单文件上限 512 MiB，会话累计也是 512 MiB。** 详见 `references/gotchas.md`。

各平台上传口 —— **⚠️ 全部指向「可见投放区」，不要指向 file input 本身**：

```bash
# 小红书  input.upload-input 是 0×0 / opacity:0，直接选它会被拒
bsk upload --session $S --tab-id $T --file "$V" --selector 'div.drag-over'
# 抖音    input[type=file] 同样是隐藏的
bsk upload --session $S --tab-id $T --file "$V" --selector 'div.drag-over'
# B站     ⚠️ 必须限定在 wrapper 内，且指向可见投放区
bsk upload --session $S --tab-id $T --file "$V" --selector '.bcc-upload-wrapper div.upload-area'
# 视频号  input 在 wujie shadow DOM 且不可见 → 用 --ref 指向可见上传区
bsk upload --session $S --tab-id $T --file "$V" --ref '@eNN'
```

**报 `target element has no visible geometry` 就是选错元素了**——不是你操作错，是那个输入框本来就不占位。用这段找可见祖先：

```js
(() => { const inp = document.querySelector('<file input 选择器>'); const out = []; let e = inp;
  for (let i = 0; i < 6 && e; i++) { const r = e.getBoundingClientRect();
    out.push([i, e.tagName + '.' + String(e.className).slice(0,30), Math.round(r.width) + 'x' + Math.round(r.height)]); e = e.parentElement; }
  return out; })()
```

挑 rect 有实际尺寸的那一层当 target。

**上传后立即独立验收，不要相信 upload 的回执。**

### 3. 填字段（上传中可并行）

**小红书 / 抖音 / B站 在上传中就能填**（省时间）；**视频号锁定，必须等传完**。

字段与选择器见 `references/platforms.md` + `references/selectors.md`。

**话题必须落成真实实体**，判定方式见 `references/verification.md`。

### 4. 传封面

按比例映射（**以实际分辨率为准，不要信文件名**）：

```
3:4  → 小红书  |  抖音竖  |  视频号（⚠️ 2026-09-29 实测：视频号只剩这一个 3:4 槽）
4:3  → 抖音横  |  B站首页推荐
16:9 → 仅 B站个人空间
```

**⚠️ 验收不能只看"URL 变了"** —— CDN 是内容寻址的，同一张图可能拿回同一个 URL。可靠的回执优先级：

```
① 平台自己吐的质量/完整性回执   小红书「封面效果评估通过」/ 抖音「双封面缺失」警告清零
② 槽位的内部绑定输出都在          B站：.cover-content 的 cover-list（extra=4:3 / main=16:9）
③ 两个槽确实是两份来源            B站：两个面板 canvas 像素比对（中心像、边角不像 = 两份源）
④ 对话框关闭
```

**同一张图传两个槽 = 错的。** B站 点「完成」时若问是否同步 4:3 到 16:9 —— **永远选「不同步」**（同步出来的不算第二个槽的证据）。

### 5. 存草稿

```
小红书    暂存离开
抖音      暂存离开
B站       存草稿
视频号    保存草稿
```

**⚠️ 视频号的「保存草稿」不保存视频标注。** 视频标注必须最后设、设完不再保存。

### 6. 交付

逐平台报告：

```
平台 / 视频✅ / 标题 / 话题实体数 / 声明 / 封面URL / 草稿位置
```

**并明确说明：草稿已就绪，最终发布由人工完成。**

---

## 幂等

**重跑同一条流程前，先判断状态，不要无脑重放：**

```
目标已完成      → 什么都不做
目标正在上传中  → 只等待，不重新注入
这次是我发起    → 正常执行
```

**重新注入会浪费几十分钟带宽，还可能触发风控。**

---

## 平台改版

这份 skill 里的选择器都有保鲜期。**失效时先怀疑平台改版，不要怀疑自己的操作。**

发现改版后：

1. 用 `bsk snapshot` / `bsk evaluate` 重新勘察真实 DOM
2. 更新 `references/selectors.md` 或 `platforms.md`
3. **把改版记录写进 `references/gotchas.md` 最后一条的列表里**
