# CHAT-CONTENT-MATH-AND-FOLLOW v1 批次证据（2026-09-24）

状态：实现与总控自验完成，候选**待独立只读验收**。候选起点 `main@d0c30ec19f8603c7c7f46572948f64bd1a376658`；参考 `F:\DeepTutor` 固定提交 `42fab3cf429a1fbf36b257ab8d116a3814964202` 只读。未触碰 `F:\ZQKY_RAG`、模型供应商配置、真实用户会话、书籍/课程返回路径或教案顶栏。

## 1. 首败与问题边界

### 1.1 已实际复现：正文 `message.content` 未使用流式安全呈现

原 UI 代码路径是 `apps/api text.delta` → `chat-stream` `onText` → store 的 `ChatMessage.content` → `Message.tsx` 直接 `<AnswerMarkdown text={message.content} />`；`StreamingMarkdown` 当时只由推理区使用。受控浏览器首轮在旧正文 renderer 上观测到：同一个 body 原文流里 8 个 `.katex`（2 个 `.katex-display`）、0 个 `.katex-error`，KaTeX computed font 为 `KaTeX_Main, "Times New Roman", serif`、DOM 可见；已闭合 `$…$`、`$$…$$`、单反斜杠 `\(...\)` / `\[...\]` 正常出现公式，代码围栏 `$HOME/$((1+2))` 保留原文，未闭合 `$x+y` 保留原文。这说明既有正文样例不能支持“正文始终正确”，但也**没有**在该合成链路复现普通有效单反斜杠公式完成后仍不渲染的产品首败。

真实输出中的双反斜杠样本 `\\(r^2\\)` 到页面 DOM 逐字未变并以原文显示；本批在展示归一化测试中覆盖“仅完整成对 delimiter 折叠一层”的安全呈现路径，但没有凭空声称该样本来自用户真实供应商。代码围栏中的相同内容不归一化。原消息、复制、导出及持久化字符串未做 rewrite。

隔离合成源覆盖美元行内/块公式、单反斜杠行内/块公式、Markdown 列表、GFM 表格、代码围栏、双反斜杠字面形式、未闭合行内数学、块级 `aligned` 环境。上游 `bodyRaw === bodyDeltas.join('')`，API 与前端回调的文本片段顺序没有被改写；修复后 IndexedDB 助手 `message.content === bodyRaw`。闭合尾段按 `.chat-answer-raw=0`、KaTeX `error=0`、公式 DOM 含预期数学文本核验；总 `.katex` 节点数随稳定块/尾段分割而变，不用单一总数代替正文公式语义。原文链路对比不使用 KaTeX DOM `textContent`（其 MathML/视觉 DOM 会重复字符）。

### 1.2 已实际复现：正文开始后推理仍活动，重开面板不跟随

隔离 HTTP SSE 顺序为 8 行 reasoning → 一条正文 `text.delta` → 48 行 reasoning；正文到达令原 `working = streaming && !content.trim()` 变为 false 并自动折叠。用户手动重开接近推理尾部时，内层滚动区 `scrollTop=0, clientHeight=180, scrollHeight=324, gap=144px`，没有跟到尾部。首败根因是同一个 `working` 同时承载“阶段默认自动展开”与“消息流仍活动”，正文出现后为满足自动折叠而关闭了后续推理滚动 effect。

修复后同一场景：正文开始自动折叠语义保留；接近第 40/48 行时内层实测 `scrollTop=317, clientHeight=180, scrollHeight=497, gap=0`。另在纯推理持续长流（48 行，内容高约 472px）逐次测距底 gap `<32px`、最新行可见；外层 `.chat-messages` 另行采样，负载下为 `scrollTop=0, clientHeight=509, scrollHeight=509`（当时无外层溢出，不能据此声称外层发生滚动或有溢出场景已验证）。真实鼠标滚轮上滚后内层 `top=123` 保持，后续内容使距底增至 `169px` 但自动 effect 未抢回；滚轮下行回到底部后 `gap=0` 恢复跟随。减少动画、触摸硬件与键盘滚动的浏览器人工操作未在本批运行，见 not_run。

## 2. 实现范围

- `Message.tsx`：仅流式中的正文 `message.content` 改用现有 `StreamingMarkdown`（已闭合块按空行边界复用解析、尾段有界处理）；终态/历史仍使用 `AnswerMarkdown`。包在 `.chat-answer-content` 下便于明确区分正文与推理选择器。落库、复制、导出投影未改。
- `markdown-math.ts`：只处理展示副本中的完整双重转义数学分隔符，且先保护代码；KaTeX `trust=false`、`skipHtml`、GFM/highlight 配置不变。
- `ReasoningDisclosure.tsx` / `Message.tsx`：分离 `working`（流仍活动且有 reasoning）与 `autoExpand`（正文之前默认展开）；活动流中用户可重开后继续跟随。保留正文出现自动折叠、手动折叠优先和 320ms 折叠内容保留。添加滚轮/触摸/键盘输入意图窗口，区分内容增长/程序滚动与用户上滚；rAF 写入回调再次校验当前元素仍挂载且仍跟随。
- 不改 `.chat-messages` 外层策略；没有调用无条件 `scrollIntoView`。

## 3. 性能结果

隔离环境：正式 FastAPI 三协议端点中的 OpenAI Chat 受控 fixture（非真实供应商），独立测试浏览器、桌面 1440×900、固定 256 字符 reasoning 增量、约 12ms 间隔；每轮结束再发送含 80 个行内/块级公式的正文。目标源字符长度由 fixture 断言精确检查。页面展示的 KaTeX DOM 字符数会因 MathML/视觉结构重复而高于原始文本，不能作为源字符长度。

| 负载 | rAF 采样帧 / p95 / 最大 | `>50ms` 帧 | Long Tasks / 最大 | 首个可见 reasoning | 受控流窗口 | 正文 KaTeX / error |
| --- | --- | --- | --- | --- | --- | --- |
| 20,000 源字符 | 788 帧 / 5.7ms / 44.5ms | 0 | 0 / 0ms | 99ms | 2.922s | 80 / 0 |
| 50,000 源字符 | 942 帧 / 5.7ms / 38.9ms | 0 | 0 / 0ms | 58.8ms | 4.390s | 80 / 0 |

（上表为最终候选 `48OQ8YwWsaXik3hvv7EQK` 构建上的一轮实测；此前同构建系列的 20k/50k 分别为 766/931 帧、首可见 59/61.9ms、流窗口 2.906/4.391s，帧 p95、`>50ms`、长任务结论相同。）

与 UX-PERF-CLOSEOUT 优化后受控基线约 `5.6ms` p95 同级；本批探针是自己的浏览器 rAF/PerformanceObserver，不与旧 CDP script CPU 值混称。不是跨硬件 60fps 承诺。负载/设备差异可能改变单次结果。曾有一轮粗粒度负载每短段均形成 Markdown 块，造成 p95 8.9/39ms、11/19 个 `>50ms` 帧与 8/14 Long Tasks；该负载块密度不代表目标的自然连续段落，已调整为严格长度且公式密度适中的版本，并完整保留实际首败过程在任务日志，不用于本表结论。

## 4. 验收命令与结果（全部在最终候选源码上重跑）

- `python -m py_compile tests/fixtures/stream_backend.py`：通过。
- `npm run typecheck`：通过（退出码 0）。
- `npm run lint`：通过，0 warning（退出码 0）。
- `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit`：**55 文件 / 463 例全部通过**。此前同源码族另有一轮 55 文件 / 462 例通过 + 1 例非本批 `ModelSettingsPanel.review.test.tsx`「MR-08」失败；该例单跑 1/1、所在文件 12/12 复跑通过 → 判为间歇，不据此改写结果，也不修本批范围外的设置模块。
- `ZQKY_TEST_BUILD=1 ZQKY_API_ORIGIN=http://127.0.0.1:8001 npm run build`：通过（`.next-test` `BUILD_ID=48OQ8YwWsaXik3hvv7EQK`）。常规 `npm run build`：通过（`.next` `BUILD_ID=vv2MkeoRZHz_a4di0tMTO`）。
- `ZQKY_TEST_BUILD=1 ZQKY_API_ORIGIN=http://127.0.0.1:8001 NODE_OPTIONS=--no-experimental-webstorage npx playwright test --config=playwright.chat.config.ts tests/integration/chat-reasoning.spec.ts`：**8/8 通过**（3 协议 reasoning + 正文公式流/终态/刷新 + 正文后推理重开跟随 + 20k + 50k + 连续跟随/手动上滚/回底）。
- `NODE_OPTIONS=--no-experimental-webstorage npm run test:chat`：**13 通过 / 1 失败**；唯一失败为既有 `tests/integration/chat-live.spec.ts:59` 模型发现按钮定位超时（`.connection-group` /「从服务获取模型」；settings contract-v1 后该入口需进入连接详情）。该用例自改码前基线即以相同路径失败，设置模块不在本批改动范围；未删除或 skip。
- `npm run test:e2e`：**201 通过 / 1 失败**（单次运行，约 9.1 分钟），唯一失败为跨批 **R-14**（`tests/e2e/books-commit-safety.spec.ts:238` 双标签页并发写不同书）。该例隔离 `--repeat-each=3` 复测 **3/3 通过** → 与本批既有台账一致为随负载出现的间歇，与本批 diff 面无交集；本批不修该用例。**因此不得声称当前候选全量 e2e 恒绿**；同一批早前构建上曾出现 202/202。

## 5. 证据分类与限制

- **真实供应商**：`not_run`。未使用真实模型/凭证、未读取用户会话或私人对话；没有“用户真实原始公式片段”可报告。合成 source 的 delimiters/反斜杠各层不变，并有 IndexedDB 原文相等证据；不能将其描述为已捕获真实用户格式。
- **合成 SSE**：三协议旧 reasoning 用例与新增正文、滚动、性能均通过；样例数据为固定合成字符串；上游统计、`.chat-bubble.assistant` 正文区域 DOM、KaTeX CSS/computed font 与持久化内容都有断言。
- **用户人工视觉**：本轮未进行用户人工验收，`not_run`。保存浏览器截图只用于测试失败排查，不声称其构成用户人工验收。
- **外层视口**：已独立采样；这组对话在测量窗口没有外层高度溢出，因此只报告样本的实际几何数值，不声称外层 overflow 场景通过。
- **触摸硬件/键盘滚动/reduced-motion**：浏览器人工输入未执行，`not_run`；单测不替代。
- **供应商设置/RAG/F:\\ZQKY_RAG**：未接入、未改动、未访问。

## 6. 冻结与独立复核范围

冻结记录见本目录 [FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)：来源为开工起点 `main@d0c30ec…` 上的未提交工作树（本批尚未提交），逐文件给出 `sha256(LF 归一化 blob)`，`BUILD_ID` 只作运行标签、不是内容指纹。冻结后源码不得再改；若验收要求修改，先撤回本轮结论、改完重冻并对新候选窄复验，且只更新受影响文件的哈希。

独立验收必须亲自打开正文流式/终态/刷新截图或页面，分辨 reasoning/body 区域（正文=`chat-bubble assistant` 下的 `chat-answer-content`；推理=`chat-reasoning-body`），并亲自操作正文开始后的推理 follow、手动上滚与回底；只复跑 `.chat-reasoning-body .katex` 数量不构成验收。真实供应商与用户人工视觉未执行，不得判“全部通过”。

## 7. 独立只读验收（Independent-Acceptor，r1）

**结论：`pass（可交付）`**，附条件说明——真实供应商与用户人工视觉仍为 `not_run`，不得表述为“真实供应商通过”或“用户视觉通过”。

其独立证据（自写探针在 `_work/acceptance-20260924/`，本地忽略区；命令退出码均为 0）：

- **哈希与范围**：17/17 文件 `sha256(LF 归一化)` 逐项匹配，且在验收开始/测试后/探针后三次复算一致；改动全部落在本批 chat 前端、相关测试/fixture 与文档，`apps/api`、锁文件、`.env`、`next.config.ts` 零改动；HEAD 前后均为 `d0c30ec…`。
- **正文公式**：`.chat-answer-content` 流式中 katex=8 / display=2 / error=**0** / raw=1，并用 KaTeX `annotation` 列表逐条证明四类定界符（`$…$`、`$$…$$`、`\(...\)`、`\[...\]`）都成了可见公式；MutationObserver 时间序列（t=127–823ms，katex 2→8）证明**流式期间逐步可见**；未闭合尾段 `.chat-answer-raw` 与上游逐字相同；代码围栏未混入 katex；终态与刷新后 11/0，刷新走静态 `AnswerMarkdown`。
- **落库原文**：IndexedDB 助手 `content === upstream.bodyRaw`（345/345，`firstDiffIndex=-1`）；流中停止 315/315 逐字相等。
- **推理跟随**：自动折叠保留；重开后 10 次采样 gap 全 0；真实滚轮上滚后 `top` 在约 2.2s、14 次采样内恒为 0 而 `scrollHeight` 275→423（gap 95→243，最新行持续不可见）→ **未被抢回**；回底后 8 次采样 gap 全 0。内层 180/497/gap 0；外层 1440×900 样本 689/689 **无溢出**（故未据此声称外层场景通过）；其补充的 1440×520 短视口下外层确有溢出且自身跟随、推理区完整可见（`clippedPx=0`）。
- **性能与归因**：其复跑集成 8/8（36.9s）；20k/50k 的 rAF p95 均 **5.7ms**、`>50ms` 0、长任务 0；并用 CDP CPU 相位切分证明正文段 markdown/KaTeX chunk 自耗时 72.9ms 对应 80 个 KaTeX 节点——**排除“每个 delta 重解析整段正文”**（那将高一数量级并产生长任务）。其单测 55 文件/463 例、typecheck、lint 均通过。
- **边界**：`AnswerMarkdown` 不在本批 diff，`trust:false`/`skipHtml` 未放宽；双转义折叠只作用于展示副本且只折叠完整成对；无密钥/真实会话；无 RAG。
- **口径**：确认 R-16 已订正且历史 A1 报告未被改写；`test:chat` 13/1 的 R-15 由其单跑复核确认为既有、范围外。

其非阻塞观察（如实记录，本批未改）：Windows 剪贴板把复制文本规范化为 CRLF（LF 归一后与上游完全相等，属操作系统约定，且复制路径文件本批未改）；推理面板自动折叠 320ms 后内容依既有语义从 DOM 卸载，故折叠态内 katex=0 属预期。

其 `not_run`：真实供应商外呼、用户人工视觉、硬件触摸/键盘滚动/reduced-motion 专项、折叠逐帧曲线（H6）、全量 `test:e2e` 与全量 `test:chat` 重跑、`npm run build` 重建（避免改写 `next-env.d.ts` 生成物）、RAG。

**遗留待决（由总控登记，不在本批扩大范围）**：① R-16 的最终关闭建议仍待真实供应商样本或用户人工视觉复核；② 外层 `.chat-messages` 跟随策略本批未改、也未纳入断言，若用户场景包含外层滚动需另立需求；③ 剪贴板 CRLF、折叠卸载语义按“非本批”处理。
