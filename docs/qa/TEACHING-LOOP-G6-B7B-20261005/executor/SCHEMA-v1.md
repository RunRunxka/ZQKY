# trial-result.json v1

X 为字段唯一负责人；ROOT 2026-10-05 批准，R 独立只读消费。所有 ref 为 `{file: string, sha256: 64 lowercase hex}` 或 null；相对 file 基于 manifest 所在目录。禁止认证头、凭证或完整配置。

顶层：schemaVersion=1，mode=dry-run|live，evidenceKind=fixture|live，reviewLabel:string，scopeSHA:string，authorizationSHA:string|null，selectedCaseIds:string[]，unrunCaseIds:string[]，productionSourceSHA/executorSourceSHA:{path:sha256}，cases:Case[]，stopReason:string|null，realModelCalls:int，fixtureWireSends:int，ledgerRef:ref，technicalGate:string。cases 恰为 selectedCaseIds，包含 STOP 后未执行项；unrunCaseIds 为已知案例中未选项，选中但未执行由 Case.technicalStatus=unrun 单列。

Case：caseId/caseSpecSHA:string，inputHash/modelFingerprint/jobId:string|null，jobAttempt/caseAttempt/providerSendCount:nonnegative int，status:string，technicalStatus=technical_pass|technical_fail|unrun，teacherStatus=teacher_pending，nativeStatus=native_pending，artifacts:{frozenInput,raw,wire,usage,attempt,job,candidate,selectedFields,applied,docx}:ref|null。artifact 为空不能冒称该项已验。

- frozenInput：生产 PreparedGeneration.frozen_input 全对象；匿名自有样本固定来源身份。source/modelPayload 保持生产含义。
- raw：raw.txt，生产 Provider.text 原文 UTF-8。已知秘密/PII 命中时不落原文；保留原字节 SHA、脱敏原因，raw ref null，执行硬停。
- wire：wire.json，实际协议 body JSON，无 headers。发送前与生产 build_request 生成体完全核验；不编辑原 wire 以迎合隐私或预算断言。
- usage：{schemaVersion:1,caseId,scopeSHA,jobId,jobAttempt,caseAttempt,protocol,evidenceKind,rawUsage:object|null,normalizedUsage:{inputTokens:int,outputTokens:int,totalTokens:int}|null,validation:{status:verified|uncertain|out_of_bound,reason:string|null},rawSHA:string|null,wireSHA:string}。rawUsage 是 HTTP 原 usage，落盘早于候选验证；坏 usage 不被补零。
- attempt：{schemaVersion:1,ticketId,caseId,scopeSHA,jobId,jobAttempt,caseAttempt,modelFingerprint,inputHash,wireSHA,rawSHA:string|null,usageSHA:string|null,reservedTokens:int,settledTokens:int|null,providerSendCount:int,state:reserved|dispatched|unknown|settled,boundProofSHA,runLabel}。与 usage、wire、raw ref SHA 关联；result candidate SHA 取 manifest ref，避免 self hash。
- job：生产 JobRecord.view().model_dump(by_alias=True,mode=json)；仅交叉核其真实 jobId/attempt。view 未提供 inputHash/modelSnapshot 时不能虚构已核该字段；冻结身份从 frozenInput/attempt 核。
- candidate：lesson_ai_proposals.payload_json，即生产 normalize_model_output 发布 payload，含 patch/budget/generationSource；validate_for_apply 再核。
- selectedFields：JSON string[]。
- applied：{beforeData:object,afterData:object,selectionActor:qa|human,revisionId:string}；本批自动选择仅标 qa，不当教师接受。
- docx：本批不主动重建旧导出；未生成的新工作副本为 null。

Live 拒绝允许 cases 全 unrun、所有模型输出 artifact null；realModelCalls=0。fixture sends 与真实调用永远分列，fixture 不转签 live。teacher/native 独立 pending；原 B6/B7 和 RAG-REL 不由技术状态关闭。

所有 ref.sha256、attempt.wireSHA/rawSHA/usageSHA 和 usage.wireSHA/rawSHA 均为对应 artifact 的实际文件字节 SHA。wire.json 带 indent2/newline；这不同于 BillingBound.wire_sha 的 canonical(body) SHA，后者只用于内部发送冻结/账费证明及 boundProofSHA。caseSpecSHA 和 scopeSHA 均使用原 common.canonical。ledgerRef 是当前 label 内只读 ledger-snapshot.json，含实际 scope 原对象、authorizationId、evidenceKind、attempts/tickets 和 stopReason；R 可独立重算 scopeSHA 并绑定 attempt ticket，而不代签预算。源码最小闭包还含原 scripts/teaching-quality/common.py；其字节只读。
