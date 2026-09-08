# 当前生效的工程决策

## 当前复刻任务口径（2026-09-08）

用户现行目标为 DeepTutor v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202 全部产品前端、AI交互与原版动画复刻，目标品牌智启课源；MCP/Skills管理统一在设置。连续执行入口为 [replica/NEXT_SESSION_START.md](replica/NEXT_SESSION_START.md)，先修 [R19–R25](replica/REVIEW_S2_S3_2026-09-08.md) 后推进全部剩余工作。保留现有技术栈/真实SSE/模型管理/教案/用户数据，当前 `/`→`/chat`，教案独立入口保留。下表及旧章节中 v1.6.4、视觉只沿用教案、Dxx单阶段任务等叙述为历史范围，不能覆盖现行用户目标；基础数据保护与工程约束继续有效。

更新：2026-09-06。以用户批准的问答修复与模型管理计划增补；旧阶段叙述作为历史保留。

| 决策 | 内容 |
| --- | --- |
| 工程根 | `H:\备份xuexi\智启课源`（2026-09-06 起本仓库实际位置；旧记录中的 F:\智启课源 为迁移前路径） |
| 前端 | Next.js 16.3.4、React/ReactDOM 19.2.8、TypeScript、Tailwind 3.4.17 |
| 版本来源 | 实施时查询npm官方注册表，Next16兼容React19；具体依赖以根锁文件为准 |
| 包管理 | npm workspaces只包含apps/web；冻结旧版锁文件不属于正式工程依赖 |
| 参考基线 | 最新UI以本项目教案工作台为准；后续模型调用参考DeepTutor v1.6.4适配层，不整仓移植 |
| 当前可用功能 | 教案工作台、学习问答、模型管理；其他业务入口仍规划中 |
| 默认入口 | `/` 跳转 `/chat`（2026-09-06 用户指定并经 2026-09-07 续审确认；更早"跳转教案"的陈述已作废，仅作历史记录） |
| 草稿 | 保留旧键、版本与JSON；正式地址保持127.0.0.1:5173 |
| 依赖注入 | 正式模块通过props/Context接收服务；移除旧window注入入口 |
| 后端 | FastAPI 三协议调用、模型目录与设置、聊天 SSE；不启动数据库或 Redis |
| 旧版 | 原目录冻结，仅新增ARCHIVED.md，保留源码及资料回退 |
| 原模板 | 根Word保持原样；正式副本、manifest与派生模板独立存放 |
| Git | 初始化本地仓库和忽略规则；不自动提交、不配置远程、不推送 |

### 问答与模型管理现行决策

交互参考 DeepTutor v1.6.4，视觉沿用教案。模型按连接组织，发现仅建议 ID，不推断能力；全局默认仅面向问答，任务分配仍规划。会话显式选择优先于默认，失效不静默换供应商。参数实际值由同一目录供设置与问答使用。

连接与流式测试证据分开；测试中配置改变不写回旧验证结果。凭证只在后端进程，普通配置 JSON 不含凭证，`.local-data/` 忽略。聊天使用安全 Markdown/公式渲染；这取代此前 D04 纯文本范围。会话 IndexedDB 用版本检查、串行合并写入，刷新恢复中断状态，冲突不覆盖编辑内容。

最新检查和未验证边界见 [CHAT_MODEL_REVIEW.md](CHAT_MODEL_REVIEW.md)；模拟上游结果不等于实际供应商验收。

旧模块文档中的Vite启动方式、窗口注入接口、脚本路径已被本轮正式工程替代。原始规划仍保留，不复制修改出另一套完整历史计划；当前实施状态以本目录文档和源码为准。

框架迁移不改变用户确认的界面方向。为可维护性拆出了公共壳、表单、填充、配置、导出和弹窗；存储增加离开页面前刷新及实例隔离。

技术依据：[Next.js迁移指南](https://nextjs.org/docs/app/guides/migrating/from-vite)、[AGENTS.md官方说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。标准规则文件为AGENTS.md，小写agent.md只作指引，不修改用户全局Codex配置。

## 2026-09-05 后续开发范围调整（计划，尚未实施）

最新执行依据为 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)，包含 D01–D09 的可复制 AI 任务包。用户本次要求编写详细 Markdown，未要求本轮开始业务代码实现。

- 不接教材数据库、题库数据库、向量数据库、SQLite 或 Redis；保留仓储、检索与能力接口。浏览器 IndexedDB 和后端本地配置/任务文件是拟定的无数据库实现方式。
- 未实现模块提前展示入口和“规划中”；已实现模块的未接通子能力单独标注，不能将模块可用误写成全部能力可用。
- 学习问答优先接真实 API 模型；为保护凭证建立精简 FastAPI，不由浏览器直接调用供应商。此服务当前还没有实现。
- UI 延续现有教案工作台；组卷使用左配置、中编辑、右实时预览，A3 默认正式试卷、A4 默认课堂小练，两种纸张均可切换。
- 无题库阶段先做手动/结构化导入的本地组卷；“从题库自动选题”和“根据教材出题”继续规划中，不用示例冒充真实库。
- DOCX 上传采用支持检查、字段映射和模板版本；实时编辑预览与正式分页预览分开，正式PDF预览和下载应来自同一产物。旧教案模板、草稿及导出兼容性保留。
- 教材库、题库、RAG、教材生成教案、AgentRun、MCP与Skills的真实服务属于后续F系列任务，需用户另行指定。

参考版本校正：GitHub API已核实 `e5f2d38c393497a57fda13209be55067c1740ca7` 是 v1.6.4 的标签对象，其实际提交为 `93df3d48b70586c36b20ebf82c613a67ed20677f`。旧规划将标签对象称为提交的描述以此校正；历史正文保留，不混用本机其他版本。核验来源见完整计划第17节。

## 2026-09-06 D01 模块导航与统一状态（已实施）

依据 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 第3节执行 D01，以下决策随代码生效：

- 导航登记项由 `available:boolean` 演进为 `status: planned | local | ready`；教案工作台为 `local`，其余模块均为 `planned`。运行态（unconfigured/connecting/error 等）留给 D02 及之后的模型与导出能力，本阶段不引入。
- 新增入口：`/papers` 智能组卷、`/question-bank` 题库、`/templates` 模板中心、`/agents` Agent任务、`/mcp` MCP、`/skills` Skills；`/knowledge-bases` 名称由“知识中心”改为“教材资料库”，路径不变。以上全部为规划状态页。
- 图标、分组与规划页内容统一登记在 `services/navigation.ts` 单一来源；`WorkspaceShell` 不再维护固定图标表，避免新增菜单缺图标导致运行错误。
- 手机端（≤767px）新增页头“功能导航”抽屉，桌面侧栏增加分组标题与内部滚动；规划中模块的可访问名称统一为“模块名（规划中）”。

## 2026-09-06 D02 精简后端与接口骨架（已实施）

依据 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) D02 任务包与第5、6、11节执行，以下决策随代码生效：

- 后端位于 `apps/api`，FastAPI 应用工厂 + 生命周期 + 本机访问防护中间件；只监听 `127.0.0.1`（开发 8000，后端测试 8001），非回环 host 在配置阶段直接拒绝。
- 工具链：uv 0.12.6 管理，uv 托管 CPython 3.12.14（`apps/api/.python-version` 固定 3.12）；锁定版本 fastapi 0.141.1、uvicorn 0.52.4、pydantic 2.13.5、starlette 1.6.0、pytest 9.1.1、httpx2 2.12.0，以 `uv.lock` 为准。Python 不加入 npm workspaces。
- 接口：真实 `GET /api/v1/health`（不含配置）与 `GET /api/v1/capabilities`（10 项能力全部 `planned`）；其余 `/api/v1/*` 统一 501 `FEATURE_NOT_IMPLEMENTED`，不返回假成功。
- 错误信封 `code、message、requestId、retryable、details?` + `X-Request-Id` 头；来源检查：非回环 Host → 400 `INVALID_HOST`，Origin 存在但不在允许列表 → 403 `FORBIDDEN_ORIGIN`，无 Origin 的本机直连放行；默认允许 5173/5174 前端来源，`ZQKY_ALLOWED_ORIGINS` 可覆盖。
- 前端经 Next rewrites 同源代理 `/api/v1/*` 到 8000（`ZQKY_API_ORIGIN` 可覆盖）；Next 只代理，没有新增业务 Route Handlers。新增手写契约 `contracts/api.ts` 与适配器 `services/api-client.ts`（网络失败/网关 5xx → `SERVICE_UNAVAILABLE`，准确报“后端服务不可用”），页面默认不调用后端，教案离线可用。
- 根脚本新增 `setup:api`、`dev:api`、`test:api`；`test:e2e`/教案行为不变。测试证据：后端 18 项 pytest 通过；前端单测 29 项、e2e 12 项通过；代理转发、501、403、后端停止行为均实测。
- 本期没有接入任何数据库、Redis 或模型凭证；`apps/api/.env.example` 只含无敏感信息示例。

## 2026-09-06 D03 统一模型调用与模型设置（已实施）

依据 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 第7节与 D03 任务包执行，以下决策随代码生效：

- 供应商适配层参考 DeepTutor v1.6.4（固定提交 `93df3d48…`，Apache-2.0）的 `LLMProvider`/`LLMResponse`/`GenerationSettings`、按协议懒加载的工厂与分层能力声明设计；实现为本项目自有代码（`apps/api/app/providers/llm/`），未复制其源码。
- D03 实现 openai-chat、openai-responses、anthropic-messages 三个独立协议适配器（请求形状、响应解析、结束原因规范化为 stop/length/error/unknown、用量提取、错误映射 UPSTREAM_AUTH_FAILED/RATE_LIMITED/UPSTREAM_TIMEOUT/UPSTREAM_UNREACHABLE/UPSTREAM_ERROR）；其他协议（Gemini 原生等）保持 `UNSUPPORTED_PROTOCOL`。
- 参数能力双层校验：模型配置 `supportedParams` 声明（temperature/top_p）→ 测试请求未声明的参数返回 422 `UNSUPPORTED_PARAMETER`；协议级不支持参数在 Provider 基类拦截。能力证据三值 `verified/claimed/unknown`，测试成功后 `chat` 自动更新为 `verified`。
- 凭证采用计划 6.3 允许的“仅当前服务进程使用”方案：进程内 `SecretStore`，只写入不回显（响应仅 `hasCredential`，`credentialScope=process`），服务重启后需重新填写，绝不写入磁盘/日志/错误；磁盘加密凭证存储留作后续增强。
- 非敏感配置存 `.local-data/model-config.json`（项目根，`.gitignore` 已忽略；`ZQKY_DATA_DIR` 可覆盖）：单文件 JSON、threading 串行化、临时文件 + `os.replace` 原子写、全局 revision，PUT 支持幂等 `expectedRevision` 冲突检测（409 `REVISION_CONFLICT`），文件损坏时报 `CONFIG_CORRUPTED` 且不自动覆盖。
- Base URL 安全规则：仅 http(s)；公网地址必须 https，http 仅允许本机回环（本机模型服务）；附加请求头名称白名单校验，凭证头（Authorization/x-api-key）由适配器最后写入、不可被覆盖。
- 设置页 `/settings` 由规划页替换为真实页面（沿用教案工作台主题）：模型连接/模型配置卡片、添加与编辑表单、连接测试（明确提示“小额实际请求”）、其余设置组如实标注规划中；导航登记 settings → `ready`。
- 模型列表自动发现未实现：模型 ID 一律手动填写；`purpose` 字段预留、当前仅 `chat`。

## 2026-09-06 D04 真实学习问答（已实施）

依据 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 第4.2、7.1、7.4、11.4 节与 D04 任务包执行，以下决策随代码生效：

- 流式接口 `POST /api/v1/chat/stream` 按第 11.4 节事件协议实现（message.start / text.delta / usage / message.end / error）；流开始前失败（未存凭证、参数未声明、消息超限）返回 HTTP 错误，流开始后失败以 `error` 事件下发；usage 缺失字段前端按“未知”展示，不算零费用。
- 三协议适配器新增流式实现：openai-chat（`stream:true` + `stream_options.include_usage`，不兼容该字段的服务器用量按未知展示）、openai-responses（response.output_text.delta / completed / failed 事件）、anthropic-messages（message_start / content_block_delta / message_delta）。上游结束原因统一规范化；未知值不得伪装成 stop。
- 取消链路：前端 AbortController → fetch 中止 → 后端 StreamingResponse 任务取消 → Provider 生成器 finally 关闭 httpx client 与上游连接。断流未收到 message.end 时，前端如实标记“已停止”，保留已收内容，不自动重发。
- 对话历史存浏览器 IndexedDB（库名 `zhiqikeyuan-chat`，经 `ChatRepository` 封装，未来可换服务端存储）；不存任何 API Key。刷新后自动恢复最近会话；换模型/换会话不删除历史。
- 上下文预算可解释：按 1 token≈2 字符估算并预留输出空间，从最新消息向前保留，始终保留最后一条用户消息；空 assistant 占位不发送。
- 交互约定：发送中禁止重复发送（按钮切换为“停止”）；失败回复的“重试”会移除失败占位并重发同一条用户消息，绝不自动重试、绝不重复追加；停止的部分回复标注“已停止”并保留。
- 模型回答按纯文本（pre-wrap）渲染，不插入模型生成的任何 HTML；Markdown/公式渲染为后续增强。信息面板如实列出 RAG、附件解析、MCP、Skills 为规划中。
- 导航登记 chat → `ready`；`/chat` 由动态规划路由替换为静态页面（先例：D03 的 /settings）。

## 2026-09-06 新对话发送静默失败排查与首页调整（已实施，用户指定）

- 现象与根因：新建对话后发送有概率“无反应/无回复”。排查确认两条静默失败路径：①默认问答模型（`defaultChatProfileId`）指向的连接凭证失效（凭证只存后端进程，重启即失效的既定决策）时 `selection=null`，`submit()` 静默返回——Enter 发送毫无反馈，而旧会话若显式选过可用模型则正常，故表现为“新对话才有概率失败”；②页面刚加载 `ready=false` 时 `send()` 也静默丢弃。
- 修复原则：**不做静默模型回退**（沿用“不静默改用其他供应商”决策）；改为消除静默——`send` 在未就绪时等待初始化（memoized，不改变已就绪时的同步语义）；发送被阻止时在输入框旁即时显示原因（缺凭证/未选模型/读取中）并附“打开设置”入口，草稿保留。
- 已实测：默认模型有效时“新建对话→立即发送”压测 10/10 成功；默认模型缺凭证时 Enter 显示“当前模型缺少凭证，请到设置补充后重试。”且草稿保留。
- 首页调整：根路径 `/` 默认跳转由 `/lesson-plans` 改为 `/chat`（用户指定）；教案工作台仍从导航与品牌按钮直达。
- EMPTY_RESPONSE 增强（用户报告“模型未返回正文”后）：三个适配器识别推理输出形态（DeepSeek `reasoning_content`、Anthropic thinking、Responses 推理摘要），推理增量经 `reasoning.delta` 事件透传并在前端折叠展示；流干净结束但零正文时按结束原因给出可操作诊断（推理耗尽预算→提示增大输出上限），正文兼容分块形态；**不做静默模型回退**。

## 2026-09-07 复刻阶段：ask_user 同轮续答语义（已实施）

- 追问（ask_user）采用原版语义：当前轮生成→提问→暂停→接受回答→继续当前轮；同一 sessionId/turnId/助手消息保持关联，禁止以普通 send 另开一轮，也不重新打开已终结轮次。旧交接中"提交后以新轮次继续"的描述作废。
- `ChatService.submitReply` 为可选能力：模拟实现以挂起点保持轮次活动并在提交后同轮续写（submissionId 幂等）；真实服务显式返回 REPLY_NOT_SUPPORTED，不静默转模拟、不把追问字段发给真实后端。
- 追问卡（问题/草稿/确认答案/状态/续写正文）随会话持久化；等待与提交的运行上下文不持久化。刷新或载入历史时，未完成的等待统一标记 interrupted（与工具/消息中断恢复同一 normalizeLoaded 语义），禁止向失效旧卡提交，可显式重试原问题开启新尝试。
- 未回答题目按原版语义在提交时标记为跳过，不加"必须答完"拦截；提交失败为卡片级失败，保留草稿与选项。

## 2026-09-07 复刻阶段：聊天扩展快照与模拟边界（已实施）

- 聊天统一事件服务改为 type 判别式联合；tool 事件必须携带 callId/kind/name/status（running/done/error/cancelled），终态（end/error/取消）后拒绝一切后续事件，工具卡按 callId 去重并随会话持久化（恢复不重放）。
- 模拟扩展能力以“发送时冻结的快照（TurnExtensionSnapshot）”进入本轮：重试沿用原快照，设置修改只影响后续发送；失效的待发送选择明确提示并移除，不静默替换。快照与工具记录只存在于模拟会话数据，真实服务不读取、不向真实后端发送该字段，`/api/v1/chat/stream` 协议未变。
- 模拟边界不变：MCP 工具为明确标识的本地模拟调用，Skills 仅展示为技能上下文已加载，不访问真实模型、MCP 或外部工具；真实模式明确显示未接入，不因真实服务错误自动切换模拟。

## 2026-09-06 前端复刻首批实施

设置改为分类与锚点内容；MCP、Skills 从主导航收进设置，旧路径重定向。扩展管理为独立本地模拟目录，模型管理保留真实服务。减少动画偏好已实现。完整八阶段尚未完成，实际范围、检查与剩余工作见 docs/replica/HANDOFF.md。
