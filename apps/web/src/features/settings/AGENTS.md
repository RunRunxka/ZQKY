# settings 模块约定（设置）

先读根 `AGENTS.md`。入口 `/settings`，统一管理外观、模型与连接、MCP、Skills 与关于。
**MCP/Skills 的唯一管理实现**（`/mcp`、`/skills`、`/space/mcp`、`/space/skills` 只重定向到这里）。

## 结构与职责

- `SettingsWorkspace.tsx`：分面板工作区——外观（显示/减少动画）、模型与连接（复用 model-settings 模块）、
  MCP（`#mcp`）、Skills（`#skills`）、关于（实现状态与版本）。
- `ExtensionManager.tsx`：MCP/Skills 目录管理（本地模拟，未接入真实执行）。
- 样式：`settings.css` + `styles/`。

## 关键不变量

- **MCP/Skills 唯一管理**：目录与管理只维护这一套；聊天扩展目录与本页共享，当前未接入的执行项明确标不可用，
  不能把保留组件写成可用能力。
- **外观设置**：减少动画（系统偏好 + 本地设置均生效）与显示偏好经 CSS 变量与 `motion.css` 落地，不加第二套动画库。
- **模型与连接**：业务逻辑归 model-settings 模块，本模块只做面板挂载，不重复实现。
- 设置改动更新聊天候选（经 `services/extension-catalog.ts`），历史轮次快照不变。

## 修改后必测

`typecheck`/`lint`/`test:unit`；e2e 跑 `settings.spec.ts`、`replica-settings.spec.ts`、
`model-settings*.spec.ts`（涉及模型面板时）。
