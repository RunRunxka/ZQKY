# 独立验收 A1 报告（第 2 轮：窄复验被修项 + 回归）

任务：UX-PERF-CLOSEOUT v1 / A1 第二轮（只读；未改动任何源码/文档/测试、未提交）
候选：`main@522daec`（= `d1ba15d` 修复 + 后续文档提交），工作树干净
构建：`.next = 7UEyDMWKt_mozNYtuwJuH`（r4）、`.next-test = hrwcN9OyO8by2EqtkSRn_`（当轮）
**判定：pass**（3 项文档残留 + 2 项证据归档建议，均不阻断；无遗留代码缺陷）

## 被修项复验

| 被修项 | 验收者命令 | 观测 | 判定 |
| --- | --- | --- | --- |
| ① rAF 内复检跟随 | `node _work/perf-20260923/stream-regression.mjs 5199 8002` | `19/19 passed`；该项 `PASS … 4 次尝试，窗口内最大值=0,0,0,0`（r3 为 `FAIL … 0 → 4052`） | pass |
| ① 独立确定性复现 | 其自写 `_work/verify-A1/scroll-deterministic.mjs 5199 8002 … 4` | 4/4 命中窗口（`armed=true`）、`frames=[0×12]`、`maxInWindow=0`、`after.top=0`，且 `textGrewWhileScrolledUp=true`（流不被阻塞） | pass |
| ① 代码面 | `git show d1ba15d -- …/ReasoningDisclosure.tsx` | 仅新增 `if (!following.current) return;` 与注释，无新状态，未动折叠/停止/断流/落盘 | pass |
| ② 旧能力值降级展示 | 其自写 `_work/verify-A1/capability-display.mjs 5199` | 「模式 · 深度求解」＋「入口已停用（随「更多能力」一并移除）…历史记录保持可读。」；「模式 · 可视化」「模式 · RAG 模式」＋「当前未接入…不代表现在可以发起」；无 capability 的消息不出现该行且 persona 条目照常；**渲染后存储快照逐字节未变** | pass |
| ② 单测/工程 | `vitest run message-duration.test.tsx`、`npm run test:unit`、`typecheck`、`lint` | 5 passed；全量 **52 文件 / 441 例**；typecheck 0；lint 0（`--max-warnings=0`） | pass |
| 回归（受影响 spec） | `npx playwright test tests/e2e/{chat,chat-home,chat-message-locate,chat-deeplink,sidebar-chat-fixes,sidebar-transition,lesson-plan}.spec.ts` | **44 passed (1.1m)**（chat 4 / chat-home 4 / chat-message-locate 12 / chat-deeplink 7 / sidebar-chat-fixes 5 / sidebar-transition 4 / lesson-plan 8），失败 0 | pass |
| 口径订正 | `git diff d65c9ca 84c0e98 -- docs/…`、grep | 长任务行与 `baseline-wf-wf-50k.json` 逐字相符（210 条/23 078 ms/最大 291 ms → 0）；「唯一变差项」已改；堆改标单次采样；§4 如实保留 r3 的 18/19；§8.2 降级展示；溢出条目名对齐 | pass（残留见下） |
| r4 冻结记录 | sha256 of `git show <ref>:<path>` | `files` vs `84c0e98` = **49/49**、`codeFiles` = **37/37**；vs `HEAD(522daec)`：`codeFiles` **37/37** | pass（范围说明见下） |
| 探针来源自检 | `node _work/perf-20260923/perf-probe.mjs --chars 50000 … 5199` | `originSelfCheck={expectedChars:50000, actualReasoningChars:50000, ok:true}`；p95 **5.70 ms**、max 22.2 ms、>50 ms **0**、script **1094 ms**、layout 2049 ms、DOM **384**、IDB 64 次、首见增量 **47.8 ms**、`longtasks=0` → **修复未带来性能回退** | pass |

## 验收者给出的机制解释（与实现一致）

按 HTML 渲染步骤，**滚动事件在 rAF 回调之前派发**：在「提交落地的微任务里上滚」这一确定性窗口下，
`following` 先变 false，rAF 回调内的复检因此拦住写入；r3 必被拉回的机制是其写入落在滚动事件之后、
并把 `following` 重新置 true。验收者同意我方口径：**修复只恢复到 r3 之前「判断即写」的行为**，
不主张比之前更好。

## 本轮点名项的处置（收尾后再次请复核）

| # | 项 | 处置 |
| --- | --- | --- |
| 1 | README:22 残留「longtask 无输出」自相矛盾 | 已改写为「观察器有效（首版探针写法静默无输出，已弃用）」 |
| 2 | 断言反转数字缺原始日志 | 已重新跑两轮并留档：`_work/perf-20260923/stream-regression-reversal.log`（18/19，构建 `ZrHj7mKmbjFQXKXS3MZCi`）与 `stream-regression-fixed.log`（19/19，构建 `oNm41Sz_SmvxGHKX_M9vi`） |
| 3 | 堆数字两份文档不一致 / §3.2 标签未改 | 统一为「CDP `Performance.getMetrics().JSHeapUsedSize`，测量窗末**单次采样**」并取同一来源运行（50k：102.4→**11.4** MiB，注明 r4 复测 11.6、A1 复测 18.8～24.3 随 GC 波动）；§3.2 标签同步改为单次采样 |
| 4 | 候选在窄复验期间又移动、r4 `files` 只等于 `84c0e98` | 出 **r5** 记录：对齐最终 tip、把 A1 报告纳入 `files`、保留 `codeFiles` 子集并写明「代码指纹以 `codeFiles` 为准」 |
| 5 | `A1-REPORT-01.md` 尾部指向尚不存在的 r2 报告 | 本文件即 A1-REPORT-02，引用闭合 |
| 6 | 5197 是重建 `.next` 之前的旧进程（chunk 404、SSR disabled） | 已停止该进程；后续界面探针一律以 `.next` 最新构建重新起服 |

## 未执行 / 无法验证（验收者声明）

- **反转实验未由验收者执行**（需改产品源码并覆盖冻结构建，超出其只读授权）——替代方式是它自己实现的
  确定性探针（4/4 恒 0）；本轮已由总控补上双轮原始日志作为反转证据。
- 全量 200 例 e2e 未重跑（其跑了受影响 7 spec 44 例 + 上一轮 6 spec 47 例 + `space-pages` 8 例 +
  `books-commit-safety` 全文件 6 例）；`test:api` 本轮未再跑（`apps/api` 零改动，上一轮 217 passed）。
- 真实供应商 / 真实 RAG / 硬件触摸 / 逐帧动画仍为 not_run；**UI 视觉像素级通过未声明**。

证据：`_work/verify-A1/a1r4-*.{log,json}` 与其自写探针 `scroll-deterministic.mjs`、`capability-display.mjs`；
旁证 `_work/perf-20260923/stream-regression-{reversal,fixed}.log`。
