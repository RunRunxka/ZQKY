# B4-D01 v1 · 文案修正第二次只读复核

CTRL通知已修三处文案后，独立只读复核 **D01-01/02/03均已解决**。本轮仅新增本second MD/JSON；首轮DOC-AUDIT.md/JSON的原SHA分别87eccced5dc5938e37e88eb4c9c2dff08443ca9bce2e2f4df4cb388afe2eb822、48f57a8d85ffb80864afc8e63ea92229c3b2df7454395c0451c6abcbdbb8ff27，现核仍一致，未覆盖。

| 首轮问题 | 现行文案与对应来源 | 结论 |
| --- | --- | --- |
| D01-01：API漏v1.3 | API.md:683明确链接并优先适用B4-CONTRACT-v1.3-ERRATA，直接说明PracticeNode.questionNo是完整最终题号、换序不自动改号；与v1.3:5覆盖旧v1的编号映射规则一致。 | 文案已解决；原v1/首轮历史原文保留。 |
| D01-02：metadata/download核验范围合写 | API.md:703明确元数据核同owner、固定审核版、任务succeeded；下载另核受管资产身份、实际hash和字节数。与ExportArtifactsService.get():13及download():33的职责相符；API路径`/api/v1/export-artifacts/{id}`与`/{id}/download`、owner JOIN、no-store/nosniff均保持实际一致。 | 文案已解决；未再承诺metadata读取已验证实际blob字节。 |
| D01-03：共享DTO仅限common两文件 | PROJECT_GUIDE.md:195–197改为后端app/contracts/与前端apps/web/src/contracts/内单一定义；common教学协议使用teaching_loop.py/teaching-loop.ts，B4 DTO使用b4.py/b4.ts；与实际文件归属和API.md:683的DTO来源一致，乐观锁/固定revision、整数单位纪律保留。 | 文案已解决；没有放宽重复定义。 |

复核范围内owner/path字段、固定修订和验收状态文字没有新增不一致。API.md:683仍明确B4独立验收和门禁完成只看CURRENT_STATUS，不将源码实现写成全部验收通过。

本轮没有执行业务／HTTP／DB／浏览器／测试，没有启动或停止服务，没有改产品、执行QA、权威文档或CURRENT_STATUS。31DTO第一轮静态字段核对未重跑，本second只核三项文案与对应静态源码／契约，不扩大非B4目标。

三处文案关闭不代表完整题号的P产品反例已通过复验，不代表B4全部验收完成，也不改变A/P/F各原始候选身份。最终业务修复、候选重冻和适用复验由CTRL收口。

现文档和相关静态来源SHA见DOC-AUDIT-second.json。复核完成后停写。
