# TEACHING-LOOP B2 · V00 独立验收报告 02（r2 窄复验）

- 批次：**TEACHING-LOOP B2**；候选：**r2**（`FROZEN-CANDIDATE.json`，84 文件，revision `r2`；
  r1 记录保留为 `FROZEN-CANDIDATE-r1.json`，83 文件）
- 起点：`main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906`；验收者：V00（只读，自建探针与证据）
- 日期：2026-10-01；前序报告：`V00-REPORT-01.md`（r1）
- 本轮边界：未改任何候选文件（含 `apps/api/AGENTS.md`）、未改实现者测试与现行文档；只新增
  `V00-probes/**` 与 `V00-REPORT-02.md`；不联网、不占 8000/8001/5174、不读写正式 `.local-data`。

---

## 0. 结论摘要

| 复验项 | 结论 | 一句话 |
| --- | --- | --- |
| r2 指纹对账 | **pass** | 84/84 文件 sha256 一致（0 缺失、0 不一致）；无 `postVerificationDocChanges` |
| r1↔r2 差异核对 | **pass** | 实测差异 = **新增 1（`apps/api/AGENTS.md`）+ 修改 3（`docs/API.md`、`docs/CURRENT_STATUS.md`、`docs/qa/TEACHING-LOOP-B2/TASK-CARD.md`）+ 删除 0**，与记录 `changedSincePrevious` 及 CTRL 声明**不多不少**；80 个未变文件与 r1 逐字节一致 |
| V9 复跑（r1 唯一 fail） | **pass** | `18/18`（0 fail）：两个 fail 项转 pass，`AGENTS.md` B2 声明项也转正；退出码 0 |
| 关键三项重跑 | **pass** | V3 `44/44`、V6 `14/14`、V7 `33/33`，退出码 0，与 r1 同数同结论 |
| 附加重跑 | **pass** | V8 前端 `9/9`、V10 变异 `11/11`（含 84 文件哈希二次复算、工作区零越界） |
| r2 文档订正事实核对 | **pass** | 18 行记录（17 pass + 1 observation）/ 0 fail：文档 ↔ 代码/实测三方一致 |
| r1 遗留 fail | **无** | r1 的 2 处 fail 已在 r2 修复并被本轮复验覆盖；未发现新的 fail |

**r2 未引入任何产品回归；r1 结论在未变文件上按"同一身份"复用（并有逐字节证明），在重跑项上原样成立。**

---

## 1. r2 指纹对账与差异核对（报告开头项）

**命令**（仓库根）：

```
python "docs\qa\TEACHING-LOOP-B2\V00-probes\r2_fingerprint_diff_probe.py" \
  --evidence "docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\r2_fingerprint_diff_probe.json"
```

- **退出码：0**；`10/10 passed`（证据：`H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\r2_fingerprint_diff_probe.json`）
- 关键输出摘录：
  - `r2.0` 记录头：`revision=r2 / fileCount=84 / base=0f4b8cb190c2… / postVerificationDocChanges=None`；
  - `r2.1` r1 保留件存在且 `fileCount=83`（revision=r1）；
  - `r2.2` **84 文件 sha256 复算 100% 一致**：`files=84 missing=[] mismatch=[]`；
  - `r2.3` 实测差异集合：`added=['apps/api/AGENTS.md'] removed=[] modified=['docs/API.md','docs/CURRENT_STATUS.md','docs/qa/TEACHING-LOOP-B2/TASK-CARD.md']`
    → **不多不少**（既没有未声明的第 4 个修改，也没有漏报）；
  - `r2.4` 实测「修改」集合 == r2 记录 `changedSincePrevious`（逐项相同）；
  - `r2.5` 文件数 83→84 恰为 +1；
  - `r2.6` **80 个未变文件在磁盘上与 r1 逐字节一致**（`drift=[]`）→ r1 在这些文件上的结论可直接复用；
  - `r2.7` 我 r1 期保存的 `baseline-hashes.json`（83 条）== r1 记录（`diff=[]`）→ r1 取证链未断；
  - `r2.8` **产品/测试/脚本零变化**：`apps/**` 仅新增 AGENTS.md，`tests/**`、`scripts/**` 无任何变化；
  - `r2.9` 迁移（teaching/question_bank）、契约（papers/assessments）、`schemas/question_bank.py`、`main.py`、
    CTRL 的 `test_b2_migrations.py`/`test_b2_contracts.py` 共 8 个关键文件**逐字节未变**。

### 1.1 候选构成（r2）

| 类别 | 文件数 | 相对 r1 |
| --- | --- | --- |
| `apps/api/app/**`（后端产品代码） | 24 | 未变 |
| `apps/api/tests/**`（实现者测试） | 14 | 未变 |
| `apps/web/src/**`（前端产品代码） | 38 | 未变 |
| `docs/**`（现行文档） | 6 | 其中 3 个修改 |
| `tests/e2e/**` | 1 | 未变 |
| `apps/api/AGENTS.md`（新增） | 1 | **新增** |
| 合计 | **84** | +1 |

### 1.2 写入停止核对

- 本报告的所有断言均针对 §1 复算一致的 84 个文件；验证期间未观察到候选文件变化（结束前二次复算仍 84/84，
  见 §6 的 `r2_v10_mutations_probe.json`）。
- 我的新增仅：`V00-probes/r2_fingerprint_diff_probe.py`、`V00-probes/r2_docs_delta_probe.py`、
  对应 evidence 与 `r2-v8-vitest-independent.log`、`V00-REPORT-02.md`；工作区允许清单核查
  `offenders=[]`（`r2_v10_mutations_probe.json` 的 V10.D2）。

---

## 2. V9 复跑（r1 唯一 fail 的收口）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v9_docs_declarations_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\r2_v9_docs_declarations_probe.json"
```

- **退出码：0**；`18/18 passed`（0 fail；证据：`…\V00-probes\evidence\r2_v9_docs_declarations_probe.json`）
- 变化点（相对 r1 的 19 行 = 17 pass + 2 fail + 1 observation）：
  - `V9.9` 由 fail → **pass**：`doc_only=[]`（`docs/API.md` 的 `GENERATION_*` 码名已能逐一对上代码常量）；
  - `V9.10` 由 fail → **pass**：`doc_409=False actual_status=422 actual_code=CLASS_ARCHIVED`
    （文档不再把它标为 409，实测/代码为 422，两侧一致）；
  - `V9.15` 由"观察项" → **真正的 pass**：`apps/api/AGENTS.md` 现含 B2 结构声明，故 r1 的
    `OBS-AGENTS.md 未同步 B2` 已关闭（本轮不再产生该 observation 行，行数 19→18）。
- 其余 15 项（路由双向、迁移 id、触发器家族 ×20、分期 CHECK、`paper_confirm` 无 `PRACTICE_NOT_REVIEWED`、
  六态 + attempt、`RECONCILE_DOMAINS` 含 question、ROUTES/导航一致性、租约 90s、§13 六条稳定决定、
  任务卡关键事实）保持 r1 的 pass。

---

## 3. 关键三项重跑（确认 r2 与 r1 结论一致）

三项都在 r2 上原样重跑（同一探针、同一断言、互不共享状态），退出码与例数：

| 项 | 命令（`cd apps/api`，均带 `--evidence …\evidence\r2_*.json`） | 退出码 | 结果 |
| --- | --- | --- | --- |
| **V3 确认与不可变** | `uv run python …\V00-probes\v3_papers_confirm_probe.py` | **0** | `44/44 passed` |
| **V6 统一任务收敛/取消** | `uv run python …\V00-probes\v6_question_job_engine_probe.py` | **0** | `14/14 passed` |
| **V7 施测真链路** | `uv run python …\V00-probes\v7_assessments_probe.py` | **0** | `33/33 passed` |

证据：`…\V00-probes\evidence\r2_v3_papers_confirm_probe.json`、`r2_v6_question_job_engine_probe.json`、
`r2_v7_assessments_probe.json`。

关键断言在 r2 上的实测（摘录）：

- **V3**：闸门 6 类拒绝后仍为 draft；确认成功（1500 单位 / 3 个计分叶）；同 `submissionId` 重放
  `replayed=True`；绕过服务直写 **16 条全部被 `IMMUTABLE_REVISION` 拒绝**，旧修订快照 digest 不变；
  改已确认卷 → 新 `version=2` 草稿、旧修订仍 `confirmed`；旧施测仍指旧修订。
- **V6**：`organize` `attempt=1/2`、冻结输入 `contractVersion=2` + 指纹；model 名额轨迹
  `start/end` 严格串行（`max_concurrent=1`）；`queued` 立即 cancelled 且零调用；`running` 取消后
  **零建议落库**；造 `running` → `reconcile` → `interrupted`（不重叫模型）→ 显式 recover → `succeeded(attempt=2)`；
  旧 checkpoint → `ORGANIZER_MODEL_RESELECT_REQUIRED` 且 provider 零调用。
- **V7**：CSV 名单导入 → 建档/归属 → T40 原卷确认 → 施测 201（2 人，快照=服务端真值）；
  同 `submissionId` 重放 `replayed=True`；10 项闸门错误码/定位一致；转班后归属未覆盖 → 422
  `PARTICIPANT_CLASS_UNCONFIRMED(row=0)` → 带依据成功且 `class_memberships` 逐行未变；
  人次冲突 409、补考新增 attempt 2 且首次记录逐字节不变、批量回滚；改名后快照不变；PATCH `revision+1`、过期 409。

### 3.1 附加重跑（低成本、直接覆盖 r2 声明的两条硬约束）

| 项 | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| V8 前端组件（教材依据区分 / 六态 / 取消重试 / 卸载停轮询） | `NODE_OPTIONS=--no-experimental-webstorage npx vitest run --config docs/qa/TEACHING-LOOP-B2/V00-probes/frontend/vitest.v00.config.ts` | **0** | `9/9 passed`（日志 `…\evidence\r2-v8-vitest-independent.log`） |
| V10 变异实验 + 候选完整性 | `uv run python …\V00-probes\v10_mutations_probe.py` | **0** | `11/11 passed`（`…\evidence\r2_v10_mutations_probe.json`）；3 处变异仍被抓到；`V10.D1 files=84 mismatch=[]`；`V10.D2 entries=83 offenders=[]` |

### 3.2 未重跑的项（V1/V2/V4/V5）与复用依据

V1、V2、V4、V5 的**全部被测文件**（迁移、契约、服务、路由、CTRL 测试）都在 §1 的"80 个未变文件"内，
且 `r2.9` 对迁移/契约/main 等 8 个关键文件做了逐字节确认；因此这四项按**同一候选身份**直接复用 r1 结论
（`87/87`、`59/59`、`32/32`、`32/32`，退出码均为 0）。**这是文档化的复用，不是重跑**；如需在 r2 上原样重跑，
命令与 r1 报告 §2–§6 相同（仅 `--evidence` 换名）。

---

## 4. r2 文档订正的事实核对（文档 ↔ 代码/实测）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\r2_docs_delta_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\r2_docs_delta_probe.json"
```

- **退出码：0**；记录 `18` 行（**17 pass + 1 observation**，0 fail；证据：`…\evidence\r2_docs_delta_probe.json`）
- 核对结果：
  - `r2.A1/A2/A3`：`docs/API.md` 声明的 5 个生成错误码（`GENERATION_INVALID_JSON` / `_OUTPUT_TRUNCATED` /
    `_UNKNOWN_KNOWLEDGE` / `_UNKNOWN_EVIDENCE` / `_FORBIDDEN_REFERENCE`）在 `generation.py` 中**都有同名常量**；
    r1 的三个旧名（`GENERATION_INVALID_EVIDENCE`/`_UNSAFE_REFERENCE`/`_TRUNCATED`）已从 `docs/API.md` 全篇消失；
    与我在 V5.1–V5.8 的真 HTTP 实测码一致。
  - `r2.A4/A5`：施测域 `CLASS_ARCHIVED` 已写为 **422（并注明名单域为 409）**，409 组不再含它；
    两侧代码状态码实测一致：`roster/service.py` = 409、`assessments/service.py` = 422，
    契约 `contracts/assessments.py` 保留 `CLASS_ARCHIVED` 常量。
  - `r2.B1/B2`：`docs/CURRENT_STATUS.md` 记录的 V00 r1 例数 `87/59/44/32/32/14/33/9/11` 与"指纹 83/83 一致"
    **由我从 r1 证据 JSON 独立复算得到同一串数字**（不是照抄文档）；`V9 fail（2 处文档事实错误…）——已订正 docs/API.md`
    的口径与 r1 报告一致。
  - `r2.B4/B5`：not_run（真实模型 / 真实 Word-WPS 排版 / 真实 Qdrant / 正式数据根迁移演练）与 B3 入口
    （T60 成绩、F20、F10、`source_practice_revision_id` 外键补齐）齐备；observation 的措辞为"已登记"，
    未被我方要求的"不得写成产品缺陷"口径违反。
  - `r2.C1/C2/C3`：`apps/api/AGENTS.md` 的 B2 迁移 id 与注册表一致（`0003`/`0004`/`question_knowledge_links`）；
    共享依赖说明与装配签名一致（`build_question_bank_service` 形参含 `knowledge_catalog/coordinator/job_engine`，
    `RECONCILE_DOMAINS=('knowledge','teaching','question')`）；"启动不自动重叫模型"与 V6 实测一致。
  - `r2.D1/D2/D3`：`TASK-CARD.md §11` 新增第 8/9 条，登记 r1 的三项 observation
    （发布失败停 `running`、错误码以 `generation.py` 为准、`KnowledgePointView.id` 口径），标注"建议 B3 统一到引擎级"，
    并保留既有边界（正式关联无 `source` 列、`ASSESSMENT_REVISION_STALE` 专用码、`ParticipantMutationResult` 只返回新增）；
    未把 observation 写成"已修复"。
- `r2.B6`：批次 `README.md` §6.1–6.3 逐项复述 r1 结论（含三个旧码名与 `CLASS_ARCHIVED`）与 7 条 observation 的处置表，
  r1 报告可经 §6.1 到达（该文件**不在候选清单**内，属批次证据，见 §5 OBS-r2-2）。

---

## 5. observation（本轮）

1. **OBS-r2-1（traceability 小项）**：`docs/CURRENT_STATUS.md` 的 V00 r1 段落**未深链 `V00-REPORT-01`**
   （只深链 `V00-REPORT-02` 与 `TASK-CARD`）。结论文字与例数都在状态页，且批次 `README.md §6.1` 已链接 r1 报告，
   故可追溯性不受影响，**不判 fail**。建议（可选）在状态页补一处 r1 报告链接。
2. **OBS-r2-2（非候选批次证据在 r2 冻结后仍有更新）**：`docs/qa/TEACHING-LOOP-B2/README.md`（mtime 15:44:19）与
   `EVIDENCE-COMMANDS.md`（15:03）在 r2 冻结（15:43:44）之后/期间被更新；两者**从未进入 r1/r2 候选清单**，
   因此既不参与 84/84 对账，也不与"零产品/测试/脚本变化"冲突——登记为事实说明，供 CTRL 判断是否要把批次
   README 纳入后续冻结口径。
3. **OBS-r2-3（r1 OBS-1 仍成立）**：原卷域"发布失败后任务停在 `running`"未在 r2 改变（r2 未触碰 papers 服务），
   已在 `TASK-CARD §11.8` 登记为 B3 统一处置；我的 V4 探针仍能复现该边界（业务零残留、
   `PAPER_PROPOSAL_STALE(409)` 真实抛出、状态停 running）。
4. **OBS-r2-4（r1 OBS-4/5 仍成立且已登记）**：`KnowledgePointView.id`（非 `pointId`）口径与"草稿内容/关联一变即回
   `needs_review`"两条仍在；前者已入 `TASK-CARD §11.8`，后者是任务卡 §6.1 的明示语义（我的 V5 按此正向复现）。
5. **OBS-r2-5（r1 OBS-6/7 复核）**：本轮验证窗口内 `H:\备份xuexi\智启课源\.local-data` 仍无新写入
   （见 §7）；台账 R-14/R-15/R-18/R-19 未复现、未"修"、未放宽，按 `CURRENT_STATUS` 口径记录。

## 6. not_run（同 r1，未因 r2 改变）

真实模型调用（AI 建议 / AI 补题 / 知识点候选 / 整理，全为受控替身）、真实 Word/WPS 排版检查、
真实 Qdrant / 教材检索链路、正式数据根迁移演练、全量 `npm run test:api` / `check` / `build` / `test:e2e`
（CTRL 组织；只读引用 `_work/b2/e2e-b2-r3.log` 的 147 passed）、实现者测试复跑、
真实浏览器**人工**视觉复核（390 视口与 reduced-motion 由 CTRL E2E 断言覆盖）、2000 人压力与真实网络抖动。
另：**V1/V2/V4/V5 未在 r2 重跑**（依据 §3.2 的逐字节同身份复用，已明确标注为复用而非重跑）。

## 7. 资源释放与边界

- 无本批启动的常驻进程/端口：8000/8001/5174/6333 无监听；无 `uvicorn`/`python` 残留；宿主工具的三个
  `node.exe`（创建于 14:53:58）非我启动。
- 验证窗口内正式数据根零写入：`find .local-data -newermt "2026-10-01 15:00"` 为空（与 r1 结论一致）。
- 探针临时数据全在系统临时目录（`zqky-v00b2-*`）；未改候选文件、未提交、未推送、未改 `.env`。
- 本轮新增产物：`…\V00-probes\r2_fingerprint_diff_probe.py`、`…\V00-probes\r2_docs_delta_probe.py`、
  `…\V00-probes\evidence\r2_*.json`（6 个）、`…\evidence\r2-v8-vitest-independent.log`、本报告
  `H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-REPORT-02.md`。

## 8. 我最不确定的一处

**"V1/V2/V4/V5 按同一身份复用 r1 结论"的可接受度**。证据侧很硬：这四项的被测文件在 r2 中逐字节未变
（80 个未变文件 + 8 个关键文件单独确认）；但哈希只能排除"代码被改"，排除不了**环境/时序类间歇**
（例如 V4 里我刻意制造的"发布期冻结失败"依赖 asyncio 门控时序、V2 的 DOCX 解析与 SQLite 锁竞争、
以及本机 tmp 目录读写负载）。也就是说：**若这四项在 r2 上重跑，理论上仍可能出现与 r1 不同的偶发结果**，
而本轮没有数据点。我选择复用是因为 r2 的产品字节与 r1 完全相同、且我已在 r2 重跑了覆盖面最广的三项
（确认不可变 / 统一任务 / 施测真链路，含触发器、任务引擎与跨库只读链路）；如总控需要"零复用"的完整覆盖，
按 r1 报告 §2–§6 的同一命令在 r2 上原样重跑四项即可（预计 3–4 分钟），结论需以重跑为准。
