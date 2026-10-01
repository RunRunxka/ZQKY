# B-R05-EXTEND v2 证据（2026-09-18）

任务卡：[TASK-CARD.md](TASK-CARD.md)（含 §7 队长裁定）。起点 SHA `de3f8b7`，实现候选 `1ca673c`（分支 `codex/replica-review-20260908`）。
范围：R-05 视觉规范推广第二批——`/books`、`/books/[bookId]`、`/courses`、`/courses/[courseId]` 四个页面条目。**只做视觉与既有状态呈现，不补新业务。**

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `TASK-CARD.md` | 任务卡：范围、共享层边界、独占文件表、资源分配、**§7 队长裁定**（§7.1 做 / §7.2 不做 / §7.3 口径 / §7.4 样式边界） |
| `E2-GAP-LIST.md` | E2 只读取证：四页逐页差距 97 条（信息结构/交互/动画三类，双证据行号）；含窄视口风险清单、13 条 e2e 冲突风险汇总、附录 A 样式归属、附录 B 断言行号清单、8 条待决 |
| `before/` `after/` | 四页三视口（1440×900 / 1920×1080 / 390×844）全页截图 + 每视口 Tab 焦点图，各 24 张 |
| `A1-REPORT.md` | 独立验收报告（结论 **pass 0 fail**，含逐项表、疑似 fail 排除说明、未执行项） |
| `A1-shots/` | A1 自测截图 37 张、JSON 审计数据 10 个、`probe/` 下 15 个可复跑脚本 |
| `shoot.mjs` | 队长前后对照截图脚本（`node docs/qa/B-R05-EXT2/shoot.mjs before\|after`，前置 5174 生产预览；含 390 溢出量测输出） |

种子数据（隔离上下文）：书籍走页面「载入演示数据」按钮（`demo-book-fractions` 就绪书、`demo-book-draft` 提案草稿；localStorage 直写会被 store 严格校验拒绝，故用按钮路径）；课程直写 `zhiqikeyuan:courses`（进行中 + 已归档各一本，字段与 `StudyCourse` 类型严格一致）。

## 实施内容（I1 书籍 / I2 课程）

- **共享边界**：`globals.css`/`space.css`/`motion.css` 只读；`books.css` 91→248 行（保留 `.books-*` 前缀，新规则用 `.books-page` 后代作用域）；新建 `courses.css`（`.courses-*` 前缀）；两者零 `!important`、注释无提前闭合序列；节点加 `books-page`/`courses-page` 修饰类。
- **窄视口修复（E2 首优先项）**：`≤900px` 单列后 `.books-rail` 解除 `sticky`（原先持续吸顶占满视口并挤压正文；姊妹类 `.space-scope-rail` 早有 static 覆盖而 books-rail 缺失）。
- **书籍列表**：卡片悬浮语言（150ms 抬升/阴影/箭头位移）、搜索 ≥640px 常驻 + 匹配计数行 + 内嵌图标、删除改两击确认（替代 `window.confirm`）、章/页/时间图标化、异步按钮 busy/disabled。
- **书籍详情**：确认提案/确认大纲 busy 态、模拟编译加载提示、侧栏长章节名截断、书签图标化、已读/未读视觉区分；重建两击确认按 §7.2 保留原实现。
- **课程列表**：卡片悬浮语言、页脚资料数图标化 + 空资料直述（**不显示未接入的会话数**）、归档折叠头视觉过渡、创建按钮 busy。
- **课程详情**：大纲进度条（`progressbar` + `width 300ms`）、单元位置编号 / covered 删除线 / 下一单元高亮 / topics 单行截断；资料行 kind 图标 + 不可用后缀独立 `shrink-0` + 移除钮 hover/focus 显隐；保存与归档 busy；学习约定保留弹窗路径仅视觉增强。
- **动画来源**：全部对照固定参考明确参数（`transition-all duration-150`、`transition-[width] duration-300`、`transition-opacity`、`active:scale-*`）；无来源不添加；减少动画复用 `motion.css` 全局机制。

## 检查记录

| 检查 | 结果 |
| --- | --- |
| typecheck | pass |
| lint（`--max-warnings=0`） | pass（0 警告） |
| unit（Node26 + `--no-experimental-webstorage`） | 43 文件 297/297（与基线一致） |
| build | pass |
| e2e（隔离 5174 自动拉起） | 154/154（一次通过） |
| api | 未重跑（本批零后端改动；基线 181） |
| **独立验收 A1** | **pass 0 fail**（三视口 12 组合 0 溢出；390 rail `static` 实测滚动 top 247.5→-152.5、1440 恢复 sticky 吸顶；reduce 实测 1e-05s；既有 aria/文案前提全套；R-11 三态含重试链路、损坏数据逐字节未变） |
| 390 视口 | 四页 before/after 各 4 张，溢出扫描均 0 |

## 实现期与集成期修复（归属记录）

1. **I2 自测发现**（含在候选内）：课程资料「不可用」后缀在 390 下被长 label 推出视口（right=601>390）——label 拆为 `truncate` 的 `courses-resource-text` + 后缀独立 `shrink-0`；复测 suffix right=320。
2. **E2 首优先项**（含在候选内）：`.books-rail` 窄视口解除吸顶。
3. 候选期无集成失败：typecheck/lint/unit/build/e2e 一次通过；A1 亦一次通过（区别于 v1 批的两轮）。

## 边界与未验

- 本批只关闭 R-05 中这四个页面切片，**不关闭 R-05 全站**；设置/教案/阅读/写作/`/space` 其余子页仍待后续批。
- 按 §7.2 裁定**保留现状**（记入矩阵与 STATUS）：StatCard 化统计、新建入口改网格末格卡、归档区紧凑行、附加资料内嵌面板、BookCreator 知识源页签、CourseNextStep/CourseProgress 聚合磁贴、Mode/Persona 字段、「N wrong」徽标、会话计数与最近活跃时间、阅读器侧栏折叠、HealthBanner、Chat 面板、compiling/paused/error 状态机（最后若干属 H1）。
- 13 处「参考结构改动会触碰既有 e2e 断言」的事项全部选择保留现状，**零断言改动**。
- 动画未逐帧采样曲线/中断（MOTION_MATRIX 相应条目保持「实现待验收」）；触摸真机、真实供应商、真实生成流水线不在本批范围。
- A1 未执行项：`after/` 像素级 diff（以实测+目测一致替代）、typecheck/lint/build 未重复跑、e2e 未运行（归队长，已全量跑过）。
