# TEACHING-LOOP B1 · V00 独立验收报告 01

- 批次：TEACHING-LOOP B1（T10 + T20 + T30-a + CTRL）
- 候选：`main@301fc356493db21d187ab85f32fd49dfffdc51ef` 工作树的 B0 r2 + B1 交付（未提交）
- 冻结指纹：`docs/qa/TEACHING-LOOP-B1/FROZEN-CANDIDATE.json`（revision r1，95 文件 sha256）
- 验收者：独立验收 Agent（V00，只读产品代码）；时间：2026-09-30
- 交付：本报告 + `docs/qa/TEACHING-LOOP-B1/V00-probes/**`（自建探针与证据）
- 结论摘要：**V1 pass / V2 fail / V3 pass / V4 pass / V5 pass / V6 pass / V7 pass / V8 pass / V9 fail / V10 pass**
  （独立探针 264 项检查：259 pass、5 fail，fail 全部为错误定位字段与文档声明口径问题，无功能性假成功）

---

## 0. 候选基线与构成核对

### 0.1 95 文件 sha256 复算（必须先过）

```
$ python docs/qa/TEACHING-LOOP-B1/V00-probes/v00_fingerprint.py
frozen revision=r1 declared fileCount=95 entries=95
matched=95 mismatched=0 missing=0
FINGERPRINT_OK 95/95            # 退出码 0
```

- 开工核对与收尾核对（跑完全部探针 / 变异实验 / 实现者测试之后）**两次均为 95/95 一致**。
- 证据：`V00-probes/evidence/` + 本报告 §0.3。

### 0.2 候选构成（我的统计口径）

| 项 | 数量 | 说明 |
| --- | --- | --- |
| B0 r2 承接的产品/测试/脚本 | 53 | B0 FROZEN-CANDIDATE 55 项减去 B0 自己的 2 个批次文档 |
| 其中 B1 未改（字节一致） | 42 | 与 B0 r2 逐文件 sha256 相同 |
| 其中 B1 修改 | 11 | `AGENTS.md`、`contracts/teaching_loop.py`、`migrations/{knowledge,teaching}.py`、`main.py`、`tests/test_migrations.py`、`tests/test_startup_gates.py`、`web/src/contracts/teaching-loop.ts`、`docs/API.md`、`docs/CURRENT_STATUS.md`、`docs/PROJECT_GUIDE.md`（与 B1 任务卡 §0 回改表一致） |
| B1 新增产品/测试 | 40 | T10 5 + T20 9 + T30-a 9 + CTRL 共享组件/测试 17（含 `tabular.py`/`publication.py`/`workflow_jobs` 相关前端服务与测试） |
| B1 新增批次文档 | 2 | `TASK-CARD.md`、`V00-TASK-CARD.md` |
| 总计 | **95** | 42 + 11 + 40 + 2 |

### 0.3 实现者已停止写入 / 无残留

- 95 文件 mtime 快照（开工时 `V00-probes/_mtime_snapshot_1.json`）与收尾复算：**0 处变化**；`git status --porcelain` 68 项与开工一致。
- 收尾检查：`netstat` 无 8000/8001/5173/5174/6333 监听；无遗留 uvicorn/python 进程；探针临时目录（124 个 `zqky-v00-*` / `zqky-v10-*` / `zqky-pytest-*`）已清理。
- 探针纪律：每个探针先 `ZQKY_DATA_DIR=<临时目录>` 再导入 `app.*`；全程不读写正式 `.local-data`（唯一例外见 observation O13：只读 `schema_migrations` 对比，`mode=ro&immutable=1`，无锁无写）。
- 验收副产物的一次性副作用：`npm run typecheck` 内的 `next typegen` 会重写生成文件 `apps/web/next-env.d.ts`（`./.next/dev/types/*` → `./.next/types/*`）。已在收尾时**还原**（`git checkout -- apps/web/next-env.d.ts`），收尾 `git status` 回到 68 项、95 文件指纹 95/95；其余新增仅为 gitignore 的构建缓存（`.pytest_cache`、`tsconfig.tsbuildinfo`）。

### 0.4 探针清单（全部自建，不复用实现者断言）

| 探针 | 检查数 | 结论 |
| --- | --- | --- |
| `v1_migrations_probe.py` | 36 | 36 pass |
| `v2_knowledge_points_probe.py` | 37 | 35 pass / 2 **fail** |
| `v3_knowledge_imports_probe.py` | 38 | 38 pass |
| `v4_knowledge_suggestions_probe.py` | 23 | 23 pass |
| `v5_roster_probe.py` | 38 | 38 pass |
| `v6_rich_parser_probe.py` | 26 | 26 pass |
| `v7_rich_renderer_probe.py` | 18 | 18 pass |
| `v8_assessment_probe.py` | 19 | 19 pass |
| `v9_doc_claims_probe.py` | 19 | 16 pass / 3 **fail** |
| `v10_mutation_runner.py` | 10 | 10 pass |
| `v00_fingerprint.py`、`_probe_common.py`、`_rich_fixture.py` | — | 工具 |

命令（示例，其余同）：`cd apps/api && uv run python ../../../docs/qa/TEACHING-LOOP-B1/V00-probes/v1_migrations_probe.py`
证据：`V00-probes/evidence/*.json`（每项含 ok/detail）。

---

## 1. V1 迁移与门控 —— **pass**（36/36）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v1_migrations_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v1_migrations.json`、`evidence/v1_formal_registry_readonly.json`

关键输出摘录：

- ① 新库：知识点库 7 张 B1 表 + 4 个触发器（`kp_cycle_update`/`kp_cycle_insert`/2×`immutable_knowledge_point_revisions_*`）齐备；教学库 5 张表齐备；`ux_active_membership` 确为部分唯一索引 `CREATE UNIQUE INDEX ... ON class_memberships(class_id,student_id) WHERE left_on IS NULL`。
- ② 仅 B0 结构的旧库（注册表仅 0001）：`verify_existing_database` 通过（不判损坏/结构不符），`KnowledgeCatalog.migrate()` 后补齐 7 表并登记 0002/0003 → 契约"合法旧库可启动"成立；`REQUIRED_TABLES` 未被扩大（`('knowledge_submissions','knowledge_jobs')`）。
- ③ 重复 apply 返回 `[]`，且库的逻辑快照（表/索引/触发器/行数/注册表）不变。
- ④ 注入一条"先建表后引用不存在表"的迁移：抛错、**该迁移的部分表被整体回滚**、不写登记、移除注入后可正常重跑。
- ⑤ `0001` 四条散列：自算 `statement_digest` 与注册表一致；teaching 0001 与 B0 V00 证据 JSON 中记录的散列**逐字节相同**；正式库四库注册表只读对比**四条全部一致（0 漂移）**，且 `knowledge`/`teaching` 仍为 B0-only（待应用 0002/0003，属预期）。
- ⑥ 垃圾文件 → `DATABASE_UNREADABLE`；合法但缺表 → `DATABASE_SCHEMA_INCOMPLETE`；篡改注册散列 → `SCHEMA_MIGRATION_DRIFT`（verify 与 apply 两条路径都拒）。

反例（预先登记、非新缺陷）：`0003` 是裸 `ALTER TABLE`、无 `adjust` 钩子（见 O1/O2）。

## 2. V2 知识点 CRUD / 父树 —— **fail**（35/37）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v2_knowledge_points_probe.py`；退出码 **1**
证据：`V00-probes/evidence/v2_knowledge_points.json`（失败项 `v2.3f`、`v2.3h`）

通过的要点：创建 201/详情/列表分页与 `q`（命中别名）/`parentId` 过滤；改名 = 追加修订（version 2、revision +1、revisionId 变化）且历史修订 UPDATE/DELETE 均被 `IMMUTABLE_REVISION` 拒绝、历史行全部保留；过期 `expectedRevision` → 409 `REVISION_CONFLICT` + `details.currentRevision`；同 code → 409 `KNOWLEDGE_CODE_CONFLICT`；空白默认不修改、`clearFields` 才清空；跨学科父 → 422 `KNOWLEDGE_CROSS_SUBJECT_PARENT` + `issues[].field=parentId`；缺父（parentId/parentCode）→ 422 + 定位字段；归档后显式编辑允许、归档后作为新父 → 409 `KNOWLEDGE_ARCHIVED` + `issues[].field=parentCode`、归档后新增教材依据 → 409 `KNOWLEDGE_ARCHIVED`（服务级证据，用受控 evidence 替身）；恢复 200；跨点同别名 201 + warning（不合并）；同请求重复别名 422。

失败 2 项（同一根因，见 §11 F1）：**自指父**与**成环父**的错误没有契约要求的 `details.issues[].field`。

## 3. V3 表格导入与确认 —— **pass**（38/38）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v3_knowledge_imports_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v3_knowledge_imports.json`

- XLSX 上传 201 + 自动映射（编码/名称/描述/父级/别名）+ 未映射列 issue；别名按 `、` 拆分；批内父链成环逐行 `KNOWLEDGE_CYCLE`（`field=parentCode`）。
- 预览持久化：批次 `issues_json` 非空、行 issues 独立落列（SQL 直读核对）。
- 阻断（环行）→ 422 `KNOWLEDGE_IMPORT_BLOCKING_ISSUES` 且 `knowledge_points` 计数 0（零写入）。
- 确认成功：`created` 按批内拓扑序（父行 rowNo=2 先于子行 rowNo=1）、`ignored=[3]`、子点 `parentCode/parentId` 正确。
- 同 `submissionId` 重放 → `replayed=true`、结果与首次一致、计数不变；同 id 不同载荷 → 409 `SUBMISSION_CONFLICT`。
- update 行：既有 code 自动匹配目标并冻结 `baseRevision`/`baseVersion`；空白（`None` 单元格）不改 description；知识点级 `clearFields` 才清空。
- 过期 `expectedRevision` 的 update 行 → 409 `REVISION_CONFLICT` + `currentRevision`，**同批 create 行也没写**（整批回滚），批次仍 `reviewing` 可重试；修正动作后重试成功。
- 行缺决定 → 422 `KNOWLEDGE_ROW_INVALID` + 逐行定位 `[1,2]` 且零写入；已确认批次 → 409 `KNOWLEDGE_IMPORT_CONFIRMED`。
- CSV 上传 + 手工映射（`{"code":"甲","name":"乙"}`）重算行并清空批次 issues；映射不存在的列 422、未知字段 422；强行 create 既有 code → 422 `KNOWLEDGE_IMPORT_BLOCKING_ISSUES`（`KNOWLEDGE_CODE_CONFLICT`）。
- 批次列表形状 `{items,total,offset,limit}` + `rowCount`/`blockingIssueCount`；缺 subjectId 422；`.docx` 媒体类型 → 422 `UNSUPPORTED_DOCUMENT_FORMAT`。

## 4. V4 AI 候选 —— **pass**（23/23）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v4_knowledge_suggestions_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v4_knowledge_suggestions.json`（受控 `FakeProvider`，零网络）

- 正常路径：任务 `succeeded` + `candidateCount=1`；批次 `source="ai"`、`state="reviewing"`、行已落库；**`knowledge_points` 零新增**；模型原始输出登记为教学库 `file_assets`（§8.3 跨库逻辑引用）。
- 非法 JSON → `failed` + `KNOWLEDGE_SUGGESTION_INVALID_JSON`；未知引用 → `KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE`；截断（`finishReason=length`）→ `KNOWLEDGE_SUGGESTION_TRUNCATED`；配置失效（resolver 抛 404）→ `MODEL_PROFILE_NOT_FOUND`；四例业务表与资产**零新增**。
- 取消迟到（任务已建、模型已返回才发现取消）→ `cancelled`、不登记资产、不发布、零新增。
- publish 注入失败 → 批次/行**零残留**（succeeded 与候选写入同事务），原始输出资产登记保留（预先登记口径）；任务状态见 O4。
- 教材证据不可用 → 503 `TEXTBOOK_EVIDENCE_UNAVAILABLE` 且**不建任务**（`knowledge_jobs` 零新增）；无任何证据 → 422 `..._NO_EVIDENCE`；未装配 job_engine → 503 `SERVICE_UNAVAILABLE`。

## 5. V5 名单 —— **pass**（38/38）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v5_roster_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v5_roster.json`

- 建班 201；同学年同 code → 409 `CLASS_CODE_CONFLICT`；学号文本原样（`0012`/`0007` 前导零保留）。
- XLSX 文本学号 `"0012"` 保留前导零；数值学号 `12` → `"12"`（无 `12.0` 噪声）；空学号 → `None`。
- 建议分类实测：`1=link`、`2=create`（数值学号无匹配）、`3=conflict`（同名两人）、`4=create`、`5=name_mismatch`、`6/7=duplicate`；建议不构成 `decision`；同名冲突行带 `ROSTER_NAME_CONFLICT` + 行号。
- 未给决定 → 422 `ROSTER_IMPORT_BLOCKING_ISSUES`（阻断行 `[3,6,7]`，先于未决行报出）；消歧后仍有未决行 → 422 `ROSTER_IDENTITY_UNRESOLVED` 逐行 `[1,2,4,5]`；两种情形均零写入。
- `link` 缺 `studentId` → 422 `ROSTER_IDENTITY_UNRESOLVED` + `issues[].field=studentId/row=1`；`create` 带 `studentId` → 422 `INVALID_REQUEST` + `field=studentId/row=4`。
- 确认成功：`applied=[1..6]`、`ignored=[7]`、已建班学生复用归属（`createdStudent=false, createdMembership=false`）；新建 3 名学生；A 班活跃 6 人；**未出现的王五不动**（无新归属、字段不变）。
- 同 `submissionId` 重放 → `replayed=true`、结果一致、无重复写入；换 id 再确认 → 409 `ROSTER_IMPORT_CONFIRMED`。
- 转班 → 旧归属置 `leftOn`、新归属活跃（2 条历史），A 班活跃人数 6→5。
- 反例：同姓名同学号 `link+create` → **阻断且零写入**（实测 409 `STUDENT_NO_CONFLICT`，行可定位，见 O6）；同名（均无学号）`link+create` → 未阻断（见 O7）；同学号异名两行都 `create` → 409 `STUDENT_NO_CONFLICT` 零写入（见 O8）；重复学号两行都 create → 422 阻断零写入，一行 create 一行 ignore → 成功。
- CSV 名单上传 + 自动映射；归档班级导入 → 409 `CLASS_ARCHIVED`。

## 6. V6 富内容解析 —— **pass**（26/26）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v6_rich_parser_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v6_rich_parser.json`（自建样本，含 vMerge + gridSpan + 图片 + 行内/独立 OMML + `w:object` + `w:sdt` + 空段）

- 块顺序/类型/定位：`p1,p2,p3,t4,p5,p5-1,p6,p7,p7-1,p8,p9`；空段落不产生块；每块 `blockStart/blockEnd` 1 基。
- 表格：`columnCount=3` 一律填写；7 个单元格（覆盖单元格不重复）`[(表头跨两列,T,1,2),(表头C,T,1,1),(纵向起始\n纵向续接文本,F,2,1),(r2c2,1,1),(r2c3,1,1),(r3c2,1,1),(r3c3,1,1)]`；续接文本并入起始单元格不丢字；表头行 `isHeader=True`（首行 + `tblHeader`）；定位附 `tableColumns/tableRows`。
- 图片：`assetId=blobs/<sha256>`、尺寸 `96×96` px；`assets[].sha256` == 源 PNG 字节 sha256；`AssetStore.read` 读回字节一致。
- OMML：2 个公式块（行内 + 独立），`ommlXml` 与源 `word/document.xml` 中 `m:oMath` **逐字节一致**。
- 未知对象：段落内 `w:object` → issue 带 `blockStart`；body 级 `w:sdt` → issue 带 `bodyIndex`；源散列不符只 warning 不拒绝。
- 共同材料分组：`material-1 = [p1,p2,p3,t4]`，题号段与其余块全部留在 `unassigned`；重复调用结果一致；组装 `RichContentV2` 后材料内表格 `columnCount/rowSpan` 原样保留（按引用透传）；同块既题干又材料 → 422。

## 7. V7 富内容渲染 —— **pass**（18/18）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v7_rich_renderer_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v7_rich_renderer.json`

- 产物可被 python-docx 重新打开（学生/教师版各有 2 个表格 = 材料表 + 题干表）。
- 学生版**不含**答案与解析文本，也不含答案图片（media=1、无答案图字节）；教师版两者都有且答案在解析前（media=2、含答案图字节）。
- 共同材料文本只出现一次（学生/教师版各 1 次）。
- 图片关系重建：源图关系改名哨兵 `rId404` 后，产物 `rId9` 为新建关系、**哨兵不出现**、字节与源一致；源文件未被修改；尺寸按块字段还原（96 px → 914400 EMU）。
- OMML 节点存在（教师/学生各 2）；LaTeX-only 经 `math2docx` 转换（合法 `m:oMath`）；非法 LaTeX → 422 `FORMULA_CONVERSION_FAILED` + `details.fields=[blockId]`。
- 表格两条路径：`columnCount` 存在 → 3×3 网格且合并单元格文本不丢；**缺失**（旧数据）→ 启发式仍还原 3×3；矛盾 `columnCount=5` → 422 `INVALID_REQUEST`（不猜）；同块 id 重复 → 422；受管资产被篡改 → `ASSET_CORRUPT`。

## 8. V8 施测契约与未装配 —— **pass**（19/19）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v8_assessment_probe.py`；退出码 **0**
证据：`V00-probes/evidence/v8_assessment_contract.json`

- `POST/GET/PATCH/PUT/DELETE /api/v1/assessments` 全部 **501 `FEATURE_NOT_IMPLEMENTED`**（真实 HTTP，非 200/空对象）；路由表无 assessments 真实现；未知 `/api/v1/*` 同样 501；同 app 内知识点路由 201（对照）。
- `UnavailablePaperReader.read_confirmed_paper_revision` → 501 `PAPER_READER_UNAVAILABLE`；`ConfirmedPaperRevisionView` 字段与契约一致。
- `bootstrap_textbooks=False`（未装配）：knowledge/roster 的 GET/POST（合法载荷）全部 503 `SERVICE_UNAVAILABLE` 且无 `items` 字段；施测仍 501。
- 教学库无施测三表。

## 9. V9 文档声明抽查 —— **fail**（16/19）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v9_doc_claims_probe.py`；退出码 **1**
证据：`V00-probes/evidence/v9_doc_claims.json`（失败项 `v9.2b`、`v9.8`、`v9.17`）

机械核对通过的：API.md B1 节列出的 27 条公开路由经 HTTP 实测全部存在（非通配 501）；B1 路由模块 32 条路由除 4 条文档简写形式外都被文档覆盖；文档列出的错误码常量都存在；文档标注状态码与 V2/V3/V4/V5 实测一致；迁移 id（knowledge 0002+0003、teaching 0002）与任务卡一致；表名在 DDL 中存在；`REQUIRED_TABLES` 门控语义与代码一致；依赖 `openpyxl==3.1.5`/`math2docx==3.1.0` 在 `pyproject.toml` 与 `uv.lock` 一致；装配工厂签名与任务卡 §5 冻结签名一致；`JOB_KINDS["knowledge"] == {"suggestion"}`；上传上限 10 MiB；`document_parsing/parser.py` 不在候选清单且 tracked-clean（既有教材解析语义未动）。

失败 3 项：`POST /classes/{id}/restore` 未文档化（F4）；三份文档未提 `0003`（F2）；PROJECT_GUIDE §12 的"服务层可定位错误"声明与实现不符（F3，同 F1 根因）。

## 10. V10 断言有牙齿（变异实验 3 处）—— **pass**（10/10）

命令：`cd apps/api && uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v10_mutation_runner.py`；退出码 **0**
证据：`V00-probes/evidence/v10_mutations.json`

在系统临时目录里复制 `apps/api/app` 后变异（**候选工作区零改动**）：

| 变异 | 变异点 | 期望失败断言 | 结果 |
| --- | --- | --- | --- |
| M1 | 环检测触发器 `WHEN NEW.parent_id IS NOT NULL` → `WHEN 0` | `v2.3g 成环父 → 422 KNOWLEDGE_CYCLE` | 变异后该断言失败（200 放行），基线 pass |
| M2 | 渲染器 `if variant == "teacher":` → `or True` | `v7.1b 学生版不含答案与解析文本` | 变异后该断言失败，基线 pass |
| M3 | `REQUIRED_TABLES` 扩成含 `knowledge_points` | `v1.2c 仅 B0 结构旧库通过启动门控` | 变异后该断言失败（门控拒绝），基线 pass |

变异后 `v00_fingerprint.py` 复算仍 **95/95 一致**（副本变异未污染候选）。

## 11. fail 明细（最小复现 / 影响 / 首败证据）

### F1（V2，A5 / 契约 §2.2）自指父与成环父缺少可定位字段 `details.issues[].field`

- 复现（自指）：
  1. `POST /api/v1/knowledge-points` `{"subjectId":"math","code":"M-01","name":"有理数"}` → `id=A`
  2. `PATCH /api/v1/knowledge-points/A` `{"expectedRevision":0,"parentId":"A"}`
  - 期望：422 且 `details.issues[0].field ∈ {parentId, parentCode}`
  - 实测：`422 {"code":"KNOWLEDGE_PARENT_INVALID","message":"父节点非法：知识点不能把自己作为父节点。","retryable":false}`，**无 `details`**
- 复现（环）：`POST .../knowledge-points` `{"subjectId":"math","code":"M-02","name":"相反数","parentCode":"M-01"}` → `id=B`；再 `PATCH /knowledge-points/A` `{"expectedRevision":N,"parentId":"B"}`
  - 期望：422 `KNOWLEDGE_CYCLE` 且 `details.issues[].field=parentId`
  - 实测：`422 {"code":"KNOWLEDGE_CYCLE","message":"父节点变更会形成环（新父节点是本节点的后代）。"}`，**无 `details`**
- 影响：调用方/前端无法按契约从 `details.issues` 定位字段；只能靠错误码+文案。跨学科父、缺父、归档父三类都可定位，仅自指与成环缺失，属契约内部不一致。
- 首败证据：`evidence/v2_knowledge_points.json` → `v2.3f`、`v2.3h`；对照通过项 `v2.3a/b/c`。
- 代码位置（只读核对，未改动）：`app/services/knowledge/service.py:1221 _resolve_parent` 只覆盖"存在/同科/归档"，无自指与环分支；自指由 `app/repositories/knowledge/points.py:608 _require_parent` 抛无 `details` 的 `AppError`；环仅由 DB 触发器经 `points.py:94 translate_integrity_error` 翻译（无 `details`）；`points.py:580 would_create_cycle` 是**死代码**（全仓库无调用点）。
- 修复方向（供队长决策，不由我实施）：在 `_resolve_parent`/`update_point` 前调用 `would_create_cycle` 并抛 `ErrorIssue(field="parentId"|"parentCode")`；自指同理。若维持现状，则应改契约与 PROJECT_GUIDE §12 的措辞。

### F2（V9）三份文档未登记 `0003_knowledge_import_issues_column`

- 复现：`grep -n "0003" docs/API.md docs/PROJECT_GUIDE.md apps/api/AGENTS.md docs/CURRENT_STATUS.md`
  - 期望：知识库实际 3 条迁移（`0001/0002/0003`），文档结构表应覆盖
  - 实测：API.md B1 结构表、PROJECT_GUIDE §12、AGENTS.md 均只写 `0002`（`cardMentions0003=true`，仅 B1 任务卡 §3 与迁移文件自身登记了 0003）
- 影响：文档与实际注册迁移不一致（`applied_migrations` 三行）；读者无法从 API.md 得知 `knowledge_imports.issues_json` 来自追加迁移。
- 证据：`evidence/v9_doc_claims.json` → `v9.8`；迁移实证 `v1.1e`。

### F3（V9）`docs/PROJECT_GUIDE.md §12` "自指/环…在服务层给出可定位错误"与实现不符

- 实测：`would_create_cycle` 定义存在但**无调用点**；服务层只有跨学科/缺父/归档三类可定位 issue；环由触发器兜底且无 `details`。
- 影响：稳定决定文档的措辞高于实现（与 F1 同源）；后续批次可能据此误判"已有服务层环校验"。
- 证据：`evidence/v9_doc_claims.json` → `v9.17`。

### F4（V9）`POST /api/v1/classes/{id}/restore` 已注册但批次文档未列出

- 实测：路由模块 `app/api/v1/roster.py:153` 注册 `/classes/{class_id}/restore`；API.md B1 表与任务卡 §4 只列 `archive`。反向核对唯一"文档外路由"。
- 影响：公开接口面大于冻结清单（非假成功、行为与 knowledge 的 `/restore` 对称）；文档缺口。
- 证据：`evidence/v9_doc_claims.json` → `v9.2b`（`extra=[["POST","/api/v1/classes/{class_id}/restore"]]`）。

## 12. observation 列表

- **O1（V1）**：`0003_knowledge_import_issues_column` 是裸 `ALTER TABLE`、无 `adjust` 钩子（B0 为 `question_bank 0002` 建立的同类模式未复用）。若某库"列已存在但注册表缺 0003"（手工加列/部分恢复），`apply_migrations` 抛原始 `sqlite3.OperationalError: duplicate column name: issues_json`，**非 AppError**、每次启动重试都失败、无自愈。可达性低（正式库为 B0-only，不存在该状态）。证据 `v1.7b/v1.7c`。
- **O2（V1）**：列被手工删除、注册表仍登记 0003 时，apply 不重补（注册表驱动，符合"只追加"语义，但结构无自检）。证据 `v1.7d`。
- **O3（V1）**：正式库只读对比仅覆盖 `schema_migrations`（`mode=ro&immutable=1`，无锁无写）。四库 0001 散列一致、0 漂移；knowledge/teaching 待应用 0002/0003（下次启动会写正式库，需写入授权，CURRENT_STATUS 已登记）。
- **O4（V4）**：publish 抛错时任务停在 `running`（B0 引擎文档口径"异常向上抛"），不是 `failed`；同事务回滚与"非 succeeded"成立，收敛依赖租约过期/重启 reconcile。证据 `v4.7a2 state=running`。
- **O5（V4）**：候选原始输出资产在教学库先落盘（§8.3 预先登记），publish 失败后该 `file_assets` 登记保留（只增不改）——与风险登记一致。
- **O6（V5）**：同姓名同学号 `link+create` → 阻断零写入成立，但错误码是 **409 `STUDENT_NO_CONFLICT`**（`students` 的 `UNIQUE(owner_id,student_no)` 在写入时兜底），不是 422 `ROSTER_IMPORT_BLOCKING_ISSUES` 预检；`details.issues[].row=2` 可定位，批次保持 `reviewing` 可重试。证据 `v5.6a/b/c`。
- **O7（V5）**：同名（两行都无学号）`link+create` **未阻断**：成功把 1 行 link 到既有"张伟"、另 1 行新建同名学生（status 200，students 8→9）。消歧检查以 `("student", studentId)` 与 `("create", 学号+姓名)` 为身份键，无法识别"link 到既有张伟 + create 新张伟"。属口径边界，是否收紧需契约决定。证据 `v5.7a`。
- **O8（V5）**：同学号异名两行都 `create` 同样由 DB 唯一约束在写入时兜底（409 + 行定位 + 零写入）。证据 `v5.8a`。
- **O9（V8）**：未装配状态下 POST + 非法请求体先得 422（FastAPI 校验早于服务解析），合法请求体才是 503；非假成功，仅记录顺序。证据 `v8.7b`。
- **O10（V9）**：`KNOWLEDGE_SUBJECT_UNKNOWN`、`KNOWLEDGE_LINK_INVALID` 在契约中定义、API.md 列为错误码，但实现层从不抛出（学科按需 `ensure_subject`；链接不存在/不属于该点走 404 `KNOWLEDGE_LINK_NOT_FOUND`）。证据 `v9.5`。
- **O11（V3）**：`.txt` + `text/plain` 被 `read_table` 当 CSV 解析（`text/plain` 在声明的 CSV 媒体类型集合内）；`.docx` 才报 `UNSUPPORTED_DOCUMENT_FORMAT`。文档口径"只支持 .xlsx/.csv"与此一致但不精确。证据 `v3.8e`。
- **O12（V2）**：`RequestValidationError` 的 `details.fields` 形如 `["('aliases',)"]`（元组 repr）——`app/main.py` 该处理器在 HEAD 已存在，B0/B1 均未改（`git show HEAD:apps/api/app/main.py` 同码），**非本批引入**，仅记录。
- **O13（V5）**：`ux_active_membership` 只在 `(class_id, student_id)` 上部分唯一，不阻止同一学生跨班同时活跃——与任务卡 §8.1 预先登记一致（结构核对，非行为缺陷）。
- **O14（V5）**：名单批次级 `issues` 由行 issues 派生（只汇总阻断问题），不落库（`roster_imports` 无 `issues_json` 列）——与 §8.2 一致。证据 `V6/V5` 结构读取 + `v9` DDL 核对。
- **O15（V9）**：`KnowledgeSuggestionJobView` 只定义未使用（接口实际返回 `JobView`）——与 §8.3 一致；TS 镜像 `knowledge.ts` 也因此不含 `candidateCount`（与实际响应形状自洽）。
- **O16（V9/前端）**：`apps/web/src/contracts/textbook.ts` 另有一个同名 `JobView`（教材重建任务形状，与 B0 冻结的 `teaching-loop.ts` 版本不同）；该文件 tracked-clean、不在 B0/B1 候选内 → 历史遗留、不在本批范围，仅记录。
- **O17（V6/V7）**：本批"排版"仅结构级验证（python-docx 重开、网格行列、文本/节点存在、图片字节），真实 Word/WPS 呈现 not_run。

## 13. not_run 列表与原因

| 未执行项 | 原因 |
| --- | --- |
| 真实大模型调用（AI 候选全链路） | 本批无授权/无环境；V4 全部使用受控替身，探针零网络 |
| 真实 Word / WPS 打开与排版目视 | 本机无自动化环境（任务卡 §8.5 预先登记）；V6/V7 只给结构级证据 |
| 真实 Qdrant / embedding / Ollama | 本批不涉及检索；未启动任何外部服务 |
| 真实 DOCX/XLSX 业务文件（教师真实名单/教材） | 无授权；样本全部自建（openpyxl/docx 现造） |
| 正式数据根写入演练（0002/0003 补齐） | 只做 `schema_migrations` 只读对比；写正式库需用户写入授权 |
| 前端 UI 视觉验收 / e2e（Playwright）/ `test:chat` | 本批不新增页面、无路由与布局改动；e2e 需 build，属可选回归 |
| `npm run check` 全串（lint + unit 全量 + build） | 未执行：本批前端仅新增两个纯类型契约文件；已改跑 `npm run typecheck`（exit 0）与 2 个相关 vitest 文件（19 例 pass）作为替代证据 |
| B0 面（跨连接凭证隔离、.env/JSON 补偿、SSE 中途失败与取消、模型发现来源、专用认证过期、默认预算耗尽） | 不在本批 diff：`core/secrets.py`、`services/model_auth.py`、`services/model_runtime.py`、`api/v1/chat.py`、`providers/llm/base.py`、`core/rag_budget.py` 均 tracked-clean 且不在候选清单；本报告不对其复验（全量后端回归 1168 例通过作为不回归证据） |

## 14. 交叉核对：实现者测试与全量回归（不替代独立探针）

| 命令 | 结果 | 证据 |
| --- | --- | --- |
| `cd apps/api && uv run python -m pytest tests/{test_knowledge_points,test_knowledge_imports,test_knowledge_suggestions,test_roster_classes,test_roster_imports,test_rich_content_parser,test_rich_content_renderer,test_b1_migrations,test_contracts_b1,test_tabular,test_publication,test_migrations,test_startup_gates}.py -q` | **退出码 0**，进度点 176 个、无 F/E | `evidence/v00_b1_targeted_tests.txt` |
| `cd apps/api && uv run python -m pytest -q`（全量后端） | **退出码 0**，进度点 1168 个、**0 F / 0 E**；本轮未出现 R-19 | `evidence/v00_full_testapi.txt` |
| `npm run typecheck` | 退出码 0（`next typegen && tsc --noEmit`） | 终端输出 |
| `NODE_OPTIONS=--no-experimental-webstorage npx vitest run apps/web/src/services/api-client.test.ts apps/web/src/services/workflow-jobs-api.test.ts` | 2 文件 / 19 例 pass，退出码 0 | 终端输出 |
| 契约镜像抽查 | `knowledge.ts`/`roster.ts` 覆盖 22/24 个 Python 契约模型；未覆盖的 3 个是 archive/restore 请求体（TS 内联表达）与未使用的 `KnowledgeSuggestionJobView`；无重复类型定义（除 O16 的历史文件） | `evidence/v00_ts_mirror_check.txt` |

## 15. 我最不确定的一处

**V6/V7 的"结构级通过"能否代表真实打开效果。** 我用 python-docx 重开产物、断言网格行列/合并单元格文本/图片字节与 `m:oMath` 节点，能证明 XML 结构自洽且自建样本的 OMML 与源逐字节一致；但纵向合并（`vMerge`）与横向合并（`gridSpan`）在 Word/WPS 中的实际版面、图片缩放表现、以及"表格首行不重复标题"等排版语义，本机无法验证（O17）。若后续有真实 Word 环境，建议优先复验这一处（V6/V7 的结论应被视为"结构成立、排版未验证"）。

---

## 附：结论速览

| 项 | 结论 | 关键依据 |
| --- | --- | --- |
| V1 迁移与门控 | pass | 36/36；新库/旧库/幂等/回滚/0001 四散列（正式库 0 漂移）/损坏拒绝 |
| V2 知识点 | **fail** | 35/37；自指父与成环父无 `details.issues[].field`（F1） |
| V3 导入确认 | pass | 38/38；零写入/重放/整批回滚/空白 vs clearFields |
| V4 AI 候选 | pass | 23/23；五类失败/取消迟到/同事务/教材证据 503 不建任务 |
| V5 名单 | pass | 38/38；前导零/建议分类/422 定位/零写入/重放/转班保留；O6–O8 口径记录 |
| V6 解析 | pass | 26/26；vMerge/gridSpan/图片字节/OMML 逐字节/未知对象定位/材料分组 |
| V7 渲染 | pass | 18/18；学生版无答案与解析、材料一次、rId 新建、OMML、LaTeX 两条路径 |
| V8 施测契约 | pass | 19/19；真 HTTP 501、`UnavailablePaperReader` 501、未装配 503、无施测三表 |
| V9 文档声明 | **fail** | 16/19；F2（0003 未登记）/F3（§12 可定位措辞）/F4（`/classes/{id}/restore` 未文档化） |
| V10 断言有牙齿 | pass | 10/10；3 处变异均使对应断言失败，候选 95/95 未污染 |
