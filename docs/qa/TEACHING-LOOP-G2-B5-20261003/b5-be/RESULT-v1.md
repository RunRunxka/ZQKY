# T90-BE v1 结果卡：作者自检通过，待独立验收

2026-10-03；负责人 `/root/g2_be`。按 CTRL 正式卡实施，G2 已关闭才编码；起点/共享基线由 CTRL 开工证据提供，不做 Git 写操作。

开工核对 `ctrl/B5-CONTRACT-FROZEN-v1.json` 的 33 个文件全部匹配，manifest SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db`，见 [OPENING.json](OPENING.json)。本卡不宣称 B5 独立验收、全 API 或浏览器门禁已经完成。

## 实际实现与写入范围

新增 `apps/api/app/repositories/teaching/lesson_plans.py`、`services/lesson_plans/{__init__,service,context,views}.py`、`api/v1/lesson_plans.py`；新增私有 helper `tests/lesson_plans_support.py` 与四个 `test_lesson_plans_{storage,proposals,api,concurrency}.py`。只另写本批 `b5-be/` 证据。未改共享 DTO/DDL/JobEngine/Registry/PublicationCoordinator/main/公共 reader/旧测试/旧 QA/权威文档/Git。

全部 12 条冻结业务路由可用：list/create/import/read/save/history/fixed revision/evidence verify/generate/proposal detail/apply/reject。列表为摘要，不重复发送正文；body 严格 DTO、完整原始请求 2 MiB 上限；只本模块路由将 RequestValidationError 转 `VALIDATION_ERROR`，issues 不回显输入。该修复已由 CTRL 明确批准，其他模块公共 handler 不变。

保存/导入冻结深拷贝原包；仅导入 updatedAt 排除请求/来源意义 hash，完整原 envelope 首次写入原样保存。固定学科/班级与 ready 报告/score/paper/KP 修订；保留历史 null 班名，classNameAtSave 单独取当时标签。当前同内容/上下文/来源/来源意义去重；A→B→A 新增历史版本。review 初值 unreviewed，本批没有审核 endpoint。

receipt 与 owner/CAS 预检读取同一 SQLite read transaction；外部准备失败在协调区重查原 receipt；最终协调区先 receipt，再 SQL-only active refs，再 execute_command 短事务。异包 409、跨 owner/跨 document 404。generate 的 job/input/receipt 同事务，注册真实 AI factory，uses_model=True。apply 重验固定 candidate 和教材原文，whole-field 选择后一次写不可变 revision、head/CAS、terminal decision 和 receipt。教师六字段及未选字段保持；仅选择 process 时带相应分钟/依据元数据；partial 首次应用即 terminal。reject 包含 stale 候选但不改正文。原成功 receipt 不回退后续版本，亦不因后来模型/资产/归档变化失效。

## 自检执行与首败

每轮命令为仓库根 PowerShell `powershell -NoProfile -File docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-be/run-self-tests.ps1 -Label <label>`，内部固定 `apps/api/.venv/Scripts/python.exe ctrl/run_b5_api.py --label <label> --source ... <私有测试文件>`。完整实际 argv、进程 PID、env、开始/结束、exit、单轮 XML、日志 hash、源前后 SHA 均在每轮 [ctrl command receipts](../ctrl/)；不以口述 argv 代替收据。

| 单轮 label | PID | exit | passed / failed / error / skipped | 整命令 ms | pytest s |
| --- | ---: | ---: | --- | ---: | ---: |
| b5-be-r1-first | 23892 | 1 | 35 / 5 / 0 / 0 | 16776.540 | 15.653 |
| b5-be-r2-settings | 4464 | 1 | 39 / 1 / 0 / 0 | 21601.600 | 20.431 |
| b5-be-r3-validation | 26196 | 0 | 40 / 0 / 0 / 0 | 18737.443 | 17.602 |
| b5-be-r4-concurrency | 24772 | 0 | 44 / 0 / 0 / 0 | 20052.202 | 18.851 |

四轮 sourceDrift 均为空；每轮执行前全源码字节快照 `<label>-source-snapshot/` 与该轮 sourceBefore 逐项散列核对，也零漂移。首败全 stdout/XML/输入/原源码/隔离库保留，不覆盖失败后输入。

r1 的 5 例均在作者 helper 缺 Settings 的 host/port/allowed_origins 处失败，未进入 HTTP 业务；只补私有样本参数，详见 [FIRST-FAILURE-r1.md](FIRST-FAILURE-r1.md)。r2 唯一失败是被冻结正确断言发现全局校验码为 INVALID_REQUEST，按 CTRL 授权在私有路由修成 VALIDATION_ERROR；原断言未弱化，详见 [FIRST-FAILURE-r2.md](FIRST-FAILURE-r2.md)。最终新增的未覆盖边界是 generation/apply/reject 同包并发和原调用体嵌套列表突变防护，4 例全部通过。

这些是实际迁移 SQL/catalog/ready report/production RagV2 reader/JobStore/JobEngine/PublicationCoordinator/三协议 serializer 的作者测试。模型 HTTP transport 和 embeddings 为显式隔离替身，不请求收费或本机模型。API 用标准 create_app、错误中间件和本模块 router，样本注入 LessonPlanService；CTRL main 装配与整体服务使用仍需独立验收，不把样本注入等同完整上线。

每轮有一条已存在 Starlette/anyio BlockingPortal deprecated 警告；没有测试 skipped，不称零警告 lint。文档 metadata 写入曾有一次 PowerShell 单引号语法错误（exit1、stdout 空、没有 app 导入或文档落盘），随后独立私有 writer 脚本成功；非业务测试失败，不计入上表。

## 隔离与资源

runner 在 app.main 或 pytest 间接导入之前创建新 OS TEMP，显式 ZQKY_DATA_DIR、ZQKY_ENV=test、PYTHONUTF8=1、PYTHONIOENCODING=utf-8、PYTHONDONTWRITEBYTECODE=1、KEEP_TEST_DATA=1，Settings.credentials_file=None、空教材根、Qdrant 16333、embedding 9。--basetemp 为该轮新 TEMP/pytest，不触其他/旧根。节点命令未使用。

各 TEMP 原样保留：

- r1 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-r1-first-2m8yl78v`
- r2 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-r2-settings-d4e1g693`
- r3 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-r3-validation-cxgbkjtp`
- r4 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-r4-concurrency-87ls7mak`

catalog 每次读写 context 结束关闭连接；异步 fixture finally 关闭 ManualEngine、AI 场景 JobEngine、RagV2 并关闭目录对象；TestClient 离开关闭 app lifespan。公共 conftest 生命周期保留，runner 仅对当轮已核绝对 containment 的 TEMP 保全清理请求，不删旧/未知根。全部日志已关闭；没有 TCP server、前端起停、build、浏览器草稿、正式数据、凭证、远程或 Git 操作。

## 来源与交接

11 个实际私有实现/测试文件 SHA、四轮完整收据绑定及停写时点见 [MANIFEST-v1.json](MANIFEST-v1.json)，manifest SHA `6a55635aa7bc168907daa1b7740c78c61caa9d1a27b91439a679a3d809b80088`。服务主文件 SHA `380b07b018b30bb73f02e1d0f083c72bdc7609f34158ecde2f72f7badff757cd`；router SHA `96669750d9185472344c7ed09442ede944155700be3c61f8e05840038151d614`；repo SHA `85e741b79d1b2560b04d5a3e1843a494f26b3498df9782eed1ec45306fc3eed7`。

产品与私有测试已停写，待 CTRL 候选与 V00。未执行：独立 V00、完整 check/full API/全 e2e/chat、浏览器视觉、正式迁移、备份恢复完整实验、真实供应商教学质量及真实 Word/WPS 手工排版。这些由对应卡/CTRL 后续执行，作者结果不冒称通过。公共依赖端口缺口已由 CTRL 解决，本卡没有阻塞项。
