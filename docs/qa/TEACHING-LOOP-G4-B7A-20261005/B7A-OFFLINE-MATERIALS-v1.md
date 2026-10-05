# B7-A 离线材料与后续人工验收入口 v1

ROOT，2026-10-05。本文件索引已经生产并核原SHA的离线材料，不给真实模型、教师评分或原生排版通过结论。工具独立签核及唯一当前阶段见本批README和CURRENT_STATUS。

先读[需求→样本→核验矩阵](B7A-REQUIREMENTS-MATRIX-v1.md)、原[手写case-specs](../TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json)及[八维rubric](../TEACHING-LOOP-G3-B6-20261004/b6-quality/RUBRIC.md)。C01～C15固定输入、wire、fixture候选、应用正文和15逐例DOCX等273条引用逐SHA保留在[新材料索引](b7a/prepared-full-v1/MATERIALS.json)，没有重新生成旧材料。

材料索引SHA `46eaa6ce99c9fea2f617504262b75a2d1498f51de65afcc00767fd082c802b6f`；[显式离线计划](b7a/plan-full-v1.json)SHA `9659953d9e6a8b03dd309f7f943c946879ae0d14d7fa8ae9a92ec0cb3ca7507f`。正常包只生产一次，实际命令PID12556/389.703ms/exit0，独立guard为0；此计数不代表模型调用。所有来源包与修改建议都按固定案例审，不从实际输出反填expected。

教师先将[原15行空反馈CSV](../TEACHING-LOOP-G3-B6-20261004/b6-quality/feedback-offline-third.csv)复制到新的教师评审目录，再填姓名、日期、八维评分、原文位置、材料支持/不支持理由、不足与修改建议、真人结论。原表保持空且只读。没有live时可对手写oracle或试用流程提意见，但fixture不能写为真实模型教学质量；硬失败不能用平均分抵消。

四个代表DOCX和四个历史PDF是另一组排版材料，与15逐例DOCX技术核查分列。下面DOCX原SHA固定，来源构建是旧q84e_pxQoZ2_nwnws9QiI；没有声称它们在当前构建重新导出。

| 样本 | 原文件 | DOCX SHA256 | 对照 |
| --- | --- | --- | --- |
| short | [DOCX](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/short/short.docx) | `af1a4c190dbb307bba3b0633ea5c6beaf68918579d29e214b1a9b70aca159c90` | [历史PDF](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/short/short.pdf) |
| long | [DOCX](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/long/long.docx) | `601752d6a093f82f3a44ce754aa09a0a422405d4c0e51bbcdf70169ca143bf22` | [历史PDF](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/long/long.pdf) |
| multi | [DOCX](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/multi/multi.docx) | `ec77559c7ba9cb525eee6dfd13d92887988bae897edc18fb8f6cb6967f7f88a0` | [历史PDF](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/multi/multi.pdf) |
| symbols | [DOCX](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/symbols/symbols.docx) | `a7b408bab888a3bc9782050a9344735db8247b12967afb4af04044048720824a` | [历史PDF](../TEACHING-LOOP-G3-B6-20261004/b6-exports/samples-r3/symbols/symbols.pdf) |

[原生逐页空反馈表](b7a/prepared-full-v1/native-pages-feedback.csv)SHA `85bf5656126ad5e97a490adafffa274442aa6f7f0923442ef1bc42884085657b`。只有四文件起始行；姓名、时间、应用/版本、实际原生页号/总页数和证据理由/结论全空。后续由教师在Word/WPS手动打开DOCX工作副本，按实际每页新增一行，核全部11字段、每条secondary、长中文/符号、合并单元格、表格续排、截断/重叠与来源文件。保留应用版本和实际证据位置，修改建议另给，不覆盖原DOCX。

[历史PDF逐页参考索引](b7a/prepared-full-v1/pdf-reference-pages.csv)列short/long/multi/symbols的1/8/2/2共13页及原PNG SHA。这13页只属于旧实际PDF，不预填为Word/WPS页数。当前自动化没有原生Word/WPS控制能力，本批原生验收未执行。

本批用户只授权离线工具与验收准备：live=not_run_user_offline_scope、teacher_review_pending、native Word/WPS not_run。冻结来源canonical完整绑定核查与当前物理源核查分列；旧物理SQLite/Blob及恢复证明缺件仍not_run，不重建旧TEMP或迁移。RAG-REL、R14、CV01～03、OBS-LP-MODE-LABEL和原环境观察保留；原B6/B7整体未关闭。

未来真实试评须另获完整modelProfileId/modelId、精确caseIds/sampleCount、maxAttempts及可执行总token或费用上限。范围预检不能提供模型存在、授权或预算执行保证。本批没有live执行器；后续必须走已有生产prepare/build_request、resolver/fingerprint、匿名白名单、JobEngine和固定候选，排除fixture profile/回环9/MockTransport。失败尝试计入总预算，usage未知停余例；原raw/wire脱敏证据只置于独立隔离目录，不另建prompt/API/表。C10～C13仅供未来优先阅读；当前不运行或收取模型费用。
