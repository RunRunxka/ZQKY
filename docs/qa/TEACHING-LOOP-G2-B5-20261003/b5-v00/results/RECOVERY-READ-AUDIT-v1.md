# B5 四库恢复保留样本独立只读审计 v1

结论：保留样本的直接 SQL、完整表行和文件字节校验通过。本结果不等同独立恢复运行，也不宣告 B5 阶段验收完成。

- 本次标准库进程 PID：23756；实际退出：0；进程耗时：211.049 ms；16 个只读连接全部显式关闭，进程已结束。
- 对 source、canonical、archive、restored 各四库执行 PRAGMA integrity_check 与 foreign_key_check，共 16 库均为 ok / 0 违规。打开前检查 WAL：所有被审计库均不存在或为 0 字节；使用 mode=ro&immutable=1 与 query_only。
- 以独立 sqlite3 SELECT * 比较 canonical 与 source/archive/restored：teaching、knowledge、questions 每个业务表、全部列及全部行精确相同；source/archive 的教材全表相同，restored 的 documents、document_revisions、chunks、generation_revisions 四固定表相同。
- 六个新教案表实际行数依次为 2、3、3、2、2、2。正文 data_json、context_snapshot_json、generation frozen_json、建议 payload_json、decision、review 以及 lesson_plans.current_revision_id 均包含在直接全列比较中；两个 current pointer 无孤儿或跨教案链接。每表及每行摘要和完整列名见 JSON。
- 原 9 条迁移校验值与 proof 一致；四份 teaching 库记录同一 0010 校验值。该检查没有重新执行生产 schema gate。
- 两份 managed asset 的 source/canonical/restored 原字节相同，SHA256 和长度各为 proof 所载值：19 与 70 字节。备份 manifest 的全部 9 个文件 SHA/长度匹配；非库恢复文件原字节一致。
- 假向量 snapshot 原文件 SHA 匹配，序列化 3 个点的 metadata 与直接 SQL chunks/generation_revisions 对应；本次未连接 Qdrant 或执行向量恢复。
- CTRL proof 与保留 sample proof 的 JSON 内容和原字节均相同；分别保存原始 SHA。全部输入及临时样本 56 个文件读取前后 SHA 不变，无新增或删除样本文件。

作者证据单独归类：b5-backup-recovery-v2，PID 26092，exit 0，2601.856 ms，1 个 pytest 通过。该 receipt 仅绑定其列出的 5 个源码 SHA，candidate 为 null；旧 v1 清理失败保留，没有将失败标为通过。作者测试中的实际恢复、应用启动和证据读取只作为作者运行证据。

未执行：本次独立 backup/restore 重跑、app.main/create_app/TestClient 启动、教案 GET 与 RAG evidence runtime、Qdrant/embedding/model 请求、旧 B4/故障回滚/全 API 套件。它们超出本任务的只读范围，不由此处的一例作者 receipt 推断。

[完整 JSON 与标准库 stdin 审计程序](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/results/RECOVERY-READ-AUDIT-v1.json)
