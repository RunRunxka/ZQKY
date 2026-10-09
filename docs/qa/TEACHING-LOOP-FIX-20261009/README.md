# 教学闭环问题修复批（2026-10-09）

**范围**：落实用户三项指令——①修复 P1 教案生成链（等待与推理档对齐 + 失败原因可见）；②修复 P1 成绩导入跨班行死结（显式忽略 + 422 逐行原因回显）；③清理 2026-10-09 复走写入正式数据根的对象。对应问题登记见 [TEACHING-LOOP-WALKTHROUGH-20261009/README.md](../TEACHING-LOOP-WALKTHROUGH-20261009/README.md)。

---

## 1. 教案生成链（apps/api + apps/web）

**改法一：非流式等待按调用放宽（仿 10-08 提取先例）**

- 新增 `apps/api/app/services/lesson_generation/service.py`：`LESSON_TIMEOUT_SECONDS = 300`（有界放宽，注释记录 10-06 登记与 10-09 真机复现）。
- 调用点 `service.py:124`：`config = replace(handle.config, timeoutSeconds=LESSON_TIMEOUT_SECONDS)` 后同时用于 `provider.complete(config, request)` 与 `asyncio.wait_for(..., timeout=config.timeoutSeconds)`；超时报文带实际秒数。**其余任务等待不变**；任务心跳独立续租，调用时长不影响租约。
- 回归：`tests/test_lesson_generation_jobs.py::test_generation_widens_provider_call_timeout`（断言实发 config 的 `timeoutSeconds == LESSON_TIMEOUT_SECONDS` 且 > `DEFAULT_TIMEOUT_SECONDS`）；原超时/显式重试用例改为 monkeypatch 常量验证超时路径。

**改法二：失败原因上屏（apps/web）**

- `features/lesson-plan/components/ProposalPanel.tsx`：任务失败时渲染 `<p role="alert" data-testid="lesson-job-error">失败原因（{code}）：{message}</p>`（数据来自既有 `JobView.error`，无契约变更）。

**真机验证（正式数据 + 正式云端凭证，deepseek-flash 推理 max）**：

- 用上一批失败任务**完全相同的冻结载荷**重新发起（`workflow_jobs.1f38955c…`）：**31 秒 succeeded**，产出候选 `a141efde…`——修复前同载荷在第 30 秒被 `UPSTREAM_TIMEOUT` 掐断。
- 浏览器 UI 全链：教案工作台 → 补前置 → 生成（任务 `08b7461c…`，约 40–85 秒）→ **生成成功，待选择** → 逐字段差异（教学过程整段，45 分钟合计，引用教材 E1）→ 勾选「教学过程（整段）」→「仅采用所选完整字段」→ **候选终结并落库，教案修订 r3→r4（`ca33af38…`）**。这是 10-04 起首次走通的"生成→采用"完整路径。
- 失败面：改选 deepseek-v4-pro 再生成（任务 `4b7d9552…`）→ 面板显示 **失败原因（LESSON_PROPOSAL_INVALID）：模型输出未完整结束；候选未发布，请调整输出预算后重试。**（此前同类失败在界面上完全不可见）。

## 2. 成绩导入「不属于本次施测」（apps/api + apps/web）

**后端**：

- 迁移 `0012_score_import_rows_ignored`：`score_import_rows.ignored INTEGER NOT NULL DEFAULT 0 CHECK(ignored IN (0,1))`（历史批次默认 0，逐字保持原行为）。
- 契约（`app/contracts/scores.py`）：`ScoreImportRowPatch.ignored: bool | None`（`ignored=true` 显式忽略并清除手工定位；`participantId` 非空解除忽略）；`ScoreImportRowView.ignored`；`ScoreImportView.ignoredRowCount`；模块 docstring 补语义条目。
- 解析（`app/services/scores/imports.py`）：`RowInput/RowMatch.ignored`；`match_rows` 对忽略行直接落"已忽略"结果（不定位、不解析、不给问题）；`PreviewMatrix.ignored_row_nos` 进入摘要与审计。
- 服务（`app/services/scores/service.py`）：行补丁处理忽略决策（含互斥清理）；预览/刷新/确认三处 `RowPayload` 全量携带 `ignored`；`summary.preview.ignoredRowCount/ignoredRowNos`；确认时冻结忽略决策。**服务端绝不自动忽略任何行**。
- 回归：`tests/test_scores_imports.py::test_ignore_row_is_revocable_and_clears_manual_participant`（忽略→阻断消失→手工定位被清→撤销→阻断恢复）；`tests/test_scores_confirm.py::test_ignored_out_of_assessment_rows_unblock_and_confirm`（24 行表→忽略别班行→确认 200；矩阵只含参测人次；审计冻结）。

**前端**：

- 行级「不属于本次施测（忽略此行）」/「撤销忽略」按钮（`data-testid=score-row-ignore-N`）；忽略行显示灰色 chip、隐藏未匹配提示与阻断清单、禁用单元格校正；表头 meta 追加「已忽略 N 行（不属于本次施测）」。
- 确认 422 **逐行原因回显**：新增 `data-testid=score-confirm-issues` 横幅（code + message + `[原表第 N 行 · 字段 …]` 明细），此前仅 `SCORE_ACKNOWLEDGEMENT_MISMATCH` 有提示、其余 422 静默。
- 顺带修复 `hooks.ts` 保存载荷的潜在缺陷：同一行同时有定位/忽略/校正时合并为一个行补丁（服务端拒绝同一 `rowNo` 多条；旧实现会拼出重复行号）。
- 回归：`ScoreImportReview.test.tsx` 增 2 例（忽略补丁载荷与已忽略态；422 原因横幅）。

**真机验证（浏览器，一班施测 + 24 行整卷成绩表）**：上传 → 12 行别班学生 `SCORE_ROW_UNRESOLVED` 阻断 → 逐行点「忽略此行」→ 保存（批次 r2/v2，**零阻断**，"已忽略 12 行"）→ 承认（缺考 1 人次 + 空白 7 单元，忽略行不计入承认）→ 确认入库 **200**：批次 `aab3f04c…` 已确认，成绩修订 **v2 `55ca9d4b…`（12 人次 × 6 叶，基于 v1）**；矩阵 72 格 / 12 人次，忽略行不在矩阵；批次行审计 12 行 `ignored=1`。该场景此前是**永久 422 死结**。

## 3. 正式数据清理（本轮复走产物，全部软删除/可追溯）

| 对象 | 操作 | 结果 |
| --- | --- | --- |
| 班级 测试一班 / 测试二班 | `POST /classes/{id}/archive` | archived |
| 原卷 闭环测试_一元一次方程原卷（`1a09dfc1…`） | `POST /papers/{id}/archive` | archived |
| 施测 ×3（`88d854d3…` / `026c4c74…` / `9cf20f3d…`） | `POST /assessments/{id}/archive` | archived |
| 针对练习（`a9c788e7…`） | `POST /practice-sets/{id}/archive` | archived |
| 学情报告 ×3（`6cf7e9e0…` / `9339cb32…` / `07845144…`） | `POST /analysis-runs/{id}/archive` | archived |
| 教案 ×2（`798aa9a5…` / `7826b237…`） | `POST /lesson-plans/{id}/archive` | archived |
| 模拟教材（`87abb66d…`，高一·数学·人教A版） | `DELETE /textbooks/{id}` | 逻辑删除 + 清队列；**向量已由 `run_cleanup_queue` 实清**，活跃书册回到 58 册 |
| 正式题 ×6 | `DELETE /questions/{id}` | archived |

**边界与保留**：成绩修订/矩阵/导入批次/command submissions/文件资产/任务记录等审计行按设计不可删除，随已归档对象保留；`计科24-2`、`未命名教案`、既有 `测试试卷` 等**非本批对象**未触碰。

**顺带发现（P3，未修）**：`IndexService.run_cleanup_queue` 在生产代码中**没有任何调用点**（仅测试调用）——教材逻辑删除后向量清理不会自动发生、`cleanup_queue` 条目会永久滞留；本次由维护脚本手动执行。建议后续给启动自检或定时 janitor 增加触发。

---

## 5. 用户人工测第二批：#1 AI 补题稳定截断（同日追加）

**用户反馈**："AI 补题一直失败，提示模型输出被截断。"

**真机复现（用户自己的任务）**：`question_jobs` 中用户 15:31（07:31Z）创建的补题任务 `46c1fa0d…`（默认档 deepseek-flash、**count=10**、三种题型）18 秒后 `GENERATION_OUTPUT_TRUNCATED`「模型输出被截断（结束原因 length）」。

**根因**：`question_bank/generation.py` 旧口径固定 `MAX_OUTPUT_TOKENS = 4096`，且**推理 token 计入输出预算**——10 道题的题干/选项/答案/解析 JSON 加上推理思考在 4096 内写不完，`finish_reason=length` → 整批失败。同屏的整理器（8192）与教材提取（16384）此前已各自按真机数据放宽，补题是遗漏的一个。

**修法（本批）**：

- 输出预算改为**按题数伸缩、有界**：`TOKENS_PER_QUESTION=2048`、`MIN_OUTPUT_TOKENS=16384`、`MAX_OUTPUT_TOKENS=32768`，实际请求 = `min(max(下限, 题数×每题预算), 业务上限, 所选模型上限)`；`_output_budget(handle, count)`。
- 单次等待按调用放宽：`GENERATION_TIMEOUT_SECONDS=300`（`replace(config, timeoutSeconds=…)` 用于 `provider.complete`；推理档单次生成常态超过默认 30 秒，只放宽预算会改撞超时）；任务心跳独立续租。
- 回归：`tests/test_question_generation.py` 新增 2 例（预算/等待放宽断言；count=10 伸缩与模型上限压制），截断负向用例保持。

**未完成**：真机复测被上游 **HTTP 402 挡住**——DeepSeek 账户 `is_available=false`、`total_balance=-0.02 CNY`（`GET /user/balance` 实测）。充值后需复跑一次补题（同一界面路径）确认端到端成功。

## 4. 门禁（本批自测，非独立验收）

- 后端：`uv run pytest tests/` **2079 例全绿（exit 0）**；涉及 0012 的三处"已登记迁移清单"断言与 B5 备份排除清单同步更新（测试意图不变）。
- 前端：`tsc --noEmit` 0 错；`eslint apps/web/src --max-warnings=0` 通过；`vitest run`（`NODE_OPTIONS=--no-experimental-webstorage`）**133 文件 / 1605 例全绿**；`npm run build` exit 0。
- e2e：`assessments.spec.ts` **4/4**（含五步真实链、完整真实链、规模实测）、`lesson-plan.spec.ts` **9/9**。
- 真机：见第 1、2 节（真实云端调用 3 次：成功 1 + 失败 1 + UI 成功 1；浏览器操作全为真实链路）。

**未执行**：独立验收（RAG-accptance）、全量 e2e（174 例）、390px 复看、教师真实试评与 Word/WPS 原生排版。
