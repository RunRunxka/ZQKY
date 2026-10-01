# H1-BOOKS-PIPELINE v2 —— 固定参考逐字规格（只读取证汇总）

参考：`F:\DeepTutor` v1.6.5 / `42fab3cf429a1fbf36b257ab8d116a3814964202`（只读）。
来源：2026-09-20 只读取证（Evidence-Collector），文件行号基于该提交。**原文为英文，目标侧 UI 为中文**：文案按语义等价翻译并标注"模拟"，参数（时长/阈值/高度/数量）逐字照抄。

## 1. 状态枚举（`web/lib/book-types.ts`）

```ts
BookStatus  = "draft" | "spine_ready" | "compiling" | "paused" | "ready" | "error" | "archived"   // :5-14
PageStatus  = "pending" | "planning" | "generating" | "ready" | "partial" | "error"                // :19-25
BlockStatus = "pending" | "generating" | "ready" | "error" | "hidden"                              // :27-32
```
Block 字段：`status` `params` `payload` `source_anchors` `metadata` `error`（:83-95）。Page 字段：`status` `blocks` `block_count?` `parent_page_id` `error`（:97-115）。
`pause_kind?: "user" | "provider"` 与 `pause_reason?: string`（:217-220）。`can_resume` / `working` / `interrupted` / `started_at` 在 GenerationOverview（:169-187）。
后端 `_UNFINISHED_PAGE_STATUSES = {PENDING, PLANNING, GENERATING, ERROR}`；**PARTIAL 刻意不在其中**（`engine.py:110-118`）。

## 2. 阶段、活动 phase 与 orb（`book-progress.ts` / `book-activity.ts`）

- `StageId = ideation | exploration | synthesis | critique | overview | compilation`（:18-24），`STAGE_ORDER` 同序（:92-99），`StageState = pending | running | completed | error`（:26）。
- `BookPhase = StageId | "paused" | "interrupted" | "done"`（:43-48）；`interrupted` 注释：`Says compiling, nothing is compiling it.`
- orb 映射（:114-124）：ideation→shaping、exploration→searching、synthesis→weaving、critique→solving、overview→connecting、compilation→composing、paused/interrupted/done→breathing。`RESTING_SPEED = 0.5`（:126-127）。
- 页面状态→活动态（:129-136）：ready→done、partial→error、error→error、planning/generating→running、pending→done。
- 计时格式（:138-146）：`` `${hours}:${mm}:${ss}` `` 或 `` `${mm}:${ss}` ``；注释 "a book compile can run that long"。
- phase 判定（:412-418）：paused 优先 → interrupted → liveChapter 或 status=compiling → 准备阶段 → ready→done。
- live 判定（:405-410）：paused 或 interrupted → false；否则 `backendWorking || streamLive`（后端"有人在干"优先于流）。
- 章行文案（:313-357）：`Some blocks failed`、`Planning the blocks…`、`{{done}}/{{total}} blocks`、`Writing {{block}}`、`Queued`、`Untitled`；章标题格式 `` `${String(index+1).padStart(2,"0")} · ${title}` ``。

## 3. 活动条（`BookGenerationActivity.tsx`）

- `const STRIP_HEIGHT = 46;`（:32-33），注释 "one line, at one height, in every view and every phase"。
- 可见性（:148-155）：`activity.empty` 或（非 live 且 phase 非 paused/interrupted）→ 返回 null。
- 章节计数（:186-193）：`{{done}}/{{total}} chapters`，`tabular-nums opacity-60`。
- 暂停（:194-202）：`Pause` 图标，`label="Pause generation"`，`busyLabel="Pausing…"`。
- 恢复（:203-223）：interrupted 用 `RefreshCcw`，否则 `Play`；`label = interrupted ? "Continue generating" : "Resume generation"`，`busyLabel="Resuming…"`。
- 展开浮层（:234-241）：`role="dialog"` + `aria-label="Finished so far"`，`dt-detail-in`，`max-h-[min(60vh,460px)] max-w-[32rem]`；分组标题 `Chapters`（:252-254）；行前置 `StatusDot`（:293）。
- 动画（`web/app/globals.css`）：`dt-detail-in` keyframes :711-720（opacity 0→1 + translateY(-2px)→none），规则 :722-724 `animation: dt-detail-in 180ms cubic-bezier(0.16, 1, 0.3, 1)`；`dt-breathing-text` :691-699 `opacity .45↔1`，规则 :701-702 `animation: dt-breathing 1.8s cubic-bezier(0.4,0,0.6,1) infinite`；两者在 reduce（:1104-1106）与 picker 打开（:789-791）时被冻结。
- 按钮通用类（:325-334）：`transition-colors hover:bg-[var(--muted)]`，busy 时 `Loader2 animate-spin` + busyLabel。

## 4. 暂停横幅（`BookPausedBanner.tsx`）

标题 `Generation paused`（:37-39）。两类说明（:40-48）：
- user：`Generation was paused. Everything generated so far is saved, and unfinished chapters will continue only when you resume.`
- provider：`Your model provider kept refusing requests, so the remaining chapters were left untouched rather than half-written. Everything generated so far is saved.`
`pause_reason` 以 `<code>` 呈现（:49-53）。恢复按钮（:55-68）`Resume generation` / busy `Resuming…`，`border border-current` 描边按钮。容器为普通 div，无 role。

## 5. 失败呈现

- 块失败卡（`BlockRenderer.tsx:124-152`）：rose 容器 + `AlertTriangle` + 标题 `{{type}} block failed`；元信息行 `{failure.kind}` + （`retryable===false` 时）` · not retryable`，`text-[11px] uppercase tracking-wider opacity-70`；正文 `block.error || failure?.message || "Unknown error"`；按钮 `Retry`。
- 生成中占位（:116-123）：虚线 + `Generating {{type}}…`。
- 页失败面板（`PageReader.tsx:584-643`）：amber 容器；标题单复数 `{{count}} block failed` / `{{count}} blocks failed`；按钮 `Regenerate page` / busy `Regenerating…`（`RefreshCcw`）；**最多列 5 条**（:612 `slice(0, 5)`），每条 `{type}` code + `{failure?.kind || "error"}: {block.error || failure?.message || "Unknown error"}` + `Retry block`。
- 阅读器头（:510-523）：`Force regenerate` / busy `Regenerating…`。排队页（:562-581）：`This chapter has not been written yet. It will be generated in turn — or start it now.` + 按钮 `Generate this chapter`。
- `ActivityHeader`（`web/components/activity/ActivityHeader.tsx`）：非展开分支 `role="status" aria-live="polite" aria-atomic="false"`（:82-86）；展开分支按钮 `aria-expanded` + `aria-live="polite"`（:66-78）；呼吸只在未 settled 时（:47）。
- 正文生成提示（`PageReader.tsx:549-561`）：`Loading this chapter…` / `Planning the blocks…` / `Compiling page…`，`orb="composing"`。

## 6. 失败分类与句子（参考后端 + 健康横幅）

后端 `_generation_error_category`（`deeptutor/book/engine.py:214-243`）分类：`quota`、`authentication`、`rate_limit`、`missing_dependency`、`provider`、`content`、`unknown`。
前端 `FAILURE_CAUSES`（`BookHealthBanner.tsx:29-37`）逐字：
`quota: "Your model credit or quota ran out."`、`authentication: "The model credentials were rejected."`、`rate_limit: "The model provider was rate-limiting the requests."`、`missing_dependency: "Some block types need an optional package that is not installed. …"`、`provider: "The model provider was unreachable or timed out."`、`content: "The model returned something the block could not read."`（渲染时过滤掉 `unknown`，用 ` · ` 连接，:138-142/231）。
计数标题（:219-225）：`{{count}} chapters failed to generate.` / `{{count}} blocks failed to generate.`

## 7. 列表与侧栏标记

列表胶囊（`BookLibrary.tsx:23-68`，仅非 ready 渲染，:311-320）：draft `Draft`、spine_ready `Outline`、compiling `Compiling`（`animate-pulse` 圆点）、paused `Paused`、ready `Ready`、error `Error`、archived `Archived`。
侧栏（`BookSidebar.tsx:19-26`）`STATUS_LABEL`：pending `Queued`、planning `Planning`、generating `Compiling`、ready `Ready`、partial `Partial`、error `Failed`；`PAGE_MARK`（:42-49）pending→done/muted、planning·generating→running/muted、ready→done/accent、partial·error→error/muted；状态词以 `title` 提示（:271），已读页 `opacity-45`（:273-277）。

## 8. 自动续跑与阈值（`deeptutor/book/engine.py`）

`maybe_resume_on_open`（:1101-1130）逐条：① `book is None or status != COMPILING` → False；② `metadata["lazy_compile"]` → False；③ `runtime.in_flight` 非空 → False；④ `runtime.worker is not None and not worker.done()` → False；否则 `resume_book`。docstring 明示 "Deliberately does *not* resume a PAUSED book"。
`CONSECUTIVE_PAGE_FAILURE_LIMIT = 2`（:105）；`_record_page_failure` 累加并在达阈值时 `_pause_compilation`（:1481-1485）；页不失败时清零（:1471-1475）。
`pause_kind` 取值：`"user"`（:1022，默认 reason `Paused by user.`）、`"provider"`（:1503）。用户暂停会把 PLANNING/GENERATING 页复位 PENDING（:1031-1034）。
`working = compiling and is_worker_live`、`interrupted = compiling and not working`、`can_resume ∈ {COMPILING, PAUSED, ERROR}`（:1672-1694）。
`metadata["compile_started_at"]`（:951/:1092）与 `metadata["lazy_compile"]`（:947）是生成期持久化字段；恢复时清除 `pause_reason`/`pause_kind`（:1085-1088）。

## 9. 目标侧裁剪（队长裁定，见 TASK-CARD §6）

参考的 6 阶段准备链与 `lazy_compile`、来源检索文案在目标侧**无对应实现**（提案/大纲为本地即时生成），本批不伪造其进度；活动条只呈现"准备（大纲已就绪·模拟）"与"逐章编译"两段。其余参数（46px 条、计时格式、`n/m 章`、浮层角色与进场、呼吸文字、暂停阈值 2、`partial 计入完成`语义）照抄。
