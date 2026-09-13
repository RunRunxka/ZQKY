# 动画清单与验收边界

更新：2026-09-12。全站视觉基准为当前学习问答；模块专属动画对照固定 DeepTutor，原版没有则不添加。下表“已验收”均绑定具体日期、候选和范围；旧模拟生成动画不能据此视为当前可发起能力。历史65项、teardown首败及后续修复见 [交付历史](../archive/DELIVERY_HISTORY.md#snapshot-status-20260910)，当前计划与验证边界见 [STATUS](../STATUS.md)。

状态词汇：待实现、部分实现、实现待验收、已验收；逐项记录开始/过渡/结束、快速中断、减少动画与焦点。

2026-09-12 B-ACCEPT补验：候选99aea55现有e2e 80/80通过，其中`chat-home.spec.ts` 4项、`sidebar-transition.spec.ts` 4项、`sidebar-chat-fixes.spec.ts` 5项重新验证思考球像素变化/系统与本地减少动画、右面板退出中断/inert/拖拽Escape清理、三视口聊天与导航过渡。实际DeepSeek Flash8192样本又验证推理自动展开/收起与手动优先，但不声称全站动画或推理动画曲线已完整验收。数据与截图见 [本次结果](../qa/acceptance-20260912/summary.json)。

| id | 场景 | 参考参数与来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| M-composer-width | 输入框宽度 | 指定主页 composer max-width 912px，外层含 48px 留白 | 已验收 | 2026-09-09 用户参考覆盖旧 768→960 扩宽；首次发送 20 帧采样证明输入列不横向跳动；测试同步保留 textarea 150ms 高度过渡 |
| M-pop | 输入区弹出层 | 指定主页入场 180ms cubic-bezier(.16,1,.3,1)，y6/scale.96；保留项目退出 160ms y4/scale.97 | 已验收 | 2026-09-09 菜单进出场、快速开关、inert/焦点回归通过；当前录像和定格帧位于 docs/qa/chat-home-20260909/；本批范围仅学习问答 |
| M-trace | 过程展开 | TracePresentation.tsx：300ms，Tailwind ease-out=cubic-bezier(0,0,0.2,1) | 实现待验收 | --ease-standard 与弹出层缓动区分；中点帧已人工查看 |
| M-ask-card | ask_user 卡片 | AskUserOptions.tsx：卡片无进场装饰动画；选项 transition-colors 150ms | 实现待验收 | 组件保留原无装饰进场规则与150ms选项颜色；旧模拟e2e已删除，当前真实无ask_user事件，接入后重验完整运行过程。 |
| M-config-list | 模拟配置列表插入 | 160ms opacity/translateY | 部分实现 | 历史模拟配置组件有160ms插入；主聊天执行禁用，退出/重排和真实运行场景未验收。 |
| M-settings-nav | 设置分类悬停与定位 | 160ms 背景、滚动定位 | 部分实现 | 基础行为已有 |
| M-model-management | 供应商/模型卡片、详情与参数折叠 | 固定DeepTutor ModelCards.tsx：background-color/border-color/transform 150ms、active scale .995，箭头150ms位移反馈 | 实现待验收 | 2026-09-13 MODEL-EXEC v3 实装：卡片 `transition: border-color/background-color/transform 150ms`、`:active scale(0.995)`、箭头 hover translateX(2px)；`@media (prefers-reduced-motion: reduce)` 关闭卡片/箭头/选项过渡与 spin 动画。e2e `model-settings.spec.ts` 覆盖三视口与减少动画可打开详情，真实联调亦覆盖减少动画；本批新增「关闭未保存更改先确认」的行为断言（非曲线）。未录制曲线采样、未做快速关闭重开与焦点返回，故不升为已验收 |
| M-reduced | 减少动画 | prefers-reduced-motion + 本地覆盖 | 已验收 | 2026-09-09 补 Canvas 本地偏好监听；浏览器像素采样验证普通状态持续变化、系统/本地 reduced 均静止；原 CSS 全局机制保留 |
| M-sidebar-panel | 侧栏/右面板宽度 | 学习问答左栏 200ms，右栏/聊天避让 220ms ease-out | 部分实现 | 2026-09-10 H0 候选：220/56px和200ms统一在公共壳；1440/1920的软导航逐帧、菜单几何与字体比较、折叠状态/历史返回回归；390抽屉遮罩/焦点/关闭/字体比较。隐藏直达页当前菜单和其他模块专属面板仍待验收。 |
| M-first-send | 欢迎区→首次发送 | 学习问答固定 912px 输入内容列；textarea height 150ms ease-out | 已验收 | 2026-09-09 主页候选：固定内容列、textarea过渡、同一发送/停止按钮与三视口通过；范围限学习问答。 |
| M-artifact | 产物面板展开/退出 | 指定主页 translateX(100%)↔0，220ms ease-out | 已验收 | 2026-09-09 主页候选：入场/退出中间帧、快速重开、退出 inert、拖动中 Escape 清理、标签与持久宽度回归通过；范围限学习问答历史产物 |
| M-thinking-orb | 思考球与状态文字 | vendored Thinking-orbs：20px 预设/18px 显示/3x；working/solving speed 1，breathing speed .5；文字 1.8s opacity .45↔1 | 已验收 | 2026-09-09 主页候选：复制参考算法，蓝色 currentColor；Canvas 实际像素变化与静止验证、离屏/隐藏暂停源码核对；状态跟随原消息，不重放整条文本动画 |
| M-buttons | 按钮悬停/按下/禁用/加载 | 逐组件核对原版 | 待实现 | S7 |
| M-ask-states | 追问卡状态切换（预览→可答→提交→摘要） | AskUserOptions 实际过渡 | 待实现 | 原版无装饰进场；状态切换动画待逐项核对（S7） |
| M-reading-layout | 阅读导航/伴生面板/选区浮条 | ReadingWorkspace/ReadingCompanion 原版逐组件参数 | 部分实现 | R31布局/拖拽和R32手机面板有历史实现记录；本次未跑阅读专属动画验收，仍需按参考逐个核参数/中断/退出，不能将原视图缺项视为允许缩减。 |
| M-kb-progress | 知识库文档处理进度条/徽标切换 | 参考 KbStatusBadge/进度条：`transition-all duration-300`、`animate-spin`；徽标/banner 无进出场动画 | 实现待验收 | 2026-09-12补查1920/390×正常/系统reduce共4个解析中样本，35%与取消入口可读，均能到就绪；系统reduce使公共壳transition 0.2s→1e-05s。采样未观察到活动CSS/Web Animations，未证明进度内条300ms曲线或完整中断，故不升为已验收；[探针](../qa/acceptance-20260912/visual-probes.json) |

动画证据边界：历史截图/录像和首败不删；已验收只覆盖表中日期与候选。H1–H5 随功能批同步验收模块动画，H6 再集中补漏；不以存在 animationName 或截图文件作为整段已播放证据。
