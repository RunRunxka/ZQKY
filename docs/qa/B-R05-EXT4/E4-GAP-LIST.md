# B-R05-EXT4-E4 逐页差距清单（v1）

- 核对时间：2026-09-19（只读取证，未运行 build/dev/e2e/单测，未做 Git 操作，未修改任何产品/测试/文档源文件）
- 参考仓库：`F:\DeepTutor` 固定提交 `42fab3cf429a1fbf36b257ab8d116a3814964202`（已用 `git rev-parse` 核实一致，工作区干净）
- 当前仓库 HEAD：`b0b24fad711b3912b9f1bdaf7d107cd18404e7ee`（分支起点 `b0b24fa` 一致）
- 审计范围：仅 P-settings（`/settings` → SettingsWorkspace + ExtensionManager，模型区内层只登记不改）与 P-lesson-plans（`/lesson-plans` → LessonPlanWorkspace 及 components）两页的信息结构 / 交互状态 / 动画三类差距，外加两份风险清单。
- **教案无参考仓库对照的说明**：参考仓库 F:\DeepTutor 无教案模块（无 `/lesson-plans` 对应物），教案页是目标自有页。其"参考"为当前 `/chat` 视觉基准（`apps/web/src/features/chat/styles/chat-home.css`、`chat.css`）与既有教案业务（`apps/web/src/features/lesson-plan/AGENTS.md` 约定）。下文教案条目不虚构 DeepTutor 参考，凡引用均为 /chat 基准文件或教案自身文件。

---

## 摘要

### P-settings 最值得做的 3~5 条
1. 设置索引导航行视觉对齐参考 Row（图标+标题+描述小字、hover/active 双态、focus 态），保留 `aria-current="location"` 语义（`replica-settings.spec.ts:23-24` 依赖），参数沿用 M-settings-nav 160ms。
2. 补搜索框 focus 态与清除按钮（参考 `SettingsNav.tsx:266-285`）；当前搜索框无 focus 视觉、无清空入口（`settings.css:87-95` 仅边框）。
3. 补搜索无结果空态文案（参考 `SettingsNav.tsx:299-303`）；当前过滤后列表直接为空无提示（`SettingsWorkspace.tsx:71-98`）。
4. ExtensionManager 卡片与按钮视觉统一（hover/disabled/focus 态、角色开关视觉），已有 `settings-enter 160ms` 入场（`settings.css:112-118,149-158`）可保留。
5. 错误/加载呈现保持"模型区内层"现状（`ModelSettingsPanel.tsx:293-308`），不引入参考式页级横幅（见范围矛盾 2）。

### P-lesson-plans 最值得做的 3~5 条
1. 导航分段/章节项 hover-active 视觉微调（`lesson-plan.css:393-420` 已有基础态），只增不改。
2. 导出菜单展开补轻量进出场动画——若做，参数必须对齐 /chat 基准弹层（`chat-home.css:233` `chat-home-popup 180ms cubic-bezier(0.16,1,0.3,1)`），记 MOTION_MATRIX 新条目，状态最高"实现待验收"。
3. 表单分区标题、type-chip、模板缩略卡的视觉统一（`lesson-plan.css:783-813`、`FormPanel.tsx:20-112`），不碰字段结构。
4. 预览工具栏图标按钮 hover/disabled 态统一（`PreviewPane.tsx:60-89`、`lesson-plan.css:190`）。
5. toast / storage-alert 视觉统一（`lesson-plan.css:1355+`、`EditorOverlays.tsx:142-163`），不改 role 与文案（e2e 依赖）。

### 全局性发现
- **settings.css 归属**：仅 `SettingsWorkspace.tsx:6` 引用（188 行）。任务卡 3.2 已定 I1 独占。注意其中 `.settings-toolbar/.settings-form/.settings-hint` 等类名与 `model-settings.css` 存在**同名类全局层叠**（详见附录 A）。
- **model-settings.css 被聊天共用**：`ChatWorkspace.tsx:59` import 了 `model-settings.css`；聊天模型选择器 `ModelSelector.tsx:77,108,118` 使用 `.model-select-trigger/.model-choice`，且 `chat-home.css:203,211,247,516` 以 `.chat-home-shell` 前缀覆盖。改既有选择器必波及聊天弹层。
- **教案 CSS 体量与禁区**：`lesson-plan.css` 1651 行、`print.css` 86 行（`@page lesson-plan` + 两个 `@media print` 块）。`lesson-plan.css` 内**无** `@media print` 块（仅有 1600+/max-height850/1279/767/reduced 五个屏幕 @media，行 1405/1428/1451/1496/1643）——I2 只增屏幕样式即天然安全，但仍不得新开 `@media print`。
- **同名类层叠顺序事实**：`SettingsWorkspace.tsx` 的 import 顺序是第 4 行 `ModelSettingsPanel`（连带 model-settings.css）先于第 6 行 `settings.css`，故同页加载时 `settings.css` 的 `.settings-form{display:grid}`（:128）覆盖 `model-settings.css` 的 `.settings-form{display:flex}`（:261）。此为既有事实，本批不要靠改 import 顺序"修"它（会翻转模型区表单布局）。

### 窄视口风险清单
| # | 位置 | 证据 | 风险 | 倾向 |
|---|---|---|---|---|
| N1 | 设置页 ≤767px 索引条带 | `settings.css:159-184`（`.settings-index a` `white-space:nowrap`、搜索框 `width:120px`） | 长标题横向滚动属预期（overflow:auto），但新增 padding/边框会改变条带高度与文档区起点；搜索框仅 120px，输入区极窄 | 视觉增量不改尺寸与 nowrap；复测 390×844 |
| N2 | 设置页模型区（只读区） | `model-settings.css:403-475` 已有 767 断点；`model-settings.spec.ts:228-237` 已断言 390 无溢出 | 外层容器增量若加固定宽度/负 margin 会破坏既有断言 | 只追加 `.settings-workspace` 后代作用域且不加定宽 |
| N3 | 教案预览工具栏 | `PreviewPane.tsx:60-89`（缩放/适合宽度/专注按钮组）；`lesson-plan.css` 767 断点 :1496 未显式处理 `.preview-toolbar` 换行 | [未验证] 390px 下按钮组是否换行/溢出未实测（既有 e2e `lesson-plan.spec.ts:168-181` 三视口通过说明现状不溢出，但新增元素后需重测） | 新增控件前 `getBoundingClientRect` 实测 |
| N4 | 教案导出菜单 | `ExportMenu.tsx:16-70` + `lesson-plan.css:1526`（767 下 save-status 处理） | 导出弹层/菜单若加动画或绝对定位，窄屏可能超出右缘 | 菜单定位保持现状，只做透明度/位移动画 |
| N5 | 两页通用 | `lesson-plan.spec.ts:168-181`、`settings.spec.ts:20`、`replica-settings.spec.ts:35`、`model-settings.spec.ts:154,236,245` 均 `scrollWidth <= innerWidth` | 任何新增固定宽元素（含 box-shadow 视觉外的实际盒）都可能破断言 | 增量样式全部用既有变量与百分比/min() |

### e2e 冲突风险汇总（详见风险清单 1 与附录 B）
- 模型区 5 处可访问名称锚点（卡片 aria-label / 用于问答 / checkbox 名称 / `^Base URL` label / dialog aria-label）为高危锚点，共涉 `model-settings.spec.ts` 9 例 + `model-settings-nesting.spec.ts` 4 例。
- `settings.spec.ts:17-18` 依赖错误态下 `.settings-form/.settings-card` count 0：**注意 `.settings-form` 同时被 ExtensionManager 使用**（`ExtensionManager.tsx:109`），错误态下 ExtensionManager 不渲染表单故断言成立；若把扩展表单类名改掉或新增渲染路径需复核。
- `replica-settings.spec.ts` 依赖：`role="switch"` + `aria-checked`（:16-19）、`设置分类` 导航名（:23,27）、`html[data-motion=reduced]`（:32）、`/mcp`、`/skills` 重定向（:5,21）。导航/开关的语义与 aria 属性不得改。
- 教案侧 e2e 依赖的类名锚点：`.subject-cell/.save-status/.fill-warnings/.process-editor/.paper/.print-text/.secondary-cell/.approval-line/.paper-footer/.preview-pane/.storage-alert/.chat-page/.chat-toolbar/.sidebar-brand`（`lesson-plan.spec.ts:27-49,60-160,183,191`）。视觉批不得删改这些类名。

### 与既有 MOTION_MATRIX 条目的关系
- `M-settings-nav`（`docs/replica/MOTION_MATRIX.md:16`，"160ms 背景、滚动定位"）：当前实现即 `settings.css:27` `transition: background 160ms` + `SettingsWorkspace.tsx:30,84-92` 滚动定位。**参数以矩阵 160ms 为准**（[推断] 参考实际是 Tailwind `transition-colors` 默认 150ms，`SettingsNav.tsx:395,460` 无 duration 后缀；矩阵记录的 160ms 对应当前实现，不建议改参数，差异记录在案）。
- `M-model-management`（`MOTION_MATRIX.md:17`，150ms 卡片/箭头、`active:scale(.995)`）：已在 `model-detail.css:20-31,90-95` 实装且 reduce 已关闭（:441-453）。本批模型区只读，实装建议一律不触碰这些参数；新动画不得引入新时长/缓动体系。

---

## P-settings（/settings）

### 信息结构
| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|---|---|---|---|
| S1 | 左侧导航为"单文档锚点+分组折叠"结构：分类头行可折叠（chevron 按钮 aria-expanded），子行带 blurb 提示；当前为 5 个平铺一级分区，无折叠层级 | `SettingsNav.tsx:368-421`（CategoryHeaderRow + 展开/折叠按钮 :404-418）、`:305-356`（standalone/分组渲染） | `SettingsWorkspace.tsx:7-13`（5 sections）、`:71-98`（平铺渲染） | 结构不同（[推断] 属有意保留差异：任务卡 6 只要求"分类导航/锚点/搜索、五分区视觉统一"） |
| S2 | 导航行有失败红点徽标（服务诊断 failed 才显示） | `SettingsNav.tsx:224-230,470-475`（`bg-red-400` 圆点） | 无对应（`SettingsWorkspace.tsx:75-98` 仅标题+小字） | 缺失 |
| S3 | 搜索无结果空态文案 | `SettingsNav.tsx:299-303`（"No settings match …"） | 无（过滤后直接空列表）`SettingsWorkspace.tsx:71-98` | 缺失 |
| S4 | 搜索框清除按钮 | `SettingsNav.tsx:275-284`（X 按钮 aria-label Clear） | 无 | 缺失 |
| S5 | 页级工具栏：草稿三态状态行（Unsaved changes/Draft not applied yet/All changes saved）+ Tour/Discard/Save draft/Apply 四按钮 + busy spinner + 存储路径 tooltip | `SettingsToolbar.tsx:56-71`（三态文案与色调）、`:73-128`（按钮组、disabled:opacity-40 :94,104,118）、`:77` title=storagePath | 无对应。当前模型区直写服务端（`ModelSettingsPanel.tsx:197` expectedRevision），无草稿概念；扩展管理为本地模拟即时保存（`ExtensionManager.tsx:30-39`） | 有意保留差异（架构不同：contract-v1 无设置草稿层） |
| S6 | 页级加载/错误横幅（loading spinner 行 + role=alert 琥珀色错误框 + Retry） | `SettingsLoadStatusBanner.tsx:18-25`（loading）、`:38-64`（role=alert + Retry + 原因文案） | 错误/加载在模型区内层：`ModelSettingsPanel.tsx:293-308`（"正在读取模型设置…"/"无法读取模型设置：…"+重试）；扩展管理器 notice 走 `role=status`（`ExtensionManager.tsx:105`） | 结构不同（错误态收在内层；`settings.spec.ts:12-15` 依赖内层文案，页级横幅若加不得重复"重试"名称） |
| S7 | Overview 落地区块：标题+副标题+引导按钮、后端在线状态条（圆点+内存）、界面/输出语言双开关、服务就绪面板、Browser API base 行、Tour 入口、草稿时间戳 | `SettingsOverview.tsx:98-121`、`SettingsStatusPanel.tsx:21-46`、`SettingsOverview.tsx:125-152,154,156-166,168-179`；就绪面板 `SettingsReadinessPanel.tsx:21-30`（状态色调） | "外观"区仅减少动画开关+status 行（`SettingsWorkspace.tsx:101-123`）；"关于"区 3 行说明（:136-142）；无状态条/就绪面板/语言开关/Tour | 缺失（多数属业务能力，本批"只做视觉不补业务"下仅可做**视觉壳**，是否呈现状态条由队长裁定，见范围矛盾 1） |
| S8 | 参考模型区为"服务×供应商卡片+弹窗编辑"（Providers 卡片、ProfileCard/ModelCard、连接凭据层 Connections） | `ServiceConfigEditor.tsx:475-530`（卡片网格）、`ModelCards.tsx:263-326`、`ConnectionsEditor.tsx:83-120` | 当前为 contract-v1 自有结构：三分区导航（问答模型/连接管理/默认模型）+ provider-grid + 详情弹窗（`ModelSettingsPanel.tsx:328-348,430-456`、`ProviderCard.tsx:28-61`） | 有意保留差异（任务卡 2.1 禁区，不逐项对照、不实施） |
| S9 | 窄视口导航：参考用原生 select + optgroup（分组下拉） | `SettingsNav.tsx:135-182` | ≤767px 为横向滚动条带（`settings.css:159-184`） | 结构不同（[推断] 有意保留差异；条带已满足 390 断言） |
| S10 | 参考导航行悬停 title 提示（blurb） | `SettingsNav.tsx:457`（`title={hint}`） | 当前 `<small>` 常显描述（`SettingsWorkspace.tsx:96`），信息等价、形式不同 | 文案/结构不同（可保留现状） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| I1 | 搜索框 focus 背景/边框反馈 | `SettingsNav.tsx:273`（`focus:bg-[var(--accent)]`） | `settings.css:87-95` 无 :focus 规则（仅全局兜底） | 缺失 |
| I2 | 搜索清除按钮 hover 态 | `SettingsNav.tsx:280`（hover:text-foreground） | 无 | 缺失 |
| I3 | 导航行 hover/current 双态 | `SettingsNav.tsx:460-464`（active=accent 底+font-medium；hover=accent/50） | `settings.css:29-32`（hover 与 [aria-current] 同为 `var(--surface)`，无字重区分） | 结构不同（可视觉增强，保留 aria-current 属性不动） |
| I4 | busy/disabled 统一视觉 | `SettingsToolbar.tsx:94,104,118`（`disabled:opacity-40`）；`ServiceConfigEditor.tsx:563` | `settings.css` 无 disabled 规则，依赖全局按钮样式；`ExtensionManager` 按钮 busy 无 spinner | 部分缺失 |
| I5 | 空态结构 | `ServiceConfigEditor.tsx:1176-1187`（零态=仅有 AddCard 的网格，"零态与常态同语言"）；`ModelListPicker.tsx:154-167`（loading/error/empty 三态） | 扩展管理有 `.settings-empty`（`ExtensionManager.tsx:67-69`）；模型区空态已有（`ModelSettingsPanel.tsx:418-428,457-459`，只读区） | 基本一致（扩展侧可对齐视觉） |
| I6 | 键盘可达 | 卡片 `role=button tabIndex Enter/Space`（`ModelCards.tsx:124-135`） | 当前 ProviderCard 用真 `<button>`（`ProviderCard.tsx:28-33`），语义更优 | 有意保留差异（无需改） |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| A1 | 导航行背景过渡 | `SettingsNav.tsx:460,395`（Tailwind `transition-colors`，默认 150ms） | `settings.css:27`（`transition: background 160ms`） | 已有（M-settings-nav 160ms 为准，不改） |
| A2 | 工具栏状态文案淡入 `animate-fade-in`（0.35s ease-out） | `SettingsToolbar.tsx:49,57`；关键帧 `globals.css:646-659` | 无对应状态行 | 缺失（若补状态提示可用 0.35s ease-out 参数，记矩阵新条目） |
| A3 | 弹层进出场：遮罩 160ms ease-out + 卡片 200ms cubic-bezier(0.22,1,0.36,1) | `globals.css:663-687`（dt-overlay-in/dt-pop-in）；调用如 `ServiceConfigEditor.tsx:534` Modal | 共享 Modal 无动画（`apps/web/src/components/ui/modal.css:1-14` 无 animation/transition）；Modal 属共享组件，**不在 I1 可写范围** | 缺失（[推断] 如要统一弹层动效应由队长另行分卡，不在本批设置页范围） |
| A4 | 卡片入场过渡（150ms background/border/transform + active scale .995 + chevron 位移） | `ModelCards.tsx:112-122,139-143` | 模型区已对齐（`model-detail.css:20-31,90-95`，M-model-management 已实装）；扩展卡为自有 `settings-enter 160ms cubic-bezier(0.16,1,0.3,1)`（`settings.css:112-118,149-158`） | 已有（扩展卡参数为自有实现，保留；[推断] 无需向 150ms 对齐） |
| A5 | reduce 动画旁路 | `globals.css:1093-1108`（0.001ms、animate-spin none） | `motion.css:14-25`（0.01ms + html[data-motion]）；模型区另有局部 reduce（`model-detail.css:441-453`） | 已有（新动画必须复用 motion.css 机制，不新增旁路） |

---

## P-lesson-plans（/lesson-plans）

（参考列 = /chat 基准文件 或「目标自有，无参考」。参考仓库无教案模块，不虚构对照。）

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| L1 | 三栏工作台（大纲/编辑/预览）+ 表单分区 + 模板缩略卡 + 预览工具栏（缩放/适合宽度/专注）+ 移动 tabs + 导出菜单，整体为目标自有信息架构 | 目标自有，无参考 | `LessonPlanWorkspace.tsx:41-54`、`OutlinePanel.tsx:30-144`、`FormPanel.tsx:20-112`、`PreviewPane.tsx:53-104`、`MobileTabs.tsx:8-23`、`ExportMenu.tsx:16-70` | 目标自有，无参考（本批只做视觉统一，不重排结构） |
| L2 | 页头保存状态徽标与 /chat 工具栏徽章语言可对齐（状态点+文本） | `/chat` 基准：`chat-home.css` 状态徽章/工具栏语言（chat-home.css:203-247 徽章与触发器风格） | `ExportMenu.tsx:17-20`（save-status + status-dot）、`lesson-plan.css:138-146` | 结构已等价（可做视觉统一） |
| L3 | [推断] /chat 基准的"eyebrow+大标题"层级语言 vs 教案 `form-section-heading`（图标+标题+描述） | `chat-home.css` 标题层级；教案 `FormPanel.tsx:21-29` | 教案自有层级 | 目标自有，无参考（不建议强套 /chat 层级） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| L4 | 按钮/输入 disabled、focus-visible、type-chip focus-within、save-status 错误色、storage-alert 恢复入口、toast 自动消失均已具备 | —（教案自有能力） | `lesson-plan.css:26`（disabled）、`:30-36`（focus-visible）、`:810-813`（focus-within）、`:138-146`（save-status）、`EditorOverlays.tsx:142-154`（storage-alert）、`EditorContext.tsx:49-53` + `EditorOverlays.tsx:155-163`（toast） | 已有（保持，不回退） |
| L5 | [推断] 导出菜单展开无过渡动画 | /chat 基准弹层有 180ms 入场：`chat-home.css:233,348`（chat-home-popup） | `lesson-plan.css:197` `.export-menu` 无 animation | 缺失（可选补，参数对齐 180ms cubic-bezier(0.16,1,0.3,1)，记矩阵新条目） |
| L6 | [推断] 教案 modal（原生 dialog）无入场动画 | /chat 基准 modal 200ms：`chat-home.css:377-380`（chat-home-modal/overlay） | `lesson-plan.css:1297-1305`（modal 无动画）；`EditorOverlays.tsx:49-56` 原生 dialog showModal | 缺失（同上；样式改动须只落屏幕样式，禁入 print 块） |
| L7 | 缩放控件 hover title 与点击复位已有 | — | `PreviewPane.tsx:68-70`（title="点击恢复适合宽度"） | 已有 |
| L8 | 长文案截断 | —（教案自有） | `lesson-plan.css:783` type-chip、预览 print-text 不截断（导出完整性优先，`lesson-plan.spec.ts:155-160` 断言全文存在）——**不得**为视觉加 text-overflow | 有意保留差异 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| L9 | 按钮过渡 0.15s（background/color/box-shadow） | —（教案自有） | `lesson-plan.css:38-42` | 已有 |
| L10 | 输入 focus 过渡 0.15s（border/box-shadow） | — | `lesson-plan.css:735-740,742-748` | 已有 |
| L11 | busy spinner `spin 1s linear infinite` | — | `lesson-plan.css:1396-1400`（`ExportMenu.tsx:32` 使用） | 已有 |
| L12 | reduce 全关 | `motion.css:20-25` 全局 | `lesson-plan.css:1643-1651` 局部 `animation/transition: none`（含 `!important`，属既有实现，非新增旁路） | 已有（不得扩散该写法到新增规则） |
| L13 | [未验证] 既有过渡曲线未逐帧采样；预览 paper 缩放（`PreviewPane.tsx:45,100` transform scale）无过渡属即时切换 | /chat 基准 `chat-home.css:578`（transform 200ms ease-out 供对照） | 教案预览缩放即时 | [未验证]/缺失（是否加 200ms 由队长定；加了须记矩阵） |

---

## 风险清单 1：设置页模型区可视改动风险

| # | 风险描述 | 触碰的断言/文件行号 | 倾向建议 |
|---|---|---|---|
| R1 | [与现有e2e冲突风险] 卡片 aria-label 是主定位锚：`打开 {名} 的详情`。改 aria-label/结构即全断 | `ProviderCard.tsx:32`；`model-settings.spec.ts:149,160,173,203,221,232`；`model-settings-nesting.spec.ts:70,76,91,101,111` | 保留现状 |
| R2 | [与现有e2e冲突风险] 卡片层不得出现 modelId 文本（详情层才有） | `model-settings.spec.ts:147`（`deepseek-chat` count 0）、`:151`（详情内可见） | 保留现状；视觉增量不得把模型列表提升到卡片层 |
| R3 | [与现有e2e冲突风险] `用于问答` 按钮名称锁定默认写入语义 | `ConnectionDetail.tsx`（用于问答按钮）；`model-settings.spec.ts:224-225`（defaultWrites 0→1） | 保留文案与 role |
| R4 | [与现有e2e冲突风险] 发现列表行 checkbox 名称 `{id} 已添加` 与 disabled 语义 | `ModelListPicker.tsx`（发现弹窗行）；`model-settings.spec.ts:163-167` | 保留行结构与 aria；只可做纯视觉（色/距/圆角） |
| R5 | [与现有e2e冲突风险] `Base URL` label 正则定位 + `放弃未保存的更改` alertdialog + `继续编辑` 按钮 | `ConnectionDetail.tsx` 表单区；`model-settings-nesting.spec.ts:92,96,102,106`；`ModelSettingsPanel.tsx:628-651`（discard 弹窗） | 保留名称/role/顺序 |
| R6 | [与现有e2e冲突风险] Modal 标题即 dialog aria-label（嵌套关闭断言读取它）；Escape 关最内层顺序、焦点返回触发卡片 | `apps/web/src/components/ui/Modal.tsx:33`（aria-label=title）、`:12-19`（焦点管理）；`model-settings-nesting.spec.ts:77-87,109-118` | 不改 Modal；弹层动画缺失不动（见 P-settings A3） |
| R7 | model-settings.css 既有选择器被聊天共用 | `ChatWorkspace.tsx:59`；`ModelSelector.tsx:77,108,118`；`chat-home.css:203,211,247,516`；`model-settings.css:326-342,353-372` | I1 只允许**追加** `.settings-workspace` 后代作用域规则，禁改既有选择器（任务卡 3.3） |
| R8 | 同名类全局层叠：`.settings-form/.settings-hint/.settings-toolbar/.settings-feedback` 在 settings.css 与 model-settings.css 双定义；且 **`.settings-workspace` 后代作用域会同时命中模型区内层表单**（ProfileForm/NewConnectionForm/ExtensionManager 表单都在 .settings-workspace 内） | `settings.css:96-142` vs `model-settings.css:233-306`；`ExtensionManager.tsx:109`；`ModelSettingsPanel.tsx:596`（ProfileForm）；`settings.spec.ts:17-18`（.settings-form count 0） | 新规则建议用更窄新类（如 `.extension-manager` 后代）或新前缀类，避免 `.settings-workspace .settings-form` 这种会波及模型区的写法——此点需队长在 I1 卡中显式约束 |
| R9 | 新增控件可访问名称与既有同名 → Playwright strict-mode 冲突（前批先例）；设置页已有两处「添加连接」同名按钮（页头+网格尾） | `ModelSettingsPanel.tsx:357-360,446-454`；任务卡 3.8 | 新控件一律用未占用名称；不给错误态加第二个「重试」（`settings.spec.ts:15`、`ModelSettingsPanel.tsx:302` 已各有一个） |
| R10 | 减少动画一致性：模型区有局部 reduce 块，新动画若绕过会双重机制 | `model-detail.css:441-453`；`motion.css:14-25` | 新动画只走 motion.css 全局机制，零 `!important`（任务卡 6） |

## 风险清单 2：教案不得触碰的导出与草稿链路

| # | 不可改动链路 | 文件:行号 | 说明 |
|---|---|---|---|
| D1 | `@page lesson-plan` 标准 A4 + 命名页面 | `print.css:1-4`、`:82-86` | PDF 页面命名与 A4 语义（AGENTS.md:11） |
| D2 | print 覆盖块整体：html/body 强制、UI 隐藏清单、paper-wrapper 分页（break-after/page-break-after）、`.lesson-table tr` break-inside | `print.css:5-16,23-33,42-67,77-80` | 分页行为锚点；`lesson-plan.spec.ts:40-44` 还断言打印样式不外溢到 /chat（body page=auto） |
| D3 | Word 导出映射：前两环节→第一表、其余→第二表、二次备课保留环节名；派生模板 `/templates/lesson-plan-template.docx` | `export.ts:14-33`（flattenForDocx）、`:34-52`（buildDocx fetch :39） | `verifyDocx` 逐字节校验 tblPr/tblGrid/tcPr/trHeight/sectPr（`scripts/verify-template.mjs:23-39`）；e2e `lesson-plan.spec.ts:80-104` |
| D4 | 原模板与校验值 | `assets/templates/source/teacher-standard.docx` + `manifest.json`（sha256 `f51bae6b…fa164`）；`verify-template.mjs:40-49` | 不修改、不再生成；结构相同不能替代人工排版验收（AGENTS.md:12） |
| D5 | DraftRepository / schemaVersion=1 / 本地键 `zhiqikeyuan:lesson-plan:v1` | `drafts.ts:2,42-54,55-57`；导入校验 `EditorOverlays.tsx:36-43` | 兼容性约定（AGENTS.md:6）；`lesson-plan.spec.ts:5-12` 用同键 |
| D6 | 600ms 防抖 / 串行写入 / 失败保留 pending / flush 语义（含 beforeunload/pagehide、路由离开 flush） | `autosave.ts:11-17,18-52`；`useDraftPersistence.ts:41-61,62-81,82`；`LessonPlanWorkspace.tsx:37`（beforeNavigate=flushDraft） | `lesson-plan.spec.ts:188-195` 损坏草稿不覆盖依赖 blockedRef 语义 |
| D7 | FillProvider 规则填充与警告合并 | `fill.ts:9-30`（aliases）、`:34+`（RuleBasedFillProvider）；`NlFillPanel.tsx:9,26+`（mergeProposal 确认填入） | `lesson-plan.spec.ts:53-68`（.fill-warnings 未知项/确认填入/撤销重做）；失败不得静默换示例（AGENTS.md:7） |
| D8 | 分页预算 | `services/pagination.ts`（75 行，整体禁改）；`PreviewPane.tsx:34` | 长文断言 `lesson-plan.spec.ts:123-167`（paper 高度≤1123、内容 bottom<footer-8、文本完整） |
| D9 | `--serif` 回退链（教案密集编辑区不强制 Lora） | `apps/web/src/styles/globals.css:39`（`--serif: 'SimSun','Songti SC',serif`）；`lesson-plan.css:470`（template-mini）、`:996`（paper 正文字体）；`docs/PROJECT_GUIDE.md:28` | 新样式不得给表单/表格/预览正文引入 `--font-display` 或 Lora |
| D10 | 布局断言锚点类名与三视口断言 | `lesson-plan.spec.ts:168-181`（scrollWidth）、`:170,183`（`.subject-cell` 可见、`.preview-pane`）；`.save-status`（`:28`）、`.storage-alert`（`:191`）、`.process-editor`（`:70-78`）、`.print-text/.secondary-cell/.approval-line/.paper-footer`（`:146-160`） | 组件 className 组合调整时这些类名必须原样保留在 DOM |

---

## 附录 A：样式文件归属与影响面

| 文件 | 行数 | 引用方（import） | 关键类清单 | 影响面/注意 |
|---|---|---|---|---|
| `apps/web/src/features/settings/settings.css` | 188 | 仅 `SettingsWorkspace.tsx:6` | settings-workspace / settings-index / settings-document / settings-toolbar / settings-form / settings-hint / settings-empty / settings-toggle / settings-enter(@keyframes) / extension-card | 与 model-settings.css 存在同名类层叠（settings-toolbar/settings-form/settings-hint/settings-feedback）；I1 可写，新增规则需防波及模型区（见 R8） |
| `apps/web/src/features/model-settings/styles/model-settings.css` | 475 | `ModelSettingsPanel.tsx:31` + **`ChatWorkspace.tsx:59`** | model-settings / settings-navigation / settings-eyebrow / settings-nav-note / settings-scroll / settings-page-head / settings-process-note / settings-list-toolbar / model-search / connection-group / connection-avatar / managed-model / model-default / model-facts / credential-ready / settings-feedback / settings-form / settings-field-row / settings-hint / settings-check / settings-param / settings-advanced / settings-default-card / settings-empty-state / settings-loading / model-select-trigger / model-dot / model-choice / model-choice-list / discovery-list | **聊天页共用**：chat-home.css 以 `.chat-home-shell .model-select-trigger/.model-choice` 覆盖（:203,211,247,516）；本批只追加 `.settings-workspace` 作用域增量，禁改既有选择器 |
| `apps/web/src/features/model-settings/styles/model-detail.css` | 453 | 仅 `ModelSettingsPanel.tsx:32` | provider-grid / provider-card(+in-use/add-card/focus-visible) / credential-chip / model-count-chip / connection-detail / detail-* / credential-actions / inline-confirm / button.danger / auth-* / provider-picker / provider-group / provider-option / model-picker / discovery-list(label.already) / settings-reasoning / settings-inline-models / inline-model-list / spin(@keyframes model-spin) | contract-v1 视觉载体，M-model-management 参数在此（:20-31,90-95）+ 局部 reduce（:441-453）；本批只读 |
| `apps/web/src/features/lesson-plan/styles/lesson-plan.css` | 1651 | 仅 `LessonPlanWorkspace.tsx:11` | lesson-workspace 系（`::where` 作用域）：save-status / status-dot / segmented / section-nav-item / template-card/template-mini / style-settings / local-mode / form-section / field-pair / lesson-types / type-chip / chip-checkbox / textarea-meta / editor-footer / live-dot / process-editor / paper 系 / preview-toolbar / preview-viewport / paper-stack / modal / modal-heading / pdf-options / toast / storage-alert / export-menu / mobile-tabs / spin(@keyframes) / outline-hidden / focus-mode | I2 可写（只增屏幕样式）；**无 @media print 块**（5 个屏幕 @media：1405/1428/1451/1496/1643）；不碰 D1-D10 锚点类名；字体走 `var(--serif)`（globals.css:39）不引入 Lora |
| `apps/web/src/features/lesson-plan/styles/print.css` | 86 | 仅 `LessonPlanWorkspace.tsx:12` | @page lesson-plan / html,body / .app-shell / 隐藏清单 / preview-pane / preview-viewport / paper-stack / paper-wrapper / paper / .lesson-table tr / page: lesson-plan | 本批禁改（风险清单 2 D1/D2） |
| 参照：`apps/web/src/components/ui/modal.css` | — | 共享 `Modal.tsx` | workspace-modal 系 | 设置/模型区弹窗共用；无动画；属共享组件不在 I1/I2 可写范围（弹层动效遗留事项，见范围矛盾 4） |

## 附录 B：现有 e2e 断言的用户可见行为清单（5 个 spec）

**tests/e2e/model-settings.spec.ts（262 行，9 例）**
- :145 连接名"DeepSeek 主账号"卡片可见；:147 卡片层无 modelId；:149 `打开 DeepSeek 主账号 的详情` 按钮打开
- :150-152 详情 dialog 内可见 modelId 与"用于问答"；:154 1440 无横向溢出
- :160-167 发现弹窗显示"来自上游实时接口"、"已添加"、已有模型 checkbox disabled、新模型 enabled
- :170-177 发现 500 时 role=alert 可见 + 「重试」按钮
- :203-207 Codex 认证不可用如实说明 + "没有公开的模型列表接口"手工添加说明
- :210-226 打开详情不写默认（defaultWrites=0），点「用于问答」写 1 次
- :228-237 390 视口详情可滚动、`保存修改` 按钮可见、无横向溢出
- :239-246 1920 视口网格与无溢出
- :248-261 供应商目录 503 时连接仍可见

**tests/e2e/model-settings-nesting.spec.ts（119 行，4 例）**
- :74-87 二级面板 Escape 只关最内层，详情 dialog aria-label 不变
- :89-97 经二级 Escape 返回后 `^Base URL` 草稿值保留
- :99-107 详情有改动直接关闭 → `alertdialog 放弃未保存的更改` + `继续编辑`
- :109-118 关闭详情后焦点回到触发卡片（按 aria-label 定位并断言 focused）

**tests/e2e/settings.spec.ts（21 行，1 例）**
- :11-15 后端 503 时"无法读取模型设置"+"后端服务不可用"可见 + 「重试」按钮
- :17-18 `.settings-form`、`.settings-card` count 0（不冒充可用）
- :20 无横向溢出

**tests/e2e/replica-settings.spec.ts（36 行，1 例）**
- :4-10 `/mcp` 重定向 `/settings#mcp`，项目功能导航无 MCP 按钮
- :11-19 添加 MCP 弹窗（名称/描述 label、`保存模拟配置`）、`role=switch` 启用、刷新后保持
- :20-24 `/skills` 重定向，`设置分类` 导航内 Skills 链接 `aria-current=location`
- :26-32 「外观」减少动画 check → reload 后 `html[data-motion=reduced]`
- :33-35 390 视口无横向溢出

**tests/e2e/lesson-plan.spec.ts（195 行，7 例）**
- :14-32 根路由跳 /chat；教案直达；课题编辑 → `.subject-cell` 同步 → `.save-status`=已保存到本机 → 刷新恢复；无 hydration 错误
- :33-52 路由切换立即保存；/chat 打印模拟下 `body` page=auto（教案打印样式不外溢）；品牌按钮 aria-label=返回学习问答；返回后草稿在
- :53-79 规则填充：`.fill-warnings` 含"未知项"、确认填入、撤销/重做、环节下移/增删（`.process-editor` 计数）
- :80-122 JSON 备份下载+导入还原；导出 Word 经 `verifyDocx`/`verifySource` 全过；PDF 弹窗说明 + `打开打印窗口` 触发 print + page.pdf 产出 %PDF
- :123-167 长核心素养/长教学设计/长二次备课 + 16px 字号：每页高度≤1123、内容底<footer-8、`.print-text` 全文不丢、`.secondary-cell` 全等
- :168-187 1440/1024/390 三视口 `scrollWidth<=innerWidth` + 截图；移动端预览 tab；未知路由 404
- :188-195 损坏草稿（invalid-json）→ `.storage-alert` 自动保存已暂停；编辑 800ms 后 localStorage 原样（不覆盖）

## 范围矛盾与待队长决定事项汇总

1. **[推断] 参考 Overview 的状态条/就绪面板是否做"视觉壳"**：参考 `SettingsOverview.tsx:123,154`（SettingsStatusPanel/ReadinessPanel）属信息结构差距（S7），但呈现它们需要后端状态/就绪数据接入，超出"只做视觉"边界；不做则设置页首屏信息量与参考差距明显。请队长裁定本批是否仅做静态占位或不做。
2. **[与现有e2e冲突风险] 参考 SettingsToolbar 草稿条不引入**：当前 contract-v1 直写服务端（expectedRevision，`ModelSettingsPanel.tsx:197`），无设置草稿层；引入三态工具栏属架构级新增，且与 `settings.spec.ts:17-18` 的"错误态无表单"断言环境冲突。倾向：不做，列保留现状。
3. **`.settings-workspace` 后代作用域的穿透问题（R8）**：任务卡 3.3/3.6 的作用域方案会同时命中模型区内层表单（同页同容器）。建议 I1 卡追加约束：新增规则用 `.extension-manager`/新前缀类收窄，或对同名类（settings-form 等）一律不写新规则。需队长确认后写入 I1 卡版本号。
4. **弹层动画归属**：参考有完整弹层进出场（dt-pop-in 200ms / dt-overlay-in 160ms，`globals.css:663-687`），当前共享 `Modal.tsx`/`modal.css` 无动画且属共享组件，不在 I1/I2 可写清单。若本批要补，需队长另开共享层小卡；否则记为遗留差距。
5. **M-settings-nav 参数差异记录**：矩阵记 160ms，参考实际 Tailwind transition-colors 默认 150ms（`SettingsNav.tsx:395,460`）。当前实现 160ms（`settings.css:27`）。按任务卡 6"不得改既有参数"处理：保持 160ms，此差异仅记录，不改矩阵。
6. **教案视觉统一上限**：`lesson-plan.css` 既有大量硬编码色值（如 `:731` #424a57、`:1300` #e2e6ef、`:1306` #16233c45），"只增不改"意味着无法替换为 globals 变量，与 /chat 基准的色彩统一存在天然上限。倾向：接受现状，仅新增元素消费变量（任务卡 3.5）。
7. **教案预览缩放是否加 200ms 过渡（L13）**：/chat 基准有 transform 200ms ease-out 先例（`chat-home.css:578`），教案为即时切换；加过渡影响连续拖动字号滑杆的体验，[未验证] 未实测帧率。倾向：本批不做，记遗留。

（E4 完；本文件为唯一产物，未改动其他任何文件。）
