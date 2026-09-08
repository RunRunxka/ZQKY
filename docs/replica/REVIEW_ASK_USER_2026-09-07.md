# R10 与追问同轮续答：独立代码复核

日期：2026-09-07。目标：`H:\备份xuexi\智启课源`。参考：`F:\DeepTutor`，本次核实 HEAD 为 `42fab3cf429a1fbf36b257ab8d116a3814964202`，参考工作区干净。

## 结论

**R10 修复通过；追问同轮续答的正常演示路径成立，但本阶段尚未达到完整验收标准。** 107 项现有单测通过，并不覆盖下列遗漏。新增独立探针在当前代码上复现了 7 项单元/组件问题和 1 项浏览器问题，归纳为 R11–R16 六组修改要求。没有修改产品代码。

本报告审查当前工作区文件，而非可追溯的提交差异；目标大量文件仍未跟踪，不能据此宣称历史上其他模块从未被修改。

## 本次实际检查

| 检查 | 本次结果 | 边界 |
| --- | --- | --- |
| `npm.cmd run typecheck` | 通过 | 当前源码 |
| `npm.cmd run lint` | 通过，0 警告 | 当前配置范围 |
| `npm.cmd run test:unit` | 107/107 通过 | 项目已有用例 |
| `npm.cmd run build` | 通过 | 不等于视觉验收 |
| 旧独立 Vitest 探针 | 2/2 通过 | `_work/review-extensions-20260907/vitest.config.ts` |
| 全量 E2E | **37/38 通过** | 录像测试 context teardown 超过 45000ms；未据此认定业务断言失败 |
| 新独立 Vitest 探针 | **7/7 复现不符合验收的行为** | 最终日志 `probes-final.log` |
| 新独立浏览器探针 | **1/1 复现复制遗漏** | 已通过真实界面完成两卡续答再点击复制 |
| 视觉抽查 | 查看 390×844 长自由文本草稿截图，提交按钮可达 | 不是全部长题干、全部状态或 1920px 视觉验收 |
| 真实供应商 / 真实 MCP、Skills | 未调用 | 不把本地模拟当成真实验证 |
| API 测试 / 完整 WebM 播放 | 本次未执行 | 没有扩大到后端实现或完整动态验收 |

R10 的打开时监听、外部点击不回抢焦点，在源码、组件回归和本次全量 E2E 对应场景中均通过。

## R11 · P2 · 异步提交与旧轮次收尾缺少身份守卫

代码：[store.ts:283](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:283)、[store.ts:560](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:560)。

两个独立复现：

1. 进入等待，提交回答但延迟服务确认，点击停止；卡片先变为 `interrupted`。此后返回 `accepted: true`，当前实现把旧卡改成 `answered`，提交返回 `true`。
2. 停止旧轮并开始新轮，新轮已收到 `new-ask`；旧服务此时才返回。旧 `run` 的 `finally` 无条件清空 `waitingInteractionId/submittingReply`，新追问失去有效入口。

事件 emitter 有 token 守卫，但 `await submitReply` 后的成功、拒绝、异常、finally 和 `run finally` 未统一受保护。`markReplyFailed` 还使用完成时的 `get().activeId`，而非发起时会话身份。

要求：以发起时的会话、轮次、助手消息、interaction、submission 身份绑定结果；异步返回只能修改仍由它拥有的状态。取消/切换/新轮后不得覆写旧终态、当前卡或新提交锁。提交接受与续答发事件之间也要定义顺序，避免简单补守卫后把正常同步续答误判为失效。补 delayed ACK、delayed reject、服务忽略 abort、切会话和新提交并发用例。

## R12 · P2 · 新增续答结构未接入上下文、复制及重试保留逻辑

代码：[store.ts:214](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:214)、[context-budget.ts:14](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/context-budget.ts:14)、[ChatWorkspace.tsx:403](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:403)、[store.ts:802](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:802)。

`asks[].followUp` 承载卡片后的正文，但原消费方仍只认 `message.content`：

- 下一轮上下文只有“先确认偏好”，没有已确认回答和最终解释。继续问“展开刚才的例子”时，服务看不到此前实际对话。
- 浏览器实测两卡续答完成后点击“复制回答”，剪贴板只有“【模拟回复】收到你的问题……先确认两件事”，未包含可见续答。
- 直接从追问开始、尚无正文/工具记录的尝试，中断后重试会把旧助手消息删除，连同追问和草稿一起丢失；独立探针已复现。

要求：建立统一、按时间顺序的消息投影；展示、可复制正文、服务上下文、预算计算、备份及重试保留应有明确一致的策略。已确认回答进入上下文，未确认草稿不能冒充已提交答案；不用机械地把界面所有装饰文字拼进模型。旧纯 content 历史兼容、不重复正文，含 ask/产物等有效记录的失败尝试保留并正确排除已取代尝试的请求上下文。

## R13 · P2 · 非空预览无法补全成完整问题

代码：[store.ts:202](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:202)、[AskUserCard.tsx:134](H:/备份xuexi/智启课源/apps/web/src/features/chat/AskUserCard.tsx:134)。

复现：同 id 先收到包含一道未完成题目的 preview，再收到两道完整问题的 waiting。实际仍只有最初一道未完成题目；`intro` 也被第一段固定。现有测试使用相同 preview/waiting 题目，未覆盖真实的逐步补全。

此外目标 preview 只显示“正在准备追问”，已有问题与选项也不展示；参考 [AskUserOptions.tsx:1063](F:/DeepTutor/web/components/chat/home/AskUserOptions.tsx:1063) 会显示只读的已有题目，无题目时才显示骨架。

要求：按稳定 questionId 接收权威题目更新，保留用户草稿与合法选择；明确 preview→waiting 的完整性边界，不让迟到 preview 退回已可回答状态。补 intro-only、部分题目/选项、完整 waiting、已编辑草稿后重复事件等场景。

## R14 · P2 · 已回答卡的重复 waiting 会抢走后续卡

代码：[store.ts:456](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:456)。

复现：回答 first → 收到 second → 再收到 first 的重复 waiting。first 虽保持 answered，但全局 `waitingInteractionId` 被改回 first，second 不能继续正常提交。

要求：活动卡依据经过身份验证和合法状态迁移后的结果确定，不能仅因原始事件标记 waiting 就设置活动 id。已回答/已中断卡不能重新取得等待权；重复、过期、逆序事件不重开卡，不覆盖当前等待。

## R15 · P2 · 单选与自由文本仅单向互斥

代码：[AskUserCard.tsx:78](H:/备份xuexi/智启课源/apps/web/src/features/chat/AskUserCard.tsx:78)。

复现：单选题允许自由输入，先填写文本，再选择选项 A 并提交。实际同时提交 `labels: ['选项A']` 和之前自由文本。参考 [AskUserOptions.tsx:959](F:/DeepTutor/web/components/chat/home/AskUserOptions.tsx:959) 选中单选项会取消自定义回答选中态。

要求：两方向均互斥。可以保留未激活的自由输入草稿供切回，但序列化答案必须只提交当前有效分支。多选题按参考允许选择和补充文本共存。补两种操作顺序的组件与浏览器用例。

## R16 · P2 · 追问卡新增了原版没有的进场动画

代码：[chat.css:1101](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:1101)、[chat-mock.spec.ts:504](H:/备份xuexi/智启课源/tests/e2e/chat-mock.spec.ts:504)。

当前追问卡套用弹出菜单的 160ms `chat-ext-pop`，E2E 还断言它必须存在。参考 AskUserOptions 的该卡片没有这项装饰进场；本地 MOTION_MATRIX 也明确记录了这个差异。这违背本阶段提示词“原版没有动画的位置不额外添加装饰效果”。

要求：移除这项偏离，保留源码实际存在的选择/按钮反馈、骨架与提交状态；按来源校正测试和动画矩阵。不能通过把不匹配实现写进断言来证明复刻完成。其余卡片结构（多题标签、自定义选项、只读摘要等）仍需逐项完成，而不是将子集直接写成全量复刻。

## 验证设施尚未闭环

`chat-motion.spec.ts` 本次再次出现 `Tearing down "context" exceeded the test timeout of 45000ms`，日志在 `e2e.log:555`。现有证据只能确认此症状复现，不能断言根因一定是 ffmpeg、环境负载或应用代码。业务检查与录像产物收尾分开报告，诊断后再验收稳定性；不能删测试、降低断言或挑选通过的复跑覆盖原失败记录。

## 独立复现与证据

探针均使用注入服务、内存仓储或隔离浏览器，不调用真实供应商，也不改真实用户数据库。

```powershell
# 在 H:\备份xuexi\智启课源 执行
npx.cmd vitest run --config _work/review-ask-user-20260907/vitest.config.ts
npx.cmd playwright test --config _work/review-ask-user-20260907/playwright.config.ts --output=_work/review-ask-user-20260907/NEW-UNIQUE-OUTPUT
```

- [单元/组件探针](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/ask-boundaries.test.tsx)
- [最终探针日志](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/probes-final.log)
- [复制回答浏览器探针](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/copy-reply.spec.ts)
- [复制遗漏日志](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/browser-2.log)
- [全量 E2E 日志](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/e2e.log)
- [390px 长草稿截图](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/browser-output-2/copy-reply-Copy-answer-mus-3b964-visible-same-turn-follow-up/ask-mobile-long-draft.png)

初版浏览器探针对多题提交按钮用了单题名称，因此曾在定位器阶段失败；更正为界面实际“提交回答”后，最终在剪贴板内容断言处复现上述产品问题。初版与最终日志分开保留，最终结论使用 `browser-2.log`。

## 后续

执行 [完整剩余任务提示词](H:/备份xuexi/智启课源/docs/replica/FINAL_REPLICA_EXECUTION_PROMPT.md)。先修 R11–R16 并完成针对性回归，再推进全部剩余前端工作。最终区分页面、交互、动画、模拟验证、真实服务验证五项完成状态。

## 修复记录（2026-09-07 晚，S0：R11–R16）

修复前复现：独立单元探针 7/7 失败；修复后 7/7 通过。浏览器复制探针修复后通过（fixcheck-01）。全部改动未削弱探针断言。

- **R11 已修复**（`store.ts`）：提交发起时冻结身份（sessionId/turnId/ownerToken/interactionId/submissionId，并登记 `activeSubmissionId`）；确认返回后按"未中止、未被新轮顶替、同会话、提交身份一致"判定归属——中止（停止/取消）或被新轮顶替后迟到确认返回 `false` 且不改写 interrupted 历史；`markReplyFailed` 写入发起时会话而非完成时的 activeId；`run` 的 finally 仅在 `generation === token`（本轮仍活跃）时释放 waiting/submitting，不清掉新轮身份；catch 路径同样受归属约束。**事件顺序定义**：确认（accept）→ 续答/收尾事件 → 提交返回值——合法同步续答可能在确认返回前推进到下一张卡甚至 end，归属判定不因此误拒（探针 old-run-finally 与 formal 测试覆盖）。`submissionId` 实际用于归属判定与服务侧单次消费，不再只是声明。
- **R12 已修复**（`context-budget.ts` + `ChatWorkspace.tsx` + `store.ts`）：新增 `conversationProjection()` 统一投影——正文 + 已确认追问回答（"问题：回答"行）+ 逐卡续写，按时间顺序；`selectMessagesForRequest` 对含追问的消息先投影再预算（服务上下文与预算一致）；复制回答改用同一投影（包含可见续答与已确认回答，不含未提交草稿）；重试保留条件加入 `asks`（仅有追问交流、无正文的失败尝试不再被删除）。旧纯 content 历史原样返回。
- **R13 已修复**（`store.ts` upsertAsk + `AskUserCard.tsx`）：新 wait-user 事件为权威数据，按稳定 questionId 整体更新题目与引言（部分预览可被完整 waiting 补全），已填草稿保留；`preview` 不把 `waiting` 降级；卡片预览态按原版呈现已有题目（只读、禁用），无题目才显示骨架。
- **R14 已修复**（`store.ts`）：wait-user 处理先 upsert 再按**更新后的卡片状态**决定活动卡——只有合法迁移到 waiting 的卡才取得 `waitingInteractionId`；已回答/提交中/中断的卡被重复事件命中时不抢走当前等待。
- **R15 已修复**（`AskUserCard.tsx`）：单选双向互斥——选中选项清空自由文本（此前只单向），序列化只提交当前有效分支（单选：有选项则不带文本；多选：选项与文本共存）；组件探针场景迁入正式测试。
- **R16 已修复**（`chat.css` + e2e + MOTION_MATRIX）：移除原版不存在的追问卡 160ms 进场动画；e2e 断言改为 `animationName === 'none'` 防回归；动画矩阵同步修正。
- **探针场景迁移**：7 项单元/组件场景全部迁入 `ask-user.test.ts`"审查 R11–R16 回归"describe（断言不弱化，另补投影/草稿保留细节）；浏览器复制场景保留 `copy-reply.spec.ts` 探针并通过。
- **录像 teardown 诊断（S0 要求项）**：`chat-motion.spec.ts` 连续 3 次独立复跑（4.4–4.8s/次，产物 `tests/.e2e-output-20260907-teardown-1..3`）均正常收尾，未复现 `Tearing down "context"` 超时；录像 webm 正常产出。应用行为、录制关闭与产物完整性三方面均无异常证据，**根因未知**——疑似与复核时环境负载相关，保持独立文件隔离，持续观察；不以"环境问题"销项，也不据单次通过宣称稳定。

### S0 实际验证

- `npm run typecheck` 通过；`npm run lint` 通过（0 警告）；`npm run test:unit` **114 项**通过（107 → 114，+7 为探针迁移）；`npm run build` 通过。
- 独立探针：单元 7/7、浏览器 1/1 通过。
- `npm run test:e2e`：**38/38** 通过（产物 `tests/.e2e-output-20260907-s0`）。
- 真实供应商/真实 MCP、Skills：未调用（模拟边界）。
