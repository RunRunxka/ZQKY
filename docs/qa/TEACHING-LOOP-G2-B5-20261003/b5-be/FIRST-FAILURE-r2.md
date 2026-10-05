# T90-BE v1 首败保全 r2

`b5-be-r2-settings`：40 tests / 39 passed / 1 failed / 0 skipped / 0 errors，pytest 20.431s；源前后零漂移。唯一失败是 actual HTTP extra-owner 字段拒绝时，422 的 code 为原全局 `INVALID_REQUEST`，B5 冻结契约与原正确断言要求 `VALIDATION_ERROR`。

已进入业务的 create/import/save/list/history/evidence/generate/apply/reject、HTTP 同包并发与原文/Unicode/大小边界均通过。不能据此称整批 API 或主装配已验收，样本服务通过显式注入覆盖装配对象。

原源码字节完整保存在 `b5-be-r2-settings-source-snapshot/`；原测试不改，原 route SHA 见该 manifest。完整 stdout/XML/argv/env/PID/exit/elapsed/source 在 `../ctrl/b5-be-r2-settings.log`、`.xml`、`-command.json`。样本根 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-r2-settings-d4e1g693` 保留。

CTRL 已明确批准只在 BE 私有 BoundedLessonRoute 捕获 RequestValidationError 转冻结 `VALIDATION_ERROR`，issues 只给字段位置与原因、不回显 input；不改公共 handler 或冻结 DTO/DDL。修复后另新 label 完整复验。
