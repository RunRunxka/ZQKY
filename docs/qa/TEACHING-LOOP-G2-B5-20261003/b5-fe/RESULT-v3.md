# F30-L v3 作者结果卡 — 待独立验收

负责人 g2_fe；停止产品写入 2026-10-03T11:00:21.048460+00:00。状态 AUTHOR_VERIFIED_PENDING_INDEPENDENT；不关闭 B5。

`PRIVATE-MANIFEST-v3.json` SHA `4102cdc5451d2d5a0649eab13e02676bdd6775d1ee7e246b0f914421b658008c`；`BEFORE-v3.json` SHA `fbaf704d8ef9e3c3bac22d66b737e104ddca4f6a5f62cf6a5d2dac93662aa019`。v1/v2 等全部 1593 项前序证据逐项 SHA 核对无漂移，旧73单轮及全部首败原件保持；冻结33件及清单 SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db` 无漂移。只改授权三件，ROOT AGENTS/types/contracts/client/router/其它产品与旧QA不写。

| 最新完整窄检查 | 实际结果 | PID | 时间 | 源漂移 |
| --- | --- | --- | --- | --- |
| f30-v3-unit-r2 | 95/95；0 failed/0 skipped | 22436 | 9473.539 ms | 0 |
| f30-v3-types-r2 | exit0 | 21512 | 1753.949 ms | 0 |
| f30-v3-lint-r2 | exit0；0 warnings | 16368 | 2959.092 ms | 0 |

最终一轮5文件、95例 = 原v2保留73 + 新v3 22，不跨轮拼绿。Node24固定路径与 NODE_OPTIONS=--no-experimental-webstorage；各最新轮 uncaughtExceptionRecords=0。完整argv/env/PID/exit/ms/sourceBefore/sourceAfter、原输入快照SHA、日志SHA与保留TEMP见 RESULT-v3.json/各command.json。

R04：实际GET接受候选时，保存该固定候选自己的完整首次generation identity clone，同固定job/operation/sourceEpoch与原编辑/加载/基线；stale从该身份判断。新的M2操作422/503/unknown/缓存写入失败不会使已有M1候选借M2签名复活。旧勾选保留但只读，APPLY HTTP为0；明确失败可拒绝旧候选，unknown仍只能恢复原操作。原包深等重放与旧job/GET迟到guard保留。

R05：统一私有完整分页，active classes、analysis-runs、practice-sets与原classesReport每页最多200，按total与真实items offset读完再采用；ready/reviewed过滤在读完后执行。每页校验epoch/unmount、safe/stable total、offset、越界、空页无进展；失败可见且不采用半份列表。真实UI选择第241班、第241 ready报告、第241 reviewed固定练习，核班级eligibility与真实固定revision；15项后页错误矩阵和refresh/unmount迟到也通过。教材/模型完整array端口与confirmed固定题50行显式继续保持。

首轮 f30-v3-unit-r1 94/95：新增unknown作者用例错误等待具体 ApiError 文本。公共status0语义展示“重试原生成包”并令error=null，首败DOM中旧候选已过期且采用禁用。新QA revision仅改等待真实unknown入口；所有旧候选/selected/APPLY0、M2首次缓存与原包深等断言、用例和时间预算保留。产品不因该首败改动；r1原testbytes/log/JSON保全，r1→r2唯一源delta为测试文件，最终完整95另新单轮实跑，不拼94+窄例。

未执行：独立V00、真实API/RAG/model/jobs/Next浏览器链及三视口、全check/build/API/e2e/chat、Word/WPS人工版式。原因：本卡仅作者私有验证，CTRL负责稳定候选/服务与最终门禁。未接触正式.env/数据/凭证/真实草稿，未起停服务、打开浏览器、真实HTTP或执行Git。

全部子进程与日志已关闭，隔离TEMP保留。产品可写范围已释放；等CTRL稳定候选及独立验收，不把替身单测当真实闭环通过。

## 修改范围

- `apps/web/src/features/lesson-plan/components/ProposalPanel.tsx`
- `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`
- `apps/web/src/features/lesson-plan/lesson-workspace.test.tsx`
