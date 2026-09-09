# 2026-09-09 后端凭证文件（优先于下方历史进程凭证说明）

- 正式 FastAPI 在应用启动生命周期读取 `apps/api/.env`；仅凭证项使用此文件，不将其读入前端。导入 `create_app` 不读取用户凭证；测试注入临时目录和 SecretStore。
- 设置页原创建/编辑连接 API 不变，非空 `apiKey` 写入 `.env` 的 `ZQKY_API_KEY_<连接ID>`；空值仍表示保持原凭证。每个连接独立映射，模型共用所属连接的 Key。写入采用临时文件、flush/fsync、原子替换，保留其他行；删除连接会移除对应文件项。
- 可手动编辑该变量（原样字符串、单引号或 JSON 双引号字符串均支持；不进行 shell 展开或变量插值），然后重启 API。进程环境变量在启动时覆盖同名文件项；Windows 环境变量名大小写不影响小写连接 ID 匹配。
- 连接响应仍不回显密钥，新增非敏感 `credentialEnvName`，`credentialScope` 为 `env-file`（正式持久化存储）或 `process`（注入的内存存储）。`.env`、临时 `.env.*.tmp` 均由既有 `.gitignore` 排除；仅无密钥 `.env.example` 入库。
- 文件读写失败返回 `CREDENTIAL_STORAGE_ERROR`，不回显凭证/底层异常。更新先校验 revision 与字段，凭证写失败不提交本次连接配置变更。没有数据库或第二套业务后端。
- 主聊天仅实例化真实服务、真实 IndexedDB 会话库；移除模拟生成与免密伪模型。SSE 事件名与三协议适配保持原契约。

# 2026-09-06 问答与模型目录增补（历史契约说明）

- `GET /api/v1/model-catalog`：原子读取 `{revision, defaultChatProfileId, connections, profiles}`。连接只返回 `hasCredential`；模型包含 `params` 和关联连接可用状态。
- `GET /api/v1/model-connections/{id}/models`：后端使用已保存连接和进程凭证发现列表，返回 `{models:[{id}]}`。只读、去重，不写入模型或推断能力。区分认证、超时、接口不支持及格式错误；空数组为成功但无可选项。
- `PUT /api/v1/model-defaults`：`{modelProfileId:string|null, expectedRevision:number}`，返回更新目录；版本过期为 409 `REVISION_CONFLICT`。
- 模型创建/修改新增 `params`，只接受 `supportedParams` 已声明且数值有效的参数；上下文/输出上限修改接受 null 清空。人工提交 verified 会降为 claimed。
- 既有连接/模型 PUT 保留 `expectedRevision`，DELETE 新增可选同名 query 参数；新前端删除携带版本。旧调用方可继续使用原接口。新增记录为追加，不覆盖已有模型，同连接相同 modelId 拒绝重复。
- `POST /api/v1/model-profiles/{id}/test` 新增 `stream:boolean`；流式结果额外包含 `stream:{chunks,firstTextMs,lastTextMs}`。普通/流式证据分别写入 chat/stream；版本变更后旧测试不覆盖新配置。该测试端点返回最终测试报告，不是聊天 SSE。
- 聊天仍使用 `POST /api/v1/chat/stream`，已保存参数作为默认值。上游连接建立后 start，随后 text/usage/end；未正常终止、空回答或协议失败为脱敏错误。主动停止逐层关闭资源。
- IndexedDB 会话增加 `schemaVersion:1`、revision、draft、modelProfileId；消息记录 modelProfileId、modelLabel、replyToId、superseded。旧记录读取补默认值。保存/删除在同一事务检查预期 revision，事务提交才返回成功。

配置及历史均不存密钥。JSON 配置与数据库边界不变。行为与验收见 [review 记录](archive/PROJECT_HISTORY.md#source-4)。下方 D02–D04 条目作为历史说明保留。

# 接口与模块边界

## 当前实际可调用能力

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

## 后端已实现接口（D02–D04，2026-09-06）

FastAPI 服务位于 apps/api，仅监听 127.0.0.1:8000；浏览器经 Next 同源代理访问 `/api/v1/*`（apps/web/next.config.ts rewrites，目标可用 `ZQKY_API_ORIGIN` 覆盖）。启动与测试见 apps/api/README.md，根脚本 `npm run setup:api / dev:api / test:api`。

| 方法与路径 | 状态 | 说明 |
| --- | --- | --- |
| GET `/api/v1/health` | 已实现 | 返回 `status/service/apiVersion/time`，不含配置内容 |
| GET `/api/v1/capabilities` | 已实现 | 能力清单；`model_settings`、`chat` 为 `ready`，组卷/模板/教材库/题库/RAG/Agent/MCP/Skills 为 `planned` |
| GET/POST `/api/v1/model-connections` | 已实现（D03） | 连接列表/创建；创建时 `apiKey` 只写入进程内 SecretStore，响应仅含 `hasCredential` |
| PUT/DELETE `/api/v1/model-connections/{id}` | 已实现（D03） | 更新（支持 `expectedRevision`，冲突 409）；被模型配置引用时删除返回 409 `CONFLICT` |
| GET/POST `/api/v1/model-profiles` | 已实现（D03） | 模型配置（模型 ID、上下文/输出上限、`supportedParams`、能力证据）列表/创建 |
| PUT/DELETE `/api/v1/model-profiles/{id}` | 已实现（D03） | 更新/删除；能力证据取值 `verified/claimed/unknown` |
| POST `/api/v1/model-profiles/{id}/test` | 已实现（D03） | 真实小额上游请求；无论上游成败都返回 200 `ok:true/false`，成功后 `chat` 证据更新为 `verified` |
| POST `/api/v1/chat/stream` | 已实现（D04） | 规范化 SSE 流式对话（见下方事件协议）；客户端断开时取消上游连接 |
| 其余 `/api/v1/*` | 已挂载占位 | 501 `FEATURE_NOT_IMPLEMENTED`，前端不得自动调用 |

错误信封统一为 `code、message、requestId、retryable、details?`（details 只含脱敏展示内容），并附 `X-Request-Id` 头。已实测行为：非允许 Origin → 403 `FORBIDDEN_ORIGIN`；非回环 Host → 400 `INVALID_HOST`；未知路径 → 404 `NOT_FOUND`；参数错误 → 422 `INVALID_REQUEST`。后端停止时 Next 代理返回 500 纯文本，前端 `services/api-client.ts` 将其与网络失败统一转换为 `ApiError('SERVICE_UNAVAILABLE')`，不会出现假成功。

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

已锁定的错误码（随任务扩充）：MODEL_NOT_CONFIGURED、UNSUPPORTED_PROTOCOL、UPSTREAM_AUTH_FAILED、RATE_LIMITED、CONTEXT_TOO_LARGE、UPSTREAM_TIMEOUT、FEATURE_NOT_IMPLEMENTED、TEMPLATE_UNSUPPORTED、RENDER_FAILED、REVISION_CONFLICT、SERVICE_UNAVAILABLE、REQUEST_FAILED、INVALID_REQUEST、INVALID_HOST、FORBIDDEN_ORIGIN、NOT_FOUND、METHOD_NOT_ALLOWED、EMPTY_RESPONSE、STREAM_INTERRUPTED。

## 后续 HTTP 草案（未实现）

下表按 IMPLEMENTATION_PLAN 的阶段标注；实现前这些路由实际返回 501，下表仍是设计而非现状。

| 方法和路径 | 用途 | 实施阶段 |
| --- | --- | --- |
| POST `/api/v1/chat/stream` | 规范化 SSE 对话 | D04 |
| POST `/api/v1/templates/inspect` | DOCX 上传检查与临时上传 ID | D05–D07 |
| POST/GET `/api/v1/exports`、cancel、artifacts | 渲染任务与受控下载 | D07 |
| POST `/api/v1/lesson-plans/fill` | 生成填充建议 | 随 D08 评估 |
| GET/POST/PUT `/api/v1/lesson-plans(/{id})` | 未来多教案服务端存储 | 未排期 |
| 教材库/题库/RAG/Agent/MCP/Skills 相关 | 仅契约规划 | F 系列 |

填充类接口实施时沿用既定约束：同源会话、JSON 请求、30 秒默认超时，校验 patch 与 warnings，不在错误后回退规则实现。

## 后端接入前置条件

确定用户和文档ID、鉴权、服务端版本号、任务状态、数据保留及错误规范后，再建立OpenAPI并生成HTTP类型。当前前端契约（`apps/web/src/contracts/api.ts`）为手写对齐，没有声明“类型已由OpenAPI生成”；health 与 capabilities 为真实实现，其余路由不提供假成功响应。

资料、问答、练习、笔记等全项目接口仍参考原项目规划，待具体任务再细化。模型密钥与数据库连接仅放服务端，浏览器不接收供应商凭证。
