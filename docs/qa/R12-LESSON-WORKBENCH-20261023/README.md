# R12 教案工作台（2026-10-23）

> 范围：`/lesson-plans` 重做为 magic-resume 形态（模块轨 · 章节编辑 · A4 校样台 + 悬浮 dock），
> 正文预览按 `lesson-plan-blank.docx` 四表逐行还原，导出目录页码与预览同源。
> 本目录为**文字记录**；逐张截图属一次性走查产物，未入库。

## 门禁（2026-10-23 实测）

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 后端 | `cd apps/api && uv run python -m pytest` | **1946 passed / 0 failed**；导出子集 `tests/test_lesson_export.py` 11 passed |
| 前端单测 | `NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit` | **87 文件 771 例**全绿 |
| 类型 / Lint | `npm.cmd run typecheck` / `npm.cmd run lint` | 0 / 0 警告 |
| 构建 | `npm.cmd run build` | 成功（15 条静态路由） |
| e2e | `npm.cmd run test:e2e` | **17 passed**（msedge 通道；含 `/lesson-plans` 公共壳当前项与无横向溢出） |

## 分页填充（2026-10-23 追加）

- 长表格行按可用高度跨页拆分（评价/反思子项逐项可拆）；续行标签列留空、候选 id 保留。
- 估算与 CSS 对齐：单元格内边距改为 12px，去掉虚高段距；`.lw-sheet-line + .lw-sheet-line`
  真正消费 `--lp-paragraph-gap`（与导出 docx 的段后距同值）。
- 长文样本（学情 80 行 / 教材 50 行 / 内容 30 行 / 思政 15 行 / 过程 4 行 / 评价 20+18 行 /
  反思 25 行）实测：**11 页**（修复前 14 页）；除末页外每页底部空隙 **5–36px**，无 `scrollHeight`
  溢出；续行在下一页从标签列空白处继续，不丢字。
- 新增 3 例单测：长行跨页不丢字、首页利用率 ≥ 90%、续行保留候选 id 且标签只在首段。

## 视觉走查

- 视口：1440×900、1600×1000、1920×1080、390×844；深色主题（`zqky.theme=dark`）。
- 状态：空稿、填充稿（基本信息/目标/过程/评价/反思）、教学过程手风琴展开、帮助弹层、
  面板折叠、dock tooltip；浏览器控制台 0 error。
- 核对点：
  - 左栏模块轨标签在 1440 下完整显示；拖拽/↑↓ 排序、显隐、删除、「已移除」还原可用。
  - 预览逐表结构：4 列基本信息、2 列教学分析、目标/策略同表（vMerge + 重点/难点两行）、
    两行过程表头 + 阶段条、评价四项、反思三项；页脚按正文从 1 起，页尾红色虚线用文档页码。
  - 深色主题下纸面恒白；dock/卡片/提示全部走 token。
  - 390：页签切换三栏单页显示，表单与预览可滚动，无横向溢出（e2e 已覆盖）。

## 未执行

- **真实导出下载未做**：本机数据目录没有学科/班级字典，无法新建可导出的教案。
  导出结构由 `tests/test_lesson_export.py`（11 例，含重开校验）覆盖；`sectionPages`
  随请求发送由 `LessonWorkbench.test.tsx` 断言。
- **打印对话框未在真机点开**：打印 CSS（`@page lesson-paper`、只印纸面）为静态规则，
  未做打印预览截图。

## 复跑

```powershell
cd apps/api; uv run python -m pytest tests/test_lesson_export.py
cd ../..; $env:NODE_OPTIONS='--no-experimental-webstorage'; npm.cmd run test:unit
npm.cmd run build; npm.cmd run test:e2e
```
