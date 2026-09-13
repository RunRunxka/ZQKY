# 接口与模块边界

更新：2026-09-13。本文为当前契约；进度、代码审查与验收只维护在 [STATUS](STATUS.md)。前端 TypeScript 服务与真实 HTTP 接口分别列明。

**实施责任：** 模型增量合同由外部队长按STATUS的MODEL-EXEC v3和PROJECT_GUIDE的D1–D16直接定稿并落地，Python schemas、TS contracts/services、响应投影与必要路由挂载无需本Codex代写。draft-2仍是提案，本节现行接口不因权限转交自动变为新合同；实施者完成后同步实际字段与测试证据。

### contract-v1 已落地（2026-09-13）

外部队长已按 MODEL-EXEC v3 完成 contract-v1 并落地；以下为本节新增的现行接口与字段。
实现文件：`apps/api/app/providers/llm/registry.py`（38 条单一真值）、`.../factory.py`（按 backend 分派）、
`app/services/model_config_service.py`（跨 .env/JSON 补偿）、`app/services/model_auth.py`（认证状态机）。
冻结散列与 D1–D16 落地位置见 `_work/model-providers-v1/contract-v1.md`（本机证据，不随 Git）。

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

**跨存储一致性（R-01，未关闭）**：连接的更新/删除在仓储同一临界区内完成 revision 校验、文档变更与
凭证写入（`ModelConfigRepository.run_atomic`）；配置落盘失败按快照回滚凭证，删除时凭证清理失败则整体不删，
可安全重试。已自检通过，仍需独立复验确认。

## 后端凭证文件

- 正式 FastAPI 在应用启动生命周期读取 `apps/api/.env`；仅凭证项使用此文件，不将其读入前端。导入 `create_app` 不读取用户凭证；测试注入临时目录和 SecretStore。
- 设置页原创建/编辑连接 API 不变，非空 `apiKey` 写入 `.env` 的 `ZQKY_API_KEY_<连接ID>`；空值仍表示保持原凭证。每个连接独立映射，模型共用所属连接的 Key。写入采用临时文件、flush/fsync、原子替换，保留其他行；删除连接会移除对应文件项。
- 可手动编辑该变量（原样字符串、单引号或 JSON 双引号字符串均支持；不进行 shell 展开或变量插值），然后重启 API。进程环境变量在启动时覆盖同名文件项；Windows 环境变量名大小写不影响小写连接 ID 匹配。
- 连接响应仍不回显密钥，新增非敏感 `credentialEnvName`，`credentialScope` 为 `env-file`（正式持久化存储）或 `process`（注入的内存存储）。`.env`、临时 `.env.*.tmp` 均由既有 `.gitignore` 排除；仅无密钥 `.env.example` 入库。
- 文件读写失败返回 `CREDENTIAL_STORAGE_ERROR`，不回显凭证/底层异常。更新先校验 revision 与字段，凭证写失败不提交本次连接配置变更。跨文件补偿已按 contract-v1 落地（R-01）：更新时先快照凭证、配置保存失败则回滚凭证；删除时配置删除后清理凭证，清理失败明确报错而非静默留孤儿；`credentialAction:"clear"` 提供独立清除动作（R-08）。相关回归见 `apps/api/tests/test_model_contract_v1_api.py`。没有数据库或第二套业务后端。
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

模型 JSON 配置及聊天历史不存密钥；凭证仅在服务端 SecretStore 和忽略的 .env 文件。历史实现依据见 [review 记录](archive/PROJECT_HISTORY.md#source-4)。

## 教案与公共壳 TypeScript 接口

以下是前端TypeScript接口，不是已部署HTTP服务。

| 接口 | 用途 |
| --- | --- |
| `LessonPlanWorkspace({services?})` | 主工程嵌入教案编辑器 |
| `LessonPlanServices.fillProvider` | 可替换要求解析策略 |
| `LessonPlanServices.repository` | 可替换草稿存储 |
| `LessonPlanServices.onChange` | 持久化成功后的变化通知 |
| `FillProvider.parse(input, signal?)` | 返回Promise，内容为patch、warnings、source |
| `DraftRepository.load()` | 同步或异步返回DraftEnvelope或null |
| `DraftRepository.save(envelope)` | 同步或异步保存，失败抛出/拒绝 |
| `WorkspaceShell.beforeNavigate()` | 路由切换前等待模块保存，失败保持当前页 |

教案数据类型在模块model/types.ts，跨模块NavigationItem在公共contracts。原 `window.__ZQKY_HOST__` 与导航CustomEvent不作为正式集成接口；导航由公共壳统一调用Next路由。

`DraftEnvelope={schemaVersion:1,revision:number,updatedAt:ISO UTC,data:LessonPlanData}`。字段和JSON格式与旧版兼容。传入自定义服务时保持引用稳定；服务端repository须自行绑定文档ID、会话和冲突语义，不能把本地revision直接当成跨用户授权依据。

默认仅使用规则填充和本地存储，页面不请求后台。可选 `HttpFillProvider` 已保留，但没有默认启用。

## 后端已实现 HTTP 接口

FastAPI 服务位于 apps/api，仅监听 127.0.0.1:8000；浏览器经 Next 同源代理访问 `/api/v1/*`（apps/web/next.config.ts rewrites，目标可用 `ZQKY_API_ORIGIN` 覆盖）。启动与测试见 apps/api/README.md，根脚本 `npm run setup:api / dev:api / test:api`。

| 方法与路径 | 状态 | 说明 |
| --- | --- | --- |
| GET `/api/v1/health` | 已实现 | 返回 `status/service/apiVersion/time`，不含配置内容 |
| GET `/api/v1/capabilities` | 已实现 | 能力清单；`model_settings`、`chat` 为 `ready`，组卷/模板/教材库/题库/RAG/Agent/MCP/Skills 为 `planned` |
| GET/POST `/api/v1/model-connections` | 已实现 | 连接列表/创建；非空 `apiKey` 经 SecretStore 持久化到 .env，响应只返回凭证状态和变量名，不回显 Key |
| GET `/api/v1/model-catalog` | 已实现 | 一次读取带 revision 的连接/模型/默认模型目录 |
| GET `/api/v1/model-connections/{id}/models` | 已实现 | 使用服务端凭证发现上游模型；不修改目录 |
| PUT `/api/v1/model-defaults` | 已实现 | 更新默认模型，expectedRevision 冲突返回409 |
| PUT/DELETE `/api/v1/model-connections/{id}` | 已实现（D03） | 更新（支持 `expectedRevision`，冲突 409）；被模型配置引用时删除返回 409 `CONFLICT` |
| GET/POST `/api/v1/model-profiles` | 已实现（D03） | 模型配置（模型 ID、上下文/输出上限、`supportedParams`、能力证据）列表/创建 |
| PUT/DELETE `/api/v1/model-profiles/{id}` | 已实现（D03） | 更新/删除；能力证据取值 `verified/claimed/unknown` |
| POST `/api/v1/model-profiles/{id}/test` | 已实现（D03） | 真实小额上游请求；无论上游成败都返回 200 `ok:true/false`，成功后 `chat` 证据更新为 `verified` |
| POST `/api/v1/chat/stream` | 已实现（D04） | 规范化 SSE 流式对话（见下方事件协议）；客户端断开时取消上游连接 |
| 其余 `/api/v1/*` | 通配占位 | GET/POST/PUT/DELETE/PATCH 返回501 `FEATURE_NOT_IMPLEMENTED`，不能假成功 |

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

下表保留历史 D 阶段映射；实际排期以 STATUS 为准。这些 `/api/v1/*` 草案由通配占位返回501，不代表具体业务接口已实现。

| 方法和路径 | 用途 | 实施阶段 |
| --- | --- | --- |
| POST `/api/v1/templates/inspect` | DOCX 上传检查与临时上传 ID | D05–D07 |
| POST/GET `/api/v1/exports`、cancel、artifacts | 渲染任务与受控下载 | D07 |
| POST `/api/v1/lesson-plans/fill` | 生成填充建议 | 随 D08 评估 |
| GET/POST/PUT `/api/v1/lesson-plans(/{id})` | 未来多教案服务端存储 | 未排期 |
| 教材库/题库/RAG/Agent/MCP/Skills 相关 | 仅契约规划 | F 系列 |

填充类接口实施时沿用既定约束：同源会话、JSON 请求、30 秒默认超时，校验 patch 与 warnings，不在错误后回退规则实现。

## 后端接入前置条件

后续多用户/任务服务接入前，先确定用户和文档ID、鉴权、版本冲突、任务状态、数据保留及错误规范。FastAPI 已有接口由服务端声明；当前前端契约（`apps/web/src/contracts/api.ts`）为手写对齐，未宣称由 OpenAPI 生成。health、capabilities、模型管理和聊天为实际实现；其他功能以实际路由登记和能力状态为准。

资料、问答、练习、笔记等全项目接口仍参考原项目规划，待具体任务再细化。模型密钥与数据库连接仅放服务端，浏览器不接收供应商凭证。
