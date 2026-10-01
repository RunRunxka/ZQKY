# H1-BOOKS-PIPELINE v2 缺陷台账（首败与修复）

记录本批从实现到冻结之间**真实出现过的失败**：谁发现、首败证据、根因、修复与对应断言。
口径：只记录实际复现过的缺陷；猜测性风险写在「剩余风险」里，不混入本表。
「真实服务」一列对全部条目均为“不涉及”——本批全部为本地模拟执行器与本地注入场景。

## 1. 修复批（I1-REPAIR，本批上一任实现者，提交前）

首败证据：`_work/h1-books/i1-repair/{RESULT-CARD.md,probe-out.txt,probe-v.txt}`（git 忽略，仅作参考）。

| # | 缺陷 | 首败表现 | 根因与修复 |
| --- | --- | --- | --- |
| R1 | 事件写入门禁过窄 | 已完成书（`ready`）上的「重试」「强制重新生成」事件全部被静默丢弃 | `books-store.runWritable` 只放行 compiling/paused/error → 放行 `ready`（页级修复的真实场景），书籍状态不变 |
| R2 | 同批事件共用陈旧序号 | `block-ready` 的 seq 等于 `lastSeq`，被当作重复事件丢弃；块永停 `generating` | `regenerateBlocks` 用陈旧快照 `nextSeq+1` → 改为每条事件前重读最新记录取 `seq = lastSeq + 1`（与队列写盘共用单调序号空间） |
| R3 | 存储失败注入在 jsdom 静默无效 | 注入后既不抛错也不生效，整轮跑成 `ready`（谎报已保存） | 直接给 Storage 实例赋值在 jsdom 代理上无效 → 改为“安装后读回校验”，未生效则落到原型描述符；两条路径都失败则保持未注入 |
| R4 | `resumeRun` 不支持 `error` 态 | 本地写入失败后的恢复段返回 `null` | 合同 §4.3 的 `error` 为可恢复态 → 增加 error→compiling→startRun 分支 |
| R5 | 续跑以检查点游标为起点 | 游标指向“最后开始的页”，其之前未完成的页（整页失败、被重生成复位的页）永远不被修 | `drive` 一律从全局首页按页状态续跑，由 `stepOnce` 跳过已完成页 |
| R6 | 存储失败注入是持续性的 | 恢复后在同一个触发点再次失败，永远出不来 | 同一 run 已因 storage 失败过就不再注入（一次性） |
| R7 | 页失败未达 provider 阈值时书假 `ready` | 存在 `error` 页却被判 ready | `run-finished` 事件不再直接置 ready，改由 `finishBookRun` 单点判定：仍有未完成页 → 保持 compiling（无执行器即“已中断”） |

## 2. 总控裁定 A1–A7（本轮）

| # | 缺陷 | 首败/证据 | 根因与修复 | 断言 |
| --- | --- | --- | --- | --- |
| A1 | `'*first'` 通配从不命中：UI「注入块失败」开关是**静默无操作** | 读码确证：UI 写 `failBlockIds: ['*first']`，引擎只做精确 `includes` | 引擎场景解析期展开：`'*first'` → 全书第一个块 id（展开值随 `setRunScenario` 持久化，续跑沿用） | 单测：注入命中“全书第一个块”且 `runScenario.failBlockIds` 不再含通配；e2e「块失败与重试」经 UI 开关真跑到失败卡 |
| A2 | 无 run 记录的书（演示书、旧四态就绪书）页/块修复静默无操作 | 前修复批剩余风险 1；e2e 第 7 例此前只能“空洞通过” | 仓储新增 `ensureBookRun`（仅当无 run 时补一个只作写入容器的检查点，不改书籍状态/阅读进度）；`retryBlock`/`regeneratePage` 改用之为写入容器 | 单测：补检查点幂等 + 书籍仍 ready + 块/页重生成真的发生；e2e 第 7 例改真断言（笔记落库后重生成期间块占位出现、结束后笔记仍在、块数与页码结构不变） |
| A3 | 归档书拒绝写入但按钮可点：不留静默无操作 | 前修复批剩余风险 2 | PageReader 对 `archived` 禁用「强制重新生成 / 重新生成本页 / 重试块 / 生成本章」，并给出同一说明（可见 `role=note` 文案 + 按钮 `title`）；书签等只读操作仍可用 | 组件测试：四个入口 disabled 且点击不调用执行器、说明可见；浏览器实测截图 `v10-archived-readonly-*` |
| A4 | `failPages` 为持续注入，恢复后永远卡在同一触发点 | 前修复批剩余风险 4 | 整页失败注入改为**一次性**：以页自身持久化的 `attempts` 为判据（失败过一次即不再注入），与 `failBlockIds` 语义一致；块注入同样加上“已带 error 不再注入”的持久判据 | 单测：首轮失败→`run.status=stopped` 保持中断、`attempts=1`；恢复后续跑到 ready 且 `attempts` 仍为 1；e2e「整页失败」同链路 |
| A5 | `error` 态「重试生成」未接线 | 合同 §5.5 要求显示原因与「重试生成」 | `BooksRoute` 接到 `resumeRun`（error→compiling→续跑），带 busy 态与失败提示 | e2e「本地存储写入失败」：真实 QuotaExceeded 注入 → error 横幅含原因 → 点「重试生成」→ 续跑到可阅读 |
| A6 | `derivePageStatus` 兜底会把仍有 pending/generating 块的页判成 `ready` | 总控复核 | 只有**全部块 ready** 才 `ready`；有 error 块 → `partial`；仍有 pending/generating → 保持 `generating`，不谎报完成 | 单测：迟到 `page-ready` 落在未完成页上时页状态为 `generating`（不冒充 ready），有失败块时为 `partial` |
| A7 | 工作树里留有无断言的探针 `zz-debug.test.ts` | `git status` | 删除（不进提交） | 全量单测 46 文件（不再是 47）且无 `zz-*` 残留 |

## 3. 本轮新发现（A1–A7 之外）

N1–N8 由「首次真跑」（构建 / 全量 e2e / 视觉实测）暴露；N9 由独立验收 A1 首轮挑刺发现并采纳修复。

| # | 缺陷 | 发现方式 | 根因与修复 | 断言 |
| --- | --- | --- | --- | --- |
| N1 | 「模拟供应商连续失败暂停」开关单独开启时**无任何效果**（与 A1 同类的静默无操作） | 读码 + e2e 供应商用例首跑 | `providerPauseAfterPages` 没有任何失败来源；只在页失败累加时才判阈值 → 场景解析取 `max(failPages, providerPauseAfterPages)` 为注入页数，供应商场景自身产生连续页失败直至阈值 | 单测：只开供应商开关也会 2 页失败并 `pauseKind=provider`；e2e 供应商用例真跑到暂停横幅 |
| N2 | 自动续跑触发面过宽：每次书籍记录变化都会自动重启 | e2e「整页失败→已中断」语义 | 页失败后的“已中断”会被下一次轮询立刻自动接管，用户既看不到中断态也看不到原因 → 自动续跑限定为：每次打开/刷新一次，另加“他标签页租约失效后接管”；本挂载内跑过的书不再自动重启；恢复入口由用户点击 | e2e：中断文案与「继续生成」可见、点击后完成；刷新中断用例仍自动续跑 |
| N3 | 暂停后刷新，「恢复生成」静默无操作 | e2e「用户暂停与恢复」首跑（时序 41s 超时） | `handleResume` 在无本地句柄时调 `startRun`，而 `startRun` 只接受 `compiling`（paused 书它拒绝） → 统一改为 `resumeRun`（先做 paused/error→compiling 转移再启动），失败时给出明确提示 | e2e：刷新后点横幅「恢复生成」→ 回到“正在逐章编译”→ 跑完 |
| N4 | `book-pipeline.css` 头部注释内含 `*/`（`--radius-*/--shadow-card`）导致**构建直接失败** | 总控首次 `npm run build`（Turbopack 报 `Invalid dangling combinator`） | 注释被提前闭合，后续文本被当成 CSS → 改为 `--radius-… 与 --shadow-card` | build 通过（BUILD_ID 记录在交付回交） |
| N5 | 就绪书卡片状态徽标被隐藏，破坏既有 e2e 合同 | 全量 e2e 首跑（`books-courses` 列表用例失败） | 视觉推广时把徽标改成“仅非 ready 渲染”，而既有用例以卡片上的「可阅读」锁定就绪态 → 恢复对全部状态渲染（保留 154 基线零断言改动；参考差异如实记录） | 既有 `books-courses` 用例回到 0 改动通过；e2e 运行态卡片显示「可阅读」 |
| N6 | 已中断（compiling 无执行器）状态下活动条没有恢复入口 | 任务卡 §5.2 与参考 interrupted 分支对照 | 「继续生成」只覆盖了 `compilation` 阶段，interrupted 既无「继续生成」也无「恢复生成」（两处条件互斥）→ 覆盖 interrupted（RefreshCcw + 继续生成，对照参考 `Continue generating`），paused 仍单独用「恢复生成」 | 组件测试：interrupted 下存在「继续生成」且无「暂停/恢复」；e2e：点「继续生成」后继续到完成 |
| N7 | 无执行器时块占位仍写“正在生成 X 块…” | 视觉自查 + 任务卡 §5.1“生成中/排队”两态 | `pending` 与 `generating` 共用一句话术，页失败/已中断时对未开始的块谎称正在生成 → 按状态分开：`正在生成 X 块…` / `X 块等待生成…`（生成中才挂旋转图标） | 组件测试：同页两态各一，排队块不出现“正在生成”；截图 `v3-*`、`v8-*` |
| N8 | 整轮失败原因在阅读器头部与横幅各出现一次（重复长文案） | 截图 `v9-run-failure-error-retry-1440x900` | 头部描述里的 `生成失败：<原因> · ` 与横幅重复 → 头部不再重复长文案，原因统一由带「重试生成」的横幅呈现 | 截图重拍；e2e storage 用例以横幅为断言对象 |
| N9 | `contentVersion` 生产代码从不写入：作答版本关系「永不触发」 | **独立验收 A1 首轮挑刺**（`contentVersion` 只在类型与消费端存在，`grep` 全 `src` 仅测试种子命中） | 声明存在、实现缺失（与 N1/A1 同类的“接口在、行为不在”）→ 执行器新增 `blockContentVersion(planned)` 内容确定性哈希，由 `plannedToBlockPayload` 写入 `contentVersion`（整轮与即时修复路径共用） | 单测：生成出的块带 `v1-xxxxxxxx`、同页不同内容块版本不同、`quizAttemptMatches` 同版本匹配/异版本不匹配/缺版本兼容、同内容重生成版本不变；A1 定向复验（见 A1 报告复验小节） |
| N10 | 活动条展开浮层被 46px 单行条裁掉：点「已生成内容」只看到一条被切碎的细缝 | **总控视觉取证**（1920 截图 `v4-strip-detail-open-1920x1080`，r2 之前）：浮层挂在 `.book-pipeline-strip`（`height:46px` + `overflow:hidden` 的 flex 行）内部，作为其子节点被裁切 | 结构错误（e2e 的 `toBeVisible`/`toContainText` 只看 DOM，看不到裁切，所以一直是绿的）→ 按参考 `BookGenerationActivity` 的结构改为：外壳 `.book-pipeline-strip-shell`（relative）→ 46px 行（role=status）→ 兄弟定位层 `.book-pipeline-detail-layer`（absolute/inset-x-0/top-100%/z-40）→ 浮层本体（max-w 32rem、max-h min(60vh,460px)、内部滚动、进场动画留在本体内以避免 transform 冲突） | 单测：浮层不得是 role=status 的子节点、不得位于 `.book-pipeline-strip` 内；e2e：浮层高度 > 60px、右/下边界不超出视口、`strip` 内无 `[role=dialog]`；新增 390 用例断言宽度 ≤ 390 且页面级溢出 ≤ 1；截图 v4 三视口重拍（1440/1920/390 实观为不透明浮层，覆盖在正文之上） |

## 4. 测试侧同批修正（均非放宽断言）

| # | 原断言 | 问题 | 改为 |
| --- | --- | --- | --- |
| T1 | `strip.toContainText(/已运行 \d{2}:\d{2}/)` | 该文案只在计时元素的 `aria-label` 上，可见文本是 `mm:ss` | 断言计时元素可见文本 `^\d{2}:\d{2}$` **且** `aria-label` 为 `已运行 mm:ss`（更强） |
| T2 | `getByText('生成已暂停', { exact: true })` | 暂停时横幅标题与活动条阶段文案同为该串 → strict mode 冲突（2 个元素） | 断言按容器限定：`.book-pipeline-paused` 含标题与说明，另单独断言活动条含「生成已暂停」（不是放宽，而是指向具体组件） |
| T3 | 展开浮层断言 `getByText(/第 01 章\|比喻是什么/)` | 章标题与状态列「正在生成 比喻是什么」同时命中 | 断言章标题元素 `.book-pipeline-detail-chapter-title` 首行为 `01 · 比喻是什么`（更强） |
| T4 | 块重试后 `expect(.books-block 数量).toBe(重试前数量)` | 重试前统计发生在生成中（其余块尚未落库，数量为 0），且重试中的块以占位呈现 → 恒不成立 | 先等整轮结束统计“块 + 失败卡 = 本页块总数（4）”，重试后等占位清空再断言总数不变，并补“页码结构不变 + 活动条未出现（未触发整本重建）” |

以上四处均在 e2e 首次真跑时暴露；**没有删除任何用例、没有放宽阈值、没有使用 `expect.poll`/`waitForTimeout` 掩盖失败**（`waitForTimeout` 只用于截图前的稳定等待，不作为断言手段）。

## 5. 一次误判（如实记录，供后续取证参考）

排查 N10 时，1920 截图上的浮层看起来「半透明、正文透出」，一度被当成独立缺陷。写探针（`.book-pipeline-detail`、`.book-pipeline-detail-layer` 的 computed style + `elementFromPoint`）后证实：浮层 `background-color` 为 `rgb(255,255,255)`、`z-index:40`、中心点命中浮层自身，**不存在透明或压层问题**。
真实原因是我自己的取证脚本在点击展开后立即截图，拍到了 `book-pipeline-detail-in` 180ms 进场的中间帧（opacity 从 0 淡入）。已把两个取证脚本改为等 320ms 再截屏后重拍，截图恢复正常。

**教训**：验证进场动画的界面时，截图前必须等动画结束；否则会把「动画中间帧」误判成产品缺陷（反向也成立：裁切类缺陷不会被 `toBeVisible()` 发现，必须量几何或断言 DOM 归属）。
