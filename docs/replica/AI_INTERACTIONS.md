# AI 交互映射与实施顺序（S1 结构化版）

状态词汇：`待实现` / `部分实现` / `实现待验收` / `实现待修复` / `已验收` / `真实服务未接入`。条目 id：`A-<能力>`。

2026-09-08 独立复核：A-capability（R19/R22）、A-attachments（R20/R23）存在需修复问题；A-persona 的当前会话隔离（R21）、A-artifact 的复合身份（R24）、轮级耗时（R25）待修。下表中的已有实现与历史通过不能代替这些缺陷闭环，详见 [最新复核](REVIEW_S2_S3_2026-09-08.md)。

| id | 交互 | 原版来源 | 状态 | 现状与待办 |
| --- | --- | --- | --- | --- |
| A-send | 发起、取消、恢复 | features/chat/model/protocol.ts、transport | 已验收（真实 SSE 部分见 A-real） | 统一事件服务+生命周期守卫；真实 SSE 复用 |
| A-real | 真实流式问答 | transport | 部分实现（真实服务未接入） | 真实 SSE 客户端与三协议后端已有；真实供应商验收待用户凭证 |
| A-mode | 模式切换（真实/模拟） | —（目标自有显式模拟） | 已验收 | 双 store 双仓储；e2e chat-mock 覆盖 |
| A-model | 模型选择 | ChatComposer 模型选择器 | 已验收 | 按连接分组、默认/会话级选择；真实模型管理 |
| A-ask-user | ask_user 追问卡 | AskUserOptions.tsx、use-card-submission.ts、ChatStateAdapter submitUserReply | 部分实现（实现待验收） | 同轮暂停→确认→继续；预览/单选/多选/自由文本/导航/跳过/失败重试/摘要/中断恢复已有；多题标签细节与移动长文本人工复核待做 |
| A-tools | 工具过程 | trace/TracePresentation | 实现待验收 | callId 去重、状态收尾、inert 焦点规则；对照原版逐项视觉验收待做 |
| A-extensions | 扩展选择与目录联动 | ChatComposer 上下文选择 | 部分实现 | 选择/快照/管理跳转已有；S2 输入区“添加内容”菜单（附件/角色/知识来源/会话引用）已接入同一快照冻结；书籍/笔记/题库等入口待对应业务页（S5）落地后进菜单 |
| A-capability | 业务能力选择与配置门控 | ChatComposer 能力菜单、CapabilityConfigCard | 实现待修复 | 目录对照 v1.6.5（主列表+更多能力飞出层；course_study/mastery_path 不进首页菜单）；needsConfig 三能力确认门控、切换能力使确认失效、真实模式非对话能力禁用并标注未接入；发送冻结 capability+config 进快照、重试沿用；e2e chat-composer.spec.ts |
| A-deep-solve | 深度解题 | deep_solve 相关 | 待实现 | planning→reasoning→writing（S4） |
| A-deep-question | 深度出题 | deep_question 相关 | 待实现 | ideation→generation（S4） |
| A-deep-research | 深度研究 | deep_research 相关 | 待实现 | rephrasing→decomposing→researching→reporting（S4） |
| A-visualize | 可视化 | visualize 相关 | 待实现 | analyzing→generating→reviewing（S4） |
| A-math-anim | 数学动画（Manim 路由） | visualize math_animator | 待实现 | 明确模拟标识（S4） |
| A-mastery | 精通之路问答 | MasteryQuestionCard/HandoffCard、ask-user-state | 待实现 | 阶段交接/新轮机制（区别普通 ask_user）（S4） |
| A-artifact | 产物与结果工作区 | SessionViewerPanel、SessionActivityPanel | 部分实现 | S3 切片 1：artifact 事件按 id 幂等消费+持久化恢复；右侧结果工作区（列表+markdown/svg/html/text 安全渲染+真实复制下载）+消息内入口 chip；出题/可视化/研究模拟产物已接。剩余：标签页多开/宽度可调/更多渲染器（随 S4）、引用与来源定位、与消息操作联动 |
| A-message-ops | 消息操作 | ChatMessageList | 部分实现 | 复制（统一投影）/重试/复用已有；引用定位、消息菜单待实现 |
| A-persona | 角色/persona | ChatComposer persona | 部分实现 | 演示目录（显式“载入演示数据”）+选择 chip+引用树+快照冻结已实现；会话级持久化与 /space/personas 业务页待 S5-A |
| A-attachments | 附件/文件 | ComposerInput | 实现待修复 | 选取/拖入/粘贴/校验（类型→单文件→配额）/预览/移除/4s 错误清除已实现；无解析服务：发送仅随快照携带元数据并明确“未读取文件内容”，真实模式不支持仅附件发送并有明确提示；e2e chat-composer.spec.ts |
| A-voice | 语音输入 | ChatComposer 录音入口 | 实现待验收 | 无 STT 服务：明确“未接入”说明+带标识演示转写，不采集音频；真实权限/设备拒绝状态待真实服务接入；e2e chat-composer.spec.ts |

## 统一事件约束（已实施部分见 chat-service.ts）

事件联合已实施为 **type 判别式联合类型**：turn-start、text（必带 delta）、reasoning（必带 delta）、process、stage、tool（必带 call/kind/name/status，状态 running/done/error/cancelled）、wait-user（必带 interaction：interactionId/intro/questions/status）、artifact（基础消费已实现）、usage、end、error。全部事件携带 sessionId/turnId；终态（end/error/取消）后拒绝一切后续事件。
**提交归属（R11）**：submitReply 结果只归属发起时的会话/轮次/交互/提交身份（submissionId 实际用于归属判定与服务侧单次消费）；事件顺序=确认→续答/收尾事件→提交返回值。
**消息投影（R12）**：`conversationProjection()` 统一正文+已确认追问交流+逐卡续写；复制、服务请求上下文、预算计算共用。
扩展快照发送时冻结；真实服务不读取、不发送模拟字段，SSE 协议未变。
待接入：artifact 完整工作区/更多渲染器、mastery 新轮机制、真实 ask_user 通道。artifact 基础消费方已有，复合身份待 R24 修复，不再按“只有预留类型”记录。
