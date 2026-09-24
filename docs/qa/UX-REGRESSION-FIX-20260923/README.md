# UX-REGRESSION-FIX v1 批次证据（2026-09-23）

用户在 `main` 上人工视觉验收发现三项回归，本批只修这三项：**学习问答 LaTeX 公式**、
**教案工作台顶栏**、**教材资料库到书籍/课程的返回路径**。任务卡与文件归属见 [TASK-CARD.md](TASK-CARD.md)。

起点 `main@3a2e4a8`（工作区干净）。取证脚本与原始数据在 `_work/regression-20260923/`（Git 忽略）。

## 1. 首败复现（改代码之前，隔离浏览器 + 受控上游）

### 1.1 学习问答 LaTeX：**流式推理全程不渲染公式**

受控上游流式输出含四种定界符的推理与正文（`_work/perf-20260923/mock-upstream.mjs`），
探针 `repro-latex.mjs` 采样流式/完成/刷新四个时点：

| 时点 | 推理容器 | 观测 |
| --- | --- | --- |
| 流式 1.5 s | `mode=raw` | **katex=0**、原文里 **61 个 `$`** 原样显示 |
| 流式 3.5 s | `mode=raw` | katex=0、174 个 `$` |
| 流式 6.0 s | `mode=raw` | katex=0、264 个 `$` |
| 流式 9.0 s | `mode=raw` | katex=0、294 个 `$` |
| 完成后（未展开） | `mode=raw` | katex=0（`renderRich = open && !streaming`，完成后自动折叠即不渲染） |
| 展开后 | `mode=markdown` | katex=123、katex-display=24、errors=0（仅此才正确） |
| 刷新恢复后 | `mode=markdown` | katex=123、errors=0 |
| 正文（回答）| AnswerMarkdown | katex=3、katex-display=2、errors=0（正文一直是正确的） |

定位结论：**问题在「推理过程」的流式呈现**，不在正文、不在落库。根因是上一批 UX-PERF-CLOSEOUT v1 的
「活跃流期间一律以纯文本轻量呈现」（`ReasoningDisclosure` 的 `streaming=true` 分支），
把「性能」做对了但把「流式期间可见公式」做没了。落库原文完整（reasoningLen=12000），复制/导出用原文。

**项目既有用例早已守着这条契约**：`tests/integration/chat-reasoning.spec.ts` 在流式阶段断言
`page.locator('.chat-reasoning-body .katex')).toBeVisible()` —— 该套件不属于本机每批默认跑的
`npm run test:e2e`（需 `npm run test:chat` + 真实代理），所以上一批没触发；本批把它扩成 8 条断言并纳入交付门槛。

### 1.2 教案工作台顶栏：标题占独立一栏

| 视口 | 标题位置 | 顶栏 | 网格行 | 结论 |
| --- | --- | --- | --- | --- |
| 1920 | y=84（标题块） | y=0..66 | `66px 58px 956px` | 标题不在顶栏行，多出 58px 一栏 |
| 1440 | y=82 | y=0..66 | `66px 54px 780px` | 同上 |
| 1024 | y=80 | y=0..66 | `66px 52px 682px` | 同上 |
| 390 | y=72 | y=0..59 | `59px 48px 683px 54px` | 同上 |

### 1.3 教材资料库返回路径：两个列表页没有返回入口

`/books` 与 `/courses` 列表页 `toKnowledgeBase=[]`（页面上没有任何指向 `/knowledge-bases` 的链接）；
详情页已有「返回书籍列表」「返回课程列表」（保留）。

## 2. 修复与修复后实测

### 2.1 公式：流式安全切分 + 按块复用解析（新文件）

- 新增 `features/chat/model/markdown-segments.ts`（纯函数，11 例单测）：把流式文本切成
  「已完整结束的块」+「未完成尾段」，块只在空行边界切、**不切进未闭合围栏/`$$` 块级公式/表格**，
  松散列表不拆；尾段超过 4000 字符时把**前面已闭合的行边界**上提为块（每次提交只解析受长度约束的尾段）。
  不变式：`blocks.join('') + tail === text`（逐字保留）。
- 新增 `features/chat/StreamingMarkdown.tsx`（6 例单测）：块逐块交给 memo 化的 `AnswerMarkdown`
  （块内容不变 → 解析结果复用，整轮解析量 O(n)）；尾段定界符闭合时同样用 Markdown 渲染
  （**公式流式即显**），未闭合/超长时按原文显示、补齐后自动转公式。
- `ReasoningDisclosure`：展开时渲染（流式期间也渲染）；折叠后保留内容 320 ms 覆盖 300 ms 折叠过渡
  （避免折叠动画变成"空框收缩"），从未展开的历史消息不渲染（不做无谓解析）。

**修复后同一探针（`_work/regression-20260923/repro-latex.json`）**：

| 时点 | 修复前 | 修复后 |
| --- | --- | --- |
| 流式 1.5 s | `mode=raw`，katex=0，61 个原文 `$` | `mode=markdown`，**katex=27**，katex-display=3，errors=0 |
| 流式 3.5 s | katex=0，174 个 `$` | **katex=68**，katex-display=15，errors=0 |
| 流式 6.0 s | katex=0，264 个 `$` | **katex=107**，katex-display=23，errors=0（仅 1 处未闭合尾段按原文） |
| 完成后展开 | katex=123 | katex=123、errors=0（不变） |
| 刷新恢复 | katex=123 | katex=123、errors=0（不变） |
| 落库原文 | 12000 | 12000（逐字不变） |
| KaTeX 字体 | `KaTeX_Main, "Times New Roman", serif` | 同（未被正文衬线覆盖） |

### 2.1.1 正文（回答）侧的对照核验（未被本批改动，作基线）

同一受控上游的正文含四种定界符 + 代码围栏里的 `$HOME 与 $((1+2))` + 未闭合 `$x + y`：

| 观测 | 值 |
| --- | --- |
| `.katex` / `.katex-display` / `.katex-error` | 3 / 2 / **0** |
| 代码里的美元符号 | `$HOME 与 $((1+2))` **保持原文**（`keepsCodeDollar=true`） |
| 未闭合行内片段 | `$x + y` **保持原文**、不产生 katex-error |
| 代码字体 | `"Cascadia Mono", Consolas, …`（等宽 token，未被正文衬线覆盖） |

### 2.2 教案顶栏（四视口实测）

| 视口 | 独立标题栏 | 标题在顶栏内 | 与导出同行 | 网格行 | 编辑区 top = 顶栏底 | 溢出 |
| --- | --- | --- | --- | --- | --- | --- |
| 1920 | 无 | 是 | 是 | `66px 1014px` | 66 = 66 | 0 |
| 1440 | 无 | 是 | 是 | `66px 834px` | 66 = 66 | 0 |
| 1024 | 无 | 是 | 是 | `66px 734px` | 66 = 66 | 0 |
| 390 | 无 | 是 | 是 | `59px 731px 54px` | 59 = 59 | 0 |

字体/字号/字重保持与协同写作、沉浸阅读同级（`--font-display` / 24px / 600 / 30px / 左对齐）；
窄屏不重叠、不横向溢出；导出菜单仍可用。

### 2.2.1 手机顶栏控件间隔（本轮自查发现并修复）

把标题移入顶栏后，390 视口实测发现「智启课源」与「教案工作台」**几何不重叠但间隔 0px**（视觉上贴成一体）：

| 视口 | 修复前（品牌.right → 标题.left） | 修复后 | 标题→导出 | 页面级溢出 |
| --- | --- | --- | --- | --- |
| 390 | **0px**（brand 46..146 / title 146..265 / export 268..376） | **6px**（brand 52..152 / title 158..257 / export 268..376） | 11px | 0 |
| 430 | 0px | 6px | 51px | 0 |
| 767 | 0px | 6px | 388px | 0 |

改法（`@media (max-width: 767px)`，仅教案页作用域）：`.app-header { gap: 0 → 6px }` +
`.lesson-page-title { font-size: 24px → 20px }`（窄屏要同时容纳「菜单键 + 品牌 + 标题 + 导出」，
按比例收一档；桌面仍是与协同写作/沉浸阅读同级的 24px）。截图见
`shots/after-header-390|430|1024|1440|1920.png`（对照 `shots/lesson-header-*.png`）。
**该修复在独立验收开始后加入 → 冻结记录升为 r2，r1 对 `lesson-plan.css` 的指纹随之失效（如实记录，不视为篡改）。**

### 2.3 返回路径

`/books`、`/courses` 列表页头部新增 `.space-back` 样式链接「返回教材资料库」→ 固定 `/knowledge-bases`
（不依赖 `history.back`，深链直开也能返回）；两条完整路径由 e2e 真实点击验证；全程导航唯一高亮「教材资料库」。

## 3. 性能：公式修复没有把长推理流拉回卡顿

50k 字推理（同一受控上游文本、同一探针、隔离浏览器，桌面 1440×900）：

| 指标 | 上一批优化前基线 | 上一批优化后（无流式公式） | **本批公式修复后** |
| --- | --- | --- | --- |
| 帧间隔 p95 / 最大 | 166.7 / 316.7 ms | 5.6 / 16.8 ms | **5.7 / 22.2 ms** |
| 帧 > 50 ms / > 100 ms | 215 / 112 | 0 / 0 | **0 / 0** |
| 长任务 | 210 条 / 23 078 ms | 0 条 | **0 条** |
| 主线程脚本 | 28 300 ms | 1 106 ms | **2 776 ms** |
| 主线程布局 | 426 ms | 2 302 ms | 330 ms |
| 推理容器 DOM 更新 | 10 455 | 383 | 1 862 |
| 首个可见增量 | 69 ms | 43 ms | 55 ms |
| JS 堆（CDP 单次采样） | 102.4 MiB | 11.4 MiB | 46.9～97.5 MiB（随 GC 时点波动） |

口径说明：本修复为「流式期间显示公式」付的代价是**主线程脚本 +1.7 s**（每次提交解析的尾段上界 4000 字符，
不是整段增长文本），**帧间隔与长任务不变**（0 帧 > 50 ms、0 长任务），相对优化前基线仍是 10 倍级改善；
把尾段上界降到 2000 字符复测为 2863 ms（无实质收益，故保留 4000 以覆盖更长的单段公式）。
`originSelfCheck` 用**落库原文长度**核对受控上游（避免折叠后 DOM 为空导致的误判），本次 `ok=true / 50000`。

## 4. 测试

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run lint`（`--max-warnings=0`） | **0 警告** |
| `npm run test:unit` | **54 文件 / 459 例通过**（上一批 52/441；本批新增 18 例） |
| `npm run build` | 通过（`BUILD_ID` 见 FROZEN 记录） |
| `npm run test:chat`（流式集成，fixture 真实代理） | 9 例中 **8 通过 / 1 失败**（失败为既有陈旧用例，见 §5） |
| `npx playwright test`（全量 e2e，202 例） | **最终候选（含手机顶栏间隔修复）：202 通过 / 0 失败**（6.6 m）。此前同一批次在未含手机修复的构建上为 **201 通过 / 1 失败**——唯一失败为 `course-sessions.spec.ts:427`「流式中切换会话」（第 461 行点击侧栏「新对话」后 URL 未切换），**不可稳定复现**（隔离 `--repeat-each=3` 3/3、整文件 `--repeat-each=2` 22/22 通过）→ 已登记 **R-17**（间歇；机制假设未证实；本批改动与 store/会话创建零交集） |
| 定向复跑（`lesson-plan.spec.ts`） | **9 通过 / 0 失败**——含新增的「标题与导出、品牌与标题都需有可见间隔（≥2px）」断言（手机顶栏修复的回归守卫） |

本批新增/扩展的用例：
- 单测 18 例：`markdown-segments.test.ts`（11：切块/围栏/块级公式/松散列表/四种定界符/代码美元/超限上提/表格不拆/未闭合不上提/逐字性）、`StreamingMarkdown.test.tsx`（6：流式公式、块级 display、未闭合→闭合、代码美元符号、逐字保留、超长原文）、`ReasoningDisclosure.test.tsx`（+1：折叠过渡期间内容仍在 DOM）。
- `tests/fixtures/stream_backend.py`：推理流改为 5 段（闭合块 ×4 + 未闭合尾段），新增 `/reasoning` 门闩。
- `tests/integration/chat-reasoning.spec.ts`：三种协议各新增 8 条断言（流式 katex=3 / display=2 / 代码美元原文 / 未闭合尾段原文 / 无 katex-error / 补齐后 katex=4 且尾段不再原文）。
- `tests/e2e/lesson-plan.spec.ts`：新增四视口顶栏用例（标题与导出同行、无重叠、无溢出、编辑区紧接顶栏、导出菜单可用）。
- `tests/e2e/books-courses.spec.ts`：新增两条完整往返路径 + 空列表/深链/手机视口返回入口 + 唯一当前项。

## 5. 既有失败定性（不隐藏、不在本批修）

`npm run test:chat` 的 `tests/integration/chat-live.spec.ts:59`「模型发现追加、默认模型同步、表单冲突保留」
**确定性失败**：第 62 行等待 `.connection-group` 过滤「教学模型服务」后点击「从服务获取模型」超时。
现场快照显示 `/settings` 默认标签是 contract-v1 的**连接卡片 + 详情弹窗**结构（`3 个连接 · 3 个模型`、
「打开 … 的详情」），没有 `.connection-group`；该 modal 现在只在连接详情内可达
（`ModelSettingsPanel.tsx:564`）。**本批改动与 `/settings`、`model-settings` 图零交集**
（`grep` 证实 settings 图不引用本批任何文件），故属**既有陈旧用例**，与三项回归无关；
是否更新该用例留待后续批次（不属本批授权范围）。三条流式推理用例在本批修复后转绿。
