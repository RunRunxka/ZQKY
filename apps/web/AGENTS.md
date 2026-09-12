# 前端开发约定

先读根AGENTS.md。本文件补充正式前端范围的规则。

- 使用Next.js App Router。页面组件以服务端为默认；需要状态、浏览器API和事件时建立明确客户端边界。`use client` 不等于允许模块顶层访问window。
- 路由在 `src/app`，共享壳为 `WorkspaceShell`。新增功能先登记 `src/services/navigation.ts` 与 `docs/ROUTES.md`，再建立业务模块。标记为规划中的页面只能解释状态，不伪造数据或可用服务。
- 公共壳仅接收标题、操作区、内容与导航前回调，不导入教案数据类型。离开有未保存内容的模块时，调用模块的保存接口后再切路由。
- 客户端业务采用props/Context依赖注入，Zustand通过工厂创建实例。浏览器本地存储仅用于本地阶段，不宣称云端持久化。
- 全局CSS只维护主题与公共布局控件；模块样式使用明确根class作用域或CSS Modules。打印规则必须限定模块，`@page`使用命名页面。
- 全站首页、列表、详情、弹窗和公共控件以当前学习问答为唯一视觉基准，保留智启课源蓝色主题与业务功能。`/chat` 是默认主页；品牌、404、错误恢复和 metadata 不得再把教案误写成全站主页。
- 公共壳沿用学习问答的 220/56px 桌面侧栏、当前项、折叠动画与手机模态抽屉。学习记录 236px 中栏和 912px 对话宽度只属于聊天；阅读、教案和编辑器按业务结构布局。已实现直达页即使不出现在桌面主导航，也必须在移动抽屉中有可解释的当前菜单和焦点目标。
- 全站迁移以学习问答的字体层级为目标：页面壳、控件和普通正文参照 Chat Geist 中文回退，聊天标题与助手回答的阅读字体参照 Chat Lora；当前公共导航仍是 Arial/微软雅黑，纳入后续统一和回归。颜色优先复用 `--blue`、`--surface`、`--ink`、`--line`。每个页面/视觉批同时验证 1440×900、1920×1080、390×844、键盘焦点和减少动画，不把存在 CSS 或单张截图当成视觉验收。
- 本地服务仅监听127.0.0.1；开发入口5173，浏览器测试5174。端口占用先查进程归属，不直接结束未知进程。
- 不依赖个人缓存中的Node包、硬编码Windows用户路径或Vite源码URL。浏览器回归使用项目内Playwright及UI/JSON导入机制。
- 依赖以根锁文件为准；不引入第二份正式前端锁文件。Next/React升级同步检查peer依赖和所有导出依赖。
- 根命令负责类型、Lint、测试、构建；新增测试尽量验证用户行为、状态隔离和错误恢复，不复制实现细节。

当前ESLint的 `react-hooks/set-state-in-effect` 与 `react-hooks/refs` 规则针对既有命令式弹窗和持久化适配关闭；其他Hooks规则保留。不要据此在渲染期间访问DOM或写存储。

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
