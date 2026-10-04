# CTRL 固定来源与运行装配补充卡 v1

2026-10-03；B5-CTRL 唯一写入者CTRL。冻结33件v1原字节保持。此卡补齐实施发现的公开选择依赖，不修改12个冻结教案接口、正文v1或旧题库DTO。

新增只读 GET /api/v1/confirmed-question-revisions?subjectId=<非空1..64>&offset=0&limit=50（1..200）。成功 Page 的 items 每项恰为 questionId/questionRevisionId/subjectId/stemMarkdown；真实题库归属由 question_bank_service.owner_id 注入，分页只选 confirmed current revision，后续生成仍按固定修订读取及重新校验。未知学科可返回真实空集，缺运行依赖503 SERVICE_UNAVAILABLE；非法参数422 INVALID_REQUEST，统一脱敏错误信封。不编造题修订ID、不调用模型、不改变题库行。

归属：CTRL 写 app/contracts/lesson_sources.py、api/v1/lesson_sources.py、services/question_bank/fixed.py 新分页口、web/services/lesson-plan-sources-api.ts、test_b5_runtime_sources.py；F30-L只读该client并在模块内消费。main.py装配生产Rag后的T90服务/registry并注册这条13号补充只读接口；capabilities依实际运行服务+executor报告可用性，仅工程能力，不代表人工教学质量。

薄lesson-plans路由解析 lessonPlanId/revisionId/analysisRunId，重复/空白/超200/没有document的revision显示错误；analysisRunId仅初始化来源。固定ready报告入口携真实runId，由公共导航guard保护，不能自动发AI或假定文档已存在。

作者公开装配新轮 b5-runtime-sources-v3 3/3通过，exit0/2751.3ms、6源0漂移、PID15820已退出、Settings None/隔离TEMP保留。v1为1pass/2fail（测试误用QuestionRecord.id和嵌套error），v2为2pass/1fail（测试误用catalog.read_connection）；完整原源/日志/XML保留；三次均无来源漂移。该轮只核装配/选择，整体独立业务与浏览器尚未执行。
