# B-R05-EXTEND v1 任务卡（队长定稿）

定稿时间：2026-09-18 ｜ 队长：外部 Agent（实施总控）｜ 起点 SHA：`3f968b0`（分支 `codex/replica-review-20260908`）
参考：`F:\DeepTutor` 固定 `42fab3cf429a1fbf36b257ab8d116a3814964202`（只读，不升级）

## 1. 批次范围（用户已锁死，不得扩大）

对**有限一组既有页面**做 R-05 视觉规范推广（信息结构 + 交互状态 + 参考有来源的动画），视觉沿用 B-R05-SPACE-VISUAL v1 的变量层：

| 页面条目 | 路由 | 组件 |
| --- | --- | --- |
| P-knowledge-bases | `/knowledge-bases` | `KnowledgeBasesSection.tsx` |
| P-knowledge-bases-[kbName] | `/knowledge-bases/[kbName]` | `KnowledgeBaseDetailSection.tsx` |
| P-notebooks | `/notebooks` | `NotebooksSection.tsx` |
| P-notebooks-[notebookId] | `/notebooks/[notebookId]` | `NotebooksSection.tsx`（深链分支） |

队长的更小组决策依据：这四页共用 `space.css` 一套设计语言、同属 S5-B，改动面收敛在 2 个模块目录内；`/space` 其余子页（chat-history/questions/personas/cli-apps）与书籍/课程/阅读/写作/设置均**不在本批**。不宣称 R-05 全站统一。

## 2. 共享层定稿（队长自留，实现者只引用）

1. **`apps/web/src/styles/globals.css`：本批不改。** 变量层 `--font-ui/--font-display/--radius-sm|md|lg|pill/--shadow-card|pop/--space-1…6` 已由 B-R05-SPACE-VISUAL v1 建立，本批直接引用；若实现中发现确需新增变量，交队长评估，不自行添加。
2. **`apps/web/src/features/space/styles/space.css`：本批不改。** 该文件被 13 个模块 import（books/courses/reading/writing/whisper/space/knowledge/notebooks），修改会外溢到本批范围之外的页面；本批只**新增模块级样式文件**，全部消费同一变量层，符合既有 `features/*/styles/*.css` 结构，不构成第二套设计系统。
3. 新增（本批创建，单一写入者见表）：
   - `apps/web/src/features/knowledge/styles/knowledge.css`（类前缀 `.kb-*`）
   - `apps/web/src/features/notebooks/styles/notebooks.css`（类前缀 `.nb-*`）
   两文件顶部注明「消费 globals.css 单一变量层（R-05）」，不重复定义色板/字体常量。
4. **禁止**：重命名或删除 `space-*` 类名（e2e 与其它模块依赖）；修改 `tests/e2e/knowledge-notebooks.spec.ts` 既有断言；新增动画库；改 `tests/` 下测试替身以外的生产路径。
5. 页面根节点可加**修饰类**（如 `space-page kb-page`）用于收窄覆盖；`.space-page` 既有几何不变。

## 3. 分卡与独占文件表

| 卡 | 负责人角色 | 独占可写文件 | 禁止修改 |
| --- | --- | --- | --- |
| B-R05-EXTEND-E1 | Evidence-Collector（只读） | `docs/qa/B-R05-EXTEND/E1-GAP-LIST.md` | 其余全部 |
| B-R05-EXTEND-I1 | Limit-scope-implementer（知识库） | `features/knowledge/KnowledgeBasesSection.tsx`、`features/knowledge/KnowledgeBaseDetailSection.tsx`、**新建** `features/knowledge/styles/knowledge.css` | `space.css`、`globals.css`、`notebooks/*`、`services/*`、`tests/*`、矩阵/STATUS |
| B-R05-EXTEND-I2 | Limit-scope-implementer（笔记本） | `features/notebooks/NotebooksSection.tsx`、**新建** `features/notebooks/styles/notebooks.css` | `space.css`、`globals.css`、`knowledge/*`、`services/*`、`tests/*`、矩阵/STATUS |
| B-R05-EXTEND-A1 | Independent-Acceptor（只读） | `docs/qa/B-R05-EXTEND/A1-REPORT.md` | 全部产品与测试文件 |
| 权威文档/矩阵/Git | 队长 | `docs/STATUS.md`、`docs/replica/*`、`docs/PROJECT_GUIDE.md`、Git | — |

I1 与 I2 文件集互不相交，可并行；两者都不启动服务器、不跑 build（构建与端口归队长）。

## 4. 资源分配

| 资源 | 归属 | 说明 |
| --- | --- | --- |
| 前端端口 5174 | 队长（A1 期间借给验收者） | 生产预览 `node scripts/run-web.mjs start 5174`；同一时刻只有一个进程 |
| 构建目录 `apps/web/.next` | 队长 | 实现者不得跑 `npm run build` / `next build`；如需类型检查用 `npx tsc --noEmit` |
| e2e | 队长（A1 可复核） | `npm run test:e2e` 会自行拉起/回收 5174，运行前必须先停队长的手动服务器 |
| 证据目录 | `docs/qa/B-R05-EXTEND/` | `before/`、`after/`、`shoot.mjs`、`E1-GAP-LIST.md`、`A1-REPORT.md`、`README.md` |
| 用户端口 5173/8000、正式 `.env`/`.local-data` | 禁碰 | 全程不读写 |

## 5. 行为闭环与验收条件

- **信息结构**：按 E1 清单补齐参考可见区块（页签指示器/计数徽标、卡片悬停箭头、空态图标+主行动、状态点等），保留全部既有数据、跳转、真实计数、演示标识与模拟标注。
- **交互状态**：加载/空/错误/搜索/切换/hover/focus/禁用/长文案截断不得回退；键盘可达性与焦点环保持。
- **动画（R1）**：仅实装参考有明确来源的参数（时长/缓动/触发），逐条记入 MOTION_MATRIX 新 `M-kb-*`/`M-nb-*` 条目，状态最高「实现待验收」。
- **减少动画**：系统与本地 reduced 均生效（复用 `motion.css` 全局机制，不新增旁路）。
- **数据兼容**：`zqky.replica.knowledge.v1`、`zhiqikeyuan:notebooks`、`zhiqikeyuan:notebook-entries` 读写语义与 R-10 来源回链不变。
- **必须运行**：I 卡 → `npx eslint <改动文件>` + `NODE_OPTIONS=--no-experimental-webstorage npx vitest run <相关测试>`；队长 → typecheck/lint/unit/build/e2e 全量 + 三视口前后截图；A1 → 独立浏览器三视口+焦点+reduce+正常/空/长/错误态。

## 6. 超出范围时

任何需要改共享文件、服务接口、测试断言或扩大页面的需求，停止并交队长重新分配；不得自行扩大或改断言掩盖失败。

## 7. 队长裁定（E1 完成后回填，2026-09-18）

E1 提出 3 处 [与现有e2e冲突风险] 与 2 项范围待决，队长裁定如下（**不改任何既有断言**）：

| 事项 | 裁定 | 理由 |
| --- | --- | --- |
| 页签加计数徽标（E1 冲突1） | 允许，但 accessible name 必须仍含「知识库」「检索引擎」字样 | `spec.ts:219` 用 `getByRole('tab', {name:/检索引擎/})` 子串匹配；徽标可 `aria-hidden` 或作空格分隔文本 |
| 新建笔记本入口迁到左栏头部 Plus（E1 冲突2） | **不实现，保留 rail 内「新建笔记本」项** | `spec.ts:494` 按 `.space-scope-item` + 「新建笔记本」定位；迁移属结构性变更、收益低 |
| 记录操作合并 MoreHorizontal 菜单（E1 冲突3） | **不实现，保留三个 icon-button 与既有 aria-label** | `spec.ts:450/462/482/523` 直接依赖「编辑记录 X」「移动或复制记录 X」「删除记录 X」；本批只补参考的 hover/active 过渡参数 |
| Markdown 渲染 / 文件树预览 | 不纳入本批 | 内容渲染器与新依赖超出视觉推广范围，登记为后续 |
| 行内连续文档编辑器 / dirty 丢弃确认 | 不纳入本批；Modal 形态保留，仅补 Esc 关闭（若 Modal 未提供） | 与既有 e2e 的 dialog 定位一致，改形态风险高 |
| 标题字号 19px / 24px 差异 | 保留当前 `--font-display` 24px | 与已交付 `/space` 首页一致；参考自身排版不作为全站基准 |
| toast 系统 | 不纳入本批，沿用页内 banner（role=status） | 参考 notify 系统非本批页面专属能力 |

**共享样式边界（附录 A 定稿）**：`space.css` 与 `globals.css` 本批**只读**。所有参考式新结构以「页面修饰类 + 后代选择器」落在新增模块样式文件内：
- 列表/详情根节点加修饰类：知识库 `space-page kb-page`、笔记本 `space-page nb-page`（可再加 `nb-detail` 区分深链）。
- 新样式文件内选择器一律以 `.kb-page` / `.nb-page` 起头，例如 `.kb-page .space-tabs button { … }`、`.nb-page .space-scope-item.current::before { … }`。
- 这样影响面严格限于这四页，不波及其它 11 个 import `space.css` 的模块。
- 既有类名一律不改名、不删（e2e 与其它模块依赖）；`aria-label`、`role`、可见文案中 e2e 已断言的部分不动。
