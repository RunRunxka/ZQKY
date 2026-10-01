# CHAT-CONTEXT-BUDGET v1 任务卡（冻结契约）

> 批次：CHAT-CONTEXT-BUDGET v1（2026-09-22）。起点 `main@b16a825`。队长独占 `contracts/chat.ts`、权威文档、集成、构建与 Git；本卡是实现者（I-CHAT）的唯一契约来源，**不得自行扩大范围**。

## 0. 复验的缺陷（探针通过 = 缺陷存在，不作为产品验收）

探针：`_work/course-gate-20260922/probe.test.ts` + `probe.config.ts`（本地，gitignored）。队长复跑结果（2026-09-22，本批开工）：

```
{"kind":"course-message","chars":32088,"courseLimit":2400,"apiSingleMessageLimit":32000}
{"kind":"request-budget","chars":2040,"budget":2000}
```

- **D1（课程消息超后端单条上限）**：UI 可输入的超长大纲单元标题（32001 字）经 `courseContextMessage` 产出 **32088 字** system 消息，同时超过本地 2400 承诺与后端 `MAX_MESSAGE_CHARS = 32000`。
- **D2（课程块在总预算之外追加）**：`store.run()` 先按 `contextBudgetChars(...)` 裁剪历史，再把课程块**追加**到最前；总字符 2040 > budget 2000，总预算不被遵守。

## 1. 范围内 / 范围外

**范围内**：请求构建的统一预算（课程上下文 + 历史 + 当前问题）、课程快照所有动态字段的受限渲染、裁剪顺序与如实记录、放不下时的**发送前**明确失败、失败路径的状态收尾、按轮次冻结语义不变、浏览器报文级验证。

**范围外（不得顺手做）**：模型输出预算默认值、推理开关与 R-13、RAG 内容或模拟聊天、后端产品代码（后端**零改动**）、课程/书籍其他模块、视觉主题。

## 2. 队长已冻结的契约（`apps/web/src/contracts/chat.ts`，本批开工时由队长新增，随本批提交）

- `ChatMessage.requestBudget?: RequestBudgetRecord`（随助手消息持久化，刷新可核）。
- `RequestBudgetRecord` 字段：`totalChars`、`inputBudgetChars`、`maxMessageChars`、`maxTotalChars`、`historyDroppedMessages`、`courseTrimmedFields`、`courseDropped`。
- 语义：**全部为字符估算**（1 token ≈ 2 字符的保守估计），不是精确 token 计数，文档与 UI 文案不得写成精确 token 保证。

## 3. 必须新增的模块与接口（`apps/web/src/features/chat/model/request-budget.ts`）

```ts
/** 后端硬限制的唯一事实来源（apps/api/app/schemas/chat.py: MAX_MESSAGES/MAX_MESSAGE_CHARS/MAX_TOTAL_CHARS） */
export const BACKEND_REQUEST_LIMITS: { maxMessages: 200; maxMessageChars: 32_000; maxTotalChars: 120_000 };

export type RequestNote =
  | { kind: 'history-dropped'; messages: number }
  | { kind: 'course-trimmed'; fields: string[] }
  | { kind: 'course-dropped' };

export type BuildRequestResult =
  | { ok: true; messages: { role: ChatRole; content: string }[]; record: RequestBudgetRecord; notes: RequestNote[] }
  | { ok: false; reason: 'question-too-large'; message: string; questionChars: number; allowedChars: number };

export function buildChatRequest(input: {
  history: ChatMessage[];            // 已过滤 superseded / error 的历史（含最新一条用户消息）
  question: string;                  // 当前问题原文（不裁剪）；普通发送时 = 即将入库的用户消息正文
  courseSnapshot?: TurnCourseSnapshot;
  contextTokens?: number | null;
  maxOutputTokens?: number | null;
  limits?: typeof BACKEND_REQUEST_LIMITS;
}): BuildRequestResult;
```

**不变量（逐条必须成立，A1 会按条核）**

1. `question` 逐字不裁剪；若 `question.length > min(inputBudget, maxMessageChars)` → 返回 `ok:false`（`reason:'question-too-large'`，`allowedChars` 为实际允许值，`message` 为可直接展示的中文说明）。
2. `ok:true` 时：`messages.length ≤ maxMessages`；每条 `content.length ≤ maxMessageChars`；`totalChars = Σ content.length ≤ min(inputBudget, maxTotalChars)` **且** `≤ maxTotalChars`。
3. **裁剪顺序**：① 课程块动态字段受限（见 §4）；② 丢弃最旧的旧历史（逐条整条丢，**不拼接半条消息**）；③ 仍超限则整体丢弃课程块，`record.courseDropped=true` 且 `notes` 含 `course-dropped`（**不得**发送残缺/伪造的课程上下文）。
4. 课程块整体丢弃后若仍超限 → 返回 `ok:false`（同一 reason 语义：必要输入放不下），**不得**发送超限请求。
5. `record` 必须反映**实际发送**的数字（逐字段可核对）；`historyDroppedMessages` 不含当前问题；`courseTrimmedFields` 列出实际被裁剪的动态字段名。
6. `courseDropped=false` 时，课程块内**必须**含固定免责句「内容未解析、未检索、未随本请求发送」。
7. 构建失败**不得**产生任何副作用：不创建助手占位、不置 `sending=true`、不清空输入、不留未处理 Promise；用户可修改后重发（失败态可重试）。
8. 轮次冻结不变：新轮用新快照、旧轮重试用原快照（**旧轮的超长快照**也必须经同一 `buildChatRequest` 安全构建，不要求清库）。
9. 不改 `maxOutputTokens` 默认值、不自动关推理、不动 R-13、不引入 RAG 或模拟聊天。

## 4. 课程块字段上限（`courseContextMessage`，渲染期防御——对**旧快照**同样生效）

| 字段 | 上限 | 说明 |
| --- | --- | --- |
| `name` | 80 字符 | 课程名原始校验上限 60；渲染期再兜底 |
| `syllabus.nextTitle` | 120 字符 | 本次缺陷 D1 的直接来源 |
| `conventions` | 1200 字符 | 沿用 |
| 资源条目数 | 12 条 | 多余以「…等共 N 项」说明 |
| 单条资源标签 | 80 字符 | 沿用 |
| 整体 | ≤ 2400 字符，且 ≤ `maxMessageChars - 1` | 免责句与固定行不可被砍 |

渲染必须对**快照入参**做防御性裁剪（历史里的旧快照可能带超长字段），但**不得**回写课程原始数据（`StudyCourse`）或历史消息正文。

## 5. 需要改动的文件（单一写入者：I-CHAT）

| 文件 | 动作 |
| --- | --- |
| `apps/web/src/features/chat/model/request-budget.ts` | 新建（§3、§4） |
| `apps/web/src/features/chat/model/context-budget.ts` | 改：保留投影（`conversationProjection`）；`selectMessagesForRequest` 若不再被产品路径使用，改为由 `buildChatRequest` 内部等价实现（**不要留两套预算语义**）；若保留导出，必须注明其不保证当前问题可容纳 |
| `apps/web/src/features/chat/model/store.ts` | 改：`send()` **先预检**（用候选问题 + 历史 + 课程快照构建请求），失败 → 设置显式提示、**不清空草稿、不入库用户消息、不建占位**、`sending=false`；成功 → 入库用户消息并把 `record` 写到助手占位上；`retry()` 用同一构建器（旧快照） |
| `apps/web/src/features/chat/ChatWorkspace.tsx` | 改：展示构建失败提示（可编辑后重发）与「课程上下文本轮被丢弃」的如实提示；文案不得声称精确 token |
| `apps/web/src/features/chat/model/request-budget.test.ts` | 新建（§6 单测） |
| `apps/web/src/features/chat/model/context-budget.test.ts` | 改：与新语义一致（若改动 `selectMessagesForRequest` 契约） |
| `tests/e2e/chat-context-budget.spec.ts` | 新建（§6 浏览器验证） |
| `docs/qa/CHAT-CONTEXT-BUDGET/probe-reversal/` | 新建：把 `_work` 探针复制进 Git，附「修复后按预期失败」的运行记录 |

**禁止触碰**：`apps/api/**`（含 schemas，除只读引用其常量值）、`features/courses/**`、`services/course-session.ts` 的归属/过滤语义、书籍模块、`.css`、`.env*`、`.local-data`、构建产物、`tests/e2e/course-sessions.spec.ts` 与 `books-*.spec.ts`（如需改动先报队长）。

## 6. 测试要求（正式测试断言正确行为；探针保留为历史证据）

**单测（`request-budget.test.ts`）至少覆盖**

1. 中文/Unicode 长标题：`name` 80 字、`nextTitle` 120 字上限生效，且课程原始数据未被改写。
2. 超过 32000 字的**旧快照**（历史遗留 `courseContext`）经构建后：每条第 ≤32000、总 ≤ min(budget, 120000)、免责句仍在（或按 §3.3 整体丢弃并标注）。
3. 正常课程块 + 接近预算的历史 + 接近预算的当前问题：总字符 ≤ 预算，历史整条丢弃计数正确。
4. 当前问题本身放不下 → `ok:false`，`allowedChars` 与文案可读；**不产生副作用**（由 store 级用例断言）。
5. 免责句在**任何**裁剪/收缩路径下都保留（课程块未被整体丢弃时）。
6. 旧轮重试用旧快照、新轮用新快照、普通会话（无课程）路径不回退。
7. 构建失败后的状态收尾：`sending=false`、无空助手占位、消息可重试、无未处理 Promise（`process.on('unhandledRejection')` 或等价手段在用例内断言）。

**浏览器验证（`chat-context-budget.spec.ts`，路由级 stub 上游，断言真实报文）至少覆盖**

1. 正常课程轮：`POST /api/v1/chat/stream` 报文中 system 课程块在最前、总字符 ≤ `min(budget, 120000)`、每条 ≤32000（对超长标题场景重复断言）。
2. 超长课程字段（UI 路径粘贴长大纲标题）：报文仍合规、免责句仍在。
3. 当前问题放不下：**没有**发往 `/api/v1/chat/stream` 的请求，输入框内容仍在，页面给出可读提示；改成短问题后能正常发送成功。
4. 失败恢复：错误（上游 5xx 或 SSE error）后按钮/忙态回到可重试，无残留空占位。

## 7. 验收条件（A1 按条核）

1. 探针在修复后按预期失败（缺陷假设不再成立），且反转记录入 Git。
2. §3 的 9 条不变量逐条有代码位置 + 测试证据。
3. §6 单测/浏览器用例真实通过，且断言与产品行为因果绑定（不是只验辅助函数长度）。
4. 现有课程闭环用例（`course-sessions.spec.ts` 11 例）不回退。
5. `typecheck`、`lint --max-warnings=0`、`test:unit` 全绿；`build` 由队长跑；全量 e2e 由队长跑。
6. 文档不得出现「精确 token」「保证不超模型上限」等夸大表述；`requestBudget.estimated` 语义用「字符估算」表述。
7. 不夸大：不得标记 RAG 已接入、真实供应商已通过、R-13 已处理。

## 8. 交付格式

- 代码 + 测试 + `docs/qa/CHAT-CONTEXT-BUDGET/probe-reversal/`（探针副本 + 反转运行记录）。
- 结果卡：起点、改动文件清单、§3 逐条不变量→证据、首败与修复、实跑数字、未执行项、剩余边界。
- 队长负责：集成、构建、全量 e2e、STATUS/PROJECT_GUIDE/矩阵、独立验收组织、本地提交。
