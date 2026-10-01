# TEACHING-LOOP B2 · 命令与结果清单（总控实跑）

环境：Windows 11 / Git Bash / Node 26（前端单测需 `NODE_OPTIONS=--no-experimental-webstorage`）/ Python 3.12（uv）。
命令在仓库根执行（除注明：后端命令在 `apps/api`）；原始日志在 `_work/b2/`（Git 忽略）。

| # | 命令 | 退出码 | 关键输出 |
| --- | --- | --- | --- |
| 1 | `npm run test:api`（B2 候选，全部写入者停止后） | 0 | `1296 passed, 1 warning in 144.24s`（B1 基线 1170 → +126 例） |
| 2 | `npm run check`（B2 候选最终；含 build） | 0 | typecheck + lint（0 警告）+ unit **86 文件 / 799 例** + build 全通过（日志 `_work/b2/check-b2-r4.log`） |
| 3 | `npm run test:e2e`（先 build，隔离 5174，全量 spec） | 0 | 第 1 轮 `142 passed / 5 failed`（全在 `knowledge-points.spec.ts`）→ 修复 → 第 2 轮 `146 passed / 1 failed` → 修复 → **第 3 轮 `147 passed / 0 failed`（6.0m）** |
| 4 | `cd apps/api && uv run python -m pytest tests/test_b2_migrations.py tests/test_b2_contracts.py -q`（CTRL 自有） | 0 | 迁移 7 例（三路径升级/幂等/回滚/触发器/分期 CHECK）+ 契约 6 例（分值边界/六态/确认依据） |
| 5 | `cd apps/api && uv run python -m pytest tests/test_b1_migrations.py tests/test_migrations.py tests/test_startup_gates.py -q`（旧测试已改为动态期望） | 0 | 全绿（B2 新迁移不再破坏既有断言） |
| 6 | `cd apps/api && uv run python -m pytest tests/test_papers_*.py -q`（T40） | 0 | 42→43 例（含 adapter 端口符合性） |
| 7 | `cd apps/api && uv run python -m pytest tests/test_question_bank*.py tests/test_question_generation.py tests/test_question_job_engine.py -q`（T50） | 0 | 122 例（含新增 HTTP 级 knowledgeLinks 三例） |
| 8 | `cd apps/api && uv run python -m pytest tests/test_assessments_api.py tests/test_roster_imports.py tests/test_papers_draft_confirm.py -q`（T30-b + 集成前置） | 0 | 20 + 18 + 16 例；含**名单→原卷确认→施测**真链路与 200 人参测规模证据（0.025s） |
| 9 | 装配冒烟 `ZQKY_DATA_DIR=<临时> uv run python -c "import app.main; …"` | 0 | 六服务 + 全部路由：knowledge 10 / roster 12 / papers 10 / assessments 3 / workflow-jobs 3；`question_bank_service` 三依赖（knowledge_catalog/coordinator/job_engine）全部接入；`RECONCILE_DOMAINS` 含 question |
| 10 | `NODE_OPTIONS=--no-experimental-webstorage npx vitest run apps/web/src/features/knowledge-points apps/web/src/features/question-bank apps/web/src/services`（F10-KP 改动面） | 0 | 36 文件 / 346 例（含我补的题库 interrupted→retry 组件用例） |

## E2E（先 `npm run build`，`npx playwright test`，隔离 5174）

| 轮次 | 结果 | 失败与处置 |
| --- | --- | --- |
| r1 | `142 passed / 5 failed` | 5 例全在新 spec：`role=alert` 计数（Next RouteAnnouncer 常驻空 alert）、`getByLabel('编码')`/`getByRole('确认入库')` strict 重复匹配、AI 用例未选学科导致任务未创建、三视口用例未选中批次 |
| r2 | `146 passed / 1 failed` | F10-KP 修 5 处（testid/学科门控/exact 定位；给控件补齐可访问名称）后：仅剩确认结果 testid 在"已确认"刷新态不存在 |
| r3 | **147 passed / 0 failed（6.0m）** | F10-KP 改页面（确认结果条在刷新后保留）与 spec（真实"响应丢失 → 同标识重放"幂等链）后全绿；日志 `_work/b2/e2e-b2-r3.log` |

## 未执行（not_run）

| 项目 | 原因 |
| --- | --- |
| 真实模型调用（AI 建议/补题/知识点候选） | 无授权凭证；全部受控替身 |
| 真实 Word/WPS 排版检查 | 本机无法自动验证；只做结构级断言（不把 XML 存在当排版通过） |
| 真实 Qdrant / 真实数据根迁移演练 | 禁止；正式库当前为"已应用 B2 迁移、无业务写入"（见 README §5.7 披露） |
| 真实 DOCX/XLSX 业务文件 | 未提供脱敏真实文件；样本程序化构造 |
| 200 人以上压力测试 | 契约上限 2000，本批验收只要求 200（已记录耗时） |

## 资源与提交

- 无本批启动的常驻进程/端口残留（E2E 的 5174 由 Playwright 自管自停）；测试数据全在 `tmp_path`。
- **未提交、未推送、未切分支**（HEAD 仍为 `0f4b8cb`）；改动以工作区差异交付。
- `apps/web/next-env.d.ts` 每次 typecheck/build 后被重写，收尾时已还原。
