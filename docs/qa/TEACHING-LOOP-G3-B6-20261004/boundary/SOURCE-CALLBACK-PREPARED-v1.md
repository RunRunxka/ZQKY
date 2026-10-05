# 新增来源迟到反例准备

2026-10-04。CTRL 完整 check-r1-first 结束后批准增加本独立反例。原 `PREPARED-v1`、5 个全字段场景及 source-r1 候选不改；本文件与 `source-callback-boundary.test.tsx` 为候选 QA 增量，必须在执行收据中单列，不回写旧候选。

实际组件为 `DocumentGateway → LessonPlanProvider/EditorContext → useServerPersistence` 与 `SourcePanel`。通过实际固定学情选择触发受控 getRun(A) 等待读取，随后实际 editor.replace 写全部 A、实际 server.discard 恢复 BASE，释放旧 A 读取，再等待多个 600ms 周期。SourcePanel 和保存 hook 均没有 mock；业务 API 为隔离受控读取/保存计数，不能将此单测称真实浏览器或真实 FastAPI PATCH 验收。

正确行为手写 oracle：全 11 正文保持 BASE、cache.context 与显示 context 保持原 BASE、恢复键仍缺失、CAS/固定修订仍 1、saveLesson 新增 0。日志输出各阶段完整正文/context/cache 和实际 save 包，便于第三人核对；预期不是生产合并逻辑计算。

准备状态 `not_run`；本 Agent 不执行测试，待 CTRL 的 PID/命令/日志 runner。可执行本文件单独测试，避免与原 5 例结果混淆；是否修改产品由 CTRL 决定。

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run test:unit -- --config docs/qa/TEACHING-LOOP-G3-B6-20261004/boundary/vitest.config.ts docs/qa/TEACHING-LOOP-G3-B6-20261004/boundary/source-callback-boundary.test.tsx --reporter=verbose
```

最小防护建议（待实际复现）：旧异步来源更新冻结当前保存会话的 document/load/writeEpoch，并在同步应用之前核对；成功 discard 更改的 epoch 使旧读取失权，正文与来源显示一并恢复可信固定上下文。教师留页后的新来源选择应捕捉新 epoch 或明确建立新编辑意图，不应永久禁用 setContext，也不靠 router 很快卸载解决。尽量复用既有来源 epoch 与保存会话，不新增 DTO、表或公共导航变更。
