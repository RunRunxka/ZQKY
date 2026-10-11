# API 契约（最小骨架版）

更新：2026-10-11（推倒重做）。未列出的 `/api/v1/*` 一律返回 501 `FEATURE_NOT_IMPLEMENTED`。

## 公共

| 方法和路径 | 用途 |
| --- | --- |
| GET `/api/v1/health` | 健康检查 |
| GET `/api/v1/capabilities` | 能力清单（当前只报 model_settings / chat / agent 三项，均为 ready；不冒充未实现能力） |

## 模型配置

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/model-providers` | 供应商目录（38 条注册表） |
| `/api/v1/model-connections`（GET/POST/PUT/DELETE） | 连接 CRUD；凭证经 SecretStore（响应只返回凭证状态，不回显明文） |
| `/api/v1/model-connections/{id}/auth/{start,cancel,logout}` | OAuth 受管认证（Codex/Copilot） |
| `/api/v1/model-catalog`、`/model-defaults`、`/model-connections/{id}/models` | 模型清单与默认配置 |
| `/api/v1/model-profiles`（CRUD + `/{id}/test`） | 模型档案与真实连接测试 |

## 对话与 Agent

| 方法和路径 | 用途 | 事件 / 说明 |
| --- | --- | --- |
| POST `/api/v1/chat/stream` | 普通对话 SSE（三协议适配） | `message.start / text.delta / reasoning.delta / usage / message.end / error` |
| POST `/api/v1/agent/stream` | Agent 对话 SSE（LangGraph 编排） | `message.start / text.delta / tool.call / tool.result / wait-confirm / message.end / error`；`attachments` 支持上传引用；`reasoningEffort` 覆盖思考强度 |
| POST `/api/v1/agent/confirm` | 写操作确认（`Command(resume)` 恢复中断） | `submissionId` 幂等 |
| POST `/api/v1/agent/upload` | 上传落受管 blob（内容寻址 sha256） | multipart；上限 100 MiB |

**模型接入**：Agent 用 LangChain 官方 provider 包；凭证只经后端 `SecretStore` **显式注入**
（本地免 Key 用占位符），构造前断言 `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 进程环境未设置；
受管认证（Codex/Copilot/CodeBuddy）暂不可用于 Agent（`AGENT_MODEL_UNSUPPORTED`），可用于
`/chat/stream` 直连。Agent 会话/中断状态经 checkpointer 落 `data/agent/agent_checkpoints.sqlite3`。
