# UX-PERF-CLOSEOUT v1 批次证据（2026-09-23）

本批覆盖用户 2026-09-23 八节指令：长推理流性能收口、学习问答模式菜单、学习记录与导航与图标、
教案工作台布局、全站双语字体与排版、文档整理、组织与交付门槛。
独立验收见 [A1 r1（needs_revision）](A1-REPORT-01.md) → [A1 r2（pass）](A1-REPORT-02.md)；
任务卡与文件归属见 [TASK-CARD.md](TASK-CARD.md)；「更多能力」移除的可达性清单见
[REACHABILITY-AUDIT.md](REACHABILITY-AUDIT.md)。

起点：`main@3dcace8`（工作区干净）。原始取证数据、脚本与截图在 `_work/perf-20260923/`
（Git 忽略）：受控上游、性能探针、正确性回归、菜单探针、字体审计。

## 1. P0 长推理流卡顿：复现与根因

**取证方法**：`_work/perf-20260923/mock-upstream.mjs`（受控 SSE 上游，确定性文本：中文段落 +
粗体 + 列表 + 行内公式 + 围栏代码 + 块级公式 + 表格，按固定分块/间隔流出）+ `perf-probe.mjs`
（Chrome DevTools Protocol `Performance` 域取主线程脚本/布局/样式重算累计时长，rAF 采样帧间隔，
`PerformanceObserver` 取长任务与 Event Timing，IDB `put` 打点统计写盘次数与字节，`MutationObserver`
统计推理容器 DOM 更新次数；隔离浏览器上下文 + 独立 IndexedDB，不读写用户草稿）。
**Performance trace 已保存**：`_work/perf-20260923/trace-50k.json`（CDP Tracing `devtools.timeline`、10 kHz 采样、
136 MB，可在 DevTools Performance 面板 Load profile 打开；主线程关键事件子集 `trace-50k-mainthread.json` 51 MB）。
用 trace 独立复核布局/样式重算时长与 CDP 指标一致（trace：layout 2.02 s / style 215 ms；CDP：layout 2.30 s / style 209 ms），
说明 CDP 口径可信。**未直接测量 React commit 次数**（以推理容器 DOM 更新次数 10 455→383 与主线程脚本时长作为等价证据）。
长任务观察器有效（见 §3.1 与 §10 的订正：首版探针用 `{type:'longtask',buffered:true}` 时静默无输出，
改用 `entryTypes` 后取到 210 条 → 0 条）。

**首败（真实数据，50k 字推理 / 30.9s 流）**：帧间隔 p95 **166.7 ms**（约 6 fps）、最大 316.7 ms，
**215 帧超过 50 ms、112 帧超过 100 ms**；主线程脚本 **28.3 s**；推理容器 DOM 更新 10 455 次；
流式期间一次按键从派发到处理完成最慢 **71.7 ms**（20k + 长历史场景）；堆峰值 102 MB。

**主热点（按证据排序，非静态推断）**：

1. **每个增量都对增长中的完整推理文本重跑 Markdown/数学/高亮解析**：`ReasoningDisclosure` 把
   `text` 交给 `AnswerMarkdown`（remark-gfm + remark-math + rehype-katex + rehype-highlight）。
   证据：脚本耗时随文本量超线性增长（5k→1.2 s、20k→6.7 s、50k→28.3 s），DOM 更新次数与增量数同阶。
2. **每个增量提交一次 UI**：`store.change()` → `publish()` 每次重建会话列表数组，并让整棵消息列表重渲染。
3. **每 400 ms 落盘一次整表**：`flush()` 的 `while (dirty.size)` 在持续增量下把新脏数据不断接进同一轮循环，
   实测一次 50k 轮写入 177～184 次 / 3.6～4.1 MB（约每 170 ms 一次整表结构化克隆）。
4. **推理容器每次提交做同步布局读写**（`scrollTop = scrollHeight`）。

`ThinkingOrb` 的常驻动画成本单独测量：终态后 3 s 空闲窗内帧间隔 p95 5.6 ms、脚本 126～134 ms，
减少动画下同窗脚本 7～8 ms → 单个 orb 约 40 ms/s，**不是**本批热点，未做任何删除或降级。

## 2. 优化（按证据最小改动）

| # | 改动 | 位置 |
| --- | --- | --- |
| O1 | **活跃流期间轻量呈现**：推理正文在「仍在流式」或「折叠未展开」时以纯文本（`pre-wrap`，字号/行高/颜色与展开后一致）呈现；仅在「已结束且用户正在看」时做一次完整 Markdown/KaTeX 渲染 | `ReasoningDisclosure.tsx`、`Message.tsx`、`chat-home.css` |
| O2 | **增量合并 + 可见更新时延上限**：文本/推理增量按「前缘立即 + 尾部合并」节流，最多每 80 ms 提交一次；按原顺序折叠进消息，任何非文本事件、终止/停止/断流/切会话/落盘前先 flush | `model/store.ts` |
| O3 | **滚动写入按帧合并**：跟随最新时每帧最多一次 `scrollTop` 写入，且仅在「仍在跟随」时执行 | `ReasoningDisclosure.tsx` |
| O4 | **流式期间每轮只保存进入时快照**：`flush()` 一轮保存一次快照后返回（`generation === null` 时仍循环到清空，保持「显式 flush 落全部」契约） | `model/store.ts` |

三者均不改变事件顺序与原文：原始推理文本逐字节保留、`delta` 不丢、终态/停止/断流/切会话/刷新
语义不变（正确性回归见 §4）。

## 3. 前后数据（同一受控文本、同一探针、隔离浏览器）

### 3.1 50k 字推理（桌面 1440×900，正常动画）

| 指标 | 优化前 | 优化后 | 变化 |
| --- | --- | --- | --- |
| 帧间隔 p95 | **166.7 ms** | **5.6 ms** | −96.6% |
| 帧间隔最大 | 316.7 ms | 16.8 ms | −94.7% |
| 帧 > 50 ms | **215** | **0** | 归零 |
| 帧 > 100 ms | **112** | **0** | 归零 |
| 长任务（`entryTypes: ['longtask']`） | **210 条 / 23 078 ms / 最大 291 ms** | **0 条** | 归零 |
| 主线程脚本 | **28 300 ms** | **1 106 ms** | −96.1% |
| 主线程布局 | 426 ms | 2 302 ms | +440% |
| 主线程样式重算 | 345 ms | 209 ms | −39% |
| 推理容器 DOM 更新 | 10 455 | 383 | −96.3% |
| IndexedDB 写 | 99 次 / 1.75 MB | 64 次 / 1.68 MB | −35% / −4% |
| 首个可见增量 | 69 ms | **43 ms** | −38% |
| JS 堆（字段 = CDP `Performance.getMetrics().JSHeapUsedSize`，**测量窗末单次采样**，非真峰值） | 102.4 MiB | **11.4 MiB** | −89%（同场景 r4 复测 11.6 MiB；A1 独立复测 18.8～24.3 MiB —— 随 GC 时点波动，方向一致） |
| 空闲窗（终态后 3 s）脚本 | 134 ms | 126 ms | 持平（ThinkingOrb 未变） |

**变差项之一是布局总量**（426 ms → 2 302 ms）：轻量呈现是单个文本节点，每次提交都要为整段文本
重做换行；但提交次数从每增量一次降到每 80 ms 一次，单次成本被摊平，**帧间隔反而从 166.7 ms 降到
5.6 ms，0 帧超过 50 ms，长任务 210 条 → 0 条**。合入判断依据是帧间隔与长任务，而不是单项布局总量。

**另有一处由本优化引入的行为差异，已由独立验收 A1 检出并已修复（r4）**：自动跟随底部的写入从
「判断即同步写」改成「排入 rAF」后，`following` 只在 effect 内检查、rAF 回调内未复检，用户在该窗口内
上滚会被拉回（A1 实测首次上滚 `0 → 4052`；本机探针原先用「随机时刻置 0 + 延迟 1.2 s 读回」的写法
只是没命中窗口）。修法：**在 rAF 回调内再次确认仍在跟随**。验证用确定性触发（在一次推理提交刚落地的
MutationObserver 微任务里立刻把滚动置 0）——**断言反转**：移除复检行时 4/4 尝试被拉回
（窗口内最大值 1936/2596/3164/4143），恢复复检后 4/4 尝试恒为 0。原始日志已留档：
`_work/perf-20260923/stream-regression-reversal.log`（18/19，构建 `ZrHj7mKmbjFQXKXS3MZCi`）与
`_work/perf-20260923/stream-regression-fixed.log`（19/19，构建 `oNm41Sz_SmvxGHKX_M9vi`）。故此差异**已关闭**，
`§3` 的量化指标不受影响。

### 3.2 20k 字推理 + 长历史（桌面，含 4 轮长消息历史）

| 指标 | 优化前 | 优化后 |
| --- | --- | --- |
| 帧间隔 p95 / 最大 | **127.8 / 222.3 ms** | **5.6 / 11.2 ms** |
| 帧 > 50 ms / > 100 ms | 79 / 66 | **0 / 0** |
| 主线程脚本 | 10 777 ms | **703 ms** |
| 推理容器 DOM 更新 | 3 998 | 155 |
| 流式期间按键最慢处理 | **71.7 ms** | **2.0 ms** |
| JS 堆（CDP 单次采样，测量窗末） | 73.0 MiB | 18.3 MiB |

### 3.3 其余场景（探针 v2 文本）

| 场景 | 帧 p95 前 → 后 | 帧 > 50 ms 前 → 后 | 脚本前 → 后 |
| --- | --- | --- | --- |
| 5k 推理 | 5.7 → 5.6 ms | 1 → 0 | 1 235 → 173 ms |
| 20k 推理（手机 390×844） | 16.7 → 5.7 ms | 1 → 0 | 6 568 → 573 ms |
| 20k 推理（平板 1024×800） | 16.7 → 5.7 ms | 1 → 0 | 6 513 → 541 ms |
| 20k 推理（`prefers-reduced-motion: reduce`） | 16.7 → 5.7 ms | 0 → 0 | 6 365 → 214 ms |

**真实供应商未外呼**（本批性能验收不依赖真实密钥）：全部数据来自受控本地上游；
真实硬件触摸与逐帧动画曲线未测（not_run）。

## 4. 正确性回归（`_work/perf-20260923/stream-regression.mjs`）

最终候选（r4，`.next-test` BUILD_ID `hrwcN9OyO8by2EqtkSRn_`）**19/19 通过**。
「上滚不被拉回」一项的判定方式已在 r4 改为**确定性触发**（提交落地即上滚 + 逐帧采样），
并做了断言反转：移除修复行后该例失败（4/4 被拉回）、恢复后通过（4/4 恒 0）。
**首版候选（r3）曾按 A1 的独立探针复现为 18/19**（该项失败），本条如实记录，不以后续修复掩盖。

| 检查 | 结果 |
| --- | --- |
| 流中 8 次采样均为原文前缀 | PASS |
| **持久化推理原文与上游逐字节全等**（12 000/12 000） | PASS |
| 终态 `done`、正文非空 | PASS |
| 完成后推理自动折叠（折叠行为不变） | PASS |
| 展开后公式完成渲染（KaTeX 120 处、`katex-display` 22/22、0 错误） | PASS |
| 展开后仍渲染完整推理文本 | PASS |
| 停止后不再有 UI 更新、已收到内容落库、`stopped/client-stop` | PASS ×3 |
| 用户上滚后（含首次）不被强制拉回底部 | r3：**FAIL（A1 独立复现 + 探针反转确认）** → r4 修复后 PASS（详见 §3.1 末段与 §8） |
| 受控断流落错误态、保留已收到内容、有重试入口 | PASS ×3 |
| 流式中切会话：原会话已收到内容已落库 | PASS |
| 刷新后推理原文完整恢复 + 展开公式正确渲染 | PASS ×2 |
| 减少动画：折叠过渡被压制（1e-05 s）、推理仍完整落库 | PASS ×2 |

另：`apps/web/src/features/chat/model/store.test.ts`、`ask-user.test.ts` 等既有会话/追问/终态用例
在增量合并后全部通过（全量单测 52 文件 / 440 例）。

## 5. 模式菜单：横向滚动修复与 RAG 模式

**首败复现（真实测量）**：`.chat-cap-panel` 在 1440 与 1024 视口 `clientWidth=278` /
`scrollWidth=514`，`scrollLeft` 可由 0 改到 60 → **存在横向滚动条且内容可左右滑动**。
容器就是菜单面板本身（`.chat-ext-panel` 带 `overflow: auto`），溢出源是 `position: absolute;
left: calc(100% + 6px)` 的「更多能力」飞出层。

**修复后**：三视口 `clientWidth = scrollWidth = 278`，`scrollLeft` 恒为 0，页面级横向溢出 0；
菜单内无 `.chat-cap-more` / `.chat-cap-flyout`；Escape 关闭后焦点回到触发器。
详见 `_work/perf-20260923/menu-BEFORE.json` 与 `menu-AFTER.json`（含 1440/1024/390 截图）。

**替换为「RAG 模式」**：与「对话 / 追问澄清 / 智能出题 / 可视化」同一列表、同一行样式、同一
`aria-pressed` 语义，无二级菜单；不可选（与其余非对话能力同一可用性契约），行内徽标
「未接入 · 规划中」在 3 视口实测**未被裁切**；`submit()` 另保留专门的阻断文案作纵深防御。
移除项与前后端可达性清单见 [REACHABILITY-AUDIT.md](REACHABILITY-AUDIT.md)。

## 6. 教案工作台布局（T5，限范围实现者交付）

- 移除「备课空间 > 教案工作台」面包屑（壳内 `.breadcrumb` 在教案页作用域内隐藏），改为与
  `/co-writer`、`/reading` 同级的直接页面标题，计算样式逐项一致（`--font-display` / 24px / 600 / 30px / 左对齐）。
- 面板顺序改为 **编辑区 → 可折叠「教案配置」→ 教案预览**，栅格、响应式断点与阅读顺序同步调整。
- 折叠按钮只保留 `EditorPanel` 顶部一个，`aria-label`/`aria-expanded`/`aria-controls` 与状态一致；
  折叠仍是「只切 class、不卸载」，表单值/预览/撤销历史/焦点不丢（e2e 断言含 3+1 次快速点击与节点复用）。
- 打印/导出回归：`emulateMedia('print')` 下标题行被隐藏、`.paper` 可见、`page.pdf()` 输出 `%PDF-`（139 759 B）、
  「导出 Word」实际下载 118 097 B。
- 证据：`_work/perf-20260923/t5/`（三视口截图、打印与导出样例、`visual-report.json`）。

## 7. 全站双语字体与排版

**字体 token（唯一来源，`styles/globals.css`）**：`--font-ui`（界面正文黑体，含中文/拉丁/缺字回退）、
`--font-display`（标题与展示衬线）、`--font-ui-serif`（界面衬线 = display 族，用于左侧导航与学习问答）、
`--font-document`（文档内容宋体族，教案纸面，与导出 Word 一致）、`--font-mono`（代码与等宽）。
`--serif` 保留为 `--font-document` 的兼容别名。**清理结果**：全仓 CSS 中 `font-family` 具体字体名
只剩 token 定义块内的两处 `@font-face` 与 token 声明本身；`Consolas` / `'Segoe UI'` /
`'Microsoft YaHei'` / `SimSun` 等硬编码（含 `font:` 简写与多行简写）全部改为 token。

**实测（`_work/perf-20260923/font-audit/`，1440/1920/390 × 6 路由）**：

| 项 | 结果 |
| --- | --- |
| 左侧导航全部元素（导航项/品牌/分组标签/底部项/头像/学习记录） | 衬线链 `Chat Lora → 中文衬线回退`，跨 6 路由一致 |
| 学习问答（标题/消息/输入框/提示/发送按钮/模式菜单触发器） | 衬线链一致 |
| 页面标题（教材资料库/书籍/学习空间） | `Chat Lora` 24px/600/30px **完全一致** |
| 页面描述 / 主按钮 / 标签 | 黑体链一致 |
| 自托管字体资源 | `/fonts/chat/*.woff2` 全部 200；`document.fonts.status = loaded` |
| 页面级横向溢出 | 三视口 × 6 路由全部为 0 |

**阻断自托管字体（`page.route('**/fonts/**')` 直接 abort）**：字体请求 0 条，
`document.fonts.check` 对 Chat Lora 返回 false（确认确实被阻断），中文回退到系统宋体；
**三视口 × 6 路由页面级横向溢出仍为 0**，按钮无文本裁切；仅剩既有小溢出（实测为 `/chat@390` 的
`.chat-chip-popover` 57/24 与两个 `clientWidth = 0` 的隐藏 `P`），阻断字体前后**一致存在、无新增**
（`.chat-ext-unavailable` 已在本批改为按内容自适应宽度，不再溢出）。
混排样本（中文简体/繁體 + English + 0123456789 + 引号/括号/书名号/破折号/省略号 + 粗体）
正常/阻断两组截图见 `font-audit/fonts-mixed-sample.png` 与 `-nofonts.png`。

## 8. 全量 e2e 中定位并修复的问题（真实浏览器，非文档口径）

新增会话区后全量回归暴露出三个失败，逐个定位到根因后修复（**不是**把断言改松）：

1. **打印媒体下公共壳栅格错位（真实产品缺陷，已修）**：`workspace-shell.css` 把
   `.global-nav { grid-row: 1 / -1 }` 写在 `@media screen` 内，打印媒体下导航退回
   `globals.css` 的 `grid-row: 2`，落进隐式 `auto` 行并吃掉整页高度，把显式 `1fr` 行里的内容区
   压成 **0 高**（实测 `emulateMedia('print')` 下 `.chat-page` 高度 0、`grid-template-rows:
   0px 900px`）。修复前该缺陷被"导航内容只有 820px、正好留出 80px"掩盖；新增学习记录区域后导航内容变高才暴露。
   修法是在同一文件已有的 `@media print` 块内补齐 `.global-nav` / `.app-header` / `.chat-page`
   的栅格放置（与屏幕态一致），而不是改断言。定位过程用注入 HEAD 版 CSS 逐一排除
   （`chat.css` / `chat-home.css` / `workspace-shell.css` / `globals.css` / `lesson-plan.css` /
   `print.css` 全部注入后现象不变 → 确认与样式改动无关，是媒体查询作用域问题）。
2. **`chat-home.spec.ts` 桌面主区宽度断言仍按旧布局**（`宽度-220-236`）→ 按新布局改为 `宽度-220`。
3. **`sidebar-chat-fixes.spec.ts` 在 200ms 过渡未结束时量宽度**（取到中间值 62px）→ 先
   `toHaveCSS('width','220px')` 等稳定再量；**`sidebar-transition.spec.ts` 跨板块比较绝对 `y`**
   ——学习问答抽屉多了学习记录区域后其下方区块整体平移，绝对 `y` 不再是跨板块不变量 →
   改为比较**分组序号 + 组内间距**与字体/尺寸/水平位置（比原来更贴近「菜单字体和尺寸沿用学习问答」的意图）。

### 8.1 实跑数字（候选 `ZkSw3NYEUtNUBATU0sde5`）

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run lint`（`--max-warnings=0`） | **0 警告** |
| `npm run test:unit`（`NODE_OPTIONS=--no-experimental-webstorage`） | **52 文件 / 440 例通过** |
| `npm run build` | 通过，`BUILD_ID = ZkSw3NYEUtNUBATU0sde5`（性能取证用 `.next-test` = `0ZQwdSFXSsgSdMsFPOlSB`） |
| `npx playwright test`（全量 200 例） | **199 通过 / 1 失败**，唯一失败为跨批既有间歇 **R-14**（见 §9）；本批改动涉及的 spec 全部通过 |
| `npm run test:api` | **217 passed**（零后端改动，沿用基线） |
| 性能探针（受控上游，前后各一轮 + 正确性回归 19/19） | 见 §3、§4 |
| 菜单三视口 / 导航与 favicon / 字体三视口 6 路由（含阻断自托管字体） / 长标题与混排 | 见 §5、§6、§7 |

## 8.2 历史旧能力值的明确降级展示（r4 补齐）

用户第 3 节要求「历史会话中存过旧能力值时保持数据可读、**明确降级展示**，不清库、不伪造功能成功」。
r3 只做到了「数据保留 + 不会被错标成对话」，**渲染层没有任何 capability 展示路径**（独立验收 A1 据此判该条款未实现）。
r4 在消息「来源与上下文」中补齐按轮次快照的如实展示：

- 仍存在的模式 → 「模式 · 可视化」＋「该模式当前未接入，仅按轮次快照如实展示，不代表现在可以发起。」
- 已移除的模式（「更多能力」三项）→ 「模式 · 深度求解」＋「该模式入口已停用（随「更多能力」一并移除），
  此处仅按历史轮次快照如实展示，历史记录保持可读。」
- 不迁移、不回填、不清库；单测 `message-duration.test.tsx` 覆盖两种分支。

## 9. 已登记 R-14 的独立复现与定性（未修改该用例）

`tests/e2e/books-commit-safety.spec.ts:238`「双标签页并发写不同书」在本批全量回归中再次失败一次（132s），
表现为 `expect(strip(page)).toHaveCount(0, { timeout: 120_000 })` 超时。独立复现：
同文件 `--repeat-each=2` → 第 1 轮失败、第 2 轮通过（20.6s）；隔离 `-g "双标签页并发写不同书" --repeat-each=3`
→ **3/3 通过**；即间歇性、随负载出现。失败页快照逐项取证：书处于既有的
**「生成已中断（无执行器在跑）」+「继续生成」** 状态，**笔记内容与阅读进度完好**（无数据丢失）。
定性维持 **「测试假设（两本书都会自动生成完成）与既定行为（冲突预算耗尽即如实中断）不一致」**，
**非产品数据缺陷**；本批**未修改、未删除该用例、未笼统加等待时间**，处置列入下一批有界核查。
证据摘录：[r14/REPRO-EVIDENCE.md](r14/REPRO-EVIDENCE.md)。

## 10. 边界与未执行

- **RAG 仍为未接入**：`get_rag_adapter()` 恒定不可用、capability 仍 `planned`；
  `F:\ZQKY_RAG` 全程只读、未启动、未评测、未接入。菜单出现「RAG 模式」**不等于**检索能力完成，
  也不发送任何检索请求、不返回模拟检索结果。
- **真实供应商未外呼**（not_run）；真实 RAG（not_run）；移动端硬件触摸（not_run）；
  逐帧动画曲线（属 H6 总验收，not_run）。
- 长任务探针**有效**：改用 `PerformanceObserver({ entryTypes: ['longtask'] })` 后，优化前基线取到
  **210 条 / 23 078 ms**、优化后为 **0 条**（首版探针用 `{ type: 'longtask', buffered: true }` 时静默无输出，
  已弃用；该首版数据另见 `_work/perf-20260923/baseline-suite-probe-v1.log`，不作结论依据）。
- 受控上游最初因响应头 `connection: keep-alive` 被 Next 代理整块缓冲（1 个 71 KB 块），
  已修正为真流式（201 块 / 3 s）；被缓冲那一轮的数据作废并单独归档在
  `_work/perf-20260923/harness-buffered-invalid/`，不计入任何结论。
