# G2 / B5 前端只读复查

日期：2026-10-03。审查现行源码，不按旧未实现状态推断；产品、旧 QA、候选、权威文档与 Git 未改动。本目录只新增探针与证据，未启动服务或浏览器，未重试被拒额外 HTTP 身份复核。

## 结论

确认两项 P2。既有保存 / unknown 原包 / 旧 ACK / 来源 / 候选 / 本地稿防护相关回归通过，不代表下面两个新场景已修复。

### B5F-R01：明确放弃编辑后，延迟离开的旧组件仍自动保存被放弃正文

位置：[useServerPersistence.ts:186](../../../../apps/web/src/features/lesson-plan/model/useServerPersistence.ts#L186)、[LeaveProtection.tsx:50](../../../../apps/web/src/features/lesson-plan/components/LeaveProtection.tsx#L50)。

教师修改正文，600ms 自动保存尚未开始；请求切路由后点击「明确放弃未保存编辑后离开」。`discard()` 删除恢复键并返回 true，离开动作已放行，但缓存仍 dirty，原自动保存 timer 未取消，发送权限未失效。若 Next 的目标页面加载期间旧组件仍挂载，600ms 到期后会用已放弃正文调用 `saveLesson`，并重建恢复键。立即卸载对照不发送，证明问题依赖路由提交延迟，而不是所有离开路径必现。

实际 hook 与真实 `LessonPlanWorkspace` 均复现。正确行为断言要求放弃后的延迟挂载区间不发送保存、不重建恢复键；两项断言当前失败，原日志见 [discard-correct-behavior-first-failure.log](discard-correct-behavior-first-failure.log)。

修复方向：将成功 discard 变成当前会话写入意图的终结，清 timer 并使 auto / save / pagehide / pending callback 无法继续写被放弃内容；恢复可信已保存正文或保留明确终止状态。存储删除失败时不得放行或丢输入。新写入不能依赖「路由很快卸载」保证。

### B5F-R02：历史复制的迟到读取覆盖读取期间的新编辑

位置：[DocumentsPanel.tsx:76](../../../../apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx#L76)。

教师从固定历史回到当前编辑，点击「明确复制历史正文到当前编辑」；该动作先等待 `refreshLatest()`。等待读取时编辑器未锁定，教师能继续输入。响应返回只检查服务端 CAS 与固定修订一致，随后无条件 `replace(pendingCopy.data)` 和 `finishCopy()`：期间输入从当前正文和恢复缓存中被替换，复制 intent 也被清除，接下来的自动保存将保存历史正文。Undo 仍可恢复被替换的新输入，故本报告不称其为永久丢失。

真实 `LessonPlanWorkspace` 使用受控迟到读取复现。正确行为要求新输入与缓存保持、复制 intent 保留到重新确认；三项断言均失败，见 [history-correct-behavior-copy-intent.log](history-correct-behavior-copy-intent.log)，较早仅输入与缓存 oracle 的首败见 [history-correct-behavior-first-failure.log](history-correct-behavior-first-failure.log)。

修复方向：请求前冻结 documentId / loadGeneration / editRevision / serverRevisionId / pendingCopy 的固定身份与正文，await 后同时核身份与编辑代次。发生变化时保持当前正文、缓存和复制 intent，提示重新确认；或在明确的复制操作期间短暂锁定编辑，且所有错误与卸载路径释放锁。不得仅以服务端 CAS 未变证明本机稿未变。

## 本轮执行

| 运行 | 结果 | 证据 |
| --- | --- | --- |
| 新增 hook 与实际工作台诊断 | 4/4 复现通过，另2正确行为用例按过滤未运行 | [diagnostic-final-four.log](diagnostic-final-four.log) |
| R01 正确行为 oracle | 1 用例失败，2 断言失败 | [首败](discard-correct-behavior-first-failure.log) |
| R02 正确行为 oracle | 1 用例失败，3 断言失败 | [完整 oracle](history-correct-behavior-copy-intent.log) |
| 现行教案窄回归 | 3 文件 / 112 例通过 | [existing-narrow-regression.log](existing-narrow-regression.log) |
| 原 B5 独立组件 v11 | 6 文件 / 27 例通过 | [existing-independent-27.log](existing-independent-27.log) |

新增诊断「通过」表示成功证明现有错误行为，不是候选通过。过滤产生的 skipped 不当成产品豁免。正确行为反例没有改产品或放宽 oracle。实际工作台探针首轮因审查测试文件漏导入 React，2 例在渲染前失败；保留 [首日志](workspace-diagnostic-first.log) 与 [原测试字节](workspace-diagnostic.first-source.txt)，修正审查夹具后实际组件诊断通过。

执行命令均由仓库根目录运行，使用 `NODE_OPTIONS=--no-experimental-webstorage`：

```powershell
npm.cmd run test:unit -- --config docs/qa/TEACHING-LOOP-B5-REVIEW-20261003/frontend/vitest.config.ts --reporter=verbose --testNamePattern='accepted explicit discard|control: an immediate|the explicit discard leave button|a history-copy latest-read response'
npm.cmd run test:unit -- --config docs/qa/TEACHING-LOOP-B5-REVIEW-20261003/frontend/vitest.config.ts --reporter=verbose --testNamePattern='required behavior'
npm.cmd run test:unit -- apps/web/src/features/lesson-plan/model/server-session.test.tsx apps/web/src/features/lesson-plan/model/lesson-operation.test.tsx apps/web/src/features/lesson-plan/lesson-workspace.test.tsx --reporter=verbose
npm.cmd run test:unit -- --config docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v11/unit/vitest.config.ts --reporter=verbose
```

第二条是合并复现两个正确行为失败的命令；本轮实际按各 testNamePattern 分别执行，首败与追加 intent oracle 都保留，未将组合命令写成已执行全量。

## 已读范围与限制

已读根 / web / lesson-plan AGENTS、CURRENT_STATUS、B5 REPORT 与模块说明；审查 `DocumentGateway` 的读取 / 切换 / copy intent 身份，`DocumentContext` 的 producer owner，`useServerPersistence` 的串行 / unknown / ACK / CAS / 恢复键，`useLessonOperation` 的原操作恢复，`ProposalPanel` 的生成基线 / 五字段 / apply / reject / stale，`SourcePanel` 的分页与迟到读取，`LeaveProtection` / `navigation-guard`，`EditorContext` / 本地 writer / Undo / Word 与打印快照。

未独立重跑完整 check、153 E2E、14 聊天、真实模型、Word/WPS、实际 PDF 保存、生产 Qdrant 或正式库迁移；浏览器的真实 Next 路由延迟本轮以保留旧树的受控工作台模拟，尚未实浏览器重现。新 P2 应在下一批修复后追加实际延迟路由与迟到历史复制浏览器验收。

## 下一阶段建议

先修上述两个写入 / 编辑时序边界，独立正确行为 oracle 转绿后，再推进质量与发布前验证。B5 已有真实后台教案、固定学情、候选逐字段选择链，下一批不应重复建设这些模块。优先验证真实模型的知识点针对性、依据可追溯、四阶段分钟与人工选择有效性；用隔离样本核 Word/WPS 长文分页与实际 PDF，并明确账号未建立与 local owner 的边界。保留旧 v1 信封 / 本地键 / ProcessItem 四字段和原任务、CAS、成功回执约束。
