# features/chat — 对话与 Agent 交互（最小骨架版）

> 2026-10-11 推倒重做后：对话页只保留对话与 Agent（无课程归属、无教材 RAG、无能力菜单）。
> 历史实现见 git tag `archive-full-v1-20261011`。

## 结构

- `ChatWorkspace.tsx`：页面（会话侧栏 + 消息列 + composer + 右侧产物面板）。
  composer = textarea + 附件（`uploadAgent` 落 blob → extensions.attachments）+ 上下文小圈
  （`ComposerContextChips`）+ 思考强度（`REASONING_EFFORT_*`）+ `ModelSelector`。
- `model/store.ts`：对话单 store（会话 CRUD、消息状态机、事件路由、追问卡、持久化）。
  事件必须匹配当前轮次与会话（迟到/串会话/重复丢弃）；`send` 经 `buildChatRequest` 组装历史。
- `model/chat-service.ts`：通道分流——**默认 Agent 通道**（`agent-chat-service` → `/agent/stream`）；
  显式注入 `stream` 时走 `/chat/stream`（测试/纯问答回退）。
- `model/agent-chat-service.ts`：agent-stream 事件 → 统一 `ChatServiceEvent`；
  `wait-confirm` 映射为追问卡（approve/reject 与选择值经 `/agent/confirm` resume）。
- `Message.tsx` / `AskUserCard.tsx`：消息渲染（markdown/推理/阶段/工具过程/产物入口）与追问卡。
- `ArtifactPanel.tsx`：右侧产物面板（消息 artifacts 的标签化查看）。

## 纪律

- 不在模块顶层读 `window`/`document`/localStorage；浏览器能力置于客户端生命周期内。
- 追问卡与确认卡共用 `AskUserCard`；写操作确认必须显式点击（不自动提交）。
- 测试：`NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit`；组件级 jsdom 覆盖，
  e2e 对齐见 CURRENT_STATUS 台账。
