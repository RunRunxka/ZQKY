# H1-COURSE-SESSIONS v1 — 批次证据（课程学习会话闭环）

> 本批为**用户锁定的业务目标批**（2026-09-22），目标是把「课程 → 创建学习会话 → 真实问答 → 返回课程 → 恢复原会话」做成可用闭环，并同时交付有界前置补丁 BOOKS-CS-FOLLOWUP v1（单独提交、单独验收，见 [其批次证据](../BOOKS-CS-FOLLOWUP/README.md)）。
> 契约冻结于 [TASK-CARD.md](TASK-CARD.md)；稳定决定写入 [PROJECT_GUIDE §4.3](../../PROJECT_GUIDE.md)；逐项页面/交互证据见 [PAGE_MATRIX](../../replica/PAGE_MATRIX.md) 与 [AI_INTERACTIONS](../../replica/AI_INTERACTIONS.md)。

## 1. 起点、范围与候选

| 项 | 值 |
| --- | --- |
| 起点 | `main@d2638f2`（现场核对了 HEAD/分支/工作区；未切分支、未合并、未推送、未部署） |
| 参考 | `F:\DeepTutor`（只读，`42fab3cf429a1fbf36b257ab8d116a3814964202`） |
| 本批候选（代码，**r2 = 当前交付候选**） | **`701d391`**（直接父 `9d966c3`；`9d966c3`/`68af6a0` 为纯文档提交，再往前是 r1 候选 `8104654`），tree `d600f77c01ab3ce721775bdf954e5ebb602a8e5d`；构建 **`BUILD_ID = 93TKwQeZ9Av2qkSOC_8aR`**。历史候选：r1 `8104654`（tree `d55e1442…`，构建 `2Rz23h6qbByqaJTSJY4x1`，A1 r1 判「需修订」）、r0 `KvvCBGKxFYVt6TGLyuGw8`（首个全量回归暴露过期断言）——候选演化与处置见 §6、[A1 r1 报告](A1-REPORT-01.md) |
| 目标闭环 | 课程页新建/恢复本课程会话 → 跳聊天 → 真实 `POST /api/v1/chat/stream` 问答（带课程上下文）→ 返回课程 → 会话仍在、归属不变 |
| 不在范围 | BookChatPanel、课程学习智能体工具、自动学习规划、精通/记忆、RAG 正式接入、真实书籍生成、全站动画重做、任何模拟聊天捷径 |

### 1.1 候选指纹（A1 复验用，`git show 701d391:<file>` 的 sha256 前 16 位；r2 变更的文件已右列更新）

| 文件 | sha256(16) | 文件 | sha256(16) |
| --- | --- | --- | --- |
| `apps/web/src/contracts/chat.ts` | `fe2123cdfd53ea23` | `apps/web/src/services/course-session.ts` | `78562a746d455ccb` |
| `apps/web/src/features/chat/model/store.ts` | `fa76948f8fee29a6` | `apps/web/src/services/chat-repository.ts` | `eeca62d80aa5b02f` |
| `apps/web/src/features/chat/ChatWorkspace.tsx` | `2dae2b9442227c84` | `apps/web/src/services/course-session.test.ts` | `465ae07d097eef1e` |
| `apps/web/src/features/chat/model/course-context.test.ts` | `65c44ba3bc215068` | `apps/web/src/services/chat-repository.test.ts` | `e2a731a66e1ea063` |
| `apps/web/src/features/courses/CourseSessions.tsx` | `243253ff8669d4db` | `tests/e2e/course-sessions.spec.ts` | `05f9c00dc662f189` |
| `apps/web/src/features/courses/courses.css`（仅注释） | `80cb0d3593cbeab6` | `apps/web/src/features/reading/ReadingWorkspace.tsx`（仅文案/注释） | `b3b40e97c8b3960b` |
| `apps/web/src/features/courses/CourseDetail.tsx` | `cdc47981a9488861` | `tests/e2e/books-courses.spec.ts` | `1f5153530658b5fb` |
| `apps/web/src/features/courses/CoursesShelf.tsx` | `170943ad56090571` | `apps/api/tests/test_chat_stream_api.py` | `86ca2645767a67ec` |

构建自证：产物内含本批专属字符串（`所属课程：`、`返回课程`、`课程资源（仅登记引用`）→ e2e 跑的是本候选产物。

## 2. 参考对照（先核对，再决定）

核对位置：`deeptutor/services/session/turns/request_preparer.py`、`deeptutor/services/courses.py`、`deeptutor/api/routers/sessions.py`。

| 维度 | 参考（DeepTutor） | 本项目 | 说明 |
| --- | --- | --- | --- |
| 归属字段 | `session.preferences.course_id`（后端会话偏好） | `Conversation.courseId` / `ConversationMeta.courseId`（本地 IndexedDB 会话 + 列表元数据） | 语义相同、承载不同（本项目聊天持久化在浏览器） |
| 归属校验 | 请求里显式给 `course_id` 时后端校验课程存在，不存在即 404；课程页另有 `OrganizedSessionList` 提供手动组织（把会话设为某课程或清空 `course_id`） | 新建会话时课程来自课程页上下文（页面上已加载的课程），保存前不写死标题；**本批不含手动改绑**（旧会话保持未归属，不提供"任意 courseId 伪造"入口） | 手动改绑属后续范围；两版都不按标题/最近访问猜测 |
| 课程会话列表 | 按 `course_id` 过滤会话 | 按 `ConversationMeta.courseId` 精确过滤，未归属/空串不回填 | **两版都不按标题/最近访问猜测** |
| 上下文进入请求 | 服务端 turn 预处理加载课程 → `_apply_course_defaults` + 渲染 `course_conventions` 放到 payload（不持久化） | 前端发送时冻结 `TurnCourseSnapshot` → 渲染为一条 `system` 消息放在 `messages` 最前（后端零改动），随助手消息持久化 | 本项目借此让"重试沿用原快照"成为可验证事实 |
| 课程删除 | `DELETE /courses/{course_id}` 先遍历全部会话，把命中会话的 `preferences.course_id` **清空**，再删课程（`deeptutor/api/routers/courses.py:198-213`）；下一轮 turn 若仍解析到失效 id 也会置空并静默按普通轮次继续 | 历史会话与归属保留、界面如实提示"课程不可用/已删除"，**不自动换绑、不级联清空**；发送时同样不带课程上下文 | **有意差异**（用户要求"保留历史会话和消息，不级联删除、不自动换绑"）：本项目不在删除时回写会话，改为显示层如实提示，避免"归属被静默抹掉" |
| 大纲/资源 | `set_unit_covered` 手判 + 资源三态 | 同（保留既有手判 covered 与 R-11 三态） | 本批不伪造掌握度 |

## 3. 实现要点（逐条对应用户要求）

1. **归属与兼容**：`Conversation.courseId?` + `ConversationMeta.courseId?`（`apps/web/src/contracts/chat.ts`）；`normalizeConversation` 只保留非空字符串 `courseId`，否则删除（旧会话保持未归属，**不猜测、不回填**）；`toMeta` 透传给列表。`schemaVersion` 仍为 1，旧数据无需迁移。
2. **单一会话库**：课程页与聊天页共用既有 `ChatRepository`（IndexedDB `zhiqikeyuan-chat`）与既有聊天 store，**没有第二套课程聊天数据库、没有模拟问答实现**。
3. **课程页会话区**（`features/courses/CourseSessions.tsx`，挂在 `CourseDetail`）：本课程会话列表（按更新时间倒序）、空态/加载/读取失败 + 重试；「新建学习会话」**先保存成功再 `router.push('/chat/<id>')`**；同一 tick 连点由同步 `creatingRef` 去重；写入失败保留页面状态并给「重试新建」；归档课程只读（新建禁用，既有会话仍可打开）。
4. **聊天页课程上下文**（`features/chat/ChatWorkspace.tsx`）：`所属课程：<name>` + 「返回课程」；课程已删除或目录读取失败时显示 `courseAvailabilityLabel` 与「重试读取课程 / 课程列表」，**不回落其他课程**；`courseContextWarning` 以可关闭提示说明"本轮未携带课程上下文"；切换到普通会话或其他课程会话时，归属条与警告都随 `activeCourseId` 重算，不残留。
5. **课程上下文进入真实请求**（`features/chat/model/store.ts` + `services/course-session.ts`）：`send` 时 `resolveCourseSnapshot` → `buildCourseSnapshot`（课程名、约定 ≤1200 字符、大纲摘要、资源**登记**清单、`frozenAt`）→ `courseContextMessage` 渲染为一条 `system` 消息（**可变部分**在 2400 字符预算内收缩：先压缩单条资源标签 → 再减少列出的资源条目并标注「…等共 N 项」→ 最后压缩约定；**资源行的「仅登记引用」免责句是固定前缀、不会被砍尾**。固定行本身超预算时函数原样返回：课程名有 60 字校验上限，但**大纲单元标题没有长度上限**，粘贴超长标题可使该轮 system 文本超过 2400 —— 仅影响请求预算，表现为上游报错而非假成功，见 §10 第 7 条）→ 插到 `requestMessages` 最前 → 既有 `ChatService.run` → `POST /api/v1/chat/stream`。快照**随助手消息持久化**（`courseContext`），`retry` 传 `last.courseContext`，因此**重试沿用原轮快照，课程修改只影响新轮**。
6. **删除/归档/读取失败**：课程删除/归档不改写任何会话与消息（**有意差异**：参考在 `DELETE /courses/{course_id}` 里把命中会话的 `preferences.course_id` 清空，本项目按用户要求保留历史与归属，只在显示层如实提示并保留"重试读取课程 / 课程列表"入口）。资源继续遵守 R-11 三态；界面如实写明"资源仅登记引用，内容未解析、未检索、未随本请求发送"。
7. **不伪造**：不生成 AI 掌握度、不自动改大纲 covered、不做学习规划；`RAG 尚未接入`的既有边界原样保留。

## 4. 请求链路三段取证（浏览器 → FastAPI → 供应商适配器）

| 段 | 证据 | 结果 |
| --- | --- | --- |
| 浏览器 → FastAPI 报文 | `tests/e2e/course-sessions.spec.ts`：路由级捕获 `/api/v1/chat/stream` 请求体，断言 `messages[0].role === 'system'` 且内容含课程名、约定、大纲与"仅登记引用"文案；第二个课程同样断言其自身课程名（不串位） | **pass（真实浏览器 + 真实构建产物）** |
| FastAPI → 供应商适配器 | `apps/api/tests/test_chat_stream_api.py::test_system_course_context_is_forwarded_to_provider`：断言 provider 收到的请求体里 system 课程上下文逐条存在且顺序在用户消息之前 | **pass（pytest，本轮 9 项全过）** |
| 适配器 → 供应商 | 既有 `apps/api/tests/test_providers.py`（Anthropic 把 system 提升为顶层 `system` 参数等） | **沿用既有证据，本批未重跑；真实供应商调用 not_run（无可用凭证）** |

结论：课程上下文确实经过"浏览器 → 现有 FastAPI → 供应商适配器"，且**未新增后端请求字段、未改后端产品代码**（`ChatMessageIn.role` 本就允许 `system`）。

## 5. 实跑结果（本批，队长集成后）

| 维度 | 命令 | 结果 |
| --- | --- | --- |
| 类型 | `npm run typecheck`（`next typegen && tsc --noEmit`） | 通过（Types generated successfully）；r2 候选复跑 |
| 静态检查 | `npm run lint`（`eslint apps/web/src tests scripts --max-warnings=0`） | 通过，0 警告 |
| 单元测试 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **51 文件 / 416 例通过**（上一批 49/403；本批 +2 文件 / +13 例，含 r2 新增的整体预算收缩用例） |
| 构建 | `npm run build`（总控自跑） | 通过，**r2 交付候选构建 `BUILD_ID = 93TKwQeZ9Av2qkSOC_8aR`**（r1 为 `2Rz23h6qbByqaJTSJY4x1`，r0 为 `KvvCBGKxFYVt6TGLyuGw8`；见 §6） |
| 课程 e2e（新增） | `npx playwright test tests/e2e/course-sessions.spec.ts` | **11/11 通过**（r1 的 9 例 + r2 新增 F1/F3 两例）；与 `books-courses.spec.ts` 合并定向跑 **17/17 通过（36.8s）** |
| 全量前端 e2e | `npx playwright test` | **191 passed / 0 failed / 0 flaky（6.4m）**（r2 候选；r1 为 189/0/0）—— 见 §5.1 |
| 后端 API 测试 | `npm run test:api -- tests/test_chat_stream_api.py` | **9 passed, 1 warning（0.47s）**（含本批新增 system 转发用例） |
| 真实供应商 | — | **not_run（无可用凭证）**；本批所有问答断言均在上游替身/后端 provider 替身上完成，未冒充真实调用 |
| UI 三视口/键盘/减少动画 | `tests/e2e/course-sessions.spec.ts` 第 9 例 | **已执行并通过**（1440×900 / 1920×1080 / 390×844 无横向溢出；聚焦后回车可新建并跳转；`prefers-reduced-motion: reduce` 下会话区完整可用） |

### 5.1 全量回归（冻结候选）

- 首轮全量回归（构建 `KvvCBGKxFYVt6TGLyuGw8`）：**188 例中 187 通过 / 1 失败** —— 失败为 `books-courses.spec.ts:138` 的**过期断言**（仍期望已被本批替换的"课程学习会话未接入"占位）。处置见 §6 第 4 条。
- 处置后全量回归（r1 构建 `2Rz23h6qbByqaJTSJY4x1`，含 UI 例）：**189 passed / 0 failed / 0 flaky（6.3m）**。
- A1 r1 判「需修订」后的修复批全量回归（**r2 交付候选构建 `93TKwQeZ9Av2qkSOC_8aR`**）：**191 passed / 0 failed / 0 flaky（6.4m）**。
- 计数口径：上一批次基线 180 例（CS 批次全量 178 + FOLLOWUP 补丁新增 2 例双标签页并发）+ 本批新增 11 例 = 191。

### 5.2 UI 验证范围（如实）

- 本批**没有新增主题、没有改动任何样式规则**：唯一的 `.css` 改动是 `courses.css` 顶部一句注释（“未接入 banner” → “课程详情页信息提示条”，r2 随 A1 F8 清扫），无选择器/属性/数值变化。会话区与课程归属条复用既有 `/chat` 的 `.chat-banner` 基类（`features/chat/styles/chat.css:239`）与课程页既有版式；归属条以 `.chat-banner.course` 语义修饰类标注（该修饰类本身无独立规则，只作选择器/测试锚点），未引入新调色板。
- **三视口（1440×900 / 1920×1080 / 390×844）已实测**：`document.scrollWidth - clientWidth ≤ 1`（无横向溢出），会话区标题与新建入口均可见（e2e 第 9 例）。
- **键盘已实测**：`新建学习会话` 可聚焦（`toBeFocused`）并用 `Enter` 创建会话后跳转 `/chat/<uuid>`；既有可见焦点环沿用（未新增 `:focus-visible` 规则）。
- **减少动画已实测**：`emulateMedia({ reducedMotion: 'reduce' })` 下课程页与会话区完整可用（不依赖过渡完成）；本批未新增关键帧动画。
- **未做**：像素级人工视觉评审与逐状态视觉矩阵（归入视觉批次），本文件**不宣称视觉通过**；真实移动设备硬件触摸仍为既有 not_run。

## 6. 首败与修复（如实记录）

| # | 现象 | 定位 | 修复 |
| --- | --- | --- | --- |
| 1 | `course-context.test.ts` 报 `vi is not defined` | 新测试文件未 import vitest 的 `vi`（项目未开 globals） | 显式 `import { vi }` 并加 `afterEach(() => vi.restoreAllMocks())` |
| 2 | `npm run lint` 报 1 个 warning：`course-session.test.ts:12 'readCourses' is defined but never used` | 用例重写后遗留未使用导入（**A1 复验书籍补丁时也观察到同一 warning**） | 删除该导入，lint 回到 0 警告 |
| 3 | 后端用例写入时脚本中断（heredoc 把 Python 字符串折行，`SyntaxError: unterminated string literal`） | 长中文/转义内容经 shell heredoc 传递被破坏 | 改用文件写盘的编辑方式落盘后再跑；`test_chat_stream_api.py` 9 passed |
| 4 | **全量前端 e2e 首次回归：187 通过 / 1 失败** —— `tests/e2e/books-courses.spec.ts:138` 断言 `课程学习会话未接入` | 该断言描述的是本批**被替换掉的旧占位横幅**（课程详情页现在是真实会话区）；同时 `CoursesShelf.tsx:68` 载入演示数据的提示文案仍写"课程学习会话未接入"，属**过期的用户可见文案**（本批漏改） | 断言改为断言新行为（`学习会话` 标题 + `本课程还没有学习会话` 空态），提示文案改为"可在课程详情创建学习会话并进入真实问答"；重跑受影响两文件 **14/14 通过**，随后全量回归见 §5.1。**未删除任何断言**，转换后的断言描述当前正确行为 |
| 5 | 课程 e2e 首跑（核心 8 例） | — | **无失败**：8/8 一次通过（未出现选择器或行为失败） |
| 6 | 新增 UI 例（三视口/键盘/减少动画） | — | **无失败**：首跑即绿（14.8s 内含全部 9 例） |
| 7 | **A1 r1 独立验收 F1：跨任务二次点击创建重复会话**（`await save` → `router.push` → 本页卸载之间，守卫在原 `finally` 里被提前释放；A1 探针 gap=10/25ms → 2 条会话） | A1 只读探针（`%TEMP%\a1-h1cs\probe-p1.log`）+ 源码 `CourseSessions.tsx` 原 `finally` 分支 | **已修**：保存成功后**守卫保持到本页卸载**（只在失败分支释放）；新增 e2e「跨任务二次点击…」用同一探针手法断言本课程会话恰好 1 条。**未删除任何既有断言** |
| 8 | **A1 r1 F2：`courseContextWarning` 跨会话残留**（课程已删除的警告切到普通会话后仍显示） | A1 探针（`[P4] 切换后警告元素数=1`）+ `store.ts` 切换路径未清除 | **已修**：`create`/`selectConversation`/`deactivate`/`removeConversation` 四处切换点清除该字段；课程删除用例追加「切到普通新会话后警告消失」断言 |
| 9 | A1 r1 F3：测试有效性缺口（读取失败无自动化证据、归档用例标题超出断言、整体截断未测、`继续最近会话` 未测） | A1 报告 §3 F3 表 | **已补**：新增 e2e「会话列表读取失败 → 错误+重试 → 恢复（且不冒充空态）」；归档用例预置既有会话并**实际打开验证历史**；单测新增整体预算收缩用例（断言免责句存活、`等共 40 项`、末条不出现）；课程列表断言 `继续最近会话` 的 `href`；删除一行无断言的遗留调用（A1 F11） |
| 10 | A1 r1 F4：文档夸大（称"按条目截断并在文案里说明"，实为整段砍尾） | A1 报告 §3 F4 | **改实现而非只改词**：`courseContextMessage` 改为预算内收缩（压缩标签 → 减少条目并标注总项数 → 压缩约定），**「仅登记引用」免责句作为固定前缀不被砍尾**；README 同步为真实行为 |
| 12 | **A1 r2 复验**（候选 `701d391` / 构建 `93TKwQeZ9Av2qkSOC_8aR`） | A1 独立探针（gap 0–150ms + **合成 click 绕过 disabled** 验证 ref 守卫、读取失败独立注入点、F4 边界探针）+ 全量复跑 | **判「可交付」**：F1/F2 确认修复且未回退；要求 4/5/6/7 重跑通过（1/2/3/8/9 抽查通过）；遗留仅文档/元数据/注释类。全文见 [A1 r2 报告](A1-REPORT-02.md)；其 §3.1–§3.4 残留已由队长订正（见该报告 §9） |
| 11 | A1 r1 F5–F8：过期文案/文档（`ROUTES.md` 课程详情"学习会话未接入"、`PAGE_MATRIX` 段落自相矛盾、`STATUS §5.B` 第 2 条仍以现在时写回退路径、阅读页 chip 与 `courses.css` 注释） | A1 报告 §2.3 表 | **已清扫**：四处就地订正（阅读页 chip 改为"阅读会话未带课程归属"以区别于聊天会话；`courses.css` 注释改为课程详情信息提示条）。F9（课程块在预算裁剪后追加、最多 +2400 字符）已登记进 §10 第 7 条 |

**本批没有出现"测试数通过但产品行为错"的静默通过**：新增 e2e 全部是真实浏览器行为断言（含报文捕获、IndexedDB 注入失败、流式中切换会话），不依赖单测数量。

## 7. 测试清单（本批新增/改动）

| 文件 | 用例 | 覆盖 |
| --- | --- | --- |
| `apps/web/src/services/course-session.test.ts`（新） | 7 | 快照构建与渲染（含截断与"仅登记"文案）、资源三态、`buildNewConversation`、`resolveCourse` 三态、`listCourseSessions` 只按 courseId 过滤 |
| `apps/web/src/features/chat/model/course-context.test.ts`（新） | 5 | `system` 消息进入请求 messages；新轮用新快照 / 重试沿用旧快照；未归属会话不带课程上下文；课程删除后不回落；读取失败时按 unavailable 处理并给警告 |
| `apps/web/src/services/chat-repository.test.ts`（改） | +1 | `courseId` 往返与旧记录（无 `courseId`）保持未归属 |
| `apps/api/tests/test_chat_stream_api.py`（改） | +1（共 9） | `system` 课程上下文逐条转发给 provider 请求体 |
| `tests/e2e/course-sessions.spec.ts`（新） | 11 | 两课程互不串位（含报文断言 + 「继续最近会话」href）；旧会话兼容；同 tick 连点 + 写入失败保留并可重试；刷新/前进后退/往返；课程修改后新轮新快照 vs 旧轮重试旧快照；课程删除后历史保留且如实提示（r2 追加切到普通会话后警告消失）；归档课程只读且**实际打开既有会话验证历史**（r2 补）；流式中切换会话不污染目标；**跨任务二次点击不产生第二条会话**（r2 新增，A1 F1 回归）；**会话列表读取失败 → 错误 + 重试 → 恢复**（r2 新增，A1 F3）；三视口无横向溢出 + 键盘新建 + 减少动画可用 |

## 8. 提交清单（本地，不推送）

| 提交 | 内容 |
| --- | --- |
| `feat(course-sessions)` | 产品代码 + 单元/后端/e2e 测试（`contracts/chat.ts`、`services/course-session.ts`、`chat-repository.ts`、`features/chat/model/store.ts`、`features/chat/ChatWorkspace.tsx`、`features/courses/CourseSessions.tsx`、`CourseDetail.tsx`、测试文件） |
| `docs(course-sessions)` | 本文件、[STATUS](../../STATUS.md)、[PROJECT_GUIDE](../../PROJECT_GUIDE.md) §4.3、[PAGE_MATRIX](../../replica/PAGE_MATRIX.md)、[AI_INTERACTIONS](../../replica/AI_INTERACTIONS.md) |
| `docs(books-followup)` | [A1 报告归档](../BOOKS-CS-FOLLOWUP/A1-REPORT.md) + W1/W2 文档卡口关闭（CS README/DEFECT-LEDGER、FOLLOWUP README） |

## 9. not_run 清单

| 项 | 原因 |
| --- | --- |
| 真实供应商问答（DeepSeek/Anthropic/OpenAI 等） | **本轮未发起任何真实外呼、未验证凭证有效性**（不对凭证可用性作结论）。A1 r2 复核订正：本机确实存在 `.env` 键名与 `.local-data/model-config.json` 的连接配置（结构层面），故原因应记为“未外呼/未验证”而不是“无凭证”。真实链路证据止于 FastAPI→adapter 替身 |
| 真实两浏览器进程/两 profile 并发下的课程会话 | 本批 e2e 为同 context 多页面；课程会话是每标签页本地 IndexedDB，未构造跨 profile 场景 |
| 逐状态视觉/动画人工验收（三视口像素级、motion 矩阵） | 归入视觉批次；本批无新增主题与关键帧动画 |
| 移动端硬件触摸（真实设备手势） | 既有 not_run 项，本批未改变 |
| RAG 检索课程教材 | RAG 未接入；资源仅登记引用（R-11 三态） |
| 后端产品代码 | 本批**零改动**；仅新增一条测试 |

## 10. 剩余边界与风险

1. **资源 ≠ 上下文内容**：`TurnCourseSnapshot.resources` 只记录"课程登记了哪些资源"，请求里明确写明"内容未解析、未检索、未随本请求发送"。RAG 接入前不得解读为"模型读过教材"。
2. **真实供应商未验**：适配器对 `system` 的处理由既有单测覆盖；真实供应商是否遵循约定内容属未验范围。
3. **同标签页多课程并发**：会话保存走既有 `ChatRepository`（带 `expectedRevision` CAS），课程页新建与聊天页写同一条记录时按既有冲突语义报错，未新增跨标签页锁。
4. **课程删除后的历史会话**：保留归属，界面显示"课程不可用"，发送时按普通问答（与参考一致的线上行为 + 更明确的提示）。若后续要求"迁移到别的课程"，属新任务。
5. **`course_conventions` 文案长度**：约定 1200 字符、整体 2400 字符为本地限制，超出即截断并在消息里说明截断，避免静默丢失。
6. **手动改绑/组织会话未实现**：参考在课程页提供 `OrganizedSessionList`（重命名、归档、设置/清空会话的 `course_id`），本项目本批只做"新建即归属"，不含把既有会话改绑到课程或清空归属的入口——属后续课程闭环范围，不在本批交付内。

7. **课程上下文的预算位置与上限性质**：课程块在 `selectMessagesForRequest`（`contextBudgetChars`）裁剪**之后**追加，小窗口模型（`maxOutputTokens` 较大而 `contextTokens` 较小时）可能因此超出请求预算，表现为**上游报错而非假成功**（代码注释已说明）。2400 字符是对**可变部分**（约定、资源条目/标签）的收缩保证；固定行不可压缩，其中**大纲单元标题无长度上限**（课程名有 60 字校验上限），粘贴超长标题时该轮 system 文本可超过 2400（仅影响预算，无数据风险，不是假成功）。后续若需全称成立：给 `snapshot.name`/`syllabus.nextTitle` 加长度上限，或把课程块纳入裁剪预算统一计算（属后续批次，需重新冻结候选）。

## 11. 资源释放

- 构建目录 `apps/web/.next` 由总控单写；本批构建完成后无并行构建。
- e2e 端口 5174 每次跑完释放（`netstat` 核对无 LISTENING）。
- 端口/进程：无残留 `next start` / `uvicorn`（派生的后台服务由 Playwright 的 webServer 管理，跑完即退）。
- `_work/` 下本批脚本仅本地使用，不随仓库提交（仓库已于 `17e3a09` 起不跟踪 `.zcode`；`_work` 亦不入库）。
