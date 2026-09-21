# B-R05-EXTEND v3 证据（2026-09-19）

任务卡：[TASK-CARD.md](TASK-CARD.md)（含 §7 队长裁定）。起点 SHA `1aad54b`，实现候选 `fc005d0`（分支 `codex/replica-review-20260908`）。
范围：R-05 视觉规范推广第三批——`/co-writer`、`/co-writer/[docId]`、`/reading`、`/reading/materials` 四个页面条目。**阅读工作区三栏（`/reading/[workspaceId]` 及 sessions 子页）不在本批。**

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `TASK-CARD.md` | 任务卡：范围、**禁区声明**（`reading.css` 与 `ReadingWorkspace.tsx`）、独占文件表、资源分配、**§7 队长裁定**（§7.1 做 / §7.2 不做 / §7.3 动画口径修正 / §7.4 样式边界） |
| `E3-GAP-LIST.md` | E3 只读取证：四页逐页差距 64 条（双证据行号）；含窄视口风险清单（材料库行头标为最高风险）、10 条 e2e 冲突风险汇总、**模拟标注保护清单 9 条**、附录 A 样式归属（含 `reading.css` 逐类消费方与 `reading-msg` 跨模块借用登记）、附录 B 断言行号清单 |
| `before/` `after/` | 四页三视口（1440×900 / 1920×1080 / 390×844）全页截图 + 每视口 Tab 焦点图，各 24 张；另含编辑器版本历史弹窗截图 |
| `A1-REPORT.md` | 独立验收报告（结论 **pass 0 fail（31 项）**，含 2 条低风险备注） |
| `A1-shots/` | A1 自测证据 36 个文件（截图 + 量测 JSON） |
| `shoot.mjs` | 队长前后对照截图脚本（前置 5174 生产预览；含 390 溢出量测输出） |

种子数据（隔离上下文）：写作走页面「新建文稿」按钮（含模板），阅读点「载入演示数据」；材料库另构造「解析失败 + 未分配」样本用于窄视口与筛选验证。

## 实施内容（I1 写作 / I2 阅读库）

- **共享边界**：`globals.css`/`space.css`/`motion.css` 只读；**`reading.css` 与 `ReadingWorkspace.tsx` 零改动**（后者是 R-09 已验收交互的载体）；新建 `writing/styles/writing.css`（`.writing-*`）与 `reading/styles/reading-library.css`（`.reading-lib-*`），只消费既有变量层、零 `!important`、注释无提前闭合序列；节点加 `writing-page`/`reading-lib-page` 修饰类。
- **窄视口修复（E3 最高风险）**：材料库行头在「解析失败 + 未分配」态会同时渲染 5 个 chip + 4 个操作按钮，而 `space-session-top` 无 wrap → 本页作用域内允许 wrap 并让 chip/操作组可收缩；390 实测超界元素 0、操作按钮右缘 ≤369。
- **写作列表**：卡片 150ms hover 过渡与焦点环、空态图标块 + 主行动按钮、按钮 opacity/scale 动效；**空态按钮与页头按钮命名区分**（见下「集成期修复」）。
- **写作编辑器**：正文区样式迁出内联 style（含 focus 环）、保存三态 chip 色彩化（`已保存`/`保存中…`/`保存失败，将重试` 文案逐字保留）、标题行与版本行整理、AI 面板/预览按钮动效。
- **阅读集合库**：卡片 hover 抬升与焦点环、材料/会话计数 chip 图标化、空态图标 + 主行动。
- **材料库**：筛选 2→4 tab（补「解析中」「解析失败」，计数来自真实数据）、状态色点（ready/failed/busy 复用 `space-pulse`）、操作按钮图标与过渡、空态增强。
- **动画口径**：E3 核出四页源码**未引用** `dt-pop-in`（实际为 tailwindcss-animate 类与 `dt-popup-up`，仅编辑器内部），故本批**不新增进出场动画**，只做参考有明确参数的 hover/focus/active 150ms 过渡。
- **模拟标注红线**：保护清单 9 条逐字保留（含 `SIMULATED_KINDS` 五类、行内「PDF · 模拟解析」、材料页两处说明与「文件名（模拟导入，不读取真实文件）」、阅读演示与说明文案），A1 逐条复核命中。

## 检查记录

| 检查 | 结果 |
| --- | --- |
| typecheck | pass |
| lint（`--max-warnings=0`） | pass（0 警告） |
| unit（Node26 + `--no-experimental-webstorage`） | 43 文件 297/297（与基线一致） |
| build | **首次失败**（退出码 `0xC0000409` STATUS_STACK_BUFFER_OVERRUN、无编译错误输出）→ **复跑两次均成功**；判为 Turbopack/Node 间歇性崩溃，非代码问题 |
| e2e（隔离 5174 自动拉起） | 154/154（首轮 152/154 见下） |
| api | 未重跑（本批零后端改动；基线 181） |
| **独立验收 A1** | **pass 0 fail（31 项）**：三视口 0 溢出、窄视口材料行头实测、键盘焦点与全部断言前提、reduce 压制、写作/阅读全交互、模拟标注 9 条逐字、**R-09 工作区不回退**（滚动跟随/回到最新/双抽屉） |
| 390 视口 | 四页 before/after 溢出扫描均 0 |

## 集成期真实失败与修复（归属记录）

**空态按钮与页头按钮同名 → Playwright strict-mode 冲突**：
- 现象：`npx playwright test tests/e2e/writing.spec.ts` → **2 failed**（`写作.spec.ts:10`、`:52`），`getByRole('button', {name:'新建文稿'})` 解析到 2 个元素。
- 根因：I1/I2 按 §7.1 #5 新增的空态主行动按钮，可访问名称与页头按钮**完全相同**（写作「新建文稿」、阅读「新建阅读集合」/「新建材料」）。
- 修复：写作空态按钮可见文案改「新建第一篇文稿」；阅读两页空态按钮加区分性 `aria-label`（可见文字不变）。
- 复验：全量 e2e 恢复 **154/154**；A1 在空态下实测三页各只解析到 1 个元素。
- **教训（已记入 STATUS）**：新增按钮/控件时，可访问名称不得与既有同名控件重复（尤其空态与页头并存场景）；此前各批的先例是 `role="alert"` 重复。

## 边界与未验

- 本批只关闭 R-05 中这四个页面切片，**不关闭 R-05 全站**；设置/教案/`/space` 其余子页仍待后续批；**阅读工作区三栏需单独任务卡**（有 R-09/READ-RETRY/READ-END 已验收交互）。
- 按 §7.2 裁定**保留现状**：新建改直建、两击删除替换原生 confirm、版本系统（当前为超出参考的本地增强）、LibraryShell 双 tab 化与行式列表、网格化、搜索框、上传对话框、DOCX 导入、真实解析/转录、真实 AI 通道、字数口径改 words、`reading-msg` 跨模块借用解耦、`?focus=mat-` 消费逻辑。
- 10 处「参考结构改动会触碰既有 e2e 断言」的事项全部选择保留现状，**零断言改动**。
- 动画未逐帧采样曲线/中断（MOTION_MATRIX 条目保持「实现待验收」）；A1 备注：reduce 下 hover 位移终态仍达成（transition 被压至 1e-05s、无动画过程），与 v2 批口径一致，如需「reduce 完全去位移」涉及三模块统一，建议后续单独裁定。
- A1 未执行项：e2e/typecheck/lint/unit/build 未重复执行（归队长，已全量跑过）。
