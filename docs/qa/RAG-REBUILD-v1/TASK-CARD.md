# RAG-REBUILD v1.0 任务卡与文件归属

计划版本：v1.0（依据 `docs/PLAN.md`，2026-09-28 派发）
仓库：`H:\备份xuexi\智启课源`
开始候选：`c2f31ec0a70fc9b9e9d38479b6c193416c19befb`（`main`，工作区仅 `docs/PLAN.md` 未跟踪）
总控：本会话

## 公共字段（每张卡都适用）

```text
固定参考：Local_Pdf_Chat_RAG@38b39f641a5228673fc46a64c802307e2e6d5209（仅借鉴解析/混合检索/模块划分）
禁止：修改原教材（F:\人教版教材）、原 Word、无关模块、他人文件；切换/合并分支；批量暂存；
      推送/部署；把真实失败改成模拟；把测试指向正式 .env / 正式 .local-data。
交付状态：实现者只交 ready_for_review；独立验收给 pass/fail/not_run；总控确认已验收。
```

运行资源归属：

| 资源 | 归属 |
| --- | --- |
| 正式前端 5173 / API 8000 | 用户在用，禁止用于自动化 |
| 测试前端 5174 / API 8001 | 总控统一调度 |
| 正式 Qdrant 6333 | 正式启用阶段由总控管理（named volume `zqky-qdrant-data`） |
| 测试 Qdrant 16333 | 独立 compose project `zqky-rag-test` + volume `zqky-qdrant-test` |
| `.next` / `.next-test` | 总控独占 |
| 单测数据库 | 各任务 pytest `tmp_path`，互不共享 |
| 临时证据 | `_work/rag-rebuild-v1/<task-id>/` |
| 留存证据 | `docs/qa/RAG-REBUILD-v1/` |
| Git | 仅总控 |

## 已冻结的共享契约（总控独占，实现者不得修改）

| 文件 | 内容 |
| --- | --- |
| `apps/api/app/core/config.py` | 新增 `textbooks_root` / `question_bank_root` / `qdrant_url` / `embedding_base_url` / `textbook_source_dir` |
| `apps/api/app/core/sqlite.py` | `connect` / `transaction` / `read_transaction` / `now_iso` |
| `apps/api/app/schemas/textbook.py` | 教材目录、导入、任教范围、Embedding、索引代全部 HTTP 模型 |
| `apps/api/app/schemas/rag_v2.py` | `ScopeSnapshot` / `EvidenceRef` / `TextbookEvidence` / `RagResultV2` / `RagExplainRequest` |
| `apps/api/app/schemas/question_bank.py` | 题库全部 HTTP 模型 |
| `apps/api/app/main.py` | 路由注册、`app.state.*` 装配、lifespan |
| `apps/web/src/contracts/*` | 前端共享类型与 `apps/api` schemas 一一对应 |
| `apps/web/src/services/navigation.ts` | 导航项与状态徽标 |
| `package-lock.json` / `apps/api/uv.lock` | 依赖锁 |

## 任务表

| ID | 角色 | 独占文件范围 | 依赖 | 状态 |
| --- | --- | --- | --- | --- |
| C0-CONTRACT | 总控 | 共享契约、main/config 接线、导航、锁文件、权威文档 | 无 | 进行中 |
| B0-CATALOG | 后端实现 | `app/repositories/textbook_catalog/**`、`app/services/textbook_catalog/**`、`tests/test_textbook_catalog*.py` | C0 | 待派 |
| B1-INGEST | 后端实现 | `app/providers/embeddings/**`、`app/services/document_parsing/**`、`app/services/textbook_ingest/**`、`app/services/textbook_index/**`、`app/repositories/vector_store/**`、`app/api/v1/textbooks.py`、`app/api/v1/embedding_models.py`、`app/api/v1/textbook_index.py`、`tests/test_textbook_*.py` | C0、B0 | 待派 |
| B2-RAG | 后端实现 | `app/services/rag_v2/**`、`app/api/v1/rag.py`、`tests/test_rag_v2*.py` | C0、B0、B1 | 待派 |
| B3-QBANK | 后端实现 | `app/repositories/question_bank/**`、`app/services/question_bank/**`、`app/api/v1/question_bank.py`、`tests/test_question_bank*.py` | C0、B1 解析接口 | 待派 |
| F0-TEXTBOOK | 前端实现 | `apps/web/src/features/textbook/**`、`apps/web/src/app/knowledge-bases/**`、`apps/web/src/services/textbook-api.ts`、`apps/web/src/features/model-settings/embedding/**` | C0 | 待派 |
| F1-CHAT | 前端实现 | `apps/web/src/features/chat/**`、`apps/web/src/services/taught-scope.ts` | C0、B2 接口 | 待派 |
| F2-QBANK | 前端实现 | `apps/web/src/features/question-bank/**`、`apps/web/src/app/question-bank/**`、`apps/web/src/services/question-bank-api.ts` | C0、B3 接口 | 待派 |
| A1-VERIFY | 独立验收 | 只读产品；`docs/qa/RAG-REBUILD-v1/A1-REPORT-*.md`、`_work/rag-rebuild-v1/A1/**` | 稳定候选 | 待派 |
| C1-INTEGRATE | 总控 | 集成、文档、全量检查、迁移启用与 Git | 全部 | 待派 |

## 不可破坏的不变量（所有实现者适用）

1. 唯一后端：真实业务全部留在 `apps/api`，Next.js 只做既有代理与页面。
2. 唯一当前索引指针：`catalog_state.active_generation_id` 是唯一权威；不新增第二指针。
3. 模型空间一致：查询向量与教材向量必须同一 Embedding 配置指纹。
4. 发布原子性：向量全部写入并核验后，才切换教材有效修订。
5. 先限制范围再排序：向量、BM25、邻块扩展与引用使用同一教材范围。
6. 删除先失效：SQLite 先停用，再清理向量；清理失败不影响逻辑删除。
7. 原文不可变：引用绑定文档修订与规范化文本指纹，不绑定可变外部路径。
8. 失败不伪装成功：服务不可用不能变成空库、模拟结果或普通聊天回退。
9. 旧数据保留：旧浏览器登记、课程引用、聊天记录及源教材不被清空。
10. 题库独立：题库没有任何向教材 collection 写入的路径。

## B0-CATALOG 任务卡（v1）

```text
目标：教材目录 SQLite 权威层——迁移、不可变修订、分类、范围解析、事务、幂等、删除。
可写文件：apps/api/app/repositories/textbook_catalog/**、apps/api/app/services/textbook_catalog/**、
          apps/api/tests/test_textbook_catalog*.py
禁止修改：共享 schemas、config、sqlite.py、main.py、其他模块、锁文件、Git。
```

必须实现（与 `docs/PLAN.md` §3 表规格一致）：

- `catalog.sqlite3` 建库迁移（幂等、可重复调用），开启外键/WAL/busy_timeout，表名与字段取计划 §3.2。
- 不可变修订：`document_revisions` 写定后不修改；`document_metadata_revisions` 同理。
- `catalog_state` 单行（id=1）持有 `active_generation_id` / `rebuild_job_id` / `catalog_version`。
- 逻辑库 `libraries`（base/personal）、`library_documents` 关联。
- 范围解析：给定 `TextbookSelection`，返回允许的 `(document, revision, metadata)`，逐条核验删除/归属/年级/学科/版本/库归属，并给出 `scopeHash`。
- 删除：先逻辑删除 + `catalog_version` 递增，再入清理队列；更新失败保持旧 `current_revision_id`。
- 幂等：`index_jobs.idempotency_key` 唯一；相同键相同 `request_fingerprint` 返回原任务，不同返回冲突。
- 版本冲突：所有裸实体写操作带 `expected_revision`，不符抛 `AppError`（409 `REVISION_CONFLICT`）。
- 事务边界：网络/解析/推理不得在写事务内；仓储函数只做 SQL。

验收：`uv run python -m pytest tests/test_textbook_catalog*.py -q` 全绿；覆盖上述每条（含
冲突、删除后不可见、范围不串库、幂等重放）。

## B1-INGEST 任务卡（v1）

```text
目标：本地 Embedding 探测与管理、三格式解析、分块、入库任务、索引重建与发布、Qdrant 客户端。
可写文件：apps/api/app/providers/embeddings/**、app/services/document_parsing/**、
          app/services/textbook_ingest/**、app/services/textbook_index/**、
          app/repositories/vector_store/**、app/api/v1/textbooks.py、
          apps/api/app/api/v1/embedding_models.py、apps/api/app/api/v1/textbook_index.py、
          apps/api/tests/test_textbook_*.py
禁止修改：共享 schemas、config、sqlite.py、main.py（路由注册由总控加）、
          app/repositories/textbook_catalog/**、其他模块、锁文件、Git。
```

必须实现：

1. `providers/embeddings/ollama_embedding.py`：原生 `/api/tags`、`/api/show`、`/api/embed`；
   只允许回环地址；`truncate=False`；`embed()` 校验数量/维度/有限值/非零；检测前后 digest 一致。
2. `services/document_parsing/`：`.md` / 文本 `.pdf`（pypdf）/ `.docx`（python-docx）→ 规范化文本 +
   来源映射（markdown 行号 / pdf 页码 / docx 段落序号）；扫描件无文本层 → `DOCUMENT_NEEDS_OCR`；
   正文与习题区 `region` 划分；分块默认 800 目标 / 1200 上限 / 120 重叠，公式、表格、代码围栏不中间截断。
3. `repositories/vector_store/`：`VectorStore` 端口 + `HttpQdrantStore`（httpx REST，无新依赖）+
   内存替身（测试用）。point id = `uuid5(APP_NAMESPACE, f"{generation}/{chunk_set}/{ordinal}/{text_sha256}")`，
   payload 字段按计划 §3.3。collection 建 payload 索引。
4. `services/textbook_ingest/`：导入状态机、`seal_document_revision`、批次写入（batch=8，OOM 缩批不换模型）、
   checkpoint、租约续租、崩溃重做相同 point id、发布原子切换。
5. `services/textbook_index/`：重建闸门、`begin_rebuild` / `run_rebuild` / 发布 / 失败终止，旧代继续可用。
6. 路由三份（严格用共享 schemas 的模型），全部经 `request.app.state` 取服务。

验收：`uv run python -m pytest tests/test_textbook_*.py -q` 全绿；替身覆盖正常/失败/取消/重试/重启恢复；
真实 Qdrant 与真实 Ollama 由总控在 `test:rag` 阶段单独验收（实现者须保证注入可切换）。

## B2-RAG 任务卡（v1）

```text
目标：v2 严格范围检索（Qdrant 向量 + BM25 + RRF + 原文证据重建）、知识点首答、所选模型详解。
可写文件：apps/api/app/services/rag_v2/**、apps/api/app/api/v1/rag.py、apps/api/tests/test_rag_v2*.py
禁止修改：共享 schemas、rag_engine/**（既有四科快照继续可读）、config、main.py、锁文件、Git。
```

要点：范围预过滤（SQLite 解析出的 revision/chunk_set 白名单进 Qdrant filter 与 BM25）；
向量 50 / BM25 50 / RRF k=60 / 证据 ≤20 条且 ≤40,000 字符；证据从 SQLite 不可变规范化文本重建并核验散列与区间；
`no_evidence` 不编造；详解走既有 Provider 栈与 SSE，不回到 `/rag/reply`；预算超限 `CONTEXT_TOO_LARGE` 不截断。

## B3-QBANK 任务卡（v1）

```text
目标：题库独立 SQLite + 导入拆题 + 校对草稿 + 可选 AI 整理建议 + 幂等确认入库 + 题目管理。
可写文件：apps/api/app/repositories/question_bank/**、apps/api/app/services/question_bank/**、
          apps/api/app/api/v1/question_bank.py、apps/api/tests/test_question_bank*.py
禁止修改：教材目录、向量库、共享 schemas、config、sqlite.py、main.py、锁文件、Git。
```

要点：未归属原文块必须保留；AI 建议只落 `pending` 且应用前核 `base_draft_revision`；
编辑已校对草稿回到 `needs_review`；确认走单事务 + 幂等 `submissionId`；重复指纹不含答案与解析。

## F0/F1/F2 任务卡（v1）

```text
目标：教材管理（基础库/我的教材/历史登记）+ Embedding 设置 + 题库界面 + 聊天范围与追问。
可写文件：见任务表「独占文件范围」；不修改共享 contracts、导航、锁文件、权威文档。
视觉：复用当前 /chat 字体 token、蓝色主题、输入框圆角、细边框与留白；不新增主题或动画库。
所有真实状态来自 FastAPI；生产不得用定时器伪造入库；请求失败不能当空目录。
```

## 结果卡（实现者填写，模板见 MULTI_AGENT_COLLABORATION_PROPOSAL §结果卡）
