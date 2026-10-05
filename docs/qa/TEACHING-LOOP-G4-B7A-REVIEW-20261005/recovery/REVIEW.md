# G4 恢复链只读审查 v1

审查日期：2026-10-05（Asia/Shanghai）。现场 `main@b7f99ab09826c68724e281d01e15215e660c1ce0`，审查的是包含 G4 未提交改动的共享工作区。读取根、web、lesson-plan AGENTS，CURRENT_STATUS 最新 G4-B7A 块、PROJECT_GUIDE、模块说明及本批 REPORT-v1；仅在本目录新增独立探针、配置、日志和报告。

确认 1 项 P2。原缓存临时写失败的公开恢复路径在现有窄回归中通过；本 finding 是新增清理恢复入口使用旧成功结果的问题，不重开原缓存入口缺失问题。

## R-G4-RECOVERY-01 / P2：第二次创建明确失败后，缓存清理可错误打开上一次创建的文档

定位：`apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx:66`（相关调用 70）。`completed` 只根据 `recoveryKind === 'cleanup'` 读取 `operation.result`，没有将结果与本次操作身份及成功/失败对应。

触发步骤（独立探针使用实际 DocumentGateway、DocumentsPanel、LeaveProtection 和后台编辑状态，所有 API 与 Storage 为隔离替身）：

1. 打开后台文档 current，创建空白后台教案；创建请求等待期间编辑 current 正文。
2. 首次创建成功返回 first-created；自动切换触发离开决策，教师点击“取消离开，继续编辑”。组件及第一次成功结果仍保留。
3. 再次创建。当前正文正常保存后，第二次创建返回明确 422。该操作的恢复缓存 removeItem 暂时失败，出现“重试创建操作恢复缓存”。
4. 恢复存储并点击该清理入口。预期只清理失败操作的缓存并保持当前文档；实际调用 `router.push('/lesson-plans?lessonPlanId=first-created')`。

根因证据：`useLessonOperation.ts:51–52` 对成功回执及明确非恢复错误都使用 cleanup；共享 `useFrozenSubmission` 仅在成功时写 result（`assessments/hooks.ts:291`），新请求和失败未清除旧 result（282–285、300–318），因此第二次失败仍暴露第一次成功的文档。新增 `retryOperationCache` 把这一旧 result 当作本次成功回执并切换。

影响：教师点击“缓存清理”会跳转到之前创建的文档，失去当前工作上下文；第二次明确失败被混入“明确回执”的成功恢复语义。没有确认第二次 HTTP 重复发送或当前正文丢失，不能扩大成数据丢失结论。导入走同一 helper，但本轮未独立执行同样的 import 双操作反例。

建议：在 cleanup 失败记录中绑定本次 receipt / operationId 以及明确结果类型；只有本次成功 receipt 才能恢复打开文档。不能用跨请求保留的 last result 推断本次成功。补充“成功但取消切换 → 后续明确失败并清理失败”组件行为场景。

首败：[stale-ack.test.tsx](stale-ack.test.tsx) 65 行正确行为断言、[stale-ack-first.log](stale-ack-first.log)。首跑 1/1 失败，149ms；前序断言已确认两次 create、第一次取消后和第二次失败后均未跳转，唯一失败发生于清理重试后。日志保留原件，未修改产品后重跑或拼绿。

## 已执行

环境：Node v26.2.0；所有 Vitest 命令设置 `NODE_OPTIONS=--no-experimental-webstorage`。外置配置及 cacheDir 均在本目录。

| 命令范围 | 结果 | 日志 |
| --- | --- | --- |
| 独立 stale-ack.test.tsx 正确行为反例 | 1 failed，实际错误跳转 first-created | stale-ack-first.log |
| 独立 cleanup-controls.test.tsx：首次成功/首次明确失败 + 清理失败两对照 | 2/2 passed，HTTP 各一次，成功才跳转 | cleanup-controls-first.log |
| 原 g4-recovery.test.tsx + 原 model/server-session.test.tsx | 37/37 passed、2 files，单轮 | regression-first.log |

完整命令（从仓库根运行）：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/recovery-review.config.ts docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/stale-ack.test.tsx --reporter verbose
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/recovery-review.config.ts docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/cleanup-controls.test.tsx --reporter verbose
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/recovery-review.config.ts apps/web/src/features/lesson-plan/g4-recovery.test.tsx apps/web/src/features/lesson-plan/model/server-session.test.tsx --reporter verbose
```

原恢复相关回归覆盖完整正文/context/source、unknown 原包、600ms 串行及后续 dirty、较高/同版本异固定身份 ACK、409 人工 CAS、坏缓存不覆盖、跨文档迟到验证、首次签名和 generation/apply/reject 公开恢复。通过计数不覆盖本报告新增双操作反例，也不能推断浏览器或真实服务通过。

只读后验：HEAD/分支保持；本代理未写产品、旧 QA、权威文档或 Git。已读关键源码的后验 SHA 见 [source-hashes-after.json](source-hashes-after.json)；该文件是当前源码事实，不冒充开工前散列或完整候选无漂移证明。

## 未执行边界

完整 check/build/API/E2E/真实浏览器、真实模型、教师评价、Word/WPS 和跨标签页实际存储竞争均未执行：本任务为离线只读审查，限定窄 unit/组件替身。未启动服务、浏览器或模型，未读取 .env、正式数据库、真实草稿或原始 Word；不撤销原 G4/B7-A 历史关闭收据、不关闭原 B6/B7 整体。
