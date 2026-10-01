# B-R05-EXTEND v5 任务卡（队长定稿）

定稿时间：2026-09-19 ｜ 队长：外部 Agent（实施总控）｜ 起点 SHA：`7b2ba5e`（分支 `codex/replica-review-20260908`）
参考：`F:\DeepTutor` 固定 `42fab3cf429a1fbf36b257ab8d116a3814964202`（只读，不升级）

## 1. 批次范围（用户已锁定，不得扩大）

**R-05 收尾批**，两组页面：

| 组 | 页面条目 | 路由 | 组件 |
| --- | --- | --- | --- |
| A（最高风险） | `P-reading-[workspaceId]`、`P-reading-sessions`、`P-reading-sessions-[sessionId]` | `/reading/[workspaceId]`（含 sessions 子页） | `features/reading/ReadingWorkspace.tsx`（1696 行） |
| B | `P-space-chat-history`、`P-space-questions`、`P-space-personas`、`P-space-cli-apps` | `/space/*` 四子页 | `features/space/*Section.tsx`（313/556/276/214 行） |

**不在本批**：`P-whisper`（`WhisperRoom`，借用阅读 CSS 但不属本批页面）、`P-co-writer` 系列（已交付）、`P-books-pages-[pageId]`、其他模块、`/space` 的 mcp/skills 重定向页。

**只做视觉与既有状态呈现推广，不补新业务。**

## 2. 两条铁律

### 2.1 阅读工作区（组 A）：视觉层可改，交互逻辑区不动

**绝对不得改变语义的代码位置**（E5 需给出完整清单，实现者需逐条自我核对）：

| 机制 | 位置 | 不得改变 |
| --- | --- | --- |
| R-09 follow-bottom 状态机 | `ReadingWorkspace.tsx:1206-1212`（effect）、`:1460-1467`（onScroll `dist < 90`）、`:1502-1510`（回到最新） | 状态切换条件、滚动目标容器、`< 90` 阈值语义 |
| R-09 会话切换恢复跟随 | `:1201-1204`（`useEffect(() => setFollowBottom(true), [activeId])`） | 依赖项与行为 |
| R-09 会话 URL 历史 | `syncSessionUrl`（`push`/`replace`）、`popstate` 监听 | push/replace 选择、地址一致时不写历史、仅"用户动作"与 popstate 改地址 |
| turnId/sessionId 守卫 | 事件处理与 `turns[sessionId]` 归属 | 迟到/跨会话事件不污染新会话 |
| finalizeTurn 幂等（READ-END） | `finalizedTurnsRef` 按 turnId | 重复/迟到 end 不重复落库、不复活取消标注 |
| retry 放行（READ-RETRY） | `:1504` 附近「重试伴生回复」 | 错误态可重试、流式防重入保留 |
| abort 归属 | `abortsRef` 与会话绑定 | 切会话/卸载时旧轮中止不回填新会话 |
| 草稿归属 | `draftOwnerRef`、`saveSessionDraft` | 按会话归属，不串用 |
| 阅读位置 | `handleScroll`（`:843-855`）+ 300ms 防抖 | 存储键与节流语义 |

**允许**：`ReadingWorkspace.tsx` 的 className 组合调整与新样式类挂载、`reading.css` 的**纯视觉增量**（但见 §3 第 3 条的多方共用约束）。
**storage 键 `zhiqikeyuan:reading-*` 与 `reading-store` 服务语义不变。**

### 2.2 /space 子页（组 B）：既有交互与断言零改动

- 真实计数、筛选（范围栏/防抖搜索）、排序、批量操作、演示载入幂等、来源回链（R-10 真实 sessionId 语义）全部保留。
- 既有 `space-*` 类名与断言文案零改动（E5 附录 B 给锚点行号；`tests/e2e/space-pages.spec.ts` 8 例）。
- **MCP/Skills 唯一管理仍在设置**（`/space/mcp`、`/space/skills` 是重定向页）；子页不得复制管理实现。
- CLI 应用「演示安装」等模拟标注不得删改。

## 3. 共享层定稿（队长自留，实现者只引用）

1. **`apps/web/src/styles/globals.css`、`motion.css`：本批只读。**
2. **`apps/web/src/features/space/styles/space.css`（748 行，被 13+ 模块 import）：本批只读。** 组 B 的视觉增量一律进**新建** `features/space/styles/space-sections.css`（`.space-*` 页面前缀后代作用域），不改 space.css 既有规则。
3. **`features/reading/reading.css`（160 行）：本批由 I1 独占（可写）但受限**——E1 已核出该类文件被 `ReadingWorkspace.tsx`、**`WhisperRoom.tsx`**、**`WritingEditor.tsx`** 三方共用：
   - `.reading-companion`、`.reading-msg`、`.reading-composer` → 阅读工作区 + WhisperRoom（`.reading-msg` 还被 WritingEditor 借用）
   - 其余（`.reading-layout/.reading-pane/.reading-mark/.reading-drawer*/.reading-selection-bar/.reading-quote-block/.reading-companion-drag`）→ 仅阅读工作区
   - **要求**：I1 的每一条 `reading.css` 增改必须逐条列出，并证明**只影响阅读工作区**（例如用 `.reading-ws-page` 后代作用域收窄，或只改仅阅读使用的类）。**不得**裸改 `.reading-companion/.reading-msg/.reading-composer` 的既有规则（会波及 Whisper 与写作页）。若判断无法安全收窄，则改为新增独立 CSS。
4. 新增 CSS 一律：只消费既有变量、零 `!important`、**注释内不得出现 `*/` 序列**（`--radius-*/` 会提前闭合注释致 Turbopack 构建失败，前批已踩两次）。
5. 页面根节点加**修饰类**用于收窄覆盖：阅读工作区 `space-page reading-ws-page`；space 子页在各自根节点加 `space-sections-page`（或各自页面前缀）。
6. **新增控件可访问名称不得与既有控件同名**（前批先例：空态按钮 vs 页头按钮、重复 `role="alert"` 触发 Playwright strict-mode）。

## 4. 分卡与独占文件表

| 卡 | 负责人角色 | 独占可写文件 | 禁止修改 |
| --- | --- | --- | --- |
| B-R05-EXT5-E5 | Evidence-Collector（只读） | `docs/qa/B-R05-EXT5/E5-GAP-LIST.md` | 其余全部 |
| B-R05-EXT5-I1 | Limit-scope-implementer（阅读工作区视觉） | `features/reading/ReadingWorkspace.tsx`（仅 className/修饰类）、`features/reading/reading.css`（受 §3.3 约束）、**新建**（如需）`features/reading/styles/reading-ws.css` | 交互逻辑区（§2.1 表）、`reading-store`/`reading-ingest`、`space.css`、`globals.css`、`motion.css`、`WhisperRoom.tsx`、`WritingEditor.tsx`、`space/**`、`tests/**`、矩阵/STATUS |
| B-R05-EXT5-I2 | Limit-scope-implementer（/space 子页） | `features/space/ChatHistorySection.tsx`、`QuestionBankSection.tsx`、`PersonasSection.tsx`、`CliAppsSection.tsx`、**新建** `features/space/styles/space-sections.css` | `space.css`（只读）、`SpaceDashboard.tsx`/`SpaceMain.tsx`（已交付 v1，不在本批）、`reading/**`、`globals.css`、`motion.css`、`tests/**`、矩阵/STATUS |
| B-R05-EXT5-I3 | Limit-scope-implementer（R-09 flaky 诊断/修复，**与 I1 串行**） | `features/reading/ReadingWorkspace.tsx`（仅 follow-bottom 相关最小改动）、`tests/e2e/reading.spec.ts`（**仅在诊断确证 flaky 且修复需要时，允许调整该用例的滚动触发方式，但断言阈值与语义不得放宽**） | 其它一切 |
| B-R05-EXT5-A1 | Independent-Acceptor（只读） | `docs/qa/B-R05-EXT5/A1-REPORT.md`、`docs/qa/B-R05-EXT5/A1-shots/` | 全部产品与测试文件 |
| 权威文档/矩阵/Git/R-05 关闭评估 | 队长 | `docs/STATUS.md`、`docs/replica/*`、`docs/PROJECT_GUIDE.md`、Git | — |

**I1 与 I3 操作同一文件（`ReadingWorkspace.tsx`）→ 必须串行**：先 I1 完成并交 ready_for_review，再由 I3 在其基础上工作。**I2 可与 I1 并行**（文件不重叠）。

## 5. 资源分配

| 资源 | 归属 | 说明 |
| --- | --- | --- |
| 前端端口 5174 | 队长（A1 期间独占） | 生产预览 `node scripts/run-web.mjs start 5174` |
| 实现者自测端口 | 5175（I1/I3）、5176（I2） | 避免互相冲突；用后必须停 |
| 构建目录 `apps/web/.next` | 队长 | **候选冻结后由队长重建并记录构建时间/BUILD_ID；A1 基于该构建验收**（不得仅凭 BUILD_ID 在位推断） |
| e2e | 队长（A1 可复核） | 先停队长手动 5174 |
| 证据目录 | `docs/qa/B-R05-EXT5/` | `before/`、`after/`、`shoot.mjs`、`TASK-CARD.md`、`E5-GAP-LIST.md`、`A1-REPORT.md`、`README.md` |
| 用户端口 5173/8000、正式 `.env`/`.local-data`、真实草稿 | 禁碰 | 全程不读写 |

## 6. 行为闭环与验收条件

- **阅读工作区**：三栏（导航/正文/伴生）视觉统一、工具栏与页签视觉、批注与选区浮条视觉、抽屉与拖拽轨视觉、移动端面板视觉；**交互行为零变化**。
- **/space 子页**：四页视觉统一（卡片/列表/筛选栏/工具条/弹窗视觉），真实计数与筛选/批量/演示载入保留。
- **交互状态**：加载/空/错误/hover/focus/禁用/长文案截断不得回退；键盘可达与焦点环保持。
- **窄视口（重点）**：390×844 历史高发区。阅读工作区已有 R-09 移动端抽屉用例（`reading.spec.ts:547`）与 R31/R32 布局断言；`getBoundingClientRect` 实测，不能只看截图。
- **动画（R1）**：先核参考来源再决定；`M-reading-layout`（部分实现）已有条目，实装须与其参数一致。新条目记入 MOTION_MATRIX，最高「实现待验收」。
- **减少动画**：复用 `motion.css` 全局机制，不新增旁路，不用 `!important` 绕过。
- **模拟标注**：阅读伴生「模拟回复」、CLI「模拟安装/演示」等文案逐字保留。

## 7. 必须运行的检查

- I 卡：`npx eslint <改动目录> --max-warnings=0`；`NODE_OPTIONS=--no-experimental-webstorage npx vitest run <相关测试>`；`npx tsc --noEmit -p apps/web`；窄视口实测值。
- **I3 额外**：R-09 五例全过 + `--repeat-each=10` 无失败 + 全量 e2e 154。
- 队长：typecheck / lint / unit 全量 / build / e2e 全量 + 三视口前后截图 + **R-05 关闭评估**。
- A1：三视口 + 焦点 + reduce + 正常/空/长文案/错误态；**阅读工作区独立复核 R-09 五例行为不回退与 R-10 来源回链**；**/space 子页复核既有交互**。

## 8. 队长裁定（E5 完成后回填，2026-09-19）

E5 交付 44 条差距（组 A 12 / 组 B 32）、**清单 1 交互保护区 19 条机制 + 锚点三档分级**、**清单 2 reading.css 14 类影响面（4 类被 Whisper/Writing 隐式共用）**、8 项待决。**总原则：阅读工作区与 /space 子页的既有交互语义、断言锚点、storage 键一律不动。**

### 8.1 必做（I 卡）

| # | 项 | 依据 |
| --- | --- | --- |
| 1 | **按钮反馈过渡**：阅读工作区按钮补 `transition-[background-color,color,transform] 150ms` + `active:scale(0.9~0.97)`（参考 `ReadingCompanion.tsx:331,351,370,383`） | E5 组 A #3；来源明确 |
| 2 | **材料 tab 长标题截断**（窄视口最高风险 N1）：tab 标题补 `max-w-[168px]` 语义 + `truncate`（参考 `ReadingWorkspace.tsx:395-397`） | E5 N1 |
| 3 | **tab busy 指示**：材料解析中 tab 补旋转图标（参考 `:390-394`） | E5 组 A #5 |
| 4 | **错误横幅可关闭**：伴生 turn error / session error 补 dismiss（新增按钮用**未占用名称**，如「关闭伴生错误提示」） | E5 组 A #2；参考 `ReaderPane.tsx:849-866` |
| 5 | **伴生栏头部信息结构增强**（形态层）：会话选择区与操作区排版、chip 化（**不新增重命名/删除会话等新业务能力**——见 §8.2 #1） | E5 组 A #1 的形态部分 |
| 6 | **space 子页卡片/列表/工具条视觉统一**：四页 hover/focus 过渡、卡片边框与阴影、工具条间距、筛选控件视觉 | E5 组 B 摘要 |
| 7 | **题库 busy/refreshing 视觉**：列表 refreshing 时 `transition-opacity + opacity-60`（参考 `question-bank/QuestionBankSection.tsx:223-227`） | E5 组 B #5 |
| 8 | **会话历史/题库头部计数 chip 与刷新按钮视觉**（形态层：`N 个会话` chip + 刷新按钮的视觉与 disabled/spinner 态；**刷新行为接既有 refresh 函数，不新增数据源**） | E5 组 B #4 |
| 9 | **CLI 应用卡片视觉统一 + 状态徽标**（**不做搜索/详情/分页**，见 §8.2 #4） | E5 组 B 摘要 |

### 8.2 不做（保留现状，记入矩阵/STATUS 边界）

| 项 | 裁定 | 理由 |
| --- | --- | --- |
| 参考伴生栏的完整聊天复用（会话重命名/删除、保存笔记本、下载 Markdown、溢出菜单） | **不做** | E5 待决 #1：等价于接入真实聊天服务/统一 ChatService，超出「只做视觉不补业务」；当前为已验收的本地模拟实现，**深层行为差异明确登记为「有意保留差异」** |
| 滚动跟随语义对齐参考（90px 双向 → 80px 只 arm 不 release） | **不做** | E5 待决 #2：当前语义被 R-09 `spec:425-460` 锁定且已验收；对齐必须改 spec（本批铁律：断言零改动） |
| 会话 URL 历史降级为参考式（去掉 push/popstate） | **不做** | E5 待决 #3：当前实现**超出参考**且被 `spec:462-492` 锁定，属目标自有增强，不按参考降级 |
| 角色卡改「卡片整体可点 + hover 显隐操作钮」 | **不做** | E5 待决 #4：`space-pages.spec.ts:272-284` 依赖常驻按钮可点；hover 显隐会降低可达性 |
| CLI 目录搜索 / 详情页 / Load more 分页 | **不做** | E5 待决 #5：依赖远程 catalog API，属新业务能力；登记为后续批 |
| persona `read_only` 保护规则 | **不做** | E5 待决 #6：需先定义本地等价规则，超出本批 |
| 阅读选区浮条改参考式底部条 | **不做** | E5 冲突表：`reading.spec.ts:71-97` 依赖 `role=menu`「选区操作」结构 |
| `dt-reader-flash` 跳转脉冲 | **不做**（登记为可选后续） | E5 待决 #7：服务的 `reader_goto` 引用链路属真实模型通道；纯前端导航 flash 可作为 v6 可选子项 |
| `space.css` 断点调整（760→多档） | **不做** | E5 待决 #8：改全局断点影响全部 space 系页面（含已交付 v1 与其他模块），超出本批权限 |
| `reading.css` 中 4 个共用类的既有规则改动 | **不做**（必须后代作用域收窄或新增独立 CSS） | E5 清单 2：`.reading-companion/.reading-msg/.reading-composer` 被 `WhisperRoom.tsx` 与 `WritingEditor.tsx` 隐式共用 |

### 8.3 关键实施约束（E5 清单落地）

1. **交互保护区 19 条机制零语义改动**（清单 1）：follow-bottom 状态机（`:1206-1212`/`:1460-1467`/`:1502-1510`）、会话切换恢复跟随（`:1201-1204`）、`syncSessionUrl` 与 popstate、turnId/sessionId 守卫、`finalizedTurnsRef` 幂等、READ-RETRY 放行、`abortsRef` 归属、`draftOwnerRef` 草稿归属、`handleScroll` 300ms 节流、R31/R32 拖拽轨与抽屉键盘可达。
2. **锚点三档分级照 E5 执行**：不可动 18 项（含 `.reading-layout`、`.reading-companion-body`、`role="separator"`「调整伴生栏宽度」、`aria-label` 系列、按钮名「收起导航/展开导航/材料库…/添加材料/移除材料 X」）一律不动；纯视觉可动；结构敏感项需在结果卡逐条说明。
3. **阅读 CSS 落点**：优先**新建** `features/reading/styles/reading-ws.css`（`.reading-ws-page` 后代作用域）；若确实需改 `reading.css`，每条增改必须证明只影响阅读工作区（用 `.reading-ws-page` 收窄），且**不得**裸改 4 个共用类的既有规则。
4. **space 子页 CSS 落点**：一律进**新建** `features/space/styles/space-sections.css`（`.space-sections-page` 后代作用域）；`space.css` 本批只读。
5. **模拟标注逐字保留**：阅读伴生「模拟回复」「伴生助手为本地模拟（未接入模型）」等、CLI「模拟安装/演示」等。
6. **新增控件命名唯一**（strict-mode 先例）；**同一路径不得出现第二个 `role="alert"`**。

### 8.4 I3（R-09-FLAKY）裁定前置

- I3 在 **I1 完成后**基于其产物进行（同文件串行）。
- **允许**：受控诊断（`--repeat-each` 压测、必要时注入时序）+ 最小修复 + 必要时调整该用例的**滚动触发方式**（断言阈值与语义不得放宽）。
- **必须**：R-09 五例全过 + `--repeat-each=10` 无失败 + 全量 e2e 154。
- **若诊断不能确证或修复风险不可控 → 只交诊断报告 + 观察建议，不强行修**；不得为关闭台账而改断言语义。
- 最终修复方案由队长裁定后才纳入候选。
