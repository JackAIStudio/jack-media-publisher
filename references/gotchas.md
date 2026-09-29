# 踩坑记录

按"会不会让你白干一场"排序。每条都是实测撞出来的，不是推测。

---

## 一、bsk 的文件大小双限制（最要命）

**bsk 的 `upload` 不是"把路径交给浏览器"，而是"暂存一份副本 → WebSocket 分块传输 → 扩展 → 塞给浏览器"。**

```
transfer.begin → transfer.chunk → transfer.finish
```

所以有**两道硬限制**：

| 限制 | 实测报错 |
|---|---|
| **单文件 512 MB** | `file size 765599973 exceeds transfer limit 536870912` |
| **会话累计 512 MB** | `session transfer staging exceeds limit 536870912` |

**会话额度按会话独立计**——开新会话就重置。但**单文件上限跨会话依然存在**。

**而且额度记账是缓存的**：手动删掉 `~/.bsk/run/transfers/` 里的文件**不会**让它重新计算。

### 解法：改用「本地服务器 + 页面内注入」

```bash
# 1. 起一个带 CORS 的本地服务（Chrome 视 127.0.0.1 为可信源，HTTPS 页面也能取）
python3 -c "
import http.server, socketserver, os
os.chdir('/tmp')
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        super().end_headers()
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
with socketserver.TCPServer(('127.0.0.1', 8899), H) as h: h.serve_forever()
" &

# 2. 页面内 fetch 成 File 再注入
```

```js
(async () => {
  const r = await fetch('http://127.0.0.1:8899/video.mp4');
  const b = await r.blob();
  const dt = new DataTransfer();
  dt.items.add(new File([b], 'video.mp4', { type: 'video/mp4' }));
  const inp = document.querySelector('<上传口选择器>');
  inp.files = dt.files;
  inp.dispatchEvent(new Event('change', { bubbles: true }));
})()
```

**实测：730 MiB / 1.1 GB 都能注入，耗时 1.2–1.5 秒，无上限。**

**额外好处**：**不消耗 bsk 的任何传输额度**（暂存区保持 0 B），一个会话就能跑完所有平台。

**注意**：注入产生的是**不可信事件**（`isTrusted: false`）。实测四个平台都能接受，但**平台改版后要重新验证**。

---

## 二、bsk 会话空闲 5 分钟自动关闭

默认配置：

```
SESSION IDLE  5 分钟      ← 会话空闲就自动关闭 Agent Window
DAEMON IDLE   10 分钟
```

**后果**：你埋头调一个平台，其他平台的窗口超时被关。关窗时 Chrome 发现页面有未保存内容，弹出「**离开此网站？**」保护提示——**B站 和视频号的草稿就是这么丢过一次。**

**修法**（需要重启 daemon，会关掉所有窗口）：

```bash
bsk daemon restart --session-idle 4h --daemon-idle 8h
```

**这是环境必备项，不是可选项。**

---

## 三、Chrome 的调试横幅

BrowserSkill 挂上调试器时，Chrome 会在**所有窗口**顶部显示：

> 「BrowserSkill 已开始调试此浏览器」

**它只是提示，不影响功能**，但很占空间且污染无关窗口。

**压制方式**：Chrome 必须以启动参数启动：

```bash
open -a "Google Chrome" --args --silent-debugger-extension-api
```

**⚠️ `open -a` 只在 Chrome 未运行时才传参数**——已在运行的话只是切到前台，参数被忽略。必须先完全退出 Chrome。

**已做成启动器**：见 `setup/chrome-silent/`。

**别改 Chrome 本体**（替换 `MacOS/Google Chrome` 二进制）——破坏签名，且每次自动更新都会失效。

---

## 四、BrowserSkill 扩展需要「允许访问文件网址」

没有这个权限时，文件上传会报（**两种措辞都遇到过，都要认出来**）：

```
cdp_failed: {"code":-32000,"message":"Not allowed"}
phase: set_files
```

2026-09-29 实测的另一种措辞（默认 `input` 模式）：

```
error: the browser could not attach the staged file to the input
hint: check that BrowserSkill has Chrome's 'Allow access to file URLs' permission; otherwise use `bsk request-help`
details: {"code":-32000,"message":"Not allowed"}
```

以及 `--mode drop` 下的第三种：

```
error: the browser could not complete the native file drop
details: {"code":-32602,"message":"Not allowed"}
```

**关键：`bsk status` 和 `bsk doctor` 在这个状态下【全绿】。** 光看状态发现不了，必须实传一次文件（见 SKILL.md 步骤 0 的探针）。

**用大文件和小文件报同一个错**，就能排除"文件太大"，直接锁定是权限问题（实测：76 MB 的视频和 630 KB 的封面报的错一模一样）。

**开启方式**：`chrome://extensions` → BrowserSkill → 详情 → 打开「**允许访问文件网址**」。
直达链接：`chrome://extensions/?id=hhcmgoofomhgciiibhipgmgkgnoenaoi`

**注意是 BrowserSkill 那个扩展**，不是别的。

⚠️ **这个权限开了之后，已经存在的 bsk session 不会自动复活** —— 重新 `bsk session start` 再传。

---

## 五、B站 封面的双面板陷阱

B站 封面有 **4:3（首页推荐）** 和 **16:9（个人空间）** 两个独立面板。

**坑一：上传前不确认激活面板 → 图进错槽**

实测错误序列：

```
① 传 横版-4x3.png   → 进 4:3 ✅
② 点 16:9 面板      → 没激活成功（没验证）
③ 传 16x9.png       → 又进 4:3 ❌ 把正确的图覆盖了
④ 真正激活 16:9
⑤ 再传 16x9.png     → 进 16:9 ✅
```

**结果**：4:3 槽里躺的是 16:9 的图，被按 4:3 裁切后"放大被切"，很难看。

**修法**：**上传前必须验证目标面板是 active 状态。** 面板的 active/inactive 类有时不暴露，此时靠点击目标面板元素（mousedown → mouseup → click）并观察哪个槽的图变了来确认。

**坑二：点「完成」时平台提议"同步"**

> 「检测到个人空间封面（16:9）未修改。是否将「4:3封面」的改动同步到「16:9封面」？」
> 　`不同步，手动编辑`　`确认同步`

**如果点「确认同步」，4:3 的图会覆盖掉正确的 16:9。**

**永远选「不同步」**（除非确实要两张一样）。

**坑三：只看"有图"就以为对了**

**必须分别验证两个槽的 URL 不同。** 同一张图传两个槽会得到相同 URL——那是错的。

---

## 六、视频号的「保存草稿」不保存视频标注

实测复现两次：

```
设置 视频标注 = 含AI生成内容  →  保存草稿  →  重新打开
结果：视频标注回到「选择视频标注」❌
（同一轮里，短标题的清空【能】保存住 ✅）
```

**所以视频标注必须作为最后一步设置，设完不再保存草稿，直接交给人工复核发布。**

**或者：人工在点「发表」前自己确认一遍。**

---

## 七、B站 会自动塞不相关的标签

实测被塞过：

```
V2（文件名）、生活记录、记录、日语现场、音乐现场、LIVE
```

**它们会占掉 10 个标签名额。** 实测一次塞了 3 个（`日语现场/音乐现场/LIVE`），导致目标标签只进了 7 个。

**做法：上传后先删掉无关标签（`.label-item-v2-container` 里的 `svg.close`），再补目标标签。**

⚠️ **空标签输入框时不要按 Backspace** —— B站 会理解成"删除最后一个标签"。

---

## 八、小红书封面编辑器加载不了大视频

4K / 730 MB 的视频，封面编辑器可能报：

> 「视频加载中，可上传图片或加载完成后选取视频帧」
> 「**视频加载遇到问题**，可以尝试以下两种解决方案：
> 　1. 检查浏览器设置
> 　2. **回退到旧版封面编辑弹窗**」

**用它的官方退路：点「回退到旧版封面编辑弹窗」。**

旧版界面会直接给出 **比例 3:4 / 4:3 / 1:1** 和裁剪工具，功能完整。

---

## 九、小红书的话题建议面板有竞态

面板出现得慢，且会重渲染。

**"先标记元素 → 再按标记点击"会失败**：标记和点击之间面板重渲染，**坐标漂移，点到别的项**。

实测后果：想选 `#DeepSeek`，结果落成了 `#DeepSeek人设`。

**必须用快照取 ref，再点 ref。**

---

## 十、抖音 `#添加话题` 的 ref 会变

固定 ref 会导致点击落空，**文字被当纯文本打进编辑器**（没有 `#` 前缀，不成为实体）。

**每轮都要重新解析它的 ref。**

---

## 十一、平台字段在上传期间的可编辑性不同

| 平台 | 上传中能填？ |
|---|---|
| 小红书 | ✅ 标题 / 话题 / 声明 / 封面 |
| 抖音 | ✅ 标题 / 声明 |
| B站 | ✅ 标题 / 标签 / 声明 |
| **视频号** | ❌ **锁定**：「文件上传中，请等待完成后再编辑」 |

**所以「上传中预填」策略只适用于前三家。视频号必须等传完。**

---

## 十二、平台会改版

实测期间遇到的改版：

- **B站封面编辑器**新增「智能生成封面」弹窗，要先点「不使用」才能进手动上传
- **B站封面**从"两个并排上传区"改成"4:3 / 16:9 双面板"
- **小红书封面**引入新版编辑器（带模板/贴纸），大视频会失败
- **视频号封面**（2026-09-29 实测）**从双槽改成了【单一 3:4 槽】**——页面上写的是「个人主页和分享卡片(3:4)」，不再有单独的 4:3 分享卡片槽。所以横屏封面在视频号**没有槽可放**，别以为漏传了
- **小红书「内容类型声明」**（2026-09-29 实测）**四个选项里没有"无需声明"**（虚构演绎 / 笔记含AI合成内容 / 内容包含营销广告 / 内容来源声明）——**留空就是"无需声明"的表达**

**所以这份文档里的选择器都有保鲜期。失效时先怀疑改版，不要怀疑自己的操作。**

---

## 十三、隐藏的 file input 会被 bsk 拒掉（四个平台全踩）

四个平台的 file input **全都是隐藏的**（`0×0` / `opacity:0` / `display:none`）。直接拿 input 当 target：

```
error: target element has no visible geometry
hint: rerun snapshot and choose a visible child ref, or wait/scroll/reload before retrying
```

**这不是权限问题，也不是操作问题——那个元素本来就不占位。**

**修法**：指向**可见的投放区**（小红书/抖音 `div.drag-over`、B站 `.bcc-upload-wrapper div.upload-area`、视频号用 `--ref` 指可见区）。完整的可见祖先探针见 `selectors.md` 的「文件上传」节。

⚠️ 这条和第四条（文件访问权限）**报错完全不同**，别混：几何问题报 `no visible geometry`（本地就能判断），权限问题报 `Not allowed`（要动浏览器设置）。

---

## 十四、B站 有些词是「仅话题」，在标签框里会静默消失

实测（2026-09-29）`WorkBuddy`：标签框里**打字 → 回车 → 文字被清空、标签不落地、连报错都没有**。

同批的 `DeepSeek` / `Kimi` / `AI` 都正常，所以**不是大小写、不是英文、不是输入法的问题**。

**根因**：B站 有些词只作为**话题**存在（WorkBuddy 话题页 993.4 万次播放），不能当自定义标签。

**解法（实测有效）**：

```
参与话题  →  搜索更多话题  →  搜索框输入词  →  选中该话题  →  确定
```

走完这条路，`WorkBuddy` 会出现在 `.label-item-v2-content` 里（标签 7 → 8 个，存盘复查后仍在）。

**兜底**：这条路也走不通时，**留成一条明确的待办报给 Jack，绝不悄悄换成别的词**（oil-oil 文档的明确要求：*Do not silently drop or replace the requested tag.*）。

---

## 十五、bsk session 会因为「中断」或「超时」整个消失

实测两次踩到：

| 触发 | 后果 |
|---|---|
| `bsk request-help` 被 abort（用户在 Agent Window 按了停止） | session 直接没了 |
| 长时间不操作 | session idle 超时关闭（默认 5 分钟，见第二条） |

**后果**：**已开的 Agent Window 和里面所有 tab 全丢**，正在做的平台要从头再来一遍。（平台侧的草稿是存住的，续做时按 SKILL.md 的幂等三态判定，**不要重放上传**。）

**所以三件事**：

1. 按第二条把 session idle 调长（`bsk daemon restart --session-idle 4h --daemon-idle 8h`）；
2. **开工前把环境自检一次做完**（尤其第四条的文件访问权限），别做到一半因为环境问题被打断；
3. 中断后先跑 `bsk session list` / `bsk browsers`，再 `bsk session start` + 从平台当前状态续做。

⚠️ 收到「用户中断」信号时，按 SKILL.md 硬边界**立即停手问用户**，不要自行重试。
