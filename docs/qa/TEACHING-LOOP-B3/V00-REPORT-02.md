# V00 · TEACHING-LOOP B3 窄复验报告（02 · r2）

- 任务：对 r2 窄改（`ScoreImportPatchRequest` 并入冻结契约）做窄复验
- 候选：`FROZEN-B3-r2.json`（**163 文件**）；定版 `FROZEN-B3.json`（files 与 r2 逐字节相同，`revision` 字段仍为 `B3-final` / r2 为 `B3-r2`）
- 只读边界：未改 `apps/**`、契约、迁移、测试、权威文档；本轮新增仅本报告与 `V00-probes/**`（探针更新见 §2）
- 方法：独立复算指纹与差异、独立重跑契约镜像探针、独立重跑 typecheck/eslint/vitest；不采信结果卡数字代替复算

## 1. 改动面核对

**清单差异（独立复算，`p32_fingerprint_r2.py`）**：r1（163）→ r2（163）**新增 0 / 删除 0 / 变更恰 2 个文件**：

- `apps/web/src/contracts/scores.ts`
- `apps/web/src/services/assessments-api.ts`

与 CTRL 声明一致；其余 161 文件在 r1/r2 清单中逐字节相同。两文件内部改动面（读数）：

- `contracts/scores.ts:127-131` 新增 `ScoreImportPatchRequest { expectedRevision: number; mapping?: ScoreColumnMapping | null; rows?: ScoreImportRowPatch[] }`；与后端 `app/contracts/scores.py` 逐字段一致（p26 全字段比对）。
- `services/assessments-api.ts`：文件头第 11-13 行注明"已由 CTRL 并入冻结契约 `@/contracts/scores`（B3 r2），本模块只再导出，不再持有第二份形状"；从 `@/contracts/scores` 导入该类型（import 块第 38 行）并在第 285 行 `export type { ScoreImportPatchRequest } from '@/contracts/scores';` 再导出；`patchScoreImport` 函数体不变（第 288-297 行）。**无第二份本地形状**（TS 解析确认文件内不存在同名 interface）。
- 调用方兼容：`features/assessments/hooks.ts:26` 仍从 `@/services/assessments-api` 引类型（再导出路径未断）、第 389 行只构造数组使用 `['rows']`；无 null 使用点。

> 局限（如实）：r1 的源码字节未留存（清单只有散列，文件未入库），因此无法做 r1→r2 的逐行 diff；改动面核对以"清单恰 2 文件 + 两文件结构读数 + 全镜像字段比对 + 调用方/类型检查"为依据。

## 2. 复验项结论

| 复验项 | 结论 | 证据 |
| --- | --- | --- |
| 1. 指纹：r2 163/163 + r1→r2 差异恰 2 文件 | **fail（文档登记过期，非产品）**：磁盘 **161/163**；两个不一致文件恰为 `docs/qa/TEACHING-LOOP-B3/{EVIDENCE-COMMANDS.md,REPORT.md}`；除这 2 个文档外的 161 个文件全部一致（160 个产品/工程文件 + `TASK-CARD.md`，含 2 个 r2 改动文件）；r1→r2 差异恰为上述 2 个产品文件 | `p32_fingerprint_r2.py`（exit 1）、`p32_fingerprint_r2.json` |
| 2. p26 契约镜像（r2 口径） | **pass**：`ScoreImportPatchRequest` 差项消失，模型集合两侧完全一致（26↔26）；496 checks / 0 failures；残差仅剩 r1 已登记的 4 条 optionality 偏差（itemColumns + AssessmentView×3，方向均为 TS 更严格）；r1 的 `rows: … | null` 偏差随 r2 一并消失 | `p26_contract_mirror.py`（已更新为 r2 口径）exit 0，`p26_contract_mirror.json`、`p26_r2.run.log` |
| 3. 行为抽查 | **pass**：`npm run typecheck` exit 0；`npx eslint <两文件> --max-warnings=0` exit 0（无输出）；`NODE_OPTIONS=--no-experimental-webstorage npx vitest run apps/web/src/features/assessments apps/web/src/services/assessments-api.test.ts` → **3 files / 46 tests passed**、exit 0 | `p33_typecheck.log`、`p34_eslint.log`、`p35_vitest.log` |
| 4. 其余项 | 未重跑（见 §3"未重验及理由"） | — |

**指纹 mismatch 最小复现**（请 CTRL 处置）：

```
cd H:\备份xuexi\智启课源
apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p32_fingerprint_r2.py
# exit 1
# 输出：disk 161/163 stale=['docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md',
#                           'docs/qa/TEACHING-LOOP-B3/REPORT.md'] verdict=stale_docs_only
```

- 期望：163/163；实际：161/163。
- 原因（有时间戳证据）：`FROZEN-B3-r2.json`/`FROZEN-B3.json` 写入 22:28:35.99 / 22:28:36.24，两个文档写入 **22:28:46.68 / 22:28:46.70**（晚约 10 秒）；两层清单中这两个文档的散列相同（r1=r2，即均取自改写前字节），当前磁盘为新字节：
  - `EVIDENCE-COMMANDS.md`：清单 `187807c304fb…`，磁盘 `2f9abea89ab3…`；
  - `REPORT.md`：清单 `e44cb5e71cb5…`，磁盘 `2e95eef85e77…`。
- 影响面：仅文档登记散列；不影响产品候选（161 个非该目录文件全部一致，其中含 2 个 r2 改动文件）。**修复 = CTRL 重算这两个文档的散列后重新冻结（或把该目录排除出哈希清单）**；本报告按事实记 fail，不代改冻结件。
- 附带口径提示：`FROZEN-B3.json` 的 `revision` 字段为 `B3-final`，而 `FROZEN-B3-r2.json` 为 `B3-r2`，两者 `files` 完全相同——定版文件内容即 r2，仅标签不同（观察项）。

## 3. 新观察项

1. **冻结与文档写入的时序竞态**（上表 fail 的直接原因）：r2 冻结清单生成后 10 秒，CTRL 又改写了同属清单的两个文档；建议冻结脚本把"生成清单"与"最后写入文档"排序固定，或冻结后立即复算一次自检。
2. **定版标签不一致**（非功能性）：`FROZEN-B3.json` revision 仍为 `B3-final`，其余内容等于 r2；建议下次冻结统一标签，避免"定版 = 哪个 r"的歧义。
3. **r2 的 `rows` 可空性收紧是行为等价向的类型修正**：旧本地类型 `rows?: ScoreImportRowPatch[] | null` → 契约 `rows?: ScoreImportRowPatch[]`；唯一使用点 `hooks.ts:389` 始终构造数组，未使用 null，故无运行时差异（typecheck/46 例亦通过）。
4. **未重验及理由**（按任务"其余项不必重跑"）：本轮两处改动均为 **TypeScript 类型层**（interface 定义与 `import`/`export type`），编译后无运行时代码；`patchScoreImport` 函数体未变、后端/迁移/契约（Python）零改动。类型层风险由 typecheck（覆盖全 web 工程引用）+ eslint + 46 例定向单测覆盖；再跑 build/e2e/后端全量对本次改动不增加判别力。如需发布前复跑 `npm run check`/全量 e2e，属 CTRL 的终验口径，本报告未执行。
5. **验证命令的写入面**：typecheck 的 `next typegen` 会再生成 `apps/web/.next/types`、vitest 会写缓存，均为构建产物（不在冻结清单）；全部命令跑完后复算 `p32` 仍为 161/163、唯一 stale 仍是那 2 个文档 → 候选未被验证动作污染。

## 4. 一行结论

**产品候选（含 r2 两处类型层改动）通过窄复验、可交付**；但**冻结清单当前不自洽**：`FROZEN-B3.json`/`FROZEN-B3-r2.json` 需先重算 `docs/qa/TEACHING-LOOP-B3/{EVIDENCE-COMMANDS.md,REPORT.md}` 两个散列并重新冻结（修复后本报告的 163/163 指纹结论即可成立），其余无新增阻塞项。
