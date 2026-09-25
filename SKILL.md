---
name: jack-media-publisher
description: 把一条视频准备成小红书 / 抖音 / B站 / 微信视频号的发布草稿——上传视频、填标题与真实话题实体、设 AI 生成内容声明、传多比例封面，每个平台独立验收，最后停在最终发布按钮之前交给人工确认。用户要求「发布视频」「传视频到几个平台」「准备发布草稿」「四个平台都发一下」时使用。不负责剪辑、转码、生成封面，也不点击最终发布。
---

# 多平台视频发布准备

把一条视频变成四个平台上**经过独立验收的草稿**，停在发布按钮前。

**这个 skill 永远不点最终发布。** 它只负责把草稿准备到可人工复核的状态。

## 必读

按任务类型读取，不要一次全读：

| 什么时候读 | 读哪个 |
|---|---|
| **动手前**（总是） | `references/platforms.md` —— 四平台字段映射 |
| 需要精确选择器 | `references/selectors.md` |
| **每次验收**（总是） | `references/verification.md` |
| 遇到失败或平台改版 | `references/gotchas.md` |
| 新机器 / 环境报错 | `setup/prerequisites.md` |

---

## 硬边界

- **绝不点击任何最终发布按钮**：`发布` / `发布笔记` / `发表` / `立即投稿` / `发布`（抖音）。任何平台都不行。
- **绝不点「安排时间」「定时发布」。**
- **不要从视频内容自行推断是否勾选原创/自制声明**——只按用户的明确指示。
- **AI 生成内容声明**：默认勾选（用户偏好），除非用户说不要。
- **不使用平台推荐封面当成品**——只有用户给了封面文件才用；没有就保持默认，不要自作主张。
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
7. AI 声明        默认勾选
```

---

## 标准流程

### 0. 环境自检

```bash
bsk status                      # daemon 与浏览器连接
bsk browsers                    # 应有 chrome 连着
```

**如果会话容易中断**，检查 daemon 是否带了长空闲超时（见 `setup/prerequisites.md`）。

### 1. 接收内容包

向用户确认：

```
视频文件绝对路径
四个平台各自的标题与话题（或由你生成后经用户过目）
封面文件（按比例映射）——可选
是否勾选 AI 声明 / 原创声明
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

各平台上传口：

```bash
# 小红书
bsk upload --session $S --tab-id $T --file "$V" --selector 'input.upload-input'
# 抖音
bsk upload --session $S --tab-id $T --file "$V" --selector 'input[type=file]'
# B站  ⚠️ 必须限定在 wrapper 内
bsk upload --session $S --tab-id $T --file "$V" --selector '.bcc-upload-wrapper input[type=file]'
# 视频号 —— input 在 wujie shadow DOM 里，原生 upload 可能失败
#          用 --ref 指向可见的上传区
bsk upload --session $S --tab-id $T --file "$V" --ref '@eNN'
```

**上传后立即独立验收，不要相信 upload 的回执。**

### 3. 填字段（上传中可并行）

**小红书 / 抖音 / B站 在上传中就能填**（省时间）；**视频号锁定，必须等传完**。

字段与选择器见 `references/platforms.md` + `references/selectors.md`。

**话题必须落成真实实体**，判定方式见 `references/verification.md`。

### 4. 传封面

按比例映射（**以实际分辨率为准，不要信文件名**）：

```
3:4  → 小红书  |  抖音竖  |  视频号个人主页卡片
4:3  → 抖音横  |  B站首页推荐  |  视频号分享卡片
16:9 → 仅 B站个人空间
```

**⚠️ 完成后必须验证每个槽的 URL 不同。** 同一张图传两个槽 = 错的。

B站 点「完成」时会问「是否同步 4:3 到 16:9」—— **永远选「不同步」**。

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
