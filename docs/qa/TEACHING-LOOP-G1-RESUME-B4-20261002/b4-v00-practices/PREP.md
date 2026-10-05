# B4-V00-P v1 独立验收准备

负责人此前编写 T70，本轮只独立验 T80 及 CTRL 共享基础；不把 T70 作者自检或聚合实现作为独立 oracle。仅复用 `tests.practices_support.open_api_scene` / `seed_api_loop` 做真实标准 main HTTP 业务种子。其余断言、固定数字/分数、完整来源逐项对账、SQLite 逐行备份恢复、ZIP CRC 与 XML 检视均由本卡单独编写。Qdrant 仅用授权的现有 MockTransport；无真实向量服务、Word/WPS 排版或真模型质量结论。

阶段：可执行 QA 已准备，**独立测试尚未执行**。等待 CTRL 冻结 QA 身份、最终候选与执行指令。所有可执行源在提交 SHA 后停写；产品、作者测试、共享契约、既有 G1 QA、前端、端口与 Git 均未写或启动。

源码四文件：`probe_support.py`、`test_independent_practices.py`、`test_independent_shared.py`、`run-probes.ps1`。静态按参数展开预计 62 项，未通过 pytest collection 确认，不能当作已执行计数。

覆盖安排：

- 正式固定题型/难度/未知难度/多 KP 单题、真实缺口/去重和未知原卷题型六合法匹配；手动固定 rid 反约束在保存或审核拒绝，允许编辑态持有错误待审时必须明确仍为 draft。未以题量不足本身判断产品失败。
- CAS、审核修订和子表 INSERT/UPDATE/DELETE 不可变、递归父环与真复合 FK；真实发布锁外读资产、归档交错、锁内复核与无半审核。
- 多叶真实完整题号及重排，固定旧版与新草稿；两 DOCX 全 ZIP/CRC/EOCD、全解压部件私有文字/私有图片扫描、OMML 分式、合并表格、选项与受管图片；材料图相同 SHA 不同资产别名去重、同 material id 不同 SHA 分别保留。
- 实际 T30 名单接受时冻结、领先零与公式样姓名文本、各叶完整题号与固定映射 XLSX；公共已注册 queued 补调度/failed 重试，冻结输入不替换。
- create/review/conversion/export 真成功响应原包重放、归档后仍先重放、异包冲突；资产故障与发布 file_asset 后故障无 metadata 半件；取消与原租约失权后实际算出的导出不发布；实际下载 owner/hash/终态闸门。
- 转换 T30 后故障及 mapping INSERT 拒绝，全部 12 相关表计数不变；真实新 T60 XLSX→新 T70 report 按全部 3 计分叶逐行核 questionNo 路径、原练习 item、paper item、父映射、固定 qrev、全 rich/KP 和分数来源。
- 父 practice 对同 owner 另一个真实 ready run/学科/owner/id 的 SQL 重归属、conversion 的 practice/paper/assessment/owner 来源错配；若候选接受则保存反例并首败停止，不修 DDL。
- 旧七迁移声明 literal SHA、真实新库二次无增量、含已确认原卷/成绩及 active 指针的 0007 全行保留；0009 copy/rename/restore/registry/两行 FK/第二行 integrity 故障的回滚、触发器恢复、FK ON 和真实重试。
- 真实标准 main 种子使 16 个 B4 新表全部非空及真实受管资产；存活 API 数据锁拒绝备份，退出后实际 backup→verify→restore；四库全部表逐行相同、所有新表非空、0FK/integrity ok、所有源 blob SHA 相同、恢复后实际 HTTP 下载字节/report/lineage 可读。

运行入口必须给唯一 label、CTRL 冻结 candidate/QA manifest 及各自 SHA。脚本在任何 indirect app.main 导入前用全新 OS temp 设置 env=test、UTF8、credentials None 所属 test 设置、空教材、16333、embedding 127.0.0.1:9；不监听。stdout/stderr 完整捕获，先等待实际 Python 子进程退出和流关闭，再独占打开日志验证释放，留下准确 receipt、所有新 temp 与 evidence，不覆盖首轮或删除未知目录。pytest `-x` 遇首败停止相关验收；未到达项如实 not_run。
