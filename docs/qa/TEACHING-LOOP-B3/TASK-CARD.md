# TEACHING-LOOP B3 任务卡（G0 前置修复 + 成绩后端 / 导入工作区 / 题库前端）

- 批次：**B3 = G0（B2 审查前置修复）+ T60 + F20-I + F10-QB + CTRL**；起点 `main@0f4b8cb1`（B2 r2 **84/84 一致**，未提交）。
- 审查输入：`docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/REVIEW.md`（B2-RV01–11 + 已披露项）。原证据只读保留，不追改历史。
- 阶段：**G0 关闭并独立复验后**才进入业务段（T60/F20-I/F10-QB）；G0 冻结 `FROZEN-G0.json`。

## 0. 文件归属

| 归属 | 新建 | 修改 |
| --- | --- | --- |
| **CTRL** | `app/services/jobs/registry.py`、`app/services/knowledge_refs.py`、`app/core/migrations/rebuild.py`（受控重建）、`tests/test_b3_g0_public.py`、`tests/test_rebuild_migration.py`；B3 业务期：`app/contracts/scores.py`、`apps/web/src/contracts/scores.ts`、`app/services/tabular.py` 扩展（原始类型/公式/坐标读取）、分数相关 schema/路由注册 | `app/services/model_runtime.py`（`resolve_frozen_model`）、`app/services/jobs/engine.py`（publish 失败收敛/`is_tracking`）、`app/api/v1/workflow_jobs.py`（retry 调度）、`app/main.py`、`app/contracts/papers.py` + TS、`app/core/migrations/teaching.py`（`0005` 标题快照、成绩迁移）、`docs/{API,ROUTES,PROJECT_GUIDE,CURRENT_STATUS}.md`、实施计划、`docs/qa/TEACHING-LOOP-B3/**` |
| **G0-A 原卷** | `apps/api/tests/test_papers_issue_resolution.py`、`test_papers_block_views.py`、`test_papers_revision_title.py` | `app/services/papers/{service,proposals,imports}.py`、`app/repositories/teaching/papers.py`、`app/api/v1/papers.py`（按 CTRL 冻结契约） |
| **G0-B 题库/任务域** | `apps/api/tests/test_question_lease_batches.py`、`test_question_subject_links.py`、`test_model_drift_guards.py` | `app/repositories/question_bank/catalog.py`、`app/services/question_bank/{service,generation}.py`、`app/services/knowledge/service.py`（仅注册执行器）、`app/api/v1/question_bank.py`（如需） |
| **G0-C 施测/前端** | `apps/api/tests/test_assessment_held_on.py`；`apps/web/src/features/knowledge-points/hooks.strictmode.test.tsx`（或扩展既有） | `app/services/assessments/service.py`、`apps/web/src/features/knowledge-points/hooks.ts`（+既有测试）、`apps/web/src/services/workflow-jobs-api.ts`（观察代次语义，按 CTRL 契约） |
| **T60（业务段）** | `app/repositories/teaching/scores.py`、`app/services/scores/**`、`app/api/v1/scores.py`、`apps/api/tests/{scores_support,test_scores_*}.py` | 无 |
| **F20-I（业务段）** | `apps/web/src/features/assessments/**`、`apps/web/src/services/assessments-api.ts`(+test)、`apps/web/src/app/assessments/**`（薄路由）、`tests/e2e/assessments.spec.ts` | 无（导航/ROUTES 由 CTRL） |
| **F10-QB（业务段）** | `apps/web/src/features/question-bank/*Knowledge*`、相关测试 | 现有 `features/question-bank/**`、`services/question-bank-api.ts`（+测试） |
| **V00** | `docs/qa/TEACHING-LOOP-B3/{V00-G0-REPORT-01.md, V00-REPORT-*.md}`、`V00-probes/**` | 无（只读） |

## 1. G0 关闭矩阵（B3-RV01–11 + 已披露项）

| 编号 | 缺陷（审查原文摘要） | 责任 | 关闭判据（正确行为，不是"探针 exit 0"） |
| --- | --- | --- | --- |
| RV01 | 公共 retry 只置 queued，无执行器调度 | CTRL（registry+路由+引擎）+ B（注册 question/knowledge）+ A（注册 teaching） | 真装配下失败→retry→**新 attempt→终态**；重复点击/并发 retry 幂等（一次执行）；入队后调度异常留 queued 可再 retry；重启后 queued 不自动重放（显式 retry 才调度）；观察语义：retry 收据 N，接受 queued(N)→running/terminal(N+1)，拒绝 N+2 |
| RV02 | 任意 resolution JSON / 空题面可通过确认 | A（契约由 CTRL 冻结） | 结构化处置（supplement_text/supplement_asset/exclude）；补录写入目标块/资产并核验存在；排除仅限非内容损失码且带理由；空计分题面、缺必要共同材料、未解决内容损失一律拒绝 |
| RV03 | 未归属块接口无正文，资产不可读 | A（契约由 CTRL 冻结） | `PaperSourceBlockView.content` 返回持久化块；受控资产内容接口（仅该修订引用过的受管键）可读；无题号文档/孤立块/公式/合并表格/图片可审阅；任意路径被拒 |
| RV04 | 模型漂移仍按旧指纹记录 | CTRL（`resolve_frozen_model`）+ A/B 接线 | 调用前比对真实配置指纹；漂移明确失败（`MODEL_CONFIG_DRIFT`），来源与执行一致；快照不含凭证 |
| RV05 | 整理中间批不校验租约 | B | `record_organize_batch` 在**同一事务**核 lease/token/attempt/running/取消；旧 attempt、失权、interrupted/终态迟到零写入；正常路径不受影响 |
| RV06 | 确认不复核已归档知识点 | CTRL（helper）+ A/B 接线 | 确认在 `PublicationCoordinator` 内复核身份/修订/学科/未归档后再写；归档后确认被拒；历史已确认关联可读 |
| RV07 | 改题学科继承旧关联 | B | 学科变化时核验完整关联集合：冲突要求显式替换/清空或拒绝；同学科改内容仍复制旧关联 |
| RV08 | 施测改日期绕过归属确认 | C | PATCH 日期后逐人次重核归属；失效 → 422 定位（要求显式重确认，经 `participants` 重确认路径），不改归属历史与快照；"今天导入名单确认过去考试"仍可用 |
| RV09 | StrictMode 下 hook 永久失效 | C | setup/cleanup 对称（每次 setup 恢复标志），StrictMode 双调用下观察正常；真实 StrictMode 测试 |
| RV10 | 旧 retry/cancel 响应接管新任务 | C | 操作绑定 jobId+观察代次；reset/切换/卸载使旧响应失效；迟到成功/失败都不污染新任务；pending 可解释 |
| RV11 | 新草稿标题改旧修订展示 | CTRL（迁移 0005）+ A（写入/读取） | `paper_revisions.title_snapshot` 非空；固定修订内容 API 与 reader 读自己的快照；旧数据回填标注来源（`title_snapshot_source='backfilled_from_paper'`），不声称还原原标题 |
| 已披露 | publish 异常后任务停 running | CTRL（引擎） | 发布事务回滚后，用**本次执行开始时的原 JobLease** 在新短事务 CAS 收敛 `failed`（取消优先→`cancelled`；失权零写入）；三业务域一致；无半批、无永久 running |

## 2. G0 验收

- 每个 RV 至少一条**正确行为回归**（替换/补充原诊断探针的断言方向），跑通即 pass；探针本身（`docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/`）只读保留，其"缺陷存在"结论在修复后应**失败**（可作反向对照）。
- 后端定向 + 全量 `test:api`；前端 `test:unit`/`typecheck`/`lint`；G0 阶段不强制 build/e2e（业务段统一跑）。
- 冻结 `docs/qa/TEACHING-LOOP-B3/FROZEN-G0.json` → 只读 V00-G0（自建探针 + 故障注入）→ 无阻塞 fail 后进入业务段。

## 3. 业务段要点（T60 / F20-I / F10-QB）

- **T60**：见授权原文第五、六节——输入限定教师 XLSX/CSV 小题得分；`tabular` 扩展原始类型/公式与缓存视图/真实坐标/不截断（≥100 计分叶）；Decimal ×100 整数；0/missing/absent/exempt；participantId 定位人次、学号前导零、姓名非主键、人工消歧；列映射固定 scoredLeaf；全矩阵 = 冻结参测集合 × 固定叶子；缺行缺列显式 missing 且确认需逐类承认（保存承认范围+预览版本）；出勤冲突阻断并可校正；总分仅全 recorded 才核对；预览持久化 + 冻结原件散列/sheet/映射/快照/双 revision；确认事务顺序（重放→预览版本→施测版本+active=base→阻断与缺失确认→draft+矩阵+快照→封存→active+施测版本→导入已确认→幂等结果）；并发双确认只前进一批；修正=从不可变 base 复制全矩阵+当时快照→新完整版本（默认 base 必须 active，审计保留原值/新值/理由/坐标）。
- **迁移**：`score_imports`/`score_import_rows`/`score_revisions`/`student_item_scores` + `participant_snapshot_json`；复合约束（同施测/同卷/同题/同人次；版本施测内唯一；base/sourceImport 不跨施测）；confirmed 不可变 + 封存闸门（按**该修订的**快照核完整性）；`assessments` 重建（CTRL 受控方式）：移除 `active_score_revision_id` 的"仅空"CHECK，恢复 `(active_score_revision_id,id)→score_revisions(id,assessment_id)` DEFERRABLE 复合外键，阻止 active 指向 draft；保留主键/字段/引用/索引/触发器；`source_practice_revision_id` **继续只能空**。
- **F20-I**：`/assessments` 工作区（名单→原卷→施测→成绩→历史）+ 真实浏览器链（至少一条真隔离 FastAPI）；五步成绩流；0/missing/absent/exempt 显著区分；真实行列地址；409 保留编辑/422 保留校对；逻辑确认冻结 submissionId+原 payload 直到明确结果；切换/卸载失效旧请求；200 人×100 叶规模与分页/虚拟化记录。
- **F10-QB**：既有题库增量（知识点筛选/标注/关联更新、旧 knowledgeTags 单独呈现、补题入口六态/取消/真实重试、AI 来源与校对链、`200+failures` 仍显示整批未确认）；不做练习组卷/学情驱动。

## 4. 预先登记（G0 阶段）

1. RV01 的重试语义：`store.retry` 返回 queued(N)，调度后 claim 才 N+1；前端观察用 [N, N+1] 窗口（CTRL 冻结 `observeJob({minAttempt,maxAttempt})`），N+2 视为被接管。
2. RV04 的历史任务：`model_snapshot_json` 无 fingerprint 的旧行（B2 前的 knowledge/teaching 任务）→ 明确失败码 `MODEL_FINGERPRINT_MISSING`（要求新任务），不静默放行。
3. RV11 旧数据回填只写 `title_snapshot = papers.title` 且标注来源；无法证明是"当时标题"。
4. `assessments` 重建使用 CTRL 的受控迁移方式（事务外设置外键状态、事务内新建/拷贝/替换/校验、finally 恢复并核验 `foreign_keys=ON`），并在**含已确认卷与多施测的 B2 旧库**上验证触发器和数据。
5. 审查探针在修复后应按预期"失败"（不再复现缺陷），作为反向证据；不修改审查目录内容。

## 5. 结果格式

同 B0–B2：任务 ID/版本、起点、可写范围、实际修改文件、正常路径、失败/取消/重试/恢复、兼容与迁移、验证命令+退出码+证据、首败与修复、未执行、剩余问题、资源释放、状态。

## 6. G0 关闭记录（2026-10-01）

- **候选与冻结**：`FROZEN-G0.json` r2 共 106 文件；r1→r2 差异**恰好 3 个文件**
  （`app/core/migrations/teaching.py`、`tests/test_b2_migrations.py`、`tests/test_migrations.py`），r1 记录保留为 `FROZEN-G0-r1.json`。
- **独立验收**：V00-G0 r1（`V00-G0-REPORT-01.md`）RV01–RV10 + 已披露 publish 收敛 + RebuildPlan 机制 pass，
  RV11 迁移 fail；修复后 r2 窄复验（`V00-G0-REPORT-02.md`）**全项 pass**：
  p12 最小复现由 fail 转 pass、自建三形状变体（两已确认 / 一草稿+一已确认 / 列已存在）pass、
  RV11 判据全项（回填+来源标注、触发器 token 级逐字恢复、`foreign_key_check` 空、`integrity_check=ok`、
  失败回滚可重跑、0005 散列不变）、RV01 与 publish 收敛重跑与 r1 同数。
- **口径更正（采纳 V00 r2）**：RV01 并发重复 retry 的合法结果应表述为
  「全部 ∈ {200, 409} 且**恰好执行一次**（attempt +1、上游调用 +1、终态唯一）」，
  修正 r1 报告中「恰好一个 200」的表述。
- **残留观察（非 fail，登记备查）**：V00 r2 无法取得 r1 时点的 `teaching.py` 源码字节做全文件 diff，
  仅能验证 0005 三条声明逐字一致 + 同散列登记不漂移 + 0.005 行为全绿；CTRL 侧的 r1→r2 差异记录
  以本目录两份 FROZEN 文件为凭据。
- **G0 后基线**：全量 `test:api` 1365 passed / 1 failed（R-19 冷启动间歇，整文件 14/14 通过，按台账管理）；
  合并入业务段后统一重跑全量与 e2e。

## 7. B4 交接（B3 交付时随报告冻结）

- **已就绪的稳定输入**：固定 `scoreRevisionId`（成绩修订，含 `participantSnapshot` 与 `itemSnapshot`）、
  固定 `paperRevisionId`（每行计分叶的 `item_id`/`max_score_units`）、完整矩阵
  （`student_item_scores`：人次 × 叶，四态 + `score_units`）与参测人次快照；
  学情/失分归因（`any_loss_v1`）可直接以"该修订的缺失/错误单元集合"为输入，不需再解析原表。
- **边界（B3 未实现，B4 若要须另行授权）**：T70 学情分析、T80 教案生成（AI）、成绩全量数据展示
  （本批只做矩阵分页与修订历史）、AI 教案、练习转换链路（`source_practice_revision_id` 外键仍未建立，
  继续只能为空）、出勤校正独立端点、导入预览 missing/absent 明细的服务端字段。
- **公共设施可复用**：`tabular.read_score_sheet`（公式/缓存双视图 + 物理坐标 + CSV + 线性读取）、
  `JobExecutorRegistry`（新增模型任务只需注册 `(domain, kind)` + `resolve_frozen_model`）、
  `RebuildPlan` 受控重建（后续结构变更照此办理）、`PublicationCoordinator` 复核模式。
