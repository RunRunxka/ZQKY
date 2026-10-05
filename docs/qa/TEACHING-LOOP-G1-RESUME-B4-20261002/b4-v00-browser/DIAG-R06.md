# B4-F-R06 v1 独立受控诊断

结论：原 transfer 测试缺少通知就绪的正向同步，最可能导致首败；本轮未发现合法草稿或撤销行为错误。**不能归因为 loading 期间名单控件消失，也不能声称本轮精确重现了原同步 getByTestId 首败。**

单轮实际 **1 文件、3/3 场景通过，exit 0/2176.98ms，PID 13712 正常退出**（runner 1.67s，测试 623ms）。三个场景各一次显式 Promise 门，暂停操作成功后的两次名单读取，不使用固定 sleep、概率重试或完整 check。原测试全部 11 个完整 matcher 断言文本保留；新增 pending 合法草稿、实际参测人数和撤销后控件消失断言。静态解析只是准备检查，不并入业务计数。

实际观察来自 [完整原始合并日志](../b4-root/r06-controlled-first.log)（4444 字节、SHA `5f8670a05fbcb12d5f86b5e85576639546b6655be3383edea9a1e486a4d4a6e4`）及 [完整命令收据](../b4-root/r06-controlled-first-command.json)：

| 观察点 | 甲控件 | loading 提示 | 撤销通知 |
| --- | --- | --- | --- |
| transfer 两个读取均被门暂停 | 仍在、勾选；缺考/2 人次草稿保留 | 在 | 不在 |
| 原负向 wait 回调首次成功 | 已移除；乙仍在 | 不在 | 不在 |
| await 原负向 wait 返回 | 已移除 | 不在 | **已在** |
| 正向通知同步后原断言完成 | 已移除且出勤/人次控件均移除 | 不在 | 在且原文字断言通过 |

因此实际捕获了新 ready 名单 render 与 effect 生成通知的提交间隙；但本轮 await negative 返回后通知已经出现，原行 80 此时可以通过。这个区别原样保留，不将窗口观察伪写成完整首败重现。原 full check 的真实首败仍在 [check-v14-second.log](../b4-root/check-v14-second.log)：transfer 用例 234ms 后行 80 找不到通知；全轮 exit 1/96796.762ms，1102 passed/2 failed，另一个 navigation 失败由 CTRL 处理。旧原件没有重跑或改写。

合法草稿实际正确：pending 与最终乙始终勾选、免考、人次 3；add/import 后甲仍取消勾选、缺考、人次 2，丙默认勾选，参测 2 人次。transfer 后甲所有参测/出勤/人次控件消失，原撤销通知及原转班 payload 断言通过，剩余乙合法草稿保留，参测 1 人次。均为真实组件/工作区/hook 配合显式 fetch 替身的组件诊断，不是实际后端或四库结论。

源码支持上述观察：`hooks.ts:65,70,74-75,88-89` 在同 key 刷新时保留 lastData；`AssessmentsPanel.tsx:109-120` 只在 ready 后用 effect 过滤离班 draft 并设置 notice，存在另一次 state 提交；原 `AssessmentsWorkspace.test.tsx:79-80` 先仅等甲消失，再同步读取通知。**最小修复建议**：CTRL 在原第 80 行前加 `await screen.findByTestId('assessments-roster-notice');`，保留原负向等待、通知全文、payload、勾选/出勤/人次和写入次数全部断言；无需产品修改。本 Agent 没有实施修复。

绑定 `CANDIDATE-b4-r4-diagnostic.json` SHA `db148ed409970bbca67ecba04562e8b63f8d1fe4af94f9b3ac92e535ea4e389e`：前审 exit 0/195ms、后审 exit 0/192ms，877 源/36 可执行 QA/5 契约全零漂移，next-env 原字节一致。新增两个已冻结源 SHA 见 [DIAG-R06.json](DIAG-R06.json)。原测试/产品/旧证据未写，全部可执行源已停写。

root 冻结 runner 明确以 stderr=STDOUT 保存完整合并流，没有独立 stdout/stderr 文件；未伪补不存在的原始分流。新 temp `C:\Users\96022\AppData\Local\Temp\zqky-b4-r06-controlled-first-j4c10z13` 保留，只读含 `empty-textbooks`，未删除任何目录；无监听/服务/浏览器操作，旧六目录未触碰。整体 B4 门槛仍未关闭。

