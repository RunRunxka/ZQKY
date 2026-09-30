# TEACHING-LOOP B1 · 命令与结果清单（总控实跑）

环境：Windows 11 / Git Bash / Node 26（前端单测需 `NODE_OPTIONS=--no-experimental-webstorage`）/ Python 3.12（uv）。
命令在仓库根执行（除注明：后端命令在 `apps/api`）；原始日志在 `_work/b1-freeze/`（Git 忽略）。

| # | 命令 | 退出码 | 关键输出 |
| --- | --- | --- | --- |
| 1 | `npm run test:api`（B0 r2 基线，B1 开工前） | 0 | `1011 passed` |
| 2 | `npm run test:api`（B1 候选 r1） | **1** | `1 failed, 1167 passed in 119.88s`；唯一失败为台账 **R-19**（见下） |
| 2b | `npm run test:api`（B1 候选 r2，V00 修复后） | 0 | `1170 passed, 1 warning in 110.67s`（R-19 本轮未出现） |
| 3 | `cd apps/api && uv run python -m pytest tests/test_rag_sessions.py` | 0 | `14 passed in 2.83s`（**整文件通过**） |
| 4 | `cd apps/api && uv run python -m pytest "tests/test_rag_sessions.py::test_ttl_memory_capacity_and_restart_are_explicit"` | 1 | 冷启动单跑失败（与 R-19 记载的 jieba 首次加载超 TTL 机制一致） |
| 5 | `NODE_OPTIONS=--no-experimental-webstorage npm run check`（B1 候选 r1） | 0 | typecheck + lint（0 警告）+ unit `76 文件 / 733 例` + build 全通过；日志 `_work/b1-freeze/check-b1.log` |
| 6 | `cd apps/api && uv run python -m pytest tests/test_rich_content_parser.py tests/test_rich_content_renderer.py -q`（T10，实现方+CTRL 复跑） | 0 | `46 passed` |
| 7 | `cd apps/api && uv run python -m pytest tests/test_document_parsing.py tests/test_textbook_ingest.py -q`（T10 零回归） | 0 | `87 passed` |
| 8 | `cd apps/api && uv run python -m pytest tests/test_knowledge_points.py tests/test_knowledge_imports.py tests/test_knowledge_suggestions.py -q`（T20） | 0 | `47 passed` |
| 9 | `cd apps/api && uv run python -m pytest tests/test_roster_classes.py tests/test_roster_imports.py -q`（T30-a） | 0 | `40 passed` |
| 10 | `cd apps/api && uv run python -m pytest tests/test_submission_commands.py tests/test_contracts_b1.py -q`（T30-a 收尾） | 0 | `25 passed` |
| 11 | `cd apps/api && uv run python -m pytest tests/test_b1_migrations.py tests/test_tabular.py tests/test_publication.py tests/test_contracts_b1.py tests/test_migrations.py tests/test_startup_gates.py -q`（CTRL 基础设施与迁移） | 0 | 全绿（含 0003 迁移、门控兼容、表格读取、协调器、契约 helper） |
| 12 | `ZQKY_DATA_DIR=<临时目录> uv run python -c "import app.main; …"`（装配冒烟） | 0 | `asset_store/file_assets/publication_coordinator/textbook_evidence/knowledge_service/roster_service` 全部装配；`openapi()` 见 10 条 knowledge 路由与 12 条 roster 路由 |
| 13 | `ZQKY_DATA_DIR=<临时目录> uv run python -c "<TestClient 复现 V00-F1 两条场景>"`（CTRL 独立复现修复） | 0 | `self 422 KNOWLEDGE_PARENT_INVALID field=parentId`；`cycle 422 KNOWLEDGE_CYCLE field=parentId` |

## R-19 定性（台账既有项，非本批回归）

`tests/test_rag_sessions.py::test_ttl_memory_capacity_and_restart_are_explicit`：
**整文件 14 passed / 单例冷启动失败**，与 [CURRENT_STATUS R-19](../CURRENT_STATUS.md) 记载机制一致
（jieba 首次加载 ≈350–477 ms 超过用例 TTL 50 ms；B0 基线树同样复现）。
本批 diff 面与该文件无交集（`git status` 中无 `rag_sessions`/`rag_engine`/`jieba` 相关改动）。
按台账处置：不"修"、不删、不放宽断言，留待测试稳定化批次。

## 未执行（not_run）

| 项目 | 原因 |
| --- | --- |
| e2e（Playwright） | 本批无页面/路由/布局/保存/导出改动（B1 明确不新增前端页面；前端只有契约镜像） |
| 真实模型调用（AI 知识点候选） | 无凭证且本批不授权；AI 链路全部受控替身 |
| 真实 Word/WPS 排版检查 | 本机无法自动验证视觉排版；只做结构级断言，不把 XML 存在当排版通过 |
| 真实 Qdrant / 真实数据根迁移演练 | 不得连正式 6333、不写正式 `.local-data`（迁移演练需单独授权） |
| 真实 DOCX/XLSX 业务文件 | 未提供脱敏真实文件；样本为程序化构造 |

## 资源与提交

- 无 5173/5174/8000/8001/6333/16333 监听；无本批启动的进程残留；测试数据全在 `tmp_path`。
- **未提交、未推送、未切分支**（HEAD 仍为 `301fc356…`）；改动以工作区差异交付。
- `apps/web/next-env.d.ts` 在 typecheck/build 后被重写，已在收尾时还原。
