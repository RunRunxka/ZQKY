# TEACHING-LOOP B1 批次证据（富内容基础 / 知识点后端 / 名单后端）

- 批次：**B1 = CTRL + T10 + T20 + T30-a**（依 [多Agent实施任务计划书 v2.0 §二.3](../../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)）
- 起点：B0 r2 工作树（`main@301fc356493db21d187ab85f32fd49dfffdc51ef` 的未提交交付；
  开工核对 [B0 r2 冻结记录](../TEACHING-LOOP-B0/FROZEN-CANDIDATE.json) **55/55 一致、0 差异**）
- 日期：2026-09-30
- 任务卡（范围/归属/契约/验收）：[TASK-CARD.md](TASK-CARD.md)；独立验收任务卡：[V00-TASK-CARD.md](V00-TASK-CARD.md)
- 冻结指纹：[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)；命令与结果：[EVIDENCE-COMMANDS.md](EVIDENCE-COMMANDS.md)
- 候选停止写入时刻：见冻结记录；**独立验收后如再做修复，须重新冻结并在 §4 说明**

## 1. 本批交付

| 计划 B1 条目 | 交付 |
| --- | --- |
| 富内容基础（T10） | `app/services/rich_content/`：DOCX 富解析（段落/表格合并单元格/图片真实字节与尺寸/OMML 原样/未知对象可见问题/共同材料保守分组/表格 `columnCount` 网格宽度）+ DOCX 渲染（学生/教师投影、共同材料一次、图片 relationship 重建、LaTeX→OMML 失败保留定位） |
| 知识点后端（T20） | 身份/不可变修订/父树/别名/归档；教材依据（区间经教材目录核验、冻结标题、`locatorHash`）；XLSX/CSV 导入预览与整批确认（幂等、拓扑、`clearFields`）；AI 候选（`knowledge:suggestion` 任务，候选仅待确认批次，写入与任务终态同库同事务） |
| 名单后端（T30-a） | 班级/学生/归属历史（转班保留旧归属）、名单导入（学号文本、人工身份核对六类建议、未出现不退班、整批回滚、幂等确认）；施测只冻结契约（501 未实现） |
| 共享装配（CTRL） | 迁移 0002（两库）、契约（knowledge/roster 后端 + TS 镜像）、`PublicationCoordinator`、`tabular.py`、`main.py` 装配与可选路由、依赖（openpyxl/math2docx） |

**未做（按范围）**：原卷（T40）、成绩（T60）、学情（T70）、练习（T80）、教案后端（T90）、真实施测创建（T30-b）、
任何新增前端页面；不改既有教材解析语义。

## 2. 迁移与兼容

| 库 | 迁移 | 内容 |
| --- | --- | --- |
| 知识点库 | `0002_knowledge_business_tables` | 设计 5 表 + 3 索引 + 4 触发器（`KNOWLEDGE_CYCLE`、`IMMUTABLE_REVISION`）+ `knowledge_imports`/`knowledge_import_rows`（B1 冻结补齐，+2 索引） |
| 知识点库 | `0003_knowledge_import_issues_column` | `knowledge_imports` 补 `issues_json`（批次级问题独立落列；纠正 0002 的字段缺口） |
| 教学库 | `0002_teaching_business_tables` | `classes`/`students`/`class_memberships`（含 `ux_active_membership` 部分唯一索引、`ix_membership_student`）+ `roster_imports`/`roster_import_rows`（+4 索引） |

- `0001` 四条声明散列与 B0 登记逐字节一致（正式数据根只读核对 0 漂移）；施测三表留 T30-b。
- 启动门控 `REQUIRED_TABLES` 仍只要求 B0 基础表：仅 B0 结构的旧库可启动，迁移后新表齐备（A2）。
- B1 对 B0 文件的回改逐条登记在 [TASK-CARD §0](TASK-CARD.md)（含 `error_details` 真实缺陷修复与 `TableBlock.columnCount` 契约增补）。

## 3. 验证（实跑；命令/退出码见 [EVIDENCE-COMMANDS.md](EVIDENCE-COMMANDS.md)）

- 后端全量 `npm run test:api`：r1 候选 `1167 passed / 1 failed`（唯一失败为台账 **R-19** 冷启动间歇，
  单例单跑失败、整文件 14/14 通过，与本批 diff 面零交集）；**r2 候选 `1170 passed / 0 failed`（退出码 0）**。
  基线 B0 r2 = 1011 passed。
- 定向：T10 富内容 46 例；T20 知识点 49 例；T30-a 名单 40 例；CTRL 基础设施（迁移/门控/表格/协调器/契约）33 例；
  B0 回归套件（jobs/assets/submissions/backup/question-bank/textbook）全绿。
- 前端：`NODE_OPTIONS=--no-experimental-webstorage npm run check` 退出码 0（typecheck + lint 0 警告 +
  unit `76 文件 / 733 例` + build）；本批前端只有契约镜像与 `columnCount` 同步，无页面改动 → **e2e not_run**。
- 装配冒烟：`openapi()` 实见 10 条 knowledge 路由与 12 条 roster 路由；四服务（asset_store/file_assets/
  publication_coordinator/textbook_evidence/knowledge_service/roster_service）全部装配。
- 独立验收 V00：见 §6。

## 4. 首败与修复

| 编号 | 现象 | 修复 |
| --- | --- | --- |
| B1-F1 | **B0 契约缺陷**：`error_details()` 因 `ErrorDetails` 未开 `populate_by_name` 而抛 ValidationError（T10/T30-a 双双踩到；B0 验收未覆盖该 helper） | CTRL：所有契约模型统一开启 `populate_by_name`；`test_contracts_b1.py` 回归；T30-a 改回共享 helper，T10 删除 workaround |
| B1-F2 | **表格行结构丢失**：`TableBlock.cells` 扁平序列无行边界，无法精确还原（T40/T50/前端消费必需） | CTRL：新增可选 `TableBlock.columnCount`（加法式）；T10 解析必填、渲染优先使用；前端镜像同步 |
| B1-F3 | B1 登记 0002 后两个 B0 测试断言（迁移计数 1）失败 | CTRL：按新契约更新计数断言（非产品行为变化） |
| B1-F4 | **批次级 issues 无列可落**：`knowledge_imports` 只有 mapping/warnings，T20 一度塞进 `mapping_json` 保留键 | CTRL：追加迁移 `0003` 补 `issues_json`；T20 改用独立列并保留旧布局容错读取 |
| 其余 | 各实现者自检首败（视图别名构造、SQL 关联、vMerge 记账、材料锚点分组等） | 见各自结果卡；均有最小复现与回归用例 |

## 5. 遗留与边界（如实登记）

1. `ux_active_membership` 不阻止同一学生同时在两个班活跃（设计原文如此），业务层不额外收紧。
2. 施测真实创建（T30-b）依赖 T40 已确认原卷修订；此前 `POST /assessments` 保持 501。
3. 富内容 LaTeX→OMML 只用于新题导出；不支持 OMML→LaTeX 反向转换。
4. DOCX 视觉排版（Word/WPS 实际打开）本机无法自动验证：结构级断言 + `not_run`，不把 XML 存在当排版通过。
5. 真实模型调用、真实 DOCX/XLSX 业务文件、真实 Qdrant 均 `not_run`。
6. `knowledge_imports.file_asset_id` 是跨库逻辑引用（EXT）；AI 批次先登记教学库资产再写知识点批次，
   两步之间失败会留下未被引用的资产登记（只增不改）。
7. 本批没有真实教学质量/真实文件的证据；"自动化通过"不等于业务或模型质量通过。

## 6. 独立验收（V00）与 findings 处置

独立验收报告：[V00-REPORT-01.md](V00-REPORT-01.md)（探针与证据在 [V00-probes/](V00-probes/)；12 个自建探针、264 项检查）。
**结论：V1/V3–V8/V10 pass，V2 与 V9 fail，另 17 条 observation，无假成功、无零写入违背。**
fail 与关键 observation 已逐条处置，修复后重新冻结 **r2** 并窄复验（[V00-REPORT-02.md](V00-REPORT-02.md)）。

### 6.1 fail 与 observation 处置

| 编号 | 等级 | 内容 | 处置 |
| --- | --- | --- | --- |
| V00-F1 | **fail** | 自指父与成环父错误缺 `details.issues[].field`（`would_create_cycle` 是死代码；环仅由 DB 触发器翻译且无 details） | T20 修复：`_resolve_parent` 写入前预检（自指 422 `KNOWLEDGE_PARENT_INVALID`、环 422 `KNOWLEDGE_CYCLE`），field 按入参给 `parentId`/`parentCode`；触发器兜底与仓储同形状；新增 3 例；**CTRL 用正式装配独立复现通过** |
| V00-F2 | fail（文档） | API.md / PROJECT_GUIDE §12 / AGENTS.md 未登记 `0003_knowledge_import_issues_column` | CTRL 已补三处 |
| V00-F3 | fail（文档） | PROJECT_GUIDE §12"自指/环…可定位"高于实现 | F1 修复后成立；措辞保留 |
| V00-F4 | fail（文档） | `POST /api/v1/classes/{id}/restore` 已注册但文档未列 | CTRL 已补 API.md 与任务卡 §4 |
| V00-O1 | observation | `0003` 裸 ALTER 无 adjust 钩子：列已存在但未登记时抛原始 sqlite3 错误且不自愈 | CTRL 已修：补 `adjust` 钩子（列已存在则跳过；声明与散列不变）；探针验证可重跑 |
| V00-O2 | observation | 列被手工删除而登记仍在时不重补（注册表驱动） | 按"只追加"语义接受，登记为边界 |
| V00-O4 | observation | `publish` 抛错时任务停 `running`（同事务回滚成立、非 succeeded） | B0 引擎契约明确"异常向上抛"；收敛靠租约过期/重启 reconcile → 可重试；登记为边界（任务卡 §8.8） |
| V00-O6/O8 | observation | 名单同身份冲突由 DB 唯一约束在写入时兜底（409 + 行定位 + 零写入） | 接受：禁止假成功、可重试；登记（任务卡 §8.7） |
| V00-O7 | observation | 同名（两行都无学号）`link + create` 未阻断 | 判定为**教师显式消歧**，允许（姓名不是主键）；登记（任务卡 §8.7） |
| V00-O10 | observation | `KNOWLEDGE_SUBJECT_UNKNOWN`/`KNOWLEDGE_LINK_INVALID` 定义但从不抛出 | API.md 改为实际抛出集合 + 保留码说明 |
| V00-O11 | observation | `.txt`/`text-plain` 按 CSV 解析 | API.md 明确说明 |
| V00-O12/O16 | observation | `details.fields` 元组 repr、`textbook.ts` 同名 `JobView` | 均 HEAD 既有、不在本批 diff 面 → 登记，不属本批 |
| V00-O3/O5/O9/O13/O14/O15/O17 | observation | 正式库待应用迁移、AI 资产先落盘、未装配校验顺序、跨班活跃、批次 issues 派生、未用视图类型、排版 not_run | 与任务卡 §8 预先登记一致 |

### 6.2 冻结修订与窄复验

- **r1**（记录保留在 [FROZEN-CANDIDATE-r1.json](FROZEN-CANDIDATE-r1.json)）：95 文件，V00 两轮复算 **95/95 一致**。
- **r2（本批最终候选）**：相对 r1 变化 **10 个文件**（产品/测试 4：`repositories/knowledge/points.py`、
  `services/knowledge/service.py`、`tests/test_knowledge_points.py`、`tests/test_knowledge_imports.py`；
  迁移 1：`core/migrations/knowledge.py`；文档 5：`API.md`、`PROJECT_GUIDE.md`、`CURRENT_STATUS.md`、
  `apps/api/AGENTS.md`、`TASK-CARD.md`），逐项对账记录在 `FROZEN-CANDIDATE.json.changedSincePrevious`。
- **r2 窄复验（[V00-REPORT-02.md](V00-REPORT-02.md)）：全部 pass，无遗留 fail**——
  F1 独立复现（自指/环 parentId+parentCode、仓库直写兜底同形状、裸 SQL 触发器兜底、批内环 field=parentCode 且零写入，
  原 v2 探针 35/37 → **37/37**）；F2–F4 文档声明探针 16/19 → **19/19**；O1 修复验证（散列逐字节不变、
  "列在+未登记"可重跑、"列缺+未登记"正常补列，13/13）；r2 指纹 **95/95** 且差异恰为声明的 10 文件；
  B1 相关 13 文件 **178 例** exit 0、全量 **1170 例** exit 0（R-19 未出现）。
  r2 新增 6 条 observation 均为边界/文档口径（含"adjust 钩子在 BEGIN IMMEDIATE 前求值"的理论 TOCTOU —— 单进程 +
  数据根锁下不可达；`KNOWLEDGE_LINK_NOT_FOUND` 有抛出点但无契约常量；审计口径披露），无新 fail。

### 6.3 未获取的证据（如实登记）

- 真实模型调用（AI 候选全链路受控替身）、真实 Word/WPS 排版（仅结构级断言）、真实 Qdrant、
  真实业务 DOCX/XLSX 文件、正式数据根上的 B1 迁移演练（需写入授权）——全部 `not_run`。
- 台账既有间歇项（R-14/R-15/R-18/R-19）与本批 diff 面零交集，按 `docs/CURRENT_STATUS.md` 口径记录。
