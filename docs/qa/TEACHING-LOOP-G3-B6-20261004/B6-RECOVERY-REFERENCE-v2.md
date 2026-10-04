# B6 迁移和恢复证据来源 v2

本批未改DDL、备份或恢复代码，没有追加0011，没有重新运行备份/恢复。仅只读绑定历史隔离证据，结果见[精确收据](ctrl/B6-RECOVERY-EXACT-REFERENCE-v2.json)。ROOT进程3748/44.374ms，未导入app.main、未打开SQL、未连接网络或正式数据。

两组证据独立列明：

1. 原早期作者实际恢复1例（PID26092/2601.856ms）及第三人16库全列审计（PID23756/211.049ms）：旧7输入、56样本文件当前字节全部相等。五个早期源码仅四个与当前相等；lesson_schema_gate后来在原B5修复过，不能称五源全等。首个过严断言失败原件保留，v1收据不作为成功结论。
2. 后来B5最终全API1918pass+1既有重型skip（PID21200/392504.479ms）的410后台子映射与当前逐文件完全相等；其中实际恢复case单次通过，JUnit time1.173s，无failure/error/skip。该运行自己的保留B5-RECOVERY-PROOF已读取并固定SHA。这是当前schema gate的同源运行证据；本批没有冒称重新执行恢复或对新样本重复第三人16库审计。

原SQLite四库和Blob为实际恢复，Qdrant点与snapshot是原隔离Transport替身，正式6333、正式迁移和新增压力均not_run。旧0001～0010迁移/备份脚本保持；旧RAG相关性和缓存warm/cold观察不由恢复通过推定关闭。
