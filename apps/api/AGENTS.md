# 后端开发规则

先读根 AGENTS.md。本文件补充 apps/api 范围的规则。

- 后端是本机单用户服务，只监听 `127.0.0.1`：开发 8000，后端测试 8001；不允许配置对外地址（`Settings` 会拒绝非回环 host）。
- 依赖只用 uv 管理：`pyproject.toml` + `uv.lock` 是唯一依赖来源；改依赖必须 `uv lock`/`uv add` 并记录版本。不把 Python 加入 npm workspaces。
- 本地存储（2026-09-28 RAG-REBUILD v1.0 起，取代旧的「禁止数据库」规则）：教材目录用 SQLite（`.local-data/textbooks/catalog.sqlite3`）、题库用**独立** SQLite（`.local-data/question-bank/question-bank.sqlite3`）、教材向量用本机 Docker 中的 Qdrant。除这三者外仍不引入 PostgreSQL、Redis 或其他数据库。
  - 连接统一走 `app/core/sqlite.py`（外键、WAL、有限 `busy_timeout`），不要在模块里各自 `sqlite3.connect`。
  - `catalog_state.active_generation_id` 是**唯一**的「当前索引」权威；不得再存第二个模型或索引指针来与它竞争。
  - 网络请求、文件解析、模型推理**不得**放在 SQL 写事务内。
  - 不可变表（`document_revisions`、`document_metadata_revisions`、`chunk_sets`、`chunks`）没有任何 UPDATE 路径；改分类=新增元数据修订。
  - 向量库不可达必须报 `QDRANT_UNAVAILABLE`，**绝不允许**降级成「没有匹配」或空结果。
  - 题库与教材向量库完全隔离：题库不得有任何写入教材 collection 的路径。
  - 单测一律用 `tmp_path` 与替身；真实 Qdrant 用测试实例（16333，compose project `zqky-rag-test`），不得连接正式 6333 跑单测。
  - 单册教材入库可能远超 90 秒：任务必须**按 ≤20 秒续租**，长任务不得因租约过期中途失败。
- 统一错误信封：`code、message、requestId、retryable、details?`；details 只放脱敏、可展示内容。未实现的 /api/v1 路由必须返回 501 `FEATURE_NOT_IMPLEMENTED`，禁止返回 200 假成功或示例数据。
- 能力状态（/capabilities）按实际实现如实报告：没写的功能保持 `planned`，不得提前标 `ready` 或 `unconfigured`。
- 来源检查：Host 必须是回环地址；带 Origin 的请求必须在允许列表（默认 5173/5174 前端端口，可用 `ZQKY_ALLOWED_ORIGINS` 覆盖）。无 Origin 的本机工具直连放行。
- 凭证与密钥只存在于服务端；`core/secrets.py` 是统一读写入口。按用户已批准范围，正式服务将凭证持久化至忽略的 `apps/api/.env`，启动时读取；测试注入临时目录或内存存储。日志、错误、health/capabilities、非敏感模型 JSON 配置不得包含密钥；响应只返回凭证状态/变量名。`.env.example` 只放空值或无敏感信息示例。
- 模型设置约定：非敏感配置写入 `.local-data/`（原子写 + revision 冲突检测，损坏时报错不覆盖）；Base URL 公网必须 https、http 仅限回环；凭证头由 Provider 适配器写入，附加请求头不可覆盖；未实现协议一律 `UNSUPPORTED_PROTOCOL`，能力证据只有 verified/claimed/unknown 三值，测试成功才可置 verified。
- 流式约定：SSE 事件使用 message.start/text.delta/reasoning.delta/usage/message.end/error；流开始前的失败返回 HTTP 错误，流开始后失败发 `error` 事件；上游结束原因规范化为 stop/length/unknown；生成器 finally 必须关闭上游连接使取消传播；对话内容不在后端落盘或记录日志。
- 后端执行代码变更后运行 `npm run test:api`；涉及启动方式或接口时同步 README、docs/API.md；目标/决定只写 PROJECT_GUIDE，进度/检查只写 docs/CURRENT_STATUS.md。旧 DECISIONS/TASKS/HANDOFF 已归档，不再维护。
- 模型 Provider、SSE 流式、模板渲染属于 D03–D07；实施时在现有 create_app/lifespan/中间件骨架上扩展，不另起第二套服务。
