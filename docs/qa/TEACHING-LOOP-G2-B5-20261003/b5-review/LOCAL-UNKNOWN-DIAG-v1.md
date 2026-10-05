# B5R-LOCAL-UNKNOWN-DIAG-v1

独立只读诊断，负责人 `/root/b5_r06_review`；源读取与分组复核于 2026-10-03 13:17 UTC（北京时间 21:17）完成。仅新增本报告及同名 JSON；未运行测试、浏览器、HTTP、服务、SQL、Git，也未改产品、QA、权威文档或旧证据。B5 未关闭。

## 结论

确认一项新 **P2：已打开的离页弹窗不订阅本地创建／导入操作状态，在 in-flight → unknown 时仍可能显示旧的进行中状态**。

具体触发：教师发起旧本地稿导入，继续编辑并请求离页；弹窗按进行中状态打开。导入响应随后丢失，操作 hook 已转为 `unknown`，但这一状态更新只重渲染 `DocumentsPanel`，未通知弹窗。因此未知提示不出现，按钮继续显示之前的进行中禁用状态；需要另一个父级／编辑状态更新，或取消后再次打开，才能读到新状态。离页 guard 仍读取实时 ref，现有证据没有证明越权导航或丢失正文，不能把暂时安全禁用解释成允许离开。

## 静态链与原运行事实

- `DocumentGateway.tsx:35,79–83` 建立 `useRef({busy:false,unknown:false})`，通过 Context 暴露；没有随 ref 更新发布 React 状态的入口。`DocumentContext.tsx:23` 仅声明 `MutableRefObject`。
- `DocumentsPanel.tsx:23–25` 的 busy／unknown 来自两个 `useLessonOperation`；effect 只写 `pendingOperationRef.current`。成功回执及卸载清理的 47、22 行也是直接写 ref。没有调用父级 setState、通知订阅或编辑 notice。
- `LeaveProtection.tsx:41–45` 在渲染时读取 ref 并决定未知提示；没有订阅它。`ask` 的 21、35 行直接读取实时 ref，并维持本地快离开、在途与未知的安全阻断。这是渲染通知缺口，不是 API 幂等机制缺口。
- `ApiError` 的第三个参数是 status；QA 使用同一客户端类的 `new ApiError('NETWORK_ERROR','独立未知',0,true)`。`asApiError` 保留该类实例；`useFrozenSubmission` 的 300–312 行在 status=0 时明确设置 `phase='unknown'`、busy=false，保留冻结操作并返回 null。`useLessonOperation.ts:44–49` 不清理 status=0 的恢复原包；`DocumentsPanel.start` 收到 null 后没有额外父级更新。没有发现此处把未知误分类为明确失败。
- 原 QA `v11/unit/local-navigation.test.tsx:240` 在 `act` 中 reject，并执行 `settle()`；59 行的 settle 是另一个 `act` 加 24 次 Promise 微任务。此处不是未 await 的立即读取。fake timer 不推进本地 600ms 自动写入，所以不能依赖无关的保存回调为弹窗补一次刷新。

CTRL 已执行的原完整私有单轮为 **27 例：26 pass／1 fail**，PID10640，exit1，5266.989ms，UTC 13:12:26.598947 开始、13:12:32.126096 结束，子进程及日志均关闭。唯一失败在上面用例的 241 行，查找精确未知提示失败。234–239 行已经通过：只发送一次原导入信封、恢复原包存在、全部新输入已填写、离页弹窗可见、未导航／未强制保存、保存和放弃按钮禁用。

**242–245 行在这次失败后未执行**，因此该轮不能证明丢回执之后的原包原字节、旧键、全部 11 字段、取消及后续零导航／零保存断言。结果内 prettyDOM 在顶部控件处被截断，没有覆盖弹窗或导入重试按钮；不据该截断 DOM 宣称已经观察到 hook 内部 phase。状态传播原因由上述源链确认，runtime 缺字仅与之相符。

相邻的「恢复已有 unknown 原导入包」用例 247–260 行通过，包括未知提示、阻止保存／放弃、原包与旧稿原字节、11 字段及取消保持；它先恢复 unknown、再打开弹窗，所以不覆盖已经打开的 busy 弹窗随后转 unknown。其他 26 例和 R07 正常本地 flush 的通过保留，不能替代本次失败。

## 修复建议与验收边界

由 CTRL 另立唯一写入卡，在 `DocumentContext`／`DocumentGateway` 增加稳定的操作状态发布入口或订阅机制；`DocumentsPanel` 在操作状态、成功清理与卸载清理时发布，`LeaveProtection` 订阅并重新计算显示。保留立即更新的 ref 供安全 guard 使用，保持 store／mode／documentId 身份、epoch、卸载、冻结载荷／metadata 和恢复原包规则。不要用轮询、无关编辑、重开弹窗或增加等待来修饰原失败；保存和放弃仍须按真实 unknown 保持阻断，保留操作按原有策略执行。

建议可写产品范围为上述四文件及作者 workspace 测试，需由 CTRL 正式分配，本文不授权或实施写入。新增有意义的作者场景应覆盖在途弹窗已经打开后转 unknown，并保持原 payload／submissionId、教师全部输入、未导航／未强制保存与取消；之后由独立 V00 重跑原完整 27，形成新候选后补适用工程与浏览器门禁。当前静态报告不能关闭该 P2 或 B5。

## 精确绑定

候选 `CANDIDATE-B5-r7.json` SHA `85774ab874d8de3343500093c1b67938ad7528d9252ea147fff425bb5707b396`，capture UTC 13:12:10.639012。命令前后 938 source／2764 executableQA 均零差异；本次只读逐件复核该候选的 **938 source／2764 executableQA／33 frozenContract／2004 build 全部 raw SHA 零差异**。build `zmNsDUHtq1oRmN-ixNctj`。未进行 Git 操作，分支／HEAD 仅引用候选记录。

| 对象 | SHA-256 |
| --- | --- |
| DocumentContext.tsx | `7d8109372ee0abc539e0b321bfc1559aa52191954a6f4d7767f2317e0b31f10a` |
| DocumentGateway.tsx | `5177156752d9801e79815c741247f24beb41b88b77d45e1bbc0485e473601f33` |
| DocumentsPanel.tsx | `2d1778034a5d05006a472bf6a54da3cc7fbcf9afa722b31d1ce455be041ef3a2` |
| LeaveProtection.tsx | `6fa64d6ef42b6e24e56c2b9f10079fbd337d0999687875cd4df7dca98a866e77` |
| useLessonOperation.ts | `89cf4d4bb5a255593e6fd3a50b8b58870bcc423ad58cc1a0a97b5b69edf98ff1` |
| assessments/hooks.ts | `24879cfbd35ba8dcc252b2d18c81d48975f14c5ce618f81c0a46f5a289522127` |
| services/api-client.ts | `49107dec7875ae64d4810134b8260ef5dfbb533d20a22957f0c9ecd95ff517ff` |
| v11/unit/local-navigation.test.tsx | `8a0bc402ff9ca5704bbbdacddbd2a48252a15d40e7c1d6378c09a7330ddbd8ba` |
| run-r7-unit-first/results.json | `67806aa7bc91977fe99cc82c61cfeaf02d1277246c035ca07ea8d9b597f88ec1` |
| ctrl/b5-v00-r7-unit-first-command.json | `f51a14dfc9e234534e28cdc5eaf64570def7198eb77a53b423f4e6530a359872` |
| ctrl/b5-v00-r7-unit-first.log | `d85e4f8e2af127d4ab63dd647fcef01824ab2952733a44ce5f7c296bf52dc98e` |

STOP：仅此诊断已完成，产品未修、本次独立失败未关闭；等待 CTRL 分配下一写入／独立验收卡。
