# B5-REVIEW v1：稳定 BE/AI 与 CTRL 公共件初轮静态审查

2026-10-03；独立审查者 `/root/b5_review`。结论：**发现两项 P2 实际代码缺陷，已即时报 CTRL；B5 不可据本静态审查关闭。** 本轮仅静态准备，没有执行独立业务 oracle、候选验收、TCP、模型、迁移或恢复实验。F30-L 尚未停写，不以它的当前状态判失败；稳定候选后继续审查 FE/session/navigation/export。

已完整读取用户原请求、B5 冻结契约及来源装配卡，读取根/API/web/lesson AGENTS、CURRENT_STATUS 和 PROJECT_GUIDE 的相关稳定规则。BE 采用停写 v2（45 作者用例），AI 采用停写 v1（81 作者用例），作者通过仅为审查起点。开工私有 22 文件均与其两份作者清单一致。

## B5R-R01 · P2：合法短数字学号与必发匿名别名碰撞，阻断无个人信息的生成

主位置：`apps/api/app/services/lesson_generation/privacy.py:44-45`；调用与构造位置：`preparation.py:151-152,166,178-179,203`、`service.py:73-74`。

触发：固定 ready 报告有合法 `studentNo="1"`（同样适用于 2..12）；旧教案、要求、教材和题目正文均不含该学号或任何身份标记。`personal_tokens` 将其加入已知身份集合；准备固定使用 `P1`、`K1`、`E1`，且每次都发送 `new:N1` 至 `new:N12`。

预期：只含匿名别名与匿名计数的正常请求可以生成；含明确身份文本（例如 `学号:1`）仍被阻断。

实际：纯数字分支用 `(?<![0-9])1(?![0-9])`，字母/冒号不构成保护边界，因此 `P1` / `K1` / `E1` / `new:N1` 中的 1 均命中。`check_tree(modelPayload)` 或最终 `check_wire` 抛 `LESSON_PERSONAL_INFO`，任务根本无法创建。另最终序列化扫描也会把合法汇总整数 1 当学号；仅修 alias 相邻字母仍不足以保证合法匿名输入通过。

最小静态反例：`check_text("new:N1", ["1"])` 必定命中当前正则并抛错。这是确定性代码推导，**未执行该函数作为独立运行验收**。建议新独立反例同时覆盖学生编号 1/2/12、必发匿名别名、合法班级计数/时长及 `学号:1` 的正阻断，三真实协议最终 wire 都核查；避免结构键、生成别名或纯统计值与人员 token 的偶然字符串碰撞，并保留实际个人信息的阻断。

缺陷源 SHA：privacy.py `9eeb55b5526c8581609f17d26497bb749b9c180618be3614c84f391abb733b69`；preparation.py `01e0c6ad6da6f07c244a379e0adaac07734cf052efe10fc12babc6411a7f16f5`；service.py `4cfb99464922dfad617b5b37795b3f05efb0b192fd57c8b05163e5fe943836ff`。归属 T90-AI，需作者新 v2 候选，旧 v1 收据原件不改。

## B5R-R02 · P2：恢复/启动结构体检将 SQL literal 转小写，漏过语义变更

主位置：`apps/api/app/core/lesson_schema_gate.py:16-17,31`；真实启动接入 `core/database_gate.py:57-60`；恢复接入 `scripts/rag/backup.py:1852-1858`。

触发：一个已登记 0010 的隔离库，重新建立 `lesson_revision_sequence` trigger，仅把原声明中 `NEW.source='ai_applied'` 改为 `NEW.source='AI_APPLIED'`，其他声明和 schema_migrations 登记保持。FK/SQLite integrity 仍可通过。这种场景用于证明恢复体检是否真的发现新结构约束漂移，并非本轮改动真实库。

预期：数据库实际保护声明已改变，启动/恢复拒绝 `DATABASE_SCHEMA_INCOMPLETE`，恢复状态保持 incomplete。

实际：`_normalized` 对整条 SQL `.lower()`，把有语义的字符串常量也折叠；上述两个声明比较相等。API 仍插入 `source='ai_applied'`，改后的 trigger 条件为 false，DB 中基于 proposal 精确 base/CAS/pending 的兜底检查被跳过。类似将表中 source CHECK 枚举转大写，则会让合法保存失败，体检却放行。JSON path 也属于不应被大小写折叠的 SQL 字面量。

最小反例建议：在**新隔离副本**保持 0010 登记 SHA，重建单个 trigger 仅改变该 literal 大小写；assert gate 拒绝，同时直接验证该变化的实际 DB 行为差异。原 trigger lowercase 正例仍须通过。建议保留字面量逐字节语义，只规范化 SQL token 的无意义大小写/空白，或保守精确比较声明。此处同样是静态确定性推导，**没有执行恢复/DDL oracle**。

缺陷源 SHA：lesson_schema_gate.py `cebb4e31d3c0e2527a53acdb4555129e77bf765326f9dfdfc354b37466382c4d`。归属 CTRL，可修公共门控；冻结 0010 DDL 不需改写。

## 已核静态范围与待验边界

本轮已追踪 BE 的 read snapshot receipt/CAS、准备失败重查、publication 外模型/原文、最终同 teaching 事务 receipt 与修订/pointer/decision；五整字段 merge 保留教师六字段；owner/base/version FK 与单次 applied/reject trigger；AI 固定报告单班/KP投影、源快照、三协议 body 构造、严格 JSON/字段/分钟/KP/引用/budget、冻结模型指纹、JobEngine 原租约/heartbeat/取消与同事务 candidate 成功；生产 RagV2 原文 hash/正文区/derived ID、confirmed 固定题和 reviewed 固定练习读口；main 装配/registry/capabilities；版本感知启动与恢复 gate。

这些静态阅读中除上列两项外尚未确认其他具体缺陷；**不表示这些路径已独立业务通过**。完整并发/取消/restart/失租约、来源归档 races、发布失败回滚、备份恢复真实实验、真实浏览器、原本地链、cache/export/nav、check/API/153/14 与视觉均未执行。FE 未停写，只列稳定候选后待检查，不给静态批准或失败结论。正式 .env/.local-data/凭证/草稿/Qdrant/收费模型、产品/原测试/权威 docs/冻结件/Git 均未访问或修改。

源绑定：`SOURCE-BEFORE-v1.json` 绑定 39 件（不存在的 runner.py 仅记录 missing，实际迁移执行在 migrations/__init__.py）；`SOURCE-CTRL-BEFORE-v1.json` 补绑 17 件；终点与任何 CTRL 已登记修复漂移另见 `SOURCE-AFTER-v1.json`。本审查写入仅本目录的新报告/清单。
