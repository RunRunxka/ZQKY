# B5-V00 v4 反例准备

CTRL 2026-10-03 明确授权，在原 prebuild-v1 的 API42/unit15 首轮结束、完整 check 的 QA 绑定结束后新增 v4，产品仍停写。v1/v2/v3 源码和首次 log/XML/JSON 全部保留。v4 仅新增 unit spec/config，本卡、静态结果与清单。

active unit 为 `v4/unit/vitest.config.ts`：继承原 unit10 与 v3 的全部5行为，唯一 fixture 更正是在模拟 LessonProposalView 中补必填 `jobId=receipt().job.jobId`，没有移除或放宽任何断言。v3 首轮这3例因自身返回 malformed DTO 不展示候选，不能据此宣称真实 unknown 链路失败或通过。后页241班级/报告、limit≤200、最后班与 KP eligible 的完整分页断言保持。

新增一例固定旧模型 A 的合法候选、选择教学重点 → 来源 B 使其 stale → 新模型 B 生成明确422/503失败 → 旧候选仍须 stale、采用按钮禁用、试点采用 API 调用次数0。先证明旧 A 原先可选择采用，再看变化后限制；真实 LessonPlanProvider/ProposalPanel/useLessonOperation，服务端回复通过 unit 能力接口注入，禁止把此 unit 冒称真实浏览器网络。两个失败状态在同一独立测试中按序检查；若首个状态失败，后续分支明确未执行。

静态发现 unit **16**（原10 +修正版5 +新增1），语法检查只 transpile/AST，不执行产品。API active 保持 `v3/api`（42），browser active 保持 `v3/browser/external.config.ts`（8）；此次等待 ROOT 新冻结含 v4 的 `B5-prebuild-v2-QA`，不会直接拿旧 candidate 声称新 QA 匹配。

获 ROOT 新 candidate 后使用新不可复用 label 与私有输出：

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:NODE_OPTIONS = '--no-experimental-webstorage'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<CTRL unique v4 first label>' --candidate '<CTRL frozen QA candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v4/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/<new private output>/results.json'
```

v4 执行 **未执行**：等待新 QA candidate 和 CTRL 首跑授权。未改产品/旧 QA/预算，不运行构建或 browser，不启停 TCP，不访问正式数据与凭证。静态证据 `preparation/prepare-v4.json`；封存清单 `QA-MANIFEST-v4.json`。
