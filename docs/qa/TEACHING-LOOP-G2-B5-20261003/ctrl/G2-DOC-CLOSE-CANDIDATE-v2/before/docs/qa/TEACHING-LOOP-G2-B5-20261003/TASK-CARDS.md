# 本批任务卡 v1.0

起点：main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；开工全部r21分组实核零漂移。最多CTRL+3，所有共享公共件/契约/权威文档/Git由CTRL独占。G2关闭前不编码B5。

| ID / 负责人 | 依赖与可写范围 | 成功/失败示例与验收 |
| --- | --- | --- |
| G2-CTRL v1 / CTRL | 先读本地Next资料；b4.py/b4.ts、assessments/hooks.ts及其专属测试、navigation-guard.tsx及测试、WorkspaceShell.tsx、app/layout.tsx、公共client与新批工具/权威docs | metadata首次冻结且unknown复用，兼容旧submit；所有离开路径/迟到ACK不回退；原公共回归不能丢失 |
| G2-BE v1 / g2_be | G2契约v1；services/practices/service.py、apps/api/tests/practices_support.py、apps/api/tests/test_practices*.py、新test_practices_draft_replay.py与本批g2-be/ | 真API原包receipt一次写；并发/异包/新旧CAS/owner/后续另存/资产失效/receipt失败回滚；不得改共享contract/repo/迁移/main/公共提交组件/旧QA |
| G2-FE v1 / g2_fe | G2契约v1及CTRL公共接口；features/practices/内编辑/工作区/新增session/相关测试与styles/practices.css，learning-analysis/LearningAnalysisWorkspace.tsx备注段及相关测试；本批g2-fe/ | 2→3/A→B首200和unknown重放留新输入，旧ACK不降基线；dirty全部离开/恢复/StrictMode；不得写公共hook/client/contract/shell/导航/权威docs/旧QA |
| G2-V00 v1 / g2_oracle | 实现者停写+CTRL稳定候选后才执行；当前只准备本批g2-v00/独立测试与配置，已允许写准备源但不得跑业务 | 手写oracle，不调生产merge/hash作预期；三个原反例正确行为、扩展矩阵和真API丢响应浏览器；失败原件保留，不改被审代码或放宽原门禁 |

所有Python命令在app.main导入前显式新系统临时根/ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8，Settings.credentials_file=None；模型教材隔离替身，16333测试Qdrant且不默认连接，正式env/data/草稿禁止。服务由CTRL核归属与构建管理，Agent不得自主起停前端；测试由各卡约定的新label/输出/收据记录。

结果格式：ID/版本/实际candidate与source SHA/改动文件/自检command+env+PID+exit+单轮计数+耗时/首败/资源/未执行原因/只标待独立验收。任何公共缺陷先报CTRL接管；同文件只一个写入者。候选冻结后停写，变动追加revisionHistory和新候选。B5角色与DDL/API另在G2关闭后冻结，不提前派实现。

## r2 首败后的修复卡

| ID / 负责人 | 实际起点与唯一可写范围 | 验收与禁区 |
| --- | --- | --- |
| G2-BE v2 / g2_be | r2 SHAaaa4868a51ff9d9ce12f45bc08bd3084832029a4ca7f2bab5ca789b78b7c9fa8；仅private practices/service.py、新test_practices_draft_replay.py及g2-be/v2/ | 同一teaching snapshot先receipt后owner/CAS/state；资产计算在事务与publication锁外，准备错误后再次读已提交同包receipt；确定性early-miss→commit及真实HTTP双200/一次写，原72例保留。修前原字节/应红与修后新label分开，完成后停写；不改公共件/独立QA/旧证据、不起停服务 |
| G2-V00 QA v5 / g2_oracle | 保存r2完整首败RESULT-v2；仅explicit-discard unit等待真实A身份与完整字段，新增manifest/delta | 保留原23组件/11API/8浏览器、全部原断言与预算；不改并发双200oracle，不重跑；等待BE停写和CTRL新候选 |
| G2-FE-READ v2 / g2_fe | 仅读g2-v00浏览器与CTRL视口脚本、产品labels/状态，消息报告 | 实现者预审仅用于指出QA缺口，不计独立验收；不写产品或QA、不执行测试/浏览器、不起停服务 |
| G2-V00 QA v6 / g2_oracle | 仅unknown重试两例等待页面精确成功notice，原browser bytes先保全，新manifest/delta | 发包长度不足以证明页面ACK处理；两成功notice后才判断3/B保留。v6已停写、未运行，原8例和预算保持 |
| G2-V00 QA v7 / g2_oracle | 保持v6原件；仅native Back两例加强只读hydration/history stamp前置，新增manifest/delta | 真Next Link前等__NA与有效navigationPosition，点击后目标position不同；禁止写history/替换Link/back，原全部行为断言/8例/预算保持。完成后停写等新候选，非独立通过 |
