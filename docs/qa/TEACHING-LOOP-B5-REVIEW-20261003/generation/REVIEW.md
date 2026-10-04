# B5 AI教案生成只读审查

2026-10-03。范围为`lesson_generation`、生产RagV2教材证据端口及三协议最终Provider body；不含后台保存/前端完整验收，也不实施下一阶段。

## 结论

本范围未发现新的可复现产品缺陷。第二轮窄回归退出码0，41项通过：5项新增独立边界、既有来源11项、生成任务22项、实际三协议wire3项。另一个纯服务诊断区分了磁盘损坏后warm cache与合法删除：合法删除在调用Provider前拒绝。完整API/check/浏览器/E2E本审查未重跑，不沿用此前数目作为本轮执行数。

模型及向量传输均为受控替身；真实模型教学质量、正式Qdrant、正式迁移、Word/WPS/PDF未执行。没有重试或变体执行被拒的额外HTTP身份核查；没有启动服务、浏览器、Git提交或改产品/旧QA/权威文档。

## 核查依据

- `apps/api/app/services/lesson_generation/preparation.py:98`从固定ready报告只取明确班级与所选知识点的完整行，校验修订身份；后续活动成绩指针不替换固定报告。独立最终Provider body的手工分数oracle为K1有效3/需巩固2/分母3，K2有效3/需巩固1/分母3；完整flag计数也逐项核对。
- `preparation.py:109`/`:148`核生产教材引用、正式固定题、审核固定练习及全部不同历史知识点修订；`:173`只构造匿名别名与班级计数和允许正文，不发学号/姓名/人次/教案与成绩ID。
- `privacy.py:86`/`:159`按路径核白名单与实际三协议序列化body；自由文本不借匿名别名或整数计数的豁免。新增NFKC全角已知ID与word-joiner组合在Provider之前阻断，错误不复述身份。已知PII阻断仍不等于任意未知身份匿名保证。
- `service.py:106`/`:116`在推理前核来源、冻结指纹；取消、原lease失权、超时、重启显式retry、原子发布、失败回滚由本轮窄回归覆盖。结果只插候选，不改教案正文。
- `validation.py:47`/`:120`严格五整字段、匿名稳定环节ID、四phase、整分钟总和、非空活动/检测、所选KP覆盖、固定依据alias及再应用校验。真实教学意义和教材相关性属于另行质量验收。

## 非阻塞观察

**G-OBS-01：重新验证固定教材，不等于每次重新读取磁盘。** `apps/api/app/services/rag_v2/source_text.py:76`缓存此前核SHA的不可变文本，`:99`缓存解析；`lesson_generation/service.py:105`注释“rebuild real source bytes”需要按实际语义理解。隔离诊断在准备后直接损坏自有TEMP的normalized Blob：warm reader仍使用原SHA正确的缓存内容生成成功；新reader读磁盘报`RAG_EVIDENCE_UNAVAILABLE`。恢复原Blob后，通过真实目录`delete_document`合法删除教材：同样已冻结的任务报`RAG_SCOPE_CHANGED`，Provider新增调用0。缓存没有发出被损坏的新字节，没有绕过合法删除，不能据此判定为B5阻塞缺陷。后续文案宜描述“重新核验固定证据内容与当前scope”；若要求每次检测物理bitrot，另行明确缓存失效策略与成本。

**G-OBS-02：计数有重叠，不能当互斥分组。** `incompleteCount`是信息不完整flag，包含absent/exempt无有效证据；`noEvidenceCount`也可覆盖同一人。K1样本selected=4，但needs2/fullCredit1/incomplete1/noEvidence1之和为5。技术传输正确；下一轮真实模型质量应检验模型不会相加这些字段重新推导人数/掌握概率，并在需要时向Prompt补明确计数语义。

## 首败说明

`narrow-first.log`与原command保留：41项中2项失败均为本审查探针问题。手工oracle错误地把全absent视为不计入informationIncomplete；另一个探针误用教材catalog没有的`write_transaction`，应使用真实`set_active_generation`。只修新增探针后第二轮41项通过，产品未改。原first-command的`appMainImported:false`字段记账错误：既有tests/conftest实际导入app.main，但导入前runner已设置新TEMP数据根和`ZQKY_ENV=test`，Settings因此`credentials_file=None`；第二轮收据准确标注导入。原`startedAt`第一轮记录在完成之后，第二轮另记准确起止时间。不得把这两项探针失败或收据错误写成产品缺陷。

## 证据

- [最终窄回归](narrow-second.log)、[实际命令与隔离根](narrow-second-command.json)
- [首败](narrow-first.log)、[原记账收据](narrow-first-command.json)
- [新增探针](test_review_generation.py)、[执行器](run_review.py)
- [缓存原诊断](warm-source-cache.json)、[缓存与合法删除区分](warm-source-cache-v2.json)、[诊断源码](probe_warm_source_cache.py)

所有样本在收据所列新OSTEMP内保留；诊断改写的TEMP Blob已恢复原字节。无需关闭新监听端口，本范围未开监听。
