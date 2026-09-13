# AI 交互映射与验收边界

更新：2026-09-12。主聊天运行时只走真实 SSE；模拟残留见 STATUS R-03，复杂能力/工具/扩展执行未接。补验候选99aea55：DeepSeek两个模型普通/流式连接通过，Flash在隔离8192预算下的真实长答、正文公式、推理折叠和恢复通过；默认预算两模型以及Pro8192长答失败。其他协议无供应商连接，不标全协议通过。知识库及阅读/写作的显式模拟单独记录，80项e2e的fixtures不能替代供应商验收。完整证据见 [STATUS](../STATUS.md) 与 [结果JSON](../qa/acceptance-20260912/summary.json)。

状态包含待实现、部分实现、实现待验收、已验收、实现待修复、真实服务未接入、已移除。下表“组件保留”不等于运行通道已接通；阅读/写作等模块的显式模拟与主聊天分开。

| id | 交互 | 原版来源 | 状态 | 现状与待办 |
| --- | --- | --- | --- | --- |
| A-send | 发起、取消、恢复 | features/chat/model/protocol.ts、transport | 部分实现 | 2026-09-12真实Flash发起、推理中停止（AbortError）、新会话2秒无晚到消息、真实错误后重试与刷新恢复通过；供应商远端计算/计费取消未观测，其他协议实际供应商未验。 |
| A-real | 真实流式问答 | transport | 部分实现 | DeepSeek发现和两模型普通/流式连接5/5通过。默认2048长答两模型均EMPTY_RESPONSE；测试副本8192下Flash长答465汉字，首中文13820ms早于结束15428ms；Pro仍预算耗尽无正文。用户正式配置未改，R-13未关闭；Responses/Anthropic无可用供应商配置。 |
| A-reasoning-math | 真实推理展示/正文公式 | 固定DeepTutor AssistantActivity、AnswerMarkdown/KaTeX | 部分实现 | Flash8192样本：3031推理增量、588正文增量；自动展开→正文出现折叠→手动开保持，刷新可恢复；27处公式/0KaTeX错误，另独立双公式样本与手机通过。推理区公式专项及其他模型/协议不据此升级全验收，Pro长答无正文仍失败。 |
| A-mode | 原真实/模拟模式切换 | 目标自有，2026-09-09 用户要求删除 | 实现待修复 | 运行界面和服务创建已是单一真实 store，无切换和免密伪模型；但生产 ChatServiceKind/Conversation.mode、不可达分支、无效提示和专用 CSS 尚未清理。测试替身只留 tests/fixtures，旧浏览器库不读取也不清除 |
| A-model | 模型选择 | 指定主页模型弹层 + 原 ChatComposer 模型选择器 | 已验收 | 2026-09-09：输入区向上弹层、实际模型品牌图标、搜索/连接分组、默认/会话级选择、管理跳转、Escape/选择焦点与生成禁用；三个视口验证；仅指当时聊天选择器，不涵盖新模型管理/供应商任务 |
| A-model-management | 连接/模型管理重做 | 固定DeepTutor ConnectionsEditor/ServiceConfigEditor/ModelCards/ModelListPicker | 实现待验收 | 2026-09-13 MODEL-EXEC v3：供应商卡片→详情弹窗→模型发现多选→参数/推理表单，保留蓝色主题；打开编辑与设默认分离、凭证独立清除（R-08）、附加请求头编辑、创建前先收集必填草稿。首轮候选 1805397 经独立审查 needs_revision（MR-07/08/12/13/14/16 为前端项），**本批已逐项修复**：保存后用服务端值重建草稿、切连接草稿隔离、关闭先确认、导入失败保留勾选并显示错误、恢复附加头、无默认地址先收集 Base URL。回归：单测 11 项 + e2e 8 项 + 真实联调 5 项。独立验收者复验前不升级为已验收 |
| A-provider-parity | 参考已有LLM供应商 | 固定DeepTutor services/provider_registry.py、llm/provider_factory.py、provider_core/* | 实现待验收 | 2026-09-13 MODEL-EXEC v3：`registry.py` 实装38条（36现行+2 legacy），6 backend 分派；专用 Azure/Codex/Copilot/CodeBuddy；发现来源；受控推理；v1→v2 迁移。独立审查 needs_revision 复现 MR-01/02/03/04/05/06/09/10/11/15 并**全部修复**：Responses 分派、本机免 Key 可调用、受管键可持久化、并发/删除/备份一致、Codex 取消-过期-续期、Copilot 退出。回归 `tests/test_review_regressions.py` 17 项；后端 181/181。真实仅 DeepSeek 通过，其余 not_run（缺凭证/本机服务），逐条见 `_work/model-providers-v1/provider-coverage-38-implemented.md` |
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
| A-attachments | 附件/文件 | ComposerInput | 部分实现 | 选取/拖入/粘贴/配额及异步身份代码已有；主聊天拒绝实际附件发送并保留编辑内容，真实解析未接。当前提示指向不存在的模拟模式，必须随 R-03 删除，不恢复模拟服务。 |
| A-voice | 语音输入 | ChatComposer 录音入口 | 实现待验收 | 无 STT 服务：明确“未接入”说明+带标识演示转写，不采集音频；真实权限/设备拒绝状态待真实服务接入；e2e chat-composer.spec.ts |
| A-reading-companion | 沉浸阅读伴生 AI | reading/workspace/ReadingCompanion、ReadingComposer | 部分实现 | companion-service 已使用统一 ChatService 事件模型，支持显式模拟流式/取消/失败重试/草稿归属；并非旧同步模板。过程/追问/产物/来源完整性、滚动与会话历史、媒体视图仍需补验，见 STATUS H2。 |
| A-kb-ingest | 知识库导入→解析→索引 | 参考 `lib/knowledge-helpers.ts`（resolveKbStatus/kbHasLiveProgress/IndexVersion）、`components/knowledge/KbStatusBadge`、`KbIndexVersionsSection` | 显式模拟（前端闭环已验收） | 2026-09-11 B-H1-KB：`services/knowledge-ingest.ts` 复刻 registered→parsing→indexing→ready、进度、取消、失败重试、刷新恢复、全部就绪追加索引版本；产物为本地结构化样例并全程标注。真实文件解析/向量检索未接入，与真实服务验收分开记录；参考另有 WS/SSE 进度与 KB 级状态（target 以逐文档状态 + KB 汇总呈现），接入真实服务时按参考协议重对齐。e2e `knowledge-notebooks.spec.ts` |

本次知识库相关既有e2e 10/10通过，1920/390的已就绪、失败、解析中和系统减少动画状态样本补验通过；仍无真实文件解析/索引/检索调用。所有结果仅更新文档，未修改生产模型配置或能力标记。

## 统一事件约束（已实施部分见 chat-service.ts）

事件联合已实施为 **type 判别式联合类型**：turn-start、text（必带 delta）、reasoning（必带 delta）、process、stage、tool（必带 call/kind/name/status，状态 running/done/error/cancelled）、wait-user（必带 interaction：interactionId/intro/questions/status）、artifact（基础消费已实现）、usage、end、error。全部事件携带 sessionId/turnId；终态（end/error/取消）后拒绝一切后续事件。
**提交归属（R11）**：submitReply 结果只归属发起时的会话/轮次/交互/提交身份（submissionId 实际用于归属判定与服务侧单次消费）；事件顺序=确认→续答/收尾事件→提交返回值。
**消息投影（R12）**：`conversationProjection()` 统一正文+已确认追问交流+逐卡续写；复制、服务请求上下文、预算计算共用。
扩展快照发送时冻结；真实服务不读取、不发送模拟字段，SSE 协议未变。
待补齐：产物完整参考验收与跨业务消费、mastery新轮机制、阅读伴生的完整参考交互。ChatService类型联合比真实HTTP事件更丰富，类型存在不代表当前供应商能产生该事件；真实ask_user、工具及复杂能力通道待接，主聊天不恢复模拟。
