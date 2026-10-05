# G4 教材来源、上下文与历史复制审查 v1

2026-10-05，任务 G4-SOURCE-REVIEW v1，负责人 g4_source_review。结论：**未确认新的可报告缺陷；G4 的显式清除修复在本轮来源回归中通过。** 本结论限代码与隔离组件行为，不关闭原 B6/B7 整体或真人待验项。

现场 main@b7f99ab09826c68724e281d01e15215e660c1ce0。已读根、前端、教案模块 AGENTS、CURRENT_STATUS 最新块、PROJECT_GUIDE、模块 README、G4/B7-A REPORT-v1、原 B6 来源 review。审查产品只读，新增文件限本 sources 目录。

## 修复与边界判断

[SourcePanel.tsx:50](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/components/SourcePanel.tsx:50) 的 clearEvidence 递增独立 verifyIntent，随后清空 evidence；首次 null→null 清除同样撤销旧意图。它没有递增其他来源 epoch 或清 pendingReport，因此教材清除不会取消在途报告、题库和 metadata 读取。公开 UI 的既有题、练习选择、教师要求、模型和时长保持。

[SourcePanel.tsx:116](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/components/SourcePanel.tsx:116) 捕获核验意图、来源 owner 与 selection/value 签名；两个 await 后以及 catch 均使用同一 isCurrent。getDocumentSource 期间清除时，不再启动后续 verifyLessonEvidence；verify 期间清除时，不采用迟到证据；两个阶段的迟到错误均不重新显示。反复清除、新核验完成后旧响应到达、非空旧证据清除亦通过。

[SourcePanel.tsx:36](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/components/SourcePanel.tsx:36) 保留 mode/document/store/live session 身份，discard 和 unmount 同时撤销来源与教材意图。[useServerPersistence.ts:203](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/model/useServerPersistence.ts:203) 用当前 cache documentId/loadGeneration/writeEpoch 判定 session；discard 在存储删除前递增 writeEpoch，删除失败也不允许旧 context setter 提交。因此守卫覆盖 React 尚未展示新 discard 状态的间隔，原删除失败保留稿件的场景通过。

[SourcePanel.tsx:80](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/components/SourcePanel.tsx:80) 的 metadataEpoch 与来源 epoch 保持独立；初始报告自动读取还需 pendingAtStart、当前 pendingReport、selectionEpoch 三条件。延迟 metadata 不复原明确取消关联的报告；刷新不取消正在读取的新报告；连续 metadata 刷新由最新 owner 接管；discard 后旧列表不能恢复报告或重启保存。这五项真实 workspace 回归完整通过。

教材下拉和切片起止输入仍可准备下一片段；这不会隐含取消已明确点击提交的当前片段。原 B6 对参数编辑的两项行为观察没有新证据把它们提升为缺陷，本轮仍区分“准备下一片段”和公开“清除”。原点击范围被采用、页面中下一范围保持的正例通过，不重报旧观察。

[DocumentsPanel.tsx:77](H:/备份xuexi/智启课源/apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx:77) 的历史复制仍冻结 intent、编辑代、文档/store/load/write身份和 CAS/完整基线；等待期间编辑或 Undo、切文档/历史、GET 失败与基线变化都保留当前稿和复制意图。正常双击只复制一次，可 Undo/Redo，显式保存创建新修订。原完整历史复制七项通过。本审查没有把复制行为扩大为新保存恢复验收。

## 本轮实际执行

一次完整窄单轮，Node 带 `NODE_OPTIONS=--no-experimental-webstorage`，Vitest 3.2.4、jsdom、retry=0。

| 文件 | 本轮实际结果 |
| --- | --- |
| g4-source-intent.test.tsx | 29/29 |
| 既有独立 v00/product/source-intent.test.tsx | 14/14 |
| b6-source-loading.test.tsx | 5/5 |
| g3-source-session.test.tsx | 5/5 |
| g3-history-copy.test.tsx | 7/7 |
| 合计 | **60/60，0 failed/pending/todo，exit 0** |

运行 UTC 06:18:37.2340403 至 06:18:41.2276683，外层 3993.628ms；北京时间 14:18:37 至 14:18:41。原输出 [run-original.log](run-original.log)，完整 [vitest.json](vitest.json)，命令 [command.txt](command.txt)，运行时间/退出/HEAD [run-receipt.json](run-receipt.json)。没有自动 retry 或拼接成功轮次；没有新增镜像实现的测试。

所用 12 项关键产品、原测试、helper 与根 setup/config 的 [before](source-before.json)/[after](source-after.json) SHA 全等。它们逐项对照最终 CANDIDATE-B7A-offline-r2.json SHA `3a73dd766c2e23e57e5726e157f7ef5ef1efe9a7c5f815429b3774ca24568297`，12/12 相符、0 mismatch，见 [candidate-binding.json](candidate-binding.json)。SourcePanel SHA `0fa3acc0bc0f8f3ff35e2fa5aa013f05b6dd8f72256c163002926188faa31a1e`，DocumentsPanel SHA `f367a999ac56be86fb5569d4657f28c2d73a56c56dd7d5e66582f4910c05482f`。

首个准备命令将原 helpers.tsx 误写为 helpers.ts，在 SHA 读取阶段退出，Vitest 未启动；原命令与输出保留 [preparation-first-failure.md](preparation-first-failure.md)。仅修本目录 runner 的路径，不改旧 QA 或业务 oracle；该准备错误不计为产品失败。

## 未执行及限制

完整 check/build/API/E2E、服务/浏览器/HTTP、真实模型、教师评价及 Word/WPS 均未执行：本任务只读审查且明确限制为窄组件运行；没有以本轮组件结果替代已有真实来源/完整工程收据。原 Qdrant/恢复/RAG-REL、人审及原生排版边界保持。未改产品、旧 QA、权威进度文档、原计划或 Git，未启动模型和业务服务。
