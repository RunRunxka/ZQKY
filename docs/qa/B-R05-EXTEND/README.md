# B-R05-EXTEND v1 证据（2026-09-18）

任务卡：[TASK-CARD.md](TASK-CARD.md)（含 §7 队长裁定）。起点 SHA `3f968b0`（分支 `codex/replica-review-20260908`）。
范围：R-05 视觉规范推广首批——`/knowledge-bases`、`/knowledge-bases/[kbName]`、`/notebooks`、`/notebooks/[notebookId]` 四个页面条目。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `TASK-CARD.md` | 任务卡定稿：范围、共享层边界、独占文件表、资源分配、队长裁定（3 处 e2e 冲突风险 + 2 项范围待决的结论） |
| `E1-GAP-LIST.md` | E1 只读取证产出：四页逐页差距清单（信息结构/交互状态/动画三类，双证据文件:行号；含附录 A 共享类影响面、附录 B 既有 e2e 断言清单） |
| `before/` | 改动前四页三视口截图（1440×900 / 1920×1080 / 390×844）+ 每个视口 1 张 Tab 焦点图，共 24 张 |
| `after/` | 改动后同视口同种子截图，共 24 张 |
| `shoot.mjs` | 截图脚本（`node docs/qa/B-R05-EXTEND/shoot.mjs before\|after`，前置 5174 生产预览） |

种子数据（隔离上下文，不读真实用户数据）：知识库 2 个（含进行中文档、长文件名、失败样本路径）、笔记本 2 个（含长名称）、记录 3 条（含长标题）、IndexedDB 会话 1 条（供来源回链校验）。

## 实施内容（I1 知识库 / I2 笔记本，两张有界实现卡）

- **共享边界**：`space.css` 与 `globals.css` 本批只读；新增 `features/knowledge/styles/knowledge.css` 与 `features/notebooks/styles/notebooks.css`，全部选择器以 `.kb-page`/`.kb-detail`/`.nb-page` 起头，只消费既有变量层；既有 `space-*` 类名零改名零删除。
- **知识库列表**：下划线指示器页签（图标 + 计数徽标）、卡片状态圆点（处理中蓝+脉冲）、ChevronRight 悬停显影、hover 描边与焦点环、描述 `line-clamp-2`、空态图标块 + 主行动按钮、搜索框内嵌图标、引擎分组图标 + 说明、错误条重试/关闭。
- **知识库详情**：头部图标块 + 状态徽标带图标、分区导航改下划线页签（五个 exact 文本与 `aria-label` 未变）、文档行操作改悬停显影 + 行内二段移除确认、批量操作进行中禁用 + 旋转图标、索引区头部与版本行状态图标章。
- **笔记本**：左栏 168→250px（仅本页）、激活项左侧 2.5px 指示条（200ms）、描述行、多色类型徽章（保留 `space-chip` 以满足既有断言）、时间戳移入行头、行 hover、操作钮过渡与 active 缩放、展开区 `pop-in`（200ms cubic-bezier(0.22,1,0.36,1)，对照参考 `dt-pop-in`）、ConsoleNotice 空/错态、深链错误独占呈现、删除后 URL 规范化、`popstate` 同步选中。
- **动画来源**：全部对照固定参考明确参数（`animate-pulse`、`animate-spin`、`transition-colors/opacity duration-150`、指示条 `duration-200`、`dt-pop-in` 200ms）；无参考来源的动画一律未添加；减少动画复用 `motion.css` 全局机制，新 CSS 无 `!important`。

## 检查记录

| 检查 | 结果 |
| --- | --- |
| typecheck | pass |
| lint（`--max-warnings=0`） | pass（0 警告） |
| unit（Node26 + `--no-experimental-webstorage`） | 43 文件 297/297（与基线一致） |
| build | pass |
| e2e（隔离 5174 自动拉起） | 154/154（首轮 153/154：深链双 `role="alert"` strict 冲突，修复后复验 10/10，全量复跑 154/154） |
| api | 未重跑（本批零后端改动；基线 181） |
| 三视口 | 1440×900 / 1920×1080 / 390×844 前后各 12 张 + 焦点图 |
| 键盘焦点 | 每页每视口 Tab 焦点图（before/after 均留档） |
| 减少动画 | 截图脚本以 `reducedMotion='reduce'` 拍摄 |

## 集成期修复（队长执行，归属记录）

1. `notebooks.css` 注释行含 `*/` 序列（`--radius-*/--shadow-*/`）导致 CSS 注释提前闭合、Turbopack 构建失败——改为中文顿号表述后构建通过。
2. 深链无效笔记本时顶部 banner 与 ConsoleNotice 同时渲染 `role="alert"`，触发 e2e strict mode 冲突（该用例断言单数定位），按 153/154 首败证据收敛为仅 ConsoleNotice 呈现；未改动任何测试断言。

## 边界与未验

- 本批只关闭 R-05 中这四个页面的切片，不宣称 R-05 全站统一；`/space` 其余子页、books/courses/reading/writing/settings/教案不在本批。
- 参考中存在但按 §7 裁定不纳入的项：Markdown 渲染器、文件树预览、行内连续文档编辑器、toast 系统、新建入口迁移、记录操作合并菜单。
- 动画未逐帧采样曲线/中断（MOTION_MATRIX 相应条目保持「实现待验收」）。
- 触摸真机、真实供应商、真实 RAG/解析服务不在本批范围。
