# B6 质量独立审计首败分类 v1

更新时间：2026-10-04T14:52:11.232360+08:00。补充叶；既有 RESULT-v1.md/json SHA保持原值，技术结论只来自新完整r3十五例，未拼接多轮。

| 分类 | 证据与处理 | 对最终业务判定 |
| --- | --- | --- |
| 业务 | 独立完整15例未发现业务结构缺陷；SourcePanel S03真实并发缺陷单列于review-source | 教学质量仍待真人，不据结构判质量通过 |
| 报告包装 | boundary的独立导出v1读错status/payload包装，v2读取实际payload后完整4样本/13页核实 | 属对方读取QA首败，保持原件；不是本卡15例失败 |
| 排序 | own r1在C06，手写提交名单与报告规范排序列表不同；前5例/65SQL行后失败 | 新r3完整集合、长度、无重复、逐ID alias/attempt/出勤/班及完整四态原矩阵核对，未删选人检查 |
| 内容投影身份 | own r2在C11，将全文normalizedTextSha256误作选中18字符slice SHA；前10例/132SQL行后失败 | 新r3分别核完整normalized Blob和精确slice offset/text/SHA，作者v3本已正确，无作者或产品修复 |
| 报告措辞 | 原“每例15次”歧义有新增计数勘误 | 15例各1次，共15替身调用；实际模型/外部0，usage null不当消费 |

r1 PID25012 /112.575ms /exit1；r2 PID25812 /141.685ms /exit1；最终r3 PID22064 /171.391ms /exit0，完整15/183SQL行，作者318文件零差异。首败原source/log/receipt均保留；新审计没有改质量作者包。teacher_review_pending、live_run待输入、RAG-REL OPEN、DOCX真实WPS布局not_run维持。STOP。
