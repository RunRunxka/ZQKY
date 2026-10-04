# G1-FE v1.1 实现结果

负责人 `/root/g1_fe`，2026-10-02；状态 **ready_for_review**，产品与直接测试已停写。起点 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` 加既有 B3-FIX r7，按本批 BASELINE.json.sourceFiles 的磁盘 SHA 比较，不把相对 HEAD 的整个 B3 diff 当成本次改动。十二项授权路径起点/终点 SHA 和实际八项变化见 [SHA.json](SHA.json)。未切分支、暂存、提交或推送。

## 产品变化

- `ScoreImportReview.tsx`：新校对同步失效承认、关闭已打开的确认弹窗；进入承认、打开弹窗、buildConfirmPayload 和实际提交均检查 dirty/保存中/映射待存与待权威预览状态。保存成功记录返回 revision/previewVersion，等父级读回至少该版本后才能重新承认；旧视图或读回失败不能确认旧矩阵。保存期间输入和撤销受同一同步守卫保护。未知确认最先取原冻结包，刷新版本或父级映射守卫不会阻断原包重放。
- `ScorePanel.tsx`：映射请求绑定编辑代次，只清属于该次请求的编辑；在途较新的输入保留并标未保存。409、422、网络失败及只读刷新均保留输入。首次默认批次固定身份，列表刷新不短暂变成 none 并误清草稿；原操作代次保护切换/卸载后的迟到响应。映射保存成功后也等待新权威预览，再解除正常确认守卫。
- `AssessmentsWorkspace.tsx`：独立名单版本通知，名单成功变更传给已经挂载的施测面板，不重挂载施测，不影响成绩草稿。
- `RosterPanel.tsx`：手建学生、名单导入确认和转班成功均通过一个通知入口刷新本地资源并通知工作区。失败和失效上下文不发成功通知。
- `AssessmentsPanel.tsx`：收到名单版本后以同资源 key 重新读取成员，保留仍在名单中的勾选、出勤和人次。成功读回发现移出成员时移除其本地草稿，并显示具体姓名和撤销说明。新增成员无需切班或重开页出现；增加明确刷新/读错提示，正常创建等待权威名单读取成功。未知创建仍按 B3 的原包重放，不因名单刷新改写确认包。

未改 `RosterImportPanel.tsx`：其已有 onChanged 在确认成功后发出，本次由 RosterPanel 连接到工作区即可。未改共享 contracts、客户端、公共 hook、CSS、路由或导航，未另造状态服务。

## 直接行为测试

改 `ScoreImportReview.test.tsx`、`ScorePanel.test.tsx`，新增 `AssessmentsWorkspace.test.tsx`；其他授权直接测试保持起点字节。

R01 验证承认后再次编辑、弹窗打开后编辑零确认 POST；保存中与 200 后仍停留旧 r1 时阻断；权威 r2 重新承认后 PATCH 的新分数与 r2/preview2 确认包一致；未知响应刷新到 r8/施测 r9 后仍逐字段重放原 r1 包和同 submissionId。此处持久化由 fetch 边界状态替身证明前端行为，实际四库新分数须由 CTRL/V00 的真实 API/浏览器链再验，不能把组件替身称为真实业务入库。

R02 验证在途 F→G 后的 200 保留 G 为 dirty，第二次 PATCH 使用权威 r2 和 G；409/422/网络失败后显式刷新仍保留 G；切换批次、卸载再挂载后旧成功/失败不能污染当前编辑；全部组件在 StrictMode 中运行。另验映射保存 200 后旧 GET r1 不解除确认、新 GET r2 后才解除。

R03 使用真实 Workspace/RosterPanel/RosterImportPanel/AssessmentsPanel，经 fetch 边界分别走手建、CSV 上传及逐行 create 确认、真实 transfer 客户端请求，回已访问施测后显示新成员/移除转出成员；乙勾选、免考和人次3，以及仍合法的甲未勾选、缺考和人次2均保留。转出甲时有明确撤销文案。实际隔离 FastAPI 的新增/导入/转班通知链须由 CTRL/V00 验收，不冒称已做真实浏览器。

## 实际命令与首败

以下均在仓库根运行；Vitest 前设置 `$env:NODE_OPTIONS='--no-experimental-webstorage'`。每次完整 stdout 留在本目录，不叠加多轮计数。

| 单次执行 | 命令 | 结果 | 日志 |
| --- | --- | --- | --- |
| 首败 R01/R02 正确行为反例 | `node node_modules/vitest/vitest.mjs run apps/web/src/features/assessments/ScoreImportReview.test.tsx apps/web/src/features/assessments/ScorePanel.test.tsx --reporter=verbose` | 3 failed / 13 passed；exit 1；1.57s | [first-score-boundaries.log](first-score-boundaries.log) |
| 第一轮五文件 | `node node_modules/vitest/vitest.mjs run apps/web/src/features/assessments/ScoreImportReview.test.tsx apps/web/src/features/assessments/ScorePanel.test.tsx apps/web/src/features/assessments/AssessmentsPanel.test.tsx apps/web/src/features/assessments/AssessmentsWorkspace.test.tsx apps/web/src/features/assessments/RosterImportPanel.test.tsx --reporter=verbose` | 2 failed / 49 passed；exit 1；4.11s。映射保存后列表刷新导致默认身份暂失，响应 notice 被清；修复固定默认选择 | [targeted-r1.log](targeted-r1.log) |
| 修复默认身份后的同五文件 | 同上一完整命令 | 51 passed；exit 0；1.99s | [targeted-r2.log](targeted-r2.log) |
| 补权威映射预览等待后的同五文件 | 同上一完整命令 | 52 passed；exit 0；1.99s | [targeted-r3.log](targeted-r3.log) |
| 局部 ESLint 首败 | `node node_modules/eslint/bin/eslint.js apps/web/src/features/assessments/ScoreImportReview.tsx apps/web/src/features/assessments/ScorePanel.tsx apps/web/src/features/assessments/AssessmentsWorkspace.tsx apps/web/src/features/assessments/AssessmentsPanel.tsx apps/web/src/features/assessments/RosterPanel.tsx apps/web/src/features/assessments/ScoreImportReview.test.tsx apps/web/src/features/assessments/ScorePanel.test.tsx apps/web/src/features/assessments/AssessmentsWorkspace.test.tsx --max-warnings 0` | exit 1；0 errors / 1 exhaustive-deps warning；默认批次派生变量已改为标量依赖 | [eslint-r3.log](eslint-r3.log) |
| 局部 ESLint 最终 | 同上一完整命令 | exit 0；0 errors / 0 warnings | [eslint-r4.log](eslint-r4.log) |
| 最终稳定前端模块回归 | `node node_modules/vitest/vitest.mjs run apps/web/src/features/assessments --reporter=verbose` | 10 files / 103 passed；exit 0；2.55s | [assessments-final-r4.log](assessments-final-r4.log) |

命令均将 stderr 合并 stdout，经 Tee-Object 写上述新日志，最后 `exit $LASTEXITCODE` 保留实际退出码。局部 ESLint 运行耗时 2.169s / 2.050s；最终模块命令宿主耗时 3.148s，Vitest 内报告 2.55s。

## 未执行、跨域与资源

未执行全量 check/build/API/e2e、真实浏览器三视口/键盘/减少动画、真实供应商、Word/WPS、Qdrant、迁移或备份；实现者不占 root 的构建和端口，交 CTRL 的最终门禁与独立 V00 处理。v1.1 按 CTRL 指派执行 typecheck，结果见下段。没有为未执行项写通过结论。旧 B3-FIX-REVIEW 探针与首败日志只读，未覆盖旧证据。

无共享文件建议或新接口依赖。浏览器/8001/5174/16333/构建目录未占用；仅 Vitest/ESLint/typecheck 命令已结束。未读 .env、正式业务库或真实浏览器会话；未手写 next-env.d.ts，v1.1 的 next typegen 生成文件由 CTRL 按现场原字节恢复后冻结；未删除任何数据或旧 policy 拒绝目录。B4 未开发。本任务产品与测试停写，等待独立验收。

## v1.1 类型门禁修复

CTRL 的 `root/g1-typecheck-first.log` 首败指出 ScorePanel 测试夹具五处 TS18049：DTO mapping 允许 null/undefined，而夹具固定提供映射。仅改授权 `ScorePanel.test.tsx` 的 `view()` 返回类型，明确它提供 `NonNullable<ScoreImportView['mapping']>`；setup 的权威视图缓存仍按完整 ScoreImportView 类型接收。所有界面、请求、原包重放、dirty 和版本行为断言保留；产品代码无改动。SHA.json 已更新为 v1.1。

- `npm.cmd run typecheck`（实际 next typegen && tsc --noEmit）：exit 0，宿主耗时 2.603s，完整输出 [typecheck-v1.1.log](typecheck-v1.1.log)。CTRL 已明确临时让出该生成目录；下一步须由 CTRL 恢复 next-env 现场原字节再冻结。
- `$env:NODE_OPTIONS='--no-experimental-webstorage'` 后 `node node_modules/vitest/vitest.mjs run apps/web/src/features/assessments/ScorePanel.test.tsx --reporter=verbose`：单次 1 文件 **15 passed**，exit 0，Vitest 1.97s，宿主耗时 2.577s，完整输出 [score-panel-v1.1.log](score-panel-v1.1.log)。此前 103 项模块结果保留，不将两次计数相加。

v1.1 产品和测试再次停写，状态 **ready_for_review**。
