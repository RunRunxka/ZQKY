# 后端开发规则

先读根 AGENTS.md。本文件补充 apps/api 范围的规则。

- 后端是本机单用户服务，只监听 `127.0.0.1`：开发 8000，后端测试 8001；不允许配置对外地址（`Settings` 会拒绝非回环 host）。
- 依赖只用 uv 管理：`pyproject.toml` + `uv.lock` 是唯一依赖来源；改依赖必须 `uv lock`/`uv add` 并记录版本。不把 Python 加入 npm workspaces。
- 本地存储（2026-09-30 TEACHING-LOOP B0 起为**四库**）：教材目录 `textbooks/catalog.sqlite3`、题库 `question-bank/question-bank.sqlite3`、知识点库 `knowledge/knowledge.sqlite3`、教学业务库 `teaching/teaching.sqlite3`（后两者 B0 只含公共基础表：提交幂等、任务、受管资产登记）；受管文件走 `assets/blobs/<sha256>`。教材向量仍用本机 Docker 中的 Qdrant。除这些之外仍不引入 PostgreSQL、Redis 或其他数据库。
  - 连接统一走 `app/core/sqlite.py`（外键、WAL、有限 `busy_timeout`；`busy_timeout` 先于 `journal_mode` 设置），不要在模块里各自 `sqlite3.connect`。
  - **迁移登记**：每库 `schema_migrations`，迁移清单在 `app/core/migrations/{textbooks,question_bank,knowledge,teaching}.py`（冻结基线 + 追加增量）。改动结构一律**新增迁移**，不得改写已登记 SQL（散列漂移会拒绝启动）；迁移内容由总控登记，实现者提供 SQL 建议。
  - **B1 业务结构（2026-09-30）**：知识点库 `0002` 登记设计 5 表（`subjects`/`knowledge_points`/`knowledge_point_revisions`/`knowledge_aliases`/`textbook_knowledge_links`，含环检测与修订不可变触发器）与导入批次表（`knowledge_imports`/`knowledge_import_rows`），`0003` 补 `knowledge_imports.issues_json`（批次级问题独立落列）；教学库 `0002` 登记 `classes`/`students`/`class_memberships`（含 `ux_active_membership` 部分唯一索引）与名单批次表（`roster_imports`/`roster_import_rows`）。施测三表留 T30-b（依赖 T40 的 `paper_revisions`）。
  - **B2 业务结构（2026-10-01）**：教学库 `0003` 登记原卷四表（设计逐字）+ `paper_source_blocks`/`paper_issues`/`ai_proposals` 与确认冻结触发器，`0004` 登记施测三表 + 参测班级显式确认列 + 只用已确认卷/不能换卷触发器；题库 `0004` 登记 `question_knowledge_links`（设计逐字 + 不可变触发器）+ 草稿关联/生成来源/版本化内容指纹。**分期偏差**：`paper_revisions.source_practice_revision_id` 与 `assessments.active_score_revision_id` 本批只允许为空（无未来表外键，CHECK 拒非空），由练习/成绩批次的新迁移补齐；`paper_revisions.source_file_id` 必须非空；草稿总分允许 0，确认闸门要求 >0 且等于计分叶子合计。
  - **题库存量服务接入共享依赖**：`build_question_bank_service` 现在接收 `knowledge_catalog` / `coordinator` / `job_engine`（由 `main.py` 装配）；组织与生成任务统一走 JobEngine 六态，`RECONCILE_DOMAINS` 含 `question`；启动不自动重叫模型。
  - **启动门控语义**：`REQUIRED_TABLES` 只要求 B0 基础表——"尚未应用 B1 迁移"的合法旧库必须能启动；新结构由迁移保证（`tests/test_b1_migrations.py` 覆盖两条路径）。
  - **跨库发布**：跨库引用发布/归档一律经 `app/services/publication.py` 的 `PublicationCoordinator`（进程内 RLock，锁内只做数据库读取与短事务；模型/解析/资产写入必须在锁外）；不得各模块自建第二把锁，也不得宣称跨库原子事务。
  - **表格文件**：XLSX/CSV 读取统一用 `app/services/tabular.py#read_table`（openpyxl 只读 + data_only；CSV 支持 UTF-8-BOM/GB18030），不得各自实现解析。
  - **富内容**：解析/渲染在 `app/services/rich_content/`（`parse_docx_rich` → `blocks`/`locators`/`assets`/`issues`；`render_rich_document(variant=student|teacher)`）；类型只用 `app/contracts/teaching_loop.py` 的 `RichContentV2`。**不得改动** `app/services/document_parsing/parser.py` 的既有教材解析语义。
  - **任务**：三个业务库各有一张任务表（`question_jobs` / `knowledge_jobs` / `workflow_jobs`），统一经 `app/repositories/jobs` + `app/services/jobs` 的租约/心跳/取消/同库提交协议；任务结果与终态必须与域内写入在同一事务提交，网络/解析/推理在事务外。对外视图见 `GET /api/v1/workflow-jobs/{id}?domain=…`。
  - **提交幂等**：新库用 `(owner_id, operation, submission_id)` 复合身份（`app/services/submissions`）；同键同 hash 重放返回原结果，同键不同 hash 409 `SUBMISSION_CONFLICT`。
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
