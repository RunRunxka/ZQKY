# 接口与模块边界

更新：2026-10-03。本文维护现行接口契约；进度、代码审查缺陷与验收限制只维护在 [CURRENT_STATUS](CURRENT_STATUS.md)。前端 TypeScript 服务与真实 HTTP 接口分别列明。当前建设以 2026-09-29 起的教材 RAG 与教学闭环为主，接口声明不代表已通过所有业务验收。

**阅读顺序：** 本文按功能与交付批次保留契约来源。同一路径、字段或分期限制出现多次时，以后续章节明确的变更为准：RAG v2 及 RAG-QUALITY 取代旧四科 v1；B2 取代 B1 的施测占位；B3 取代 B2 的成绩指针仅空限制。B0–B3 的稳定契约继续有效，实现偏差与待修项见 CURRENT_STATUS。历史阶段编号和角色分工不构成当前执行、提交或部署授权。

### contract-v1 已落地（2026-09-13）

模型 contract-v1 于 2026-09-13 落地；以下字段与协议继续用于既有模型配置的维护和兼容。
实现文件：`apps/api/app/providers/llm/registry.py`（38 条单一真值）、`.../factory.py`（按 backend 分派）、
`app/services/model_config_service.py`（跨 .env/JSON 补偿）、`app/services/model_auth.py`（认证状态机）。
历史冻结材料曾保存在 `_work/model-providers-v1/contract-v1.md`（本机证据，不随 Git）；现行接口可依据本节、源码与版本记录核对，不以该本机文件作为唯一交接入口。

| 方法与路径 | 状态 | 说明 |
| --- | --- | --- |
| GET `/api/v1/model-providers` | 已实现 | 供应商目录（36 现行 + 2 legacy）；返回 providerId/label/aliases/mode/authMode/apiFormats/defaultApiBase/baseUrlsByFormat/thinkingStyle/requiresKey。**不下发原始 backend**（D15） |
| GET `/api/v1/model-connections/{id}/auth` | 已实现 | 认证四态 `disconnected/authorizing/connected/error`，附 operationId/authorizeUrl/expiresIn/errorCode；不回显令牌 |
| POST `/api/v1/model-connections/{id}/auth/start` | 已实现 | 仅 openai_codex 发起 PKCE 授权；缺自有 OAuth 应用凭据返回 `ok:false` + `OAUTH_APP_NOT_CONFIGURED`，**不伪造授权地址**；API Key 型返回 `UNSUPPORTED_OPERATION` |
| POST `/api/v1/model-connections/{id}/auth/cancel` | 已实现 | 取消进行中的授权；取消后迟到回调不复活（operationId + cancelled 判定） |
| POST `/api/v1/model-connections/{id}/auth/logout` | 已实现 | 断开并清理托管凭证（Codex/Copilot 令牌）；不注销第三方 CLI 会话 |

连接/模型新增字段：`providerId`、`apiFormat`（`auto`/`openai_chat`/`openai_responses`/`anthropic`）、
`apiVersion`（Azure，仅 `preview` 实际转发）；请求可带 `credentialAction: keep|replace|clear`（R-08 显式清除）；
模型新增 `reasoningEnabled`（三态）与 `reasoningEffort`（`none|minimal|low|medium|high|xhigh|max`），
响应另带只读派生 `reasoningStyle`（不落库）。连接响应新增可调用性字段
`hasManagedCredential`、`callable`、`callableReason`：本机免 Key 服务（ollama 等）为 `callable:true`，
缺凭证云服务为 `false` 并给出原因（MR-02）。

**协议分派（MR-01）**：openai_compat 供应商选择 `openai_responses` 时创建 Responses 适配器；
无 `providerId` 的旧 `openai-responses` 连接也保持 Responses，不被降级为 Chat。

迁移（D1/D8）：无 `providerId` 的旧 v1 连接按 `protocol` 映射为 `custom` + 对应 `apiFormat`，
不猜供应商、不改 baseUrl、保留 id/revision/默认引用；读取 v1 不改写文件，首次写入前备份为
`model-config.v1.backup.json`（备份失败返回 `CONFIG_BACKUP_FAILED` 且不写入，MR-06）。
无 `providerId` 的调用方请求字节保持不变。

发现（D12）：响应新增 `source`：`upstream`（上游实时）| `manual`（该供应商无列表接口，需手工添加）|
`catalog:<name>`（内置回退目录，非实时）。认证/网络失败不再吞成空列表。

新增错误码：`UNSUPPORTED_PROVIDER`、`UNSUPPORTED_API_FORMAT`、`UNSUPPORTED_OPERATION`、
`AUTH_REQUIRED`、`AUTH_EXPIRED`、`OAUTH_APP_NOT_CONFIGURED`、`AUTH_PENDING`、`AUTH_CANCELLED`、
`CONFIG_BACKUP_FAILED`（迁移前备份失败，写入被取消，MR-06）。

**跨存储一致性（R-01）**：连接的更新/删除在仓储同一临界区内完成 revision 校验、文档变更与
凭证写入（`ModelConfigRepository.run_atomic`）；配置落盘失败按快照回滚凭证，删除时凭证清理失败则整体不删，
可安全重试。修复及独立验收候选统一见 [CURRENT_STATUS 问题台账](CURRENT_STATUS.md)，本文件只维护当前接口语义。

## 后端凭证文件

- 正式 FastAPI 在应用启动生命周期读取 `apps/api/.env`；仅凭证项使用此文件，不将其读入前端。导入 `create_app` 不读取用户凭证；测试注入临时目录和 SecretStore。
- 设置页原创建/编辑连接 API 不变，非空 `apiKey` 写入 `.env` 的 `ZQKY_API_KEY_<连接ID>`；空值仍表示保持原凭证。每个连接独立映射，模型共用所属连接的 Key。写入采用临时文件、flush/fsync、原子替换，保留其他行；删除连接会移除对应文件项。
- 可手动编辑该变量（原样字符串、单引号或 JSON 双引号字符串均支持；不进行 shell 展开或变量插值），然后重启 API。进程环境变量在启动时覆盖同名文件项；Windows 环境变量名大小写不影响小写连接 ID 匹配。
- 连接响应仍不回显密钥，新增非敏感 `credentialEnvName`，`credentialScope` 为 `env-file`（正式持久化存储）或 `process`（注入的内存存储）。`.env`、临时 `.env.*.tmp` 均由既有 `.gitignore` 排除；仅无密钥 `.env.example` 入库。
- 文件读写失败返回 `CREDENTIAL_STORAGE_ERROR`，不回显凭证/底层异常。更新先校验 revision 与字段，凭证写失败不提交本次连接配置变更。跨文件补偿按 contract-v1 实现（R-01）：更新在同一临界区快照凭证，配置保存失败则回滚；删除在配置落盘前清理凭证，清理失败整体不删除，配置落盘失败恢复凭证；`credentialAction:"clear"` 提供独立清除动作（R-08）。相关回归见 `apps/api/tests/test_model_contract_v1_api.py` 与 `apps/api/tests/test_review_regressions.py`。凭证与模型配置沿用文件存储，不另建凭证数据库；教学业务使用下文的四库结构，全部由同一 FastAPI 后端提供服务。
- 主聊天仅实例化真实服务、真实 IndexedDB 会话库；移除模拟生成与免密伪模型。SSE 事件名与三协议适配保持原契约。

## 模型目录与会话约定

- `GET /api/v1/model-catalog`：原子读取 `{revision, defaultChatProfileId, connections, profiles}`。连接只返回 `hasCredential`；模型包含 `params` 和关联连接可用状态。contract-v1 后连接另返回 `providerId/providerLabel/apiFormat/apiVersion/baseUrl/resolvedBaseUrl`，模型另返回 `reasoningEnabled/reasoningEffort/reasoningStyle`。
- `GET /api/v1/model-connections/{id}/models`：后端使用已保存连接和服务端凭证发现列表，返回 `{models:[{id}], source}`。`source` 取值 `upstream`/`manual`/`catalog:<name>`；只读、去重，不写入模型或推断能力。区分认证、超时、接口不支持及格式错误；空数组为成功但无可选项，**不吞掉认证/网络失败**。
- `PUT /api/v1/model-defaults`：`{modelProfileId:string|null, expectedRevision:number}`，返回更新目录；版本过期为 409 `REVISION_CONFLICT`。
- 模型创建/修改新增 `params`，只接受 `supportedParams` 已声明且数值有效的参数；上下文/输出上限修改接受 null 清空。人工提交 verified 会降为 claimed。
- 既有连接/模型 PUT 保留 `expectedRevision`，DELETE 新增可选同名 query 参数；新前端删除携带版本。旧调用方可继续使用原接口。新增记录为追加，不覆盖已有模型，同连接相同 modelId 拒绝重复。
- `POST /api/v1/model-profiles/{id}/test` 新增 `stream:boolean`；流式结果额外包含 `stream:{chunks,firstTextMs,lastTextMs}`。普通/流式证据分别写入 chat/stream；版本变更后旧测试不覆盖新配置。该测试端点返回最终测试报告，不是聊天 SSE。
- 聊天使用 `POST /api/v1/chat/stream`，已保存参数作为默认值。上游连接建立后 start，随后 text/reasoning/usage/end；未正常终止、空回答或协议失败为脱敏错误。主动停止逐层关闭资源。
- IndexedDB 会话增加 `schemaVersion:1`、revision、draft、modelProfileId；消息记录 modelProfileId、modelLabel、replyToId、superseded。旧记录读取补默认值。保存/删除在同一事务检查预期 revision，事务提交才返回成功。

模型 JSON 配置及聊天历史不存密钥；凭证仅在服务端 SecretStore 和忽略的 .env 文件。历史实现依据见 [review 记录](archive/History.md#source-4)。

## 教案与公共壳 TypeScript 接口

以下是前端TypeScript接口，不是已部署HTTP服务。

| 接口 | 用途 |
| --- | --- |
| `LessonPlanWorkspace({services?,initialLessonPlanId?,initialRevisionId?,initialAnalysisRunId?,initialRouteError?})` | 主工程嵌入教案编辑器 |
| `LessonPlanServices.fillProvider` | 可替换要求解析策略 |
| `LessonPlanServices.repository` | 可替换草稿存储 |
| `LessonPlanServices.onChange` | 持久化成功后的变化通知 |
| `FillProvider.parse(input, signal?)` | 返回Promise，内容为patch、warnings、source |
| `DraftRepository.load()` | 同步或异步返回DraftEnvelope或null |
| `DraftRepository.save(envelope)` | 同步或异步保存，失败抛出/拒绝 |
| `WorkspaceShell.beforeNavigate()` | 路由切换前等待模块保存，失败保持当前页 |

教案正文v1/后台外层v2类型在公共contracts/lesson-plans.ts，模块model/types.ts兼容re-export；跨模块NavigationItem在公共contracts。原 `window.__ZQKY_HOST__` 与导航CustomEvent不作为正式集成接口；导航由公共壳统一调用Next路由。

`DraftEnvelope={schemaVersion:1,revision:number,updatedAt:带时区ISO8601字符串,data:LessonPlanData}`。新本地稿通常写UTC；显式导入保留合法原时区与字符串拼写。字段和JSON格式与旧版兼容。传入自定义服务时保持引用稳定；服务端repository须自行绑定文档ID、会话和冲突语义，不能把本地revision直接当成跨用户授权依据。

默认本地正文继续使用规则填充与旧草稿键；教师显式打开/创建后台教案后经FastAPI保存。可选旧 `HttpFillProvider` 已保留，真实固定学情建议走下文B5任务接口，不把旧provider当作后台实现。

## 后端已实现 HTTP 接口

FastAPI 服务位于 apps/api，仅监听 127.0.0.1:8000；浏览器经 Next 同源代理访问 `/api/v1/*`（apps/web/next.config.ts rewrites，目标可用 `ZQKY_API_ORIGIN` 覆盖）。启动与测试见 apps/api/README.md，根脚本 `npm run setup:api / dev:api / test:api`。

| 方法与路径 | 状态 | 说明 |
| --- | --- | --- |
| GET `/api/v1/health` | 已实现 | 返回 `status/service/apiVersion/time`，不含配置内容 |
| GET `/api/v1/capabilities` | 已实现 | 能力清单；`model_settings`、`chat`、`textbook_repository`、`question_bank` 为 `ready`，RAG 按运行时就绪状态为 `ready` / `unavailable`；教案真实AI按服务与lesson_generation执行器实际装配为ready/unavailable；组卷、模板、Agent/MCP/Skills为planned。清单不是全部教学闭环接口的索引 |
| GET/POST `/api/v1/model-connections` | 已实现 | 连接列表/创建；非空 `apiKey` 经 SecretStore 持久化到 .env，响应只返回凭证状态和变量名，不回显 Key |
| GET `/api/v1/model-catalog` | 已实现 | 一次读取带 revision 的连接/模型/默认模型目录 |
| GET `/api/v1/model-connections/{id}/models` | 已实现 | 使用服务端凭证发现上游模型；不修改目录 |
| PUT `/api/v1/model-defaults` | 已实现 | 更新默认模型，expectedRevision 冲突返回409 |
| PUT/DELETE `/api/v1/model-connections/{id}` | 已实现（D03） | 更新（支持 `expectedRevision`，冲突 409）；被模型配置引用时删除返回 409 `CONFLICT` |
| GET/POST `/api/v1/model-profiles` | 已实现（D03） | 模型配置（模型 ID、上下文/输出上限、`supportedParams`、能力证据）列表/创建 |
| PUT/DELETE `/api/v1/model-profiles/{id}` | 已实现（D03） | 更新/删除；能力证据取值 `verified/claimed/unknown` |
| POST `/api/v1/model-profiles/{id}/test` | 已实现（D03） | 真实小额上游请求；无论上游成败都返回 200 `ok:true/false`，成功后 `chat` 证据更新为 `verified` |
| POST `/api/v1/chat/stream` | 已实现（D04） | 规范化 SSE 流式对话（见下方事件协议）；客户端断开时取消上游连接 |
| GET/POST `/api/v1/workflow-jobs/...` | 已实现（TEACHING-LOOP B0） | 公共任务查询/取消/重试；见下「教学闭环 B0 公共契约」，域未装配返回 503 |
| 教材、索引、RAG、题库、知识点、名单、原卷、施测与成绩 | 已建立真实路由 | 具体路径和语义见本文对应章节；依赖未就绪不能返回假成功 |
| 未登记的 `/api/v1/*` | 通配占位 | GET/POST/PUT/DELETE/PATCH 返回501 `FEATURE_NOT_IMPLEMENTED`，不能假成功 |

错误信封统一为 `code、message、requestId、retryable、details?`（details 只含脱敏展示内容），并附 `X-Request-Id` 头。约定：非允许 Origin → 403 `FORBIDDEN_ORIGIN`；非回环 Host → 400 `INVALID_HOST`；非 `/api/v1/*` 的未知路径 → 404 `NOT_FOUND`；参数错误 → 422 `INVALID_REQUEST`。后端停止时 Next 代理返回500纯文本，前端 `services/api-client.ts` 转为 `ApiError('SERVICE_UNAVAILABLE')`。本次与历史验收范围以 STATUS 为准。

### POST /api/v1/chat/stream 事件协议（D04 已实现）

请求体：`{requestId, modelProfileId, messages: [{role, content}], maxOutputTokens?, params?}`。流开始前的失败（模型不存在 404、未保存凭证 400 `MODEL_NOT_CONFIGURED`、参数未声明 422 `UNSUPPORTED_PARAMETER`、总长超限 413 `CONTEXT_TOO_LARGE`）返回 HTTP 错误信封；流开始后按 `text/event-stream` 逐条下发：

| 事件 | data 字段 |
| --- | --- |
| `message.start` | `requestId, messageId, modelProfileId` |
| `text.delta` | `messageId, text` |
| `reasoning.delta` | `messageId, text`（推理模型的思考过程增量，如 DeepSeek `reasoning_content`、Anthropic thinking；前端折叠展示，不算正文） |
| `usage` | `messageId, inputTokens?, outputTokens?`（缺失字段按未知展示，不算零费用） |
| `message.end` | `messageId, finishReason`（stop / length / unknown） |
| `error` | `requestId, code, message, retryable` |

前端以 `fetch + ReadableStream` 消费（POST 不支持 EventSource），`TextDecoder(stream:true)` 处理 UTF-8 跨块；客户端 AbortController 停止生成，取消传播至上游连接。已实测经 Next 代理 SSE 逐段到达（间隔与上游一致），代理未缓冲。

`EMPTY_RESPONSE`（流干净结束但零正文）会给出可操作诊断：`finishReason=length` 且存在推理内容 → “模型已产生推理内容，但输出预算在生成正文前耗尽（当前输出上限 N tokens）…请增大输出上限”；仅推理内容 → “模型仅返回推理内容，未输出正文”；否则为通用文案。正文兼容字符串与 `[{type:'text',text:'…'}]` 分块两种形态。

已锁定的错误码（随任务扩充）：MODEL_NOT_CONFIGURED、UNSUPPORTED_PROTOCOL、UNSUPPORTED_PROVIDER、UNSUPPORTED_API_FORMAT、UNSUPPORTED_OPERATION、AUTH_REQUIRED、AUTH_EXPIRED、AUTH_PENDING、AUTH_CANCELLED、OAUTH_APP_NOT_CONFIGURED、UPSTREAM_AUTH_FAILED、RATE_LIMITED、CONTEXT_TOO_LARGE、UPSTREAM_TIMEOUT、FEATURE_NOT_IMPLEMENTED、TEMPLATE_UNSUPPORTED、RENDER_FAILED、REVISION_CONFLICT、SERVICE_UNAVAILABLE、REQUEST_FAILED、INVALID_REQUEST、INVALID_HOST、FORBIDDEN_ORIGIN、NOT_FOUND、METHOD_NOT_ALLOWED、EMPTY_RESPONSE、STREAM_INTERRUPTED。

## 后续 HTTP 草案（未实现，不作当前调用契约）

下表只列当前尚未实现的 HTTP 草案，历史 D 阶段编号仅供追溯；实际任务以 CURRENT_STATUS 为准。未登记的路径由通配占位返回 501，不代表具体业务接口已实现。教材、题库、RAG 和教学闭环已实现部分见后文，不属于本表。

| 方法和路径 | 用途 | 实施阶段 |
| --- | --- | --- |
| POST `/api/v1/templates/inspect` | DOCX 上传检查与临时上传 ID | D05–D07 |
| POST/GET `/api/v1/exports`、cancel、artifacts | 渲染任务与受控下载 | D07 |
| POST `/api/v1/lesson-plans/fill` | 生成填充建议 | 随 D08 评估 |
| Agent/MCP/Skills 执行相关 | 仅契约规划 | 历史 F 系列；当前未排期 |

填充类接口实施时沿用既定约束：同源会话、JSON 请求、30 秒默认超时，校验 patch 与 warnings，不在错误后回退规则实现。

## 后端接入前置条件

后续多用户/任务服务接入前，先确定用户和文档ID、鉴权、版本冲突、任务状态、数据保留及错误规范。FastAPI 已有接口由服务端声明；当前前端契约（`apps/web/src/contracts/api.ts`）为手写对齐，未宣称由 OpenAPI 生成。health、capabilities、模型管理和聊天为实际实现；其他功能以实际路由登记和能力状态为准。

学情报告和练习闭环现行接口见下文B4；后台教案和固定学情调整建议的候选接口见下文B5，独立验收与阶段门禁只看 CURRENT_STATUS。[教学闭环设计](design/teaching-loop-v1/README.md)与原项目规划区分现行契约和历史参考。模型密钥与数据库连接仅放服务端，浏览器不接收供应商凭证。

## 历史本地教材 RAG v1（已由 RAG v2 替代）

本节保留旧四科快照契约的来源，**不作当前调用契约**。生产 `/rag/*` 已由下文 RAG-REBUILD v1.0 的 v2 协议取代；请求使用 `scope`，不再使用本节的 `subject` 或旧固定索引范围。

所有接口位于现有 FastAPI，沿用回环 Host/Origin 限制和统一错误信封，无第二套业务后端。

| 接口 | 请求/结果 |
| --- | --- |
| GET `/api/v1/rag/status` | `available/detail/humanQuality/localOnly/limits`；就绪不表示质量通过 |
| POST `/api/v1/rag/stream` | `{requestId, sessionId, turnId, question, subject?, afterEventId?}`；题文 1–4000 字符，subject 仅四科或空 |
| POST `/api/v1/rag/reply` | `{sessionId, turnId, interactionId, submissionId, answers}`；答项含 questionId/labels/freeText/skipped |
| POST `/api/v1/rag/cancel` | `{sessionId, turnId}`；显式取消，迟到结果丢弃 |

`subject` 为空时检索空间是**四科全部册**（本机快照 6,745/11,608 个正文块），不是整个索引；
索引内其他学科的册不属于产品范围，不会被作为教材原文发布。显式传 subject 时收窄到该科册。
索引与冻结评测分组不改，范围选择只发生在产品入口。

SSE 使用单调递增 `id`：`message.start` → `rag.result` / `text.delta` → `wait-user`，提交后 `reply.accepted`，
再产生结果或 `message.end`；任何阶段失败发 `error`。每个事件携带 requestId/sessionId/turnId/messageId。
`rag.result.result` 包括 `status/evidence/citations/explanations/uncertain_reason`，
原文模式另带 `answerMode="textbook_excerpt"`。引用包含相对 file、book/path、源字节 SHA、半开字符区间、行号、原文。
其 `ok` 仅表示本轮可展示材料，**不表示已完整解题或人工教学质量通过**；`partial` 只展示部分原文；
`uncertain/no_evidence` 不带诊断候选。核验技术失败是明确错误，不冒充证据不足。

相同 turnId 不允许替换题目/学科；跨 session 禁止复用。断线只断传输，`afterEventId` 重放已产生事件；
后端重启或过期返回 410 `RAG_TURN_EXPIRED`。重复 submissionId 必须保持载荷相同，重复确认不再次推理。
空/跳过回答结束本轮；补充与原题合计 >4000 字符会拒绝，卡片仍可修改。队列 4、并发 1、每次 180 秒、
最多 64 个内存轮次、TTL 600 秒、最多 3 次定位。取消/超时不提前释放仍在推理的工作线程。

宿主只发布经核对的教材原文，不发布未验证的自由推导或教材外补充。生成和查询模型强制 local-only、固定 digest、
禁用环境代理和重定向。结果缓存（含拒答）仅在进程内，容量 64、有效期 600 秒，取用重验源 SHA；
宿主清理器每 15 秒清理过期内容。业务题文不写后端磁盘或日志，调用台账仅含计数/身份/成本等元数据。

---

## RAG-REBUILD v1.0 接口（2026-09-28）

本轮把教材 RAG 从「固定四科 npy 快照」重建为「SQLite 教材目录 + Qdrant 向量库 + 严格任教范围」。
**`/api/v1/rag/*` 是破坏性升级**：请求与结果结构升到 v2，旧四科的 `subject` 字段被 `scope` 取代。
旧 `rag_engine`（`app/services/rag_engine/**`）与 `.local-data/rag` 资产保留在仓库里但**不再是生产路径**，
回滚方式为 revert 对应实现提交。逐项对照见 [RAG-REBUILD v1.0 历史批次证据](archive/pre-20260929/qa/RAG-REBUILD-v1/README.md)。

### 教材目录与导入

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/textbook-taxonomy` | 学段/年级/学科/版本字典（含中文标签）；页面显示一律取自这里 |
| GET/POST `/api/v1/textbook-libraries` | 逻辑库列表（`kind/gradeId/subjectId/editionId/includeDeleted`）与创建 |
| GET/PATCH/DELETE `/api/v1/textbook-libraries/{id}` | 库详情（含书册）、改名/改年级/改版本（`expectedRevision`）、停用 |
| POST `/api/v1/textbook-imports` | multipart：`file` + 可选 `metadataJson`（`{metadata, targetDocumentId?, expectedCurrentRevisionId?, confirmMetadata?}`） |
| GET/PATCH `/api/v1/textbook-imports/{id}`、GET `/api/v1/textbook-imports` | 草稿详情（含解析预览与警告）与列表；PATCH 确认/修改分类（`expectedRevision`） |
| POST `/api/v1/textbook-imports/{id}/commit` | 提交入库任务；返回 `JobView`（`submissionId` 幂等，`libraryIds` 必填） |
| GET `/api/v1/textbook-jobs`、GET `/api/v1/textbook-jobs/{id}` | 任务列表与进度（阶段/已入库教材与块数/错误原因/是否可重试） |
| POST `/api/v1/textbook-jobs/{id}/cancel`、`/retry` | 协作式取消；重试按当前状态创建合法新任务 |
| GET `/api/v1/textbooks`、GET/PATCH/DELETE `/api/v1/textbooks/{id}` | 书册列表/详情/改分类（新建元数据修订）/逻辑删除 |
| GET `/api/v1/textbook-revisions/{id}/source` | 受控原文与定位（`charStart`/`charEnd`；散列与区间逐次核验） |
| GET/PUT `/api/v1/teaching-settings`、POST `/api/v1/teaching-settings/scope-check` | 任教范围（年级+学科+版本+已确认书册）与范围可用性预检 |

### Embedding 与索引代

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/embedding-models` | 本机 Ollama 已安装模型；标注是否为 Embedding 模型（聊天模型不会被误认） |
| POST `/api/v1/embedding-probes` | 真实嵌入能力检测：维度、模型身份 digest 前后一致、有限且非零 |
| GET/POST `/api/v1/embedding-profiles` | 已登记配置与新建（编辑影响向量的字段=新配置，不原地改写） |
| GET `/api/v1/textbook-index/status` | 唯一索引权威：当前代、当前模型与维度、重建任务、Qdrant 可用性、范围是否就绪 |
| POST `/api/v1/textbook-index/rebuilds` | 新建重建任务（`submissionId` 幂等；在途入库时返回 409 `INDEX_MUTATION_BUSY`） |

### 教材定位与详解（v2）

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/rag/status` | 分别报告 `retrieval` / `summarization` / `sourceAccess` / `scope` / `generation` / `humanQuality`；不再用单一 `localOnly`。`retrieval.available` / `summarization.available` 包含**对上游可达性的短超时真实探测**（Embedding 与概括分别探测），不可达时 `available=false` 并给出 `reason`；`scope.ready` 只表示任教范围是否就绪，与上游健康无关 |
| POST `/api/v1/rag/stream` | `{requestId, sessionId, turnId, question, scope:{kind:"selection",selection}|{kind:"frozen",snapshot}, afterEventId}` |
| POST `/api/v1/rag/reply` | 澄清提交：`{requestId, sessionId, turnId, interactionId, submissionId, answers}`；同键同载荷幂等，不同载荷 409 |
| POST `/api/v1/rag/cancel` | `{sessionId, turnId}`；显式取消，迟到结果丢弃 |
| POST `/api/v1/rag/explain/stream` | 用**当前聊天所选模型**详解：`RagExplainRequest`；普通聊天 SSE（无事件游标），断开即关闭上游 |

`scope` 快照在定位时由服务端冻结（`scopeSnapshot`），客户端只回传、不构造判定；每次使用前服务端重新核验归属、
修订、分类、删除与索引代并重算 `scopeHash`，不符即 409 `RAG_SCOPE_CHANGED`。检索固定为
向量 50 + BM25 50 + RRF(k=60)，证据按完整区间选择（≤20 条、≤40,000 字符）。
**索引范围口径**：正文与习题区的块**都写入向量库**（payload 带 `region`），检索时用过滤器限定
`region="body"`——即「只检索正文」，而不是「只索引正文」。
详解不要求 Qdrant 在线、不要求旧 Embedding 模型在场、不复用定位缓存。

新增/明确错误码：`RAG_SCOPE_EMPTY`(422)、`RAG_SCOPE_CHANGED`(409)、`INDEX_NOT_READY`(409)、
`INDEX_REBUILD_IN_PROGRESS`(409)、`INDEX_MUTATION_BUSY`(409)、`EMBEDDING_MODEL_CHANGED`(409)、
`EMBEDDING_UNAVAILABLE`(503)、`QDRANT_UNAVAILABLE`(503)、`RAG_SUMMARY_UNAVAILABLE`(503)、
`RAG_EVIDENCE_UNAVAILABLE`(409)、`RAG_TURN_EXPIRED`(410)、`CONTEXT_TOO_LARGE`(413)、
`DOCUMENT_NEEDS_OCR`(422)、`DOCUMENT_TOO_LARGE`(413)、`LEASE_LOST`(409)、`REVISION_CONFLICT`(409)、
`IDEMPOTENCY_CONFLICT`(409)。

### 独立题库（不进入教材向量库）

| 方法与路径 | 说明 |
| --- | --- |
| POST/GET `/api/v1/question-imports`、GET `/api/v1/question-imports/{id}` | 试题文件导入（multipart）、批次列表与详情（含草稿与**未归属原文块**） |
| PATCH `/api/v1/question-drafts/{id}` | 校对编辑（`expectedRevision`）；编辑已校对草稿会回到 `needs_review` |
| POST `/api/v1/question-imports/{id}/split`（`?draftId=`）、`/merge` | 拆分与合并草稿 |
| POST `/api/v1/question-imports/{id}/organize` | 用户主动 AI 整理；返回 `suggestions`（仅供参考）与逐批 `failures` |
| POST `/api/v1/question-suggestions/{id}/apply` | 应用/忽略建议；`expectedDraftRevision` 不符 409 `DRAFT_REVISION_CONFLICT` |
| POST `/api/v1/question-imports/{id}/confirm` | 幂等确认入库（`submissionId`）；`HTTP 200 + failures` 表示整体不确认 |
| GET `/api/v1/questions`、GET/PATCH/DELETE `/api/v1/questions/{id}` | 题目筛选/分页、新修订编辑（乐观锁）、归档 |

### 运行与备份命令

```text
npm run rag:db:start / rag:db:stop / rag:db:status     # 正式 Qdrant（named volume）
npm run rag:db:test:start / rag:db:test:stop          # 验收 Qdrant（独立 project 与 volume，端口 16333）
npm run rag:migrate                                   # 迁移原始教材进正式目录与索引（--dry-run 只识别）
npm run rag:verify                                    # 真实检索验收（无替身）
npm run rag:backup / rag:backup:verify / rag:restore  # SQLite VACUUM INTO + Qdrant snapshot + 原件
```

备份**不含** `apps/api/.env`；恢复只写新目录，不覆盖正在使用的数据。

---

## RAG-QUALITY v1.1 接口变更（2026-09-29）

本批修复首答重复展示、图片 Markdown 污染、证据窗口无界、首答无长度约束、引用校验用错证据集，
并把题库 AI 整理改回「当前聊天模型」。**只加字段、不改旧协议**；新增字段对旧历史消息一律可选。

### 首答与证据（`/rag/stream`、`/rag/reply`）

| 项 | 变化 |
| --- | --- |
| `text.delta` | **只含知识点正文**（编号 + 标题 + 说明 + `[n]`），**不再拼接教材原文摘录**。原文改由结构化来源面板展示 |
| `rag.result.result.presentation` | 新增可选：`{version:"compact-v1", answerStyle:"brief", bodyCharCount}`；`bodyCharCount` 为知识点正文码点数 |
| `rag.result.result.reasonCode` | 新增可选：`NO_MATCH` / `EVIDENCE_TEXT_EMPTY` / `EVIDENCE_UNIT_TOO_LARGE` / `SUMMARY_INVALID` / `SUMMARY_PARTIAL`；`ok` 时为 `null` |
| `evidence[].readable` | 新增可选：`{version:"rag-readable-v1", text, removedImageCount}`。**新服务端必填**，旧历史可缺失 |
| `evidence[].text` | **语义不变**：仍是可逐字验证的**封存原文切片**（含图片 Markdown 也必须原样保留）。展示/预览/复制用 `readable.text`；回传引用与散列校验只用 `text` 与坐标字段 |

`[n]` 的编号 = 该证据在 `result.evidence` 数组中的序号（1 基），与后端渲染的首次出现顺序一致。

**首答预算（`app/core/rag_budget.py` 为唯一事实来源，长度单位为 Unicode 码点）**：

```text
首答证据最多 6 条；邻块扩展左右各 ≤1 块
单条证据清洗后 ≤1600 码点；单条原文切片 ≤6000 码点；证据原文总量 ≤16000 码点
首答入模证据总量 ≤6000 码点（并受模型 num_ctx 估算二次约束）
首答 ≤3 个知识点；单点「标题+说明」≤90 码点；合计 ≤250 码点；每点 ≤2 条引用
模型输出不合法时最多修正一次
```

**状态语义（不得退化）**：有文本命中但因预算无法完整装入 → `partial` + `EVIDENCE_UNIT_TOO_LARGE`（附定位），
**不得**报「没有找到教材依据」；有命中但清洗后无文本 → `uncertain` + `EVIDENCE_TEXT_EMPTY`；
范围内没有任何文本命中 → `no_evidence` + `NO_MATCH`。

### 索引与分块

- `ChunkPolicy` 新增 `textProjectionVersion`（默认 `rag-readable-v1`）并**进入分块策略指纹**：
  清洗策略一变指纹就变，必然产生新 `chunk_set`，绝不复用旧划分/旧清洗。
  旧策略 JSON 缺该字段时按 `raw-v0` 解释，且**旧指纹仍可复现**。
- 块坐标与 `text_sha256` 仍绑定**原文切片**；新增索引输入文本 = 清洗投影；
  清洗后为空的块在**分块清单阶段**排除（不留「有块无向量」的计数差异），仅含公式的块保留。
- Qdrant payload 新增 `textProjectionVersion` 与 `indexTextSha256`；`text_sha256` 含义不变。
- BM25 文档文本按该代登记的清洗版本投影；缓存键含 `generation_id + 修订集合 + 清洗版本 + 分词版本`。
- 入库导入草稿：清洗后无可用文本时 `canCommit=false` 且给出可读警告，错误码 `NO_INDEXABLE_TEXT`（422）。

### 题库 AI 整理（`POST /question-imports/{id}/organize`）

`modelProfileId` **必填**，语义恢复为**当前聊天模型的 profile id**（本地或云端一视同仁），
由共享的 `services.model_runtime.resolve_chat_model` 解析。任务在点击时**冻结**模型；
进行中切换聊天模型不影响已冻结任务。新增错误码：
`ORGANIZER_MODEL_RESELECT_REQUIRED`（旧语义的未完成任务，不自动恢复，既有建议保留）、
`ORGANIZER_OUTPUT_TRUNCATED`（上游截断，不生成可应用建议）、
`AUTH_REQUIRED` / `RATE_LIMITED` / `UPSTREAM_UNAVAILABLE`（**任务级**，文案指向模型服务，不得说成「试题内容无效」）。
取消时在途未完成批的建议**不落库**。

### 备份与恢复（`scripts/rag/backup.py`）

- `create`：先取数据根**排他锁**（拿不到 → `DATA_LOCK_BUSY`，非零退出，不写任何文件）；
  有未结束任务则拒绝（含知识点库/教学库任务）；用 **SQLite backup API** 生成副本（不直接拷 WAL）；
  只复制**被数据库引用**的文件；含 `staging` 草稿产物（排除 `tmp-*.part`）；
  Qdrant 快照核对点数与维度；**全部通过才把清单标 `status:"complete"`**。
- 清单 `schemaVersion: 3`（TEACHING-LOOP B0 起）：**四个库**都必须入清单——
  `textbooks/catalog.sqlite3`、`question-bank/question-bank.sqlite3`、`knowledge/knowledge.sqlite3`、
  `teaching/teaching.sqlite3`；受管资产按 `restorePath = assets/blobs/<sha256>` 入清单（归档路径为
  `files/assets/blobs/<sha256>`，前缀 `files/` 只出现在归档内）；`files[]` 带
  `logicalRole/restorePath/sha256`，`collections[]` 带维度/点数/快照指纹。
  **缺任一库/任一被引用原件即 `status:"failed"`**（CLI 非 0，不宣称备份完成）。
- `restore`：**按应用运行布局**写入四库与 `assets/…`；
  恢复后对四库做 `integrity_check` + `foreign_key_check`，并从恢复后的教学库重新推导
  `file_assets` 引用逐文件重算 sha256（缺失/不符即失败）；
  Qdrant 恢复必须显式给 `--isolated-qdrant`（给 6333 或缺失一律拒绝）；
  先验后写，失败把 `restore-state` 留在 `incomplete`；旧清单（`schemaVersion:2` 两库与 legacy）
  只读兼容并标 `legacy_revalidated`，其范围只覆盖当时的教材目录与题库。
- 数据根处于 `incomplete` 时**应用拒绝启动**；API 生命周期持有同一把锁（`app/core/data_lock.py`）。

### 运维命令补充

```text
npm run rag:rebuild       # 同 Embedding 身份、新清洗策略重建一个新代并原子切换（旧代保留不删）
npm run rag:quality       # 固定质量集（30 问：10 组 × 2 正向 + 1 边界），只读、不建库、不改任教设置
```

`rag:verify` / `rag:quality` / 命中率测量脚本一律**只读打开**正式数据根，
**不再调用 `migrate()`、不再写入任教设置**（验收不得改用户配置）。

---

## 教学闭环 B0 公共契约与基础设施（2026-09-30）

依据 [教学闭环设计目录](design/teaching-loop-v1/README.md) 与
[多 Agent 实施任务计划书 v2.0 §二.3](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md) 实施 B0
（CTRL + T00）：冻结类型/错误/版本/任务/资产/迁移契约并落地公共基础。下表记录 B0 的基础结构；
知识点、名单、原卷、施测、成绩与对应页面由 B1–B3 增量实现。B4 学情与练习及B5后台教案候选接口见文末；独立验收状态见 CURRENT_STATUS。
任务卡与逐项证据见 [B0 批次目录](qa/TEACHING-LOOP-B0/TASK-CARD.md)。

### 四库与迁移登记

| 存储 | 路径 | B0 内容 |
| --- | --- | --- |
| 教材目录 | `.local-data/textbooks/catalog.sqlite3` | 既有结构（冻结为 `0001_textbooks_baseline`） |
| 题库 | `.local-data/question-bank/question-bank.sqlite3` | 既有 9 表 + `question_jobs` 任务引擎列（`0002`） |
| 知识点库 | `.local-data/knowledge/knowledge.sqlite3` | `knowledge_submissions`、`knowledge_jobs` |
| 教学业务库 | `.local-data/teaching/teaching.sqlite3` | `command_submissions`、`file_assets`、`workflow_jobs` |
| 受管资产 | `.local-data/assets/blobs/<sha256>` | 内容寻址原件（不覆盖） |

- 每库持有 `schema_migrations(id, sha256, applied_at)`；迁移清单在 `app/core/migrations/`，**追加式**：
  已登记迁移的 SQL 散列不符 → 启动拒绝（`SCHEMA_MIGRATION_DRIFT`），结构变化必须新增迁移。
- 迁移逐条独立事务：失败整体回滚且不登记，下次启动从该条重跑。
- 启动顺序：恢复状态闸门（`incomplete` 拒绝启动）→ 既有库体检（不可读/结构不符/漂移拒绝，
  **不按空库重建**）→ 迁移登记 → 任务收敛（遗留 `running` → `interrupted`）。
- 业务表增量（B1+）由实现方提供 SQL、总控登记；不得改写冻结基线。

### 公共任务（`/api/v1/workflow-jobs`）

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/workflow-jobs/{jobId}?domain=knowledge\|question\|teaching` | 返回 `JobView`；未知任务 404 `JOB_NOT_FOUND`；域非法 422；域未装配 503 |
| POST `/api/v1/workflow-jobs/{jobId}/cancel`（body `{domain}`） | 协作式取消，幂等；`queued` 立即取消，`running` 置标志后不发布迟到结果 |
| POST `/api/v1/workflow-jobs/{jobId}/retry`（body `{domain}`） | 终态 `failed/interrupted/cancelled` 可重试（保留冻结输入与模型指纹）；已注册执行器的 `queued` 重复请求幂等补调度/返回当前视图，`running/succeeded` → 409 `JOB_NOT_RETRYABLE` |

`JobView = {jobId, domain, kind, attempt, state, result, error}`；
`state ∈ queued | running | succeeded | failed | cancelled | interrupted`。
租约 90 秒、每 20 秒续租；**同时最多 2 个后台重任务，其中最多 1 个模型生成任务**；
任务结果与终态在所属业务库的**同一事务**提交；页面停止观察不取消任务，只有 cancel 接口取消；
重启不自动重跑中断的模型任务。

G1修复后，claim/complete/fail/cancel在取得SQLite写锁并读当前行后采时；发布与终态写入在事务内核原attempt/token/取消/租约到期。已经到期的旧轮不能写业务、checkpoint或终态，心跳不能恢复旧授权。新queued轮在旧轮heartbeat收尾期间排队等待，重复retry只接受一次目标轮调度，旧tracking清理不删除新轮。租约时长不变。

### 提交幂等与错误详情

- 提交幂等身份 `(ownerId, operation, submissionId)`：同键同 `requestHash` 重放返回原结果
  （不重复执行业务写入）；同键不同 hash → 409 `SUBMISSION_CONFLICT`。
- 版本冲突 409 `REVISION_CONFLICT` 带 `details.currentRevision`；422 行列错误带
  `details.issues[{row?, column?, field?, code, message}]`；简单字段错误用 `details.fields`。
- 前端 `ApiError` 现在保留 `details`；`AbortError` 原样抛出（`isAbortError` 判定），不再被
  吞成 `SERVICE_UNAVAILABLE`；新增 `apiRequestBlob`（返回 `{blob, fileName}`）供导出产物下载。

### 受管资产

- `file_assets`（教学库）：`id/owner_id/kind/blob_key/sha256/original_name/media_type/byte_size/created_at`；
  `kind ∈ roster|score_sheet|paper|export|attachment`。
- `blob_key` 只接受 `blobs/<64 位小写 hex>`；文件读取时重算 sha256，缺失/篡改分别报
  `ASSET_MISSING` / `ASSET_CORRUPT`；路径穿越、非法键一律 422 且不创建目录。

### 跨模块类型（冻结）

`apps/api/app/contracts/teaching_loop.py` 与 `apps/web/src/contracts/teaching-loop.ts` 双侧一致：
`RevisionIdentity`（`revision` 乐观锁 vs `revisionId` 固定修订）、`ScoreCell`（`scoreUnits` 整数）、
`Observation`、`AssetRef`、`RichContentV2`/`ContentBlock`、`JobView`、`canonical_hash`。
分数禁止浮点；外部 JSON camelCase、内部 snake_case；时间 UTC。

---

## 教学闭环 B1 接口（2026-09-30）——富内容基础 / 知识点后端 / 名单后端

依据 [多 Agent 实施任务计划书 v2.0 §二.3](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)
实施 **B1（T10 + T20 + T30-a + CTRL）**。任务卡与证据见
[B1 批次目录](qa/TEACHING-LOOP-B1/TASK-CARD.md)。**本批不新增前端页面。**

结构与依赖（追加式迁移，B0 已登记声明与散列不变）：

| 库 | 迁移 | 内容 |
| --- | --- | --- |
| 知识点库 | `0002_knowledge_business_tables` | 设计 5 表（`subjects`/`knowledge_points`/`knowledge_point_revisions`/`knowledge_aliases`/`textbook_knowledge_links`）+ 环检测与修订不可变触发器 + 导入批次表（`knowledge_imports`/`knowledge_import_rows`） |
| 知识点库 | `0003_knowledge_import_issues_column` | `knowledge_imports` 补 `issues_json`（批次级问题独立落列；列已存在时由 adjust 钩子跳过 ALTER） |
| 教学库 | `0002_teaching_business_tables` | `classes`/`students`/`class_memberships`（含 `ux_active_membership` 部分唯一索引）+ 名单批次表（`roster_imports`/`roster_import_rows`） |

- 新增依赖（uv 锁定）：`openpyxl==3.1.5`（XLSX 只读解析）、`math2docx==3.1.0`（LaTeX→OMML，导出新题用）。
- 表格导入接受 `.xlsx` 与 `.csv`；`.txt`/`text/plain` 按 CSV 文本解析（方便教师直接贴表格），其余格式 422 `UNSUPPORTED_DOCUMENT_FORMAT`。
- 启动门控 `REQUIRED_TABLES` 仍只要求 B0 基础表：**尚未应用 B1 迁移的旧库可正常启动**，迁移后新表齐备。
- 跨库发布/归档统一经 `app/services/publication.py` 的 `PublicationCoordinator`（进程内锁，锁内只做数据库读取与短事务；
  不是跨进程锁，也不宣称跨库原子事务）。

### 知识点（T20）

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/knowledge-points` | 列表：`subjectId`/`status`/`parentId`/`q` 过滤 + 分页 `{items,total,offset,limit}` |
| POST `/api/v1/knowledge-points` | 人工建立（201）；同 `(subjectId, code)` → 409 `KNOWLEDGE_CODE_CONFLICT` |
| GET `/api/v1/knowledge-points/{id}` | 详情（当前修订、别名、`revision` 乐观锁与 `revisionId`/`version`） |
| PATCH `/api/v1/knowledge-points/{id}` | 更新（`expectedRevision`；改名=追加修订；空白默认不修改，`clearFields` 明确清空） |
| POST `/api/v1/knowledge-points/{id}/archive`、`/restore` | 归档/恢复（`expectedRevision`）；归档保留历史引用，新引用禁选归档 |
| GET/POST `/api/v1/knowledge-points/{id}/textbook-links`、DELETE `/…/{linkId}` | 可选教材依据：区间经教材目录核验并冻结标题；教材不可用 → 503 `TEXTBOOK_EVIDENCE_UNAVAILABLE`（**不当作"没有依据"**） |
| POST `/api/v1/knowledge-imports` | multipart：`file`(.xlsx/.csv) + `subjectId` + 可选 `mappingJson`/`sheetName`；字段 `subjectCode/code/name/description/parentCode/aliases` |
| GET `/api/v1/knowledge-imports`、GET `/api/v1/knowledge-imports/{id}` | 批次列表 / 详情（含行、建议动作与 `issues`） |
| PATCH `/api/v1/knowledge-imports/{id}` | 改映射 / 行动作（`expectedRevision`） |
| POST `/api/v1/knowledge-imports/{id}/confirm` | 确认（`expectedRevision`+`submissionId`+`actions`）；同 `submissionId` 同载荷重放返回原结果 |
| POST `/api/v1/knowledge-suggestion-jobs` | AI 候选（`modelProfileId`+`subjectId`+`materials`/`textbookEvidence`）→ 202 `JobView`；候选只进 `source="ai"` 待确认批次，不写正式表 |

知识点错误码：`KNOWLEDGE_CODE_CONFLICT`(409)、`KNOWLEDGE_PARENT_INVALID`/`KNOWLEDGE_CROSS_SUBJECT_PARENT`/
`KNOWLEDGE_CYCLE`(422，自指/环/跨学科/缺父都可经 `details.issues[].field ∈ {parentId, parentCode}` 定位)、
`KNOWLEDGE_ARCHIVED`(409)、`KNOWLEDGE_IMPORT_BLOCKING_ISSUES`(422)、`KNOWLEDGE_LINK_NOT_FOUND`(404)、
`KNOWLEDGE_LINK_DUPLICATE`(409)、`KNOWLEDGE_SUGGESTION_INVALID_JSON`/`_UNKNOWN_REFERENCE`/`_TRUNCATED`/`_NO_EVIDENCE`(422)、
`TEXTBOOK_EVIDENCE_INVALID`(422)、`TEXTBOOK_EVIDENCE_UNAVAILABLE`(503)。
（契约中的 `KNOWLEDGE_SUBJECT_UNKNOWN` 与 `KNOWLEDGE_LINK_INVALID` 为保留码：当前实现按需 `ensure_subject`
建学科、链接不存在/不属于该点返回 404 `KNOWLEDGE_LINK_NOT_FOUND`，这两个码**目前不会抛出**。）

### 班级、学生与名单（T30-a）

| 方法与路径 | 说明 |
| --- | --- |
| GET/POST `/api/v1/classes`、GET/PATCH `/api/v1/classes/{id}`、POST `/api/v1/classes/{id}/archive`、`/restore` | 班级 CRUD（`schoolYear`+`code` 用户内唯一 → 409 `CLASS_CODE_CONFLICT`；归档班级仍可读，新导入 409 `CLASS_ARCHIVED`） |
| GET `/api/v1/classes/{id}/students` | 该班活跃成员（含归属历史） |
| GET `/api/v1/students`、GET `/api/v1/students/{id}`、POST `/api/v1/students` | 学生身份：**学号按文本保存并保留前导零**；无学号可显式建档；姓名允许重名 |
| PATCH `/api/v1/students/{id}`、POST `/api/v1/students/{id}/transfer` | 改名/改学号（乐观锁）；转班（旧归属置 `leftOn`，历史保留） |
| POST `/api/v1/classes/{id}/roster-imports` | multipart 名单上传（`.xlsx`/`.csv`）→ 预览批次 |
| GET `/api/v1/roster-imports`、GET `/api/v1/roster-imports/{id}`、PATCH、POST `/…/confirm` | 批次/预览/校对/确认（`identityMatches` 每行 `link|create|ignore`；未出现的学生不自动退班；整批回滚；幂等重放） |

名单错误码：`CLASS_CODE_CONFLICT`/`CLASS_ARCHIVED`/`STUDENT_NO_CONFLICT`(409)、
`ROSTER_ROW_INVALID`/`ROSTER_IDENTITY_UNRESOLVED`/`ROSTER_IMPORT_BLOCKING_ISSUES`/`ROSTER_MAPPING_INVALID`(422)。

### 施测契约的 B1 分期说明（已由 B2 实现替代）

B1 仅冻结 `AssessmentCreateRequest`/`ParticipantSnapshot`/`ConfirmedPaperRevisionView`/
`ConfirmedPaperReader`。B2 已装配真实 `ConfirmedPaperReader` 并实现施测创建，现行路径与闸门见下文「施测（T30-b）」。
未装配真实 reader 时仍须明确返回不可用错误，不能返回模拟成功；不再将正式 `POST /api/v1/assessments` 描述为通配 501 占位。

### 富内容（T10，库能力，无 HTTP 路由）

- `app/services/rich_content/`：`parse_docx_rich`（段落/表格合并单元格/图片真实字节与尺寸/OMML 原样/未知对象进
  `issues`，块顺序与来源坐标可核验）→ `group_shared_materials`（保守分组，题号前/材料标记）→
  `render_rich_document(variant=student|teacher)`（学生版不输出答案与解析；共同材料只出一次；图片重建
  relationship，不复用旧 rId；OMML 原样、LaTeX 经 `math2docx` 转换，失败报 `FORMULA_CONVERSION_FAILED`(422) 并保留定位）。
- 表格块 `cells` 为**行优先**序列、`rowSpan`/`colSpan` 占位；`columnCount`（B1 新增，可选）给出网格宽度，
  是精确还原行的依据（DOCX 解析器必须填；旧数据缺失时消费方回退启发式）。
- 该模块是 T40/T50/T80 的复用基础；正式原卷确认与练习导出业务在相应批次实现。
- 本模块新增错误码：`DOCUMENT_FILE_MISSING`(500)、`DOCUMENT_PARSE_FAILED`(422)、`RICH_IMAGE_UNSUPPORTED`(422)、
  `ASSET_NOT_FOUND`(422)、`FORMULA_CONVERSION_FAILED`(422)；资产层 `ASSET_MISSING`/`ASSET_CORRUPT` 原样传出。

---

## 教学闭环 B2 接口（2026-10-01）——原卷后端 / 题库增量 / 施测真实创建 / 知识点前端

依据 [多 Agent 实施任务计划书 v2.0 §二.3](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)
实施 **B2（T40 + T50 + T30-b + F10-KP + CTRL）**。任务卡与证据见
[B2 批次目录](qa/TEACHING-LOOP-B2/TASK-CARD.md)。新增前端页面 `/knowledge-points`（见 [ROUTES.md](ROUTES.md)）。

结构与依赖（追加式迁移，B0/B1 已登记声明与散列不变）：

| 库 | 迁移 | 内容 |
| --- | --- | --- |
| 教学库 | `0003_teaching_paper_tables` | `papers`/`paper_revisions`/`paper_items`/`paper_item_knowledge`（设计逐字）+ `paper_source_blocks`/`paper_issues`/`ai_proposals` + 触发器（`paper_cycle_*`、`paper_confirm`、`immutable_paper_revisions_*`、`no_direct_sealed_paper_revisions`、`freeze_paper_{items,item_knowledge,source_blocks,issues}_*`） |
| 教学库 | `0004_teaching_assessment_tables` | `assessments`/`assessment_classes`/`assessment_participants` + 参测班级显式确认列 + `assessment_confirmed_paper_insert`/`assessment_paper_fixed` |
| 题库 | `0004_question_knowledge_links` | `question_knowledge_links`（设计逐字 + 不可变触发器）+ `question_draft_knowledge_links`、`question_import_provenance`、`question_content_fingerprints` |

**分期结构及后续覆盖**：B2 冻结时 `paper_revisions.source_practice_revision_id` 与 `assessments.active_score_revision_id`
均只允许为空。B3 的 `0007` 已重建 `assessments`，恢复成绩指针复合外键并允许引用本施测已确认成绩；
现行成绩语义见下文「成绩迁移」。B4 的 `0008/0009` 先建练习修订，再受检重建原卷来源：文件/固定审核练习恰一非空，练习指针是真 FK，并核 owner/学科及确认内容映射；文件卷仍核原件与来源块。
草稿 `total_score_units >= 0`，确认闸门要求 >0 且等于计分叶子合计；旧确认不可变与复合外键保留。迁移实际验收见 CURRENT_STATUS。

### 原卷（T40）

| 方法与路径 | 说明 |
| --- | --- |
| POST `/api/v1/paper-imports` | multipart `file`(.docx)+`subjectId`+可选 `title`；T10 富解析 → 原文块/问题清单/规则拆题持久化；返回 `PaperImportView`(201) |
| GET `/api/v1/papers` | 列表（`subjectId`/`status`/`q` + 分页） |
| GET `/api/v1/papers/{id}` | 试卷概览（当前修订指针/状态/总分/计分叶/阻断问题数） |
| PATCH `/api/v1/papers/{id}/draft` | **整表替换**草稿（items/blocks/issues，含知识关联）；`expectedRevision`=`papers.revision`；当前修订为 confirmed 时**自动新建 version+1 草稿**再应用 |
| POST `/api/v1/papers/{id}/confirm` | 确认闸门（唯一题号/无环/仅叶子计分/知识点齐备/总分一致/块归属或排除/无 blocking issue）；`submissionId` 幂等；确认后不可增删改 |
| GET `/api/v1/papers/{id}/revisions/{revisionId}/content` | 固定修订完整内容（items/blocks/issues） |
| POST `/api/v1/papers/{id}/knowledge-proposals` | AI 知识点建议（`teaching:paper_mapping` 任务）→ `JobView`(202) |
| GET `/api/v1/paper-proposals/{id}`、POST `…/apply`、POST `…/reject` | 建议读取（`stale` 实时计算）/应用（只应用已有知识点，核草稿版本）/拒绝 |

分值一律**十进制字符串**（`maxScore`/`totalScore`，≤2 位小数）；服务端换算 `×100` 整数单位。
错误码：`PAPER_NOT_FOUND`(404)、`PAPER_REVISION_STALE`/`PAPER_NOT_EDITABLE`(409)、`PAPER_CONFIRM_INVALID`/
`PAPER_BLOCK_UNASSIGNED`/`PAPER_ISSUE_BLOCKING`/`PAPER_TOTAL_MISMATCH`/`NO_SCORED_ITEMS`/
`ITEM_KNOWLEDGE_MISSING`/`SCORED_ITEM_MUST_BE_LEAF`/`ITEM_CYCLE`/`ITEM_PARENT_INVALID`/
`ITEM_QUESTION_NO_DUPLICATE`/`ITEM_SCORE_INVALID`/`PAPER_BLOCK_INVALID`/
`KNOWLEDGE_REFERENCE_INVALID`/`PAPER_IMPORT_PARSE_FAILED`/`PAPER_IMPORT_ASSET_INVALID`(422)、
`UNSUPPORTED_DOCUMENT_FORMAT`(422)、`PAPER_PROPOSAL_STALE`(409)。

### 题库增量（T50）

| 方法与路径 | 变化 |
| --- | --- |
| PATCH `/api/v1/question-drafts/{id}` | 新增可选 `knowledgeLinks`（提供即整表替换，空数组清空）；内容或关联变化 `revision+1` 且回 `needs_review` |
| POST `/api/v1/question-imports/{id}/confirm` | 草稿关联冻结为 `question_knowledge_links`（含学科与名称快照）；旧 `knowledgeTags` 保持原义 |
| GET `/api/v1/questions?knowledgePointId=` | 按正式知识点筛选（只查最新修订） |
| PATCH `/api/v1/questions/{id}` | 新增可选 `knowledgeLinks`；内容修改**复制旧正式关联**，明确改关联才替换（均产生新修订） |
| POST `/api/v1/question-generation-jobs` | AI 补题（`question:generate`，独立 `GenerateReply`）→ `GenerationJobView`(202)；候选进既有校对确认链 |
| 任务视图 | `OrganizeJobView`/`GenerationJobView` **六态 + `attempt`**（`interrupted` 可经 `/workflow-jobs/{id}?domain=question` 与显式 retry 处理；组织/生成统一走 JobEngine，启动收敛含 question 域） |

错误码补充：`GENERATION_INVALID_JSON`、`GENERATION_OUTPUT_TRUNCATED`、`GENERATION_UNKNOWN_KNOWLEDGE`、
`GENERATION_UNKNOWN_EVIDENCE`、`GENERATION_FORBIDDEN_REFERENCE`（均 422 级）、`KNOWLEDGE_REFERENCE_INVALID`(422)、
`SERVICE_UNAVAILABLE`(503，模型/知识点库未装配)。

### 施测（T30-b）

| 方法与路径 | 说明 |
| --- | --- |
| GET/POST `/api/v1/assessments` | 列表（`subjectId`/`classId`/`state`）/创建（201，`submissionId` 幂等） |
| GET `/api/v1/assessments/{id}` | 详情（含参测人次快照） |
| PATCH `/api/v1/assessments/{id}` | 标题/类型/日期（`expectedRevision` 守卫；**不能换卷**） |
| POST `/api/v1/assessments/{id}/participants` | 补录/补考新增人次（分配下一 `attemptNo`；不覆盖既有记录） |

闸门：只用**已确认**原卷修订（reader + DB 触发器）；参测姓名/学号**服务端读取后冻结**；显式非空名单；
`classIds` 存在且未归档、participant `classId` 必须在范围内；`(assessment, student, attempt)` 唯一；
**归属未覆盖 `heldOn`** → 422 `PARTICIPANT_CLASS_UNCONFIRMED`（逐行定位），教师带 `classConfirmed` +
`classConfirmationNote` 重提后冻结并保存依据（**不修改归属历史**）。
错误码：`ASSESSMENT_NOT_FOUND`(404)、`ASSESSMENT_PAPER_INVALID`/`ASSESSMENT_HELD_ON_INVALID`/
`PARTICIPANT_EMPTY`/`PARTICIPANT_INVALID`/`PARTICIPANT_CLASS_UNCONFIRMED`/`PARTICIPANT_CLASS_SCOPE`/
`CLASS_ARCHIVED`(422，施测域；名单域的 `CLASS_ARCHIVED` 为 409)、
`ASSESSMENT_PAPER_FIXED`/`ASSESSMENT_REVISION_STALE`/`PARTICIPANT_ATTEMPT_CONFLICT`(409)。
`UnavailablePaperReader` 的 501 `PAPER_READER_UNAVAILABLE` 已由真实 adapter 取代。

### 知识点前端（F10-KP）

- `/knowledge-points`：学科筛选（取 `/textbook-taxonomy` 的真实 `subjectId`）、父树、建立/更新（`clearFields`）、
  别名、归档/恢复、教材依据（**不可用显示"暂不可用"，不显示成"没有依据"**）、XLSX/CSV 预览/映射/行校对/整批确认、
  AI 候选（`/workflow-jobs` 六态 + 取消/重试，轮询守卫 jobId/attempt）。
- 题库页兼容：整理任务支持 `interrupted` 横幅与「重试整理」（经 `/workflow-jobs/{id}/retry` 后按新 attempt 继续观察）。

### 新增依赖与命令

无新增 Python 依赖（B1 的 openpyxl/math2docx 继续使用）。前端仍 `npm run dev/build/check`；E2E 先 `build` 再
`npx playwright test`（隔离 5174）。

## 教学闭环 B3 接口（2026-10-01）——G0 前置修复 / 成绩后端 T60 / 成绩导入工作区 F20-I / 题库前端 F10-QB

### G0 公共语义修正（B2 审查 B2-RV01–11 + 已披露项）

- **公共重试已调度**：`POST /workflow-jobs/{id}/retry` 置 `queued` 后经唯一执行器注册表
  （`app/services/jobs/registry.py`）原子入队；registry 导入失败**阻断启动**（不再静默无执行器）。
  重试语义：retry 收据 `attempt=N`，随后接受 `queued(N)→running/终态(N+1)`；前端观察窗口 [N, N+1]，
  N+2 视为被接管。并发重复 retry 合法结果 ∈ {200, 409}，且**恰好执行一次**。
- **发布失败收敛**：业务结果发布异常时，用本次执行开始时的原 JobLease 在新短事务 CAS 收敛
  `failed`（`error.code` 保留域内错误码；跨域异常统一 `JOB_FAILED` + 已回滚说明）；请求过取消 →
  `cancelled` 优先；失权零写入。三域（teaching/question/knowledge）一致。
- **冻结模型指纹**：任务创建时冻结 `model_fingerprint = sha256(canonical{modelId, protocol, baseHost,
  apiFormat})`（不含凭证）；执行前比对真实配置，漂移 → 409 `MODEL_CONFIG_DRIFT`；旧任务无指纹 →
  422 `MODEL_FINGERPRINT_MISSING`（要求新任务，不静默放行）。
- **知识点引用复核**（`app/services/knowledge_refs.py`）：原卷/题库确认在 `PublicationCoordinator`
  内复核引用身份/修订/学科/未归档；归档 → 409 `KNOWLEDGE_ARCHIVED`，无效引用 →
  422 `KNOWLEDGE_REFERENCE_INVALID`（`details.issues[].field`）。
- **原文块与资产**：`PaperSourceBlockView.content` 返回持久化块正文；
  `GET /papers/{paperId}/revisions/{revisionId}/assets/{assetId}/content` 只读该修订引用过的受管资产；
  结构化问题处置（`supplement_text`/`supplement_asset`/`exclude`）；空题面 `ITEM_STEM_MISSING`、
  缺必要共同材料 `ITEM_MATERIAL_MISSING`。
- **修订级标题快照**：`paper_revisions.title_snapshot`（迁移 0005；旧数据回填来源标注
  `backfilled_from_paper`，不声称还原原标题）；固定修订读取自己的快照。

### 成绩迁移（0006 / 0007）

- 0006 建 `score_imports` / `score_import_rows` / `score_revisions`（含 `participant_snapshot_json`、
  `item_snapshot_json`）/ `student_item_scores` / `score_revision_corrections` + 封存闸门与不可变触发器；
- 0007 受控重建 `assessments`：移除分期 CHECK，恢复
  `(active_score_revision_id,id)→score_revisions(id,assessment_id)` DEFERRABLE 复合外键；
  `active` 只允许指向本施测**已确认**修订（触发器 `SCORE_REVISION_NOT_CONFIRMED` 兜底）。
  重建在含已确认卷/施测/参测数据的 B2 旧库上验证：数据逐行保留、`foreign_key_check` 空、
  `integrity_check=ok`、触发器逐字恢复。

### 成绩导入（T60）

- `POST /assessments/{assessmentId}/score-imports`（multipart `file` + 可选 `workSheet`/
  `baseScoreRevisionId`，XLSX/CSV）→ `ScoreImportView`；服务端用**公式视图 + 缓存值视图**读表、
  保留物理行列、超限明确报错、不静默截断；原件为受管资产（`kind='score_sheet'`）。
- 成绩路径的单元格完整文本上限20,000字符；身份/出勤/总分/小题及XLSX公式/缓存视图使用同一完整转换后长度校验。
  超限返回422 `TABLE_TOO_LARGE`，`details={sheet,row,column,address,view,actualLength,maxLength}`；
  `row`为1基物理行、`column`为列字母，`view`为`formula`/`cached`/`csv`，不先截断再校验。
  CSV解析器无法读取字段/记录时返回422 `TABLE_PARSE_FAILED`，`details={sheet:"CSV",row}`；
  解析器不能给出可靠列时不伪造列号。拒绝不建立导入或正式成绩/矩阵，不修改原件。
- `GET /score-imports?assessmentId=&offset=&limit=`、`GET /score-imports/{importId}`、
  `GET /score-imports/{importId}/rows?offset=&limit=`。
- `PATCH /score-imports/{importId}`（`ScoreImportPatchRequest`：mapping / 行定位 `participantId` /
  单元格校正 `ScoreCellPatch`（原表行号+列字母））；每次生效递增 `revision` 与 `previewVersion`。
- `POST /score-imports/{importId}/confirm`（`ScoreImportConfirmRequest`）→ `ScoreImportConfirmResult`。
  三版本语义互不替代：`expectedImportRevision`（导入草稿锁）/`expectedAssessmentRevision`（施测锁）/
  `baseScoreRevisionId`（所基于的正式版本；首个版本为 null）任一不符 → 409 明确错误码 + `currentRevision`。
  承认内容必须与预览完全一致（逐班 absent 人次 + missing 人次/单元数）→ 否则 422
  `SCORE_ACKNOWLEDGEMENT_MISMATCH`；同一 `submissionId` 重放返回原结果（`replayed=true`）。
- `GET /assessments/{assessmentId}/score-revisions`、`GET /score-revisions/{revisionId}`、
  `GET /score-revisions/{revisionId}/matrix?offset=&limit=`（`items` 不分页=固定计分叶；
  `rows` 分页；`totalUnits` 仅在该人次全 recorded 时非空）。
- `POST /assessments/{assessmentId}/score-revisions/correct`（`ScoreRevisionCorrectRequest`）：
  base 必须等于当前 active；从不可变 base 复制全矩阵 + 修正当时参测快照生成新完整版本，
  审计（原值/新值/理由）落 `score_revision_corrections`。
- 分数一律 Decimal 文本 ↔ ×100 整数单位；0=recorded(0)、空=missing、缺考=absent、免考=exempt
  四态不得互相顶替；全矩阵 = 冻结参测人次 × 固定计分叶，缺行缺列显式 missing、绝不补 0；
  确认后不可变（DB 触发器 + 服务）。
- 错误码：`SCORE_IMPORT_NOT_FOUND`/`SCORE_REVISION_NOT_FOUND`(404)；
  `SCORE_IMPORT_NOT_EDITABLE`/`SCORE_REVISION_IMMUTABLE`/`SCORE_BASE_REVISION_CONFLICT`/
  `SCORE_NO_BASE_REVISION`(409)；`SCORE_IMPORT_REVISION_CONFLICT`/`SCORE_ASSESSMENT_REVISION_CONFLICT`(409，
  带 `currentRevision`)；`SCORE_MAPPING_INVALID`/`SCORE_ROW_UNRESOLVED`/`SCORE_ROW_DUPLICATE_PARTICIPANT`/
  `SCORE_CELL_INVALID`/`SCORE_CELL_OVER_MAX`/`SCORE_ACKNOWLEDGEMENT_MISMATCH`/`SCORE_MATRIX_INCOMPLETE`/
  `SCORE_PARTICIPANT_UNKNOWN`/`SCORE_ITEM_UNKNOWN`/`SCORE_CORRECTION_INVALID`(422，带行列定位)。

### 成绩导入工作区（F20-I）与题库前端增量（F10-QB）

- `/assessments` 五步工作区（名单 → 原卷 → 施测 → 成绩 → 历史）：成绩流
  `upload → 映射 → 校对 → 预览承认 → 确认`；0/missing/absent/exempt 显著区分；异常显示原表物理地址；
  409 保留编辑、422 保留校对；逻辑确认冻结 `submissionId` + 原 payload 到明确结果；切换/卸载使在途请求失效。
- 题库：知识点筛选/标注与显式替换、旧 `knowledgeTags` 分区块呈现、补题六态（取消/真实重试 [N, N+1] 窗口）、
  AI 来源与校对链（pending/apply/reject/stale）、`200 + failures` 仍显示**整批未确认**。

### B3 修复与补齐接口（2026-10-02）

- `ScoreImportView.requiredAcknowledgements = {absences, missing}` 是当前 `previewVersion` 的权威有效全矩阵范围；前端直接展示并逐类承认，不从原件空格或当前名单推导。原件标记覆盖整人次时，其他空格不成为伪 missing。旧预览仍保持原冻结参测范围，施测变更会显示版本冲突。
- `ScoreColumnMapping` 增加可选 `totalColumn`/`attendanceColumn`。列字母归一为大写后校验计分/身份/总分/出勤占用与重复。总分仅在所有叶 recorded 时精确校验；未完整时只提示。出勤与冻结参测不符时返回定位的 `SCORE_ATTENDANCE_MISMATCH`，不自动改出勤。`SCORE_TOTAL_MISMATCH` 同为 422。
- `ScoreRawCellView` 同时返回 `originalText`、`originalCachedText`、`correctedText`、`effectiveStatus`、`scoreUnits`，保留公式与物理坐标。历史 `text` 字段继续提供有效文本；原始证据不被校正覆盖。改 sheet/表头/身份/计分映射都重新提取行，保留仍适用坐标的已确认校正。
- `PATCH /assessments/{id}/participants/{participantId}/attendance`：`{submissionId, expectedRevision, attendance, reason}`，原因须非空；只改变指定人次的出勤，记录旧值/新值/理由/时间，递增施测版本，不改身份、归属及旧成绩快照。结果 `ParticipantMutationResult.attendanceCorrection` 返回审计。同键同包先重放，不因重放时版本已旧拒绝。
- `POST /score-imports/{id}/refresh`：`{expectedImportRevision, expectedAssessmentRevision, baseScoreRevisionId}`。显式重新冻结当前参测/出勤，两个 CAS 都须匹配；base 必须仍是原预览基准且等于当前 active，不自动换 base。刷新递增导入修订/预览版本，保留适用人工校正，原承认失效。
- `POST /assessments/{id}/score-corrections` 是设计路径；既有 `/score-revisions/correct` 保持兼容。严格区分 recorded 数字与其他三态文本；不合法返回 422 定位错误，不返回非契约 500。
- `ScoreRevisionView.paperRevisionId` 必填，来自施测不可换卷的固定关系；数据库完整矩阵各行继续具有同固定卷复合约束。无需修改已登记0001–0007迁移。
- 题库 `QuestionContent.richContent?: RichContentV2 | null`：富内容存在时为权威，Markdown 为派生投影。保留旧 rich 却改 Markdown 拒绝；转回纯文本必须明确提交 `richContent: null`。含 rich 的纯文本拆合/AI应用须先明确转换，避免静默丢图/表/公式。资产按块引用、拥有者与真实字节散列校验，派生指纹包含富内容和真实资产散列；旧纯 Markdown 路径兼容。
- `GET /question-drafts/{id}/assets/{assetId}/content` 与 `GET /questions/{id}/assets/{assetId}/content`：只返回该对象实际引用且属于其导入/题目的受管图片，拒绝任意路径、跨对象和散列不符读取。前端从受控字节建立并释放 object URL。
- F20 已接名单 CSV/XLSX 映射、逐行 link/create/ignore、批次恢复与转班；原卷 DOCX 上传、完整来源块、手工题面/容器叶子/满分/知识点、结构化补录或依据排除、确认和建议任务。既有施测参测补录与出勤校正独立操作；所有固定修订读取自己的标题。共享富内容渲染器与公共任务观察 hook 各只有一份。
- 数字文本按 Decimal 的符号/系数/指数精确转换为百分之一分整数，不依赖全局运算精度。极端指数及超过两位有效小数返回定位 422；不会舍入为有效值或溢出 500。重复物理行指向同一人次时，两行都返回 `SCORE_ROW_DUPLICATE_PARTICIPANT` 并阻断确认，必须人工消歧。
- 成绩 PATCH 在预计算前和短写事务内均核原预览的施测修订及 active/base。过期上下文返回 409、导入行与预览版本不变；采用新参测集合必须调用明确 refresh。
- 正式题 PATCH 的资产/派生指纹预检在锁外；显式关联与继承到新修订的关联在同一 `PublicationCoordinator` 中复核并完成域提交。历史已确认关联只读；归档关联不能进入新修订，显式清空或替换后可提交。
- 心跳只能续尚未到期的当前 running 租约；已经过期返回 false、零修改，不能重新授权旧批。首次知识点/题库/原卷任务的 queued 收据均接受一次 claim 的 N/N+1，running 只观察 N，N+2 拒绝。
- G1题库查重追加 `question-surface-v1`，与已有`content_fingerprint`和`derived-v1`并存。富题面为权威，共同材料、题干、选项、公式/表格及真实图片字节参与题面身份；来源/随机块ID/答案不改变题面身份，答案差异仍显式进入冲突审核。预览、确认和显式去重采用相同口径；旧题缺新指纹时只读固定题面计算比较，不改写旧指纹。同包真正重复题保持原去重/审核语义，材料不同的两题可分别正式入库。
- 所有逻辑确认在结果未知时保留提交标识及深复制的完整请求，写控件锁定、只读对照可用，重试原包优先于最新视图校验；成绩摘要也展示原冻结版本。题库 `status=0` 明示结果未知，不能声称零入库；只有明确 `200 + failures` 才释放原载荷供教师修正，并按既有未登记语义保留提交标识。

## B4 学情、针对练习与受管导出

以下接口已有源码实现，B4 是否已独立验收及门禁完成只看 [CURRENT_STATUS](CURRENT_STATUS.md)。Python `contracts/b4.py` 与 TypeScript `contracts/b4.ts` 对应；完整 DTO、成功/失败样例及发布端口见 [B4 契约](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/B4-CONTRACT-v1.md)、v1.1/v1.2 修正及优先适用的 [v1.3 完整题号修正](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/B4-CONTRACT-v1.3-ERRATA.md)。`PracticeNode.questionNo` 是完整最终题号，换序不自动改号。外部 camelCase，分页 `{items,total,offset,limit}`，offset≥0、limit 1～200。

| 方法与路径（均为 `/api/v1`） | 输入与结果 |
| --- | --- |
| POST `/assessments/{id}/analysis-runs` | `{submissionId,scoreRevisionId,selectedParticipantIds,ruleCode:"any_loss_v1"}`；202 固定 run/score/paper/inputHash 与 teaching analysis 任务收据 |
| GET `/analysis-runs` | 可选 `assessmentId/scoreRevisionId` + 分页 |
| GET `/analysis-runs/{id}` | 固定来源、显式选人快照、知识点与六态任务、reportReady |
| GET `/analysis-runs/{id}/classes`、`students`、`evidence` | 可选 `classId/participantId/knowledgePointId` + 分页；非 ready 不当空报告 |
| POST/GET `/analysis-runs/{id}/notes` | 追加 `{submissionId,participantId?,knowledgePointId?,note}`；或分页只读备注 |
| POST/GET `/practice-sets` | 建立 `{submissionId,analysisRunId,title,targetKnowledgePointIds,constraints}`；或 `analysisRunId` + 分页 |
| GET `/practice-sets/{id}` | 当前草稿/审核版及固定修订历史 |
| GET `/practice-sets/{id}/revisions/{revisionId}` | 固定快照，不替换为当前题库版本 |
| POST `/practice-sets/{id}/suggestions` | `{expectedRevision,constraints}`；正式固定题、真实覆盖及缺口，不调用模型 |
| PATCH `/practice-sets/{id}/draft` | `{submissionId,expectedRevision,items,constraints}`；submissionId必填1～128字符；显式节点来源、完整题号、计分叶、Decimal满分及正式KP |
| POST `/practice-sets/{id}/review` | `{submissionId,expectedRevision}`；锁外预检、发布锁内复核、封存审核快照 |
| POST `/practice-sets/{id}/revisions` | `{submissionId,sourceRevisionId}`；从固定审核版新建草稿，旧版不改 |
| POST `/practice-sets/{id}/revisions/{revisionId}/exports` | `{submissionId,variant,assessmentId}`；202 export 收据；variant=student/teacher 时 assessmentId=null，score_template 须为本版实际转换施测 |
| GET 同一 exports 路径 | 成功产物分页，metadata 含固定修订/真实名单施测/fileAsset/hash/字节数/下载 URL |
| GET `/practice-sets/{id}/revisions/{revisionId}/assets/{sha}` | 仅该固定修订声明的受管图片 |
| POST `/practice-sets/{id}/revisions/{revisionId}/assessments` | `{submissionId,title,heldOn,classIds,participants}`；同事务固定卷、真实 T30 参测与 provenance 映射，姓名学号服务端读取 |
| GET `/export-artifacts/{id}`、`/{id}/download` | 元数据核同owner、固定审核版、任务succeeded；下载另核受管资产身份、实际hash与字节数后返回真实文件，no-store/nosniff |

学情按该 confirmed score 自己的 participant/item 快照与完整四态矩阵冻结。recorded 包括 0；失分优先标需巩固，informationIncomplete 独立；分母为本 KP 至少一格 recorded 的被选唯一学生，0 分母 ratio=null。总分只在全部计分叶 recorded 时返回，不因多 KP 重复累加。旧快照没有班名时 `className=null` 并标“该成绩未记录班名”。ready 输入/结果/全题证据不可变，备注独立追加。

练习选题约束不会自动放宽；题型未知的原卷仅在排原题比较中使用明确的未知规则，不伪造原题型。缺题需教师主动走现题库候选→人工保存→审核→正式确认，再重新选择。审核及子表封存，改动新草稿。学生 DOCX 不含答案解析，教师版标缺答案；模板在接受导出时冻结实际参测及固定卷叶映射，空白分数不补0。回流沿用 T60 确认新成绩，再创建 T70 新报告。

题库与教学业务保留各自既有归属标识；标准装配显式将实际题库服务的 owner 注入练习固定题读取，建议、保存和审核复核使用相同的题库归属。单题读取、编辑与归档均拒绝其他归属题，返回 404 `QUESTION_NOT_FOUND`；不改写旧题的 owner，也不放宽固定修订读取器的精确归属判定。

页面导航沿用真实题库确认接口，确认成功后返回 `/question-bank?tab=library`，带练习上下文时另带编码的 `returnPracticeSetId`。`tab`受限为`imports/library/generation`；显式查询优先，旧`#library/#generation`兼容。`generation`仅打开补题面板，教师仍须明确提交后才调用模型；无效或重复页面查询显示错误，不影响HTTP业务契约。

分析和导出复用六态 JobEngine；计算/渲染/IO 在事务及发布锁外，结果与任务 succeeded 用原租约同事务 CAS。提交 `(owner,operation,submissionId)` 同包先重放、异包409；版本冲突409带依据，422定位 issues；失败不返回假产物。教学库新增 `0008/0009`；四库保持，跨题/KP为服务校验+固定快照，本段描述B4的0008/0009，B5追加结构见下文0010；验收状态以CURRENT_STATUS为准。`ZQKY_ENV=test` 下配置 credentials_file=None。

2026-10-03 G2保存契约增量：草稿PATCH的operation为`practice.draft:{practiceSetId}`；同owner/operation/submissionId原包先于当前CAS/state/外部引用检查返回原`PracticeSetView`，标记`replayed=true`，不会改成最新稿。后续另存后重放旧包仍返回旧receipt，GET当前稿保持新版本。同身份异包409`SUBMISSION_CONFLICT`；新ID旧CAS409`REVISION_CONFLICT`/`details.currentRevision`；无ID422。没有旧无ID兼容分支。保存及原receipt同teaching事务；内部审核仅验证内容，不另造保存提交。此段描述当前实现契约，阶段验收以CURRENT_STATUS为准。

## B5 后台教案与固定学情建议接口

源码契约/路由与运行装配已建立；整体独立验收和适用门禁状态只看 [CURRENT_STATUS](CURRENT_STATUS.md)。Frozen Python/TS DTO、严格限制、12路由静态OpenAPI与示例见 [B5契约v1](qa/TEACHING-LOOP-G2-B5-20261003/B5-CONTRACT-v1.md)，追加只读来源口见 [CTRL补充契约](qa/TEACHING-LOOP-G2-B5-20261003/B5-CTRL-SOURCE-RUNTIME-DELTA-v1.md)。静态示例不是实跑收据。

| 方法与路径（统一 /api/v1 前缀） | 真实服务用途 |
| --- | --- |
| GET/POST `/lesson-plans` | 分页后台教案 / 创建v1正文与明确班级学科、可空固定学情上下文 |
| POST `/lesson-plans/import-local` | 教师主动导入完整合法DraftEnvelopeV1；旧键原字节保留 |
| POST `/lesson-plans/evidence/verify` | 生产RagV2核选定原文区间、hash、scope并生成可核对固定refs |
| GET `/lesson-plans/{id}` | 当前固定修订、server CAS与冻结上下文 |
| PATCH `/lesson-plans/{id}/draft` | 幂等正文另存 / 同正文上下文来源意义去重 / CAS冲突保稿 |
| GET `/lesson-plans/{id}/revisions`、`/{revisionId}` | 不可变历史分页 / 精确历史正文及独立审核状态 |
| POST `/lesson-plans/{id}/proposals` | 单班级/KP、固定ready报告/教材refs及可选confirmed题/reviewed练习生成建议任务 |
| GET `/lesson-plans/{id}/proposals/{proposalId}` | 精确候选、五整字段diff、四阶段分钟预算与来源 |
| POST `/lesson-plans/{id}/proposals/{proposalId}/apply` | 教师选部分完整字段、当前base/CAS重新核对，单次终结并新修订 |
| POST `/lesson-plans/{id}/proposals/{proposalId}/reject` | 幂等终结候选，不改正文 |
| GET `/confirmed-question-revisions?subjectId=...&offset=0&limit=50` | 按真实题库owner分页读取confirmed固定revision ID；未知学科真实空集，依赖缺失503 |

写操作皆有submissionId，保存/应用有expectedRevision，生成同时绑定baseRevisionId/baseServerRevision。成功原包重放在后来CAS/外部来源预检之前，异包409，版本冲突409保留details.currentRevision；教案请求非法422 VALIDATION_ERROR、业务422 LESSON_INVALID等、413超2MiB，错误不回显学生个人信息。没有归档/审核HTTP端点，保存不偷偷审核。

正文仍11字段v1，ProcessItem仍id/stage/design/secondary；外层protocolVersion2、环节分钟为独立processMetadata。五个AI可改整字段为coreCompetencies/keyPoints/teachingDesign/process/exercises；教师标题/课时/课型/反思不属于patch。后台缓存按document ID新键，旧zhiqikeyuan:lesson-plan:v1不与后台共写。

任务沿用teaching/lesson_generation与公共六态workflow-jobs观察/取消/显式retry。首次/重试均核冻结profile与指纹；只有候选发布与succeeded同事务，教师应用才另存正文。模型最终请求仅单班级/KP匿名固定计数与明确教学文本；已知个人信息在各来源和最终三协议wire阻断，不能据此宣称普遍匿名化或人工教学质量通过。输入128000 UTF-16/256KiB，输出256KiB/最多16384token，校验失败/截断/不可用不回退规则或静默裁切。

教学库只追加0010的lesson_plans/lesson_plan_revisions/lesson_revision_reviews/lesson_generation_inputs/lesson_ai_proposals/lesson_proposal_decisions，真owner/基线/任务/报告FK、不可变trigger与CAS保护，0001～0009原声明保持。跨教材/KP/题库由生产读取口与固定快照验证，不伪造跨库FK；版本感知体检和全四库离线恢复包括新增表及受管资产。
