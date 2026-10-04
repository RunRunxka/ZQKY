# B4-R10 final QA 独立静态补审

结论：**PASS（静态与证据身份绑定）**。`CANDIDATE-b4-r10-final.json` SHA256 `0ff66980996772ac8c991afa94cabe7984e3e99c44c3cf61571056c9e3e2b49b`，878 产品 / 40 QA / 5 契约全量逐文件散列核验 **0 漂移**。产品和契约完整映射与 r9 完全一致；r9 至 r10 只变更两项 QA，无新增、删除。

`b4-v00-practices/probe_support.py` 只在 Scene.question 的新题入库将字面 owner 改为实际 `self.app.state.question_bank_service.owner_id`。修前 SHA `5f3107ec5582fcb0c30adc98e12f21a767cf176222498dfd04760761fd7f9448`、修后 `ad122d8918a2c4fac77c3ccaf51ba0edbd18d95b7b6b203c40e16daf1e63ff63`；单一表达式替换可逐字节还原，23 个 helper assert 的 AST 完全相同。两个独立测试文件及原 runner 精确同于 r9：95＋40＝135 个测试 assert 原形保留，未改原外 owner 手工域、foreign 判定、业务 oracle 或事务/回放断言。原 23 函数/64 参数化案例范围来自保留的准备清单，本轮未 collect 或执行。

`b4-v00-browser/run.py` 仅新增 `sys.stdout.reconfigure(encoding="utf-8")` 与 stderr 同式（及空行）；修前 SHA `af9f103c6080d55b634779661d4bd8a5f1b52173d2288bf15fe88d719c55b779`、修后 `f30ef3002b6ec2e974806ff77b713b6b524d630360b602a44d1c9830915fa6d0`。去除这两条顶层表达式后，原 AST 全部相同；删除新增字节块可精确还原原件。CLI 参数、环境围栏、子进程命令、等待/超时、完整输出/exit/收据和清理行为均未改变；没有吞掉异常、改零退出或减弱业务断言。该改动针对原第三轮外层输出 GBK 编码失败，不将旧外层 exit1 重写为成功。

浏览器 spec 与 seed 仍精确同于 r9（SHA 分别 `66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156` / `f84e424d40dcbc6ed4d03f08116374175072d3b84278fe2a14d6ec713d654ada`），因此先前独立 R08 核验的原 115 直接 matcher、2 个 expect.poll、唯一额外精确 URL 等待，以及 6 个 seed assert 全部保留。历史首敗、晚 GET500 与原第三轮子 exit0/外层 exit1 收据均没有由本审阅覆盖；本补审不重新裁定这些业务事件。

r5 全部 **451 前端文件、32 根级共同输入、2007 构建文件**与实际字节精确同源；BUILD_ID 仍为 `v3NL9Nd4Zve30UcCepg0R`，next-env SHA 与构建身份一致。未构建或操作前端。T70 作者 v1.3 的 14 项源码/自检/QA 脚本与作者、r2、r5、r9、r10 和实际文件逐项一致，4 项独立 A 可执行 QA 与 r2 一致。R09 静态报告保留了 Analysis 装配/教学 owner 不变与 FixedReader/迁移不变的证据，此处不把 Practice 的题库 owner 改为 T70 owner。

CTRL 的真实 `full-api-owner-first` 收据明确绑定 **r9**，outer exit0、完整 log SHA 匹配收据；日志末行为 **1698 passed, 1 skipped, 1 warning in 270.40s**，r9 后审计源码/QA/共享契约/旧证据均无漂移。r10 的 878 产品（包括 apps/api/tests）与 r9 完全相同，可据此按精确同源保留该全 API 证据；这是来源绑定，不宣称 r10 又执行了全 API。

先前独立 A `RESULT-fixed-first.json` 仍是实际 **r2** 的完整 8 场景、165 HTTP、exit0、20k 全证据/100 页结果，原前后审计无漂移；本轮按上述 T70/共同执行路径/A QA 同源绑定，不重标为新 r10 运行，也不重做规模测试。新 owner 夹具的 P 全64与修复 UTF8 后的正式浏览器轮仍须依 CTRL 冻结执行指令给出真实收据。

本轮仅读源、前字节、清单、元数据和既有日志并做 stdlib AST/散列；仅写此 MD/JSON。未导入 app.main、未测试/收集/HTTP、未启动停止服务、未读取实际数据、未改产品或 QA 执行源、未操作 Git。报告已停写。
