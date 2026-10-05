# 离线教学质量材料入口 v1

此入口只为本批用户授权的离线工具与验收准备。没有模型执行器、凭证读取、网络、原生渲染或教师评分；不能把预检合法当真实模型可用、预算已保证或调用获授权。

`prepare_review.py --plan <严格JSON> --plan-sha <可选固定SHA> --output-dir <不存在的新目录>`。默认完整计划见仓库`docs/qa/TEACHING-LOOP-G4-B7A-20261005/b7a/plan-full-v1.json`；它明确列举C01～C15，expected集合不从实际results生成。显式子集使用新的scope/summary/docx collection及新plan，不改旧文件，未选案例单列unrun。

plan为精确schema：顶层schemaVersion必须是整数1，mode为offline_review_preparation；artifactRoot；requirements及g4Close各含file/sha256；aggregate按现有聚合器全部公开输入显式列路径/SHA/前缀/source_mode；materials含rubric/feedbackCsv/feedbackMd/representativeExportResult/representativeRoot和明确四样本short、long、multi、symbols。不允许秘密、未知字段、重复键或非有限JSON数。

入口每次调用新`aggregate_review.aggregate`，再核固定原材料路径与artifact SHA，输出MATERIALS/RESULT、使用说明、四文件原生分页空反馈表及历史PDF13页参考索引。15案例/原输入/expected/fixture输出/逐例DOCX、四代表DOCX/PDF及原PNG都只读引用，不复制为新输出或重新生成。

代表导出manifest.context只是analysisRunId与selectedKnowledgePointIds选择描述，不能当完整后台contextSnapshot。入口将其ID与saved.currentRevision.contextSnapshot关联，并全等核saved/before/after完整固定教案修订JSON、全部正文与context以及前后全部历史JSON；source标签与代表收据固定revision映射另核，不能为形状适配跳过身份或正文。

空feedback原件按SHA引用，先复制至教师自己的新评审label再填写。原生表中真实页号/总页数、应用/版本、评审者、证据理由、分数或结论都留空：按实际Word/WPS每页追加行。PDF的1/8/2/2共13页仅作历史参考，不是原生页数。

空表引用在发布前同时核内容。CSV必须是固定顺序的20个表头、完整15例顺序、每行恰20个字符串单元格，四项原案例/来源/候选/DOCX散列对应冻结索引，全部人审列为空；额外格即使为空、短行、重复或未知表头/案例均拒绝。合法UTF-8 BOM、CSV引号/逗号分隔和引号内的空白换行保留CSV语义，不能藏入额外内容。

Markdown按独立冻结manifest的caseId/title和原case.json散列在内存重建原明确空模板，核全部15块和每块14个`____`空槽（共210个），包括评审人、日期、硬失败位置、八维分数、不足、建议和真人结论。仅允许起始UTF-8 BOM和CRLF/CR/LF换行表示差异，其他正文、身份、标题、散列、槽内容及附加评语必须严格相等；不会删除评语后标为空表。显式14例技术子集仍引用并核原完整15例空表，未运行C15另列。两种空性核查全部通过后才输出originalEmptyFeedback引用及humanFieldsFilled=0；该零值不代表真人已完成评价。

`frozen-source-binding`核原完整来源canonical与身份，物理源未复核单列；`readonly-catalogs`缺库/Blob失败且没有迁移。真实模型/真人教学判断/原生排版分栏，RAG-REL OPEN，原B6/B7未关闭。新源码不改变已验的G4三个工具、后端或前端；工程与浏览器门禁由ROOT按精确来源域引用。
