# AI 交互映射与实施顺序（S1 结构化版）

2026-09-09 用户范围覆盖：A-mode 的双模式切换及主聊天模拟执行已删除；S2–S4 下方模拟执行证据为历史记录，不代表当前可调用功能。生产 store 仅调用真实 SSE，测试脚本迁入 tests/fixtures，不进入应用依赖。推理按 AssistantActivity 自动展开/回答时折叠/用户选择优先，Markdown 数学归一化用于正文与推理。三协议 9 项 HTTP 链路验收通过，真实供应商未调用。详见 [STATUS](../STATUS.md)。

2026-09-09 指定学习问答主页外观改造：原 ChatService、store、快照与服务契约不变；本批聊天/附件/能力/追问/深链/工作区/导航/设置相关浏览器回归 **65/65** 通过，真实供应商未调用。`A-model` 新增向上弹出呈现但仍读取原分组目录；角色快捷菜单共享原目录和会话归属；上下文胶囊标明估算与未包含内容，不改变实际请求。证据见 [STATUS](../STATUS.md) 与 `chat-home.spec.ts`。

状态词汇：`待实现` / `部分实现` / `实现待验收` / `实现待修复` / `已验收` / `真实服务未接入`。条目 id：`A-<能力>`。

2026-09-08 校正：R19–R25 后续修复及 S3/S4 已有切片均已登记，不再沿用过期“待修”指令。阅读伴生 AI 尚未复用主聊天流程，见 [本次审查](../reviews/READING_REVIEW_2026-09-08.md)。实现不等于完整验收，当前范围见 [STATUS](../STATUS.md)。

| id | 交互 | 原版来源 | 状态 | 现状与待办 |
| --- | --- | --- | --- | --- |
| A-send | 发起、取消、恢复 | features/chat/model/protocol.ts、transport | 已验收（真实 SSE 部分见 A-real） | 统一事件服务+生命周期守卫；真实 SSE 复用 |
| A-real | 真实流式问答 | transport | 部分实现 | 真实 SSE 与三协议后端已接；本轮供应商未验证（与新能力未接入不同），不可标全部真实验证完成。 |
| A-mode | 原真实/模拟模式切换 | 目标自有，2026-09-09 用户要求删除 | 已移除 | 主聊天单一真实 store；无切换/失败布防/免密伪模型；测试替身仅 tests/fixtures |
| A-model | 模型选择 | 指定主页模型弹层 + 原 ChatComposer 模型选择器 | 已验收 | 2026-09-09：输入区向上弹层、实际模型品牌图标、搜索/连接分组、默认/会话级选择、管理跳转、Escape/选择焦点与生成禁用；三个视口验证；真实模型配置与协议保持原实现 |
| A-ask-user | ask_user 追问卡 | AskUserOptions.tsx、use-card-submission.ts、ChatStateAdapter submitUserReply | 部分实现（实现待验收） | 同轮暂停→确认→继续；预览/单选/多选/自由文本/导航/跳过/失败重试/摘要/中断恢复已有；多题标签细节与移动长文本人工复核待做 |
| A-tools | 工具过程 | trace/TracePresentation | 实现待验收 | callId 去重、状态收尾、inert 焦点规则；对照原版逐项视觉验收待做 |
| A-extensions | 扩展选择与目录联动 | ChatComposer 上下文选择 | 部分实现 | 选择/快照/管理跳转已有；S2 输入区“添加内容”菜单（附件/角色/知识来源/会话引用）已接入同一快照冻结；书籍/笔记/题库等入口待对应业务页（S5）落地后进菜单 |
| A-capability | 业务能力选择与配置门控 | ChatComposer 能力菜单、CapabilityConfigCard | 实现待验收 | 配置确认/切换失效/可用性/冻结快照已有；R19/R22 后续修复和正式回归存在。S7 参考视觉与完整状态验收待做。 |
| A-deep-solve | 深度解题 | deep_solve 相关 | 实现待验收 | S4 planning→reasoning→writing 模拟及结构化答案已有；参考配置、错误/取消和跨页验收待完。 |
| A-deep-question | 深度出题 | deep_question 相关 | 实现待验收 | S4 ideation→generation、题目作答与题库保存已有模拟闭环；完整参考状态待验收。 |
| A-deep-research | 深度研究 | deep_research 相关 | 实现待验收 | S4 四阶段与研究报告模拟已有，可保存笔记；实际外部研究未接入，参考配置及失败恢复待逐项核对。 |
| A-visualize | 可视化 | visualize 相关 | 实现待验收 | S4 三阶段及 SVG/HTML/Chart/Mermaid 模拟已有；不能将样例渲染等同全配置验收。 |
| A-math-anim | 数学动画（Manim 路由） | visualize math_animator | 实现待验收 | 本地显式模拟产物分支已有；Manim 真实渲染未接入，参考完整子阶段与结果行为待核对。 |
| A-mastery | 精通之路问答 | MasteryQuestionCard/HandoffCard、ask-user-state | 待实现 | 阶段交接/新轮机制（区别普通 ask_user）（S4） |
| A-artifact | 产物与结果工作区 | SessionViewerPanel、SessionActivityPanel | 实现待验收 | 已有复合身份、多标签、宽度调整、Markdown/SVG/HTML/Chart/Mermaid/题目等呈现及保存操作；参考来源定位和所有消息/跨页联动仍需逐项验收。 |
| A-message-ops | 消息操作 | ChatMessageList | 实现待验收 | 复制、引用、消息菜单与结果工作区切片已有；完整对照验收和全业务联动待补，复用统一投影。 |
| A-persona | 角色/persona | ChatComposer persona | 实现待验收 | /space/personas 与聊天共用目录，选择与会话归属已有回归；后续跨业务输入区仍需共享同源目录。 |
| A-attachments | 附件/文件 | ComposerInput | 实现待验收 | 选取/拖入/粘贴/配额/异步身份及提交接纳清理已有，R20/R23 已有正式回归；真实内容解析未接入，解析前端状态仍须按参考补齐。 |
| A-voice | 语音输入 | ChatComposer 录音入口 | 实现待验收 | 无 STT 服务：明确“未接入”说明+带标识演示转写，不采集音频；真实权限/设备拒绝状态待真实服务接入；e2e chat-composer.spec.ts |
| A-reading-companion | 沉浸阅读伴生 AI | reading/workspace/ReadingCompanion、ReadingComposer | 部分实现 | 当前同步模板聊天；须复用统一服务/消息输入、流式/取消/失败/重试/追问/产物、草稿与引用归属，见 R32 |

## 统一事件约束（已实施部分见 chat-service.ts）

事件联合已实施为 **type 判别式联合类型**：turn-start、text（必带 delta）、reasoning（必带 delta）、process、stage、tool（必带 call/kind/name/status，状态 running/done/error/cancelled）、wait-user（必带 interaction：interactionId/intro/questions/status）、artifact（基础消费已实现）、usage、end、error。全部事件携带 sessionId/turnId；终态（end/error/取消）后拒绝一切后续事件。
**提交归属（R11）**：submitReply 结果只归属发起时的会话/轮次/交互/提交身份（submissionId 实际用于归属判定与服务侧单次消费）；事件顺序=确认→续答/收尾事件→提交返回值。
**消息投影（R12）**：`conversationProjection()` 统一正文+已确认追问交流+逐卡续写；复制、服务请求上下文、预算计算共用。
扩展快照发送时冻结；真实服务不读取、不发送模拟字段，SSE 协议未变。
待补齐：产物完整参考验收与跨业务消费、mastery 新轮机制、阅读伴生服务复用。真实 ask_user 与新复杂能力通道未接入；R24 复合身份已有后续修复记录，不再保留过期“待修”指令。
