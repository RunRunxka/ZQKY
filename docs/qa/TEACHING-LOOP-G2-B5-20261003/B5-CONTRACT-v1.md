# B5 共享契约 v1

2026-10-03，前置G2已独立关闭，见ctrl/G2-CLOSED-r4-v1.json。此文件冻结本批范围；实施与验收状态另看CURRENT_STATUS。授权止于B5，无Git写入或部署。

## 内容、大小与身份

Python唯一DTO为apps/api/app/contracts/lesson_plans.py，TS镜像为apps/web/src/contracts/lesson-plans.ts；API transport为services/lesson-plans-api.ts。现有LessonPlanData十一字段与ProcessItem四字段保持，旧model/types兼容re-export，DraftEnvelope仍schemaVersion=1。五个教材证据类型逐字段迁入contracts/rag-v2.ts，旧import入口保留。readable镜像Python既有nullable，TS允许缺省/null；chat校验接受这两种历史缺投影情形，非null仍严格校验，不改变引用原文/坐标语义。

字符串字段上限按JS UTF-16 code units：title/otherTypeText80，stage120，其余旧内容字符串100000，process最多100且id唯一。普通保存/导入允许旧空过程/空正文，不套AI四环节要求。lessonTypes保留原顺序和重复值；不静默去重。无效Unicode显式422。公开完整写请求原始UTF-8字节及canonical typed request均≤2MiB；原旧合法稿可能超过该门槛，超限413/422且原件保留，不宣称所有旧合法稿可导入。

旧envelope严格校验schemaVersion整数1、revision非负JS安全整数、updatedAt合法带时区ISO原字符串、全v1字段及无额外字段；这是导入新增校验。JSON读取失败/空串/错误结构不是missing，暂停覆盖；仅getItem===null代表无旧稿。导入冻结完整原envelope和context，成功不重写/删除旧key。updatedAt不参与command重放hash或来源意义hash，不重建时间/process IDs；first envelope完整保存于固定revision。

document班级/学科创建后固定，owner只由装配注入不接受HTTP字段。editRevision只属于前端，revision为后台CAS，revisionId为固定正文UUID。保存仅source=manual/rule；import_local和ai_applied由服务赋值，不能伪造AI来源。context必填，null代表无固定报告；非空则ready分析ID＋1..50非空唯一KP，原选择顺序保留。freeze context含固定run/score/paper/inputHash/KP修订，classNameInReport缺失保留null/“当时未记录”；classNameAtSave明确为当时当前班标签，不补历史事实。

同包身份(owner,operation,submissionId)；save/apply/reject/generate operation作用域包含document/proposal。command hash排除submissionId与仅import updatedAt；canonical key排序但有序数组不排序。版本contentHash包含v1数据、context、source及来源意义；仅比较current，同意义去重不增CAS/版本。A→B→A建立新的固定版本。成功receipt先返回，不受后来CAS/状态/归档/资产/模型变化影响；异包409 SUBMISSION_CONFLICT。

## 数据库与事务

追加teaching迁移0010，唯一DDL见app/core/migrations/lesson_plans.py；0001～0009声明/散列保持。6个新表：lesson_plans、lesson_plan_revisions、lesson_revision_reviews、lesson_generation_inputs、lesson_ai_proposals、lesson_proposal_decisions。专用候选/输入与终结decision在同一teaching库，原通用ai_proposals及paper流程保持；不用第五库。

班级owner真复合FK；current pointer+CAS→所属revision/owner/version四列DEFERRABLE真FK，初始INSERT也保护版本；baseRevision+baseCAS四列FK；输入/proposal→同owner报告、任务、文档、base revision，proposal与input/job lineage触发器校验。revision/context/source、输入、payload、terminal decision禁止UPDATE/DELETE。accepted_proposal_id唯一且AI新revision必须基于proposal精确base/CAS，DB禁止重复应用；有accepted revision不能写reject decision。proposal首次部分应用即terminal decision，至多一条。review独立表初值unreviewed，本批不提供审核endpoint、不偷偷审核正文，扩展审核只改变独立状态。

G2修复所得读快照规则继续适用：首查receipt与owned/CAS预检在同一read_transaction，或将CAS仅放最终事务；不能early miss后另读新CAS而误报同包409。原命令深拷贝冻结，外部准备在事务/PublicationCoordinator之外。准备失败须重查已提交同包receipt，否则保留原异常。最终coordinator内先重查receipt、只读复核cross-bank active refs，短teaching事务再次receipt/owner/CAS/lineage→immutable append→pointer CAS→receipt。协调锁内不做文件/模型/网络；不宣称跨库原子。

新已注册0010库按版本检查6表/索引/触发器/FK，不能将新表加进B0 REQUIRED_TABLES拒绝合法B4库。离线备份仍4库整库与受管资产，恢复体检复用。新库/B4有数据/故障回滚重跑/FK与资产hash须实际验。

## HTTP与错误

完整schemas/成功及失败样例见B5-OPENAPI-v2.json和ctrl/B5-WIRE-EXAMPLES-v2.json（静态契约，不是已实现成功；v1准备期原件保留）。所有写入submissionId1..128；CAS正安全整数。path ID opaque；list offset≥0/limit1..200，默认0/50。列表只返回Summary，单固定revision GET返回完整正文，避免列表重复传大正文。

| 方法/路径（/api/v1） | 请求 | 成功DTO/状态 |
| --- | --- | --- |
| GET /lesson-plans | subjectId/classId/offset/limit可选 | Page<LessonSummary> /200 |
| POST /lesson-plans | LessonCreateRequest | LessonView /201 |
| POST /lesson-plans/import-local | LessonImportRequest | LessonView /201 |
| GET /lesson-plans/{id} | 无 | LessonView /200 |
| PATCH /lesson-plans/{id}/draft | LessonSaveRequest | LessonView /200 |
| GET /lesson-plans/{id}/revisions | offset/limit | Page<LessonRevisionSummary> /200 |
| GET /lesson-plans/{id}/revisions/{revisionId} | 无 | LessonRevisionView /200 |
| POST /lesson-plans/evidence/verify | LessonEvidenceRequest | LessonEvidenceView /200（只读，无submission） |
| POST /lesson-plans/{id}/proposals | LessonGenerateRequest | LessonGenerationReceipt /202 |
| GET /lesson-plans/{id}/proposals/{proposalId} | 无 | LessonProposalView /200 |
| POST /lesson-plans/{id}/proposals/{proposalId}/apply | LessonApplyRequest | LessonView /200 |
| POST /lesson-plans/{id}/proposals/{proposalId}/reject | LessonRejectRequest | LessonProposalView /200 |

统一ApiErrorEnvelope：code/message/requestId/retryable/details。404 NOT_FOUND不区分不存在或其他owner。409 REVISION_CONFLICT带details.currentRevision和fields；409 SUBMISSION_CONFLICT/LESSON_PROPOSAL_STALE/LESSON_PROPOSAL_TERMINATED/RAG_SCOPE_CHANGED；422 VALIDATION_ERROR或LESSON_INVALID/LESSON_PROPOSAL_INVALID/LESSON_PERSONAL_INFO/LESSON_INPUT_BUDGET带定位issues；413 LESSON_REQUEST_TOO_LARGE；503 SERVICE_UNAVAILABLE。底层RAG/模型错误原稳定码保留。未知资料/未装配不假200；job失败进入原六态error，不当生成完成。

## 生成输入与执行器端口（实现者不得另改）

T90-BE提供 `LessonPlanService(catalog, *, analysis_reader, knowledge_catalog, coordinator, job_engine, generation_service, evidence_reader, owner_id="local")`。公开方法为list_lessons(subject_id=None,class_id=None,offset=0,limit=50)、create_lesson(body)、import_local(body)、get_lesson(id)、save_draft(id,body)、list_revisions(id,offset=0,limit=50)、get_revision(id,revision_id)、verify_evidence(body)、async generate_proposal(id,body)、get_proposal(id,proposal_id)、async apply_proposal(id,proposal_id,body)、reject_proposal(id,proposal_id,body)。响应DTO或同形dict均可，route用冻结response_model；重活prepare/apply证据核验放bounded thread。服务state名lesson_plan_service；AI为lesson_generation_service。真实executor注册为LessonPlanService.register_job_executors(registry)，不能提供只挂名executor。

T90-AI提供 `LessonGenerationService(catalog, *, analysis_reader, knowledge_catalog, evidence_reader, fixed_question_reader, practice_reader, model_resolver, frozen_model_resolver, question_owner_id)`。

- `prepare(body:LessonGenerateRequest, *, lesson:LessonView, owner_id:str) -> PreparedGeneration` 同步外部准备，无写锁/网络模型调用；服务通过bounded thread调用。
- PreparedGeneration frozen dataclass：`frozen_input:dict`, `model_snapshot:dict`, `context_snapshot:dict`；deep JSON快照。frozen_input顶层至少contractVersion1/lessonPlanId/ownerId/subjectId/classId/baseRevisionId/baseServerRevision/analysisRunId/full source/anonymous modelPayload；inputHash=canonical_hash(frozen_input)，无自身hash字段。model_snapshot只profileId/fingerprint。
- `insert_input_in(conn, *, job, prepared, owner_id) -> str` 仅SQL，新input_id，与job的input_hash/model_snapshot一致；BE在其create-command transaction调用。列名按0010DDL，job kind=lesson_generation。
- `executor_for(record)` 返回既有async executor；或 `execute(FrozenJob,JobContext)->JobOutcome`。真实register归BE服务 `register_job_executors(registry)`，factory委托AI，uses_model=True。executor用原FrozenJob.input/hash/modelSnapshot，首轮及retry均frozen_model_resolver核指纹，I/O/计算在事务外；JobOutcome.publish(conn)由AI写候选，与JobStore.complete succeeded同事务，不另调完成状态。
- `validate_for_apply(payload:dict, frozen_input:dict) -> dict` 纯函数，重新验证保存的patch/budget/evidence/field结构；返回规范化payload。BE应用只调用此口，再做已准备refs的只读复核；AI不写BE保存/应用事务文件。
- `revalidate_prepared_refs(frozen_input:dict) -> None` 仅跨库SQL状态/归属/修订核查，锁内可调用；RAG原文重建需另在锁外prepare/apply阶段，绝不在此读Blob或模型。BE先receipt再外部evidence完整复验，最后本口SQL复验；同包replay优先于失效refs。
- AI publication payload固定 `{patch,budget,evidence,generationSource}`（对应DTO四对象），proposalId UUID生成于executor返回结果前；result=`{lessonPlanId,proposalId}`。publish按jobId查唯一input，INSERT lesson_ai_proposals且lineage列精确相同；不修改正文。

CTRL公共真实证据口：RagV2Service.prepare_selected_evidence(selection,slices)->LessonEvidenceView，resolve_scope→ImmutableSource verified text→derived evidence_id/ref→verify_scope/rebuild_evidence_refs；`verify_selected_evidence(scopeSnapshot,evidenceRefs)->list[TextbookEvidence]`复用生产verify/rebuild。始终1..6、单段≤6000/总≤16000、scope subject与教案同学科、正文区/当前ready范围/归属/hash/坐标核验。不用旧rag_engine或手输段落伪造证据。RAG-REL仍为已有待验质量边界。

practice_reader=`PracticeService.read_reviewed_revision(revision_id,owner_id=...)`，返回该固定已reviewed版本，不读current重新准备资产。question_owner显式注入真实question service owner（当前local-user），teaching owner当前local；FixedQuestionReader读取confirmed固定题，新生成另核archived状态，旧receipt不重核。

固定ready报告公开读取，必须显式单班，选KP只属于其固定报告，与doc班级/学科匹配；不能发active成绩/当前名单或重算掌握概率。classes只选目标class/KP的计数白名单，不用全报告selectionSnapshot作单班总数。内部冻结来源身份，但模型仅opaque KP/evidence/process别名、匿名汇总、必要文本。报告participants/students/备注绝不入modelPayload。对旧正文/需求/所有入模text阻断该报告已知姓名、学号、student/participant IDs以及明确身份标记；最终三协议序列化请求探针核查。可验证已知来源阻断不等同全信息匿名；界面明确需求不填学生个人信息，不隐藏适用边界。

输入固定选定doc/baseCAS、报告/score/paper/KP修订、要求、5..180分钟、模型profile/fingerprint、生产教材证据和0..20已confirmed固定题、0..5已reviewed固定练习。有序数组唯一且保序。模型输入明确预算（≤128000 UTF-16 units/≤256KiB UTF-8）、输出JSON≤256KiB、tokens≤min(handle.max_output_tokens,16384)；超限可见失败，不静默截断、默认模型或示例回退。

## 候选与应用

只允许whole field coreCompetencies/keyPoints/teachingDesign/process/exercises；teacher六字段不进入patch。process必需4..12，metadata一一对应稳定id，至少introduction/exploration/practice/conclusion各一；integer minutes1..180，精确合计duration，KP/evidence aliases只能冻结允许集且每selected KP被覆盖。activity/check必需非空。分钟/依据/KP/check在metadata，不进入原ProcessItem。

模型process id仅用准备的opaque P1..Pn或new:N1..N12；AI规范化回原安全id或inputHash+alias确定性新id，拒绝重复/未知alias，不发可能含人名的旧id。未知key、path/index patch、null字符串、非法分钟/假引用/少环节/超长/截断全部422/visible failed。Candidate nullable未建议的字符串字段不可选；process为完整字段。

apply首查receipt，owned pending同baseRevision+expectedCAS，selectedFields1..5唯一且存在，纯validator重新校验candidate；外部原文核验在锁外，tx再核receipt/owner/CAS/decision/准备refs。只合并选定whole fields，保留所有未选及title/totalLessons/currentLessonNo/lessonTypes/otherTypeText/reflection；新revision+pointer+terminal decision+receipt同事务，注入故障全部回滚。partial终结该候选；reject同包幂等且不改正文，stale也可明确reject。旧apply receipt不回退后续版本；undo为新local edit/新保存revision，历史不改。

## F30 会话与交互

保留默认本地模式、旧writer600ms/serial/失败/坏稿保护、规则警告与确认、undo/redo、JSON/Word/打印。服务器模式使用独立controller/每doc缓存 `zhiqikeyuan:lesson-plan:server-session:v1:{encodedId}`，旧键不共写。缓存须在HTTP前持久化original frozen op+context/load/edit identity，读写失败保留可见错误并停写；pending可继续输入，unknown原包重试不重新取代次或CAS，迟到只记原docreceipt，ACK仅确认original edits，较高server baseline不倒退。StrictMode不自动重放未知写；409停自动写，显式查看差异再选择恢复，不自动读新CAS偷覆盖。

create/import/save/generate/apply/reject各自冻结原op；生成前flush与source选择一致的当前稿，再冻结本地editRevision及model/source上下文。任何编辑/undo/换doc/model/source使建议stale；旧候选迟到不取代新上下文。apply成功用一次store.replace保留应用前undo；不hydrate清历史。history固定正文只读，回编辑显式基于最新current CAS复制成新dirty，不把history版本当CAS。

复用G2公共registerNavigationGuard，切doc/history/本地模式/公开route/Back先取消、保存成功离开、keep恢复离开或明确discard；pending/unknown不可丢弃，失败留当前稿。WorkspaceShell原beforeNavigate不得在guard之后另触发未知新保存。

preview/Word/JSON/print标签与实际data同一冻结快照：本地编辑rN；后台固定vN+revisionId；未保存编辑rN基于vN；冲突稿；历史固定vN。延迟print也固定data/source，不让后续编辑改变打印正文；打开print仅称“打印窗口已打开”。旧模板及中文/全部字段/长正文/二次备课/符号/公式须回归。真实Word/WPS人工排版、真实供应商教学质量/Qdrant/正式迁移另列not_run，不冒充技术PASS。

## 界面方向与验收

对象为教师：页面工作是从固定报告得到可核查建议，并自主选字段进入已有教案。沿现有token：纸面#fff、工作面#f7f7f7、字#0d0d0d、分隔#e5e5e5、品牌蓝#2563eb、浅蓝#eff5ff；字体只--font-ui/--font-display/--font-document。签名为真实来源链“固定学情 → 当前教案版本 → 调整建议”，每个标识可核；不增装饰统计卡/新动画。

布局沿原“配置/编辑/纸面预览”：必要文档/来源/差异面板分段可折叠，桌面差异当前/建议两列，手机上下堆叠。计划复核后舍弃始终占宽的第三新侧栏，以免挤压原A4预览；把来源链集中在模式/版本条，只用一处蓝色强调。实际390×844/1024×768/1440×900（1920按适用），键盘focus/对话框/低动效/错误保留须截图审阅。

独立V00须覆盖保存/导入/幂等并发/owner/真FK/immutable/unknown新编辑/旧ACK/dual-tab/conflict/cache故障；三协议真实wire/PII/timeout/cancel/restartretry/lostlease/fingerprint/publish rollback/invalid patch/refs/budget/stale/partial/reject；真实4库完整浏览器从固定成绩/ready报告到后台教案/来源/隔离AI/选择apply/history/undo另存/Word与print，原成绩/报告/练习不改；旧本地全链与迁移/备份恢复实验。最后完整check/API、新build后全153/14适用门禁、所有首败、资源退出/源契约构建历史next-env/文档audit。不能模块存在即完成。
