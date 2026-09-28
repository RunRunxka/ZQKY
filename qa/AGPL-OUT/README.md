# AGPL-OUT v1 批次证据

批次：**移除 AGPL-3.0 流体背景并替换为自研实现**，2026-09-23。
起因：用户指出"项目后面可能公开使用，使用这个带 AGPL-3.0 有麻烦"，并要求把已写在
`glass-chat-scaffold` 里的原创流体实现搬回本项目替换。

## 1. 处置对象与问题性质

| 文件 | 起点状态 |
| --- | --- |
| `apps/web/src/components/layout/fluid-shader.ts`（491 行） | 头部自述移植自 DSH-Transparent-UI-Plugin（AGPL-3.0）"除本头注释外代码与上游保持一致"；且自述 GLSL 源码 "verbatim from the site bundle"（抄自 deepseek.com 线上包，**无任何许可**） |
| `apps/web/src/components/layout/fluid-tones.ts`（70 行） | 同为 AGPL-3.0 移植版 |

两个文件全部历史只有一个提交 `bba132a`，之后**没有任何移除/替换/合规动作**；
它们是静态 import（关掉流体开关也照样进 bundle），且流体层默认开启。

## 2. 做了什么

- **整份替换为自研实现**（不用"改写"路线：改写仍属演绎作品，不消除传染）。新实现为低分辨率
  Canvas 2D + 正弦叠加驱动的软光斑 + 放大柔化 + `lighter` 叠加；对外接口完全一致。
- **同步改调用方上下文预检**：`GlassBackdrop.tsx` 的 `getContext('webgl2')` → `getContext('2d')`。
- **行为对齐**：补齐本地 `data-motion=reduced`（原版只判系统偏好）；粗指针设备不注册指针视差。
- **文案与注释去 WebGL 表述**：设置页开关"WebGL 流体背景"→"流体背景"；`glass.css` 两处注释改写。
- **台账补齐**：新建 `docs/licenses/glass-theme/README.md`（原台账从未登记这两个 AGPL 文件）。

## 3. 首败机制证据（headless Chromium 实测）

一个 canvas 只能持有一种上下文。在真实浏览器里实测：

```
先取 webgl2 再取 2d → null（槽位被占用）
先取 2d   再取 2d → 同一个对象
```

**结论**：若不改预检就把实现换成 Canvas 2D，会出现两种都不会渲染的机型分支——
WebGL2 可用时槽位被占、`getContext('2d')` 返回 null，画布全空白却仍标记
`data-glass-fluid-ok='on'`，而该标记会 `display:none` 掉 CSS 环境光 → **背景彻底空白且不报错**；
WebGL2 不可用时直接走回落。改为 2D 预检后安全（同类型取回同一对象）。

## 4. 真实浏览器验证（`fluid-browser-check.cjs`）

1440×900、深色玻璃、`zqky.glass=on` + `ambient` + `fluid=true`，读取画布像素：

| 场景 | `data-glass-fluid-ok` | 画布 | 平均亮度 | 亮度标准差 | 色调数 | 帧间变化 | CSS 环境光 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 常态 | `on` | 144×90 | 11.13（近黑） | 5.5 | 264 | **true** | 已让位 |
| `data-motion=reduced` | `on` | 144×90 | 11.13 | 5.5 | 257 | **false** | 已让位 |

判定：流体确实在绘制（非纯色、非空白、非全透明）；CSS 环境光被正确让位、无双重绘制；
减少动画下只画一帧、不进入帧循环。原始输出见 `fluid-browser-output.txt`。

## 5. 工程检查（实跑）

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run lint`（`--max-warnings=0`） | 通过，0 警告 |
| `npm run test:unit` | **49 文件 / 379 例通过**（上一批 47/367，净增 2 文件 12 例：`fluid-shader.test.ts` 6 例 + `fluid-tones.test.ts` 6 例） |
| `npm run build` | 通过，`BUILD_ID = hkta-oovvflBHWmLYCGdh` |
| `apps/api` pytest | 未执行（本批零后端改动） |

## 6. 本批明确未做

- **未做新旧实现的逐像素对齐**：原实现已删除，无法同机对比；`glass-chat-scaffold` 里的
  MAD 4.55 是另一套环境下的历史数字，不作为本批证据。
- **未做全站许可审计**：只处置了这一条已知红线。`glass.css` 磨砂配方按通用技术自有实现处理
  （依据见台账 §3），未重写。
- 未跑全量 e2e（168）、未做移动真机、未做独立 A1 验收。
- 参数兼容性：`FluidParams` 中 `decay / distortBoost / noiseBoost / swirlBoost / distortion /
  swirl / swirlIterations / shapeScale / rotation / proportion` 为接口兼容保留，新实现不读取
  （设置页仍会写入 localStorage，但不再影响画面）。
