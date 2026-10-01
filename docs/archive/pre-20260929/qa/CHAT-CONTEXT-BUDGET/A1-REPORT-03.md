# CHAT-CONTEXT-BUDGET v1 独立验收报告 r3（A1，窄复验：只读）——最终结论：可交付

> 归档说明（队长）：本文件保存 A1（`Independent-Acceptor`，只读）对 r3 候选的窄复验；文末「总控处置」为队长记录。A1 证据在仓库外（`%TEMP%\a1-verif-r3-20260923\`）。A1 首轮结果卡曾因工具原因空返，队长请求其**只重发结论**（未补跑、未推断），本文即该重发版。

## 0. 候选与指纹

| 项 | 值 | 核对 |
| --- | --- | --- |
| 会话首/末 HEAD | `8fa1272693ff6c64fe3d9fb5c82b5a6df28f1d1b`（首末一致） | 一致 |
| r3 候选 | `a5be12863d56f265cdb1c9e31de01b4def1c5eb9`，tree `3062d9641696830e2645b8f8860c90ba3fc029be` | 与 FROZEN r3 一致 |
| 构建 | `apps/web/.next/BUILD_ID = dm5NJM2F0N_z9lp13FK0s`（mtime 16:22:53，md5 `f63bc529146d306a48be827c1ad87693`，会话首末未变） | 与 FROZEN 一致 |
| 指纹 8/8 | `request-budget.ts 1fe5896eb331d946`、`request-budget.test.ts 9ec18c573105c810`、`chat.ts eb04f89d…`、`context-budget.ts 1cc2154f…`、`store.ts c1f3f3df…`、`ChatWorkspace.tsx 4df74bb6…`、`course-session.ts 20d745bd…`、e2e spec `cdc53f32…` | 8/8 与 r3 FROZEN 一致 |
| 后续提交 `8fa1272` | `git diff --stat a5be128 8fa1272` = 仅 FROZEN JSON（+20/−13） | 仅文档，通过 |
| superseded | FROZEN 保留 r1 `a9968cd`、r2 `3303f7f` 记录 | 一致 |

## 1. F2/F3/F4（+F5）逐条结论

| 项 | 结论 | 关键观察 |
| --- | --- | --- |
| F2 | **pass** | FROZEN `checks.build` = 当前构建，与磁盘 `BUILD_ID` 逐字符相同 |
| F3 | **pass** | 注释称「只计存活条目」与实现一致；实证 13 存活 + 4 丢弃 → 输出「…等共 13 项」，断言不含 14/15/16/17 |
| F4 | **pass（任务清单四形态）** | `retry()` 最小场景：`threw=null`、`unhandledRejections=0`、`requests=1`、`budgetNotice=null`、`sending=false`；system 含 `课程名称：123`、`<<<\n5\n>>>`、`下一个未完成单元：42`、资源行 `：123（knowledge_base·available）`；**不含 `[object Object]`/`undefined`/`null`/`unknown`/`等共`**；免责句在；`record.totalChars=179 = Σ content.length`；旧轮快照未被改写。四形态（`{label:{}}`/`{kind:{}}`/`{availability:true}`/三缺）与 `[[]]` 全部丢弃 → 渲染「无登记资源」 |
| 反向断言 | **pass** | `label:{toString:()=>'FAKE-NAME'}` 不泄漏、不隐式强转；`kind:88`/`availability:{}` → `（unknown·unknown）`（不原样展示脏值）；丢弃项不计入「等共」 |
| r2 回归 | **pass** | `resources=[null]` 经 `retry()`：不抛错、渲染「无登记资源」、无 null/undefined、账目 129=129 |
| F5 | **pass（随 F4 收口）** | `[[]]` 因 `Array.isArray` 显式排除而丢弃 |

## 2. 未回退核对

- 不变量 1/2/3/6/7 独立探针 **6/6 通过**（问题逐字不裁剪含首尾空格、边界 2000/2001 与 32000/32001、空问题、250 条历史 → 恰好 200 条丢 51、Σ=账目、课程块在最前、`courseDropped=true` 时 `courseTrimmedFields=[]`、6 种收缩形态免责句均在且 system ≤2400、send 预检零副作用）。
- r2 全套探针在 r3 源码上重跑 **38/39**：唯一差异为契约外 `availability`（如 `local`）现统一降级 `unknown`（枚举白名单），属本轮加固方向，契约内三值不受影响。
- diff 面：`git diff --stat 3303f7f a5be128 -- apps/web` 仅 `request-budget.ts`(43+/14−) 与 `request-budget.test.ts`(37+/0−)；`-- tests` 为空；`course-session.ts` 在 `a9968cd→a5be128` 与 `3303f7f→a5be128` 均为空。
- 探针反转：原件与副本均 **2/2 按预期失败**（D1 208 字、D2 1990≤2000）；副本 md5 仍 `18122b3c1953eb3ef2ca53dfe92d7ccc`；产品路径反转探针 **3/3 通过**。
- **突变对照（实跑非推断）**：把 `asText` 唯一改回 `String(value)`（diff 核实仅 3 行），用逐字节复制的官方测试运行 → **15 通过 / 2 失败**，失败恰为新 F4 用例与 r1 期脏快照用例 → 新增用例与实现**因果绑定**；断言未放宽（r3 仅新增 37 行、0 删除）。

## 3. 独立复跑数字

| 项 | 声称 | A1 实测 |
| --- | --- | --- |
| lint | 0 警告 | **0 警告**（exit 0） |
| unit | 52/436 | **52 文件 / 436 例全过（81.83s）** |
| 定向 e2e | 15/15 | **15 passed（18.3s）**（`next start` 5174，即冻结构建） |
| typecheck / api / 全量 e2e | — | **not_run**（typecheck 与 api 不在本轮允许命令集，后端零改动；全量 e2e 按指令不跑，R-14 已知无增量信息） |

## 4. A1 本轮新发现

1. **扩展边界（低，判「无需再修」）**：条目「标签不可读但 kind/availability 可读」被保留并渲染为空标签，如 `{label:{}, kind:'file', availability:'available'}` → `（file·available）`。仅契约外/损坏数据可达（应用写入器标签恒为字符串）；不抛错、无 `[object Object]`、不伪造名称、计数按存活口径。
2. **r2→r3 行为差异（记录）**：契约外 `availability` 字符串统一渲染 `unknown`（白名单），契约内三值不变；A1 的 r2 探针中该行断言随之作废，非缺陷。
3. **观察**：`label:false` → 渲染 `false（file·available）`，与数字标签同一「按文本降级」策略，无伪造。
4. **文档/流程（非候选缺陷）**：`docs/STATUS.md` 有一处未提交修改（队长更新本批数字），`docs/qa/CHAT-CONTEXT-BUDGET/A1-REPORT-02.md` 未跟踪但被 STATUS 链接引用 → 建议随下一提交落库。
5. **A1 过程备注（诚实记录）**：其首次探针反转复跑漏设 `NODE_OPTIONS=--no-experimental-webstorage`，导致 15 例误失败；该次作废并用正确环境重跑，本文所引数字均出自纠正后的运行。

## 5. A1 结论（原文摘要）

> **可交付**（候选 `a5be128`、tree `3062d964…`、构建 `dm5NJM2F0N_z9dk…`）。F2/F3 关闭、F4（任务清单四形态）关闭、F5 关闭；不变量未回退；探针反转 2/2、产品路径 3/3；lint/unit/定向 e2e 三项独立复跑与声称一致；新增单测经突变对照证明因果绑定。附 1 条低危扩展边界（无需再修）与 2 条文档收尾项。
> **覆盖范围**：前端请求构建与课程块加固、账目一致性、定向浏览器报文级 e2e 15 例、52 文件 436 例单测、lint、构建产物/指纹一致性、探针反转、突变因果对照。
> **未覆盖**：真实供应商（无凭证 not_run，未验证凭证有效性）；视觉/动画（无 `.css` 改动，不宣称视觉通过）；精确 token（全为字符估算）；R-14 跨批间歇（书籍批次，未定性、本批不修）；typecheck/api/全量 e2e 本轮未重跑。

## 6. 总控处置（队长，2026-09-23）

| 项 | 处置 |
| --- | --- |
| r3 结论 | **采纳**：本批交付候选定为 **`a5be128`**（tree `3062d964…`，构建 `dm5NJM2F0N_z9lp13FK0s`）；三轮验收记录见 [A1-REPORT-01.md](A1-REPORT-01.md)、[A1-REPORT-02.md](A1-REPORT-02.md) 与本文件 |
| 第 4 节第 4 条（文档收尾） | **已处置**：`A1-REPORT-02.md`/`A1-REPORT-03.md` 与本轮 STATUS/矩阵更新随最终提交入库，STATUS 链接不再悬空 |
| 第 4 节第 1 条（标签不可读但 kind 可读仍渲染空标签） | **登记为已知边界，不在本批修**：仅契约外/损坏数据可达，行为不抛错、不伪造、计数如实；是否「标签不可读即整条不渲染」留待后续小批（与 `courseContextMessage` 双渲染口径技术债同批处理更合适） |
| 第 4 节第 2/3 条（契约外可用性/布尔标签的降级口径） | **认可现状**：白名单外一律 `unknown`、原始类型按文本降级，方向与「不展示脏值、不伪造」一致；写入 `docs/PROJECT_GUIDE.md` §4.4 的既有口径已足够（上限与免责句），该细节留有单测固化 |
| 矩阵标签 | **已按 A1 r2/r3 建议改为「已验收（前端；真实供应商 not_run）」** | 
| R-14（跨批间歇） | 维持 STATUS 台账登记，本批不修；`FROZEN-CANDIDATE.json` 已就其对全量汇总数字的影响作说明 |
