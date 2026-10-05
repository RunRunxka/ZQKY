# B4-D01 v1 · 只读契约／文档复核

复核者 g1_resume_browser；仅写本 DOC-AUDIT.md/JSON。未改产品、执行QA、API/ROUTES/PROJECT_GUIDE/CURRENT_STATUS或旧证据；没有启动测试服务或执行业务测试。本审阅不是业务验收，A第二轮和P/F独立结果保持各自原身份与范围。

读取 docs/API.md、ROUTES.md、PROJECT_GUIDE.md，B4-CONTRACT-v1及v1.1/v1.2/v1.3 errata，现行Python/TS DTO、薄页面与API路由、公共JobEngine/retry、T70快照／ready／备注、T80结构／审核／转换／模板、下载服务和前端原包hook。只读stdlib AST／文本比较31个Python/TS B4模型的外部字段集合，0差异；没有导入app或调用模型／路由／服务。没有将此字段集合检查冒称全类型或运行语义通过。

## 实际文案不一致

| ID | 文档位置 | 文案与实际差异 | 建议CTRL修正 |
| --- | --- | --- | --- |
| D01-01 | docs/API.md:683 | 当前B4索引只列v1/v1.1/v1.2，遗漏现行v1.3；原v1:41仍称“节点扁平化后服务决定唯一总ordinal/题号映射”，v1.3:5已明确questionNo是教师输入的完整最终题号，换序不改题号。只循API现列修正会遗漏这一覆盖规则。 | 链接v1.3并明确其完整题号语义覆盖v1旧映射文字，旧QA原文保持。 |
| D01-02 | docs/API.md:703 | 表格将GET元数据和download共同描述为受管asset hash／真实字节核验后返回。实际ExportArtifactsService.get():13–31仅通过DB JOIN核owner、同export/revision、reviewed及job succeeded后构造DTO；真实asset归属、hash／byte_size／media／blob_key对应和读取重算字节散列在download():33–42。metadata读取代码没有真实blob检查。 | 分开元数据身份／终态校验与下载资产和真实字节核验，勿额外承诺metadata GET已读真实字节。此项是静态路径文案核对，未运行新的损坏字节试验。 |
| D01-03 | docs/PROJECT_GUIDE.md:195–197 | 稳定基础规则仍写跨模块类型“只在”teaching_loop.py与teaching-loop.ts定义；现B4 31个共享DTO在contracts/b4.py与contracts/b4.ts，且API.md:683已明确该对。这里保存稳定约束而非已作废快照，这一“只在”排他文字与现B4布局矛盾。 | 改为共享contracts目录内唯一权威定义；公共基础仍用teaching_loop/teaching-loop，B4明确用b4.py/b4.ts，禁止复制的决定保留。 |

以上仅建议，所有权威文档由CTRL修改；本审阅未代改。

## 已登记产品反例的文档关联

v1.3:5要求固定审核快照、DOCX、转换原卷、XLSX与回流证据使用同完整题号。当前 scores/service.py:376–385 的 path_of() 对leaf.question_no无条件再拼所有parent.question_no；例如已完整16(2)的子题置于16容器下，静态路径拼为16/16(2)。这是CTRL已告知P首轮实际反例的同一个问题。本D01未再运行，不另算新反例，也不建议弱化完整题号文档来掩盖产品问题；待CTRL修复／重冻／P适用复验。

## 重点核对结果与验收文字边界

- 固定成绩id：分析请求强制scoreRevisionId；薄页面assessmentId/scoreRevisionId/runId与practices三固定ID、API查询字段一致。T70事实读取score自己的confirmed快照，不替换active；FrozenParticipant和ClassReportRow的className在Python/TS均null，说明固定为“该成绩未记录班名”。
- 公共六态／retry：Python/TS有queued/running/succeeded/failed/cancelled/interrupted；公共retry对注册queued补调度，失败／取消／中断重排并保原冻结输入，running/succeeded409。API.md:386与实际workflow_jobs.py／registry相符。A首轮details过严已通过v1.1 QA适配登记，不能将该首败归成新的API信封缺陷。
- 来源XOR：PROJECT_GUIDE:242–243和API:515与0009重建CHECK及真实复合FK／source/owner/reviewed门相符；没有发现文档要求两个来源同时存在或将practice来源当可选占位。
- 审核不可变：文档只允许新草稿修改，实际ready/reviewed子表INSERT／UPDATE／DELETE触发器、practice源确认映射和审核publication复核保留；本D01不运行DB门禁。
- 实际模板名单：score_template须本固定practiceRevision已转换的assessmentId；接受导出事务读当前实际assessment_participants和该固定paper叶，冻结nameSnapshot/studentNoSnapshot/attendance/attemptNo等；模板空白不补0，显示冻结created_at而不让时钟进入inputHash。DOCX assessmentId必须空。Python/TS请求和现导出路径相符。
- 未知响应与范围：公共useFrozenSubmission对原包structuredClone，status0复用原标识／原载荷，epoch拒绝卸载迟到；B4前端包包括对象与固定revision，服务提交scope为analysis.create:<assessment>／analysis.note:<run>／practice.create／review:<set>／revision:<set>／export:<revision>／assessment:<revision>，与契约表一致。此结论仅代码阅读，浏览器晚响应由F卡验。
- owner下载：artifact GET和download通过export/revision/set/job的owner一致JOIN；download再核file asset owner/kind/hash/size/media/blob及读取字节。文件缓存头no-store/nosniff与API一致。D01-02只指出metadata读取检查范围被合并表述。
- API.md:683、ROUTES:5/22/23与PROJECT_GUIDE:325均明确源码实现不等于B4独立验收／门禁完成，状态只看CURRENT_STATUS；未找到提前宣称B4全验收的当前文字。当前导航source的ready与ROUTES固定query keys一致。
- API旧章节“后续学情报告…”与B0/B2旧分期叙述按API自身“后续章节覆盖”及明确历史说明读取，不当当前能力限制，不作为问题。各errata中的当时自检／实施阶段描述是原件历史，不冒充当前已验收状态，也不要求覆盖历史证据。

完整输入文件SHA登记DOC-AUDIT.json；结果是待CTRL修订3处文案，非新的业务通过计数。收口后停写。
