# 动画清单（S1 结构化版）

2026-09-09 本批学习问答改按用户指定 `deeptutor-page/src/style.css` 与 vendored Thinking-orbs 核对。三视口静态/动态检查和菜单录像通过；最终相关 e2e **65/65**，本轮 FFmpeg 无效二进制及修复证据见 [STATUS](../STATUS.md)。以下旧轮失败保留作历史，其他模块动画未重新验收。

2026-09-08 本轮实际全量 e2e：91 通过、chat-motion 1 项 context teardown 超时（45 秒）。保留该失败，后续专项诊断见 [STATUS](../STATUS.md)。本轮只人工查看阅读缺陷静态截图，未重新验收全部动画。

状态词汇：`待实现` / `部分实现` / `实现待验收` / `已验收`。条目 id：`M-<场景>`。原版没有动画的位置不添加装饰动画（R16 教训：追问卡进场已按此移除并加防回归断言）。

| id | 场景 | 参考参数与来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| M-composer-width | 输入框宽度 | 指定主页 composer max-width 912px，外层含 48px 留白 | 已验收 | 2026-09-09 用户参考覆盖旧 768→960 扩宽；首次发送 20 帧采样证明输入列不横向跳动；测试同步保留 textarea 150ms 高度过渡 |
| M-pop | 输入区弹出层 | 指定主页入场 180ms cubic-bezier(.16,1,.3,1)，y6/scale.96；保留项目退出 160ms y4/scale.97 | 已验收 | 2026-09-09 菜单进出场、快速开关、inert/焦点回归通过；当前录像和定格帧位于 docs/qa/chat-home-20260909/；本批范围仅学习问答 |
| M-trace | 过程展开 | TracePresentation.tsx：300ms，Tailwind ease-out=cubic-bezier(0,0,0.2,1) | 实现待验收 | --ease-standard 与弹出层缓动区分；中点帧已人工查看 |
| M-ask-card | ask_user 卡片 | AskUserOptions.tsx：卡片无进场装饰动画；选项 transition-colors 150ms | 实现待验收 | R16 移除原版不存在的进场 pop，e2e 断言 animationName=none 防回归；选项 150ms 过渡 |
| M-config-list | 模拟配置列表插入 | 160ms opacity/translateY | 部分实现 | 插入已实现；退出与重排待补 |
| M-settings-nav | 设置分类悬停与定位 | 160ms 背景、滚动定位 | 部分实现 | 基础行为已有 |
| M-reduced | 减少动画 | prefers-reduced-motion + 本地覆盖 | 已验收 | 2026-09-09 补 Canvas 本地偏好监听；浏览器像素采样验证普通状态持续变化、系统/本地 reduced 均静止；原 CSS 全局机制保留 |
| M-sidebar-panel | 侧栏/右面板宽度 | 本批指定主页左栏 200ms，右栏/聊天避让 220ms ease-out | 部分实现 | 主聊天 220↔56px 与工作区拖动/恢复/实际布局通过；拖动时禁用避让缓动，取消/卸载清理；其他模块保持其既有审查状态 |
| M-first-send | 欢迎区→首次发送 | 本批指定主页固定 912px 输入内容列；textarea height 150ms ease-out | 已验收 | 不复制参考的示例历史；空态到真实/模拟消息转场、同一发送/停止按钮位置与三视口回归通过；旧宽度过渡被本次用户参考覆盖 |
| M-artifact | 产物面板展开/退出 | 指定主页 translateX(100%)↔0，220ms ease-out | 已验收 | 主聊天入场/退出中间帧、快速重开、退出 inert、拖动中 Escape 清理、标签与持久宽度回归通过；范围限本批主聊天 |
| M-thinking-orb | 思考球与状态文字 | vendored Thinking-orbs：20px 预设/18px 显示/3x；working/solving speed 1，breathing speed .5；文字 1.8s opacity .45↔1 | 已验收 | 复制参考算法，蓝色 currentColor；Canvas 实际像素变化与静止验证、离屏/隐藏暂停源码核对；状态跟随原消息，不重放整条文本动画 |
| M-buttons | 按钮悬停/按下/禁用/加载 | 逐组件核对原版 | 待实现 | S7 |
| M-ask-states | 追问卡状态切换（预览→可答→提交→摘要） | AskUserOptions 实际过渡 | 待实现 | 原版无装饰进场；状态切换动画待逐项核对（S7） |
| M-reading-layout | 阅读导航/伴生面板/选区浮条 | ReadingWorkspace/ReadingCompanion 原版逐组件参数 | 部分实现 | R31 布局缺陷、拖拽/手机面板及动画差距待补；不得统一套 160ms |

动画证据边界：过去扩展/过程的截图与录像记录见 [历史归档](../archive/DELIVERY_HISTORY.md#source-3)；历史通过不覆盖本轮 teardown 失败。S7 仍须逐条对照原版动态验收，不以存在 animationName 或截图文件作为已播放整段证据。
