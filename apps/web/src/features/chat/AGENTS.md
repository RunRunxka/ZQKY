# chat 模块约定（学习问答）

先读根 `AGENTS.md`。本模块是全站默认主页 `/chat` 与视觉基准，**主聊天只走真实 FastAPI 三协议 SSE**，
不存在运行时模拟分支（`mock` 仅用于读取旧历史与测试替身注入）。

## 结构与职责

- `ChatWorkspace.tsx`：页面装配（输入区、消息流、产物面板、学习记录入口、课程归属条）。
  只组合状态与服务，不直接落库或发请求。
- `model/store.ts`：会话与轮次状态（Zustand 双 store + 统一 `ChatService` 事件），
  含 sessionId/turnId 事件守卫、串行 flush、终态守卫。`send()` 只透传，不二次裁剪。
- `model/request-budget.ts`：唯一请求构建入口 `buildChatRequest()`——课程上下文 + 历史 +
  当前问题共享同一预算，裁剪阶梯固定，当前问题逐字不裁剪；`BACKEND_REQUEST_LIMITS` 是后端硬限制的单一事实来源。
- `model/chat-service.ts` / `chat-sse.ts` / `chat-stream.ts`：SSE 连接与事件分发。
- `model/rag-service.ts`：本地教材 RAG 通道（`/api/v1/rag/*`），独立于普通聊天，无需配置云模型。
- `Message.tsx` / `AnswerMarkdown.tsx` / `StreamingMarkdown.tsx` / `ReasoningDisclosure.tsx`：
  正文/推理的流式与终态渲染（KaTeX 公式、代码围栏保护、安全分块；活跃流轻量呈现 + 增量合并）。
- `artifacts/`：智能出题（Quiz）与深度报告（Report）产物视图。**「保存到题库/笔记」已随学习空间移除**，
  出题作答仅当前消息内即时判定，报告仅展示，均不持久化。
- `styles/`：`chat.css` / `chat-home.css`。

## 关键不变量

- **真实优先**：真实失败不回退模拟；不引入 `?mode=mock` 捷径；不把测试替身放回生产。
- **持久化**：会话/草稿/轮次快照存 IndexedDB `zhiqikeyuan-chat`（`services/chat-repository.ts`）；
  revision、串行 flush、终态守卫必须保持；旧 `zhiqikeyuan-chat-mock` 留存但不读写。
- **轮次冻结**：重试沿用冻结在助手消息上的原快照（课程/能力/附件），课程修改只影响新轮。
- **请求预算**：见 `request-budget.ts`；数字是字符估算（1 token≈2 字符），不宣称精确 token。
- **已断开的旧能力**：人设选择、知识来源/会话引用、「保存到题库/笔记」均已随学习空间移除；
  输入区只保留附件。`Message.tsx` 仍只读渲染历史消息快照里的 `persona`/`knowledge` 标签（向后兼容旧数据，不新写入）。
- **课程上下文**：经 `services/course-session.ts` 把课程快照渲染为一条 system 消息插在请求最前，
  不新增请求字段、不改后端协议；归属只按稳定 `courseId`，不按标题/最近访问猜测。

## 修改后必测

`npm.cmd run typecheck`、`lint`、`test:unit`；涉及流式/渲染/会话另跑 `test:chat` 与相关 e2e
（`chat*.spec.ts`、`course-sessions.spec.ts`）。性能敏感改动需复核长推理流帧间隔（见批次证据）。
