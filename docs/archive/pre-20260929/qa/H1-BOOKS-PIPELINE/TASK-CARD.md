# 任务卡：H1-BOOKS-PIPELINE v2 —— 书籍生成流水线与增量阅读闭环

任务 ID：H1-BOOKS-PIPELINE
版本：v2
负责人：实施总控（本会话队长）
角色：总控 / 取证 / 实现 I1·I2·I3 / 独立验收 A1

目标：把目标侧书籍生成从"确认大纲即同步 ready"改为**可观察、可暂停、可恢复、可中断、可失败重试的显式模拟流水线**，并让生成中的页面与块状态真实落库、阅读器可增量消费。不接真实 LLM，不新增第二套业务后端。

用户授权范围：书籍生成流水线 + 必要阅读器状态（本文件"行为闭环"全部条目）。
非目标（本批不做，且不因本批通过而关闭）：BookChatPanel、课程学习会话、真实 LLM/解析、真实 HealthBanner 数据（kb_drift/log_health）、书籍侧栏折叠、多用户权限、R-13、R-06 错误页 reset 补测、14 类 block 全面重做、导航字体收口。

## 0. 起点与接手现场

- 起点 HEAD：`bf460ab5ee53810679752c5104f7e2a777221d08`（分支 `codex/replica-review-20260908`）。
- 接手前改动（**本批不提交、不还原、不清理、不当作第 0 步**）：`.zcode/agents/evidence-collector.md`、`.zcode/agents/independent-acceptor.md`、`.zcode/agents/limit-scope-implementer.md`、`apps/web/next-env.d.ts`、`apps/web/src/components/layout/workspace-shell.css`。
- 快照与校验值：`_work/h1-books/handoff-snapshot/`（`SHA256SUMS.txt`、`handoff.diff`、`HANDOFF.md`、`files/` 原始副本）。构建若再次改写生成文件（如 `next-env.d.ts`），只把**本批新增的改动**撤回，恢复到该快照。
- 参考：`F:\DeepTutor` v1.6.5 / `42fab3cf429a1fbf36b257ab8d116a3814964202`，只读。

## 1. 依赖与固定参考

- 参考入口（逐字规格见 `REFERENCE-SPEC.md`）：`web/lib/book-types.ts`、`book-progress.ts`、`book-activity.ts`、`app/(workspace)/books/BooksRoute.tsx` 与 `components/{BookGenerationActivity,BookPausedBanner,PageReader,BlockRenderer,BookSidebar,BookLibrary}.tsx`、后端 `deeptutor/book/{engine,compiler,models}.py`。
- 目标现有实现：`apps/web/src/services/books-store.ts`（4 态同步模拟）、`apps/web/src/features/books/{BooksRoute,PageReader}.tsx`、`books.css`、`apps/web/src/services/local-collection.ts`（严格读写 + 回滚）。
- 依赖关系：`courses-store.ts` 依赖 `books-store` 的书籍目录（资源三态 R-11 必须不回退）。

## 2. 可写文件与禁区

| 角色 | 可写范围 |
| --- | --- |
| 总控 | `docs/STATUS.md`、三矩阵、`docs/PROJECT_GUIDE.md`（必要决定）、`docs/qa/H1-BOOKS-PIPELINE/**`、`tests/e2e/books-pipeline.spec.ts`（新建）、`tests/e2e/books-courses.spec.ts`（同步语义改造）、Git 与构建资源 |
| I1 | `apps/web/src/services/books-store.ts`、新建 `apps/web/src/services/book-generation.ts`、`apps/web/src/services/books-store.test.ts`、新建 `apps/web/src/services/book-generation.test.ts` |
| I2 | `apps/web/src/features/books/BooksRoute.tsx`、新建 `apps/web/src/features/books/BookGenerationStrip.tsx`、新建 `apps/web/src/features/books/BookPausedBanner.tsx`、新建 `apps/web/src/features/books/styles/book-pipeline.css`、新建同目录组件测试 |
| I3 | `apps/web/src/features/books/PageReader.tsx`、新建 `apps/web/src/features/books/BookBlockFailure.tsx`、新建 `apps/web/src/features/books/styles/book-reader-states.css`、新建 `apps/web/src/features/books/PageReader.test.tsx` |
| A1 | 只读；证据写 `docs/qa/H1-BOOKS-PIPELINE/` |

**禁区（只读，本批任何卡都不得修改）**：`apps/web/src/features/space/styles/space.css`、`apps/web/src/styles/globals.css`、`apps/web/src/components/layout/workspace-shell.css`、`apps/web/src/components/ui/Modal.*`、`apps/web/src/services/local-collection.ts`、`apps/web/src/services/navigation.ts`、`apps/web/src/services/knowledge-catalog.ts`、`apps/web/src/services/notebook-store.ts`、`apps/web/src/services/courses-store.ts`、`apps/web/src/contracts/chat.ts`、`apps/web/src/features/books/books.css` 的既有规则（可读，不可改；新样式只进两个新 CSS 文件）、`apps/web/src/features/books/PageReader.tsx` 与 `BooksRoute.tsx` 的既有可访问名称与断言锚点。

**锚点（必须逐字保留）**：`载入演示数据`、`新建书籍`、`创建（生成模拟提案）`、`确认提案（进入大纲）`、`确认大纲并编译（模拟）`、`返回书籍列表`、`返回书籍首页`、`重建书籍`、`导出 Markdown`、`添加书签`/`移除书签`、`章节目录`、`第 N/M 页`、`章节页不存在或已被重建`、`我的笔记内容`、`A. 理解本页概念并能举例`/`B. 背诵全文`、`回答正确。`/`回答错误，正确答案 X。`，以及全部既有模拟标注原文（见 §5）。

## 3. 运行资源

- 用户服务：5173（不得占用）、8000（本批无后端改动，不启动）。
- 实现者自测：**5175** + `_work/h1-books/<role>/` 产物目录；不得跑 `npm run build`、不得跑全量 e2e。
- 队长：构建 `.next` 独占；e2e 独占 5174（`playwright.config.ts` 自带 webServer）。
- 报告与截图：`docs/qa/H1-BOOKS-PIPELINE/`。已知共享产物：e2e 会写 `_work/e2e-export-probe.md`（`books-courses.spec.ts:104`）。

## 4. 状态与服务合同（冻结；I2/I3 按此编码，I1 按此实现，不得改名）

### 4.1 状态枚举（`books-store.ts`）

```ts
type BookStatus = 'draft' | 'spine_ready' | 'compiling' | 'paused' | 'ready' | 'error' | 'archived';
type PageStatus = 'pending' | 'planning' | 'generating' | 'ready' | 'partial' | 'error';
type BlockStatus = 'pending' | 'generating' | 'ready' | 'error';   // 参考另有 hidden；目标无隐藏块功能，不引入
type BookFailureKind = 'content' | 'storage' | 'internal' | 'unknown';
type RunPauseKind = 'user' | 'provider';
```

生产者与转移（每条都要有代码出处，写进结果卡）：

| 状态 | 生产者 | 进入条件 | 恢复操作 |
| --- | --- | --- | --- |
| `draft` | `createBook` | 新建 | 确认提案 |
| `spine_ready` | `confirmProposal` | draft 且提案存在 | 开始编译 |
| `compiling` | `confirmSpine`、`resumeRun` | spine_ready 或 paused/error/中断后续跑 | 暂停 / 继续 |
| `paused` | 用户暂停（`pauseKind='user'`）或模拟供应商连续页失败达阈值（`pauseKind='provider'`） | 运行中 | 仅"恢复生成"后继续 |
| `ready` | 运行结束且所有页 `ready` | 全部完成 | 重建 / 归档 |
| `error` | 整轮失败：`storage`（本地写入失败）或 `internal` | 无法继续 | 重试生成（从断点/重建按范围） |
| `archived` | `archiveBook`（仅 ready↔archived，语义不变） | 就绪书归档 | 取消归档 |

页面/块状态生产者：`pending`（骨架创建）、`planning`（页面进入规划）、`generating`（块逐个生成中）、`ready`（页/块完成）、`partial`（页内有失败块，但其余块可用）、`error`（整页失败）。**禁止**把局部块失败或页面失败写成"供应商错误"；`provider` 只用于"模拟供应商连续失败"这一显式标注的暂停原因。

### 4.2 字段（向后兼容，读取不写回）

```ts
interface BookBlock { /* 既有 */ status?: BlockStatus; failure?: BlockFailure; contentVersion?: string }
interface BlockFailure { kind: BookFailureKind; message: string; retryable: boolean; simulated: true }
interface BookPage  { /* 既有 */ status?: PageStatus; error?: string; attempts?: number; generatedAt?: string }
interface BookRunCheckpoint {
  runId: string; status: 'running'|'paused'|'stopped'|'finished'|'failed';
  stage: 'preparing'|'compilation';
  cursor: { chapterIndex: number; pageIndex: number; blockIndex: number };
  pauseKind?: RunPauseKind; pauseReason?: string;
  failure?: { kind: BookFailureKind; message: string };
  startedAt: number; updatedAt: number; finishedAt?: number;
}
interface ReplicaBook { /* 既有 */ run?: BookRunCheckpoint | null; runScenario?: BookRunScenario | null }
```

**兼容规则**：缺 `status` 的旧页面/块一律按 `ready` 处理（读取期派生，不写回）；旧四态书籍照常可读；`run` 缺失表示无历史运行。损坏/结构非法/未知版本仍走 `local-collection` 抛错路径，不当作空库、不覆盖。

### 4.3 仓储 API（`books-store.ts` 新增/变更）

```ts
confirmSpine(bookId): ReplicaBook | null        // spine_ready→compiling：建章节+页面骨架（页/块 pending），写 run 检查点，清阅读进度（语义同现状）
applyRunEvent(bookId, runId, event): ReplicaBook | null   // 唯一写入口；校验 bookId+runId+cursor；重复/迟到事件忽略
pauseBookRun(bookId, kind: RunPauseKind, reason: string): ReplicaBook | null   // → paused；正在生成的页/块复位 pending（对照参考）
resumeBookRun(bookId, runId): ReplicaBook | null                                // paused/error(可恢复)→compiling
failBookRun(bookId, runId, failure: {kind, message}): ReplicaBook | null        // → error
finishBookRun(bookId, runId): ReplicaBook | null                               // 全 ready→ready；仍有 error 页→保持 compiling（无执行器即"已中断"）
retryBlock(bookId, pageId, blockId): ReplicaBook | null                        // 单块：pending + 清 failure；页 partial→generating
regeneratePage(bookId, pageId): ReplicaBook | null                             // 整页：非 user_note 块复位 pending 并清 failure，**保留 user_note 内容与块身份**；页→pending
markVisited(bookId, pageId): void                                              // 仅在该页有内容（ready/partial）时登记 visited；currentPageId 始终更新
recordQuizAttempt(input): BookQuizAttempt                                      // 新增 blockVersion 字段
quizAttemptMatches(block, attempt): boolean                                    // 版本关系判定
exportBookMarkdown(bookId)                                                     // 未完成/失败页如实标注，不伪装成完整成书
```

**合并与并发**：所有写入必须经"读取最新记录 → 局部修改 → 写回"（`mutateBook` 语义），执行器**不得**用内存整本快照覆盖；生成期间新增的笔记、书签、阅读进度必须保留。

### 4.4 模拟执行器（新建 `apps/web/src/services/book-generation.ts`）

```ts
interface BookRunScenario {
  stageDelayMs?: number;       // 默认 300：准备段
  blockDelayMs?: number;       // 默认 220：逐块
  failBlockIds?: string[];     // 首次尝试即失败的块（重试即成功）
  failPages?: number;          // 前 N 页整页失败（模拟页面失败）
  providerPauseAfterPages?: number;  // 连续 N 页失败触发 provider 暂停（默认取 CONSECUTIVE_PAGE_FAILURE_LIMIT）
  storageFailureAt?: { pageIndex: number } | null;  // 在该页写入时模拟本地存储写入失败
}
interface BookRunHandle {
  bookId: string; runId: string;
  pause(): void;                      // 用户暂停
  resume(): void;
  stop(): void;                       // 中止（卸载/删除），保留断点
  readonly status: 'running'|'paused'|'stopped'|'finished'|'failed';
}
startRun(bookId, options?: { scenario?: BookRunScenario; source?: 'user'|'auto-open'|'retry' }): BookRunHandle | null
getRun(bookId): BookRunHandle | null
resumeRun(bookId): BookRunHandle | null      // paused 只能由用户显式调用；compiling 无执行器时可由自动续跑调用
stopRun(bookId, reason: string): void
retryBlock(bookId, pageId, blockId): void
regeneratePage(bookId, pageId): void
getLease(bookId): { owner: string; runId: string; heartbeatAt: number; live: boolean; mine: boolean } | null
DEFAULT_RUN_SCENARIO: BookRunScenario
CONSECUTIVE_PAGE_FAILURE_LIMIT = 2   // 对照参考 engine.py:105
RUN_LEASE_STALE_MS = 3000
```

- **正常路径必须由事件推进**：为每页/每块产生增量事件（`pending→generating→ready`），逐块落库（默认 200ms 合并写，页面完成/暂停/失败/结束/`pagehide` 立即 flush）。禁止"先同步生成整本、再播放假进度"。

事件联合（`applyRunEvent` 的唯一输入，每条都带 `bookId`、`runId`、`seq`）：

```ts
type BookRunEvent =
  | { type: 'run-start' }
  | { type: 'page-start'; chapterIndex: number; pageIndex: number }
  | { type: 'page-planned'; pageId: string; blockIds: string[] }
  | { type: 'block-start'; pageId: string; blockId: string }
  | { type: 'block-ready'; pageId: string; blockId: string; block: BookBlock }
  | { type: 'block-error'; pageId: string; blockId: string; failure: BlockFailure }
  | { type: 'page-ready'; pageId: string }
  | { type: 'page-error'; pageId: string; message: string }
  | { type: 'run-paused'; kind: RunPauseKind; reason: string }
  | { type: 'run-finished' }
  | { type: 'run-failed'; failure: { kind: BookFailureKind; message: string } };
```

**单执行者与页面生命周期**：执行器是**模块级**（不随 React 组件卸载取消）——同书翻页、组件重挂载不得取消或重复启动；只有删除书籍或用户暂停才停止。刷新/关闭会丢失模块状态，靠 `run` 检查点 + 租约失效识别并续跑（重载后 `sessionStorage` 中的 ownerId 不变，租约 `mine=true` 视为可续跑）。
- **可替换服务接口**：执行器与仓储解耦，事件经 `applyRunEvent` 落库；换真实服务时只替换执行器。
- **取消信号**：`stop()` 走 AbortSignal 语义；迟到的定时器/回调必须用 `bookId+runId` 校验后丢弃。
- **租约（单执行者）**：`zhiqikeyuan:book-lease:<bookId>` = `{owner, runId, heartbeatAt}`；每标签页一个 `ownerId`（`sessionStorage`），心跳 1s，>3s 视为失效。他标签页持活租约时本标签**不得**启动第二个执行器，只读显示生成中。
- **自动续跑（对照参考 `maybe_resume_on_open`）**：打开书籍 / `storage` 事件 / 租约失效时，若 `status==='compiling'` 且无活跃执行器 → 从检查点续跑（source `auto-open`，界面提示"已从断点继续"）；`paused` 无论何种情况都**不**自动续跑；他标签页持活租约时不启动。参考的 `lazy_compile` 在目标侧无对应物（目标始终整本编译），文档如实记录为"不适用"。

## 5. 行为闭环与文案

1. **正常链路**：新建→提案→确认大纲（`confirmSpine` 建骨架，进入 compiling）→活动条出现→逐章逐块生成（阅读器可见已完成块与"生成中/排队"占位）→全部就绪→`ready`。
2. **活动条（对照参考 BookGenerationActivity）**：固定 46px 单行；`role="status" aria-live="polite"`；显示 阶段文案 + `n/m 章` + `mm:ss` 计时（超 1 小时 `h:mm:ss`）；运行中显示「暂停生成」/「正在暂停…」，无执行器的 compiling 显示「继续生成」（图标刷新），paused 显示「恢复生成」；点击展开浮层 `role="dialog" aria-label="已生成内容"`，按章分组列出块级进度（`已完成/总数 块`、`正在生成 <块名>`、`排队`、`部分块失败`）；无活跃执行器且非 paused/interrupted 时不显示。
3. **暂停横幅（对照参考 BookPausedBanner）**：`paused` 时显示标题「生成已暂停」+ 按 `pauseKind` 分叉的说明 + 可选 `pauseReason` 代码块 +「恢复生成」/「正在恢复…」；`provider` 类说明必须写明是**模拟供应商连续失败**，不得宣称真实上游故障。
4. **正文生成提示**：阅读器内在生成/规划/排队时显示提示行（对照参考 `ActivityHeader` 的 `role="status"`）：`正在编译本页…`、`正在规划本页的块…`、`正在载入本章…`，以及排队页「本章尚未生成，将按顺序生成——也可以现在开始。」+「生成本章」。
5. **失败与重试**：块失败卡（`AlertTriangle` + `「<类型> 块生成失败」` + 分类 + 可重试标记 + 原因 +「重试」）；页失败面板（`N 个块失败` +「重新生成本页」+ 最多 5 条「重试块」）；阅读器头「强制重新生成」/「正在重新生成…」；整轮失败（`error`）显示原因与「重试生成」；**部分失败**时书籍顶部与卡片不得显示"全部成功/已完成"。
6. **模拟场景设置（队长裁定，新增数据）**：`SpineView` 与运行中详情提供"模拟执行器设置（仅本地模拟）"：注入块失败、注入整页失败、模拟供应商连续失败暂停、模拟存储写入失败。默认全部关闭。所有注入必须显式标注为本地模拟。
7. **阅读进度与导出**：生成进度与阅读进度分开；未生成页打开只更新 `currentPageId`，不登记已读；Markdown 导出对未完成/失败页如实标注（例：`> 本章尚未生成完成（状态：生成中）`），并在文首注明存在未完成章节。
8. **模拟标注保留**：`books-store.ts` 与 `BooksRoute.tsx`/`PageReader.tsx` 中既有"模拟提案/模拟生成/显式模拟占位/未接入"标注逐字保留；因新行为失效的旧文案（如"确认后同步编译为可读书籍"）可修改，但必须记录变更并同样如实说明"本地模拟、不调用模型"。

## 6. 队长裁定（I 卡必须遵守）

1. **阶段裁剪**：活动条只呈现"准备（大纲已就绪·模拟）"与"逐章编译"两段；**不伪造**参考 6 阶段（ideation/exploration/synthesis/critique/overview）的进度与"检索 N 个来源"类文案——目标侧提案/大纲为本地即时生成。
2. **块状态不引入 `hidden`**（目标无隐藏块功能）。
3. **失败分类本地化**：分类值对照参考（content/provider/storage/internal/unknown 的可用子集），句子用中文并标注"本地模拟"；不得出现"额度不足/密钥被拒"等**真实上游**归因。
4. **供应商暂停阈值 = 2 连续页失败**（对照参考常量）。
5. **暂停语义**：pause 时把正在生成的页/块复位 pending（对照参考），恢复后从断点继续；刷新/切页不绕过 paused。
6. **视觉最小化**：新增样式只进 `book-pipeline.css`、`book-reader-states.css`（各以页面修饰类起头，如 `.book-pipeline-*`/`.book-reader-*`），只消费既有变量（`--blue/--surface/--ink/--line/--font-ui/--radius-*/--shadow-card`），零 `!important`，无 `@media print`，reduced-motion 走全局层；动画对照参考参数（浮层进场 `180ms cubic-bezier(.16,1,.3,1)`、呼吸文字 1.8s），仅此两类，不新增别的进出场。
7. **旧合同失效**：`books-store.test.ts` 的"确认大纲完成模拟编译"与 e2e `books-courses.spec.ts` 第 2 例锁定"同步 ready"，本批改为异步流水线断言（更强），逐项在结果卡说明理由；禁止删测试、放宽阈值或保留同步捷径。
8. **无后端改动**：本批 `apps/api` 零改动；API 测试未重跑需在交付中如实说明。

## 7. 验收条件

- 正常路径：新建→提案→确认大纲→活动条→逐章逐块增量可见→ready；生成中阅读器可读已完成内容与未完成占位。
- 空态/错误：块失败、页失败、整轮失败、本地存储写入失败四类各自可复现且文案分类正确；无执行器时不显示"正在生成"。
- 取消/重试/恢复：用户暂停、模拟供应商暂停、恢复、刷新中断恢复、paused 不自动续跑、同书翻页不重启执行器、块重试与整页重生成只作用于约定范围、快速暂停恢复不丢内容。
- 数据兼容：旧四态书籍与缺字段页面/块可读；损坏/读拒/写满不覆盖且不谎报已保存；生成中新增笔记/书签/进度不被覆盖；作答历史与版本关系正确；演示数据幂等；R-11 课程资源三态不回退。
- 视觉基准：`/chat` 蓝色主题与变量；三视口 1440×900 / 1920×1080 / 390×844 无页面级溢出；键盘焦点可见；减少动画下不新增动画。
- 动画：活动条展开/收起、暂停横幅出现与恢复、按钮忙碌态；验证进入、退出、快速开关、中断、焦点与 reduce。
- 真实服务与模拟边界：全程显式模拟标注，`provider` 暂停写明"模拟供应商"，不得暗示真实上游。
- 必须运行：`npm run typecheck`、`npm run lint`（0 警告）、`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit`、`npm run build`（队长重建并记 BUILD_ID）、`npm run test:e2e`（既有 154 + 新增 spec）。

## 8. 结果格式（每张卡回交）

```text
任务 ID / 版本：
负责人：
候选 SHA 或差异标识：
状态：ready_for_review | pass | fail | blocked
修改文件：
行为变化：
保留的数据与兼容方式：
验证（command / result / evidence）：
首败与修复：
未执行：
真实服务边界：
视觉边界：
剩余风险：
需要总控决定：
```
