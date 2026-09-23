# CHAT-CONTEXT-BUDGET v1 独立验收报告 r2（A1，只读复验）

> 归档说明（队长）：本文件保存 A1（`Independent-Acceptor`，只读）对 r2 候选的复验（并含其对 RAG-I0 候选的未回退确认）；文末「总控处置」为队长记录，不改写 A1 的原始结论与数字。A1 证据在仓库外（`%TEMP%\a1-verif-r2-20260923\`）。

## 0. 候选与写入停止

- r2 候选：`3303f7f78c54a1cc18fdbba775829605506eb0bd`（tree `c6350d8728c6c3bede8d0ff10e89a368dcb21652`），构建 `jWdzmxYFOf6RtLUVbtOkL`；其后 `c0a7641` 仅改 FROZEN JSON（核对通过）。
- 源码面等价核对：`git diff 3303f7f HEAD -- apps tests` = 空。
- 会话首末 HEAD 均为 `c0a7641`；`git status` 无 tracked 改动；实现者停止写入确认。

## 1. r1 六条处置的逐条结论（A1 自建探针）

| # | 验收内容 | 结果 | 判定 |
| --- | --- | --- | --- |
| 1 | `courseContext.resources=[null]` + `retry()` 不抛错、正常发送或可读提示、不伪造、免责句在 | `threw=null`、`requests=1`、`sending=false`、`unhandledRejections=0`；system 126 字含免责句，**不含 `null`/`undefined`**、无编造资源行（渲染为「无登记资源」）；`recordTotalChars=129 = Σ实际`；`[null]`/`['broken',42,true]`/`resources=undefined` 等均被丢弃 | **pass** |
| 1b | 缺失字段 unknown 兜底 | `[{label:null,kind:null,availability:null}]` → `（unknown·unknown）`，无 null/undefined | **pass** |
| 2 | FROZEN 全 SHA | 两份 FROZEN 的 `candidateFullSha` 与 `git rev-parse` 一致 | **pass** |
| 3 | STATUS 日期 | 已为 2026-09-23 | **pass** |
| 4 | 矩阵标签不早于验收 | 现为「实现待验收（…待 r2 复验…）」 | **pass**（A1 要求本轮判可交付后改为「已验收」） |
| 5 | FROZEN-2 性能边界来源 | 与上游 `EVAL.md`/`STATUS.md` 记录一致，措辞如实（非本批实测） | **pass** |
| 6 | `course-session.ts` 本批未改 | `git diff 9fcab13 3303f7f -- …/course-session.ts` 为空；`a9968cd→3303f7f` 仅 `request-budget.ts` + 其测试 | **pass** |

## 2. 未回退核对

- 自建探针 **39/39 通过**：`r2-invariants` 28（不变量 1/2/3/4/5/6/7/8 + §4 上限）、`r2-legacy` 2、`r2-regression` 5、`r2-corrupt-retry` 1、`r2-corrupt-matrix` 1、`r2-sse-failure` 2（SSE 中途失败 → error 终态 + 可重试；带正文与脏快照的失败轮重试不抛错、旧轮 superseded）。
- 探针反转：原探针与副本均 **2/2 按预期失败**（D1 208 字；D2 1990≤2000）；副本 md5 `18122b3c1953eb3ef2ca53dfe92d7ccc` 与 `_work` 原件逐字节一致；产品路径反转探针 **3/3 通过**。
- 回归：定向 e2e 15/15 全绿。

## 3. 独立复跑（A1 本机）

| 项 | 声称 | 实测 |
| --- | --- | --- |
| lint | 0 警告 | exit 0 |
| unit | 52/435 | **52 文件 / 435 例** |
| api | 217 | **217 passed**（RAG 契约 35 例含内） |
| 定向 e2e | 15/15 | **15 passed（18.1s）** |
| 全量 e2e | 195/0/0 | **#1 194/1（9.0m）；#2 195/0（6.4m）** |
| 构建 | 不重跑 | `jWdzmxYFOf6RtLUVbtOkL` 前后一致；`.next` 0 新文件；指纹 8/8 一致 |

## 4. A1 本轮新发现（原文摘要）

1. **F1（中，跨批）**：全量 e2e 汇总数字不能稳定重现——`books-commit-safety.spec.ts:238`「双标签页并发写不同书」在 `--repeat-each=3` 下 **1 passed / 2 failed**（失败形态为等待 `.book-pipeline-strip` 消失超时，130.7/137.7s vs 通过 20.6s）。本批 diff 面无书籍代码、无 import 耦合，非本批引入；建议按既有 flaky 流程处置。
2. **F2（低，文档）**：r2 FROZEN 的 `checks.build` 仍写 r1 构建号。
3. **F3（低，注释与行为不符）**：`request-budget.ts:123` 注释称非对象条目「计入『等共 N 项』总数」，实测只计存活项 → 建议改注释。
4. **F4（低，同 r1 第 1 条同类残留）**：`safeResources` 只防「条目缺失/非对象」，**非字符串字段**（`name=123`/`conventions=5`/`nextTitle=42`/`resources=[{label:123}]`）仍抛 `.trim is not a function`（同路径同影响）。
5. **F5（观察）**：`resources:[[]]` 因 `typeof [] === 'object'` 通过过滤，渲染为 `（unknown·unknown）` 而非丢弃；无编造名称。

## 5. A1 结论（原文摘要）

> **预算候选（`3303f7f`，构建 `jWdzmxYFOf6RtLUVbtOkL`）：可交付。** r1 第 1 条经自建探针确认关闭；其余 5 条核对通过；九条不变量关键用例与新增 SSE 中途失败用例 39/39；探针反转与指纹 8/8 独立重现。**不覆盖**：真实供应商、视觉/动画、精确 token。附 F1（跨批间歇，需队长处置）与 F2–F4（低危文档/健壮性残留）。
> **RAG 候选（`13a93ae`）未回退确认**：`git diff 13a93ae HEAD -- apps/api` 为空；`get_rag_adapter()` 仍恒定抛 `RagAdapterUnavailable`、capability 仍 `planned`；35 例契约测试通过。r1 结论（可交付，限定契约/准备范围）仍成立。
> 并建议把矩阵 `A-request-budget` 由「实现待验收」改为「已验收（前端；真实供应商 not_run）」。

## 6. 总控处置（队长，2026-09-23）

| 项 | 处置 | 证据 |
| --- | --- | --- |
| F4（同类残留） | **本批内关闭**：新增 `asText/asKind/asAvailability` 安全降级（原始类型按文本；对象/数组按缺失，**不产出 `[object Object]`**）；不承载信息的条目整条丢弃；渲染与 `trimmedFields` 探测同步；新增单测（含 `[object Object]` 与「等共」反向断言） | `request-budget.ts`、`request-budget.test.ts`（17 例） |
| F3 | **已订正**：注释改为「『…等共 N 项』只计存活条目（丢弃项不是资源，计入会让总数失真）」 | 同上 |
| F2 | **已订正**：FROZEN `checks.build` 更新为当前构建，并在 r3 记录中固化 | FROZEN r3 |
| F5（`[[]]` 观察） | **随 F4 一并收口**：数组条目现按「非对象」丢弃（`Array.isArray` 显式排除），不再渲染空标签 | 同上 + 新单测 |
| F1（跨批间歇） | **登记为 STATUS 台账 R-14，本批不修**：队长复现 `--repeat-each=3` → 1/3 失败，并从失败快照取得状态证据——书处于既有如实状态「生成已中断（无执行器在跑）+ 继续生成」，内容与笔记未丢；判为「测试假设与既定行为不一致」（两标签同时生成同一集合时写锁竞争、冲突预算耗尽即如实中断），与本批 diff 面无交集，待书籍批次定性（测试接受「已中断」再走继续生成，或调宽等待） | `docs/STATUS.md` R-14 行；`npx playwright test tests/e2e/books-commit-safety.spec.ts:238 --repeat-each=3` |
| 矩阵标签 | 待 r3 复验后改为「已验收（前端；真实供应商 not_run）」 | `docs/replica/AI_INTERACTIONS.md` |

**处置后状态**：F2/F3/F4/F5 关闭 → **重新构建并重新冻结**（r3 候选 `a5be128`，构建 `dm5NJM2F0N_z9lp13FK0s`），定向 e2e 15/15、unit 52/436、lint/typecheck 通过；r3 一次全量为 194/1（唯一失败为 R-14）。r3 窄复验见 `A1-REPORT-03.md`（冻结后补）。
