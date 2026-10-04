# F30-L v4 作者结果卡 — 待独立验收

负责人 g2_fe；B5R-R06；停止产品及可执行作者QA/runner写入 2026-10-03T11:59:28.741973+00:00。状态 AUTHOR_VERIFIED_PENDING_INDEPENDENT；不关闭 B5。

`PRIVATE-MANIFEST-v4.json` SHA `92f5b631d0e349a4c6960c5ac39f2484b922698c391d3d54e9bca0c6516b683b`；`BEFORE-v4.json` SHA `7198877d6ffef11fe67824014f122f2e2d151600528e01fc964f5110d1268dad`。全部 1946 项前序证据逐项 SHA 无漂移，v1/v2/v3、95作者场景及全部首败原件保持；冻结33件与清单 SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db` 无漂移。仅改 SourcePanel 与 lesson-workspace.test；ProposalPanel、ROOT AGENTS、types/contracts/client/router/其余产品及旧QA不写。

| 最新完整窄检查 | 实际结果 | PID | 时间 | 源漂移 |
| --- | --- | --- | --- | --- |
| f30-v4-unit-r1 | 106/106；0 failed/0 skipped | 480 | 11399.79 ms | 0 |
| f30-v4-types-r1 | exit0 | 5228 | 1837.024 ms | 0 |
| f30-v4-lint-r1 | exit0；0 warnings | 6208 | 3354.146 ms | 0 |

最终完整单轮5文件106例 = 原95 + 新11；不跨轮拼绿。旧测试定义逐字节核对保持（仅新增ModelProfileView类型import及尾部新用例）。Node24固定路径 + NODE_OPTIONS=--no-experimental-webstorage；完整argv/env/PID/exit/ms/sourceBefore/sourceAfter、原输入快照、日志SHA、首败及隔离TEMP见RESULT-v4.json/各command.json。

R06修复：来源异步采用读取latest selection与当前教师inputs，保留模型/时长/要求；granular patch先同步latest ref再回传onChange，避免同轮迟到闭包用旧整体值覆盖。相同来源刷新保留合法固定题/练习与已核验证据；真实班级/KP/报告/学科变化按意义清除失效证据和选项。每次await后的alive/epoch、同学科ready/班级/KP、完整分页及错误不采用半份均保持。教材核验仍精确比对捕获signature，教师新inputs期间迟到核验拒绝回填。生成原包/幂等/cache/ProposalPanel不变，新模型使既有M1候选过期且不能采用。

修前完整f30-v4-unit-before：101/106，exit1，PID24400，11466.86ms，source0；原95全部通过。新增5例真实产品首败：首次固定报告晚读把M2擦为空，classes/report/practices晚读及旧候选刷新把M2倒退M1。失败都发生在模型实际DOM断言，其后的时长/要求/选项/证据断言在该轮未执行，最终完整106全部实跑。新增另外6例unknown/503、取消读取、真正换来源及过期核验在修前已通过。修前源码/testbytes/log/JSON保全，修前→最终唯一变化SourcePanel，作者QA未修改、断言与预算未削弱。

新11用例覆盖：首次固定报告晚读；class/report/practice三种刷新晚读；status0/503来源失败；取消后旧响应；真正换报告/学科；教师新输入后核验证据晚到；既有M1勾选候选在刷新期间换M2仍过期/APPLY0。全部使用实际控件、固定期望值和受控API替身，不调用生产merge作oracle。

未执行：独立V00/静态审查、真实API/RAG/model/jobs/Next浏览器及四视口、全check/build/API/e2e/chat、Word/WPS人工版式。原因：本卡只作者私有验证，CTRL持有服务与稳定候选最终门禁。未接触正式.env/数据/凭证/真实浏览器草稿，未起停服务、打开浏览器、真实HTTP或执行Git。

全部检查子进程及日志已关闭，新隔离TEMP保留。产品/可执行作者QA/私有runner范围已STOP释放，等待CTRL冻结及独立验收；不以替身单测代表真实闭环通过。

## 修改范围

- `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`
- `apps/web/src/features/lesson-plan/lesson-workspace.test.tsx`
