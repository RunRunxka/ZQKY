# B5-REVIEW-R08-v1

负责人 `/root/b5_r06_review`，独立只读静态复核。FE v6 产品停写 UTC **2026-10-03T13:25:23Z**；本报告绑定随后 `CANDIDATE-prebuild-v6.json`，全件 raw SHA 读取在 CTRL 新 check 开始前完成。只新增此报告与同名 JSON，未运行测试、浏览器、HTTP、服务、SQL、Git，未改产品、QA、权威文档或旧件。

## 静态结论

**未发现新确认 P1/P2。R08 状态传播缺口的候选修复满足静态要求；该结论不关闭 B5，也不替代适用工程与浏览器门禁。**

1. `DocumentGateway.tsx:41–55` 由文档控制器持有稳定发布能力。两个布尔值未变时不通知；变化时先同步更新 `pendingOperation.current`，再更新新的 React 状态对象。Context 值包含此状态，重新发布给包括未改动的 `LeaveProtection` 在内的消费者；弹窗仍按实时 ref 渲染。没有轮询、全局事件、额外教师编辑或重开弹窗触发器。
2. 每次 bind 生成唯一 owner Symbol，并捕获当前 documentId／revisionId／routeError 身份。publish、release 和 isCurrent 都检查 alive、当前 owner、当前上下文。新 lease 接管并复位旧状态；旧 lease 的迟到 publish 或 release 无法清新 lease。`DocumentsPanel.tsx:23,26` 的 bind callback 稳定，单纯状态通知不导致反复重绑；cleanup 清理自身 publisher ref 并释放自己的 lease。StrictMode 与真正卸载中的 hook epoch／mounted 判断仍保持。
3. `DocumentsPanel.start` 在任何 await 之前捕获自己的 publisher，成功后需 receipt.current、alive 和该 lease 接受 publish 才能清 pending 并导航；catch 也需该 publisher 仍 current。旧或已替换发布者不能利用组件后续 alive=true 清除新上下文。导入信封构造、原 pending.payload 选择、submissionId 发送、editRevision 参数与 `useLessonOperation` 的冻结 metadata 机制均未改。
4. Context 通知只引起渲染，不改变 `LessonPlanProvider` 的 `mode|documentId|revisionId` key。编辑 store 由 `useState` 创建并保持。`useServerPersistence` 的初始化／hydrate effect 依赖 docId、store 和稳定 callbacks，不依赖整个 binding；新 Context render 虽重建 server binding 包装对象，另一个 `[binding]` effect 只更新已知后台版本／冲突通知，没有重新 hydrate cache 或新建编辑代次。未发现 pending 状态通知抹掉教师最新输入、重建后台会话或恢复原包的路径。
5. 唯一四件授权 delta 为 DocumentContext、DocumentGateway、DocumentsPanel、workspace test。R07 LeaveProtection、公共 NavigationGuard、useLessonOperation、DTO、后台及冻结 33 件保持。`lesson-workspace.test.tsx` 仅首行加入 StrictMode 导入和新增 R08 块；反向移除新增块并恢复首行原字节后，原完整测试文件 raw bytes 完全一致。首行原 CRLF 在编辑后为 LF，这属于该授权 import 行，未宣称所有修改行 raw 相同。

当前生产调用方没有其他 pending ref 写入者；保留原测试 harness 的直接 ref 写与主动 repaint。六新增作者场景使用实际创建／导入 hook 与编辑／离页能力，覆盖 busy→unknown、unknown→retry busy→422／503、已知成功后明确保存才导航、旧组件卸载后新 StrictMode 实例恢复 unknown。最后一例是整体卸载／新挂载，不冒称它运行覆盖了同 Gateway 内所有可能 producer 替换；同 Gateway 的 owner／context 保护另由源码检查。

## 原结果与首败保全

作者原六轮全部保留，无跨轮拼绿：

| 单轮 | 实际结果 | PID / exit / ms |
| --- | --- | --- |
| unit-before | 127 中 123 pass／4 fail | 23836 / 1 / 18009.456 |
| unit-before-r2 | 127 中 124 pass／3 fail | 18692 / 1 / 17456.223 |
| unit-before-r3，同最终 QA 修前 | 127 中 122 pass／5 fail | 3876 / 1 / 13612.167 |
| unit-r1，修后最终完整单轮 | 127/127、0 fail／skip | 21864 / 0 / 13554.087 |
| types-r1 | exit0 | 27816 / 0 / 1814.403 |
| lint-r1，max-warnings=0 | exit0 | 8604 / 0 / 3013.921 |

前两轮的新 unknown 文字采用等待，600ms 本地写回调可能另行刷新父级而遮住初次传播缺口；仍捕获 retry busy／known receipt 的 3 个真失败。随后作者将新场景加强为完整 act 后立即检查，并给发送 body 添加类型。**同最终 QA 在修前 r3 的 raw bytes 完全相同**，五个新 UI 反例失败、原 121 例通过；修后完整 127 全部通过。没有改原独立 v11 27 的等待、文字、断言或预算。

unit-before 还有一例原 v5 “失败后明确保留”找不到可访问按钮；原 body 未改，before-r2、同最终 QA before-r3 及最终 127 未复现。准确间歇原因尚不能唯一确定，保留原输入／日志／结果，不据后续绿宣称候选永久恒绿。作者记录的编辑前 count guard 拒绝没有写入源，也不当成产品修复。各次先失败的场景中，首错之后的断言未执行；修后完整单轮独立列出。

CTRL 原 v11 完整 27 新单轮 `r8-unit-second` 已实际 **27/27**，PID27472，exit0，5529.201ms，childClosed／logsClosed true，源／QA 前后零漂移。该结果由 CTRL 运行，本审查员仅实读结果和命令收据，未运行测试。原 r7 的 26/1、全部原 QA 和首败保持。CTRL 传达在此之前第一 label 因错写候选文件名被 preflight 拒绝、child 未启动／tests0；该启动前错误独立保留，不与第二轮拼接为绿。

作者结果仅为 AUTHOR_VERIFIED_PENDING_INDEPENDENT；ROOT 后续新 check／build 及完整浏览器 8／原 153／14 chat 等仍按适用门禁执行。本报告的 build 2004 是 check 前已有 build，不能当成本轮 R08 新构建。

## 绑定和复核范围

- FE v6 RESULT SHA `f73cf5b116d7eafc69cd354dfcf646f85fc0f5dd55a22db8a27bdab0ddfc34dd`；PRIVATE-MANIFEST SHA `04a662661d1094e84a33f2aca101cb361279f13e5e9faab78aa5634447850987`；BEFORE SHA `7b198286918c9b26fa799703c30650cf65352e2252426a4ae02f1367f39b5acd`。
- 本审查员逐件核 private43、public readonly6、BEFORE 所保全 prior2601，均 raw SHA 零漂移，43 件相对 BEFORE 只有四授权文件变化。
- `CANDIDATE-prebuild-v6.json` SHA `37b1e790ad2eecfe91c4455549d1cf21747bd4f170bc18d875cd77ca581c03ec`，UTC capture `2026-10-03T13:29:30.747970+00:00`。**938 source／3061 executableQA／33 frozenContract／2004 build／1684 prior 全部实际逐件 raw SHA 零漂移**，读取先于 ROOT 新 check 的派生写。后续 next-env／build 由 ROOT 独占，本文不把并行派生与此时点混算。

| 重点对象 | SHA-256 |
| --- | --- |
| DocumentContext.tsx | `4dc4479781b054156fbbc9c762adae727272969ec598f3041218da0256f84d54` |
| DocumentGateway.tsx | `5fb0c0c479d9d64caa9915b78dd0ede3c5a1043ad25a39c9eee758735a06c75f` |
| DocumentsPanel.tsx | `de66e6f5ae118bfa0c2d40165381cb4f062ff312ba1bf3d725afa7a0fd82b58d` |
| lesson-workspace.test.tsx | `1f869cc95d897b344d22786755022f87754e6e2e2d239a358094671d8d8d74ef` |
| LeaveProtection.tsx，保持 R07 | `6fa64d6ef42b6e24e56c2b9f10079fbd337d0999687875cd4df7dca98a866e77` |
| 作者同最终 QA 修前 r3 results.json | `ca2938fc321a5f736775dfde01582b9da07501582dc394fdcc8b2631cc4d2225` |
| 作者最终127 results.json | `48377d160f33703f03fd6037cf37512360c960cde58a208c38dc7cffb5a2bd7c` |
| 独立 r8-unit-second results.json | `5f0400e4aa4817381346acceedd64755e6952a0e9b3acf3dc6de12c39c69e9c3` |
| 独立 r8-unit-second command.json | `4ac9405bda1543001f9576232bda875142b9f3ce5162b03cae4f43d2f01f7ddc` |

STOP：本静态复核已完成，无新确认 P1/P2，产品／QA 仍停写；R08 和 B5 的最终门禁关闭由 CTRL 决定。
