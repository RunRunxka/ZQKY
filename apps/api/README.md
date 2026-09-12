# 后端服务（D04：含模型设置、统一 Provider 适配层与流式对话）

本目录是可运行的 FastAPI 本机服务：health、capabilities、模型连接/模型配置 CRUD、目录/默认模型、连接测试与三协议真实流式问答已实现；提供统一错误信封与本机访问防护。不连接数据库或 Redis；模板渲染、RAG 等未实现能力在 capabilities 报告 planned。真实供应商验收与本地链路测试分开，见 [STATUS](../../docs/STATUS.md)。

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
  api/v1/            health、capabilities、模型管理/目录、聊天 SSE
  core/config.py     环境变量配置（回环校验、来源列表、数据目录）
  core/http_safe.py  Host/Origin 访问防护中间件
  core/secrets.py    服务端凭证存储（.env 持久化、不回显；测试可注入内存）
  providers/llm/     统一 Provider 基类与 openai-chat / openai-responses / anthropic-messages 适配器、工厂
  repositories/      模型配置 JSON 仓储（原子写、revision 冲突检测）
  schemas/           能力状态、错误信封、模型设置模型与请求体
tests/               health、capabilities、防护、配置/凭证、Provider 协议、SSE、接口与仓储回归
```

## 数据与凭证

- 非敏感配置：项目根 `.local-data/model-config.json`（已 gitignore，`ZQKY_DATA_DIR` 可覆盖）。原子写入；损坏时服务报 `CONFIG_CORRUPTED` 并拒绝读取，不会自动覆盖，请人工备份修复。
- 凭证（API Key）：统一经 `core/secrets.py` 写入忽略的 `apps/api/.env`，变量为 `ZQKY_API_KEY_<连接ID>`；应用启动读取，手动编辑后需重启 API。响应只给 `hasCredential`、`credentialScope`、`credentialEnvName`，不回显密钥，不进日志/模型配置 JSON/Git。详见 [当前 API 契约](../../docs/API.md)。

## 接口契约

当前端点、请求/响应、SSE 事件、错误码、凭证作用域和未实现接口只维护在 [API 契约](../../docs/API.md)，本文件不重复接口状态，避免两处漂移。实现进度、代码审查与实际验证只看 [STATUS](../../docs/STATUS.md)。`GET /api/v1/capabilities` 必须按源码真实报告；当前已知文案差距记录在 STATUS R-12。

技术栈：Python 3.12（uv 托管 CPython 3.12.14）、FastAPI 0.141.1、Uvicorn 0.52.4、Pydantic 2.13.5；测试 Pytest 9.1.1 + httpx2 2.12.0 + pytest-asyncio 1.4.0（starlette 1.6.0 的 TestClient）。版本以 `uv.lock` 为准。Provider 接口设计参考 DeepTutor v1.6.4（Apache-2.0，固定提交 `93df3d48…`），为本项目自有实现。

## 运行参数（环境变量，均可省略）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ZQKY_API_HOST` | `127.0.0.1` | 只允许回环地址，其余值启动即拒绝 |
| `ZQKY_API_PORT` | `8000` | 监听端口 |
| `ZQKY_ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://127.0.0.1:5174` | 允许的浏览器来源 |
| `ZQKY_ENV` | `development` | 环境名称（仅用于日志） |

示例见 `.env.example`，不得填入真实密钥后提交。凭证由设置页写入 .env，也可按连接编辑窗口显示的变量名手动配置；启动时同名进程环境变量优先于文件。运行配置与凭证文件的读取边界见 [API](../../docs/API.md)。
