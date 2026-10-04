# G2-BE v1 实现与自检结果

2026-10-03，北京时间。状态：**实现自检通过，待 CTRL 稳定候选上的独立验收**。业务源码已经停写；此结果不关闭 G2，不授权提前实施 B5。

实际起点为 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；CTRL 开工基线 SHA `834cc083063e9cf484f46e0787ed199728ca5f39a48ecc57652fab349287342e`。依赖 [G2 契约 v1](../G2-CONTRACT-v1.md) 与 [任务卡](../TASK-CARDS.md)，原 r21 基线和历史审查保持。详细来源及每次实际命令收据见 [RESULT-v1.json](RESULT-v1.json)。

## 实际改动

- `services/practices/service.py`：保存身份为 owner + `practice.draft:{practiceSetId}` + submissionId，hash 固定首次原包并包含原 expectedRevision。成功收据查询先于当前 CAS、审核状态和外部引用/资产预检；PublicationCoordinator 内再次查询并复核引用，`execute_command` 同 teaching 事务再次查收据，随后核 owner/CAS/state，保存业务及原结果收据。重放返回原 `PracticeSetView` 且 `replayed=true`，不重新取当前稿冒充原结果。
- `_prepared` 改为纯 items 内容入口，审核直接传 `draft.draft_items`；不构造假提交 ID，不调用另一次保存。
- `practices_support.py` 为每个新的逻辑保存提供新 ID，实际 HTTP 种子显式传 ID；`test_practices_api.py` 的真正旧 CAS 探针使用新操作 ID，仍要求409。
- 新 `test_practices_draft_replay.py` 覆盖后续另存/审核后的原收据、异包、新操作旧 CAS、对象与 owner 作用域、引用/资产失效后重放、同包并发仅一次写入、收据登记失败回滚及发布前引用归档。

共享 Python/TS 契约由 CTRL 修改；本实现者没有修改共享合同、路由、仓储、迁移、main、提交公共件或 PublicationCoordinator。无无 ID 兼容分支，缺字段422；当前前端必须使用新契约。

## 单轮实际自检

| label | 实际结果 | PID / 外层耗时 | 原件 |
| --- | --- | --- | --- |
| draft-replay-first | 8例：7 passed / 1 failed，exit1，0 errors/skip | 3576 / 4574.045ms | [日志](draft-replay-first.log)、[XML](draft-replay-first.xml)、[命令](draft-replay-first-command.json) |
| practices-related-fixed-first | 5文件：72 passed / 0 failed/errors/skip，exit0；其中新增8、既有64 | 11248 / 24931.869ms；XML23.829s | [日志](practices-related-fixed-first.log)、[XML](practices-related-fixed-first.xml)、[命令](practices-related-fixed-first-command.json) |

第一轮失败为新测试错误信封 oracle 漏掉既有 `details.fields=['expectedRevision']`，实际 error code 与 currentRevision 正确；修正测试明确验证完整既有信封，未改产品。首轮完整源另存 [first-source.before.txt](first-source.before.txt)，SHA `ddf72b34cd8db5f32628afd9a757d6dd02f833eb8e0a798858bad5c74841932b`，与首轮收据 sourceBefore 相符。最终72例是独立的新单轮完整结果，没有拼接首轮7例。仅有既有 Starlette/AnyIO 弃用 warning，未屏蔽。

新增真实 FastAPI/TestClient 用真实四库、迁移、JobEngine、T60→T70→T80种子链。保存1.25→1.00 首写200，将响应视为未送达；发送完全相同原 wire，再返回同 revision/完整业务内容。随后另存3.00，再重放旧包仍返回原1.00收据，而 GET 当前稿保持新版本。原包异体409 `SUBMISSION_CONFLICT`、新操作旧 CAS409、缺 ID422、foreign owner404无当前版本泄漏都实际通过。TestClient没有起 TCP 服务；此项不冒称实际浏览器丢响应已执行。

## 隔离、保全与资源

每个命令在任何 app.main 导入前新建系统临时根，并显式设置 ZQKY_DATA_DIR、ZQKY_ENV=test、PYTHONUTF8/PYTHONIOENCODING、空教材目录、Qdrant16333、embedding9。Settings.credentials_file=None 的默认配置及实际 API scene 均显式验证。没有正式 env/凭证/数据/浏览器草稿访问，没有真实模型/Qdrant调用。

两个根 `zqky-g2-be-draft-replay-first-sqpnehxo` 和 `zqky-g2-be-practices-related-fixed-first-dv2b61nj`、内部 pytest 数据和首败日志全部保留。执行时 runner 把 tempdir 指向本次新根/tmp；实际各仅记录一次同根会话目录的保留清理。执行过的完整 runner 另存 [run_api.py.executed-first.before.txt](run_api.py.executed-first.before.txt)。执行结束后将其保留 override 收紧为拒绝所有根外清理，AST 验证零原 rmtree 调用；该 QA-only delta 见 [RUNNER-RETENTION-DELTA.json](RUNNER-RETENTION-DELTA.json)，不冒称重新跑过业务或修改之前运行事实。

固定72例的四个后端源和共享 Python 契约 sourceBefore/sourceAfter一致，并在结果生成时再核当前字节相符。原三文件开工原字节在 [OPENING.json](OPENING.json) 对应快照中。两个测试 PID 已实查退出；数据库和 TestClient 使用上下文退出，并发线程池已退出；无本次 TCP监听，自有端口不占用，用户进程没有起停操作。[资源收据](RESOURCES-v1.json) 保存只读现场事实。

辅助只读失误保留：准备时猜测两个不存在的包文件，rg归位；结果整理初次猜错 JUnit classname 前缀，读取实际 `tests.*` 后修正生成，不重跑业务。它们未导致产品写入或掩盖测试失败。

未执行：独立 V00、全量 API、check/build、E2E和真实浏览器丢响应/导航链（由 CTRL 在稳定候选上安排）；真实供应商、正式数据迁移、Word/WPS、Qdrant和超基线压力（非此次隔离后端自检）。没有提交、推送、切分支或部署。
