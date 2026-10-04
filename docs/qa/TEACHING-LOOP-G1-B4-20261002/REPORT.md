# G1+B4 本次状态报告（未完成）

2026-10-02，CTRL `/root`。**G1八项已修复并通过独立正确行为验收，冻结候选的check与全量API通过；真实浏览器/E2E因5174前端启动被自动审批拒绝而未执行，整体G1门槛未关闭，B4未开工。当前结果不构成用户要求的G1+B4交付。** 唯一当前状态与下一动作入口仍为[CURRENT_STATUS](../../CURRENT_STATUS.md)。

## 现场、范围与冻结

现场始终为 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`，继承未提交B3-FIX r7与用户文档改动；[开工基线](BASELINE.json)及[初始git状态](initial-git-status.txt)保留。未暂存/提交/推送/切分支/部署，未读取正式.env、凭证、业务库或用户浏览器草稿。旧六临时目录未删除、未重试被拒动作、未作为本批样本。

相对开工现场，本次实际修改13个产品文件及8个测试文件（4个改测、4个新测），共21个：

- 后端7个：JobStore/JobEngine/Registry三文件、tabular.py、题库service.py/fingerprint.py/catalog.py。
- 前端6个：ScoreImportReview、ScorePanel、AssessmentsWorkspace、AssessmentsPanel、RosterPanel、公共RichContentRenderer。
- 测试8个：question_generation、RichContentRenderer、ScoreImportReview、ScorePanel既有测试；新增jobs租约重试、score文本边界、question重复身份、AssessmentsWorkspace测试。

没有修改迁移0001–0007、共享契约/公共客户端/导航/路由/锁文件/模板资产；成绩服务/仓储及question_bank/rich.py保留现行实现，仅所登记测试覆盖。权威说明由CTRL更新API/CURRENT_STATUS/QA索引，不覆盖旧QA报告。

当前[候选g1-r2](CANDIDATE-g1-r2.json)完整826项，覆盖产品/测试/契约/迁移/配置/锁与现行资产。清单文件SHA256：
`9471f43eb5ba9cde9d79ab65b84f5cf1fcd607729b1ad2388d2bfde5c78a072b`。
r1原825项保留，r2仅补安全.env.example覆盖，共同825项字节未变，不冒称行为重跑。[后验](AUDIT-g1-r2.json)826项零漂移，开工登记629份旧证据零漂移。

`apps/web/next-env.d.ts`构建后恢复本次备份原字节，SHA为
`0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`，不是依据猜测重建文件。实现者停写后才分配三位独立V00；他们只写新证据目录，产品停写冻结期间未边验边修。

## 八项正确行为及独立证据

逐项收据和阶段门槛见[G1-CLOSE-MATRIX](G1-CLOSE-MATRIX.md)、[独立索引](INDEPENDENT-RESULTS.md)。原诊断证明缺陷，不计修复通过；以下是新自建正确行为断言。

| 独立任务 | 单次结果 | 关闭的正确行为 |
| --- | --- | --- |
| [JOBS](v00-jobs/RESULT.md) | 52passed，0fail/skip，6.10s，exit0 | R05取得真实SQLite写锁后核时间；无人接管到期、第二连接等锁跨到期、失权与取消零业务/checkpoint/终态。R06真实ASGI retry与cleanup barrier，16种组合，新轮恰好一次、旧tracking不删新轮、取消/错误/重启收敛 |
| [SCORE/QB](v00-score-qb/RESULT.md) | 53passed，0fail/skip，16.15s，exit0 | R04共33项，XLSX/CSV身份/出勤/总分/小题、公式/缓存、超限定位/拒绝零写、精确尾零/有效0/四态及源字节；R07共20项，完整富题面与共同材料区分、真重复/答案冲突、同包/旧题兼容、原包先重放 |
| [FE组件](v00-fe/RESULT.md) | 20passed，0fail，2.35s，exit0 | R01四入口与编辑失效承认、保存后新权威预览/承认、未知原包；R02迟到200/409/422/网络失败/刷新/卸载/Strict保留新编辑；R03已挂载施测合法选择/出勤/人次保留及撤销说明；R08全部delimiter参数/sepChr/空项/复杂子式/安全全文替代 |
| [FE真API组件链](v00-fe/real-api-third.log) | 另一次1passed，2.21s，exit0 | 实际8001 FastAPI请求、真实四库持久化，不制造业务成功响应；名单新增/CSV导入/转班→施测→成绩→保存新分数→实际确认提交后丢响应→相同冻结包重放→恰好一个正式版本 |

真API链是jsdom组件到实际HTTP服务的业务验证，传输适配没有验证物理网络AbortSignal；**不是实际浏览器验收**。原CSV中的甲Q1从2改为1，保存前零确认请求，最终甲为[100,200,500]、总分800；丙为[200,300,500]、1000；丁为[0,300,500]、800。固定施测 `6b855beb49c54c1daf44564939a9abf3` 的正式修订仅 `bbe7c4fadbe74bbc8fce13aa3c3274e9` 一份，完整3人次×3叶=9格。[实际HTTP收据](v00-fe/real-api-receipts.json)、[只读SQL对账](root/closed-data-check.json)保留。

## 工程门禁与首败

| 本次执行 | 单次结果 |
| --- | --- |
| [npm run check](root/g1-check-first.log) | exit0；typecheck、lint零警告、109文件1088单测（81.80s）、build通过 |
| [npm run test:api](root/g1-api-first.log) | exit0；1599passed/1skipped/1既有warning，232.67s；skip是既有规模环境门控，不隐瞒为零跳过 |
| [成绩专项](g1-score/RESULT.md) | 169passed/0fail/skip，45.05s；显式开启200×100，不把它并入全量计数 |
| [题库专项](g1-qb/RESULT.md) | 119passed/0fail，30.31s；旧derived-v1保留，新增surface算法并存，各算法分别断言 |
| [前端实现者专项](g1-fe/RESULT.md) | 103passed；类型与lint通过；不是独立V00计数 |
| [CTRL公共专项](root/jobs-first.log)及[OMML](root/omml-r3.log) | 65passed/17.68s与8passed/1.22s，分别exit0；不重复加总全量测试 |

所有实际命令与退出码见[EVIDENCE-COMMANDS](EVIDENCE-COMMANDS.md)。root路径错误/类型夹具首败、实现者首败、独立夹具前置/转发/断言首败、冻结覆盖遗漏及root收尾预期表两次错误均保留在[ROOT-FIRST-FAILURES](ROOT-FIRST-FAILURES.md)和各RESULT，不删除失败原文或把重复多轮计数拼成单轮全绿。root首次OMML错误没有生成本地日志，原stderr仅工具输出留存，明确标明缺失，不补造记录。

本次事实记录另由独立[D00核对](d00/RESULT.md)：逐文件候选/旧证据、最终XML与命令退出码、API字段、资源观测及未完成边界均与实物一致。D00只核记录，没有重新运行业务，也不替代浏览器/E2E或B4验收。

## 未执行及剩余边界

| 项目 | 本次状态/原因 |
| --- | --- |
| 真实浏览器、三视口像素、键盘、reduced-motion | 未执行。启动已构建5174前端被自动审批拒绝，理由仅`blocked by policy`；准备的浏览器脚本收集1例不等于执行 |
| 全量E2E、受影响聊天浏览器回归 | 未执行。依赖前端服务启动，未用另一命令/工具/Agent绕过拒绝；旧B3-FIX E2E153和浏览器6项只作历史 |
| 模板verify、实际Word/WPS、真实模型/Qdrant、人为教学质量 | 未执行；本次没有修改模板/导出资产或供应商/RAG路径，浏览器门禁仍待闭合 |
| B4契约/DTO/迁移0008+及迁移故障/旧数据测试 | 未开工/未执行；用户要求G1全部必需门槛通过后才进入B4 |
| T70规则事实、不可变报告/证据/备注及200×100分析性能 | 未开工/未执行。成绩规模专项不等于分析规模基线 |
| T80正式题选题/练习审核/富DOCX/成绩模板/施测回流/第二次分析 | 未开工/未执行 |
| F30/F10页面真实操作链、B4独立验收/full gates/含新表备份恢复 | 未开工/未执行 |

畸形XLSX dimension仍是观察项；本次仅顺带封装触及成绩路径的csv.Error，不把观察项冒充第九/十个G1阻塞。正式数据迁移、真实模型教学质量和人工Word/WPS不从旧报告推断。

预读B4现行结构发现：代码尚无已实现的export_artifacts表/服务，API仍将导出列为规划；现有成绩参测快照有classId但没有冻结className。两处在后续B4契约冻结时需根据实际实现明确方案，本次没有增加替代导出服务、读当前班名补历史或提前改共享契约。

## 资源与保全

[资源记录](RESOURCES.json)：完成真API验证后，核本批uvicorn命令、PID4844与8001监听归属，再仅停止该进程；8001/5174均无监听。exec退出1对应显式停止服务，不是产品测试失败，不宣称优雅shutdown。没有启动实际浏览器或5174服务。所有实现者及三位V00已停写；新临时库、原表、HTTP/SQL收据与失败轮样本保留为证据，不清理未知数据。四库只读integrity_check全部ok，完整foreign_key_check零异常。

[硬件记录](root/hardware.json)：i5-14600KF、14核20线程、约32GiB物理内存；仅记录环境，没有B4性能测量。候选SHA、旧证据、next-env原字节及Git现场后验另存，权威说明与产品冻结清单分开核验。授权范围未扩大，本轮仍未完成。
