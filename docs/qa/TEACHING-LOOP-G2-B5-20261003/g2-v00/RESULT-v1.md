# G2-V00 独立首轮结果 v1

2026-10-03，北京时间。状态：FAILED_FIRST_RUN_QA_AND_LAUNCHER；G2 保持打开。绑定候选 `CANDIDATE-G2-r1.json`（SHA `454e7bde71864cc4c3e0a276e921ce6537f7dbe9630473936f3b2f541def830e`），构建 `Y6c5E7notWcBElEjX1GF_`。

本记录固定首轮当时事实。全部 9 份可执行 QA 原字节已留在 `run-api-first/source-snapshot/`，原 v1/v2/v3 manifest、HTTP journals、完整 logs/XML、runner receipt 和独立新 TEMP 数据保留。后续 QA 修正必须使用新版本和新 label，不追改本结果。

## 实际执行

| 检查 | 真实结果 | 耗时 / 进程 | 证据 |
| --- | --- | --- | --- |
| 23 unit | 未执行。千余 `--source` 路径展开导致 Windows 在创建 Python 进程前拒绝；runner/Vitest 均未启动 | tool 308.8889ms；PID 无；tool exit 1 | `run-unit-first/LAUNCH-FAILURE-v1.json/txt` 保留全部 requested argv 和原工具报错 |
| 11 API 函数 | pytest 1 failed、4 passed bodies、11 errors、0 skipped、1 warning；门禁失败 | PID 2644；exit 1；8162.86ms；pytest 7.88s | `../ctrl/g2-v00-api-first-command.json`、`.log`、`.xml` |
| 8 browser | 未执行，等待 CTRL 服务身份与新 seed、独立运行卡 | 无 | 不以准备源码冒称通过 |

JUnit 是 12 testcase entries、1 failure、11 errors、0 skipped、7.847s，涉及 11 个不同函数。首例的 body failure 与 teardown error 分别占一条；4 个 passing bodies 同样存在 teardown error，因此完整通过案例数为 0，不写成 4 个独立验收通过。

API 使用 TestClient 真 FastAPI 路由，无 TCP 监听。默认凭证 None，真实环境是新系统 TEMP `zqky-g2-ctrl-g2-v00-api-first-bs90e0a2`；默认教材为空，Qdrant 16333、embedding 9。sourceBefore/sourceAfter 各 886，sourceDrift `[]`，logsClosed true。完整日志 SHA `66cf8dc60e17e19aeaabcff44409570262fd512d4f6b16041c68ef65c5807ec6`；原 argv/env、时间、四库路径与各测试栈见 JSON/原日志。日志完整留存，工具展示截断不代表文件截断。

## 首败与归因

1. 6 个 setup errors 的知识点 HTTP 422 是 QA 把完整函数名用作 seed tag，超出既有 code 64 字符契约。它们没有执行目标业务 body；不据此认定产品行为失败。
2. 5 个 teardown errors 是 QA 调用不存在的 `TextbookCatalog.read_connection`。四库 integrity/FK 尚未完整验证，不能视作通过。
3. 首例已完成首次 PATCH 200（CAS 3→4 / 100 分数单位）、原包重放 200 / replayed true、去 replayed 的响应深等、完整业务及收据快照不变；随后 once-write count 断言把 seed 自身 draft 收据一并计入，得到 2 而失败。原断言保留在 r1 快照；后续仅可把 count 限定原 S1 submissionId/operation，保留一次写和完整不变断言。
4. unit 不是测试红灯；它是启动前的参数长度失败。`LAUNCH-FAILURE-v1.json` 的重建 argv 严格来自被冻结 r1 的 source/QA 路径及当时 PowerShell Sort-Object -Unique 算法，未再启动进程。后续 CTRL runner 将在 `--candidate` 内部读 source/QA hashes，不能再展开千余 `--source`。

4 个 passing bodies 涉及：跨练习身份作用域、真实旧 CAS 的新 submission 冲突、无 submission 422 且不写、其他 owner 404 且不泄露。它们的 teardown 未通过，保留实际断言执行事实但不授予独立验收通过。

没有启动/停止前后端，没有写产品、权威文档、Git 或旧证据；未执行浏览器。待授权 QA v4 停写和 CTRL 新 r2 冻结后，仅在新 TEMP、新 label 重跑原预算。
