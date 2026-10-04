# G2-V00 独立窄复验结果 v3

2026-10-03，北京时间。状态 PASSED_UNIT_API_ONLY_BROWSER_NOT_RUN。绑定 G2-r3 SHA 4cb87b15870799f638c6c48527f8fbed34013ac9c9a74a41ec09d27e42168034、v7 manifest 198c2216564f6a0a2e3e931a4ce5f4c5442b2ad459d605fe170ac7bbd555649c、构建 Y6c5E7notWcBElEjX1GF_。此轮仅独立组件/API窄门禁通过，G2仍待真实浏览器和全部适用门禁，不宣称关闭。

| 检查 | 实际结果 | PID / exit / runner耗时 |
| --- | --- | --- |
| 4文件 / 23组件 | 23 passed、0 failed、0 skipped；4文件通过 | 15520 / 0 / 2712.652ms；Vitest 2.17s |
| 11真实FastAPI | 11 passed、0 failed/errors/skipped；1既有AnyIO deprecation warning | 18704 / 0 / 14043.419ms；pytest13.74s / JUnit13.709s |
| 四库完整性 | 11例×4库=44项 integrity=ok/FK空，所有连接显式关闭 | 11份完整integrity.json |
| 8浏览器 | 未执行，等单独运行卡 | 不以准备/组件/API代替真实浏览器 |

两个门禁各一次、retry0、全新label和TEMP，完整23/11原场景与正确行为断言均保留。本轮 firstFailures=[]。包含原同S1并发双200/一false一true/一次收据与一次编辑、异包冲突/owner、S2后旧S1不回退、receipt失败全回滚等真实HTTP断言。R01完整恢复/明确放弃目标身份等待、R02首次metadata/迟到/高版本与同CAS固定ID等组件场景均通过。浏览器场景尚未执行，不能依据这些结果授予导航真实体验通过。

完整argv/env/PID/ms/logSHAs和全部每例结果见RESULT-v3.json及CTRL原runner receipts。unit显式Node24、no-webstorage，childClosed/logsClosed=true；API在app.main导入前配置隔离env，credentials None，无TCP server，空教材/Qdrant16333/embedding9。API使用TestClient真实HTTP路由，未访问正式env/data/草稿。

unit source886/QA304 before/after零漂移；API source886 before/after零漂移，独立qa-before-v3/qa-after-v3另核QA304前后零漂移。全部before与r3候选hash表相等，next-env前后相同。各新TEMP保留，11份完整HTTPjournal、11份四库integrity、unit JSON、完整logs/XML/receipts保留；9份v7执行源字节在run-api-r3-first/source-snapshot验证冻结hash后留存为.before.txt，没有新增可执行QA。

RESULT-v1/v2和其首败、原源码、logs/XML/TEMP不追改，不用本轮全绿擦除历史并发缺陷或等待缺口。此轮未修改产品/QA、起停服务、操作Git或权威文档。V00已停写；等待CTRL单独浏览器身份/seed运行卡，后续全部必要门禁由CTRL按适用范围确认。
