# G6 恢复缓存只读复核

2026-10-05。读根、前端和教案 AGENTS、模块说明、CURRENT_STATUS 和本批 REPORT；只在本轮 `cache/` 下新增外置配置、独立探针、缓存与证据。产品、原测试、旧 QA 和权威文档没有由本复核者改动。所有 Storage 均为隔离 jsdom 或显式内存实例，没有真实浏览器、服务、网络、模型、凭证或业务数据库调用。

## 结论

G6 **正常 ACK 与明确结果 cleanup 的原限定修复保持**。共享 `clearAcknowledgedPackage` 在正常 ACK 和公开 cleanup 中都核对完整 FrozenSubmission、活会话、读取和删除读回；foreign、坏包、不可读均保护，自有合法包或已空包允许结束。代码明确声明 localStorage 读/删不是原子 CAS，本复核没有把它提升为原子保证。

新增一项继承路径 P2：**R-G6-WRITE-OWNER-01，正常发送与 write 重试尚无完整缓存归属判断，能够覆写另一已打开会话结果未知的合法原包**。它不重开原 G6 ACK 修复，以下两个入口归同一个写入归属问题。

| 入口 | 精确实现点 | 可复现触发 | 结果 |
| --- | --- | --- | --- |
| 正常 `run` | [useLessonOperation.ts:65](../../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts#L65) | A/B 都先挂载并读到空缓存；B 先合法创建/导入，获得 status=0 未知结果；A 随后首次正常操作 | 不读共享键归属便写入 A，再发送 A；B 的完整恢复包被 A 替换 |
| 公开 write 重试 | [useLessonOperation.ts:93](../../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts#L93) 至 95 | A 首次缓存写失败，发送 0；B 合法发送并结果未知；A 存储恢复后点击原包缓存重试 | 仅验证 B 包形状/context，随后覆写为 A，返回 true 并解锁 |

两个入口都用真实 create/import 契约形状、完整 11 字段正文/完整旧稿信封、冻结 operationId/submissionId/payloadKey/metadata 和两个合法已打开 hook。B 的原包由生产 hook 正常生成并通过 `validateOperation`，没有注入伪造身份或破坏原包。B 的内存 `pending` 及 `resultUnknown` 仍保持；失去的是持久键中 B 的恢复包，本报告**不声称正文丢失、服务端重复写入或 HTTP 自动重发**。

建议下一修复把正常 write 和公开 write retry 的归属判断统一：先读取原件，空包或完整同包允许；foreign、坏、不可读拒写并阻止本次 HTTP，保留当前操作与原字节；会话变化同样拒写。应在会修改恢复状态的 `prepare` 之前完成归属闸门，并保持读回和会话校验。仍需如实保留非原子 Storage 边界。加强闸门会使旧“两个已打开会话都允许先后占同一键并发发送”的夹具前置改变，后续实现者应明确登记调整依据与新正确 oracle，不能削弱 foreign 保持判据。

## 实跑

统一在仓库根以 `$env:NODE_OPTIONS='--no-experimental-webstorage'` 运行，外置配置使用本轮 `cache/vite-cache`，`retry:0`、串行文件。命令均已退出；未开启任何服务或浏览器。输出文件不覆盖前一轮。

```powershell
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/vitest.config.ts --reporter=default --reporter=json --outputFile=docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/regression-first.json

node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/vitest.config.ts docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/write-retry-owner.test.tsx --reporter=default --reporter=json --outputFile=docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/write-owner-first.json
```

第二、最终新完整探针命令只把输出名换为 `write-owner-second.json`、`write-owner-final.json`，stdout/stderr 分别保存同名前缀 `.log`。独立 oracle 未改变：第二轮仅补自有/坏/不可读对照，最终轮仅加正常发送反例；原首轮探针源码另保存在 `write-retry-owner-first-source.tsx.txt`。

| 本轮实际记录 | 结果 / exit | 解释 |
| --- | --- | --- |
| [regression-first.json](regression-first.json) / [log](regression-first.log) | 9 文件、127/127、exit 0、13.06s | 包含旧 4 own + 4 foreign（现全通过）、本批独立 ACK 20 场景、G5 清理错跳及窄恢复/会话回归 |
| [write-owner-first.json](write-owner-first.json) / [log](write-owner-first.log) | 2 pass / 2 fail、exit 1、744ms | 两空缓存对照通过；create/import write retry 的 foreign 字节保持反例失败 |
| [write-owner-second.json](write-owner-second.json) / [log](write-owner-second.log) | 8 pass / 2 fail、exit 1 | 增加两自有、四坏/不可读对照，原两个反例仍失败；不拼轮计绿 |
| [write-owner-final.json](write-owner-final.json) / [log](write-owner-final.log) | 8 pass / 4 fail、exit 1、834ms | 12 场景最终完整轮；补 create/import 正常 first run foreign 反例，四反例均实证失败 |

最终 12 例的八项对照为每种操作的空、自有、坏、不可读各一项；四项反例为 create/import × normal/write-retry。它们是新增 reviewer 反例，产品未修，因此 exit 1 是期望正确行为不成立的证据，不是“硬拒通过”的计数。正常入口额外实核 `sendA=1`（正确应 0）和 B 字节改变；重试入口实核 `sendA=0`，但 B 字节改变且返回 true/解除阻断（正确应保持并返回 false）。

## 身份与未执行

- 读取时 hook SHA256：`16f38d8348b4dfd57b64b3e0f3374d6770ee936388d128ab4bc1ee1bfdc550b4`。
- 最终 reviewer 探针 SHA256：`07b67087f9bd9563a98da8bfa566160bfe0d270102a86ed39ba6fa8a7a3de5b2`。
- 原首轮探针源码 SHA256：`33255ee753445fd201b73e9581fa94742bfc17487d8e1c75426fda4ab778e23c`。
- 本轮没有重跑完整 check/API/E2E、浏览器跨页、真实模型、教师、Word/WPS 或 RAG；没有任何 Git 写操作。
- 原本批 check/211/16/174 属历史交付实跑，本报告仅复核代码与上述窄测试，没有转签为本轮完整重跑。
- 仓库和旧证据整体保全由根审查者单独核对；本复核者没有补造原物理数据、浏览器或模型证据。
