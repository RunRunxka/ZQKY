# G5-DOC 独立审查准备 v1

本任务只审 ROOT 的本批新增文档、收据与证据一致性。G5-Q 已停止，产品和作者 quality/ 原证据只读；唯一可写范围为本目录。此准备不签 PASS。ROOT 明确“最终文档可审”后，审查者才填写显式输入索引和实际观察，并在不存在的新 label 执行一整轮。

六份 authority 只剥精确 `<!-- G5:20261005 -->` 状态块及该块紧随的新增空行，剥离后的全部字节必须等于 opening 原文件。v2 的原任务和伪代码不可改。其余 opening authority（Guide/API/ROUTES/PLAN、模板、next-env、提示词）保持原字节或原不存在状态。HEAD/main 直接只读解析本地 Git 引用，不执行 Git 写入。

独立重核 opening 的22207份旧QA、1056份原材料、正常包273条引用和当前候选 source/执行QA/contract/build域，不把原缺失 VISUAL-REVIEW 当本批新增错误。缺失旧物理源不重建，MISSING_NOT_RUN 仍保持。新报告/矩阵/两finding/关闭/资源收据、完整check/新build/独立组件/CLI/新8场景浏览器/完整174的来源与真实命令时间、PID、argv、退出、计数须一致。API/chat/export未跑应与 HISTORICAL-REFERENCE-v1 的同源边界和真实原SHA一致。

审查脚本只检查当前 G5 块与 ROOT 新文档链接，历史段不作为当前结论的 oracle。输入索引由独立审查者根据实际冻结路径填写，包含每份当前文档SHA、gate命令记录、原始log/JSON、JSON计数pointer/期待值与人工逐条事实核对；未知计数不从实际输出推造期望。已知浏览器8/full174提前固定。脚本只在所有机器判据和明确人工审查都完成后输出独立结果；输入材料缺失、漂移或冲突必须失败，首败留存，修后新label整轮重验。

等待边界须明确：B7-B/live未开始、教师与Word/WPS/native、当前物理SQLite/Blob、R14/RAG-REL和原B6/B7整体保持待验；原policy拒绝HTTP探针不重试，Git无写，本批停止而无下一批。最终审查输出和后加文档单列delta，不声称旧candidate覆盖它们。文档审查不是产品或教师验收。

准备 STOP 后仅冻结本目录的 PLAN/ORACLE/脚本SHA，不运行最终审查或发布结论。实际审查用 `python -B audit_documents_v1.py --label <新label> --inputs <独立显式索引>`，禁止覆写label。
