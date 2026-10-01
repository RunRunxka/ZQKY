# 侧栏与问答逻辑修复验收（2026-09-09）

全部截图来自隔离浏览器、5174 测试端口与固定测试数据；未操作用户 5173 会话。推理截图使用测试上游，经正式 FastAPI 与 Next 代理传输，不是供应商验收。

| 文件 | 验证状态 |
| --- | --- |
| [independent-history.png](independent-history.png) | 全局侧栏收起为 56px，236px 学习记录仍独立显示；模型未配置/后端不可用错误如实显示 |
| [mobile-drawer.png](mobile-drawer.png) | 390px 模态抽屉，完整菜单、遮罩、关闭入口；当前 `/space/chat-history` 对应学习空间高亮，测试断言打开后该项获得焦点 |
| [reasoning-streaming.png](reasoning-streaming.png) | 1280px 推理先显示，正文仍被上游门闩阻断；推理公式已渲染 |
| [reasoning-restored-mobile.png](reasoning-restored-mobile.png) | 刷新恢复后手动展开推理，正文行内/块级公式正常，390px 无页面横向溢出 |

检查：typecheck、lint、build 通过；前端单元 245/245、后端 88/88；相关 e2e 首轮最终集合 42/43（唯一失败为旧顶栏断言），调整为当前聊天工具栏后该场景单独复跑 1/1；侧栏截图等待动画稳定后再复跑 5/5。三协议 HTTP 集成最终 9/9。不能将以上表述为一次全量 e2e 绿灯或真实供应商通过。

相关用例：`sidebar-chat-fixes.spec.ts`、`chat-home.spec.ts`、`chat.spec.ts`、`chat-deeplink.spec.ts`、`chat-composer.spec.ts`、`chat-composer-boundaries.spec.ts`、`navigation.spec.ts`、`space-pages.spec.ts`、`lesson-plan.spec.ts`、`chat-reasoning.spec.ts`、`chat-live.spec.ts`。详细过程与范围见 [STATUS](../../STATUS.md)。
