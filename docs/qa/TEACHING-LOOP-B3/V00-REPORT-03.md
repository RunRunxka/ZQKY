# V00 · TEACHING-LOOP B3 最终确认（03 · r3/r4 冻结收口）

- 任务：确认 CTRL 按 R2 建议"重算两个文档散列并重新冻结"后的最终状态
- 对象：`FROZEN-B3.json`（定版，`revision=B3-final`，163 文件）、`FROZEN-B3-r2.json`、`FROZEN-B3-r3.json`、`FROZEN-B3-r4.json`
- 边界：只读复算；本轮新增仅本报告与 `V00-probes/p36_final_confirm.*`；未改任何进入清单的文件
- 证据：`docs/qa/TEACHING-LOOP-B3/V00-probes/p36_final_confirm.py`（exit 0）、`p36_final_confirm.json`、`p36_final_confirm.run.log`

## 1. 三点确认

| 确认项 | 结论 | 证据 |
| --- | --- | --- |
| 1. 按定版 `FROZEN-B3.json` 复算 163/163 | **pass**：磁盘 163/163 一致，`stale_docs_only` 消失；此前 2 个过期文档（`EVIDENCE-COMMANDS.md`/`REPORT.md`）已与定版一致 | `p36`：`diskOk=163`、`diskBad=[]` |
| 2. r2 → 定版变更集合 | **pass**：新增 0 / 删除 0 / 变更**恰为** `docs/qa/TEACHING-LOOP-B3/{EVIDENCE-COMMANDS.md,REPORT.md}`；产品/测试零变化；两个 r2 改动文件（`contracts/scores.ts`、`services/assessments-api.ts`）磁盘字节 = r2 = 定版（`r2ProductFilesUnchanged` 两项 True） | `p36`：`r2ToFinal.changed`、`r2ToFinalProductChanged=[]` |
| 3. 是否仍需重验 | 无（类型层改动已由 typecheck + eslint + 46 例单测覆盖，R2 已复验；本轮仅文档散列重算，无产品字节变化） | 见 §4 一行结论 |

补充复核（独立复算，非采信声明）：

- `FROZEN-B3.json` 的 `files` 与 `FROZEN-B3-r4.json` **逐条逐字节相同**（`finalEqualsR4=True`）。
- `FROZEN-B3-r3.json` 的相对关系：r2→r3 变更同样恰为那两个文档（r3 为中间冻结）；
  **但 r3 与定版不等价**——r3 与定版恰在上述两个文档上不同（详见 §2）。

## 2. 新发现（文档记录与实际锚点不符，需 CTRL 处置）

- 事实：
  - `EVIDENCE-COMMANDS.md`（冻结文本）写："**`FROZEN-B3-r3.json` = 定版 `FROZEN-B3.json`**（…r2→r3 差异恰这 2 个文档）"、"定版…其内容与 `FROZEN-B3-r3.json` 逐字节等价（脚本已核对）"；`REPORT.md` 同述 r3 = 定版。
  - 独立复算：**定版 = `FROZEN-B3-r4.json`，而不是 r3**。r3 与定版差异恰为同两个文档：
    - `EVIDENCE-COMMANDS.md`：r3 `2f9abea89ab30d23…` → 定版/r4 `4660f30b32790787…`；
    - `REPORT.md`：r3 `2e95eef85e77c8ef…` → 定版/r4 `f9389b05ce716521…`。
  - 即：r3 冻结的是"R2 报告所指出的过期文本"版本；随后 CTRL 把 r3 结论写进这两份文档并再次冻结为 r4，定版取 r4 内容。其最新消息中"r3 = 定版"与该文档文本一致，但与磁盘/清单事实不符（"r4 = 定版"才是事实）。
- 影响：**不影响产品候选与 163/163 自洽性**（定版清单与磁盘完全一致，产品/测试零变化）；仅影响冻结文档中的流程记录准确性（r3 归因）。
- 建议（下一次成批处置，不必立即）：把两份文档中的"r3 = 定版/逐字节等价"更正为"r3 为中间冻结；定版与 r4 逐字节等价"；由于两份文档在清单内，更正后会再次改变这 2 个散列，需要按"最后一步 = 冻结"的顺序重算并重新冻结（r5）。是否需要更正由 CTRL 决定；本报告只报告事实，不代改。

## 3. 未能/未做

- 未对 r3/r4 之前的文档历史做逐次全文 diff（只有散列与当前文本；差异已用散列定位到"同两个文档"）。
- 未重跑产品行为检查（R2 已跑：typecheck 0 / eslint 0 / vitest 46/46；本轮无产品字节变化，`p36` 证明）。

## 4. 最终一行结论

**产品候选可交付；冻结清单自洽（定版 163/163，r2→定版差异恰两个文档、产品与测试零字节变化）。** 唯一残留是冻结文档中"r3 = 定版"的归因记录与实际（定版 = r4）不符——属文档记录问题，建议后续成批更正并作 r5 重冻结，不阻塞交付。

---

## 追加 · r7 收口确认（第三次，30 秒口径）

对象：`FROZEN-B3.json`（定版，163）、`FROZEN-B3-r7.json`、`FROZEN-B3-r2.json`；证据：`V00-probes/p37_final_confirm_r7.py`（exit 0）、`p38_closure_audit.py`（exit 1，见下）、各自的 `.json`/`.run.log`。

### 清单侧（全部通过）

| 确认项 | 结论 | 数据 |
| --- | --- | --- |
| 按定版复算 163/163 | **pass** | `p37`/`p38`：`diskOk=163/163`、`diskBad=[]` |
| r2 → 定版变更集合 = 3 个文档 | **pass** | 恰为 `docs/CURRENT_STATUS.md`、`docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md`、`docs/qa/TEACHING-LOOP-B3/REPORT.md`；新增/删除 0 |
| 产品/测试零变化 | **pass** | `apps/**`、`tests/**`、`scripts/**` 自 r2 起零字节变化（`productChanged=[]`；两个 r2 类型层文件保持 r2 字节） |
| `r7 == 定版` | **pass** | `finalEqualsR7=True`；`FROZEN-B3.json.revisionHistory` 含 r1…r7、`docsChangedVsR2` 三项、`productTestUnchangedSinceR2=true`（`p37`） |

### 文档归因残留（非阻塞，需 CTRL 决定是否再修）

定版清单自洽，但**冻结文档内部对"本批终态"的修订归因仍落后于账本**（与上一轮"r3 vs r4"同类，只是这次是 r5/r6 vs 实际 r7）：

- `docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md:84-87`（冻结字节）："逐次修订记录（r1…r6 全部保留，**定版 = `FROZEN-B3-r6.json`**…）"、"其内容与 `FROZEN-B3-r6.json` 逐字节等价（脚本已核对）"。实测：定版 = **r7**；r6 与定版仍差 1 个文件（恰为本文件 `EVIDENCE-COMMANDS.md`：r6 哈希 `8f810cf582d3d173…` → 定版/r7 `322ba3763a55e3b0…`），故该句不成立。
- `docs/qa/TEACHING-LOOP-B3/REPORT.md:101/103`（冻结字节）："已按…更正记录并冻结为 **r5**"、"r2→定版差异恰**两个**文档"。实测：终态冻结为 **r7**；r2→定版为 **3 个文档**（含 `docs/CURRENT_STATUS.md`）。
- `docs/CURRENT_STATUS.md:46`（冻结字节）："逐次修订 r1→r2→r3→r4→**r5** 全部保留"。实测账本为 r1…**r7**。
- `p38_closure_audit.py` 以脚本复现全部取证：`ledger.ok=true`、`docAttribution.ok=false`、`verdict=ledger_ok_attribution_lag`（exit 1）。

影响与处置建议：

- **不影响**产品候选交付与清单自洽性（163/163 与产品零变化成立）；纯文本归因问题。
- 若要文本精确：需改这 3 个文档并再冻结为 r8（又会改变这 3 个散列）。**建议**：改述为"逐次修订以 `FROZEN-B3.json.revisionHistory` 为准"，正文不再硬编码最终 rN，避免"每次记录冻结 → 又落后一轮"的循环；或直接接受为已知残留并在 B4 起流程里要求"冻结后不再回写任何进入清单的文件"。
- 按 CTRL 要求，本轮只报告、不代改、不重冻。

### r7 收口一行结论

**产品候选可交付；定版清单自洽（163/163；r2→定版差异恰 3 个文档；产品/测试/scripts 自 r2 起零字节变化；定版 = r7）。** 唯一残留为冻结文本里的修订归因未同步到 r7（写作 r5/r6、"两个文档"），属文档记录问题、不阻塞交付；是否再修（需 r8 重冻）由 CTRL 决定。

---

## 追加 · r8 最终核对（正文归因循环终止后的收口）

对象：`FROZEN-B3.json`（定版，163）、`FROZEN-B3-r8.json`、`FROZEN-B3-r2.json`；证据：`V00-probes/p39_final_confirm_r8.py`（exit 0）、`p39_final_confirm_r8.json`、`p39_final_confirm_r8.run.log`。

| 核对项 | 结论 | 数据 |
| --- | --- | --- |
| ① 定版 163/163 | **pass** | `diskOk=163/163`、`diskBad=[]` |
| ② r2 → 定版 = 3 个文档、产品零变化 | **pass** | 变更恰为 `docs/CURRENT_STATUS.md`、`docs/qa/TEACHING-LOOP-B3/{EVIDENCE-COMMANDS.md,REPORT.md}`；新增/删除 0；`apps/**`、`tests/**`、`scripts/**` 零字节变化 |
| ② 附：`r8 == 定版` | **pass** | `finalEqualsR8=True`；`revisionHistory.revisions` 含 r1…r8、`docsChangedVsR2` 三项、`productTestUnchangedSinceR2=true` |
| ③ 三处文档不再硬编码"定版 = rN" | **pass** | 脚本扫描 `EVIDENCE-COMMANDS.md`、`REPORT.md`、`CURRENT_STATUS.md`：`定版 = FROZEN-B3-rN` / `冻结为 rN` / `与 rN 逐字节等价` / `r1…rN 全部保留` / `r1→…→rN` 命中均为 **0**；三处均出现 `revisionHistory` 指向（"逐次修订以冻结记录的 `FROZEN-B3.json.revisionHistory` 为准"） |
| ③ 附：残留事实陈述一致性 | **pass（事实核对）** | `REPORT.md` 仍有一句"r2→定版差异恰三个文档"——属变更集事实陈述（非"定版 = rN"硬编码），实测恰为 3，一致；不构成阻塞 |

说明：`p39` 首轮曾把"差异恰 N 个文档"也列入禁止模式而报 fail；核对 CTRL 承诺的口径（只禁"定版 = rN"、正文指向 `revisionHistory`）后，把该句改为"与实测一致性"检查——实测 3=3，通过。此调整只发生在我方探针，不涉及候选。

### r8 最终一行结论

**产品候选可交付；定版清单自洽（163/163；r2→定版差异恰 3 个文档；产品/测试/scripts 自 r2 起零字节变化；定版 = `FROZEN-B3-r8.json`，逐次修订以 `FROZEN-B3.json.revisionHistory` 为准）。** 正文归因循环已终止，无新增残留；B3 闭环，未启动 B4、未提交、未推送，不再改动任何进入清单的文件。
