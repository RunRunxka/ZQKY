# 当前版本的交付级别复核与新会话接续

日期：2026-09-07。审查目标为 `H:\备份xuexi\智启课源`。再次确认只读参考 `F:\DeepTutor` 为 `42fab3cf429a1fbf36b257ab8d116a3814964202`，工作区干净。

## 交付判断

**当前是可接续开发、可演示部分聊天流程的开发版本，尚未达到完整前端交付标准。** 上轮针对性修复的 3 项单元和 3 项浏览器探针均已通过，但本轮仍复现两种终态顺序错误、一项深链刷新问题；Lint 和全量 E2E 也没有全部通过。

即使修复这几个问题，仍不能将产品整体交付：S1 规格只完成框架，S2 完整输入区尚未完成，S3 产物工作区、S4 复杂能力、S5 大部分页面、S6 设置补齐、S7 视觉/动画和 S8 最终验收均有必需工作。页面表 53 个非调试条目中，仍有 46 项标记待实现；4 个“已验收”条目还包含兼容重定向，不宜用 4/53 表示产品完成度。`FINAL_ACCEPTANCE.md` 当前不存在。

已有源码和交接足以交给新会话继续，不需要重新初始化或重写总方案。代码审查无法验证另一个 AI 是否实际耗尽上下文；这里仅依据当前文件、命令结果和恢复点判断接续条件。

## 本轮实际验证

| 检查 | 实际结果 |
| --- | --- |
| 类型检查 | 通过 |
| 正式单元测试 | **117/117 通过** |
| 上轮独立单元探针 | **3/3 通过** |
| 上轮独立浏览器探针 | **3/3 通过**：新建不回跳、切换不回跳、纯续答复制按钮 |
| 构建 | 通过 |
| Lint | **失败**：1 条未使用变量警告，项目要求 0 警告 |
| 全量 E2E | **41/42 通过**；录像用例 context teardown 超时 |
| 新终态顺序探针 | **2/2 复现错误**，见下文 |
| 新深链刷新探针 | **1/1 复现错误**，见下文 |
| 真实供应商 / 真实 MCP、Skills / API 测试 | 本轮未执行 |

交接中的“预期 40/40”已过时，当前全量浏览器套件为 42 项。该数量来自实际执行，后续新增后继续据实更新，不把数字当成固定验收目标。

## P2：error 已经到达，但 run 尚未返回时仍能接受迟到 ACK

位置：[store.ts:313](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:313)。

当前 `turnAlive = generation === ownerToken` 只判断运行对象是否还保留，没有判断 `terminal` 或已收到的 `endReason`。当 error 事件已经令卡片 interrupted，而服务的 run Promise 暂时未返回时，`turnAlive` 仍为 true。此时迟到 accepted ACK 被接受，卡片重新变为 answered。

| 事件顺序 | 应有结果 | 当前结果 |
| --- | --- | --- |
| 提交 → error → run 仍挂起 → accepted ACK | 拒绝；卡保持 interrupted | 接受；卡变 answered |

上轮探针在 ACK 前先等待 run 返回，所以没有覆盖这个窗口。要求：业务终态与 Promise 生命周期明确区分；已经进入 error/stop/disconnect 的等待不因运行对象尚未释放而恢复可提交性。

## P2：正常 end 被通用收尾覆盖成 disconnect，合法确认反而丢失

位置：[store.ts:652](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:652)。

`patchStoppedIfStreaming` 只在修改消息时检查 streaming，但在此前无条件重写 `token.endReason`。正常 end 后 service.run 返回也会调用它，于是 end 被改成 disconnect。根据当前自己声明支持的“合法同步续答可在 ACK 返回前 end”契约，稍后 accepted ACK 应仍记录确认答案，但当前被拒绝。

| 事件顺序 | 应有结果 | 当前结果 |
| --- | --- | --- |
| 提交 → 正常 end → run 返回 → 合法 accepted ACK | 接受；保留 answered | 拒绝；卡保持 interrupted |

要求：明确终态只进入一次，通用断流兜底只适用于尚未收到明确终态的流，不能覆盖正常 end 或 error。把这两项与已通过的取消、断流、正常两卡续答组合成完整的状态迁移测试，避免继续只补前一条失败路径。

## P2：深链的立即回跳修复，但 URL 与当前会话仍不同步

位置：[ChatWorkspace.tsx:112](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:112)、[ChatWorkspace.tsx:241](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:241)。

浏览器实际操作：打开 `/chat/alpha` → 列表选择 beta → 正常显示 beta，说明上一轮修复有效；但地址仍是 `/chat/alpha` → 刷新后重新显示 alpha。

一次性定位守卫解决了用户操作被立即覆盖的问题，尚未实现完整深链契约。复制当前 URL、刷新及浏览器历史不能准确表达正在查看的会话。

要求：用户主动新建/切换/删除会话时同步地址或采用等价且可恢复的路由设计；URL 与活动会话之间的来源明确，避免双向更新循环。覆盖刷新、后退/前进和真实/模拟模式，保持草稿保存、正常生成和取消语义。该项继续作为 S2 未完成部分处理，不必推翻已通过的新建/切换修复。

## 工程门禁与交接准确性

- [ask-user.test.ts:666](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/ask-user.test.ts:666) 声明了未使用的 `emitWaiting`；实际 `npm.cmd run lint` 返回 1。删除该冗余声明或按需要使用，不能关闭规则掩盖。
- 录像测试再次出现 `Tearing down "context" exceeded the test timeout of 45000ms`。这是当前完整套件未通过的原因；不能据此断言动画业务一定错误，也不能把问题销项为“偶发环境因素”。采集收尾问题需单独诊断，正式业务断言和动态证据仍要保留。
- replica/HANDOFF 和页面表已经修正 S1、53 条目等信息，但根 TASKS 的旧当前摘要仍写 S1 完成、51 条目，根 HANDOFF 的“最新”部分仍是更早阶段。应让新会话有一个准确入口，旧内容明确标成历史，避免重复误判进度。

## 证据与复现

所有新增探针使用注入服务、内存仓储或独立浏览器测试数据，不访问真实模型、不修改用户会话。

```powershell
# 在 H:\备份xuexi\智启课源 执行；浏览器输出目录替换为未使用名称
npx.cmd vitest run --config _work/review-delivery-20260907/vitest.config.ts
npx.cmd playwright test --config _work/review-delivery-20260907/playwright.config.ts --output=_work/review-delivery-20260907/NEW-UNIQUE-OUTPUT
```

- [终态顺序探针](H:/备份xuexi/智启课源/_work/review-delivery-20260907/terminal-order.test.ts)
- [终态顺序失败日志](H:/备份xuexi/智启课源/_work/review-delivery-20260907/terminal-order.log)
- [深链刷新探针](H:/备份xuexi/智启课源/_work/review-delivery-20260907/route-refresh.spec.ts)
- [深链刷新日志与 URL 证据](H:/备份xuexi/智启课源/_work/review-delivery-20260907/route-refresh.log)
- [Lint 日志](H:/备份xuexi/智启课源/_work/review-delivery-20260907/lint.log)
- [全量 E2E 日志](H:/备份xuexi/智启课源/_work/review-delivery-20260907/e2e.log)
- [上轮单元探针复跑](H:/备份xuexi/智启课源/_work/review-delivery-20260907/previous-probes.log)
- [上轮浏览器探针复跑](H:/备份xuexi/智启课源/_work/review-delivery-20260907/previous-browser.log)

本轮新增探针和交接文档，并在当前交接入口加入本次独立结论；未修改产品代码、依赖、参考仓库或真实数据，未提交 Git。

## 新会话该怎样继续

选择目标项目 `H:\备份xuexi\智启课源` 作为工作目录。让新会话读取 [NEXT_SESSION_START.md](H:/备份xuexi/智启课源/docs/replica/NEXT_SESSION_START.md)，再按其引用读取完整 FINAL 任务。

执行顺序：本轮收尾问题 → 完整 S2 输入区和首次发送过渡 → S3 产物工作区 → S4–S8。每批检查通过后直接继续，不以旧探针通过或写完交接作为总任务结束条件。当前缺少真实供应商凭证不阻塞其余模拟前端实施。最终分别验收页面、交互、动画、模拟与真实服务。
