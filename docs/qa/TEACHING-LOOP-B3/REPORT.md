# TEACHING-LOOP B3 批次报告（G0 前置修复 + T60 + F20-I + F10-QB + CTRL）

- 日期：2026-10-01。分支 `main`，基线 commit `0f4b8cb190c2`（B2 r2 工作树，未提交）。
- 授权范围：用户明示「B3 = G0（B2 审查前置修复，RV01–RV11 + 已披露 publish 项）+ T60 成绩后端 +
  F20-I 导入工作区 + F10-QB 题库前端 + 共享契约/迁移/装配 + 独立验收；**完成本批后停止，不自动启动 B4**」。
- 交付状态：**实现与自检完成，独立验收 V00-B3 进行中**；未提交、未推送、未切分支、未改全局 Git 身份。
- 证据入口：[TASK-CARD](TASK-CARD.md)（含 G0 关闭记录 §6 与 B4 交接 §7）、
  [EVIDENCE-COMMANDS](EVIDENCE-COMMANDS.md)、`FROZEN-B3.json` / `FROZEN-G0.json`、`V00-G0-REPORT-01/02.md`、
  `V00-probes/`、V00-B3 报告（见 §7）。

## 1. G0（前置修复）：已关闭，独立验收 r2 全项 pass

- 11 项 B2 审查缺陷（[REVIEW](../TEACHING-LOOP-B2-REVIEW-20261001/REVIEW.md)）+ 已披露 publish 停滞项全部修复：
  - 公共 retry 经**唯一执行器注册表**真调度（注册表导入失败阻断启动；重复/并发 retry 幂等，
    合法结果 ∈ {200,409} 且**恰好执行一次**；观察窗口 [N, N+1]）；
  - 发布异常按**本次执行开始时的原 JobLease** 收敛 `failed`（请求过取消 → `cancelled` 优先；失权零写入），三域一致；
  - **冻结模型指纹**（`sha256(modelId, protocol, baseHost, apiFormat)`，不含凭证）：漂移 →
    `MODEL_CONFIG_DRIFT`，旧任务缺指纹 → `MODEL_FINGERPRINT_MISSING`；
  - 原卷/题库确认在 `PublicationCoordinator` 内复核知识点（归档 → `KNOWLEDGE_ARCHIVED`；
    无效 → `KNOWLEDGE_REFERENCE_INVALID`）；结构化问题处置（补文/补资产/排除）与受管资产只读内容接口；
    空题面/缺必要共同材料拒绝确认；
  - 整理器中间批建议与 checkpoint 在**同一事务**核 lease/token/attempt/running/取消（旧 attempt 零写入）；
  - 改题学科变化核验完整关联集合（显式替换/清空或 422）；施测改日期逐人次重核归属（显式重确认路径）；
    StrictMode hook 对称恢复 + 操作身份/观察代次；修订级标题快照（迁移 0005 + 来源标注回填）。
- 独立验收：`FROZEN-G0.json` r2（106 文件，r1→r2 差异恰 3 文件）经 V00 窄复验**全项 pass**
  （最小复现 p12 由 fail 转 pass、自建三形状变体、触发器 token 级恢复、失败回滚可重跑、0005 散列不变）；
  采纳其口径更正一处（retry 并发表述）。

## 2. T60 成绩后端（实现者交付 + CTRL 集成）

- 新增 12 文件：`repositories/teaching/scores.py`、`services/scores/{__init__,dto→并入契约,imports,matrix,service}.py`、
  `api/v1/scores.py`、测试 5 文件；33 例后端测试（导入/确认/修正/规模）通过，未改既有文件。
- 语义（与冻结契约一致）：教师 XLSX/CSV 原始小题得分、Decimal×100 整数单位、四态互不顶替、
  全矩阵 = 冻结参测人次 × 固定计分叶、缺行缺列显式 missing 不补 0、承认逐类且与预览完全一致、
  三版本权威、确认后不可变（DB 触发器 + 服务）、修正 = 复制全矩阵 + 当时快照 → 新完整版本 + 审计。
- CTRL 集成修复（皆为真实缺陷，非风格问题）：
  1. `read_score_sheet` 逐格 `.cell()` 超线性 → 改 `iter_rows` 一次性物化（200×102 由外推 >40 分钟 → **0.13s**），
     并补 **CSV** 支持（物理行号 = 文件行号，无公式视图）；
  2. `ScoreImportPatchRequest` 并入冻结契约（删 `services/scores/dto.py`）；
  3. `AssessmentView.activeScoreRevisionId` 补进后端契约/仓储/TS 镜像，前端改用权威字段（缺失才回退推断）。

## 3. F20-I `/assessments` 工作区（实现者交付 + CTRL 集成）

- 新建 16 文件：五步工作区（名单 → 原卷 → 施测 → 成绩 → 历史）、成绩流 upload → 映射 → 校对 → 承认 → 确认、
  修订历史与只读矩阵分页、修正入口；46 例单测 + 3 条真隔离后端浏览器用例通过。
- 关键行为：0/空白/缺考/免考显著区分（不只靠颜色）；异常显示原表物理地址（如「原表第 2 行 · 列 C」）；
  409 保留编辑与输入、422 保留校对；逻辑确认冻结 `submissionId` + 原 payload；切换/卸载使在途请求失效。
- CTRL 集成修复：100 列矩阵把文档撑宽到 7607px（单元格内 `.visually-hidden` 逃出滚动裁剪）→
  `.score-matrix-wrap/.score-matrix` 建立包含块，修复后 `scrollWidth = innerWidth = 1440`；规模用例由 200×10
  提升为 **200 人次 × 100 叶**（首屏 50 行 1105ms、翻页 1098ms）。

## 4. F10-QB 题库前端增量（实现者交付）

- 知识点筛选与标注（显式替换、422 字段级定位）、旧 `knowledgeTags` 独立分区呈现、补题六态 + 取消 +
  真实重试（[N, N+1] 窗口，N+2 判接管）、AI 来源与校对链（pending/apply/reject/stale）、
  `200 + failures` 显示**整批未确认**；159 例单测（含新增 70 例）通过，未改契约与后端。
- CTRL 补齐契约缺口：`QuestionDetail.knowledgeLinks`（`QuestionKnowledgeLinkView`）入 `contracts/question-bank.ts`。

## 5. 共享契约、迁移与装配（CTRL）

- 契约：`app/contracts/scores.py` + `apps/web/src/contracts/scores.ts`（导入/映射/单元格校正/承认/确认/修正/
  修订/矩阵分页/错误码；三者版本语义注释在案）。
- 迁移：`0006_teaching_score_tables`（四表 + 修正审计 + 快照列 + 封存闸门「按该修订自己的快照」+
  不可变触发器 + active 必须已确认）与 `0007_teaching_assessment_active_score_fk`（受控重建 `assessments`：
  去分期 CHECK、恢复 DEFERRABLE 复合外键、保留触发器与索引）；在**全新库 / 含业务数据的 B2 旧库 /
  正式库只读副本**三条路径验证：数据逐行保留、`foreign_key_check` 空、`integrity_check=ok`、回滚可重跑。
  期间修掉两个真实缺陷：重建会连带删掉 0006 建在该表上的 active 闸门触发器（已加入 restore）；
  触发器 `WHEN` 误把 NEW 与 NEW 比较（应为 OLD）。
- 装配：`main.py` 增 `_build_score_runtime` 与可选路由（模块缺失降级为警告）；`/assessments` 登记进导航与
  `docs/ROUTES.md`；`docs/API.md` 增 B3 接口节；`docs/PROJECT_GUIDE.md` §14 稳定决定；
  `docs/CURRENT_STATUS.md` 更新本批状态与口径。

## 6. 验证（本批实测）

| 项目 | 结果 |
| --- | --- |
| 后端全量 `uv run pytest tests -q` | 1405 用例；**第一轮全绿**；另两轮仅 **R-19**（台账既有冷启动间歇：整文件 14/14、单跑 3/3 失败，jieba 首载 ≈350ms > TTL 50ms） |
| `test_b3_score_migrations.py` + 迁移相关 | 35 passed（封存闸门/不可变/active 语义/旧库升级/对账失败回滚） |
| 规模 | 读取 200×102 = **0.13s**；后端 200×100 确认链 **2.13s**；浏览器 200×100 首屏 **1105ms**、翻页 **1098ms** |
| `NODE_OPTIONS=--no-experimental-webstorage npm run check` | **exit 0**：typecheck 0、lint 0 警告、unit **97 文件 / 927 例**、build 成功 |
| `npx playwright test`（全量，9.0m） | **149 passed / 1 failed**；唯一失败 = 台账 **R-14**（隔离 `--repeat-each=3` **3/3 通过**，未改用例、未放宽断言） |
| 冻结候选 | `FROZEN-B3.json` **162 文件**；相对 G0：+56 / ~20 / -0 |

## 7. 独立验收（V00-B3，只读）

- 派发内容：指纹自核与差异核对、成绩后端真实装配自建探针（含至少一处变异实验）、迁移三路径与散列不漂移、
  契约逐字段镜像比对、前端 spec 复跑与呈现检查、**对边界声明的反证**、G0 无回归抽查。
- **V00-REPORT-01 结论：可交付、无阻塞 fail**——163/163 一致；A1–A5（成绩正常链/失败路径/不可变+变异实验/
  修正/规模与 CSV）、B6–B7（迁移与散列不漂移、按修订自身快照）、C8–C10（契约镜像/前端 e2e 3-3/边界反证）、
  D11（G0 无回归；两条过期探针已用 B3 口径独立复算判非回归）全项 pass，另有 7 条观察项如实登记。
- **V00 后处置（r2）**：采纳其唯一镜像差项——`ScoreImportPatchRequest` 并入 `apps/web/src/contracts/scores.ts`，
  客户端改引用并再导出；定向验证（typecheck 0 / eslint 0 警告 / assessments 单测 46 例）通过后
  **重新冻结 `FROZEN-B3-r2.json`（163 文件，r1→r2 差异恰 2 文件）→ 定版 `FROZEN-B3.json`**，
  已请求 V00 窄复验（`V00-REPORT-02.md`）。
- **V00-REPORT-02 结论**：产品候选（含 r2 两处类型层改动）**通过窄复验、可交付**——
  契约镜像 **26↔26、0 失败**（`ScoreImportPatchRequest` 差项消失），typecheck 0 / eslint 0 警告 /
  assessments 单测 46/46 独立复现一致；同时指出**冻结清单登记过期**（我在冻结后才写 EVIDENCE/REPORT 两文档，
  产品逐字节未动）。已按建议重算散列并重新冻结（**逐次修订以冻结记录 `FROZEN-B3.json.revisionHistory` 为准**；
  产品与测试自 r2 起零字节变化，r2→定版差异恰为 3 个文档：本文件、`EVIDENCE-COMMANDS.md`、`docs/CURRENT_STATUS.md`）；
  V00 `p36`/`p37`/`p38` 独立复核 **163/163 自洽**，并指出冻结文本硬编码"定版 = rN"会随每次记录反复落后——
  已按"正文不再硬编码、以 `revisionHistory` 为准"改写，并把"最后一步 = 冻结"登记为 B4 起的流程要求
  （见 EVIDENCE-COMMANDS 冻结时序节）。
- **V00-REPORT-03 最终结论**：**产品候选可交付；冻结清单自洽**（定版 163/163；r2→定版差异恰三个文档、
  产品与测试/scripts 零字节变化；`contracts/scores.ts`、`services/assessments-api.ts` 保持 r2 字节）。

## 8. 如实边界（不声称已通过）

- 成绩导入预览的 missing/absent **明细集合没有服务端字段**：前端本地推导 + 服务端 422 定位兜底；
- 出勤冲突策略为「文件标记优先、不自动改施测快照」，**没有独立的出勤校正端点**（校正路径 = 重传修正文件）；
- 修正路径与确认路径的故障注入未做真实浏览器链（仅单测覆盖）；取消入口不可用（无取消端点，只呈现 `cancelled` 态）；
- F10-QB 全部用例为 stub fetch 替身，**无真实后端联调断言**（后端语义按只读源码逐条编码）；
- not_run：真实模型调用、真实 Word/WPS 排版、真实 Qdrant、正式数据根迁移演练（0006/0007 在正式库副本验证通过，
  正式应用在下次启动）；R-14 / R-19 按台账口径，未"修"未放宽；R-15/R-18 本批未复现。

## 9. B4 交接

见 [TASK-CARD §7](TASK-CARD.md)：固定 `scoreRevisionId`/`paperRevisionId`、完整矩阵与参测快照可直接作为
学情（`any_loss_v1`）输入；T70/T80、成绩全量数据展示、AI 教案、练习转换外键（`source_practice_revision_id`）、
出勤校正端点、预览明细字段均**未实现**，需另行授权。公共设施可复用：`read_score_sheet`、
`JobExecutorRegistry` + `resolve_frozen_model`、`RebuildPlan`、`PublicationCoordinator` 复核模式。
