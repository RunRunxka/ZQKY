# AI 交互映射与验收边界

更新：2026-09-11。主聊天生产只走真实 SSE，模拟模块已删除；普通对话外的复杂能力、工具与扩展执行未接。知识库解析/索引为独立模块的显式模拟（A-kb-ingest），与主聊天分开记录。测试 fixtures 和历史 S2–S4 模拟成绩不能当作当前可调用能力。模型弹层、正文/推理公式、推理自动展开/正文出现收起及手动优先已有，真实供应商仍未验收。历史证据见 [交付历史](../archive/DELIVERY_HISTORY.md#snapshot-status-20260910)，当前计划见 [STATUS](../STATUS.md)。

状态包含待实现、部分实现、实现待验收、已验收、真实服务未接入、已移除。下表“组件保留”不等于运行通道已接通；阅读/写作等模块的显式模拟与主聊天分开。

| id | 交互 | 原版来源 | 状态 | 现状与待办 |
| --- | --- | --- | --- | --- |
| A-send | 发起、取消、恢复 | features/chat/model/protocol.ts、transport | 部分实现 | 真实 SSE 发起/取消/终态守卫/历史恢复已有；隔离HTTP链路有历史证据，实际供应商验收见 A-real。 |
| A-real | 真实流式问答 | transport | 部分实现 | 真实 SSE 与三协议后端已接；本轮供应商未验证（与新能力未接入不同），不可标全部真实验证完成。 |
| A-mode | 原真实/模拟模式切换 | 目标自有，2026-09-09 用户要求删除 | 已移除 | 主聊天单一真实 store；无切换/失败布防/免密伪模型；测试替身仅 tests/fixtures |
| A-model | 模型选择 | 指定主页模型弹层 + 原 ChatComposer 模型选择器 | 已验收 | 2026-09-09：输入区向上弹层、实际模型品牌图标、搜索/连接分组、默认/会话级选择、管理跳转、Escape/选择焦点与生成禁用；三个视口验证；真实模型配置与协议保持原实现 |
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
| A-attachments | 附件/文件 | ComposerInput | 部分实现 | 选取/拖入/粘贴/配额及异步身份代码已有；主聊天拒绝实际附件发送并保留编辑内容，真实解析未接。提示仍提到已移除模拟模式，列入后续说明修正，不恢复模拟服务。 |
| A-voice | 语音输入 | ChatComposer 录音入口 | 实现待验收 | 无 STT 服务：明确“未接入”说明+带标识演示转写，不采集音频；真实权限/设备拒绝状态待真实服务接入；e2e chat-composer.spec.ts |
| A-reading-companion | 沉浸阅读伴生 AI | reading/workspace/ReadingCompanion、ReadingComposer | 部分实现 | companion-service 已使用统一 ChatService 事件模型，支持显式模拟流式/取消/失败重试/草稿归属；并非旧同步模板。过程/追问/产物/来源完整性、滚动与会话历史、媒体视图仍需补验，见 STATUS H2。 |
| A-kb-ingest | 知识库导入→解析→索引 | 参考 `lib/knowledge-helpers.ts`（resolveKbStatus/kbHasLiveProgress/IndexVersion）、`components/knowledge/KbStatusBadge`、`KbIndexVersionsSection` | 显式模拟（前端闭环已验收） | 2026-09-11 B-H1-KB：`services/knowledge-ingest.ts` 复刻 registered→parsing→indexing→ready、进度、取消、失败重试、刷新恢复、全部就绪追加索引版本；产物为本地结构化样例并全程标注。真实文件解析/向量检索未接入，与真实服务验收分开记录；参考另有 WS/SSE 进度与 KB 级状态（target 以逐文档状态 + KB 汇总呈现），接入真实服务时按参考协议重对齐。e2e `knowledge-notebooks.spec.ts` |

## 统一事件约束（已实施部分见 chat-service.ts）

事件联合已实施为 **type 判别式联合类型**：turn-start、text（必带 delta）、reasoning（必带 delta）、process、stage、tool（必带 call/kind/name/status，状态 running/done/error/cancelled）、wait-user（必带 interaction：interactionId/intro/questions/status）、artifact（基础消费已实现）、usage、end、error。全部事件携带 sessionId/turnId；终态（end/error/取消）后拒绝一切后续事件。
**提交归属（R11）**：submitReply 结果只归属发起时的会话/轮次/交互/提交身份（submissionId 实际用于归属判定与服务侧单次消费）；事件顺序=确认→续答/收尾事件→提交返回值。
**消息投影（R12）**：`conversationProjection()` 统一正文+已确认追问交流+逐卡续写；复制、服务请求上下文、预算计算共用。
扩展快照发送时冻结；真实服务不读取、不发送模拟字段，SSE 协议未变。
待补齐：产物完整参考验收与跨业务消费、mastery新轮机制、阅读伴生的完整参考交互。ChatService类型联合比真实HTTP事件更丰富，类型存在不代表当前供应商能产生该事件；真实ask_user、工具及复杂能力通道待接，主聊天不恢复模拟。
