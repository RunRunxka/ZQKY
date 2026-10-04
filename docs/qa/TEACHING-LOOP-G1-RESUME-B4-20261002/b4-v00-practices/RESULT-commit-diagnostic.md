# B4-V00-P v1.2 — 未修改产品的提交级诊断

本轮是 CTRL 明确授权的 CollectAll 诊断，不是修复验收。实际执行完整 **64 项：57 passed / 7 failed / 0 skipped / 0 未执行**。未改产品、冻结契约或可执行 QA 源；未修复当场失败。四项已获授权的夹具修正及真实事务终判使旧诊断中的夹具问题消失，7 项剩余失败均有实际业务响应或提交后的持久记录。

冻结身份：`CANDIDATE-b4-p4.json` SHA256 `74d8ed35c86adb2844529a3aef8b15a4f0f0db592b97511fe5b78fbb8627559a`；877 产品源与 p1/p3 完全相同，候选 P 范围 18 可执行 QA。`QA-SOURCE-MANIFEST-v1.2.json` SHA256 `64c8c73173d0475d529388d76a2124466a7bca36d7c304faaeddb3ccc2922469`，包含本任务 4 个执行源。首轮字节、v1.1 原源、diff、first/diagnostic 日志与收据全部保留。`commit-diagnostic-preflight-audit.json` 与 runner 收尾 identityAfter 均为零漂移。

## 实际命令与资源

```powershell
& 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\b4-v00-practices\run-probes.ps1' -Label commit-diagnostic -CollectAll -CandidatePath 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\CANDIDATE-b4-p4.json' -CandidateSHA256 74d8ed35c86adb2844529a3aef8b15a4f0f0db592b97511fe5b78fbb8627559a -QAManifestPath 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\b4-v00-practices\QA-SOURCE-MANIFEST-v1.2.json' -QAManifestSHA256 64c8c73173d0475d529388d76a2124466a7bca36d7c304faaeddb3ccc2922469
```

实际 Python runtime 为仓库 `.venv\Scripts\python.exe`，3.12.14；完整 argv/cwd/env 见 `commit-diagnostic-receipt.json`。外层隔离在任何间接 main 导入前生效：test、新 temp DATA_DIR、UTF8、空新教材根、QDRANT 16333、EMBEDDING 127.0.0.1:9；test Settings 与恢复 Settings 的 credentials_file 均 None。全部 HTTP 使用标准 main 的 TestClient；监听新增 0，未启动/停止用户前端或业务服务，未读正式凭证。

执行 UTC `2026-10-02T12:41:08.2173372Z` 至 `12:42:10.7406003Z`，elapsed 62386ms，exit 1，未超时。自有子进程 PID 23340 真正退出，stdout/stderr 流关闭，日志写完后独占读取成功；stdout 28680 字节，stderr 0 字节（实际空文件保留）。完整日志为 `commit-diagnostic-stdout.log` / `commit-diagnostic-stderr.log`。

新自有 OS temp 根保留：`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-p-commit-diagnostic-f17ebade0bec4c2da00f1e3bde75df5a`。109 份逐例 JSON 见 `commit-diagnostic-evidence-index.json`；其中 55 份场景资源记录，每份四库 integrity=ok、foreign_key_check=0，共 220 次四库检查。所有用例主体与 fixture 清理已执行完毕；未删除任何新样本或未知/历史目录。

## 7 项实际失败

| 测试 | 实际结果 / 契约差异 | 持久证据 |
| --- | --- | --- |
| `test_cas_multileaf_reorder_fixed_old_revision_and_real_return_mapping` | 真实练习 → 转原卷/施测 → XLSX 成绩确认 → T70 ready/evidence。原题号 `16(1)`、`16(2)` 在回流证据变成 `16/16(1)`、`16/16(2)`；`自定义-17` 正确，recorded 0 保留。3 行映射、分值和来源在新样本中均已封存，违反 v1.3 完整最终题号规则。 | stdout 首败及 `commit-diagnostic-full-number-readonly.json`；原场景四库资源 JSON |
| `test_reviewed_practice_parent_cannot_reassign_frozen_source_identity[analysis_run_id]` | 已 reviewed 的 practice parent 更新到同 owner 的另一真实 ready run，事务完整 COMMIT 成功，新连接复读仍为新 run，FK=0；冻结历史来源可被重归属。 | `parent-commit-analysis_run_id-b5f5d64b1ce9.json` |
| `test_reviewed_practice_parent_cannot_reassign_frozen_source_identity[subject_id]` | reviewed practice parent 的 math 改为 english，真实 COMMIT 成功、新连接复读 english、FK=0。 | `parent-commit-subject_id-11a00a57a3e1.json` |
| `test_conversion_insert_requires_actual_practice_paper_assessment_owner_source[practice-source]` | 实际已确认原卷/真实新施测保持合法关系，但 conversion 指向另一个 reviewed practice revision；COMMIT 成功、复读错 source、FK=0。 | `conversion-commit-practice-source-f2d71b42501b.json` |
| `test_conversion_insert_requires_actual_practice_paper_assessment_owner_source[owner]` | local practice、paper、assessment 的 conversion owner 写成 other-owner；COMMIT 成功、复读 owner 错归属、FK=0。 | `conversion-commit-owner-cb0e078a93d7.json` |
| `test_same_practice_same_paper_mapping_cannot_swap_valid_source_leaf` | 同一 practice revision、同一已确认新 paper 内，合法 practice item A 映射到合法 paper item B；B 的固定 source_locator.practiceItemId 实际为另一 item。完整 COMMIT 成功、新连接复读错叶映射、FK=0。原卷先经过真实 one-to-one confirm，conversion 与 T30 assessment 亦实际入库。 | `mapping-wrong-leaf-commit-72b89f7853c4.json` |
| `test_initial_practice_subject_must_match_actual_ready_run` | 新 practice set 初始 english 指向真实 ready math run，并建立完整合法 draft/current 指针；COMMIT 成功、复读 FK=0。实际 GET practice 200，返回 subjectId=english，analysisRunId 为 math run。 | `initial-parent-subject-commit-179d1bc112c8.json` |

上表后 6 项的判断均位于 write_transaction 正常退出之后；无主动抛出的断言阻止 COMMIT。它们是提交后的实际语义反例，不是 staging 中间状态。`commit-diagnostic-terminal-results.json` 汇总完整事务终判与复读数据。parent 的 owner_id / id 两项则在真实提交时被 `FOREIGN KEY constraint failed` 拒绝并回滚，两项测试通过，旧轮因主动中断事务产生的误判已经消除。

## 本轮实际通过的范围

完整 64 个测试名和结果保存在 `commit-diagnostic-results-summary.json`，未以修正夹具减少业务断言。

- 目标知识点交集、显式约束、题量不足保持、稳定题面查重、未知难度、未知原题型的六类排原题；教师固定 rid 不能绕过类型/难度/未知难度/原题/查重约束（5 项）。
- 重复完整题号、漏选项、零分计分叶、无 KP、坏 parent 的拒绝与无半草稿；reviewed revision/selection/item/KP 的七类数据库封存。
- asset I/O 在事务锁外执行；archive 交错后发布锁内再次核引用；失败不留下 reviewed 半结果。
- 2 个完整 DOCX ZIP oracle：同字节不同 alias 的 material 合并与同 material id 不同字节不合并；逐 part CRC、XML/OMML、表格、图片、学生卷全包私密文字/图片排除、教师卷实际保留。v1.2 的 bare SHA alias 已真实写入 QuestionBlobStore。
- 模板 accept 时冻结真实 T30 名单；queued registered public retry 真实补调度；新旧 export 的名单区别、学号 leading zero、公式文本安全、完整各叶题号/空分值、attendance/attempt 均实际校验。
- 原包 success replay 先于 archive 引用检查及异包 collision；conversion after-T30 和 mapping-insert 故障实际回滚；export metadata publication 故障/来源资产故障后的真实 public retry、frozen input、无半产物；实际渲染产物遇 cancel/原 lease 丢失无法发布；owner、实际 blob SHA、job state 下载门禁。
- 旧七迁移 literal SHA 不变、新库二次初始化、含实际旧 0007 非空成绩 0 的升级与六类复制/重命名/恢复/registry/FK/integrity 故障回滚和真实重试；真实复合 FK、间接父环门禁。
- 15 个真实 paper practice source confirm 正反边界：来源排他/owner/完整题号/ordinal/questionRevision/内容/分值/KP revision、name、role、增漏项/duplicate source/parent 关系。

## 全 B4 表、资产备份与恢复 HTTP

`test_actual_all_b4_tables_assets_offline_backup_verify_restore` 本轮已完成并通过。标准 main 种子使全部 16 新表非空，包括 T70 evidence/notes、T80 selection/items/KP、conversion/mapping、3 exports/artifacts。活动数据根持锁时实际 backup 被 DATA_LOCK_BUSY 拒绝且无输出目录；标准 app 退出释放锁后实际 create_backup → verify_backup → restore_backup：manifest complete、verify failures=[]、restore ready。

独立全行 oracle 比较全部四库所有业务/迁移表（catalog 16 / question_bank 14 / knowledge 10 / teaching 40 表），所有行完全相等；7 个受管 blob 源/恢复 SHA 一致。之后真实打开恢复根的标准 main TestClient：GET practice 与原包完全相同；3 份 export artifact metadata 与原包完全相同，下载实际 HTTP 200 且字节与原包完全一致；GET returned analysis 实际 reportReady=true；GET evidence 与原包完全相同，1 行 lineage 的 practiceRevisionId 与 practiceItemId 正确。不是以备份完成代替 HTTP 执行。

证据 `all-b4-backup-restore-e8003a184e74.json`、本轮 PASSED 行及 summary。Qdrant 仅使用授权的既有 MockTransport，collections=[]；本结论不扩展为正式向量服务的备份验收。

补充 reconciliation 只用标准库读取已有日志/JSON 与现有新 temp SQLite 的 mode=ro 连接，未导入 app、未增加测试次数。命令、退出 0、实际 stdout/stderr、关闭信息见 `commit-diagnostic-reconcile-receipt.json`；该只读连接已关闭。可执行 QA 自 manifest v1.2 后无修改；结果交 CTRL 后停止写入，等待修复候选及新的执行卡。
