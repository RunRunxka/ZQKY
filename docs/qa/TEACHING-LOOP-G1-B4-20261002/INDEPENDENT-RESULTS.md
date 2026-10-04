# 新独立验收索引

实现者全停写；独立验收只写新QA目录，CTRL也不修改冻结产品。g1-r1共825项，g1-r2只补安全.env.example配置，共同825项不变，当前完整826项及旧629证据后验零漂移。

| 独立任务 | 正确行为结果 | 边界与证据 |
| --- | --- | --- |
| G1-V00-JOBS | 一次52passed/0fail/skip，6.10s，exit0；R05/R06 pass | [RESULT](v00-jobs/RESULT.md)、[r2覆盖补审](v00-jobs/ADDENDUM-r2.md)、52条真实SQLite/ASGI收据；未重复运行52例 |
| G1-V00-SCORE-QB | 一次53passed/0fail/skip，16.15s，exit0；R04/R07正确行为 | [RESULT](v00-score-qb/RESULT.md)、[最终日志](v00-score-qb/accepted-v2.log)、[XML](v00-score-qb/accepted-v2.xml)；独立夹具前置/结果字段首败原文保留 |
| G1-V00-FE | 一次20passed/0fail，2.35s，exit0；R01/R02/R03/R08组件正确行为；另一次真API完整链1passed，2.21s，exit0 | [RESULT](v00-fe/RESULT.md)、[组件日志](v00-fe/component-third.log)、[真API日志](v00-fe/real-api-third.log)、[真实收据](v00-fe/real-api-receipts.json)；5174启动被工具拒绝，真实浏览器脚本准备但未执行 |

前端组件替身不能当真实持久化或浏览器通过；真API组件链也不替代实际浏览器及适用E2E。整体G1门槛尚未关闭，B4未开工。后续新候选若改实际源代码须重冻并重跑受影响独立验收；本次覆盖扩展没有行为源改变。

三位实现者和三位独立验收者均已停止写入。真实8001组件链结束后，CTRL按原CSV及固定快照核对完整3人次×3叶=9格矩阵、仅一份正式修订，四库integrity_check全部ok、完整foreign_key_check零异常，见[root收尾对账](root/closed-data-check.json)。这项对账不是额外浏览器通过项。

另有[D00事实记录核对](d00/RESULT.md)，仅只读核文件、日志/XML/JSON、API文本及资源，不新增业务测试通过项。首轮发现OMML首次启动日志文件未生成，CTRL据实纠正引用；不补造日志，不扩大完成结论。
