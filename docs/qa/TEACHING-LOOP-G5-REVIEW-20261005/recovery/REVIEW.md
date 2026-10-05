# G5 恢复回执只读审查

2026-10-05，读取根、web、lesson-plan AGENTS、教案模块说明、CURRENT_STATUS 和 G5 REPORT-v1。只在本 recovery 目录新增探针、配置、日志与报告；不改产品、原测试、旧 QA、权威文档或 Git，不启动服务、浏览器或模型，不读取正式 Storage、凭证或数据库。

原 R-G4-RECOVERY-01 的修复保持：cleanupOutcome 明确区分本次成功回执与本次明确失败，DocumentsPanel 不再读取共享历史 result 推断本次成功。旧错跳反例、新 G5 作者用例及既有恢复回归本次 71/71 通过。新增确认 1 项 P2，来自继承的正常 ACK 清缓存路径。

## R-G5-CACHE-01 / P2：正常明确回执可删除另一标签页的原操作恢复包

定位：[useLessonOperation.ts:61](../../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts#L61)。正常 success 或明确 failure 均调用 `recoveryRef.current.write(null)`，没有读取并核对缓存中的操作是否属于本次 outcome。与之相比，缓存清理重试在同文件 74 行已有合法包及完整身份核验。

生产条件是两个已经打开且空闲的标签页。DocumentsPanel 第 25、26 行分别固定使用 `zhiqikeyuan:lesson-plan:operation:v1:create` 与 `...:import`，以及相同 `lesson|new|create/import` context；同一浏览器同源 localStorage 共享这些键。两个页面加载后各自发起合法操作，后发者正常写入自己的恢复包。先发者返回明确成功或 422 时，当前正常 ACK 路径删掉后发者的恢复包。

独立探针 [full-cache-owner.test.tsx](full-cache-owner.test.tsx) 使用真实 `browserOperationRecovery` 和 `useLessonOperation`、共享隔离 Map Storage、完整 LessonCreateRequest 或 LessonImportRequest（含完整 v1 draft、二次备课字段），由 hook 自己冻结两个不同 submissionId/loadGeneration 的包。四个 foreign 场景均调用生产 `validateOperation` 核对 B 包，并确认包与 B 实际 send 参数完全一致；没有伪造 adapter read 或篡改 operation 结构。

每个反例的顺序：

1. A、B 两个 hook 都在没有旧操作时完成恢复读取。
2. A 发起并等待响应；B 发起另一合法操作，其完整包成为共享键当前字节。
3. A 成功或明确 422；B 随后 status 0 响应丢失，B 内存状态正确为 unknown、pending 仍是自己的原包。
4. 正确 oracle 要求 B 持久缓存仍为原字节；实际为 undefined，即键已被 A 清除。各 send 均只调用一次。

create/import × success/failure 四个正确行为断言全部失败；同文件另四个自有包正常 ACK 清理对照均通过。首跑共 **4 passed / 4 failed，exit 1**，原 JSON 和日志完整保留。最初 generic 载荷诊断另 2 failed，未混入完整载荷用例或通过计数。

影响限于已证实事实：另一未明结果操作的持久恢复包被误删；其页面当时尚保留内存原包。刷新或重新打开后无法再从该键恢复 B 的提交身份，是由键被删除推导的后果，本次没有实际刷新浏览器。没有确认正文丢失、服务端数据丢失或重复 HTTP，不将此缺陷写成已发生重复创建。该 finding 不重开原“第二次失败跳到第一次成功文档”问题，也不称本批新引入回归。

建议最小修复：正常 ACK 清理与公开 cleanup 重试共用同一 owned-cleanup 判据；先读取并验证原字节，只有 missing 或完整包属于本次操作时才能清理。合法 foreign 包、坏字节或读取失败均拒绝删除，保留本次 outcome 与现有公开恢复入口，提示当前缓存归属冲突。无需为此引入另一套存储或标签锁；共享单键整体并发能力不由这一有限修复证明。

静态观察（不另报 finding）：kind=write 的公开重试会读取 old，但其 foreign 包比较不在该分支；本轮未为该路径构造生产行为反例，不能把观察计作第二个已确认缺陷。

## 本次实跑与证据

Node v26.2.0；每轮设置 `NODE_OPTIONS=--no-experimental-webstorage`；外置配置、缓存及所有输出都在本目录。retry 0、fileParallelism false。各轮独立计数，不能合并成“全部通过”。

| 范围 | 结果 | 原件 |
| --- | --- | --- |
| generic 两标签诊断 | 2 failed，exit 1，783ms | [日志](inflight-cache-owner-first.log)、[JSON](inflight-cache-owner-first.json) |
| 完整 create/import 新 oracle 与自有 ACK 对照 | 4 passed / 4 failed，exit 1，867ms | [日志](full-cache-owner-first.log)、[JSON](full-cache-owner-first.json) |
| 6 文件既有窄恢复回归 | 71 passed，exit 0，8.38s | [日志](regression-first.log)、[JSON](regression-first.json) |

71 项为旧 stale-ack 1、cleanup-controls 2、G4 recovery 26、server-session 11、G5 cleanup-outcome 26、lesson-operation 5。覆盖旧历史 result 保留与当前类型区分、第二成功/失败、教师取消或保留离开、发送前零 HTTP、unknown 原包、StrictMode、读/写/清理错误、正常缓存归属重试、busy、迟到与卸载、跨文档/load、完整数据/context/source 保持。作者/交付历史 152、8 浏览器及 174 E2E 本次未重跑，不用本次 71 替代。

复跑命令（仓库根）：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G5-REVIEW-20261005/recovery/review.config.ts docs/qa/TEACHING-LOOP-G5-REVIEW-20261005/recovery/full-cache-owner.test.tsx --reporter verbose
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G5-REVIEW-20261005/recovery/review.config.ts docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/stale-ack.test.tsx docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/cleanup-controls.test.tsx apps/web/src/features/lesson-plan/g5-cleanup-outcome.test.tsx apps/web/src/features/lesson-plan/g4-recovery.test.tsx apps/web/src/features/lesson-plan/model/server-session.test.tsx apps/web/src/features/lesson-plan/model/lesson-operation.test.tsx --reporter verbose
```

## 未执行

完整 check/build/API/E2E、真实浏览器及实际多标签 storage 事件、真实模型、教师评价、Word/WPS、正式 Qdrant/迁移/压力均未执行。本轮只读源码审查与隔离 hook/组件行为；不关闭原 B6/B7，保留交付所列待验项。没有产品修复或下一批执行。
