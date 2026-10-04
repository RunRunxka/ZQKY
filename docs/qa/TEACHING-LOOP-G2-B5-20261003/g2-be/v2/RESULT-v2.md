# G2-BE v2 结果卡

负责人：G2-BE。状态：**待独立验收；实现已停写**。本卡不关闭 G2，不启动 B5。

r2 独立 11 例为 10 通过／1 失败：完全相同 deep-copy 请求返回 409 `REVISION_CONFLICT`／200。首败由 CTRL 保留于 [g2-v00-api-fixed.log](../../ctrl/g2-v00-api-fixed.log)。修前服务与测试原字节已按 r2 候选 SHA 核对并保存于 [OPENING.json](OPENING.json)，旧证据不覆盖。

## 修复与原理

`save_draft` 早期回执读取为空后，旧实现以另一读取事务取得新 CAS，因而在另一同包请求已提交成功时误报旧 CAS。本次增加私有 `_replay_in`：回执查询与 owner／CAS／state 预检使用同一 `TeachingCatalog.read_connection` 明确 BEGIN 快照。该快照不能只看见新业务值而看不见同事务提交的回执。准备题目和图片时已退出读取事务，且仍在发布锁外。

资产准备抛错时，在既有 PublicationCoordinator 内再查原回执；已提交同包回放原结果，没有回执则重新抛出原异常，异包保留 409。原发布前回执／引用复核和 `execute_command` 写事务内回执／CAS／state 复核继续保留，业务保存与回执仍同一事务。使用原进程内协调器，没有新增锁，不宣称跨进程或跨库原子性。

只改 `apps/api/app/services/practices/service.py` 与 `apps/api/tests/test_practices_draft_replay.py`。原 8 例测试前缀字节保持完全一致；新增 7 例覆盖早期 miss 后保存／审核、读快照中间提交、实际图片 IO／校验失败后的成功回执、无回执时原异常，以及真实 FastAPI HTTP ASGI 栈下同包并发。

## 实际自检

| 单轮 label | 用例 | 失败 | exit | wall ms | PID |
| --- | ---: | ---: | ---: | ---: | ---: |
| r2-author-reproduction-first | 5 | 5 | 1 | 3665.933 | 19848 |
| draft-replay-v2-fixed-first | 15 | 0 | 0 | 7139.421 | 22132 |
| practices-related-v2-fixed-first | 79 | 0 | 0 | 27048.784 | 21420 |

首轮为**有意使用 r2 原服务的应红复现**：两例早期 miss 后 `REVISION_CONFLICT`、两例原资产 IO／校验异常，以及真实 HTTP 200／409；完整 5 个首败、全部输入原字节、XML／log／样本根保留于 [r2-author-reproduction-source.json](r2-author-reproduction-source.json)。随后修复首轮 15／15，再相关 5 文件 79／79，均 0 错误／跳过，不弱化断言。

79 例包括 selection 28、review/export 21、conversion 14、API 1、draft replay 15，即原 72 例加 7 个新窗口。三轮命令所记 sourceBefore 与 sourceAfter 完全一致。完整修后输入见 [FIXED-SOURCE-v2.json](FIXED-SOURCE-v2.json)；3 个未改原回归文件另与 r2 候选 SHA 核对并冻结。私有 runner 不逐项枚举动态导入文件，整仓归属以 CTRL 候选为准。

- `r2-author-reproduction-first`：`C:\Users\96022\AppData\Local\Temp\zqky-g2-be-v2-r2-author-reproduction-first-2pfqsudq`，完整 argv／env／源码前后 SHA／时间见 [r2-author-reproduction-first-command.json](r2-author-reproduction-first-command.json)。
- `draft-replay-v2-fixed-first`：`C:\Users\96022\AppData\Local\Temp\zqky-g2-be-v2-draft-replay-v2-fixed-first-phlonoft`，完整 argv／env／源码前后 SHA／时间见 [draft-replay-v2-fixed-first-command.json](draft-replay-v2-fixed-first-command.json)。
- `practices-related-v2-fixed-first`：`C:\Users\96022\AppData\Local\Temp\zqky-g2-be-v2-practices-related-v2-fixed-first-bynocwnm`，完整 argv／env／源码前后 SHA／时间见 [practices-related-v2-fixed-first-command.json](practices-related-v2-fixed-first-command.json)。

每轮在 `app.main` 导入前新建 OS 临时根，显式设置 `ZQKY_DATA_DIR`、`ZQKY_ENV=test`、UTF8、credentials None、空教材目录、Qdrant 16333 与 embedding 9。保留器只接受该新绝对根及其子路径，根外清理直接拒绝。测试使用真实路由／业务／四库／回执和实际图片，不启动 TCP、模型或 Qdrant。ASGI TestClient 自检并非独立 TCP 门禁。每轮有现存 Starlette AnyIO deprecated 警告 1 条。

## 资源与证据保全

三轮 PID 19848／22132／21420 已退出；ThreadPoolExecutor、TestClient 与数据库上下文均结束，样本根刻意保留。只读资源核查显示 8001／8002 无监听，5174 仍由 CTRL 的 PID 19604 持有；BE 未启动／停止／重启服务，见 [RESOURCES-v2.json](RESOURCES-v2.json)。旧私有 v1 manifest 的 18 个证据逐项 0 漂移。

## 未执行与下一动作

**未执行**独立 V00、实际 TCP、浏览器／e2e、整套 API、npm check／build／chat、B5 与 Git 操作：不属于本私有修复卡，需 CTRL 冻结新候选并按适用门禁接续。G2 仍须独立复验和总控确认。

服务 SHA：`497fa7df1c66f40aa205e4e723872f6c0f8c2ef32560397b53b6ae0e538eaca2`。

测试 SHA：`7e89f70751bebc199d4ab1b1484426c489c4232f2a62bd8f44ea2318aa6106ea`。

原异常、首败明细、每轮完整 argv／env／PID／exit／毫秒／源与资源关闭均见 [RESULT-v2.json](RESULT-v2.json)。两次只读定位猜错路径及一次辅助终端中文编码显示问题已记入 JSON；未改源码或原日志来掩盖，UTF8 重读确认 XML 原字节正确。
