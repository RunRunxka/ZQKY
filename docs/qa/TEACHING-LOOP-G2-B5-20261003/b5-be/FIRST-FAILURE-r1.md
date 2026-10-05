# T90-BE v1 首败保全 r1

2026-10-03，作者自检，非独立验收。`b5-be-r1-first`：40 tests / 35 passed / 5 failed / 0 skipped / 0 errors，pytest 15.653s；源前后零漂移。

5 个 HTTP 用例均在私有 `tests/lesson_plans_support.py:78` 的 Settings 构造处失败：`TypeError: Settings.__init__() missing 3 required positional arguments: 'host', 'port', and 'allowed_origins'`。未到路由/业务；这是作者样本装配错误。保存/导入/真实并发窗口/事务回滚及三协议真实 serializer+MockTransport 生成应用等 35 例通过，不等于整个 API 已验收。

完整原源码在 `b5-be-r1-first-source-snapshot/`；其中 helper SHA `296d4d90f13a7ad0294ae6731081ec31f930ab52e9ab654ba30f73af6a5c23a5`。全 stdout、XML、命令 argv/env/PID/exit/elapsed/source SHA 在 `../ctrl/b5-be-r1-first.log`、`.xml`、`-command.json`。隔离样本根 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-r1-first-2m8yl78v` 原样保留。

修复仅补私有 helper 显式测试 host/port/allowed_origins；原测试断言保持，另新 label 完整复验。不修改旧 QA 或公共 conftest，不启动 TCP。
