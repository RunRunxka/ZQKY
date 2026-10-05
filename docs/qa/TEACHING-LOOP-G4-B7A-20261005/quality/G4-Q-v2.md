# G4-Q v2：显式分开冻结来源材料与物理来源复核

2026-10-05；ROOT释放v2解释后实施。原v1作者首轮`author-r1`在setUpClass发现原offline-third TEMP的四库sqlite文件不存在，执行0测试、exit5；父目录仍在不代表文件可读，原因未确定。原日志、命令、输入与TEMP保留，没有修旧路径、重建旧库或调用业务重新生成15个案例。

聚合器必须显式指定`--source-mode`，不自动降级：

- `frozen-source-binding`：核原case-bound-v3位于用户冻结候选f79ac…中的精确SHA；逐项核完整行canonicalSHA和固定身份、已冻结Blob散列、手写case/oracle、输入/wire、应用完整11字段及导出。可以记录本次材料结构15/15或授权14/14，单独写`physicalSourceCheck=not_run_source_temp_unavailable`；没有新四库或Blob读取，不声称旧物理证明本批重跑。
- `readonly-catalogs`：对显式TEMP路径用stdlib SQLite mode=ro/query_only，逐全列与冻结行对比，并读实际Blob。任何缺库/缺Blob必须非0。没有app导入、迁移或正式数据访问。

冻结材料本身缺项、SHA不符、canonical散列不符、来源身份不一致或DOCX结构错误在两种模式都失败，不以not_run放行。冻结SHA由调用方显式提供，不能从本次实际结果反生成expected；合法scope预检也不提供真实模型授权或总预算执行保障。未来真实运行仍须新真实来源、模型resolver/fingerprint和执行身份另验。
