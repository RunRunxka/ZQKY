# 后端服务（D04：含模型设置、统一 Provider 适配层与流式对话）

本目录是可运行的 FastAPI 本机服务：真实 `/api/v1/health`、`/api/v1/capabilities`、模型连接/模型配置 CRUD 与真实连接测试、统一错误信封、本机访问防护与后端测试。不连接任何数据库或 Redis；学习问答对话（D04）、模板渲染（D05–D07）等能力按计划接入，未实现能力在 `/capabilities` 如实报告 `planned`。

## 启动与测试（项目根执行）

```powershell
npm.cmd run setup:api   # 首次：uv sync 创建 .venv 并安装锁定依赖
npm.cmd run dev:api     # 启动 http://127.0.0.1:8000
npm.cmd run test:api    # 运行后端 pytest
```

服务只监听本机回环地址；开发端口 8000，后端测试约定端口 8001。前端由 Next 同源代理转发 `/api/v1/*` 到该服务（见 apps/web/next.config.ts），浏览器不需要直连 8000。前端单独可用：后端停止时教案工作台与所有规划页照常工作。

## 目录

```text
app/
  main.py            应用工厂、生命周期、501 占位路由、统一错误处理
  api/v1/            health、capabilities、model-connections、model-profiles
  core/config.py     环境变量配置（回环校验、来源列表、数据目录）
  core/http_safe.py  Host/Origin 访问防护中间件
  core/secrets.py    进程内凭证存储（只写入、不回显、重启失效）
  providers/llm/     统一 Provider 基类与 openai-chat / openai-responses / anthropic-messages 适配器、工厂
  repositories/      模型配置 JSON 仓储（原子写、revision 冲突检测）
  schemas/           能力状态、错误信封、模型设置模型与请求体
tests/               health、capabilities、防护、501、配置、Provider 协议、设置接口、仓储共 52 项测试
```

## 数据与凭证

- 非敏感配置：项目根 `.local-data/model-config.json`（已 gitignore，`ZQKY_DATA_DIR` 可覆盖）。原子写入；损坏时服务报 `CONFIG_CORRUPTED` 并拒绝读取，不会自动覆盖，请人工备份修复。
- 凭证（API Key）：只保存在当前服务进程内存（`core/secrets.py`），接口只回 `hasCredential`，不回显明文，不写入磁盘/日志；后端重启后需在设置页重新填写。磁盘加密凭证存储为后续增强。

## 接口状态

- `GET /api/v1/health`：真实可用性，返回 `status/service/apiVersion/time`，不含任何配置。
- `GET /api/v1/capabilities`：能力清单；`model_settings=ready`，其余 `planned`。
- `GET/POST /api/v1/model-connections`、`PUT/DELETE /api/v1/model-connections/{id}`：模型连接管理；创建/更新时 `apiKey` 只写入进程；被模型配置引用的连接删除返回 409。
- `GET/POST /api/v1/model-profiles`、`PUT/DELETE /api/v1/model-profiles/{id}`：模型配置管理（协议、模型 ID、上下文/输出上限、`supportedParams`、能力证据）。
- `POST /api/v1/model-profiles/{id}/test`：发送一次小额真实请求；上游成败均返回 200 `ok:true/false`，成功后该配置 `chat` 证据更新为 `verified`。
- `POST /api/v1/chat/stream`：规范化 SSE 流式对话（事件协议见 docs/API.md）；流前失败返回 HTTP 错误，流中失败发 `error` 事件，客户端断开即取消上游连接。
- 其余 `/api/v1/*`：返回 501 `FEATURE_NOT_IMPLEMENTED` 信封；前端不得自动调用。
- 错误信封：`code、message、requestId、retryable、details?`，同时带 `X-Request-Id` 响应头。Provider 层错误码：`UNSUPPORTED_PROTOCOL`、`UNSUPPORTED_PARAMETER`、`MODEL_NOT_CONFIGURED`、`UPSTREAM_AUTH_FAILED`、`RATE_LIMITED`、`UPSTREAM_TIMEOUT`、`UPSTREAM_UNREACHABLE`、`UPSTREAM_ERROR`。

错误行为已实测：非允许 Origin → 403 `FORBIDDEN_ORIGIN`；非回环 Host → 400 `INVALID_HOST`；未知路径 → 404 `NOT_FOUND`；revision 过期 → 409 `REVISION_CONFLICT`。后端停止时，Next 代理返回 500（纯文本），前端适配器将其转换为 `SERVICE_UNAVAILABLE`（“后端服务不可用。”），不会伪造成功。

技术栈：Python 3.12（uv 托管 CPython 3.12.14）、FastAPI 0.141.1、Uvicorn 0.52.4、Pydantic 2.13.5；测试 Pytest 9.1.1 + httpx2 2.12.0 + pytest-asyncio 1.4.0（starlette 1.6.0 的 TestClient）。版本以 `uv.lock` 为准。Provider 接口设计参考 DeepTutor v1.6.4（Apache-2.0，固定提交 `93df3d48…`），为本项目自有实现。

## 运行参数（环境变量，均可省略）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ZQKY_API_HOST` | `127.0.0.1` | 只允许回环地址，其余值启动即拒绝 |
| `ZQKY_API_PORT` | `8000` | 监听端口 |
| `ZQKY_ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://127.0.0.1:5174` | 允许的浏览器来源 |
| `ZQKY_ENV` | `development` | 环境名称（仅用于日志） |

示例见 `.env.example`。没有密钥类配置；凭证由设置页提交并只保存在进程内存（见“数据与凭证”）。
