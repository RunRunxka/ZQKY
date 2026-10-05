# B7B-X v1 作者结果卡 — STOP，待 ROOT 独立验收

本卡完成受控试跑离线技术条件。产品仅新增六个 controlled_*.py、一个专属 test_controlled_executor.py 与 README-controlled-trial-v1.md；未改生产服务/Provider/提示词/API/表/依赖锁、原 common/prepare/aggregate/preflight，也未导入旧 QA builder。新证据只写本批 executor/。

真实生产链覆盖 prepare/build_request/execute、固定学情/教材/正式题快照再验证、LessonPlanService proposal/QA apply、JobEngine 和三协议原 Provider；每次最终 HTTP body 经 BoundaryTransport 校验，进入显式 MockTransport。CLI15 新整轮实际 fixtureWireSends=15、realModelCalls=0、15 technical_pass、累计已核 fixture usage=3000；成功 receipt 重放新增 Provider 0。所有 teacher/native 仍 pending，docx ref 为 null。

| 完整轮 | 实际结果 | PID / elapsed ms |
| --- | --- | --- |
| self-check-sixth | 73 passed，exit 0，源码零漂移 | 3136 / 22899.983 |
| cli-fifteen-v1 | 15 案例新 TEMP 实际生产链通过，exit 0 | 26272 / 14913.667 |
| cli-live-no-auth-v1 | AUTHORIZATION_MISSING，exit 2，发送 0 | 13364 / 277.662 |
| cli-live-no-proof-v1 | BILLING_BOUND_UNSUPPORTED，exit 2，发送 0；不读给定授权路径 | 25932 / 253.362 |
| cli-case-drift-v1 | CASE_SPEC_DRIFT，exit 2，发送 0 | 17396 / 233.975 |
| material-quality-v2 | 原 quality 52 passed，exit 0 | 9144 / 8938.753 |
| material-prepare-v3 | 原 prepare 49 passed +34 subtests，exit 0 | 19932 / 32828.867 |

第六作者轮 guard：合法生产 import 184、TEMP SQL 3610、asyncio 内部 self-pipe 30；未隔离 app.main、正式 env、正式数据、非 TEMP DB、真实网络五类禁止项均 0，app.main 未导入，credentialsFile=null。CLI15 合法 import 183/TEMP SQL 1720，禁止项均 0。两个 live 拒绝及 case 漂移的独立 guard 合法生产 import/SQL/真实网络均 0。纯材料回归共 52+67 个子 CLI 四 guard 总量均 0，不将真实生产链的合法 TEMP SQL 隐写为 0。

反证包含独立冻结 scope 与同授权 immutable scope、model/profile/config/request/output cap 漂移、原 case 事实身份、预算最后不足、attempt 耗尽、坏 JSON/结构/length 已核 usage 保留、坏/缺/负/bool/不一致/超上界 usage、unknown/超时/取消、重启不自动重发、换 label 延续累计、实际 OS 锁并发、日志失败保留预留、内部第二次发送拒绝、秘密回显不落原文、未选字段/教师字段保护以及原包重放零新增发送。

账本根由 CLI 固定控制状态 namespace 决定，不接受外部 --ledger-root；同授权子目录由 authorizationId 散列决定，不由 scope/output/label 决定。预留在可能发送前持久化；重启 reserved/dispatched/responded 转 unknown 并停止。JSON 损坏、状态/次数/身份/settlement 不一致拒绝，不当空库。scope 经过独立 canonical bytes 冻结，原列表或打开的 ledger scope 引用突变不能移动预算。原15规格固定文件 SHA 与每 case canonical 身份均在发送前核，不让换 --case-specs 篡改原样本。

真实模型边界：executorPresent 仅离线 fixture 加可信宿主 DI 接口；budgetEnforced 是受控 fixture 技术证明。CLI live registry 空，当前绝不支持真实模型发送；未来还须真实授权 provenance、具体模型全部账费/usage 语义证明、可信 host/凭证绑定与无重试原 transport。成本上界/价格/币种/汇率未实现，maxCostCny 拒绝；不猜字符 token 或默认费率。fixture 证明、回环/9 端口和 MockTransport 不能标 live。当前 usage 结算仅支持可核 input/output/一致 total 形状，其他收费维度仍不支持。不能据一份 scope 或上界数字宣称任意模型可直接 live。

原件入口：`cli-fifteen-v1-result/trial-result.json` SHA `da22bf4f83986498c0d9622b7623bbe2892197701526648ecdf65d021c9b487b`。ledger-snapshot、相对 artifact refs、生产12文件与 executor6+原 common.py 源码 SHA 可由 R 独立重算；本卡最终核对 production/executor 与 manifest 均零漂移。typed 接口见 SCHEMA-v1.md。

`FINAL-SHA.json` SHA `4db83dc9d7e3f5e2b566a7cc92fa906d7d12a00b0c446fdcb9364e7e9746764a` 包含8产品SHA、各轮 actual argv/PID/起止/elapsed/exit/日志关闭、原件SHA、边界和guard汇总。最初六个 self-check 的 OS birth 未采，保留原记录且不追溯伪补；这些进程均由当轮实际 process.wait 回收。后续 CLI/回归轮及其119个稳定纯材料子CLI通过自有 Popen 句柄 GetProcessTimes 采实际 OS 出生身份，均实际 wait/reap。

首四作者失败轮、pure material 启动器目录/TEMP 误用首败，以及 prepare 的 R 并行源码漂移失败轮均原样保留，各有解释文件。首轮 Windows asyncio 内部 self-pipe 被 guard 错分为20次禁止网络并拒绝；后续仅按真实 stdlib asyncio 调用栈放行此内部连接并单列计数，普通 Provider/loopback/其他 connect 仍拒绝。没有拼轮或删除首败。

未执行真实模型、真人教师、新原生软件、RAG-REL 验证，原因是缺相应输入和授权。全仓 check/e2e 与独立验收由 ROOT 统一执行，本卡不借 Python 自检关闭原 B6/B7 教师、native 或 RAG-REL 门禁。现 STOP，不继续修改产品或执行作者 QA，等待 ROOT 定稿。
