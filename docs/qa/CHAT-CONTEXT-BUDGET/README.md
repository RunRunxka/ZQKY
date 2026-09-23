# CHAT-CONTEXT-BUDGET v1 — 批次证据

> 批次：CHAT-CONTEXT-BUDGET v1（2026-09-23 本地实施，待独立验收）。起点 `main@b16a825`。契约见 [TASK-CARD.md](TASK-CARD.md)。
> 同批另一工作流：RAG-I0-PREP v1（[证据](../RAG-I0-PREP/README.md)），两条工作流**分别小提交**。

## 1. 目标与复验的缺陷

为「一次真实请求到底发送什么」建立**统一预算**：课程上下文（system 块）、历史消息与当前问题在同一预算内共同裁剪，预留输出预算，并分别遵守后端单条/总长度硬限制（`apps/api/app/schemas/chat.py`：`MAX_MESSAGES=200`、`MAX_MESSAGE_CHARS=32000`、`MAX_TOTAL_CHARS=120000`）。

冻结探针（`_work/course-gate-20260922/`，队长复验）：

```
{"kind":"course-message","chars":32088,"courseLimit":2400,"apiSingleMessageLimit":32000}
{"kind":"request-budget","chars":2040,"budget":2000}
```

- **D1**：UI 可输入的超长大纲单元标题（32001 字）使课程 system 消息达 **32088 字**，同时越过 2400 承诺与后端 32000 单条上限。
- **D2**：课程块在 `contextBudgetChars` 裁剪**之后**追加，总字符 2040 > 预算 2000。

## 2. 实现要点

| 位置 | 内容 |
| --- | --- |
| `features/chat/model/request-budget.ts`（新，337 行） | 唯一请求构建入口 `buildChatRequest()`：`BACKEND_REQUEST_LIMITS` 为后端硬限制单一事实来源；裁剪阶梯 ①课程块动态字段 → ②整条丢弃最旧历史 → ③整体丢弃课程块；当前问题逐字不裁剪、放不下即 `ok:false`（不发送）；`RequestBudgetRecord` 账目 + `RequestNote` 说明；`renderCourseContextBlock()` 对**快照入参**做防御性裁剪且不改写原始数据 |
| `features/chat/model/context-budget.ts` | 保留 `conversationProjection`（R12 投影）；新增 `projectRequestHistory` + `takeNewestMessages`（整条取舍、绝不拼接半条）；`selectMessagesForRequest` 降为兼容入口并注明非产品路径 |
| `features/chat/model/store.ts` | `send()` **发送前预检**：失败只设 `budgetNotice`，不清草稿、不入库用户消息、不建占位、不置 `sending`；成功把 `record` 持久化到助手消息（`requestBudget`）；`retry()` 用同一构建器 + 旧轮冻结快照 |
| `features/chat/ChatWorkspace.tsx` | 构建失败提示（保留输入可改）与「本轮未携带课程上下文」如实提示；文案统一写「字符估算」 |
| `services/course-session.ts` | `courseContextMessage` 渲染期新增 `name ≤ 80`、`nextTitle ≤ 120`（授权最小补丁；归属/过滤/快照生成语义一字未动） |
| `contracts/chat.ts` | 队长新增 `RequestBudgetRecord` + `ChatMessage.requestBudget`（稳定契约） |

字段上限：`name ≤80`、`nextTitle ≤120`、`conventions ≤1200`、资源 ≤12 条且单标签 ≤80、课程块整体 ≤`min(2400, maxMessageChars-1)`；**「内容未解析、未检索、未随本请求发送」免责句在课程块未整体丢弃时始终保留**。

## 3. 实跑结果（队长集成，生产构建）

| 维度 | 命令 | 结果 |
| --- | --- | --- |
| 类型 | `npm run typecheck` | 通过 |
| 静态检查 | `npm run lint` | 0 警告 |
| 单元 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **52 文件 / 435 例通过**（上一批 51/416；含 A1 r1 加固新增的脏快照用例） |
| 构建 | `npm run build` | 通过，**r2 交付候选构建 `BUILD_ID = jWdzmxYFOf6RtLUVbtOkL`**（r1 为 `JvWSAvqG7aThtH-p1KhOw`） |
| 定向 e2e | `npx playwright test tests/e2e/chat-context-budget.spec.ts tests/e2e/course-sessions.spec.ts` | **15/15 通过（17.6s）**（新增 4 + 课程闭环 11） |
| 全量 e2e | `npx playwright test` | **195 passed / 0 failed / 0 flaky**（r1 与 r2 两次构建均一致，见 §4） |
| 后端 | `npm run test:api` | **217 passed**（含本批 RAG adapter 契约 35 例） |
| 真实供应商 | — | **未发起真实外呼、未验证凭证有效性**（not_run） |
| 视觉 | — | **不宣称视觉通过**（本批无 `.css` 改动） |

## 4. 全量前端 e2e（生产构建）

- **195 passed / 0 failed / 0 flaky（6.4m）**（r1 构建 `JvWSAvqG7aThtH-p1KhOw` 与 r2 构建 `jWdzmxYFOf6RtLUVbtOkL` 两次均通过；上一批 191 例 + 本批新增 4 例）。
- 计数口径：基线 191（含课程闭环 11 例）+ 新增 `chat-context-budget.spec.ts` 4 例 = 195。
- A1 独立验收者在冻结候选上另行复跑（记录见 `A1-REPORT.md`）。

## 5. 缺陷探针反转（历史证据）

探针原件与副本：`probe-reversal/{probe.test.ts,probe.config.ts,probe-copy.config.ts}`（副本 md5 `18122b3c1953eb3ef2ca53dfe92d7ccc` 与 `_work` 原件逐字节一致，**未改动、未另存适配版**；就地运行靠新增的纯 alias 配置 `probe-copy.config.ts`，断言一个字未改）。运行记录见 `probe-reversal/probe-run-after-fix.txt`：

- **原探针 A/B（副本就地运行）**：2 例**全部按预期失败** —— D1 `expected 208 to be greater than 32000`（缺陷期 32088，现 **208**）；D2 `expected 'user' to be 'system'` 且实测 `{"chars":1990,"budget":2000}`（缺陷期 2040 > 2000）。
- **反转探针 C（产品路径断言）**：**3/3 通过** —— `course-message 243`、`request-budget 1990 ≤ 2000`、次轮 roles `["system","user","user"]`。

## 6. 首败与修复（如实）

| # | 现象 | 定位 | 修复 |
| --- | --- | --- | --- |
| 1 | 单测捕获：课程块**存在**但因单条上限过小而无法渲染时，`buildChatRequest` 仍报 `courseDropped:false`（账目与实际发送不符，违反不变量 5） | `request-budget.ts` 的 `else` 分支缺失 | 快照存在但渲染为 `null` 即置 `courseDropped:true` |
| 2 | `context-budget.test.ts` 首败：旧规则「最后一条用户消息即使超预算也保留」与新语义冲突 | 语义变更（当前问题放不下改为显式失败） | 该例按新语义重写，其余 3 例未动；**写入本表的目的是说明这不是"放宽断言"而是契约变更**（见 [TASK-CARD](TASK-CARD.md) §0/§3） |
| 3 | 测试自身错误：重试用例把课程约定写进了 `createCourse` 的 `description` 参数 | 测试夹具 | 改用 `updateCourse(id,{instructions})` |
| 4 | 孤立渲染函数 `courseContextMessage` 仍无限幅（探针 D1 仍命中） | 授权最小补丁（见 §2 表末行） | 新增 `name ≤80`/`nextTitle ≤120`，并只新增 1 例断言；既有 7 例断言未改 |

| 5 | **A1 r1 独立验收（低危）**：脏历史快照的资源项未防御（`courseContext.resources=[null]`，仅外部损坏可产生）→ 重试路径抛 `TypeError` 且无可读提示 | A1 最小复现（`request-budget.ts:193`） | **本批内关闭**：新增 `safeResources()` 防御读（非对象条目丢弃、缺失字段以 `unknown` 兜底、总数如实计数不伪造内容），覆盖 `renderCourseBlock` 与 `renderCourseContextBlock` 两处；新增单测「脏历史快照…不抛错」。理由：任务卡要求「失败不得留下无法重试的状态或未处理 Promise」，而该路径正是重试按钮上的重复抛错 |

## 7. not_run / 边界

- 真实供应商调用：**未外呼、未验证凭证有效性**；本批全部断言在上游替身（路由级 stub）与真实浏览器报文上完成。
- 精确 token：**不做**。全部数字为字符估算（1 token ≈ 2 字符），不保证不超模型自身上下文上限，只保证不超本轮输入预算与后端硬限制。
- 未改动：模型输出预算默认值、推理开关、R-13、RAG 内容、模拟聊天、`.css`、后端产品代码。
- 边界：`selectMessagesForRequest` 作为兼容入口仍在（非产品路径）；`requestBudget` 账目只记发送时事实，不改写历史正文与课程原始数据。
- **技术债（登记，未在本批合并）**：`services/course-session.ts` 的 `courseContextMessage` 已不在产品路径（仅测试引用），对畸形快照仍直接解引用 `syllabus/resources`，与主路径 `renderCourseContextBlock` 形成两套渲染口径；建议后续小批合并或显式标注废弃（合并会触及课程闭环既有断言，故本批不做）。
- 独立验收：[A1 r1 报告与总控处置](A1-REPORT-01.md)（**可交付**，第 4 节低危项已在本批内关闭）；r2 复验结论见 `A1-REPORT-02.md`（冻结后补）。

## 8. 提交

（队长在集成稳定后作本地小提交；与 RAG-I0-PREP 分开提交。）
