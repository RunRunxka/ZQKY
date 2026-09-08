# 动画清单（S1 结构化版）

2026-09-08 本轮实际全量 e2e：91 通过、chat-motion 1 项 context teardown 超时（45 秒）。保留该失败，后续专项诊断见 [STATUS](../STATUS.md)。本轮只人工查看阅读缺陷静态截图，未重新验收全部动画。

状态词汇：`待实现` / `部分实现` / `实现待验收` / `已验收`。条目 id：`M-<场景>`。原版没有动画的位置不添加装饰动画（R16 教训：追问卡进场已按此移除并加防回归断言）。

| id | 场景 | 参考参数与来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| M-composer-width | 输入框宽度变化 | ChatComposer.tsx：650ms cubic-bezier(.16,1,.3,1)，max-width 768→960 | 实现待验收 | e2e chat-composer.spec.ts：duration/easing 断言+发送后 20 帧采样捕获中间宽度（真实发生）；整段录像动态验收待 S7 |
| M-pop | 输入区弹出层 | ChatComposer.tsx：160ms cubic-bezier(.16,1,.3,1)，进 y6/scale.96、退 y4/scale.97 | 实现待验收 | ExtensionPicker 进出场+快速开关+中断正确；录像 webm 与定格帧已人工查看（tests/.e2e-output-20260907-r12） |
| M-trace | 过程展开 | TracePresentation.tsx：300ms，Tailwind ease-out=cubic-bezier(0,0,0.2,1) | 实现待验收 | --ease-standard 与弹出层缓动区分；中点帧已人工查看 |
| M-ask-card | ask_user 卡片 | AskUserOptions.tsx：卡片无进场装饰动画；选项 transition-colors 150ms | 实现待验收 | R16 移除原版不存在的进场 pop，e2e 断言 animationName=none 防回归；选项 150ms 过渡 |
| M-config-list | 模拟配置列表插入 | 160ms opacity/translateY | 部分实现 | 插入已实现；退出与重排待补 |
| M-settings-nav | 设置分类悬停与定位 | 160ms 背景、滚动定位 | 部分实现 | 基础行为已有 |
| M-reduced | 减少动画 | prefers-reduced-motion + 本地覆盖 | 已验收 | 全局机制接管所有新组件；刷新保持 |
| M-sidebar-panel | 侧栏/右面板宽度 | 逐组件核对原版 | 部分实现 | 主聊天结果宽度调节已有；阅读收起存在 R31，其他页面待补 |
| M-first-send | 欢迎区→首次发送 | ChatComposer 宽度过渡（同 M-composer-width），textarea minHeight 64→28 | 实现待验收 | e2e 同步覆盖：欢迎 768→会话 960+中间帧采样；textarea 高度过渡 0.15s ease-out；整段录像待 S7 |
| M-artifact | 产物面板展开 | 逐组件核对原版 | 实现待验收 | S3 组件已有；动态过渡与快速中断仍需验收 |
| M-buttons | 按钮悬停/按下/禁用/加载 | 逐组件核对原版 | 待实现 | S7 |
| M-ask-states | 追问卡状态切换（预览→可答→提交→摘要） | AskUserOptions 实际过渡 | 待实现 | 原版无装饰进场；状态切换动画待逐项核对（S7） |
| M-reading-layout | 阅读导航/伴生面板/选区浮条 | ReadingWorkspace/ReadingCompanion 原版逐组件参数 | 部分实现 | R31 布局缺陷、拖拽/手机面板及动画差距待补；不得统一套 160ms |

动画证据边界：过去扩展/过程的截图与录像记录见 [历史归档](../archive/DELIVERY_HISTORY.md#source-3)；历史通过不覆盖本轮 teardown 失败。S7 仍须逐条对照原版动态验收，不以存在 animationName 或截图文件作为已播放整段证据。
