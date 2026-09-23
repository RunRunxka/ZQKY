# 玻璃主题的第三方来源与许可

> 免责：以下是工程风险判断，不是法律意见。对外正式发布前建议让懂许可的人过一遍。
>
> 本文件是玻璃主题（`apps/web/src/styles/glass.css` 及背景层组件）的来源与许可台账。
> 学习问答参考包的资源台账在 [`../deeptutor-chat/README.md`](../deeptutor-chat/README.md)。

## 1. 现状一览

| 资产 | 项目内位置 | 来源 / 许可 | 能否随公开产物分发 |
| --- | --- | --- | --- |
| 流体背景（着色器） | `apps/web/src/components/layout/fluid-shader.ts` | **自研实现**（AGPL-OUT v1 替换，2026-09-23） | ✅ 可 |
| 流体色调表 | `apps/web/src/components/layout/fluid-tones.ts` | **自研实现**（同上） | ✅ 可 |
| 玻璃磨砂配方 | `apps/web/src/styles/glass.css` | 通用 Web 技术（`backdrop-filter` + 半透明填充 + 固定背景层）的自有实现，选择器为自有类名 | ✅ 可（判断依据见 §3） |
| 字体 Chat Geist / Chat Lora | `apps/web/public/fonts/chat/` | SIL OFL 1.1，随 `Geist-OFL.txt` / `Lora-OFL.txt` | ✅ 可，发布时须保留两份 OFL 文本 |
| thinking-orbs | `apps/web/src/features/chat/vendor/thinking-orbs/` | MIT（目录内自带 LICENSE） | ✅ 可 |

**当前没有已知的 copyleft 传染项。** 下节记录此前存在、现已消除的那一项。

## 2. 已消除：AGPL-3.0 流体背景（AGPL-OUT v1，2026-09-23）

### 2.1 问题（两层，不是一层）

原 `fluid-shader.ts`（491 行）与 `fluid-tones.ts`（70 行）是**逐行移植**，文件头自述：

- 移植自 **DSH-Transparent-UI-Plugin（AGPL-3.0）**，且"除本头注释外代码与上游保持一致"；
- 其中 GLSL 着色器源码 **"verbatim from the site bundle"** —— 即字面量抄自 **deepseek.com 线上包**。

第二层比第一层更麻烦：AGPL 至少还有许可条款可循（附加许可证、公开整份源码），
而站点 bundle 的着色器源码**没有任何许可授权**，属于未授权复制，"补个 LICENSE"解决不了。

此外这两个文件是**静态 import**，即使界面上关掉流体开关也照样进 bundle；
而流体层默认是开启的（`GlassBackdrop` 在 localStorage 键缺失时视为开），
所以"关开关"不构成授权层面的处置。

### 2.2 处置：整份替换为自研实现

| | 原（已删除） | 现（自研） |
| --- | --- | --- |
| 算法 | WebGL2 双通道 ping-pong 流体求解 + 域扭曲噪声渲染 | 低分辨率 Canvas 2D + 正弦叠加驱动的软光斑 + 放大柔化 + `lighter` 叠加 |
| 依赖 | WebGL2 / GLSL | Canvas 2D |
| 规模 | 约 560 行 | 约 345 行（含注释） |
| 共用代码 | — | **零**。字段名相同仅因接口兼容 |
| 对外接口 | — | **完全一致**：`FluidParams` / `SITE_FLUID_PARAMS` / `FluidShaderHandle` / `attachFluidShader` / `fluidToneColors` / `HUE_BASE` |

接口一致使调用方改动极小，但**不是"零改动"**：`GlassBackdrop.tsx` 原有的
`canvas.getContext('webgl2') === null` 预检必须改为 `'2d'`。原因见 §2.3。

### 2.3 换实现时必须改预检（已实测的机制）

一个 canvas 只能持有一种上下文。实测（headless Chromium）：

```
先取 webgl2 再取 2d → null（槽位被占用）
先取 2d   再取 2d → 同一个对象
```

因此在 Canvas 2D 实现下，WebGL2 预检会导致：WebGL2 可用时槽位被占、`getContext('2d')` 返回
null（画布全空白却标记 `data-glass-fluid-ok='on'`，而该标记会 `display:none` 掉 CSS 环境光
→ 背景彻底空白）；WebGL2 不可用时直接走回落。两种机型都不会渲染。
改为 2D 预检后安全：同类型 `getContext` 返回同一对象。

### 2.4 替换后的真实浏览器证据

`qa/AGPL-OUT/fluid-browser-check.cjs`（1440×900、深色玻璃、流体开）：

| 场景 | `data-glass-fluid-ok` | 画布 | 平均亮度 | 亮度标准差 | 帧间变化 |
| --- | --- | --- | --- | --- | --- |
| 常态 | `on` | 144×90 有像素 | 11.13（近黑） | 5.5 | **true（在动）** |
| `data-motion=reduced` | `on` | 同上 | 11.13 | 5.5 | **false（不循环）** |

即：流体确实在绘制（非纯色、非空白）、CSS 环境光被正确让位、减少动画下只画一帧。

## 3. `glass.css` 的磨砂配方为什么可以分发

**事实**：该文件此前头部注释自述"技术平移自 DSH-Transparent-UI-Plugin 的磨砂配方"，
但同一段注释也写明"选择器全部替换为 ZQKY 自有类名"，不依赖任何外部运行时。

**判断**：`backdrop-filter: blur()` + 半透明填充 + 固定背景层是通用 Web 技术；
本文件没有复制上游的选择器、文件结构或运行时代码。著作权保护表达而不保护技术路线，
因此按"自有实现"处理。AGPL-OUT v1 已把该注释改写为不依赖任何外部来源的表述，
并在本文件完整披露这段历史。

**若将来要更保守**：把 `glass.css` 按自有类名整体重写一遍（配方本身很短），
代价是 1~2 小时 + 一轮像素比对。当前判断为**不需要**。

⚠️ 无论怎么改，**不要写 `-webkit-backdrop-filter`**：Turbopack 的 lightningcss 在标准属性
与前缀并存时会丢弃标准属性，磨砂会整体失效且计算值为 `none`。

## 4. 复核方法

想确认现状，做这三件事即可：

1. **全仓搜索**这三个词：`AGPL`、`DSH-Transparent`、`WYH66666666`。
   预期只剩两类命中：`fluid-shader.ts` / `fluid-tones.ts` 头部"本文件此前是…已替换"的
   来源说明，以及本文件与 `qa/AGPL-OUT/`。**不应再有任何承载 AGPL 代码的文件。**
2. **确认流体已是 Canvas 2D**：`apps/web/src/components/layout/` 下不应再出现 `webgl2`，
   `attachFluidShader` 与 `GlassBackdrop` 的预检都应走 `getContext('2d')`。
3. **浏览器端确认真的在画**（先 `npm run build`，再起一个构建产物服务）：

   ```bash
   node qa/AGPL-OUT/fluid-browser-check.cjs http://127.0.0.1:5174
   ```

   预期：常态 `fluidOk: "on"` 且 `changedBetweenFrames: true`；
   `data-motion=reduced` 时 `changedBetweenFrames: false`。

> 注意：本机 shell 的 `grep` 搜中文会静默返回空，`rg` 未安装。全仓搜索请用编辑器/IDE 的
> 搜索功能，这些词都是 ASCII，用任何带全仓索引的工具都可以。
