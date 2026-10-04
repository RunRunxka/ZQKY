# B5-DOC-AUDIT v1 提前静态文档核对

2026-10-03，北京时间。负责人 `/root/g1_doc_audit`；范围由CTRL登记在本目录TASK-CARD.md。结论为 **提前文档核对完成，整体B5独立验收未执行，不构成最终精确文档核准**。G2关闭事实按CURRENT_STATUS；本轮不重验G2，不把B5作者结果、静态65实例或旧构建门禁写成B5已验收。

现场main@6aeb57280f6a7e0d7391cad4d150745479ea58ec由CTRL提供，审计未调用Git。读取根/API/web/lesson四份AGENTS、CURRENT_STATUS、PROJECT_GUIDE、API、ROUTES、教案模块说明、本批原请求、冻结33件契约、公开端口及实际源码。补读本批矩阵、REPORT最新记录、NEXT入口和已有迁移/恢复收据；未导入app.main、执行产品/测试、启动服务或操作浏览器，未访问正式env/业务数据/真实草稿/旧六目录。唯一写入为本新目录的卡、报告与前后SHA；没有保存可执行QA脚本。

## 具体文字修正

以下为观察到的旧文案与源码依据；权威说明均由CTRL修。本报告保留发现和处理事实，不改任何历史失败或收据。

| ID | 观察位置与问题 | 建议/已处理文字 | 源码依据与处理状态 |
| --- | --- | --- | --- |
| B5-DOC-R01 | 根AGENTS第1节把学情驱动AI教案只列后续设计，PROJECT_GUIDE:13也只写后续接入，与实际候选源码及稳定决定§15不一致 | 明确后台教案与固定学情建议已有候选源码，AI只进待教师选择的建议；验收/门禁只看CURRENT_STATUS | main.py:287的真实runtime和LessonPlanService:55的实际executor注册已有装配。CTRL已保全并更新根AGENTS/PROJECT概述；本轮复读的新措辞符合候选/未验边界 |
| B5-DOC-R02 | API:87将DraftEnvelope.updatedAt写为ISO UTC，过窄 | `updatedAt:带时区ISO8601字符串`；新本地稿通常写UTC，显式导入保留合法原时区与字符串拼写 | contracts/lesson_plans.py:95的iso_timestamp接受带时区原字符串且直接return；server-cache.ts:20原包校验，lesson-workspace.test.tsx的+08:00完整导入fixture支持此口径（只读测试源，未执行）。CTRL已修API，复读符合实际契约 |
| B5-DOC-R03 | API:150“后续…排期”、:359“升级留在B5”仍使当前B5候选接口读成未来规划 | 指向文末B5已建立的后台教案/固定学情候选接口，验收与阶段门禁仍只看CURRENT_STATUS | 实际lesson_plans.py十二路由、lesson_sources.py第十三只读来源口、main.py runtime已存在。CTRL已修API两处，复读符合候选状态。旧`/lesson-plans/fill`仍是独立规划口，不能删掉或混成B5 proposals口 |
| B5-DOC-R04 | CURRENT_STATUS:22准备期尾句仍是当前时态“独立审查仍在核共享契约，尚未冻结或派三个模块实现”；虽然后文“随后”及顶部已正确，独立摘读会误认当前仍未冻结 | 将段首标为“B5准备期当时实际结果（以下为历史）”，并将尾句标“当时独立审查仍…”，保留全部当时数据与首败原文事实；当前冻结/实现/门禁事实继续由顶部和后续补记表达 | 冻结33清单status为FROZEN_FOR_MODULE_IMPLEMENTATION；实际0010追加登记、BE/AI实现及公开runtime已有源码。该项为历史时态澄清，未发现当前下一动作的业务顺序错误；留CTRL处理，审计不改权威文件 |

## 已核对的实际边界

| 范围 | 实际依据 | 文档口径核对 |
| --- | --- | --- |
| 12 B5口与第13题选择 | [lesson_plans.py](H:/备份xuexi/智启课源/apps/api/app/api/v1/lesson_plans.py:46)有12个实际装饰器：list/create/import/verify/get/save/history list/history get/generate/get proposal/apply/reject；[lesson_sources.py](H:/备份xuexi/智启课源/apps/api/app/api/v1/lesson_sources.py:17)追加GET confirmed-question-revisions，分页1..200、真实question owner、固定DTO | API文末明确源码/路由/装配已有，不将静态OpenAPI或capability ready当业务验收。verify是只读校验；题选择不改题库或调用模型，后续生成按固定revision重新核查。没有新增审核/归档/服务器教案PDF端点 |
| 默认本地与旧信封 | [EditorContext.tsx](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/model/EditorContext.tsx:21)默认RuleBasedFillProvider；[drafts.ts](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/services/drafts.ts:2)旧键仍zhiqikeyuan:lesson-plan:v1、schemaVersion仍1；[server-cache.ts](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/model/server-cache.ts:7)另存documentId会话，完整旧包和原字节保留 | 模块说明/API/新lesson AGENTS符合v1正文与HTTP外层2分离、显式导入、坏稿暂停和默认规则。后台列表存在不意味着改成默认AI或废弃本地单稿 |
| 真实任务/模型/发布 | [LessonGenerationService](H:/备份xuexi/智启课源/apps/api/app/services/lesson_generation/service.py:98)实际执行生产证据复核、冻结model resolver/指纹、provider.complete、严格输出与候选INSERT；publish交给JobOutcome，由原JobStore成功事务完成。[LessonPlanService](H:/备份xuexi/智启课源/apps/api/app/services/lesson_plans/service.py:55)真实register teaching/lesson_generation，main在RagV2之后注入实际依赖 | 六态/取消/retry沿原JobEngine；失败不回退示例；首次与retry都核原指纹。capability依真实装配与registry，只表示工程可用入口。真实供应商教学质量仍未执行，作者隔离wire链不能替代该结论 |
| 单班固定报告与生产依据 | [preparation.py](H:/备份xuexi/智启课源/apps/api/app/services/lesson_generation/preparation.py:82)要求当前固定base/CAS、ready原run、同学科单班/完整所选KP；模型只取匿名化明确计数和选定教学内容；[RagV2Service](H:/备份xuexi/智启课源/apps/api/app/services/rag_v2/service.py:218)真实scope/immutable原文/hash/坐标核验；[fixed.py](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/fixed.py:34)及[PracticeService](H:/备份xuexi/智启课源/apps/api/app/services/practices/service.py:113)按confirmed/reviewed固定修订读取 | classNameAtSave是当时当前标签；旧报告className缺失保留null，不能补写历史事实。固定题/练习不能按current指针重取旧候选。来源valid不等于教学相关性通过，RAG-REL未关闭。已知身份阻断和最终三协议wire核验不证明能识别全部个人信息 |
| 保存、归属、固定历史 | [LessonPlanService](H:/备份xuexi/智启课源/apps/api/app/services/lesson_plans/service.py:78)同read_transaction先receipt再owned/CAS，最终短事务先复查receipt；contentHash含正文/context/source意义，仅和current去重；[Repository](H:/备份xuexi/智启课源/apps/api/app/repositories/teaching/lesson_plans.py:29)按document+owner+revision读固定记录 | 后台600ms串行、unknown保留首次原操作、旧ACK不倒退新CAS、409保留编辑。历史只读，复制/undo是当前会话新编辑再保存，不能改旧revision。owner由装配注入、HTTP不收owner；未增加账号/多用户鉴权能力，归属检查不宣称完整认证系统 |
| 教师应用 | [apply_proposal](H:/备份xuexi/智启课源/apps/api/app/services/lesson_plans/service.py:250)核receipt/owned pending/base CAS、选whole fields、严格payload与来源，追加新revision/decision/receipt；[validation.py](H:/备份xuexi/智启课源/apps/api/app/services/lesson_generation/validation.py)提供独立校验 | 五个完整AI字段与教师六字段分离；partial终结候选，reject不改正文，旧apply receipt不回退后续版本。ProcessItem v1未加分钟或模型metadata字段 |
| Word/打印来源 | [EditorContext.tsx](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/model/EditorContext.tsx:120)Word复制当前data并带来源；beginPrint复制data/source并锁编辑，Workspace纸面使用printSnapshot；[EditorOverlays.tsx](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/components/EditorOverlays.tsx:131)先固定快照再100ms调用print；[export.ts](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/services/export.ts:53)沿原DOCX和window.print | 保留原非标准A4模板/映射，网页打印标准A4且不能保证同分页；打开打印窗口不等于PDF保存。没有把B4受管双DOCX移植成教案新业务端点；Word/WPS人工分页、真实供应商质量明确not_run |
| 0010与四库 | [teaching.py](H:/备份xuexi/智启课源/apps/api/app/core/migrations/teaching.py:791)只追加0010；[lesson_plans.py](H:/备份xuexi/智启课源/apps/api/app/core/migrations/lesson_plans.py:151)定义同teaching库六表、真FK及不可变/lineage触发器；[lesson_schema_gate.py](H:/备份xuexi/智启课源/apps/api/app/core/lesson_schema_gate.py:24)仅已登记0010才启B5核查，SQL literal/JSON路径不被改大小写；database_gate及backup恢复调用该gate | 仍四库，没有第五库，B0 required入口未追加无版本条件的六表。旧九声明v1/v2保全JSON的完整内容和hash逐项相等；本轮不执行迁移代码。既有CTRL新19迁移/1恢复收据为隔离作者结果，非本轮独立重跑、正式数据迁移或正式Qdrant6333验收 |

当前CURRENT顶部、B5矩阵、REPORT最新18:14记录与NEXT均没有把作者BE45/AI144/FE50或准备中的FE71、QA v3静态65实例当独立通过。CTRL单独稳定绑定410后端文件后完整API轮正在运行且已见失败，最新记录明确待完整结果与归因；FE仍有获授权修复，整批候选未冻结。实际下一动作仍为FE窄修自检和稳定集成/新候选→独立v3→新check/API/build→完整业务浏览器/153/14→资源与精确文档后验；次序符合用户授权，止于B5，不进行Git写/推送/部署。R03～R05本轮只核说明与实际修复源码存在，未给业务关闭结论。

## 保全与结束

[SHA-BEFORE.json](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-doc-audit/SHA-BEFORE.json)于UTC10:06:35捕捉105件；[SHA-AFTER.json](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-doc-audit/SHA-AFTER.json)按同105路径再读。冻结33件前后均0差异，manifest SHA仍8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db。观察期间有9项获授权并发变化：根AGENTS、lesson AGENTS、PROJECT_GUIDE、API、CURRENT_STATUS及DocumentGateway/ProposalPanel/SourcePanel/lesson-workspace.test；前后精确值已记录。CTRL权威文档修复和FE v2私有修复不是审计漂移异常，也不构成稳定候选验收。

旧九保全声明全等仅来自读取原JSON，不扩大为执行当前正式迁移。其他旧QA/历史日志没有审计写入；本轮没有起产品/服务/浏览器，故没有审计自有运行资源待释放。read-only检索中有路径拼写不匹配，经rg定位实际文件后读取；不是产品测试失败或重试通过。本任务写入结束，后续若需最终精确文档核准须由CTRL另卡冻结字节后核验。
