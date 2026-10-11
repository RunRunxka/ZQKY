# 路由与模块状态（最小骨架版）

更新：2026-10-11（推倒重做）。按 `apps/web/src/app` 与 `apps/web/src/services/navigation.ts` 核对。

| 路径 | 页面与能力 | 状态 |
| --- | --- | --- |
| `/` | 重定向到 `/chat` | 唯一默认首页 |
| `/chat` | 对话：会话管理、流式消息、附件上传、Agent 中断确认卡、产物面板 | `ready` |
| `/settings` | 设置：外观 / 模型与连接 / 关于 | `ready` |
| 其他未知路径 | 404 | 保留公共壳，提供返回对话入口 |

**已删除**（历史实现见 git tag `archive-full-v1-20261011`）：`/lesson-plans`、`/question-bank`、
`/knowledge-points`、`/assessments*`、`/learning-analysis`、`/practices`、`/knowledge-bases*`、
`/books*`、`/courses*`、`/mcp`、`/skills`、规划页捕获路由。

导航清单的唯一运行时来源是 `apps/web/src/services/navigation.ts`（对话 + 设置）。
桌面侧栏展开 220px、收起 56px；手机为模态抽屉。新增路由必须同步本表与导航登记。
