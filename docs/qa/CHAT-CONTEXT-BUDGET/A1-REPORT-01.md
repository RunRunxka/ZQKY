# CHAT-CONTEXT-BUDGET v1 独立验收报告 r1（A1，只读复验）

> 归档说明（队长）：A1（`Independent-Acceptor`，只读）本轮对**两条工作流**出了一份合并报告；本文件保存其中与候选 1（CHAT-CONTEXT-BUDGET v1）有关的部分，RAG-I0-PREP v1 部分见 [RAG-I0-PREP/A1-REPORT-01.md](../RAG-I0-PREP/A1-REPORT-01.md)。文末「总控处置」为队长对该报告第 4 节的处置记录，不改写 A1 的原始结论与数字。A1 探针与配置在仓库外（`%TEMP%\a1-verif-20260923\`），不随仓库提交。

## 0. 复验对象与写入停止

- 候选 1：`a9968cd`（`feat(chat-budget)`，父 `b16a825`），tree `60d64f33ae65b684c36b6696a86f2e8df0854491`；构建 `BUILD_ID = JvWSAvqG7aThtH-p1KhOw`。
- 其后 `13a93ae`（RAG-I0）与 `9fcab13`（仅文档，diff 面无 `apps/**`、无锁文件）经核对。
- 候选自到验起未被写入：`git status --porcelain -uall` = 0，HEAD 全程 `9fcab13`。

## 1. 指纹表（A1 自测）

| 项 | 候选 1 | 一致性 |
| --- | --- | --- |
| 提交 / 父 / tree | `a9968cd3c1f7451a9c13c82217e547a977c19423` / `b16a8250…` / `60d64f33ae65b684c36b6696a86f2e8df0854491` | 与 FROZEN-1 一致 |
| 7 文件 sha256_16 | `chat.ts` eb04f89d…／`request-budget.ts` 284a4878…／`context-budget.ts` 1cc2154f…／`store.ts` c1f3f3df…／`ChatWorkspace.tsx` 4df74bb6…／`course-session.ts` 20d745bd…／`chat-context-budget.spec.ts` cdc53f32… | 7/7 与 FROZEN-1 一致 |
| 构建 | `.next/BUILD_ID = JvWSAvqG7aThtH-p1KhOw`，会话前后一致且未重跑 | pass |

## 2. 逐条结论（A1 自建探针复跑，非照抄 README）

| 项 | 结论 | 关键证据 |
| --- | --- | --- |
| 不变量 1 逐字不裁剪 + 32000/32001 边界 | **pass** | 32000 字逐字发送、`totalChars=32000`；32001 → `ok:false`（`questionChars=32001`、`allowedChars=32000`）；`'😀a'×5000` 代理对未被切断 |
| 不变量 2 条数/单条/总长 | **pass** | 260 条历史 → 发送 ≤200 条（`dropped=61`）；40000 字历史消息**整条丢弃不截断**；总数 ≤ min(inputBudget,120000) |
| 不变量 3 裁剪顺序 + 不拼半条 + notes 一致 | **pass** | 发送的历史内容逐字属于输入集合（集合成员断言）；课程块放不下 → 无 system、`courseDropped=true`、notes 一致。观察（不记 fail）：实现把"课程块放不下"判定放在丢历史之前，结果等价，账目如实 |
| 不变量 4 不发送超限请求 | **pass**（第二半为结构兜底） | `maxMessageChars=80`：块不可渲染 → 整体丢弃；问 100 字 → `ok:false`；问 60 字 → `ok:true` 无 system。`maxMessages=0`/`maxTotalChars=0` → `ok:false`。`withinLimits` 自检为防御性兜底（A1 未构造出可触发输入，如实登记） |
| 不变量 5 账目逐字段可核 | **pass** | 多分支断言 `record.totalChars === Σ content.length`；重试形状 `historyDroppedMessages=1`（丢最旧 user，不含当前问题） |
| 不变量 6 免责句必在 | **pass** | 8 变体（无资源/零大纲/超长 name/超长 nextTitle/超长 conventions/40 条资源/超长标签/空 name）均含「内容未解析、未检索、未随本请求发送」；整体丢弃时无 system（不伪造） |
| 不变量 7 失败零副作用 | **pass** | 请求数 0、无占位、无用户消息入库、`sending=false`、草稿保留、提示含字数；30ms 窗口 `unhandledRejection` 空；`dismissBudgetNotice` 只清提示 |
| 不变量 8 轮次冻结（含旧超长快照） | **pass** | 新轮新快照、重试旧快照；仓储载入的旧快照 `nextTitle=32001 字` → 报文合规且**存储超长值未被回写**、历史正文不变 |
| 不变量 9 未越界 | **pass** | `git diff b16a825 a9968cd --stat` 18 文件；关键词扫描无 `maxOutputTokens` 默认值/推理开关/R-13/mock 改动；无 `apps/api` 产品代码 |
| §4 字段上限 | **pass** | name ≤80、nextTitle ≤120、conventions ≤1200、资源 ≤12×80、整体 ≤2400（`maxMessageChars=1000` → 块 ≤999；=60 → 整体丢弃）；**课程原始数据未回写**（32001 字标题、4000 字约定原样） |
| 探针反转 | **pass** | 原探针实跑 **2/2 按预期失败**（208 / 1990≤2000）；副本实跑一致；副本 `probe.test.ts` md5 `18122b3c1953eb3ef2ca53dfe92d7ccc` 与 `_work` 原件**逐字节一致**；产品路径反转探针 **3/3 通过** |
| 回归防护 | **pass** | 定向 15/15、全量 195/0/0；补充探针 5/5：`requestBudget` 经仓储重载逐字段相等（刷新可核）、`budgetNotice` 在新建/切换/取消激活后清除且不吞 `courseContextWarning`、重试不重发失败轮正文且账目一致、流式中取消 `sending=false`+终态 stopped、课程块放不下时无 system 且 `courseDropped` 如实；H1 课程闭环语义无回退 |

## 3. 独立复跑数字（A1 本机）

| 项 | 声称 | A1 实测 |
| --- | --- | --- |
| lint | 0 警告 | exit 0，无输出 |
| unit | 52/434 | **52 文件 / 434 例通过（81.6s）** |
| api | 217 | **217 passed** |
| 定向 e2e | 15/15 | **15 passed（17.4s）** |
| 全量 e2e | 195/0/0 | **195 passed（6.3m），0 failed / 0 flaky** |
| 构建 | 不重跑 | BUILD_ID 前后一致；`.next` 2326 文件，会话后 0 个新/改动 |

## 4. A1 发现的问题（原文摘要）

1. **产品缺陷（低）— 脏历史快照的资源项未防御**：最小复现为仓储返回一条 `status:'error'` 的助手消息、其 `courseContext.resources = [null]`（仅外部改写/损坏可产生）→ `retry()` 抛 `TypeError: Cannot read properties of null (reading 'label')`（`request-budget.ts:193`）。影响：不发请求、`sending` 未置位、消息未改动、**不假成功**，但没有可读提示，该轮重试点一次抛一次；与任务卡 §4「渲染必须对快照入参做防御性裁剪」的目标不完全对齐。A1 建议排期在后续小批（一行 `resource ?? {}` 防护 + 1 例单测），**不阻断本批交付**。
2. **文档不准（低）**：两份 `FROZEN-CANDIDATE.json` 的 `candidateFullSha` 填的是 7 位短 SHA。
3. **文档不准（低）**：`docs/STATUS.md:3` 头部仍写「更新：2026-09-22」。
4. **文档口径（低）**：`AI_INTERACTIONS` 新行 A-request-budget 标「已验收」，与 STATUS §5.A 同批「待交付审查」不一致（状态标签早于独立验收结论）。
5. **文档口径（低）**：FROZEN-2 的 `performanceBoundary` 未标注来源（实为上游历史记录，非本批实测）。
6. **既有技术债（范围外）**：`services/course-session.ts` 的 `courseContextMessage` 已不在产品路径，对畸形快照仍直接解引用，与主路径形成两套渲染口径，建议后续合并或标注废弃。

**测试无效性检查**：未发现无效断言；`context-budget.test.ts` 被改写的一例为契约变更（TASK-CARD §3.1 明文，README §6 与用例注释已说明）；`chat-context-budget.spec.ts` 全部按真实 POST 报文断言且与产品行为因果绑定。

## 5. A1 结论（原文摘要）

> **候选 1（CHAT-CONTEXT-BUDGET v1，`a9968cd`）：可交付。** 覆盖范围：九条不变量（自建探针复跑）、§4 上限与不回写、探针反转、H1 课程闭环不回归、`requestBudget` 刷新可核、失败路径零副作用、真实浏览器报文合规。**不覆盖**：真实供应商、视觉/动画、精确 token（本批全为字符估算）。第 4 节第 1 条为低 severity 健壮性缺口（需外部损坏数据才可达），建议排入后续小批，不阻断本批交付。

## 6. 总控处置（队长，2026-09-23）

| 项 | 处置 | 证据 |
| --- | --- | --- |
| 第 4 节第 1 条（脏快照抛错） | **本批内关闭（不改契约语义，仅加固）**：理由是本批任务卡明确要求"预算/构建失败不得留下无法重试的状态或未处理 Promise"，而该路径是重试按钮上的重复抛错。新增 `safeResources()` 防御读（非对象条目丢弃、缺失字段以 `unknown` 兜底、总数如实计数**不伪造内容**），并覆盖 `renderCourseBlock` 与 `renderCourseContextBlock` 两处；新增单测「脏历史快照（类型系统之外的 null 资源条目/缺失字段）不抛错」 | `apps/web/src/features/chat/model/request-budget.ts`、`request-budget.test.ts`（16 例） |
| 第 4 节第 2 条 | **已订正**：两份 FROZEN 的 `candidateFullSha` 改为全 SHA（`a9968cd3…` / `13a93aec…`） | 两份 FROZEN 记录 |
| 第 4 节第 3 条 | **已订正**：STATUS 头部更新为 2026-09-23 并写明本批范围 | `docs/STATUS.md:3` |
| 第 4 节第 4 条 | **已订正**：`A-request-budget` 状态改为「实现待验收（A1 首轮可交付，脏快照加固后待 r2 复验）」，r2 通过后再改「已验收」 | `docs/replica/AI_INTERACTIONS.md` |
| 第 4 节第 5 条 | **已订正**：FROZEN-2 增加 `performanceBoundarySource`，注明为上游 `docs/EVAL.md`/`docs/STATUS.md` 的历史记录、本批未实测 | `docs/qa/RAG-I0-PREP/FROZEN-CANDIDATE.json` |
| 第 4 节第 6 条（两套渲染口径） | **登记为技术债，本批不合并**：`courseContextMessage` 已不在产品路径，合并会触及课程闭环的既有断言；在后续小批处理 | 见批次 README §7 |

**处置后状态**：因第 1 条为**产品代码**改动，本批**重新构建并重新冻结**（新构建 `jWdzmxYFOf6RtLUVbtOkL`），定向/全量 e2e 与单测重跑后交 A1 r2 复验（见 `A1-REPORT-02.md`）。A1 已通过的其余 8 条不变量与全部回归项在 r2 中做「未回退」核对。
