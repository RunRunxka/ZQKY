# G5 总控提示词独立审查 v1

2026-10-05，负责人 g4_source_review。只读审查新 G5 提示词、recovery/tools/sources 三份报告、两处当前代码与原空 Markdown 模板。本目录保存审查，未改提示词、产品、旧证据或权威文档，未启动服务/模型，也未执行修复。提示词及三份报告 SHA 见 [prompt-input-binding.json](prompt-input-binding.json)。

**技术事实、修复语义、验收和执行边界通过；没有需纠正的已确认技术事实。** 总报告已落盘并补读，交付引用存在。

| 核查项 | 结论与依据 |
| --- | --- |
| 两项问题事实 | 恢复报告确认第二次明确422+cleanup失败恢复后跳到 first-created，没有证明正文丢失或第三次HTTP；提示词准确写该序列和影响。工具报告确认CSV额外格与仅填MD结论两种假通过，正常已知CSV reviewer非空正确拒绝；提示词没有误写原273包已非空。 |
| 既有事实 | main@b7f99ab、B7-A r2候选SHA/959/3496/33/970/build/proxy与本批REPORT一致。37恢复及60来源/历史是本轮各自完整范围，不是新G5预先通过；提示词只要求保持。G4旧四项关闭、正常B7-A包不被新finding推翻。 |
| cleanup身份与清理失败 | 将 success/failure 作为本次清理结果，并绑定本次 operationId/submissionId/contextKey/loadGeneration，实际提交回调捕获本次operation；不从旧render frozen或历史result猜回执。只有本次success打开本次文档，failure仅清理/解锁；unknown/发送前write失败保留原包和发送限制。恢复后仍校验owner/session，仍走现有离开保护，含取消、跨文档/卸载/迟到及双操作create/import验收。未遗漏关键身份或第二次success误采用第一次result的对照。 |
| 空反馈完整校验 | CSV准确表头、每行key集合/字符串、全集顺序与固定case/DOCX hash、全部人审列空；MD需固定case/hash和允许的空槽、无重复/遗漏/未知块与正文评语。检查结果共同决定 originalEmptyFeedback* / humanFieldsFilled=0。原Markdown含“真人结论”标签，因此正确禁止仅按关键字拒绝；允许固定模板/BOM/换行规范化，不允许吞真人内容。 |
| 独立验收 | 保留两条原首败与首次成功/失败对照；组件验证教师可见导航/HTTP，而非内部字段镜像。工具穿过合法SHA再次核内容，拒绝形状异常与MD多种填值，正常15/显式14、原材料不变、四guard、硬拒独立列示。check+build后必要真实浏览器及完整E2E为恢复导航变更的适用门禁，没有以unit代替真实业务。 |
| 范围与原计划 | G5仅两项修复及独立技术收口；明确不等同原v2 G5整体。不新模块/API/迁移/依赖，不重制15例/273引用/四历史导出；共享模块默认只读、扩大写范围需CTRL登记，不修改原v2任务/伪代码。无Git/部署，完成后STOP。 |
| live与后续试评 | B7-B章节只作交接，executorPresent=false/budgetEnforced=false及合法预检不创造授权写明；本批不实现或运行live执行器，不凭现有连接/未回复授权。后续必须明确模型、精确案例/数量、attempt和可执行预算，并复用既有业务链，真实教学评价和原生Word/WPS证据仍待真人。没有把固定输出或13页PDF当真实模型/native证明。 |

没有发现扩大当前两项修复为真实试评、重建物理源、整体计划关闭或绕过旧自动审批拒绝的路径。提示词对模型0、正式数据库及旧被拒HTTP probe边界明确。

**交付引用已核：** 初次读取时总 REVIEW.md 尚未落盘，已通知 ROOT；本卡写入前已经生成。随后实际补读总报告与本批 README，内容与三份分项报告和提示词一致；两处提示词/总报告相对链接均指向现有文件。该临时缺件已经消除，不作为未完成事项。若提示词或总报告后续改变实质事实/范围，须另核变化。
