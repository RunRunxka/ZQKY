# B4 shared foundation v1.1 · 精确修正

v1 DTO/列名/请求语义不变；以下源码调查错误和首探失败均已纠正，未覆盖首轮证据。

1. 0009 重建不能让外部触发器引用处于临时缺失的 paper_revisions。RebuildPlan 同事务先卸对应原/相关触发器再 drop/rename，restore 原触发器并增加 practice 来源门；未改公共执行器。首轮 foundation-first.log 原件保留。
2. 现 score_revisions 只有 UNIQUE(id,assessment_id)，paper身份来自 assessments。0008 的真实复合 FK 改为 (score_revision_id,assessment_id)→score_revisions 与 (assessment_id,paper_revision_id)→assessments；原三列/score-paper pair引用错误分别保留第二/第三日志。第四新样本迁移两次通过，0FK、integrity ok。
3. practice-origin paper_confirm 新门：全题数量与固定practice_items一致；sourceLocator.practiceItemId 引用同固定practiceRevision，is_scored/max_score_units/content_json与固定审核题快照一致。conversion可先确认卷再建施测/conversion/mappings，避免循环前置；确认时的来源locator是真实固定题映射依据。file-origin旧计分/来源门保持。普通paper draft fork禁止绕开练习审核编辑practice来源卷，返回 PRACTICE_PAPER_EDIT_REQUIRES_NEW_REVISION；从newpractice draft审核后转换。
4. T70公开 read_ready_report 增 originalQuestionContents（固定原卷兼容题内容，不含学生数据），T80用现 question-surface-v1 算法排file原题，不能null questionRevisionId即失效。FixedQuestionReader.surface_fingerprint也用 duplicate_content_fingerprint / DUPLICATE_ALGORITHM_VERSION，不混原content fingerprint。
5. 现 QuestionBankService 只有 get_content_asset(kind,id,assetId)，没有 v1准备所称read_asset。main内部 question_asset_reader callable 直接复用 services.question_bank.rich.read_asset，注入现managed assets/QB blobs；T80先核fixed题owner与全部declarations，再只读核字节+规范managed，HTTP不暴露任意键。第一次foundation-pytest因错误装配AttributeError失败日志保留；修正后实际专属9pass exit0，4.802秒命令耗时。

最终共享精确SQL/hash以稳定candidate冻结时登记为准；当前仍作者实施阶段，不能将此foundation自检标独立验收或B4已完成。0001～0007 original声明/hash专属literal验证已通过。
