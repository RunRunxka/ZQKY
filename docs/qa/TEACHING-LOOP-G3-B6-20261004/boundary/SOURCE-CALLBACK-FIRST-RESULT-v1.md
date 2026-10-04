# 来源回调首败独立核查

2026-10-04。CTRL runner 实际执行 PID 19084，2020.119ms，exit 1，1 场景/8 个正确行为 soft 断言失败。原测试 SHA `bfc96c302b1ccb2581c11b6a6c9101389821d0d3de9844ff8e18c14f1420099d` 未改；原首日志、命令和样本保留。来源与执行 QA 前后无漂移，完整绑定见 [结果收据](SOURCE-CALLBACK-FIRST-RESULT-v1.json)。

实际 `DocumentGateway/SourcePanel/EditorContext/useServerPersistence` 路径复现：成功 discard 已恢复全 11 正文及 BASE 上下文、恢复键已删除；旧 getRun(A) 返回随后把 cache.context 与显示 context 改为 null，恢复键重建，新增 saveLesson 调用 1，收到替身回执后缓存 CAS 从 1 变为 2。发送正文仍完整 BASE，发送上下文为 null。没有把观察夸成弃稿 A 正文再次提交或永久丢稿。

这是实际组件的受控业务 API 诊断，不是实际 FastAPI PATCH 或真实浏览器结论。完整各阶段事实从原日志提取到 [只读 facts](SOURCE-CALLBACK-FIRST-FACTS-v1.json)，不是重跑或重写首日志。

结论：r1 未完全封存 R01 的旧来源异步入口，G3 尚不能关闭。CTRL 已登记并释放最小 r2 修复；本审查者未改产品。修后必须原 case 原字节重跑，再执行新教师来源意图与 run/KP/inputs 保持的补充场景，不能删反例或改断言隐藏首败。B6 未启动。
