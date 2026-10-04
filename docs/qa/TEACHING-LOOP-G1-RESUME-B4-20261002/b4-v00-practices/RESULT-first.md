# B4-V00-P v1 · 首轮独立验收首败

结论：未通过。真实多叶练习转换、新 T60 教师成绩与新 T70 ready 报告完成后，证据 `itemPath` 重复套父题号，违反 B4-CONTRACT-v1.3 的完整最终题号约定。练习/转换 paper 均为 `16(1)` / `16(2)`，实际证据为 `16/16(1)` / `16/16(2)`。没有修改产品或降低断言。

冻结候选 `CANDIDATE-b4-p1.json` SHA `648c6c7edf7351edbb549405f0173cd2effd361a7480605c359d44cdbe0712d7`；运行 QA 清单 `QA-SOURCE-MANIFEST-v1.json` SHA `4663504aa78860872e755710cb714c5698b4f23b7d6056a67d57b86f93703d12`。runner 检查运行前后全部产品、可执行 QA 和共享契约身份均 unchanged。

本轮 11 pass / 1 fail，`-x` 停止，余 50 项未执行。已通过正式题约束/缺口/六题型未知原题排除、手动固定题反约束五种变体、重复完整题号/漏选项/零满分/无 KP/失效 parent 等五种结构。失败用例前半段完成 CAS 与审核旧版不变、真实四节点转换的全 parent/number/qrev/rich/KP 集合对账及新 T60 计分、ready 报告；由于中途首败，不能把此完整用例标通过。

实际启动命令为本目录 `run-probes.ps1 -Label first`，其余五参数的绝对值见 `first-receipt.json` 中 candidate/QA 路径及 SHA。Python 实际绝对 exe、全部参数、cwd、外层 test/新 temp/UTF8/空教材/16333/embedding9 环境也见该收据，不用概略命令代替完整运行身份。退出 1、总进程 14172 ms、未超时；Python PID 17780 实际退出，stdout/stderr 流关闭后日志独占读取成功。stdout 6957 字节、stderr 明确为空（0 字节）。仅 TestClient，无监听/前端操作/Git/正式凭证读取。

新根保留：`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-p-first-2eeb20c6edfd4718ab858c85e7c385ef`。各 12 个实际运行 fixture 的四库 integrity ok/0FK 和隔离资源收据均在 `first-evidence`。首败 fixture 实际数据库保留于该根 `pytest/test_cas_multileaf_reorder_fix0/data/teaching/teaching.sqlite3`。只读提取按真实 submission/run 找回三叶、全部映射、成绩 cells、ready evidence/item snapshots，证明两个子题同错误、单叶自定义题号正常；完整数据见 `first-counterexample-readonly-r2.json`，连接已关闭、0FK/integrity ok。

只读提取的第一次命令错用了列名 `payload_json`，exit 1；原命令/stderr/空输出均保存。第二次改用实际 `snapshot_json`，exit 0 / 103 ms，完整命令见对应 r2 收据。两次均只读原失败新根，无新业务测试，不改数据；不得把第一次提取失败当产品失败或删掉。

未执行：审核所有子表封存、发布锁与归档交错、DOCX 全 ZIP/富图片材料 identity、真实名单 XLSX、原包未知成功重放、导出失败/取消/旧租约、owner/hash/终态闸门、转换故障、父对象来源重归属、共享旧七 hash/迁移 fault、完整 16 新表与资产 backup/verify/restore，因冻结 QA 的 `-x` 首败停止。未宣称 B4、真实 Qdrant、Word/WPS 排版或真模型质量已验。

证据索引：`first-receipt.json`、`first-stdout.log`、`first-stderr.log`、`first-evidence/*.json`、`first-counterexample-readonly[-r2].json`、对应 readonly 两轮 command receipt/stderr、`QA-SOURCE-MANIFEST-v1.json`。首轮和原 manifest 保持原件。CTRL 随后仅授权准备 runner v1.1 `CollectAll`：测试与 oracle 三个 `.py` 原字节保留，诊断全轮须重新冻结并获得执行指令，不是修复后验收。
