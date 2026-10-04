# B4 shared foundation v1.4 · 独立反例修复

DTO和外部路由不变，v1.3完整最终题号仍优先适用。提交级独立诊断64项为57通过/7失败，真实事务结束后归为4组问题；原候选、源码、失败样本和日志保持。

- T60固定卷reader快照新增内部来源标记；练习来源原样使用完整questionNo，文件来源继续原层级相对题号路径。历史已确认成绩或报告不改写。
- practice父身份id/owner/analysisRun/subject/createdAt固定；初始subject必须与同owner的真实报告一致。title/status/currentRevision/乐观revision仍可按现行操作更新，审核修订及子表原封存闸门保留。
- conversion插入必须同时对应同owner审核练习、来源为该练习的已确认卷、同学科卷与该实际施测，不以两端各自合法FK代替来源关系。
- 同卷映射还需核固定paper_item.sourceLocator的practiceItemId与practiceRevisionId，拒绝把合法源叶A映射到另一合法卷叶B。

仅改变本批新增0008/0009声明，不改教学0001～0007及其散列。不使用旧B4试验库冒充最终迁移，后续验证均全新隔离样本；带数据0007迁移、故障回滚和含全部新表/资产恢复须在新候选重新执行。该文件登记修复语义，验收结果只看关闭矩阵。
