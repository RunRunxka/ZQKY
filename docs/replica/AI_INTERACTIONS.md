# AI 交互映射与验收边界

更新：2026-09-15。主聊天仅真实SSE，R-03生产模拟残留已清；复杂能力/工具/附件真实执行仍未接。模型管理和供应商隔离合同已有局部独立验收；真实DeepSeek证据按模型/预算/推理开关分组，R-13未关闭，其他供应商不据此升级。阅读/写作/知识库的显式模拟单独标注。当前状态与候选索引见 [STATUS](../STATUS.md)，历史真实首败见 [2026-09-12结果](../qa/acceptance-20260912/summary.json)。

状态包含待实现、部分实现、实现待验收、已验收、实现待修复、真实服务未接入、已移除。下表“组件保留”不等于运行通道已接通；阅读/写作等模块的显式模拟与主聊天分开。

| id | 交互 | 原版来源 | 状态 | 现状与待办 |
| --- | --- | --- | --- | --- |
| A-send | 发起、取消、恢复 | features/chat/model/protocol.ts、transport | 部分实现 | 2026-09-12真实Flash发起、推理中停止（AbortError）、新会话2秒无晚到消息、真实错误后重试与刷新恢复通过；供应商远端计算/计费取消未观测，其他协议实际供应商未验。 |
| A-real | 真实流式问答 | transport | 部分实现 | 2026-09-13 B-MODEL-ACCEPT：普通非流式与SSE**分开**测量（`/test` stream:false 返回 application/json 单 JSON；`/chat/stream` 为 text/event-stream），纠正上轮用SSE冒充普通调用。DeepSeek两模型三档：默认2048零正文(EMPTY_RESPONSE)；关推理默认预算出正文但 finishReason=length（**截断，不算成功**）；受控8192 stop 完整结束。浏览器受控档首可见中文1172ms、KaTeX 12处0错误、停止/重试/刷新通过。R-13**仍未关闭**；Responses/Anthropic无可用凭证。 |
| A-reasoning-math | 真实推理展示/正文公式 | 固定DeepTutor AssistantActivity、AnswerMarkdown/KaTeX | 部分实现 | Flash8192样本：3031推理增量、588正文增量；自动展开→正文出现折叠→手动开保持，刷新可恢复；27处公式/0KaTeX错误，另独立双公式样本与手机通过。推理区公式专项及其他模型/协议不据此升级全验收，Pro长答无正文仍失败。 |
| A-course-resource-safety | 课程资源目录可用性 | 目标自有（对照参考课程资源引用）；知识库/笔记本/书籍目录 | 已验收 | 2026-09-14 B-COURSE-RESOURCE-SAFETY：目录在 effect 中集中读取为容错快照，三态区分 available/missing/unknown；读取失败显示错误与重试、不断言目标已删除、不阻断课程正文/大纲/其他目录、不自动删引用；e2e `course-resource-faults.spec.ts` 9 项含故障→重试→修复→恢复与手机视口 |
| A-source-locate | 来源回链与消息定位 | 目标自有（对照参考会话深链）；业务页 → 聊天 | 已验收 | 2026-09-14 B-CHAT-SOURCE-FINISH：题库/笔记产物保存时落库真实 sessionId（E2E 走真实保存按钮路径证明）与可选 messageId；进入 `/chat/<sessionId>?message=<messageId>` 后**仅在该会话内**定位该消息并提示「已定位到来源消息」；消息已删提示「原消息已不存在」，会话与原内容保留；失效会话给不可用态、不自动打开最近会话、不新建会话，学习记录与主动返回保留；减少动画下不依赖平滑滚动。e2e `chat-message-locate.spec.ts` 12 项 |
| A-mode | 原真实/模拟模式切换 | 目标自有，2026-09-09 用户要求删除 | 已验收 | 2026-09-14 B-H0R-CHAT-LINKS：不可达 mock 分支（InfoPanel 模拟模型块、ComposerContextChips mock 人设胶囊、mode 常量/依赖）、`mock={false}` 残留参数、误导文案与专用 CSS（`.chat-mode-switch*`/`.chat-banner.mock`/`.chat-mode-chip`/`.chat-stale-notice`）已清除；`ChatServiceKind/Conversation.mode` 保留但仅用于读取历史与测试替身。隔离验收真实失败不回退模拟。测试替身仅 tests/fixtures，旧模拟库不读不写不清空 |
| A-model | 模型选择 | 指定主页模型弹层 + 原 ChatComposer 模型选择器 | 已验收 | 2026-09-09：输入区向上弹层、实际模型品牌图标、搜索/连接分组、默认/会话级选择、管理跳转、Escape/选择焦点与生成禁用；三个视口验证；仅指当时聊天选择器，不涵盖新模型管理/供应商任务 |
| A-model-management | 连接/模型管理重做 | 固定DeepTutor ConnectionsEditor/ServiceConfigEditor/ModelCards/ModelListPicker | 已验收 | 2026-09-13 MODEL-EXEC v3：供应商卡片→详情弹窗→模型发现多选→参数/推理表单，保留蓝色主题；打开编辑与设默认分离、凭证独立清除（R-08）、附加请求头编辑、创建前先收集必填草稿。首轮候选 1805397 经独立审查 needs_revision（MR-07/08/12/13/14/16 为前端项），**本批已逐项修复**：保存后用服务端值重建草稿、切连接草稿隔离、关闭先确认、导入失败保留勾选并显示错误、恢复附加头、无默认地址先收集 Base URL。回归：单测 11 项 + e2e 8 项 + 真实联调 5 项。后续4ef803b/9965592独立复验已通过已测功能范围；嵌套、草稿与焦点有正式e2e。视觉为实施队长检查，动画partial；不等于全设置或全部真实供应商通过 |
| A-provider-parity | 参考已有LLM供应商 | 固定DeepTutor services/provider_registry.py、llm/provider_factory.py、provider_core/* | 实现待验收 | 2026-09-13 MODEL-EXEC v3：`registry.py` 实装38条（36现行+2 legacy），6 backend 分派；专用 Azure/Codex/Copilot/CodeBuddy；发现来源；受控推理；v1→v2 迁移。独立审查 needs_revision 复现 MR-01/02/03/04/05/06/09/10/11/15 并**全部修复**：Responses 分派、本机免 Key 可调用、受管键可持久化、并发/删除/备份一致、Codex 取消-过期-续期、Copilot 退出。回归 `tests/test_review_regressions.py` 17 项；后端 181/181。后续独立验收已确认合同/隔离行为；真实仅DeepSeek指定场景通过，其余not_run（缺凭证/本机服务），逐条见 `_work/model-providers-v1/provider-coverage-38-implemented.md` |
| A-shell-nav | 全站主页/公共导航/错误页壳 | WorkspaceShell + navigation 登记表 + 固定DeepTutor SidebarNav 当前项语义 | 已验收 | 2026-09-13 B-H0R-SHELL：单一主页来源 HOME_PATH=/chat（品牌按钮/404/规划页/默认标题派生）；单一解析器 resolveCurrentNavigationId（桌面标可见父菜单、抽屉标隐藏项，有对应菜单的路由各1个当前项，未知404不伪造当前项）；StatusShell 使 404/错误页恰好一层壳。独立验收者亲自浏览器遍历 14 路由+404+抽屉并给命中表（e2e `shell-home-nav.spec.ts` 27 项）；错误页reset运行时未验 |
| A-ask-user | ask_user 追问卡 | AskUserOptions.tsx、use-card-submission.ts、ChatStateAdapter submitUserReply | 真实服务未接入 | 追问组件、同轮状态机与历史渲染保留；当前真实SSE不提供wait-user，不能新发起此闭环。旧模拟测试仅历史；接入真实事件后补全卡片状态、提交归属与取消恢复验收。 |
| A-tools | 工具过程 | trace/TracePresentation | 真实服务未接入 | 工具过程渲染、callId身份/状态守卫与历史展示保留，生产无工具执行事件；视觉与真实通道待验收。 |
| A-extensions | 扩展选择与目录联动 | ChatComposer 上下文选择 | 真实服务未接入 | extension-catalog 与设置唯一管理保留；主聊天显示“扩展·真实模式尚未接入”，选择/快照组件存量不等于可执行扩展。 |
| A-capability | 业务能力选择与配置门控 | ChatComposer 能力菜单、CapabilityConfigCard | 真实服务未接入 | 目录/配置/快照和门控代码保留，但主聊天除普通对话外均禁用；不恢复旧模拟生产服务。完整配置状态随真实执行通道接入验收。 |
| A-deep-solve | 深度解题 | deep_solve 相关 | 真实服务未接入 | planning/reasoning/writing及结构化答案的历史组件/测试保留，当前不能从主聊天发起；真实通道与全状态待接。 |
| A-deep-question | 深度出题 | deep_question 相关 | 真实服务未接入 | 旧模拟ideation/generation及题库产物测试为历史；当前无主聊天执行入口，题目保存/来源联动需随真实通道核验。 |
| A-deep-research | 深度研究 | deep_research 相关 | 真实服务未接入 | 研究阶段/报告/笔记渲染存量保留；当前无外部研究执行通道，不能称可运行模拟闭环。 |
| A-visualize | 可视化 | visualize 相关 | 真实服务未接入 | SVG/HTML/Chart/Mermaid产物组件存量保留；主聊天生成禁用，真实配置/事件/错误恢复待接。 |
| A-math-anim | 数学动画（Manim 路由） | visualize math_animator | 真实服务未接入 | 历史模拟产物可由组件呈现，Manim真实执行未接；不能从当前主聊天发起。 |
| A-mastery | 精通之路问答 | MasteryQuestionCard/HandoffCard、ask-user-state | 待实现 | 阶段交接/新轮机制（区别普通 ask_user）（S4） |
| A-artifact | 产物与结果工作区 | SessionViewerPanel、SessionActivityPanel | 实现待验收 | 复合身份、多标签/宽度和多类型产物渲染、保存操作组件保留；普通真实SSE没有artifact事件，历史展示与新产物生成分别验收；来源与跨页联动待核验。 |
| A-message-ops | 消息操作 | ChatMessageList | 实现待验收 | 复制、引用、消息菜单与结果工作区切片已有；完整对照验收和全业务联动待补，复用统一投影。 |
| A-persona | 角色/persona | ChatComposer persona | 实现待验收 | /space/personas 与聊天共用目录，选择与会话归属已有回归；后续跨业务输入区仍需共享同源目录。 |
| A-attachments | 附件/文件 | ComposerInput | 部分实现 | 选取/拖入/粘贴/配额及异步身份代码已有；主聊天拒绝实际附件发送并保留编辑内容，真实解析未接。R-03已删除指向不存在模拟模式的提示，真实附件服务仍未接，不恢复模拟服务。 |
| A-voice | 语音输入 | ChatComposer 录音入口 | 实现待验收 | 无 STT 服务：明确“未接入”说明+带标识演示转写，不采集音频；真实权限/设备拒绝状态待真实服务接入；e2e chat-composer.spec.ts |
| A-reading-companion | 沉浸阅读伴生 AI | reading/workspace/ReadingCompanion、ReadingComposer | 部分实现 | companion-service 已使用统一 ChatService 事件模型，已有显式模拟流式/取消/草稿归属；并非旧同步模板。**R-09 已修（2026-09-15）**：滚动跟随由用户控制（上滚不被强拉回、"回到最新"显式触发且只滚伴生容器）、已测轮次按会话归属、会话切换有前进/后退历史。**READ-RETRY/READ-END 已修（2026-09-18，a9ebcaa）**：错误态重试放行（受控首败后修复）、finalizeTurn 按 turnId 幂等（重复/迟到 end 不重复落库），组件级替身 5 场景回归；显式模拟性质不变。过程/追问/产物/来源完整性、媒体视图仍需补验，见 [STATUS问题与批次索引](../STATUS.md#3-问题台账与验收限制)。 |
| A-kb-ingest | 知识库导入→解析→索引 | 参考 `lib/knowledge-helpers.ts`（resolveKbStatus/kbHasLiveProgress/IndexVersion）、`components/knowledge/KbStatusBadge`、`KbIndexVersionsSection` | 显式模拟（前端闭环已验收） | 2026-09-11 B-H1-KB：`services/knowledge-ingest.ts` 复刻 registered→parsing→indexing→ready、进度、取消、失败重试、刷新恢复、全部就绪追加索引版本；产物为本地结构化样例并全程标注。真实文件解析/向量检索未接入，与真实服务验收分开记录；参考另有 WS/SSE 进度与 KB 级状态（target 以逐文档状态 + KB 汇总呈现），接入真实服务时按参考协议重对齐。e2e `knowledge-notebooks.spec.ts`。**B-R05-EXTEND v1（2026-09-18）**：状态徽标带图标（处理中 Clock3 / 就绪 Check / 失败 AlertTriangle）、版本行状态章、批量与重试按钮进行中禁用防重入（A1 实测 `disabled` 生效）；显式模拟性质与标注未变 |
| A-nb-records | 笔记本记录交互 | 参考 `NotebookConsole`/`NotebookRecordRow`（记录行、展开、类型徽章） | 实现待验收 | 2026-09-18 B-R05-EXTEND v1：railed 选中指示条与描述行、四类多色类型徽章、展开区 pop-in、ConsoleNotice 空/错态、深链错误独占、删除后 URL 规范化、`popstate` 同步选中；三个操作钮与 aria-label 按队长裁定保留（未合并为菜单）。记录编辑器形态与 Markdown 渲染未纳入本批；A1 复验 pass 14/14。数据仍为本地仓储、来源回链语义未变 |
| A-books-pipeline | 书籍提案→大纲→模拟编译 | 参考 `BookCreator`/`BooksRoute`（提案表单、SpineEditor、编译加载）；目标以本地确定性模拟实现 | 部分实现 | 2026-09-18 B-R05-EXTEND v2：确认提案/确认大纲补 busy 态（`disabled` + Loader2）、模拟编译补加载提示（role=status）、侧栏长章节名截断、书签图标化；**状态机本身未变**（draft→spine_ready→ready→archived，仍为同步模拟）。compiling/paused/error、流式生成、暂停恢复、BookChatPanel、HealthBanner 按裁定属 H1，未实现；A1 独立验收 pass 0 fail。模拟性质与显式标注未变 |
| A-course-syllabus | 课程大纲与资料 | 参考 `CourseSyllabus`/`CourseResources`（进度条、单元行、资料行） | 实现待验收 | 2026-09-18 B-R05-EXTEND v2：大纲加 progressbar 进度条（width 300ms）、单元位置编号/covered 删除线/下一单元高亮/topics 截断；资料行 kind 图标 + 不可用后缀独立 shrink-0 + 移除钮 hover/focus 显隐；保存/归档 busy。**R-11 三态与重试链路经 A1 独立回归**（available/missing/unknown 区分、失败重试恢复、原始损坏数据逐字节未变）；课程学习会话、聚合磁贴、Mode/Persona 按裁定属 H1 |
| A-writing-ai | 协同写作 AI 修改（选区改写/润色/扩写/全文生成） | 参考 `CoWriterWorkspace` + `useSelectionEdit`；目标以统一事件模型显式模拟 | 实现待验收 | 2026-09-19 B-R05-EXTEND v3：编辑器正文区样式迁出内联（focus 环）、保存三态 chip 色彩化、AI 面板/预览按钮过渡；**事件模型、取消/失败重试、应用前自动快照、撤销栈、版本恢复逻辑零改动**，`【模拟生成】` 标注与 `AI 改写预览`/`AI 修改预览` aria-label 逐字保留。DOCX 导入（参考 `importCoWriterDocx`）与分栏/同步滚动按裁定属后续批；A1 独立验收 pass 0 fail。显式模拟性质未变 |
| A-reading-library | 阅读库级页面（集合/材料库） | 参考 `reading/library/*`（LibraryShell、ReadingLibrary、MaterialLibrary） | 实现待验收 | 2026-09-19 B-R05-EXTEND v3：集合卡片 hover 与计数图标、材料库筛选 2→4 tab（解析中/失败，**计数来自真实数据**）、状态色点（ready/failed/busy 复用 space-pulse）、行头窄视口 wrap 修复；模拟解析四态与取消/重试/分配路径、`模拟解析` 标注与「文件名（模拟导入，不读取真实文件）」说明逐字保留。LibraryShell 双 tab 化与真实解析按裁定属后续批；A1 独立验收 pass 0 fail（含 R-09 工作区不回退实测） |

本次知识库相关既有e2e 10/10通过，1920/390的已就绪、失败、解析中和系统减少动画状态样本补验通过；仍无真实文件解析/索引/检索调用。所有结果仅更新文档，未修改生产模型配置或能力标记。

## 统一事件约束（已实施部分见 chat-service.ts）

事件联合已实施为 **type 判别式联合类型**：turn-start、text（必带 delta）、reasoning（必带 delta）、process、stage、tool（必带 call/kind/name/status，状态 running/done/error/cancelled）、wait-user（必带 interaction：interactionId/intro/questions/status）、artifact（基础消费已实现）、usage、end、error。全部事件携带 sessionId/turnId；终态（end/error/取消）后拒绝一切后续事件。
**提交归属（R11）**：submitReply 结果只归属发起时的会话/轮次/交互/提交身份（submissionId 实际用于归属判定与服务侧单次消费）；事件顺序=确认→续答/收尾事件→提交返回值。
**消息投影（R12）**：`conversationProjection()` 统一正文+已确认追问交流+逐卡续写；复制、服务请求上下文、预算计算共用。
扩展快照发送时冻结；真实服务不读取、不发送模拟字段，SSE 协议未变。
待补齐：产物完整参考验收与跨业务消费、mastery新轮机制、阅读伴生的完整参考交互。ChatService类型联合比真实HTTP事件更丰富，类型存在不代表当前供应商能产生该事件；真实ask_user、工具及复杂能力通道待接，主聊天不恢复模拟。
