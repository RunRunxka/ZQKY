# 离线教学质量材料使用说明

本包只核材料结构和SHA，不运行模型、不确认教学质量或Word/WPS排版。先读需求矩阵、手写expected和八维rubric，再读固定输入/fixture输出及原15行空feedback。需要填写时先复制空表到新的教师评审label；由真人填原文位置、支持/不支持理由、修改建议与评分，不覆盖旧证据。硬失败不能用平均分抵消。C10～C13只是未来优先阅读建议，不构成模型调用授权。

native-pages-feedback.csv只有四个文件的起始行：应用/版本、真人姓名日期、实际原生页号/总页数和所有结论留空。请在Word/WPS手动打开原DOCX的工作副本，逐一实际页面新增行，填实际页数，核长中文/全部secondary/合并/表格续排/截断与来源文件名。pdf-reference-pages.csv的13页来自历史实际PDF，仅作对照，不能把其页码或总页数填作原生页数。当前原物理源复核状态在technical.physicalSourceCheck单列，冻结source binding核查不代表新四库/Blob物理通过。

真实模型、真人教学判断与原生排版分别待验；本批用户明确只做离线。预检合法也不提供模型存在、真实授权或总预算执行保证。RAG-REL OPEN，原B6/B7整体未关闭。旧15输出、DOCX/PDF/PNG没有复制或重新生成。
