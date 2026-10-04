# B4-V00-P · 同源完整诊断，非修复验收

本轮完整 62 项：51 pass / 11 fail，未通过。只按 CTRL 显式诊断授权使用 `CollectAll` 省略 `-x`，全部原断言保持。候选 `CANDIDATE-b4-p3.json` SHA `8ea093a39349d046b3f8169344453f74d62424c12ff208dfaf21257bb553b67c`，877 产品与 p1 完全同源；16 可执行 QA/配置及全部共享契约在运行前后均无漂移。执行 QA manifest v1.1 SHA `4c318b6de20f0bf4462eabf635af095b7b9ca75ee5610714c800a95b70a2dc7f`。

失败归因逐项如下，不能把 11 fail 全算作 11 产品缺陷：

| 失败用例 | 真实观察与归因 |
| --- | --- |
| 多叶新 T60→新 T70回流 | 产品反例：源 practice/paper 是完整 `16(1)`/`16(2)`，证据重复父前缀；首轮及本轮均实际复现，违背 v1.3。 |
| 相同 SHA 不同 alias 的 DOCX | QA 种子漏写 legacy QuestionBlobStore：仅 global assets 有同字节，bare SHA reader 按原约定读题库 blob 报 `QUESTION_BLOB_MISSING`，未到达材料去重/整包 oracle；不归产品。不同 SHA 同 material ID 的完整双 DOCX/私有图片扫描实际通过。 |
| 名单模板 | 实际 queued 公共 retry、接受时名单冻结、新名单导致新 inputHash、完整题号与旧 XLSX 文本通过；QA 对随机 participant ID 排序误假定新学生恒在第 3 行。应按实际学号定位，保留全文字/leadingzero/空叶单元格断言，不归产品。 |
| 未知成功原包重放 | 四类成功原包在题/KP归档后实际重放、异包409全部先通过；后续新请求正确 `409 KNOWLEDGE_ARCHIVED`，QA 错写422，不归产品。 |
| 父 practice.analysis_run_id | 同 owner 另一真实 ready run 可完成 UPDATE 阶段，存在历史来源被重指风险；本轮 QA 提前自抛断言导致主动 rollback，必须下一轮真实 COMMIT 终判，当前不冒充提交级结论。 |
| 父 practice.subject_id | math 源可 UPDATE 到 english；同上，待真实提交终判。 |
| 父 practice.owner_id | TeachingCatalog 使用 `defer_foreign_keys=ON`，QA 在提交前自抛断言；可能由真实 COMMIT FK 拒绝，不能据此报产品缺陷。 |
| 父 practice.id | 同上，已知原 revision→parent FK 应在提交核验，当前 probe 终判过早。 |
| conversion practice-source | 两端 FK 各自合法、不同 source practice/paper 组合可 INSERT 到阶段；同上待真实提交终判与错配明细，当前保留反例，不宣称已提交。 |
| conversion owner | 可阶段 INSERT 不同 owner，当前同上待提交终判。 |
| 全 B4 backup/restore | backup complete、verify无失败、restore ready、四库全部表逐行相同、全部16新表非空、全部源 blob 字节与 SHA相同实际通过；QA恢复 HTTP Settings漏 required allowed_origins，TypeError后未到达恢复API。不归产品，也不把整项标通过。 |

已通过的 51 项逐例列表见 `diagnostic-results-summary.json`。包括固定正式题约束与手动反约束、结构重复完整题号等拒绝、审核三个子表全部 INSERT/UPDATE/DELETE 封存、锁外资产 IO 与锁内归档交错复核、转换 T30 后和 mapping insert 故障 12 表无半件、导出资产故障/metadata发布故障与真实 registered 公共 retry、原租约失权和取消后实际算出的导出无发布、真实 owner/hash/job终态下载闸门、旧七 literal hash/新库/填充0007升级与六个 rebuild 故障回滚、复合 FK/三节点循环，以及严格 paper-practice 确认来源 15 种正确/错配分支。

实际运行入口 `run-probes.ps1 -Label diagnostic -CollectAll`，完整绝对命令参数、cwd、隔离环境、candidate/QA SHA在 `diagnostic-receipt.json`；Python PID24188已退出、两输出流关闭后日志独占读取成功。exit1 / 总进程59242 ms、未超时；stdout37207字节、stderr明确0字节。各 TestClient 已结束，无监听或用户前端操作、无Git、无正式凭证。新 OS root：`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-p-diagnostic-3c5ec23caccb43bebfe6040127918f65`，全部保留。

备份只读补证据 `diagnostic-backup-readonly.json` / 对应完整 command receipt：对已经生成的源库和恢复库独立逐行读取，不开应用或再跑业务；8个只读连接全部关闭、每库0FK/integrity ok，11归档文件真实SHA/字节长度核对，7源blob字节相同。16新表计数为：analysis_runs/participants/item_snapshots/evidence各2，student_results/class_results各4，teacher_notes1，practice_sets/revisions/selections/items/conversions/mappings各1，item_knowledge2，practice_exports/export_artifacts各3。Qdrant仍仅授权MockTransport，空 collections 场景，不冒充真向量或非空教材索引恢复。

证据索引：`diagnostic-receipt.json`、完整 `diagnostic-stdout.log` / `diagnostic-stderr.log`、`diagnostic-evidence/*.json`（包括六个 staged SQL反例）、`diagnostic-results-summary.json`、`diagnostic-preflight-audit.json`、`diagnostic-backup-readonly.json` / receipt / stderr。preflight 的两个 count 字段受 PowerShell 属性枚举影响写成一串1，原件保留；summary 明确其真实长度877/16，不改写原审计。所有 first 原件与原源码保持；v1.1执行源码另有四个 `.v1.1.before.txt` 完整原字节副本。

CTRL 已授权 QA v1.2，仅修上述明确夹具、真实 COMMIT/失败ROLLBACK 终判，并追加同卷合法 A→B 错叶映射、初始 practice 学科与实际 ready run 绑定两个探针；准备后重新冻结，不能自行执行。下一轮仍对未修改产品作诊断，不是修复验收。真实 Word/WPS、正式服务迁移、真模型与真Qdrant未执行。
