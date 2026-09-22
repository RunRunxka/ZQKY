# H1-COURSE-SESSIONS v1 任务卡与冻结契约

- 起点候选：`d2638f2`（`main`；开工核对 HEAD/分支/工作区，未切分支、未合并、未推送）。前置补丁 BOOKS-CS-FOLLOWUP v1 已单独提交（`a45b011`）并单独验收。
- 目标（用户锁定）：完成"**课程 → 创建学习会话 → 真实问答 → 返回课程 → 恢复原会话**"完整闭环；课程内创建/恢复**真实**聊天、明确课程归属、课程与聊天往返、旧会话兼容及失效资源处理。
- 参考（只读，`F:\DeepTutor` @ `42fab3cf`）事实要点（详见本批 README 的参考对照）：会话归属存在会话 **preferences 的 `course_id`**（空串/缺失 = 未分类，无迁移回填，读取处一律 `str(x or "")` 容错）；**没有**服务端"列出某课程会话"的接口（课程页拉全量会话后在客户端按 `course_id` 过滤，排序 = 置顶 → 流式输出中 → `updated_at` 倒序）；课程上下文进入请求的两条通道是 ①课程 `instructions` 渲染为 **system prompt 块**（截断 1200 字符，`<<< >>>` 分隔）②`course_study` 的状态摘要拼进**用户消息 seed**（≤3200 字，仅该 capability 生效）；**每轮现读课程、不随会话冻结**；课程删除时**先清空命中会话的 course_id 再删课程**（消息/题库/附件保留，显式非破坏）；课程归档对会话零操作（已绑定会话继续注入约定）。
- 与参考的有意差异（本批冻结，理由随行）：本宿主无服务端会话库，会话在浏览器 IndexedDB；课程上下文随**轮次冻结快照**发送（参考为每轮现读）——本批要求"发送时冻结快照、重试用原快照"，因此以本宿主需求为准，并在 README 登记差异。

## 1. 数据与归属契约

1. `Conversation` 新增**可选** `courseId?: string`（会话归属，稳定 id；缺失或空串 = 未归属）。
   - **不改 `schemaVersion`**：旧记录缺该字段照常读；`normalizeConversation` 只保留"非空字符串"的 `courseId`，其他类型丢弃（不猜测、不回填）。
2. `ConversationMeta` 新增可选 `courseId`（列表元数据贯通）；`toMeta` 透传。
3. **禁止猜测归属**：任何按标题、最近访问、URL 或当前打开页面推断并写入/改写 `courseId` 的行为都不允许；旧会话保持"未归属"，不因出现在某课程页而被改写。
4. 归属写入只发生在：①课程页"新建学习会话"（创建时带上 `courseId`）；②未来显式的"移动到课程"操作（本批不做）。
5. 课程**删除/归档不修改会话**：不级联删除、不清空 `courseId`、不自动换绑（与参考"删除即清空归属"**有意不同**：本批要求保留历史与归属可追溯，失效在展示层如实标注）。

## 2. 课程页会话区契约（`features/courses/CourseDetail.tsx` + 新建 `services/course-session.ts`）

- 位置：替换现有"课程学习会话未接入"横幅所在区块，改为**本课程学习会话**区。
- 数据：`readCourseSessions(courseId)`（纯函数，输入 `ConversationMeta[]` → 按 `courseId` 过滤，按 `updatedAt` 倒序）。列表来自既有 `ChatRepository.list()`（同一 IndexedDB `zhiqikeyuan-chat`，**不建第二套会话库**）。
- 新建：`新建学习会话` → 用共享的 `buildNewConversation({ courseId, title })` 生成会话对象 → `repository.save(...)` **等待保存成功** → 成功后才 `router.push('/chat/<id>')`；失败则**保留页面状态、显示失败原因、可重试**，不跳转、不产生第二条会话（busy 期间忽略重复点击）。
- 打开既有会话：`<Link href={'/chat/' + id}>` 深链（复用既有会话存在性校验）。
- 状态：加载中（骨架/文案）｜空态（"本课程还没有学习会话"+新建入口）｜读取失败（错误 + `重试`）｜保存失败（失败提示 + 重试）。
- 归档课程：会话区只读（新建禁用并说明），既有会话仍可打开（保留历史）。
- 课程读取失败：沿用课程页既有三态处理；会话区不得因课程读取失败而清空或改写任何会话。

## 3. 聊天页课程上下文契约（`features/chat/**`、`contracts/chat.ts`）

1. **归属展示**：当前会话有 `courseId` 时显示"所属课程：<名称>"chip 与「返回课程」链接（`/courses/<courseId>`）；课程**已删除/不可用**时显示"所属课程已删除或不可用"并隐藏返回链接（不回落其他课程）。
2. **不残留**：切换会话（含普通未归属会话、其他课程会话）时，课程上下文一律随当前会话重算，不粘住上一会话的课程。
3. **每轮冻结快照**（`TurnCourseSnapshot`，随助手占位消息持久化，与 `extensions` 同法）：
   ```ts
   interface TurnCourseSnapshot {
     courseId: string;
     name: string;
     /** 课程约定（instructions），按上限截断 */
     conventions: string;
     /** 大纲摘要（total/covered/next 标题），供模型参考 */
     syllabus: { total: number; covered: number; nextTitle: string | null };
     /** 仅"登记引用"信息：kind/label/availability —— 不代表内容已解析或已传给模型 */
     resources: { kind: string; label: string; availability: 'available' | 'missing' | 'unknown' }[];
     frozenAt: string;
   }
   ```
   - 发送时**现读课程**生成快照；快照**持久化在助手消息上**，重试沿用原快照（不读取最新课程替换旧轮配置）。
   - 课程修改后**新轮**用新快照（旧轮不追溯）。
4. **真实请求链路**：发送时把快照渲染为一条 `system` 消息，**插在请求 `messages` 最前**（`selectMessagesForRequest` 之后、发送之前），经既有 `streamChat` → `POST /api/v1/chat/stream`；后端 `ChatMessageIn.role` 已支持 `system` 且逐条转 `LLMMessage` 交给供应商适配器（见 `apps/api/app/api/v1/chat.py`、`providers/llm/*`）。**不新增请求字段、不改后端协议**。
   - 渲染上限 1200 字符（对照参考 `_COURSE_CONVENTIONS_LIMIT`）；内容必须**如实**：包含课程名、约定、大纲摘要、资源仅为登记引用（不得声称资源已被解析/检索，不得声称 RAG 已接入）。
5. **能力不可用**：课程不存在或 `readCourses()` 抛错时——不发 system 消息、如实提示"课程上下文不可用，已按普通问答发送"，**不沿用其他课程**。
6. 会话创建（聊天页内"新对话"）默认**未归属**；课程页创建的会话才带 `courseId`（不因为用户在课程页停留过就自动绑定）。

## 4. 不做 / 不变量

- **不做**：BookChatPanel、课程学习智能体工具、自动学习规划、精通/记忆、RAG 正式接入、真实书籍生成、全站动画重做、`?mode=mock` 之类模拟聊天捷径、按标题/最近访问猜归属、服务端会话库。
- **不变量（不得回退）**：主聊天仅真实服务；R-10 来源回链；R-11 资源三态（available/missing/unknown，目录失败不得当成"目标已删除"）；大纲 covered 为**学员手判**（不伪造 AI 掌握度/课程规划）；归档会话不进侧栏；深链失效不回落最近会话；消息级 turnId/sessionId 守卫与迟到事件丢弃；旧会话缺 `courseId` 可读可用。

## 5. 验收条件（行为测试至少覆盖）

1. 两个课程各自创建与恢复会话，互不串位。
2. 普通旧会话（无 `courseId`）兼容：不出现在任何课程列表、聊天页正常、不被改写归属。
3. 创建写入失败保留输入与页面状态、无重复会话（含同一 tick 连点）。
4. 刷新、前进后退、课程 ↔ 聊天往返（`/courses/<id>` ↔ `/chat/<sessionId>`）。
5. 课程修改后新轮使用新快照、旧轮重试保持旧快照（断言发往 `/api/v1/chat/stream` 的 system 内容）。
6. 课程删除/归档/读取失败时历史内容保留（消息、会话、归属不被改写），展示层如实标注。
7. 流式中切换会话不污染目标会话（沿用既有守卫 + 新增断言）。
8. R-10 来源回链与 R-11 三态回归不回退。
9. 工程：`typecheck`/`lint`(0 警告)/`unit`/`build`/相关 e2e；集成稳定后全量前端 e2e；后端仅新增一条"system 消息确实转发"的 API 测试时运行 `npm run test:api` 并记录。
10. UI：1440/1920/390 三视口 + 键盘焦点 + 减少动画（本批新增区块）。
11. 真实供应商：无可用凭证则记 **not_run**，不伪造通过；"浏览器 → 现有 FastAPI → 供应商适配器"三段分别给证据（e2e 网络层请求体、后端 schema/路由源码 + API 测试、供应商适配器既有 system 透传测试）。

## 6. 文件归属（队长=本会话实现者；构建/文档/Git 归队长）

- 新增：`services/course-session.ts`、`tests/e2e/course-sessions.spec.ts`、`services/course-session.test.ts`。
- 修改：`contracts/chat.ts`、`services/chat-repository.ts`、`features/chat/model/store.ts`、`features/chat/ChatWorkspace.tsx`、`features/courses/CourseDetail.tsx`、`features/chat/styles/chat.css` 或新建 `features/courses/styles/course-sessions.css`（仅本区块，消费既有变量）。
- 后端：`apps/api/tests/test_chat_stream_api.py` 仅新增一条断言（不改产品代码）。
- 独立验收 A1 只读稳定候选；不参与实现。
