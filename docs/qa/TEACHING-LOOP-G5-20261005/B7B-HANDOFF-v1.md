# G5 之后的 B7-B 接续条件（仅交接）

ROOT，2026-10-05。本批授权止于 G5。已有 [B7-A 离线材料入口](../TEACHING-LOOP-G4-B7A-20261005/B7A-OFFLINE-MATERIALS-v1.md)、[273 原材料引用](../TEACHING-LOOP-G4-B7A-20261005/b7a/prepared-full-v1/MATERIALS.json)、15 案例和四类历史导出保持；后续承接这些材料，不重复制作准备包。G5 的严格空反馈核验只确认输入状态，不代填教师意见或给教学质量结论。

真实试评需用户另行提供并明确授权以下范围，输入不含 API Key：

| 必需输入 | 可执行范围 |
| --- | --- |
| modelProfileId、modelId | 明确实际连接及模型；凭证仅走既有后端安全配置 |
| 精确 caseIds、sampleCount | 与原固定案例一致，不以默认全集推定授权 |
| 每例 maxAttempts | 失败尝试也计入；不能自动超次重试 |
| maxTotalTokens 或 maxCostCny | 总上限必须能执行；usage 未知时停剩余案例 |
| 教师与反馈返回方式 | 真人填写评分、原文位置、支持理由、不足、建议与结论，使用新评审 label |
| Word 或 WPS、原生页核方式 | 实际打开 DOCX 工作副本，记录应用版本、实际页码/总页数和逐页问题 |

现有 scope_preflight 仍是 `executorPresent=false`、`budgetEnforced=false`；合法预检不等于真实调用授权或预算保证。未来实施应复用既有 LessonGenerationService.prepare/build_request、resolver/fingerprint、匿名来源白名单、JobEngine 和固定候选，先独立证明总预算、发送次数与失败/未知用量停止条件。不得另造提示词、业务 API、表或把 fixture profile/MockTransport 计作 live。

原空教师表保持。真实输出结构、教师教学判断、教材 RAG 支持和 Word/WPS 原生排版分开验收；历史 13 页 PDF 不当原生页数。`RAG-REL`、原 B6/B7 整体及 R14/CV01～03/OBS-LP-MODE-LABEL 仍按实际证据推进，本文件不关闭它们。

G5 收口后 STOP，不启动 B7-B，不收费调用模型，不进行 Git 写入、推送、切分支或部署。
