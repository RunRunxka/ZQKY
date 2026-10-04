# B5 实施卡 v1（冻结清单批准后生效）

2026-10-03；main@6aeb57280f6a7e0d7391cad4d150745479ea58ec。G2实际关闭见ctrl/G2-CLOSED-r4-v1.json；B5开工保全见ctrl/B5-BASELINE-v1.json。依赖B5-CONTRACT-v1与CTRL最终B5-CONTRACT-FROZEN-v1.json；没有清单不得开始模块写入。最多CTRL+3；独立V00不得参与实现。下面卡只授予指定文件，发现公共缺陷先发消息由CTRL修复。

| ID/负责人/起点 | 可写范围 | 成功与失败示例/验收 |
| --- | --- | --- |
| B5-CTRL v1/CTRL/共享基础最终清单 | main.py；共享Python/TS DTO、RAG类型迁移、lesson-plans-api.ts、迁移DDL及登记；core/sqlite.py提交异常回滚及新test_sqlite_commit_rollback.py；database_gate.py与公共backup；RagV2Service两个生产selected-evidence口与PracticeService只读reviewed端口；app/lesson-plans路由、learning-analysis报告→教案入口；公共件必要修复及专属新测试；权威文档/批工具/候选 | 0001～0009声明hash不变；四库0010体检/备份恢复真实实验；真实装配/公开retry；当前用户前端归属核实，自有服务管理；完成独立与整体门禁，不以模块存在关闭 |
| T90-BE v1/g2_be/上述冻结清单 | 新apps/api/app/repositories/teaching/lesson_plans.py；新apps/api/app/services/lesson_plans/包；新app/api/v1/lesson_plans.py；新tests/lesson_plans_support.py/test_lesson_plans_*.py；本批b5-be/ | create/import/save/list/history/owner/CAS/同包重放/并发receipt一次；相同意义去重与A→B→A；固定context/来源不可改；三种外部准备错误之后再查receipt；generate事务Job+input+receipt、apply的immutable revision+pointer+decision+receipt全回滚；不写AI模块/公共件/旧QA |
| T90-AI v1/新agent/上述冻结清单 | 新apps/api/app/services/lesson_generation/包；新tests/lesson_generation_support.py/test_lesson_generation_*.py；本批b5-ai/ | 同固定报告单班KPs/真实RagV2/confirmed固定题/reviewed固定练习；三协议真实wire无已知PII；预算与四阶段分钟/alias完整validator；fingerprint/timeout/cancel/heartbeat/restart显式retry/lostlease/publish失败；不写BE保存/apply文件或JobEngine/Registry/coordinator/main/contracts/DDL |
| F30-L v1/g2_fe/上述冻结清单 | features/lesson-plan/下业务与私有测试（model/types.ts除外），含其styles/lesson-plan.css/lesson-visual.css/print.css及必要本模块新style；本批b5-fe/ | 现有本地编辑/规则/600ms/坏稿/undo/JSONWordprint保持；后台独立session缓存原包/原代次；pending输入、unknown深等重发、较高baseline晚ACK、409停写/手工差异、切doc/history/route/Back/StrictMode恢复；fixed source选择与新六态任务/五字段diff选择一次apply/reject；source标签冻结与实际导出一致；不写共享DTO/client/navigationguard/shell/rootroutes/learning-analysis入口/旧QA |

共用方法和构造签名以B5-CONTRACT为准。F30-L工作区props冻结为 `initialLessonPlanId?:string; initialRevisionId?:string; initialAnalysisRunId?:string; initialRouteError?:string`，CTRL薄路由负责解析重复/空query并以可见error传入。analysisRunId只初始化来源，不自动调用AI。根report入口只带analysisRunId，不假定后台文档已存在。F30-L可以在模块内再拆文件，保持包级唯一写入；跨模块资产/数据完整性由CTRL和独立V00另验。

环境：任何app.main间接导入之前新OS TEMP→ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8；Settings.credentials_file=None、空隔离教材、16333 Qdrant/9 embedding、无收费模型、ZQKY_KEEP_TEST_DATA=1。正式.env/.local-data/真实草稿/凭证绝不读。Node24固定路径，NODE_OPTIONS=--no-experimental-webstorage。Agent不得起停5174或自建共享服务，测试独立TEMP/新输出label，完成关闭连接并保留样本；不删旧拒删根。任何首败原stdout/输入/trace必须保留，修复后新label不覆盖。

每卡结果：ID/version/实际manifest SHA、写入范围与source SHA、命令/env/PID/exit/单轮passed/failed/skipped/耗时、首败归因与保全、资源/样本、未执行与原因、公共依赖缺口、停止写入时点。实现者只标“待独立验收”。CTRL集成稳定停写后另发未参与实现的V00卡和候选，验期间不改产品/原断言/预算。新候选记录revisionHistory，权威文档单独登记；不Git写入/推送/部署，止于B5。
