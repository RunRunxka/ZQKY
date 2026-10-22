# features/chat — 学习问答与 Agent 交互

> 2026-10-12：R 系列重建完成。对话即唯一入口：学习问答、业务工具（八板块）、附件、
> 追问澄清（普通对话）全在一页；**没有模式切换**。

## 结构

- `ChatWorkspace.tsx`：页面（会话侧栏 + 消息列 + composer + 右侧产物面板）。
  composer = textarea + 附件（`uploadAgent` 落 blob → extensions.attachments）+ 上下文容量环
  （`ComposerContextChips`：上限**档案 `contextTokens` 优先**，其次后端 `contextWindow`
  的 `model/upstream/model-table` 解析值；来源为族暂估/未知时弹层提供「读取模型信息」按钮，
  调 `POST /model-profiles/{id}/refresh-metadata` 一次更新**上下文与输出上限**并展示 old→new；
  占用以最近一轮供应商真实 usage 为基准，`context-usage.ts` 只估算其后新增内容与输入框草稿）+ 思考强度
  （`reasoningSupport.selectable` 为 true 即显示；未验证模型带“上游可能忽略或报错”提示）+ `ModelSelector`。
  切换模型时旧档位不在新集合内会回到“默认”，不会静默发送隐藏值。
- `model/store.ts`：对话单 store（会话 CRUD、消息状态机、事件路由、追问卡、持久化）。
  事件必须匹配当前轮次与会话（迟到/串会话/重复丢弃）；`send` 经 `buildChatRequest` 组装历史。
- `model/chat-service.ts`：通道分流——**默认 Agent 通道**（`agent-chat-service` → `/agent/stream`，
  业务能力全经 Agent 工具）；显式注入 `stream` 时走 `/chat/stream`（测试/纯问答回退）。
- `model/agent-chat-service.ts`：agent-stream 事件 → 统一 `ChatServiceEvent`；
  `wait-confirm` 映射为追问卡（approve/reject 与选择值经 `/agent/confirm` resume）。
- `Message.tsx` / `AskUserCard.tsx`：消息渲染（markdown/推理/阶段/工具过程/产物入口）与追问卡。
- `ArtifactPanel.tsx`：右侧产物面板（消息 artifacts 的标签化查看）。

## 纪律

- 不在模块顶层读 `window`/`document`/localStorage；浏览器能力置于客户端生命周期内。
- 追问卡与确认卡共用 `AskUserCard`；写操作确认必须显式点击（不自动提交）。
- 工具/阶段/候选语义：AI 产出只进候选；「采用」动作必须在用户显式操作后发生。
- 测试：`NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit`；组件级 jsdom 覆盖，
  e2e 见 `tests/e2e`（本轮重建对齐九路由壳与问答主路径）。
