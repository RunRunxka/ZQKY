# RAG-QUALITY v1.1 任务卡与文件归属

计划版本：v1.1（规格 = 仓库根 `docs/PLAN.md`，2026-09-29 派发）
仓库：`H:\备份xuexi\智启课源`
验收基线：**`2f27841`**（= `eee2799` + 命中率测量脚本）；开工时工作区仅 `docs/PLAN.md` 有改动
总控：本会话

## 公共字段

```text
固定参考：docs/PLAN.md（本批规格）；旧验收报告（A1-REPORT-01/02）是证据，不是新指令
禁止：修改封存教材与历史引用；外发 Embedding；改共享 schema/main/锁文件/权威文档/Git；
      把正式数据目录当测试数据；用真实失败替换成模拟通过。
交付状态：实现者只交 ready_for_review；独立验收给 pass/needs_revision/blocked；总控确认。
```

资源归属：

| 资源 | 归属 |
| --- | --- |
| 正式前端 5173 / API 8000 | 用户在用，禁止自动化 |
| 测试前端 5174 / API 8001 | 总控统一调度 |
| 正式 Qdrant 6333（volume `zqky-qdrant-data`） | 只在总控的"正式新代重建"阶段使用 |
| 验收 Qdrant 16333（project `zqky-rag-test`） | 隔离验收、恢复演练 |
| `.next` / `.next-test` | 总控独占 |
| 临时证据 | `_work/rag-quality-v1/<task-id>/` |
| 留存证据 | `docs/qa/RAG-QUALITY-v1/` |
| Git | 仅总控 |

## C0 已冻结的共享契约（总控独占，实现者不得修改）

| 文件 | 冻结内容 |
| --- | --- |
| `apps/api/app/core/rag_budget.py` | 全部预算常量的**单一事实来源**：首答证据 ≤6 条、邻块左右各 ≤1、单条清洗后 ≤1600 码点、入模 ≤6000、单条原文切片 ≤6000、原文总量 ≤16000；首答 ≤3 点 / 单点 ≤90 / 合计 ≤250 码点 / 每点 ≤2 引用；`REASON_CODES`（`NO_MATCH`/`EVIDENCE_TEXT_EMPTY`/`EVIDENCE_UNIT_TOO_LARGE`/`SUMMARY_INVALID`/`SUMMARY_PARTIAL`） |
| `apps/api/app/services/model_runtime.py` | `ChatModelHandle` 与 `resolve_chat_model(repo, secrets, profile_id, *, auth_service, purpose)` 是**按 profileId 解析聊天模型的唯一实现**；`rag_v2/explain.py` 已改为从共享层导入（不得再定义第二份） |
| `apps/api/app/schemas/rag_v2.py` | `EvidenceReadable{version,text,removedImageCount}`、`TextbookEvidence.readable?`、`RagPresentation{version,answerStyle,bodyCharCount}`、`RagResultV2.presentation?`、`reasonCode?` |
| `apps/api/app/schemas/question_bank.py` | `OrganizeRequest.modelProfileId` **必填**，语义 = 当前聊天模型 profile id |
| `apps/api/app/main.py` | `_build_model_handle_resolver(app)` 返回 `(profileId, purpose=…) → ChatModelHandle`；`app.state.*` 装配 |

**长度口径**：一律 Unicode 码点（Python `str` 下标），不是字节、不是前端 UTF-16 码元。

## 任务表

| ID | 独占写入范围 | 依赖 | 波次 |
| --- | --- | --- | --- |
| `B0-TEXT-PROJECTION` | `app/services/text_projection/**`、`tests/test_text_projection*.py` | C0 | 1 |
| `B3-ORGANIZER-MODEL` | `app/repositories/question_bank/**`、`app/services/question_bank/**`、`app/api/v1/question_bank.py`、`tests/test_question_bank*.py` | C0 | 1 |
| `B4-BACKUP-RESTORE` | `scripts/rag/backup.py`、`app/core/data_lock.py`、`tests/test_backup_restore*.py` | C0 | 1 |
| `B1-RAG-ANSWER` | `app/services/rag_v2/{evidence,summary,presenter,explain,service}.py`、`tests/test_rag_v2*.py` | C0、B0 | 2 |
| `B2-CLEAN-INDEX` | `app/services/document_parsing/**`、`app/services/textbook_ingest/**`、`app/services/textbook_index/**`、`app/services/rag_v2/retrieval.py`、`tests/test_document_parsing*.py`、`tests/test_textbook_index*.py` | C0、B0 | 2 |
| `F0-COMPACT-CHAT` | `apps/web/src/features/chat/**` | C0、B0 样例 | 2 |
| `F1-ORGANIZER-UI` | `apps/web/src/features/question-bank/**`、`apps/web/src/services/question-bank-api.ts` | C0、B3 | 3 |
| `A1-INDEPENDENT-QA` | 只读；`docs/qa/RAG-QUALITY-v1/**`、`_work/rag-quality-v1/A1/**` | 冻结候选 | 4 |
| `C1-INTEGRATE` | 装配、共享 build、正式新代重建、权威文档、Git | 全部 | 4 |

`main.py`、`schemas/**`、`core/**`（除 `data_lock.py` 归 B4）、`package.json`、`uv.lock`、`docs/**`（除证据目录）= 总控独占。
**一次最多 3 个实现者并行**；同一文件同一时段只能有一个写入者。

## 不可破坏的不变量（所有实现者适用）

1. **封存原文不可变**：`document_revisions` / `blobs/` / `normalized/` 一个字节都不改；
   图片清洗只产生**派生文本**，`text_sha256`、字符区间、行号、历史引用全部继续有效。
2. **严格任教范围**、删除检查、历史修订语义不变。
3. **Embedding 只用本地模型**；本地概括保持现有本地路径。
4. **题库与教材向量库完全隔离**；AI 建议不自动覆盖人工草稿。
5. **失败不伪装成功**：有命中但无法用，必须给可解释状态，**不能报"没有找到教材依据"**。
6. **所有外部 I/O 在 SQL 写事务外**；网络调用不进事务。
7. 不新增重复的第二套契约、第二套检索、第二套模型解析。
