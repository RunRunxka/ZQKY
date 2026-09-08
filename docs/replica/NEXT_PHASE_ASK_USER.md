# 下一阶段执行提示词：追问卡片与同轮续答

本文件由 2026-09-07 R5–R9 复核产生。修复主流程已通过原独立探针，但复核新增 R10：扩展菜单外部点击监听的条件写反。先修这个小回归，再实现本阶段；不要直接执行旧交接中的“提交后以新轮次继续”。

## 源码依据与边界

- [ask_user.py:1](F:/DeepTutor/deeptutor/tools/ask_user.py:1)：明确规定暂停同一轮，收集 1–4 个结构化问题，一次提交回答。
- [AskUserOptions.tsx:814](F:/DeepTutor/web/components/chat/home/AskUserOptions.tsx:814)：预览只读、单选/多选/自由文本、多问题导航、跳过与已回答摘要。
- [use-card-submission.ts:27](F:/DeepTutor/web/hooks/use-card-submission.ts:27)：提交失败恢复可操作状态，不能把未送达表现为持续提交中。
- [ChatStateAdapter.tsx:2415](F:/DeepTutor/web/features/chat/ChatStateAdapter.tsx:2415)：向当前 activeTurnId 发送 submit_user_reply，并等待确认。
- [ChatWorkspace.tsx:1776](F:/DeepTutor/web/features/chat/components/ChatWorkspace.tsx:1776)：等待回答时，主输入框同样路由到 submitUserReply。
- [pipeline.py:1136](F:/DeepTutor/deeptutor/agents/loop/pipeline.py:1136)：等待用户回答并发出 ask_user_resolved，然后继续当前轮。
- [ask-user-state.ts:41](F:/DeepTutor/web/lib/ask-user-state.ts:41)：普通 ask_user 与结束本轮后开启新轮的 mastery 问题是不同机制，本阶段只实现前者。

参考源码用于确定行为，不要求把目标项目的 FastAPI SSE 换成 DeepTutor WebSocket，不要求复制整套运行时。

## 完整提示词（可直接复制）

```text
目标项目：H:\备份xuexi\智启课源
只读参考：F:\DeepTutor
固定基线：v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202

先读目标根与 apps/web 的 AGENTS.md、README、docs/DECISIONS.md、
docs/TASKS.md、docs/HANDOFF.md，以及 docs/replica/HANDOFF.md、
REVIEW_EXTENSIONS_2026-09-07.md 最新复核记录和 NEXT_PHASE_ASK_USER.md。
历史提示词是参考，本条当前任务优先。不要从历史规划自动开展其他阶段。

本轮目标：先修复 R10，再只实现“模拟追问卡片＋同一轮暂停和续答”。
保留现有技术栈、锁文件、教案、模型管理、真实 SSE、真实/模拟存储隔离、
revision 冲突保护、卸载清理与终态守卫。不接真实 MCP/Skills 或付费模型，
不新增业务后端/数据库，不改只读参考，不自动提交 Git 或推送。

一、前置修复 R10
ExtensionPicker.tsx 外部点击 effect 的 `if (!mounted || open) return`
导致菜单打开时没有注册监听。先运行
_work/review-r5-r9-20260907/outside-click.spec.ts 复现，再修正监听条件和清理。
补正式回归：点击内部不关闭；点击外部输入框后正常退场且焦点留在输入框；
Escape 恢复触发器焦点；快速开关及生成开始自动关闭仍正确。
原 R5–R9 的 2 项单元和 4 项浏览器探针必须保持通过，不削弱断言。
完成前置修复后继续本阶段，不需要再次等待用户批准。

二、先核对参考语义，禁止把追问提交实现为另开一轮
重点读取参考中的：
web/components/chat/home/AskUserOptions.tsx
web/hooks/use-card-submission.ts
web/lib/ask-user-state.ts
web/features/chat/ChatStateAdapter.tsx（submitUserReply）
web/features/chat/components/ChatWorkspace.tsx（主输入框等待回答的分支）
deeptutor/tools/ask_user.py
deeptutor/agents/loop/pipeline.py（_await_user_reply_and_resolve）
以及对应 ask-user 测试。

原版 ask_user 的语义是：当前轮生成→提问→暂停→接受回答→继续当前轮。
同一 sessionId、turnId 和当前助手消息保持关联，不再调用普通 send 新建轮次，
不把旧轮标记 end 后又允许迟到事件把它重新打开。
精通之路题目、答完开启新轮等其他机制不在本阶段。

三、扩展统一事件与服务接口
把现在只有 prompt:string 的 wait-user 预留事件扩成结构化判别式联合。
问题包含稳定 questionId、prompt、header、options(label/description)、
multiSelect、allowFreeText、placeholder；一张卡片包含稳定 interactionId 和 intro。
所有交互事件、回答提交与确认都携带 sessionId + turnId + interactionId。
引入 submissionId 或等价机制，保证重复点击、重复确认只消费一次。

在 ChatService 上提供提交回答的统一接口或等价会话句柄；明确支持能力与
接受/拒绝结果。模拟实现接收 text 或结构化 answers，真实实现明确不支持，
保留现有真实 SSE 请求与事件兼容性，不能悄悄转为模拟。
不要将 resolver、AbortController、Promise 等运行对象存进 IndexedDB。

模拟 run 在等待用户时应保持活动且可取消，不能因为发出 wait-user 就正常
返回、触发 store 的断流收尾。明确区分生成中、等待回答、提交中、继续生成、
完成、错误、取消状态；不要只把 sending=false 后放开普通 send。
提交失败是卡片级失败；仍有有效等待上下文时保留草稿和选项以便重试。
上下文失效必须明确拒绝、收尾，不能永久转圈或假装提交成功。

四、消息内追问交互
模拟模式提供明确可选的演示场景，不根据用户问题中的隐藏关键词触发。
复刻原版卡片的单问题/多问题标签、上一题/下一题、选项说明、单选、多选、
自由文本及跳过语义。单选后的前进、多选不自动前进等以源码为准。
未回答题目按原版标记为跳过，不自作主张加“所有题必须答完”的拦截。
预览中的问题只读；收到完整可回答事件后才开放操作，不允许回答半生成问题。

卡片提交与主输入框回答都走当前追问的统一提交接口。主输入框等待时明确提示
“回答当前追问”，不能误发为新问题；失败时保留输入，接受后再完成相应状态更新。
提交中禁用重复提交，接受后显示只读问答摘要，继续正文并保留之前的内容。
同一轮可先后出现两张追问卡，只有当前有效卡可回答，旧卡保留对应答案。
正文→提问→回答记录→续写的顺序应正确，不能把所有正文挤到卡片同一侧。
兼容旧的纯 content 历史，避免重复显示内容；不要顺手重写整个消息系统。

五、确定性模拟与数据恢复
脚本至少覆盖：无追问、单选、包含多选/自由文本的多问题卡、全部跳过、
预览→可答、同轮两次追问、提交一次可重试失败、等待中取消、提交时取消。
回答后继续的模拟内容必须反映实际选择或自由文本，不能所有答案都返回同一结果。
始终展示模拟标识，不进行真实检索、工具执行或外部网络调用。

发送时冻结的扩展快照贯穿追问和续答；设置后续变更不影响正在进行的轮次。
问题、草稿、选择、已确认答案、状态和消息顺序随会话保存；保留 revision 机制。
切会话、新会话、离开路由、浏览器返回和 dispose 时取消等待并释放运行资源。
刷新后恢复记录与未提交草稿，但未完成的本地等待上下文已失效：明确标记中断，
禁止直接向旧卡提交，不自动重新执行。用户可以显式重试原问题开启新的尝试；
保留旧卡历史，不自动把旧答案冒充这次用户的提交。
旧会话没有这些字段时照常读取，不能清库或重置用户数据。

六、交互与动画
逐组件提取 AskUserOptions 的实际 CSS 过渡；不要把所有地方统一套 160/300ms，
也不要在原版没有动画的地方新增装饰。复用现有动画机制与减少动画支持。
覆盖进入、预览变可答、切题、选择、提交、失败重试、只读摘要的状态与焦点。
支持中文 IME，组合输入时 Enter 不能误提交；隐藏/锁定内容不能获得不可见焦点。
正文增量不重播卡片动画、不重置用户选择；用户上滚后不强制拉回底部。
390×844、1440×900、1920×1080 下长题干、多选项、错误提示和按钮均完整可达。

七、验收与交接
测试直接证明：
- 等待时没有 end，也没有普通 send/run 的第二次调用；回答后同 turnId 继续。
- 单选、多选、自由文本和跳过传入服务的数据正确，提交确认前不显示已回答。
- 双击/Enter 并发提交只接受一次；失败保留答案；错误确认不影响别的交互。
- 取消、切会话、卸载及终态后的迟到问题/确认/正文全部被守卫拒绝。
- 同轮多张卡不串答案；重复事件不重复建卡，也不覆盖已填写的草稿。
- 刷新与再次选择历史不重放，失效卡不可提交；旧历史和原快照兼容。
- 原 R1–R10、真实问答适配、模型管理和教案相关回归保持通过。

运行 typecheck、lint、test:unit、build、相关/全量 test:e2e；每轮使用新的
独立产物目录。动画证据必须记录实际动画存在、时间点和状态，不只靠截图文件名。
录像与定格截图分开验收。本次复核曾遇到 chat-motion 录像 context teardown 超时，
应独立诊断并如实记录，不删除录像测试或把单次通过说成稳定通过，也不因此把
全部业务断言误报为失败。

更新 replica 的 AI_INTERACTIONS、PAGE_MATRIX、MOTION_MATRIX、HANDOFF，
同步 DECISIONS/TASKS 和本阶段验证记录；修正旧交接中“提交后以新轮次继续”的提示。
交付包含源码映射、状态/接口说明、实际命令结果、截图/动态证据和未验证项。
本轮不做产物工作区、研究/出题/精通之路完整流程或其他业务页面。
```
