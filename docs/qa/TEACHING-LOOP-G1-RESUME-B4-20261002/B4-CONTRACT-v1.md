# B4-CONTRACT v1 · CTRL 冻结交接

G1 已关闭；本批 B4 包含 T70/T80 与两实际页面，止于 B4。起点见 b4-root/BASELINE.json（826 源、1150 受保护证据，main@6aeb572…）。Python app/contracts/b4.py 与 TS contracts/b4.ts 是逐字段权威；不再持第二份 DTO。内部 snake_case、外部 camelCase。下面所有响应模型必须全字段输出（nullable 字段输出 null），请求默认字段可省略。

## HTTP / 提交身份

统一 Page<T>={items,total,offset,limit}，offset≥0、1≤limit≤200。不存在/不属于 owner 404；服务缺失503；数据损坏500，禁止失败降为空成功。409 使用统一错误信封并 details.currentRevision/fields/冲突身份，422 details.issues=[{field,row?,column?,code,message}]；原包重放先于当前活动/CAS/IO检查。操作 scope 下列逐对象身份；canonical 请求身份不含 submissionId，不含当前名称/active/时钟；集合排序但不得默默去重非法重复。完整固定事实另外构成 inputHash。

| 方法/路径（统一 /api/v1） | 请求 → 成功模型/状态 | operation scope |
|---|---|---|
| POST /assessments/{id}/analysis-runs | AnalysisCreateRequest → AnalysisReceipt 202 | analysis.create:{assessmentId} |
| GET /analysis-runs | assessmentId?/scoreRevisionId?/offset/limit → Page<AnalysisRunView> 200 | 只读 |
| GET /analysis-runs/{id} | → AnalysisRunView 200 | 只读 |
| GET /analysis-runs/{id}/classes,students,evidence | classId?/participantId?/knowledgePointId?/offset/limit → 对应 Page 200 | ready 否则409 REPORT_NOT_READY；filter必须属于该报告 |
| POST/GET /analysis-runs/{id}/notes | NoteRequest → NoteView 201；GET Page<NoteView> | analysis.note:{runId} |
| POST/GET /practice-sets | PracticeCreateRequest → PracticeSetView 201；GET analysisRunId?/offset/limit Page<PracticeSetView> | practice.create |
| GET /practice-sets/{id} | → PracticeSetView 200 | 只读 |
| GET /practice-sets/{id}/revisions/{rid} | → PracticeRevisionView 200 | 固定归属 |
| POST /practice-sets/{id}/suggestions | PracticeSuggestionsRequest → PracticeSuggestions 200 | 不修改草稿 |
| PATCH /practice-sets/{id}/draft | PracticeDraftPatch → PracticeSetView 200 | expectedRevision CAS |
| POST /practice-sets/{id}/review | PracticeReviewRequest → PracticeSetView 200 | practice.review:{setId} |
| POST /practice-sets/{id}/revisions | PracticeRevisionRequest → PracticeSetView 201 | practice.revision:{setId} |
| POST /practice-sets/{id}/revisions/{rid}/exports | ExportRequest → ExportReceipt 202 | practice.export:{revisionId} |
| GET /practice-sets/{id}/revisions/{rid}/exports | → Page<ExportArtifact> 200 | 成功固定产物历史 |
| GET /practice-sets/{id}/revisions/{rid}/assets/{sha} | → 图片字节，核本修订声明/owner | 只读 |
| GET /export-artifacts/{id} /download | → ExportArtifact 200 / 真实字节200 | CTRL共享下载，核owner/hash/大小 |
| POST /practice-sets/{id}/revisions/{rid}/assessments | PracticeConversionRequest → PracticeConversionReceipt 201 | practice.assessment:{revisionId} |

### 完整样例绑定

请求分析：`{"submissionId":"s1","scoreRevisionId":"sr1","selectedParticipantIds":["pa","pb"],"ruleCode":"any_loss_v1"}`。202 必须含 `runId,inputHash,scoreRevisionId,paperRevisionId,job,replayed,reused`，job 完整形状 `{"jobId":"j1","domain":"teaching","kind":"analysis","attempt":0,"state":"queued","result":null,"error":null}`。第一次 replayed=false/reused=false；同原包回原收据身份 replayed=true；新submission相同固定inputHash回同run reused=true，失败终态也不偷创建，走公共 retry。GET job 可反映当前六态，保存回执不能被active替换。

班级事实完整：`{"classId":"c1","className":null,"classNameNote":"该成绩未记录班名","knowledgePoint":{"knowledgePointId":"k1","knowledgeRevisionId":"kr1","name":"固定名称","role":"primary"},"selectedCount":4,"validCount":3,"needsCount":2,"incompleteCount":1,"noEvidenceCount":1,"fullCreditCount":1,"numerator":2,"denominator":3,"ratio":0.6666666666666666}`。incompleteCount 是 informationIncomplete 人数（与needs可重叠），不等同 observation=incomplete 人数。

完整409：`{"code":"REVISION_CONFLICT","message":"草稿已更新，请核对后重试。","requestId":"req-1","retryable":false,"details":{"currentRevision":3,"fields":["expectedRevision"]}}`。完整422：`{"code":"ANALYSIS_SELECTION_INVALID","message":"同学生只能选择一个人次。","requestId":"req-2","retryable":false,"details":{"issues":[{"field":"selectedParticipantIds[1]","code":"DUPLICATE_STUDENT_ATTEMPT","message":"同学生只能选择一个人次。","row":1}]}}`。404/500/503/任务error同统一信封；实际requestId由middleware生成，不固定样例值。更多完整成功样例由本卡附属 b4-root/contract-examples.json 按模型导出登记，不能用伪结果代验收。

## 事实、结构与导出

AnalysisRunView.participants 是**本次明确选择**；SelectionSnapshot 记录四态计数。原成绩所有可选人次由现行固定 GET score revision 获取。历史className始终null，classId分组；不新增猜测班名。每participant×leaf一条主体证据（多KP列表），全题含无失分/非recorded；normalized item 快照保存完整content/material/source/assets，分页合成 EvidenceRow。成绩/原卷/确认KP修订和名称为权威，任何读取/矩阵缺格损坏500。

练习目标必须来自ready报告。constraints 默认不含unknown难度、排原题、查重，空 questionTypes/difficulties 表示该维度不限制；unknown难度必须 includeUnknownDifficulty=true才入选。建议不改变草稿，稳定按未覆盖目标数降序→约束匹配→questionId/revisionId，多KP占一个候选。PracticeDraftItem.maxScore为整题满分十进制文本，必须等于节点计分叶合计；selectedKnowledgePointIds非空且正式links子集。itemStructure.nodes 使用本 selection 唯一 nodeKey/parentNodeKey、显式题号/局部ordinal、仅叶 isScored/maxScore>0；sourceBlockIds显式从该固定题富stem/options分配，复合题叶不能凭空。简单单叶可以sourceBlockIds包含全部题面块。顶层itemKey/ordinal唯一，节点扁平化后服务决定唯一总ordinal/题号映射，保留nodeKey和sourceLocator。审核存固定RichContentV2/正式KP快照/来源/答案状态/选题依据，当前题改名不影响旧版；新审核仍必须活动题与活动KP。

score_template **必须给已由此practiceRevision转换的assessmentId**；接受 export 的同事务冻结该时点实际T30参测名单及固定paper/leaf映射，包含nameSnapshot/studentNoSnapshot/attendance/attempt/participantId。之后名单修改不变旧模板或原提交身份。DOCX禁止assessmentId。XLSX学号/姓名为文本（含前导0、公式样貌名字），分数留空；模板meta工作表保存固定IDs/映射/冻结时间。DOCX复用T10，整份共同材料依内容身份只输出一次，所有学生ZIP部件无teacher区泄漏，缺答案教师版明确“未提供答案”。Job.result 成功结构固定 `{"exportId":...,"artifactId":...,"practiceRevisionId":...,"variant":...,"assessmentId":null|string}`；不能202即给成功链接。

## DDL / 单一发布端口

CTRL独占 core/migrations/b4.py + teaching.py；精确SQL以 b4.py 的 TABLES/TRIGGERS/paper_rebuild 为准。本卡v1登记0008新增analysis/practice/export表→0009受检重建paper_revisions，0001～0007声明不改。B5字段/表全部省略。同库复合FK、owner/来源/ready/reviewed闸门及sealed子表INSERT/UPDATE/DELETE拒绝，跨库question/KP只固定服务校验。

公共新增端口：JobStore.create_in(conn,*,kind,frozen_input,model_snapshot?,owner_id='local',job_id?)→JobRecord，调用方同teaching事务，create复用该端口；registry注册 teaching/analysis、teaching/export，uses_model=False，公共retry走同冻结executor，不自动另起任务。现 JobOutcome.publish(conn) 与任务终态原lease CAS同事务；锁外计算/IO，不在SQL持锁后反拿coordinator。

AnalysisService(catalog,*,job_engine,asset_store,owner_id='local')，register_job_executors(registry)。T80公开 `analysis_service.read_ready_report(run_id,owner_id='local')->dict`：完整 AnalysisRunView by_alias + `originalQuestionRevisionIds:list[str]` 固定原卷所有题revision，供排原题；禁止读取T70私有表实现二次规则。T70 evidence lineage从practice_paper_item_mappings按fixed paper/item读真实复合归属，文件卷null。

FixedQuestionReader(question_catalog).read_revision(question_revision_id,*,owner_id='local')->FixedQuestionSnapshot：字段见 services/question_bank/fixed.py；.list_confirmed(subject_id,owner_id) 只用于新建议的当前正式题，read_revision永不跟current。publication内再调用read_revision并核status与content_hash+KP修订学科活动，题archive共用coordinator。QuestionBankService.read_asset(asset_id) 提供只读兼容QB blob；T80锁外核全asset/hash并用现AssetStore.store_original规范到managed，保存rich映射，不新造store。

AssessmentService.create_in(conn,payload:AssessmentCreateRequest)->完整 AssessmentCreateResult by_alias dict，不自开事务/不登记提交，ConfirmedPaperReaderAdapter.read_in复用同conn全部确认闸门。T80负责 conversion业务：同execute_command conn创建paper draft→items/KP→confirmed→mapping→T30 create_in→conversion/映射回执，一错全回滚；不要串调用会commit的公共create。

PracticeService(catalog,*,analysis_reader,fixed_question_reader,knowledge_catalog,coordinator,assets,question_asset_reader,job_engine,file_assets,assessment_service,owner_id='local')，register_job_executors(registry)。question_asset_reader为callable(str)->(bytes,mediaType)，analysis_reader为AnalysisService；main在注册registry之前装配。下载共享 ExportArtifactsService(catalog,*,assets,file_assets,owner_id='local') 由CTRL装配，不新注册任务。

## 前端与写入归属

CTRL独占 shared contracts/b4.ts、services/teaching-loop-b4-api.ts，props服务的默认完整实现出口 `b4Api`（函数与Python路由同语义），每函数最后optional AbortSignal，失败抛既有ApiError。thin page server await searchParams；learning-analysis props initialAssessmentId/initialScoreRevisionId/initialRunId；practices props initialPracticeSetId/initialPracticeRevisionId/initialAnalysisRunId；F20 props initialAssessmentId + initialStep='score'|'history'。未知/重复参数明确错误不猜active。前端可直接复用 assessments/hooks.ts 中useFrozenSubmission/useAsyncResource，不复制；公共Rich renderer/hook原样。

题库补题手动 link `/question-bank?returnPracticeSetId=<id>#generation`（不包含学生数据），CTRL补最小返回入口/显式 generation initial 参数，不自动发模型请求或自动把候选入练习。公共壳roots、导航与HistoryPanel固定分析Link均CTRL负责。

正式作者卡分别 v1 T70、T80、F；文件同一时段一个writer。全部ready停写才能独立复核。v1共享端口问题由作者报CTRL，禁止自己改共享契约。最终单轮check/API/build后E2E、带新表资产备份恢复、独立literal oracle/故障/浏览器全回流；任何未执行如实记录，不把设计当实现。
