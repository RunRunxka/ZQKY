# B3 前端独立审查证据

仅新增本目录 `ui_*` 文件；产品、冻结件、正式数据与正式浏览器会话未改。两个 Python 探针在 `TemporaryDirectory` 中先设置 `ZQKY_DATA_DIR` 再导入应用；HTTP 使用 TestClient 8001（未监听端口），模型使用受控 Provider。Vitest 使用真实组件/hooks/API 客户端，仅替身 fetch/缺失的 jsdom dialog 方法。

## UI-01 — P1 初次 AI 补题观察拒绝正常首次 claim

- 产品定位：`apps/web/src/features/question-bank/jobs.ts:220`（`adoptJobView(next, exactAttemptWindow(next.attempt))`）。窗口函数在 48–49 行。
- 真后端创建返回 `queued, attempt=0`，首次 claim 后 `succeeded, attempt=1`。真实创建/执行/落库结果见 `ui_generation_fixture.json`。
- 实际 hook 接收这两个真实 JSON 后仅查询一次，显示“新的尝试接管”，停在 `queued@0`，候选批次 ID 仍为空、终态回调未触发。成功和失败的初次任务都无法正常观察。
- 修复方向：初次 queued 收据应容纳首次 claim，初次 N=0 的合法观察窗口为 `[0,1]`；更高尝试仍须停止旧观察。测试需使用真实 create 收据的 attempt，不以 queued(1)→terminal(1) 模拟初次创建。

## UI-02 — P1 文件缺考/免考标记产生伪 missing 承认，阻止合法成绩确认

- 产品定位：`apps/web/src/features/assessments/labels.ts:328`–349（只根据施测出勤过滤 present，逐原始单元格计数，未应用文件标记整人次 absent/exempt 语义）；`ScoreImportReview.tsx:557`–560 强制勾选推导 missing。
- 真场景：两人三题，施测默认 present；甲文件分数为 `(缺考,空白,空白)`，乙为 `(2,3,5)`。后端按文件标记把甲整行记 absent，`missingCellCount=0`。
- 前端却推导甲 2 个 missing，并强制勾选后才能确认。实际组件发送该伪范围；同场景真 API 返回 422 `SCORE_ACKNOWLEDGEMENT_MISMATCH`。取消伪 missing（`missing=null`）的正确请求真 API 返回 200，但页面取消勾选后禁用确认，无法发出正确请求。
- 原表行接口只返回映射分数列；本结论没有把学号/姓名/备注列计入。真实接口数据见 `ui_absence_fixture.json`。免考同样走整行状态覆盖，属于同一逻辑缺口。
- 修复方向：优先暴露并直接承认后端预览的权威范围；至少让前端推导遵循后端的文件标记覆盖全部叶语义，再覆盖 present 快照与单格标记/其余空白的真实 API 链。

## UI-03 — P2 卸载后的旧创建响应仍覆盖父级施测选择

- 产品定位：`apps/web/src/features/assessments/AssessmentsPanel.tsx:170`–176（`useFrozenSubmission` 的 `run` 内先执行 `setCreated/onSelectAssessment/onChanged`）。
- 条件：创建施测请求在途时切班级或换原卷，工作区用 class/paper key 重挂载创建面板。旧响应抵达时 hook 自身虽然会拦截过期结果，但 `run` 内父级回调已经执行，旧施测重新成为当前选中施测。
- 实证：真实 AssessmentsPanel 发起 POST 后卸载；延迟 fetch 返回成功，`onSelectAssessment('old-assessment')` 与 `onChanged()` 仍各执行一次。
- 修复方向：`run` 只做请求并返回，父级/页面副作用放在 `await submission.submit(...)` 返回非空之后；卸载/操作身份失效返回 null 时不更新父级。

## 已执行命令

1. `apps/api`：`$env:PYTHONUTF8='1'; uv run --no-sync python ..\..\docs\qa\TEACHING-LOOP-B3-REVIEW-20261001\probes\ui_absence_source.py`。退出 0：UI 推导载荷 422，正确载荷 200。
2. `apps/api`：`$env:PYTHONUTF8='1'; uv run --no-sync python ..\..\docs\qa\TEACHING-LOOP-B3-REVIEW-20261001\probes\ui_generation_source.py`。退出 0：202 queued@0 → succeeded@1，真实候选批次落库，受控 Provider 1 次调用。
3. 根目录：`$env:NODE_OPTIONS='--no-experimental-webstorage'; node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_vitest.config.ts`。最终退出 0：3 文件 / 4 测试通过（独立探针确认缺陷存在）。

探针准备阶段出现过三类夹具错误：Python 使用错误字段 `assessment.id`（改为真实 `assessmentId`）；独立目录 JSX 未自动转换（专用配置启用 automatic）；jsdom 缺 `dialog.showModal/close`（只为测试添加 DOM shim）。它们不属于产品缺陷，最终以上三条命令均已通过。

没有执行全量回归/构建/E2E、真实模型、正式 Word/Qdrant、正式数据迁移或浏览器会话操作。本审查不宣称这些边界已通过。
