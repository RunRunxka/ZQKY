# TEACHING-LOOP B0 · 命令与结果清单（总控实跑）

环境：Windows 11 / Git Bash / Node 26（前端单测必须 `NODE_OPTIONS=--no-experimental-webstorage`）/ Python 3.12（uv）。
所有命令在仓库根执行（除注明）；原始日志在本机 `_work/b0-smoke/`（Git 忽略）。

| # | 命令 | 退出码 | 关键输出 |
| --- | --- | --- | --- |
| 1 | `npm run test:api`（基线，改动前） | 0 | `920 passed, 1 warning in 86.41s` |
| 2 | `npm run test:api`（r1 候选） | 0 | `1007 passed, 1 warning in 102.07s` |
| 3 | `npm run test:api`（r2 候选，含 V00 修复） | 0 | `1011 passed, 1 warning in 104.77s`（日志 `_work/b0-smoke/testapi-r2.log`） |
| 4 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 0 | `Test Files 76 passed (76)` / `Tests 733 passed (733)`（本批变更范围 +13 例） |
| 5 | `npm run typecheck`（根） | 0 | `Types generated successfully` |
| 6 | `npm run lint`（根，`--max-warnings=0`） | 0 | 无输出（0 警告） |
| 7 | `NODE_OPTIONS=--no-experimental-webstorage npm run check`（r2 最终候选） | 0 | typecheck + lint（0 警告）+ unit（`76 passed / 733 passed`）+ build 全通过；日志 `_work/b0-smoke/check-final.log` |
| 8 | `cd apps/api && uv run python -m pytest tests/test_workflow_jobs_api.py -q`（CTRL 路由集成） | 0 | `9 passed` |
| 9 | `cd apps/api && uv run python -m pytest tests/test_migrations.py tests/test_startup_gates.py -q`（r2） | 0 | `19 passed` |
| 10 | `cd apps/api && uv run python ../../_work/b0-smoke/smoke_migrations.py`（CTRL 冒烟：四库登记/幂等/漂移/失败回滚/损坏拒绝） | 0 | `SMOKE OK` |
| 11 | `cd apps/api && uv run python ../../scripts/rag/backup.py verify --path ../../_work/rag-backups/rag-20260929-130007-pre-clean-generation`（实现方 T00-b） | 0 | 旧 v2 清单只读复验通过（350 文件、1 collection） |

前端构建与 e2e：**e2e 未执行**——本批无 `app/` 路由、布局、保存或导出改动（任务卡 §5 明确不跑）；
`npm run check` 内含 build，已通过。真实模型调用、真实 Qdrant v3 备份恢复 CLI 成功路径、真实 DOCX/XLSX
解析均 `not_run`（本批无业务模块、无凭证、禁止连正式 6333）。

资源：无 5173/5174/8000/8001/6333/16333 监听；无本批启动的进程残留；测试数据全在临时目录。
提交：**未提交、未推送、未切分支**（HEAD 仍为 `301fc356…`）；改动以工作区差异交付。
生成文件：`apps/web/next-env.d.ts` 在每次 `typecheck/build` 后被重写（`.next/dev` ↔ `.next` 路径），
已在收尾时 `git checkout --` 还原，工作区不含该生成差异。
独立验收：V00 r1（[V00-REPORT-01.md](V00-REPORT-01.md)）9 pass / 1 fail / 6 observation；
修复后 r2 窄复验（[V00-REPORT-02.md](V00-REPORT-02.md)）**5/5 pass**。
