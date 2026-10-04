# B4-V00-P v1.2 — r2 独立修复验收

CTRL 授权后，以原 v1.2 可执行 QA 字节对 `CANDIDATE-b4-r2.json` 运行默认 `-x` 的完整 64 项。实际 **64 passed / 0 failed / 0 skipped / 0 未执行**，exit 0；与上一轮 64 个测试名完全相同，未降断言、未删用例。本任务 T80/shared 独立验收通过，原 7 失败对应 R01–R04 的修复行为均在新样本验证。B4 整体关闭仍由 CTRL 汇总其他独立与适用门禁决定。

冻结候选 SHA256：`665d4857d7da692c753b813a99f028eaab082b6f32bbd3f48c6171e8bfd4e26b`。877 产品源、34 执行 QA、5 共享契约的开工与收尾身份核验无漂移；相较未修复 p4，只有 reader.py、scores/service.py、core/migrations/b4.py 三产品文件改变。本任务 4 个执行源保持 `QA-SOURCE-MANIFEST-v1.2.json` SHA256 `64c8c73173d0475d529388d76a2124466a7bca36d7c304faaeddb3ccc2922469`。first 首败、diagnostic 62 项、commit-diagnostic 64 项及其全部原样证据继续保留。

实际命令：

```powershell
& 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\b4-v00-practices\run-probes.ps1' -Label fixed-first -CandidatePath 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\CANDIDATE-b4-r2.json' -CandidateSHA256 665d4857d7da692c753b813a99f028eaab082b6f32bbd3f48c6171e8bfd4e26b -QAManifestPath 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\b4-v00-practices\QA-SOURCE-MANIFEST-v1.2.json' -QAManifestSHA256 64c8c73173d0475d529388d76a2124466a7bca36d7c304faaeddb3ccc2922469
```

完整实际 runtime/argv/cwd/env 见 `fixed-first-receipt.json`。Python 3.12.14，外层隔离 test/newtemp/UTF8/credentials None/空新教材根/QDRANT 16333/EMBEDDING 127.0.0.1:9 在间接 main 导入前生效。标准 main TestClient 真实 HTTP，未启动监听，未操作用户前端或正式服务/凭证，未执行 Git/build。

UTC `2026-10-02T12:49:37.9497448Z` 至 `12:50:46.6515552Z`；elapsed 68555ms，未超时。自有 PID 24460 已退出，stdout/stderr 流关闭，写完日志后独占读取均成功。stdout 6896 字节、stderr 实际空 0 字节，完整原件 `fixed-first-stdout.log` / `fixed-first-stderr.log`。仅既有 Starlette DeprecationWarning；故障注入用例的发布失败 warning 属预期内部日志，不影响真实重试断言。

## 原反例的新候选行为

| 台账组 | 实际新轮验证 | 证据 |
| --- | --- | --- |
| R01 完整题号 | 真实练习 → T30 原卷/施测 → T60 XLSX 成绩 → T70 ready/evidence。`自定义-17`、`16(1)`、`16(2)` 原样返回，分值 0/75/25；无重复父前缀。旧 reviewed 版本在复制新 draft 后不变，四节点一一映射的 qrev/parent/content/KP 固定事实全部相同。 | `fixed-first-evidence/multileaf-real-return-f79ce4ff12a8.json`（含真实 HTTP 原包）；`fixed-first-full-number-readonly.json`（新 temp 的 3 行实际 SQLite mode=ro 复读） |
| R02 父身份/初始学科 | parent analysis_run_id、subject_id、owner_id、id 均被 IMMUTABLE_REVISION 拒绝；初始 english → ready math 被 PRACTICE_SOURCE_MISMATCH 拒绝。事务正常失败回滚后新连接复读，原对象仍保留、错对象无记录、FK=0。 | `fixed-first-terminal-results.json` 的 4 parent 与 1 initial 记录 |
| R03 conversion 来源与 owner | 使用两端各自真实合法 FK 的错 practice source、other-owner 两种 conversion 插入均被 PRACTICE_CONVERSION_SOURCE_MISMATCH 拒绝，回滚后不存在该 row，FK=0。 | 同 terminal results 的 2 conversion 记录 |
| R04 同卷错叶 | 同 practice/same confirmed paper 的 A → B 互换被 PRACTICE_ITEM_MAPPING_MISMATCH 拒绝，回滚后 insertedMappings=[]，固定 B source locator 仍指向 B，FK=0。合法确认/转换路径先实际完成。 | 同 terminal results 的 mapping 记录 |

原始 7 反例对应的全部用例 PASSED，8 个真实事务边界结果全部 rejected=true/committed=false。未用主动抛断言阻止 COMMIT。逐项 PASSED 名称与准确计数见 `fixed-first-results-summary.json`。

## 原 64 项的其他适用回归与备份恢复

原 64 项中的显式约束/未知难度与未知原题型排原题、教师固定 rid 五边界、计分结构无半草稿、七子表封存、事务锁外资产 I/O + 发布内引用复核、两完整 DOCX ZIP 私密信息/公式/表格/图片/material identity、真实名单模板冻结与 registered queued public retry、原包 replay/collision、实际 conversion/export 故障回滚与 public retry、取消/原 lease 失效封存、实际下载 owner/blob/job state 门禁，全部重新通过。

旧七迁移 literal SHA、新库初始化二次、真实带数据旧 0007 升级及六类故障回滚/重试、复合 FK/间接环、15 个严格 paper practice source confirm 边界全部在新隔离样本重新通过。旧首败及旧试验库未替代新轮证据。

全 B4 表备份恢复用例实际 PASSED：16 新表全非空，活动锁内 backup 实际拒绝，退出标准 app 后实际 create_backup/verify/restore；complete / failures=[] / ready；四库全部表逐行完全相同（16/14/10/40 表），7 受管 blobs 源/恢复 SHA 相同。恢复根标准 main TestClient 实际执行 GET practice exact、3 artifact metadata exact、3 次 HTTP 200 下载字节 exact、returned analysis ready、1 行 evidence/lineage exact（含固定 practiceRevisionId/practiceItemId）。Qdrant 是授权既有 MockTransport，collections=[]，不宣称正式向量服务验收。完整原包 `fixed-first-evidence/all-b4-backup-restore-e8003a184e74.json`。

110 个逐例 JSON 及其 SHA/长度见 `fixed-first-evidence-index.json`；55 场景四库 integrity/FK 共 220 次均 ok/0。新自有 temp 根完整保留：`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-p-fixed-first-009e2be429874854ba0632c946df8f2c`。没有删除未知、历史或本轮失败样本。

收尾补充只用标准库读现有日志/JSON 和新 temp SQLite mode=ro，不导入 app、不新增测试、不写执行源；`fixed-first-reconcile-receipt.json` 保存实际命令、stdout/stderr、elapsed/exit0/流关闭，SQLite 连接已关闭。完成仅证据文字/JSON后停写，交 CTRL 独立验收范围通过。
