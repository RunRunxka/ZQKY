# 当前状态与实施主线

更新：2026-09-23（启动 GLASS-POLISH v1 当前任务：浅色流体加深、浅色覆盖聊天区、流动增强）。本文件是唯一进度、问题、任务和后续计划入口。长期目标与稳定决定见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，逐项范围见三矩阵，历史首败与批次全文见 [整理前完整快照](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)。

## 1. 目标与当前结论

**以智启课源品牌完成固定 DeepTutor 的产品前端、AI 交互与原有动画；全站以当前学习问答 `/chat` 为视觉基准，保留蓝色主题及原业务功能。整体尚未完成。**

**当前实施批是 GLASS-POLISH v1（玻璃主题三处调整：浅色流体加深、浅色覆盖聊天区、流动增强，2026-09-23）**，范围与实测数据见 §5.0，证据与前后截屏见 [qa/GLASS-POLISH](qa/GLASS-POLISH/README.md)。**本批只调玻璃主题的观感与浅色显隐，不含新增功能，也不是全站视觉验收。**

上一实施批是 **AGPL-OUT v1**（移除 AGPL-3.0 流体背景并替换为自研实现，2026-09-23，已推送，记录见 §5.6）。**该批的历史残留为知情保留，见 [玻璃主题许可台账](licenses/glass-theme/README.md) §2.5。**

上一实施批是 **SKILL-INJECT v1**（Skill 注入通道与三个内置教学技能，2026-09-23，已推送 `origin/feat/glass-theme`，记录见 §5.7）。**该批只做提示词级技能上下文与本地目录，不含 MCP 连接/工具调用，也不含真实教材检索。**

上一实施批是 **H1-BOOKS-PIPELINE v2**（书籍生成流水线与增量阅读闭环，2026-09-20 完成本地实现与验收，记录见 §5.8 与 [qa 任务卡](qa/H1-BOOKS-PIPELINE/TASK-CARD.md)）。**该批全部为本地模拟执行器与本地显式注入，不接真实 LLM/解析：通过不代表真实供应商能力，也不代表书籍模块或全站完成。**

上一个已交付批次是 **R-05 内容视觉统一收尾批**。**第六批（B-R05-EXTEND v5，2026-09-19）**覆盖阅读工作区（`/reading/[workspaceId]` 含 sessions 子页）与 `/space` 四子页，并同批受控诊断、修复 R-09 滚动跟随的真实缺陷（详见 §3 R-09-FLAKY）。独立验收记录为 A1 **pass 0 fail**（R-09 五例 5/5、压测 10/10、55 项浏览器实测）。**沿用外部总控收口记录，R-05 在 §5.3 登记的既有页面视觉推广范围内关闭**，不扩大为全站逐状态视觉或功能完成。下一实施批尚未指定，H1/H2 是建议路线，见 [当前批次与下一动作](#current-task)。

- 最近产品提交：视觉六批（见 §4 批次表最终 SHA）；阅读补测修复 `a9ebcaa`。新接手者必须重新核对 `git status --short`、`git log -5 --oneline`，不能把文档提交当产品验收候选。
- 工作树中 `.zcode/agents/*.md` 是用户自己的改动，批次全程不触碰、不纳入提交。
- **R-13 是模型真实长答未关闭项，不是整个项目唯一剩余问题。** 逐状态视觉缺口、未实现模块、真实复杂能力和未验动画仍属于最终交付范围。
- 主聊天仅真实 FastAPI；阅读、知识库和写作等批准的显式模拟仍保留。执行模拟不能省略交互状态，模拟通过不能标为真实供应商通过。

## 2. 模块现状与保留边界

| 模块 | 已有实现与局部成果 | 仍未完成或未验 |
| --- | --- | --- |
| 公共壳 | `/chat` 单一主页；220/56px侧栏、跨页折叠；隐藏页父菜单；手机模态抽屉；404一层壳；聊天独立学习记录中栏 | R-05 收口范围见 §5.3；错误页reset运行时未验；部分过渡曲线未验 |
| 教案 | 本地规则填充、编辑、草稿恢复、Word/PDF导出；R-05 v4 有界视觉推广及导出/草稿回归 | 不是AI生成；逐状态视觉与动画按矩阵保留未验项；冻结旧版及原Word不改 |
| 学习问答 | 三协议SSE、推理/正文及公式、本地会话、模型选择；生产mock残留已清；来源消息定位与失效会话空态已修 | ask_user、工具、附件解析及复杂业务真实执行通道未接；不能以存量组件当可发起功能 |
| 模型与供应商 | contract-v1、38条注册（36现行+2 legacy）、6 backend、专用适配/受管认证、发现来源、推理控制、v1→v2迁移与凭证补偿；卡片/详情/发现/参数/默认选择闭环 | 真实仅DeepSeek指定场景有证据，其余37条注册项无独立真实通过；Codex真实登录条件仍需核实具备；R-13未关闭；模型动画partial |
| 学习空间/笔记/题库 | 会话历史、角色、题库、笔记编辑、跨页保存；真实sessionId回链+可选messageId定位，旧数据缺身份不猜测；`/space` 首页、四子页与笔记本列表/详情已列入视觉推广批 | `/space` 功能级完整验收（弹窗/错误/长文案逐状态）待补；笔记编辑器等参考差距按矩阵保留；CLI只本地登记，无真实执行 |
| 知识库 | 登记→解析→索引显式模拟，进度/取消/重试/恢复；局部状态与数据保护已有证据；R-05 v1 列表/详情视觉有界验收 | 不读真实文件、不做向量检索/RAG；全部分区/弹窗逐状态视觉及进度动画仍未完整验收 |
| 书籍/课程 | 14类block、练习保存、笔记、大纲、资源、进度/导出；课程目录读取失败三态及隔离已修；**H1-BOOKS-PIPELINE v2 起书籍生成可观察/可暂停/可中断/可重试**（七态状态机 + 本地模拟执行器 + 活动条/展开详情/暂停横幅/块页重试/增量阅读/未完成导出标注） | 书籍生成仍为本地模拟（无真实 LLM/解析与真实供应商证据）；BookChatPanel、课程学习会话缺口；部分block仅模拟形态；逐帧动画与硬件触摸未验 |
| 阅读 | 材料/集合、批注/书签/进度、显式模拟伴生；R-09滚动/会话历史/已测跨会话归属已修；READ-RETRY/READ-END 已修（2026-09-18） | 媒体原视图、完整过程/来源仍待补验 |
| 写作/Whisper | 自动保存、显式模拟AI预览/应用/取消/重试、撤销/版本、双席位房间；写作列表/编辑器已有 R-05 v3 视觉证据 | DOCX导入、完整参考差距、逐状态视觉与动画；写作批不代替 Whisper 独立验收 |
| 伙伴/智能体 | `/agents`规划入口 | 列表/创建/详情/群组、任务过程与执行闭环待实现 |
| 精通/记忆/账户 | 无完整业务闭环 | 页面、阶段/反馈、身份/权限、本地保存与联动待实现 |
| 完整设置 | 外观、模型、MCP、Skills、关于已有；扩展管理本地模拟 | 工作空间、解析、网络、记忆、任务模型等整合；MCP/Skills唯一管理仍在设置 |

页面统计只由 [PAGE_MATRIX](replica/PAGE_MATRIX.md) 维护：保留53个非调试条目的功能分类，不能当产品完成百分比。功能、视觉、动画和真实服务状态分别见 [AI_INTERACTIONS](replica/AI_INTERACTIONS.md) 与 [MOTION_MATRIX](replica/MOTION_MATRIX.md)。

## 3. 问题台账与验收限制

| 编号 | 当前状态 | 范围与依据 |
| --- | --- | --- |
| R-01 | 已关闭 | 跨.env/JSON并发、删除失败补偿及备份；模型审查修复后独立复验。关闭不证明所有供应商真实可用 |
| R-02 / R-04 | 已关闭 | 唯一主页、唯一当前菜单及手机焦点；`e7fb2a4`公共壳批 |
| R-03 | 已关闭 | 主聊天不可达模拟分支/文案/CSS清理；`a5bb39c`。历史类型与测试替身不构成生产模拟 |
| R-05 | **既有页面推广范围内已关闭（沿用2026-09-19收口记录，依据见 §5.3）** | 公共变量层 + `/space` 首页与四子页 + 知识库/笔记本四页 + 书籍/课程四页 + 写作/阅读库四页 + 设置/教案两页 + 阅读工作区三栏（B-R05-SPACE-VISUAL v1 与 B-R05-EXTEND v1~v5）。**边界**：各页逐状态功能/视觉标签不升级；`P-books-pages-[pageId]` 等矩阵未验项保留；`待实现` 模块按基准建设；动画精度（逐帧曲线/中断）随 H6 总验收补齐 |
| R-06 | 壳缺失修复已关闭；恢复另有未验项 | 404壳及返回主页已有浏览器证据；错误页reset只有代码/构建证据，运行时仍not_run |
| R-07 / R-08 / R-12 | 模型批实现并有相关回归 | 受控推理字段、独立清除凭证、作用域文案已修；R-07字段支持不等于全协议真实推理验收 |
| R-09 | 已关闭已复现的A/B/C | `a1fa16e`：上滚不被拉回、已测跨会话轮次显示/收尾、push/pop导航。正文媒体与全部异常终态合同不因本批升级 |
| R-10 | 已关闭A/B两部分 | `a5bb39c`会话身份回链；`aeacea8`消息定位/失效会话不回落最近会话；真实保存按钮路径有e2e |
| R-11 | 已关闭 | `2308822`：课程目录损坏/读取被拒不崩页、不冒充空、不丢引用；失败目录不阻断其他来源 |
| R-13 | **未关闭，真实服务轨道** | 默认2048+推理样本零正文；off/2048有正文但length截断；off/8192指定样本stop。不能自动关推理、无界加预算或断言正式384000配置必然成功 |
| READ-RETRY | 已关闭（2026-09-18） | 受控首败证明错误态"重试"被 turn 非空挡住（run 仍 1 次），`a9ebcaa` 放行错误态重试、保留流式防重入；组件级替身回归+全量单测 |
| READ-END | 已关闭（2026-09-18） | 首败证明重复/迟到 end 落库 2 份；`a9ebcaa` finalizeTurn 按 turnId 幂等（finalizedTurnsRef），旧轮迟到 end 不重复落库/不复活取消标注/不清新轮；R-09 会话归属语义未变 |
| R-09-FLAKY | **已关闭（2026-09-19，含产品修复）** | 受控诊断确证**双层机制**：(a) CDP 层——`mouse.wheel` 派发与 `evaluate` 读值竞争（24 次决定性实验、wheel 到达延迟实测 20-30ms）；(b) **产品层真实缺陷**——流式拉底产生的 `scroll` 事件因 `dist<90` 把 `followBottom` 重置回 true，用户上滚被永久吞掉（现场探针抓到完整序列：上滚成功 top=0 → 5ms 后拉回 179 → 最终贴底 212）。修复（`a9c28ea`）：`userScrolledAwayRef` 同步记录用户意图、堵住 `setState` 提交延迟窗口；`programmaticScrollRef` 区分程序化拉底副作用与用户滚动；spec 侧仅一处 `expect`→`expect.poll`（**阈值 `<60` 与语义未变**）。验证：R-09 五例 5/5、`--repeat-each=10` 队长复测 **10/10**（修复前同环境 3/10 失败）、A1 独立复现 **10/10**、阅读 spec 17/17、全量 154/154。**队长注意**：v4 批曾试过"仅加 poll"并失败撤回——那次失败正是因为 poll 只吸收 CDP 层、会暴露产品层的 212 贴底值，此结论已归档 |

阅读两项（READ-RETRY/READ-END）已于 2026-09-18 受控补测并有界修复关闭。2026-09-15方向审查的事实已整理于本表；完整临时报告 `_work/review-direction-6d98718/REVIEW.md` 仅是补充，交接不依赖其存在。

其他仍需保留的边界：全站视觉/动画尚未通过；硬件触摸及部分快速中断未验；真实供应商/真实OAuth缺条件的项保持not_run；主聊天复杂能力缺真实通道；模型预算样本只证明对应模型/参数/问题。

## 4. 已完成批次与证据索引

以下是**指定候选的历史验证**，不是本次文档整理重新运行的全部测试。实现者自检与独立验收范围以证据为准，不因提交或测试数增加扩大模块完成度。

| 批次 | 实现 / 收口提交 | 关键验证与独立范围 | 证据 |
| --- | --- | --- | --- |
| MODEL-EXEC与MR-01~16修复 | `1805397`→`560ac76`→`4ef803b` / `3dfc2fa` | 首轮needs_revision；修复API181、unit274、e2e88；后端/组件独立复验通过，真实及动画不全覆盖 | [模型审查与修复全文](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)，正式model回归测试；部分原始探针仅在_work |
| B-MODEL-ACCEPT | `9965592` / `2d0caaa` | 嵌套弹窗/草稿/焦点；unit274、API181、e2e92；视觉为实施者检查、动画partial；DeepSeek真实partial | [API报告](qa/model-accept-20260913/r13-api-report.md)、[浏览器证据](qa/model-accept-20260913/r13-browser-evidence.json) |
| B-H0R-SHELL | `e7fb2a4` / `957730d` | unit278、API181、e2e119；独立遍历路由/三视口；reset运行时与曲线not_run | [截图目录](qa/shell-accept-20260913/)、`tests/e2e/shell-home-nav.spec.ts` |
| B-H0R-CHAT-LINKS | `a5bb39c` / `97c6992` | unit285、API181、e2e128；来源身份与真实失败不回模拟；后续消息定位由下一批补齐 | [失败截图](qa/chat-links-20260914/r03-real-failure-no-mock.png)、`tests/e2e/chat-source-links.spec.ts` |
| B-CHAT-SOURCE-FINISH | `aeacea8` / `4869e88` | unit286、API181、e2e140；独立7场景、真实产物保存按钮、deactivate无持久化副作用 | `tests/e2e/chat-message-locate.spec.ts`、[批次全文](archive/DELIVERY_HISTORY.md#snapshot-status-20260915) |
| B-COURSE-RESOURCE-SAFETY | `2308822` / `e7cd87f` | unit292、API181、e2e149；独立7例22断言，存储逐字节不变；笔记目录未单独注入 | [故障截图](qa/course-r11-20260914/)、`tests/e2e/course-resource-faults.spec.ts` |
| B-READING-NAV-SCROLL | `a1fa16e` / `33ecd58`、`6d98718` | 实施者e2e154、API181；独立黑盒8/8+reading17/17，未独立重跑154全量 | [README与黑盒用例](qa/reading-r09-20260915/README.md) |
| B-R05-READ-BOUNDED | `a9ebcaa`（阅读切片） | 首败5用例（重试无效、重复/迟到end双份落库）后修复；阅读目录9/9、全量unit297、eslint 0警告 | [首败与修复摘要](qa/space-r05-20260918/read-first-failure-excerpt.txt)、`ReadingWorkspaceCompanion.test.tsx` |
| B-R05-SPACE-VISUAL | 见本批最终提交 | typecheck/lint/unit297/build/e2e154 全过；三视口前后截图+焦点+reduce；`P-space` 升部分验收、M-space-tile 实装 | [qa README](qa/space-r05-20260918/README.md)；api 未重跑（零后端改动，基线181同日现场复跑过） |
| B-R05-EXTEND v1（R-05 推广首批） | `82871fa` → `19b514c`（修复版） | 知识库/笔记本四页视觉推广；typecheck/lint/unit297/build/e2e154 全过；E1 差距清单 90+ 条；独立验收 A1 首轮 **needs_revision**（390 窄视口：rail 溢出、记录标题 0 宽），修复后复验 **pass 14/14**；三视口前后 48 张+焦点图 | [批次证据](qa/B-R05-EXTEND/README.md)、[E1 清单](qa/B-R05-EXTEND/E1-GAP-LIST.md)、[A1 报告](qa/B-R05-EXTEND/A1-REPORT.md)；api 未重跑（零后端改动，基线181） |
| B-R05-EXTEND v2（R-05 推广第二批） | `1ca673c` | 书籍/课程四页视觉推广；E2 差距清单 97 条 + 队长裁定 §7（13 处 e2e 冲突全部选择保留现状、零断言改动）；typecheck/lint(0警告)/unit297/build/e2e154 全过；**独立验收 A1 一次通过 pass 0 fail**（三视口 12 组合 0 溢出、390 rail 解除吸顶实测、reduce 压制实测、R-11 三态含重试链路与损坏数据逐字节未变）；三视口前后 48 张+焦点图 | [批次证据](qa/B-R05-EXT2/)、[E2 清单](qa/B-R05-EXT2/E2-GAP-LIST.md)、[A1 报告](qa/B-R05-EXT2/A1-REPORT.md)；api 未重跑（零后端改动，基线181） |
| B-R05-EXTEND v3（R-05 推广第三批） | `fc005d0` | 写作/阅读库四页视觉推广；E3 差距清单 64 条 + 队长裁定 §7（10 处 e2e 冲突保留现状、动画口径修正）；`reading.css` 与 `ReadingWorkspace.tsx` 禁区零改动；typecheck/lint(0警告)/unit297/build/e2e154 全过（首次 build 遇 Turbopack 间歇崩溃 0xC0000409，复跑两次成功）；**独立验收 A1 一次通过 pass 0 fail（31 项）**（三视口 0 溢出、材料库行头窄视口修复实测、重名按钮复核、模拟标注 9 条逐字、R-09 工作区不回退） | [批次证据](qa/B-R05-EXT3/)、[E3 清单](qa/B-R05-EXT3/E3-GAP-LIST.md)、[A1 报告](qa/B-R05-EXT3/A1-REPORT.md)；api 未重跑（零后端改动，基线181） |
| B-R05-EXTEND v4（R-05 推广第四批） | `d54bd93` | 设置/教案两页视觉推广（全站最后两个既有模块页）；E4 差距清单 34 条 + **双风险清单各 10 条** + 队长裁定 §8；**模型区 contract-v1 与教案导出/草稿链路双禁区零改动**（`model-settings/**`、`chat/**`、`print.css`、`services/pagination.ts`、`model/*`、`assets/` diff 全空）；增量全进新建 `settings-extend.css`/`lesson-visual.css`；typecheck/lint(0警告)/unit297/build/e2e154 全过；**独立验收 A1 pass（33 pass / 0 fail / 4 not_run）**——模型区 mock 成功态全链路 + 教案 `verifyDocx` 导出产物 + 损坏草稿不覆盖，390 页面级溢出实测归零 | [批次证据](qa/B-R05-EXT4/)、[E4 清单](qa/B-R05-EXT4/E4-GAP-LIST.md)、[A1 报告](qa/B-R05-EXT4/A1-REPORT.md)；api 未重跑（零后端改动，基线181）；**R-09-FLAKY 观察中**见 §3 |
| B-R05-EXTEND v5（R-05 收尾批） | `a9c28ea` | 阅读工作区三栏（`/reading/[workspaceId]` + sessions 子页）与 `/space` 四子页（chat-history/questions/personas/cli-apps）视觉推广；E5 差距清单 44 条 + **交互保护区 19 条机制** + **reading.css 影响面 14 类** + 队长裁定 §8；增量全进新建 `reading-ws.css`/`space-sections.css`（`reading.css`、`space.css` 零改动）；**同批受控诊断并修复 R-09 滚动跟随真实缺陷**（follow-bottom 竞争，见 §3 R-09-FLAKY）；typecheck/lint(0警告)/unit297/build（队长重建 BUILD_ID `eYs-YyFDf0XQJugH8zZcO`）/e2e154 全过；**独立验收 A1 pass 0 fail**（R-09 五例 5/5、压测 `--repeat-each=10` 10/10、55 项浏览器实测、R-10 回链 21/21+12/12、space-pages 8/8） | [批次证据](qa/B-R05-EXT5/)、[E5 清单](qa/B-R05-EXT5/E5-GAP-LIST.md)、[A1 报告](qa/B-R05-EXT5/A1-REPORT.md)；api 未重跑（零后端改动，基线181） |
| 2026-09-15方向审查 | `6d98718`只读产品审查 | Node26.2.0 + `--no-experimental-webstorage`：42文件292/292，exit0；未重跑浏览器/API/build | 最近Codex审查结果；临时报告_work/review-direction-6d98718/REVIEW.md，本表保留关键结论 |
| H1-BOOKS-PIPELINE v2（书籍生成流水线与增量阅读闭环） | `f31d39f`（父提交 `bf460ab`；提交信息 `feat(books-pipeline): H1-BOOKS-PIPELINE v2——书籍生成流水线与增量阅读闭环`） | typecheck/lint(0警告)/unit 46文件353/build(BUILD_ID `TPMei2ra-L9r31dqKSPpl`)/e2e 168（既有154+新增14）全过；**独立验收 A1 pass 32 / fail 0 / not_run 0**（含 4 项挑刺：无 run 记录书的整页重生成、笔记写入失败不谎报、provider 开关单独开启真暂停、interrupted 恢复入口；并检出 `contentVersion` 生产路径从不写入，修复后复验）；视觉/动画三视口+焦点+reduce+快速开关+中断实测（浮层 180ms、呼吸 1.8s、reduce 压制 1e-05s） | [批次证据](qa/H1-BOOKS-PIPELINE/README.md)、[首败台账](qa/H1-BOOKS-PIPELINE/DEFECT-LEDGER.md)、[A1 报告](qa/H1-BOOKS-PIPELINE/A1-REPORT.md)；**全部为本地模拟执行器，不含真实 LLM/解析**；api 未重跑（零后端改动，基线181） |

### 4.1 真实服务与数据事件

- 真实供应商证据目前限DeepSeek指定场景，普通JSON接口与SSE已分别测量；其他注册项不得标真实通过。2026-09-12与09-13的模型、推理开关和预算不同，历史Pro8192失败不与后续off/8192成功混为同配置结果。
- B-MODEL-ACCEPT受控浏览器样本首个可见中文1172ms、KaTeX12处0错误，停止/重试/刷新有证据；不是所有模型延迟保证。
- 早期探针曾误写正式.env一行，随后实施者报告按行恢复；缺早期前置散列，不能追认当时完全未写。后续修为内存凭证副本并有前后不变断言。完整事件、当时MD5与来源保留在归档，不删除、不改成“从未写入”。
- 正式384000预算配置在相应API报告中为not_run，不依据它保证日常无零正文；本次不读写正式配置。

### 4.2 测试环境与文档整理记录

根测试命令与启动方式见 [README](../README.md)。Node26单测按已验证配置运行：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run test:unit
```

原阅读批使用临时localstorage文件获得292/292，裸命令失败数量在报告中有不同口径；原文完整归档，不据此改写成产品回归。后续只读审查使用上面的既有参数292/292通过，不需要升级依赖。该结论不声称裸命令已通过。

2026-09-15 **DOC-FOCUS v1**（`7fc61f5`）只整理现行文档、归档、链接与任务；未修改产品、测试实现、依赖、凭证或浏览器数据。已验证3份完整归档原文/散列、现行文档链接、矩阵ID与数量、D1–D16及R-01～13和后续路线完整性，`git diff --check`通过；[机器检查结果](qa/docs-focus-20260915/verification.json)随Git保存。独立只读内容复核通过，提出的两处阅读矩阵措辞已收窄并改成现行索引；另对照源码订正API旧删除顺序描述。产品测试该轮未重跑（纯文档变更），上面的292项为先前同日只读产品审查结果。

2026-09-20 **DOC-FOCUS v2** 从现场 `a27dd69` 继续整理：保留后续六批视觉推广、阅读补测及 R-09 增强修复的提交与证据；统一过期摘要、R-05 范围和接手规则，改用固定锚点 `current-task` / `roadmap`，避免重做已交付批次。校验结果见 [文档检查](qa/docs-focus-20260920/verification.json)。本批不修改产品代码，不读写正式配置；产品测试、浏览器、真实供应商及独立产品复验均未执行，既有 pass 只属于原候选与原验收范围。

<a id="current-task"></a>

## 5. 当前批次与下一动作

### 5.0 当前实施批：GLASS-POLISH v1（浅色流体加深、浅色覆盖聊天区、流动增强）

**状态：本批实现与浏览器验收完成（2026-09-23）**；证据与前后截屏见 [qa/GLASS-POLISH](qa/GLASS-POLISH/README.md)。

1. **需求（用户指定）**：① 浅色主题流动颜色太浅，加深一点；② 浅色要与深色一样能"覆盖"（透到）右侧聊天输入界面；③ 流动效果不明显，稍微增强。
2. **实测根因（不是凭感觉改的）**：① 浅色 palette 底色取 `hsl(h, 0.25, 0.955)` 近白，而流体是 `lighter` **加法**叠加——底色越白越快饱和成纯白，改前画布平均亮度 **246.4**、平均 RGB (243,247,250)；② `chat.css` 硬编码 `.chat-main` / `.chat-composer` 为 `background: white`，深色方案在 `glass.css:261` 起显式置了透明/玻璃，**浅色这一路从来没补齐**；③ 光斑漂移幅度偏小。
3. **实现**：`fluid-tones.ts` **只改浅色分支**（底色降到 `ramp(0.855, 0.9, 0.95)` 给加法留余量；bloom/mid 同步加深加饱和）；`fluid-shader.ts` 漂移幅度 ax/ay **×1.4**、叠加不透明度 0.38→0.42（位置与周期不变）；`glass.css` 新增浅色「主区/输入区让位」块（`.chat-main` 透明、`.chat-composer` 玻璃 + `blur`、焦点描边、6px 渐隐条改半透明以免留白边）。
4. **文件归属**：`components/layout/fluid-tones.ts`、`fluid-tones.test.ts`、`fluid-shader.ts`、`styles/glass.css`；证据 `qa/GLASS-POLISH/`。**未改深色分支**。

#### 5.0.1 本批结果（实跑）

- 前后对比（1440×900、玻璃开、色调 0°/深浅 25）：浅色画布平均亮度 **246.38 → 223.88**、平均 RGB **(243,247,250) → (212,226,243)**、亮度标准差 **4.56 → 5.71（+25%）**、色调数 **130 → 198（+52%）**；深色分支数值不变（亮度 11.13 → 11.28，属相位差）。`.chat-main` 由 `rgb(255,255,255)` 变为 `rgba(0,0,0,0)`，`.chat-composer` 由实白变为 `rgba(255,255,255,0.6)` + `blur(16px)`；深色两值未变。
- 流动强度（同页采样 2.5s）：浅色平均像素变化 2.13/255、变化 >2 的像素占比 35.9%；深色 3.14 / 38.1%。即持续运动。
- 补充验证：浅色渐隐条命中新规则（深色仍是自己的深色渐变）；1440 与 390 均无横向溢出。
- 工程检查：typecheck 通过；lint **0 警告**；unit **49 文件 / 382 例**（新增 3 例锁定浅色调色板不再回退到近白）；build 通过。

#### 5.0.2 语义变化与边界

1. **浅色"深浅"滑块现在也影响底色**：浅色 `color3` 由固定 0.955 改为 `ramp(0.855, 0.9, 0.95)`，滑块 0 = 最深、100 = 最浅（与深色同义）。
2. **深色调色板一字未动**，仅因共用的漂移幅度/不透明度提升而"动得略多一点"。
3. **玻璃主题仍无自动化测试覆盖**：全仓确认没有测试开启 `data-glass`，三处观感问题（含此前的预检 bug）正因此长期存在。要让视觉不回退需要单补一组玻璃主题的浏览器基线。
4. **未做**：会话态（有消息）整页截屏（本机后端未启动，起不了真实会话；渐隐条规则以临时插入同名元素验证命中）；改动前的运动基线采样（需回退构建两次，故"增强前 vs 后"的运动差值无实测数字）；中栏"学习记录"列仍是实底（与深色一致，用户本次只要求右侧）；未同步 `glass-chat-scaffold` 技能（其模板含同名三文件且基线图与该调色板绑定，同步需连带重出 9 张基线并更新 manifest，属独立一次操作）。

### 5.6 上一实施批：AGPL-OUT v1（移除 AGPL-3.0 流体背景，替换为自研实现）

**状态：本批实现与浏览器验收完成（2026-09-23）**；证据见 [qa/AGPL-OUT](qa/AGPL-OUT/)。合规结论与复核方法见 [玻璃主题来源与许可](../docs/licenses/glass-theme/README.md)。

1. **需求（用户指定）**：用户指出"项目后面可能公开使用，使用这个带 AGPL-3.0 有麻烦"，要求把已经写在 `glass-chat-scaffold` 里的原创流体实现搬回本项目替换掉 AGPL 版本。
2. **起点问题（两层）**：原 `fluid-shader.ts`（491 行）/ `fluid-tones.ts`（70 行）是 DSH-Transparent-UI-Plugin（AGPL-3.0）的**逐行移植**，且 `fluid-shader.ts` 自述 GLSL 源码 "verbatim from the site bundle"——字面量抄自 deepseek.com 线上包，**没有任何许可**。两个文件是静态 import（关开关也照样进 bundle），流体层在 `GlassBackdrop` 中默认开启，且此前只为"将来公开分发时注意"留了注释，**没有任何处置动作**。
3. **实现方式**：两个文件整份替换为自研实现（低分辨率 Canvas 2D + 正弦叠加驱动的软光斑 + 放大柔化 + `lighter` 叠加），对外接口（`FluidParams` / `SITE_FLUID_PARAMS` / `FluidShaderHandle` / `attachFluidShader` / `fluidToneColors` / `HUE_BASE`）保持完全一致。改写不采用——改写仍属演绎作品，不消除传染。
4. **同步改动**：`GlassBackdrop.tsx` 的上下文预检由 `webgl2` 改为 `2d`（**必须改**，机制见 §5.6.2）；`glass.css` 两处注释与设置页开关文案（"WebGL 流体背景"→"流体背景"）去掉 WebGL 表述；新增两份单测；新建玻璃主题许可台账。
5. **文件归属**：`components/layout/fluid-shader.ts`、`fluid-tones.ts`、`GlassBackdrop.tsx`、新建 `fluid-shader.test.ts`、`fluid-tones.test.ts`；`styles/glass.css`（仅注释）；`features/settings/SettingsWorkspace.tsx`（仅开关文案）；文档 `README.md` / `PROJECT_GUIDE` / 本文件 / 新建 `docs/licenses/glass-theme/README.md` / `docs/licenses/deeptutor-chat/README.md`（加指引）。

#### 5.6.1 本批结果（实跑）

- 工程检查：`npm run typecheck` 通过；`npm run lint`（`--max-warnings=0`）**0 警告**；`npm run test:unit` → **49 文件 / 379 例通过**（上一批 47/367，净增 2 文件 12 例）；`npm run build` 通过，`BUILD_ID = hkta-oovvflBHWmLYCGdh`。
- **真实浏览器验证**（1440×900、深色玻璃、流体开，`qa/AGPL-OUT/fluid-browser-check.cjs`）：常态 `data-glass-fluid-ok='on'`、画布 144×90、平均亮度 11.13（近黑）、亮度标准差 5.5、色调数 264、`changedBetweenFrames=true`（真的在动）；`data-motion=reduced` 时同样成帧但 `changedBetweenFrames=false`（只画一帧，不循环）。两场景 `ambientHidden=true`（CSS 环境光正确让位，无双重绘制）。
- 首败机制证据（headless Chromium 实测）：`先取 webgl2 再取 2d → null（槽位被占用）`；`先取 2d 再取 2d → 同一个对象`。这解释了为什么"换成 Canvas 2D 却不改预检"会导致全空白画布并把 CSS 环境光一起顶掉。

#### 5.6.2 语义变化（接手者必须知道）

1. **流体实现换了一整套**：WebGL2 流体求解 → Canvas 2D 低分辨率软光斑。视觉是"接近但非逐像素等同"；`FluidParams` 中 `decay / distortBoost / noiseBoost / swirlBoost / distortion / swirl / swirlIterations / shapeScale / rotation / proportion` 仅为接口兼容保留，**新实现不读取**（参数仍会被设置页写入 localStorage，但不再影响画面）。
2. **上下文预检必须是 `2d`**：一个 canvas 只能持有一种上下文。任何"WebGL → Canvas 2D"的替换都必须同步改 `GlassBackdrop` 的预检，否则 WebGL2 可用机型上槽位被占、拿不到 2D 上下文，画布全空白却标记 `data-glass-fluid-ok='on'`，把 CSS 环境光一起 `display:none` 掉——背景彻底空白且不报错。
3. **减少动画补齐本地开关**：原移植版只判系统 `prefers-reduced-motion`；新实现把本地 `html[data-motion="reduced"]` 一并纳入（"系统与本地设置均生效"的项目要求）。判定发生在挂载时，切换后需重挂载（刷新页面）才生效。
4. **粗指针设备不注册指针视差**：与替换前的指针策略保持一致。
5. **设置页文案**：流体开关由"WebGL 流体背景"改为"流体背景"（实现已不是 WebGL，文案不能继续暗示）。

#### 5.6.3 边界与未做

- 不做视觉逐像素对齐验收：原实现已删除，无法与 AGPL 版做同机对比；本批只验证"确实在绘制、确实尊重减少动画"。
- 未做像素级基线比对新旧实现（`glass-chat-scaffold` 里的 MAD 4.55 是另一套环境下的历史数字，不作为本批证据）。
- `glass.css` 磨砂配方未重写（判定为通用技术自有实现，依据见台账 §3）；若将来要求零外部来源表述，需另开一批。
- 未跑全量 e2e（168）；未在移动真机验证；未做独立 A1 验收。

<a id="skill-inject"></a>

### 5.7 上一实施批：SKILL-INJECT v1（Skill 注入通道与三个内置教学技能）

**状态：本批实现与本地验收完成（2026-09-23），已提交 `1f8fea9` 并推送 `origin/feat/glass-theme`。** 负责人：本会话实施；未做独立第三方验收（A1）。完整证据见 [qa/SKILL-INJECT](qa/SKILL-INJECT/README.md)（含真实服务原始输出）。

1. **需求（用户指定）**：用户指出"设置里有 Skill 和 MCP 服务，但是没有任何内容"，要求按评估结论实施——先做技能注入通道，并预置三个 P0 教学技能。**本批不做 MCP**。
2. **起点事实**：本批前技能完全不生效——`extensions-snapshot.test.ts` 明确断言真实服务不转发 extensions，`ChatStreamRequest` 无 skills 字段，`ChatWorkspace` 发送时从不构造扩展快照。设置里的 Skill/MCP 是纯标签。
3. **实现方式**：技能说明作为**提示词级系统上下文**注入。前端把"已启用 + 正文非空"的技能随轮次快照冻结下发；系统消息的唯一拼装点在 `apps/api/app/services/skill_context.py`，由 `apps/api/app/api/v1/chat.py` 在既有 `LLMRequest` 收口处前置。发送即冻结、重试沿用原快照；无有效技能时不携带 `skills`，保持旧请求形态。
4. **文件归属**：契约 `contracts/chat.ts`（skills 项加可选 `content`）；目录 `services/extension-catalog.ts`（内置技能预置、`seedBuiltinSkills`、`buildTurnExtensionSnapshot`、`skillTakesEffect`）；通道 `services/chat-stream.ts` + `features/chat/model/chat-service.ts` + `ChatWorkspace.tsx`；后端 `app/schemas/chat.py` + 新建 `app/services/skill_context.py` + `app/api/v1/chat.py` + `capabilities.py`；界面文案 `features/settings/ExtensionManager.tsx`、`SettingsWorkspace.tsx`、`features/chat/Message.tsx`、`ExtensionPicker.tsx` 与其测试；样式增量 `features/settings/styles/settings-extend.css`；文档 `API.md` / `PROJECT_GUIDE` / `ROUTES` / 本文件。

<a id="skill-inject-results"></a>

#### 5.7.1 本批结果（实跑）

- 工程检查：`npm run typecheck` 通过；`npm run lint`（`--max-warnings=0`）**0 警告**；`npm run test:unit` → **47 文件 / 367 例通过**（基线 46/353，净增 14）；`npm run build` 通过，`BUILD_ID = cnodHanXs1xNpzQww6yCO`；`apps/api` pytest → **191 例通过**（基线 181，净增 10）。
- 浏览器回归：`settings.spec.ts` + `replica-settings.spec.ts` **2 passed**；聊天组 8 个 spec **44 passed**。合计 46 例通过，**全量 168 未跑**（只跑与本批改动相关的 spec）。首轮 `replica-settings` 曾 1 failed——旧断言锁定了"保存模拟配置"按钮文案，本批按文案变更同步该断言并加注，另补内置技能载入的浏览器断言。
- **真实服务验证（DeepSeek Flash，本机 8000）**：A 决定性探针——同一问题下，不带技能无标记、带探针技能首行出现规定标记；B 产品级对比——同一提问下，不启用「教案规范」时缺 `核心素养目标 / 教学设计 / 练习与作业`，启用后九个栏目齐备并遵循"环节名称 · 时长""时长合计与总课时一致""教学反思待补充"。原始输出在 [real-service-output.txt](qa/SKILL-INJECT/real-service-output.txt)。
- 重建能力口径：`capabilities.skills` 由 `planned` 改为 `ready`（detail 写明仅提示词级、不执行工具）；`mcp` 保持 `planned` 并写明"不连接、不检测、不执行"。设置页 Skill 与 MCP 分区文案分别改为真实生效 / 未实现。

#### 5.7.2 语义变化（接手者必须知道）

1. **Skill 真的生效了**：此前设置里的技能只是本地标签；现在"已启用 + 说明正文非空"的技能会作为系统上下文随每轮问答发送。空说明的技能不发送，卡片上如实提示"本轮不会生效"。
2. **技能是提示词级，不是执行级**：不产生 `tool` 事件、不访问外部服务。`Message` 的技能/ MCP 来源说明已按此改写（MCP 那条改为"未实现：本轮没有任何工具调用或连接"）。
3. **自动生效，无逐轮选择器**：`ExtensionPicker` 仍未挂载到输入区，本批未新增任何输入区控件，`/chat` 视觉基准与既有断言不变。
4. **不扩 `ExtensionEntry` 结构**：技能注入只需既有 `name`/`content`；原评估中"第一批就扩学科/MCP 字段"的建议按最小必要收窄，不做预留字段。
5. **旧快照兼容**：缺 `content` 的旧轮次快照按原样读取，不迁移、不重置、不注入。

#### 5.7.3 边界与未做

- **不含 MCP**：无连接、无检测、无工具循环（后端 provider 层没有 tool 调用实现）；设置里的 MCP 条目只是本地登记。
- **不含 DeepTutor 式逐轮扩展选择器**；不含技能与 `deep_question` 等业务能力的绑定（能力层 `capabilityAvailableInReal` 仍只放行普通对话）。
- **内置技能内容未经教研评审**，是产品口径初稿（教案栏目对齐 `assets/templates/source/teacher-standard.docx`），需老师试用后迭代。
- 同一批观察：以 3000 tokens 请求教案时命中既有 **R-13**（推理耗尽预算、零正文 `EMPTY_RESPONSE`），提高到 16000 后正常；R-13 仍未关闭，不因本批改动。
- 未跑全量 e2e/动画矩阵、未在移动真机验证、未做独立 A1 验收。

<a id="h1-books-pipeline"></a>

### 5.8 上一实施批：H1-BOOKS-PIPELINE v2（书籍生成流水线与增量阅读闭环）

**状态：本批实现与本地验收完成，待交付审查（2026-09-20）。** 负责人：实施总控（本会话接手上任未收口工作）；独立验收 A1 只读。起点候选 `bf460ab`（接手前工作区改动快照见 §5.8.5，本批不提交、不还原）。完整任务卡、冻结契约（状态枚举/字段/仓储 API/执行器 API）、队长裁定、锚点与禁区清单在 [docs/qa/H1-BOOKS-PIPELINE/TASK-CARD.md](qa/H1-BOOKS-PIPELINE/TASK-CARD.md)，本节登记范围与边界，结果与语义变化见 §5.8.7–§5.8.9。

1. **需求（用户锁定）**：① 补齐 `draft/spine_ready/compiling/paused/ready/error/archived` 七态与页面/块的等待·生成中·完成·部分失败·失败状态，明确生产者、转移条件、持久化字段与恢复操作，区分局部块失败/页面失败/整轮失败/本地存储失败；② 可观察生成：新建→提案→确认大纲→逐章逐块生成，增量落库、阅读器可见已完成与未完成，活动条/阶段文案/章数/计时/展开详情/暂停横幅/正文提示对照固定参考，进度来自真实任务状态；③ 暂停与中断：用户暂停与**模拟**供应商连续失败暂停两类，均只在明确恢复后继续，刷新/选页不绕过暂停，对照参考 `maybe_resume_on_open` 仅对"compiling 且无活跃执行器"自动续跑；④ 失败与重试：单块重试、页面失败恢复、整页重生成，不暗中重建整本，部分失败如实显示；修复初次读取失败停在加载态；⑤ 数据与并发：旧数据兼容读取、损坏不覆盖、增量合并保护生成期间新增笔记/书签/进度、块身份稳定、作答版本关系、整书重建语义不变、事件绑定 bookId+runId+序号且重复/迟到不重复落库、同书单一执行者（双标签页不互相覆盖）、存储失败停止推进且不谎报已保存、生成进度与阅读进度分开、导出不伪装完整、课程 R-11 三态不回退。
2. **实现方式**：`books-store.ts` 扩状态机与持久化（唯一写入口 `applyRunEvent`）；新建 `services/book-generation.ts` 作为**可替换的显式模拟执行器**（增量事件 + AbortSignal + 确定性失败场景 + 每书租约），正常路径由事件逐块推进，不预先同步生成整本；`BooksRoute.tsx` 承载活动条/展开详情/暂停横幅/自动续跑/模拟场景设置；`PageReader.tsx` 承载块与页状态、失败重试、整页重生成、作答版本关系。不接真实 LLM，不新增第二套业务后端。
3. **文件归属**：I1＝`services/books-store.ts` + 新建 `services/book-generation.ts` + 两处单测；I2＝`features/books/BooksRoute.tsx` + 新建活动条/暂停横幅组件 + 新建 `features/books/styles/book-pipeline.css` + 组件测试；I3＝`features/books/PageReader.tsx` + 新建块失败组件 + 新建 `features/books/styles/book-reader-states.css` + `PageReader.test.tsx`；总控＝STATUS/三矩阵/必要决定、`tests/e2e/books-pipeline.spec.ts`（新建）、`books-courses.spec.ts` 异步语义改造、构建与 Git；A1＝只读独立验收。同一文件同一时段单一写入者。
4. **验收条件**：见任务卡 §7（正常链路、四类失败、暂停/恢复/中断/重试、数据兼容与并发、三视口与减少动画、模拟边界），必须运行 typecheck / lint(0 警告) / unit / build（队长重建记 BUILD_ID）/ e2e（既有 154 + 新增）。**不包含**：BookChatPanel、课程学习会话、真实 LLM/解析、真实 HealthBanner 数据、侧栏折叠、多用户权限、R-13、R-06 补测、14 类 block 全面重做、导航字体收口——这些范围不因本批通过而关闭。
5. **接手现场（§5.8.5）**：起点 HEAD `bf460ab`；`.zcode/agents/*.md`(3)、`apps/web/next-env.d.ts`、`apps/web/src/components/layout/workspace-shell.css` 为接手前改动，本批不提交、不还原、不清理；快照与校验值在 `_work/h1-books/handoff-snapshot/`（构建改写生成文件时按此恢复）。
6. **旧合同失效声明**：`books-store.test.ts`「确认提案→确认大纲完成模拟编译」与 e2e `books-courses.spec.ts` 第 2 例锁定"确认大纲即同步 ready"，本批以异步流水线取代，改为更强的异步状态断言，逐项在结果卡说明理由；不删测试、不放宽既有阈值、不保留第二条同步捷径。

<a id="h1-books-results"></a>

### 5.8.7 本批结果（实跑）

- 工程检查：`npm run typecheck` 通过；`npm run lint`（`--max-warnings=0`）**0 警告**；`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` → **46 文件 / 353 例通过**（基线 47 文件/344 中删去零断言探针 `zz-debug.test.ts`，本批净增 10 条）；`npm run build`（总控自跑）通过，`BUILD_ID = TPMei2ra-L9r31dqKSPpl`（迭代：r1 `hrsgX9VjAM3HhtDYpjgPj` → r2 `tqqP-RbOtTrgBVOXkRUET` → r3 修浮层裁切，见 §5.8.10）；`npm run test:e2e` → **168 例通过 / 0 失败**（既有 154 + 新增 `books-pipeline.spec.ts` 14 例，构建产物来自本批源码）。
- 独立验收 A1（只读，冻结指纹见 §5.8.10）：r1 **pass 32 / fail 0 / not_run 0**（含 4 项挑刺：无 run 记录书的整页重生成、笔记写入失败不谎报、provider 开关单独开启真暂停、interrupted 态恢复入口，全部成立）；A1 挑出的 `contentVersion` 生产路径从不写入已按建议修复 → r2 定向复验 **pass**（真实存储实测「作答 `blockVersion` == 块 `contentVersion`」）；r3（修活动条展开浮层被 46px 条裁切，台账 N10）定向复验记录见其报告。
- 视觉与动画（真实浏览器 msedge，三视口 1440×900 / 1920×1080 / 390×844）：浮层进场 `180ms cubic-bezier(0.16,1,0.3,1)`、呼吸文字 `1.8s`、reduce 下两项均被压制（`1e-05s`）、快速开关 0→1→0、展开中暂停后浮层仍可收起、活动条按钮焦点环 2px、390 页面级溢出 0。截图与量化证据见 [qa visual](qa/H1-BOOKS-PIPELINE/visual/evidence.json)。
- 证据索引：[批次 README](qa/H1-BOOKS-PIPELINE/README.md)、[首败与修复台账](qa/H1-BOOKS-PIPELINE/DEFECT-LEDGER.md)、[A1 报告](qa/H1-BOOKS-PIPELINE/A1-REPORT.md)、[冻结指纹](qa/H1-BOOKS-PIPELINE/FROZEN-CANDIDATE.json)。
- 未执行：`apps/api` 测试（本批零后端改动）、真实供应商链路、移动端硬件触摸、逐帧动画曲线（属 H6 总验收范围）。

### 5.8.8 语义变化（与旧实现不同的行为，接手者必须知道）

1. **「确认大纲」不再同步 ready**：`confirmSpine` 建骨架并写 run 检查点进入 `compiling`，由本地模拟执行器逐章逐块异步推进到 `ready`（旧同步断言已替换为更强的异步断言）。
2. **失败不再假完成**：仍有未完成页 → 书籍保持 `compiling`（无执行器即“已中断”，活动条显示「继续生成」）；本地写入失败 → `error` 并给「重试生成」。部分失败（partial 页）计入完成但卡片与导出如实标注。
3. **自动续跑时机收窄**：只在“打开/刷新书籍”或“他标签页租约失效”时自动接管一次；同一挂载内跑过执行器后不再自动重启——否则一次页失败后的“已中断”会被下一次轮询立刻自动接管，用户看不到中断态、失败原因与恢复入口。
4. **注入场景一次性**：块失败、整页失败、本地写入失败都是“首次失败、重试即成功”，不会在同一触发点无限失败；整页失败以页自身 `attempts` 为判据，刷新/续跑后不重复注入。
5. **UI 开关必须真的命中**：`'*first'` 通配在场景解析期展开为全书第一个块；「模拟供应商连续失败暂停」自身产生连续页失败直至阈值（此前单独开启时无任何效果）。
6. **归档书只读**：生成/重试/重新生成入口禁用并给出同一说明（不再出现“按钮可点但什么都没发生”）。
7. **块占位分两态**：`正在生成 X 块…`（真的在写，带旋转图标）与 `X 块等待生成…`（排队或当前没有执行器）。
8. **`contentVersion` 真实写入**：执行器按生成内容的确定性哈希写入块版本；作答版本关系由“永不触发”变为“内容变化则旧作答如实标记为旧版记录”（内容相同的重生成不误判为过期）。
9. **就绪书卡片状态徽标保持渲染**：视觉推广期曾改为“仅非 ready 渲染”，本批恢复为全状态渲染（既有 e2e 以卡片上的「可阅读」锁定就绪态，按“保留既有断言”处理；与参考的差异如实记录）。

### 5.8.9 数据兼容、恢复与边界

- 兼容：旧四态数据照常可读；缺 `status` 的页面/块按 `ready` 读取期派生、不写回；`run` 缺失表示无历史运行（演示书/旧就绪书的页/块修复会补一个只作写入容器的检查点，不改书籍状态与阅读进度）；损坏/结构非法/写拒仍走 `local-collection` 抛错路径，不当作空库、不覆盖、不谎报已保存。
- 恢复：`paused` 只能由用户显式恢复（刷新不自动续跑）；`compiling` 无执行器时按页状态续跑（不重复生成已完成页）；`error` 可续跑；双标签页靠租约保证单执行者。
- 边界：全部为本地模拟执行器与本地显式注入，**不接真实 LLM/解析**；本批通过不代表真实供应商能力、不代表书籍模块或全站完成。不包含：BookChatPanel、课程学习会话、真实 HealthBanner 数据（kb_drift/log_health）、侧栏折叠、多用户权限、R-13、R-06 补测、14 类 block 全面重做、导航字体收口。
- 保留风险（记录备查，非本批缺陷）：暂停/恢复/重试按钮忙态为固定 600ms 复位；活动条 UI 由 500ms 轮询刷新（事件落库与界面更新最大约 0.5s 延迟）；“缺 status 即 ready”是长期兼容约定，缺 status 但实际未完成的页会被按完成读取。

### 5.8.10 冻结候选

本批候选为工作树（未提交），父提交 `bf460ab`；15 个产品/测试文件的 SHA256 与 `BUILD_ID` 记于 [FROZEN-CANDIDATE.json](qa/H1-BOOKS-PIPELINE/FROZEN-CANDIDATE.json)（`revision` 字段记录 r1→r2→r3 三次冻结：r1 首轮 A1 pass 32/0/0；r2 采纳 A1 挑刺补 `contentVersion` 生产写入并复验通过；r3 修视觉取证发现的展开浮层裁切并复验）。每次冻结的验收结束后都复校指纹一致；验收后未再改动产品代码。

以下 §5.1–5.3 保留 B-R05-EXTEND v5 / R-05 收口的原始交付与边界记录，不因本批启动而改动。

### 5.9 上一实施批：B-R05-EXTEND v5（R-05 收尾批）

已于2026-09-19交付。实施 + 独立验收 pass，产品候选 `a9c28ea`，文档收口 `a27dd69`。负责人：外部Agent队长（实施总控）。Codex负责交付审查。

### 5.1 交付结果

1. **范围（用户锁定）**：组 A 阅读工作区（`P-reading-[workspaceId]`、`P-reading-sessions`、`P-reading-sessions-[sessionId]`）；组 B `/space` 四子页（`P-space-chat-history`、`P-space-questions`、`P-space-personas`、`P-space-cli-apps`）。
2. **组 A 视觉分工保护交互逻辑**：任务卡列出19条保护机制，包括 follow-bottom、onScroll `<90` 阈值、回到最新、会话切换恢复跟随、`syncSessionUrl`/popstate、turnId-sessionId 守卫、`finalizedTurnsRef` 幂等、READ-RETRY 放行、`abortsRef` 归属、`draftOwnerRef` 草稿、`handleScroll` 300ms 节流、拖拽轨/抽屉键盘可达。视觉增量为 className/修饰类/关闭钮/本地 dismissed 状态，`reading.css` 与 `reading-store` 零改动。**同批另有 §3 R-09-FLAKY 记录的 follow-bottom 产品修复，不能把整批描述成“交互逻辑零改动”。**
3. **组 B 铁律执行**：真实计数/筛选/搜索/批量/演示载入/来源回链（R-10）全部保留；`space.css` 只读；既有断言锚点（`搜索会话历史`/`会话名称`/`关闭提示`/`新分类名称`/`移动到分类`/`查看出处会话`/`已启用`/`已停用` 等）原样。
4. **共享层边界**：`globals.css`/`space.css`/`motion.css` 只读；增量全进新建 `features/reading/styles/reading-ws.css`（`.reading-ws-page` 作用域）与 `features/space/styles/space-sections.css`（`.space-sections-page` 作用域），只消费既有变量、零 `!important`、无 `@media print`、无 `prefers-reduced-motion` 覆盖（依赖全局层）。
5. **组 A 实装**：按钮反馈过渡（150ms + active scale，对照参考 `ReadingCompanion.tsx:331,351,370,383`）、材料 tab 长标题截断（修 E5 标为最高风险的 N1）+ 解析中 tab 旋转指示、错误横幅可关闭（`关闭伴生错误提示`/`关闭会话错误提示`，只隐藏视觉不改 error 数据、重试仍可用、新错误自动重显）、伴生栏与阅读头部形态 chip 化。
6. **组 B 实装**：卡片/列表/工具条视觉统一、会话与题库计数 chip + 刷新 spinner 态、题库 refreshing 变暗（对照参考 `transition-opacity + opacity-60`）、CLI 状态徽标、行头窄视口 wrap。
7. **R-09 真实缺陷修复**（本批最重要产出）：受控诊断确证双层机制并修复，详见 §3 R-09-FLAKY 与 [诊断证据](qa/B-R05-EXT5/A1-REPORT.md)。
8. **证据**：[qa B-R05-EXT5](qa/B-R05-EXT5/)（任务卡含队长裁定 §8、E5 差距清单 44 条 + 交互保护区 19 条 + `reading.css` 影响面 14 类、三视口前后 60 张 + 焦点图、A1 报告 25 张独立证据）。

### 5.2 验证与边界

- typecheck/lint（0 警告）/`--no-experimental-webstorage` unit 297（与基线一致）/build（**队长在候选上重建，BUILD_ID `eYs-YyFDf0XQJugH8zZcO`**）/e2e **154/154** 全过；api 未重跑（零后端改动，基线 181）。
- **独立验收 A1 判 pass 0 fail**：**R-09 五例 5/5**、**「R-09 滚动跟随」`--repeat-each=10` → 10/10**（队长另跑同参数 10/10；修复前同环境为 3/10 失败）、阅读 spec 17/17、`space-pages` 8/8、R-10 相关 `chat-source-links` 21/21 与 `chat-message-locate` 12/12、独立浏览器脚本 **55/55**（滚动保持/回到最新只滚伴生容器/会话历史与草稿/错误横幅关闭后新错误重显/tab ellipsis/焦点环/reduce 压制 1e-05s/390 双抽屉/space 四子页全交互/R-10 href 形态）。
- **A1 未执行项（如实记录）**：turn error 横幅的浏览器实测 not_run（本地模拟无法在 UI 稳定构造失败轮次；源码审查确认与 sessionError 横幅同一 dismiss 模式）；无凭证供应商真实调用 not_run（本批纯前端）。
- **队长裁定（任务卡 §8）**：`§8.2` 保留现状 11 类——参考伴生栏的完整聊天复用（等价于接入真实聊天服务）、滚动语义对齐参考 80px（当前 90px 双向已被 R-09 锁定）、会话 URL 历史降级（当前 push/popstate 超出参考且已验收）、角色卡 hover 显隐、CLI 搜索/详情/分页（依赖远程 catalog）、persona `read_only`、选区浮条改底部条、`dt-reader-flash` 跳转脉冲（登记后续可选）、`space.css` 断点调整、`reading.css` 中 4 个共用类的既有规则改动（`.reading-companion`/`.reading-msg`/`.reading-composer` 被 Whisper/Writing 隐式共用）。
- **过程教训（已记入）**：I2 曾用 `git stash` 量测改动前基线，6 秒窗口被队长巡检撞见并触发误报排查；已明确禁止在共享工作区用 stash 做基线对比（改用 `_work/` 备份副本或既有 before 截图）。
- 动画未逐帧采样曲线/中断（MOTION_MATRIX 条目保持「实现待验收」）；触摸真机、真实供应商不在本批范围。

### 5.3 R-05 收口范围与保留缺口

沿用2026-09-19外部总控的范围内关闭记录；本次只统一此前“可关闭/已关闭”的摘要用词，未增加产品验收。下表是已交付推广清单，各批独立验收与自检边界按 §4 证据记录，不等于每页全部状态均通过。

| 范围 | 批次 | 状态 |
| --- | --- | --- |
| 公共变量层（字体/圆角/阴影/间距单一来源） | B-R05-SPACE-VISUAL v1 | 已交付 |
| `/space` 首页 + `/space` 四子页（chat-history/questions/personas/cli-apps） | v1 + v5 | 已交付（v5 有 A1 pass） |
| 知识库列表/详情、笔记本列表/详情 | B-R05-EXTEND v1 | 已交付（A1 复验 pass 14/14） |
| 书籍列表/详情、课程列表/详情 | B-R05-EXTEND v2 | 已交付（A1 pass 0 fail） |
| 写作列表/编辑器、阅读库/材料库 | B-R05-EXTEND v3 | 已交付（A1 pass 0 fail 31 项） |
| 设置、教案工作台 | B-R05-EXTEND v4 | 已交付（A1 pass 33/0/4） |
| 阅读工作区三栏（含 sessions 子页） | B-R05-EXTEND v5 | 已交付（A1 pass 0 fail，R-09 五例 5/5 + 压测 10/10） |
| `/chat` 基准页与其他次要页（404/错误页壳） | 既有各批 | 基准页与壳验收已交付 |

**边界声明（关闭 R-05 不等于已完成全站）**：
1. `待实现` 模块（partners/agents/mastery/memory/账户/管理视图，共 22 项）**不属于 R-05 范围**——它们是尚未实现的新页面，实现时直接按 `/chat` 基准建设，不回溯计入 R-05。
2. 视觉状态为「部分验收」的页面（如 `P-chat-[sessionId]`、`P-knowledge-bases-[kbName]`）其**功能级全状态验收**仍属各自模块后续批，不由 R-05 关闭覆盖。
3. **动画精度**（逐帧曲线/中断/退出参数）不在 R-05 范围，由 H6 总验收统一补齐（MOTION_MATRIX 条目多为「实现待验收」）。
4. 三矩阵中 `P-` 条目的**功能状态与真实服务状态不受 R-05 关闭影响**。
5. 页面矩阵仍列 `P-books-pages-[pageId]` 视觉待验，Whisper 等未有独立完整验收的范围继续保留；不得从“既有模块页推广”推导这些条目已通过。

<a id="roadmap"></a>

## 6. 后续路线与推进规则

| 顺序/轨道 | 交付中心 | 出口 |
| --- | --- | --- |
| R-05 推广范围内已收口；**GLASS-POLISH v1 为当前批（§5.0）**；H1/H2 仍是建议路线 | 登记页面的视觉推广已交付（范围与未验项见 §5.3）。建议路线仍是业务闭环：H1 书籍课程（compiling/paused/error、流式生成、暂停恢复、书籍聊天、课程学习会话）或 H2 既有模块闭环（阅读媒体原视图与完整伴生过程、写作/Whisper、产物消费） | 先明确一个有界批次；逐状态视觉与数据/错误/取消/恢复同步验收 |
| T3 MCP 执行通道（本批之外，未授权） | 设置里 MCP 条目的真实语义：服务端连接管理（凭证走 SecretStore）、工具清单发现、tool 调用循环与流式 `tool` 事件、失败与取消 | 需要独立批次与任务卡；不得在只有本地登记时声称已连接或已执行 |
| H1书籍课程闭环 | compiling/paused/error、流式生成、暂停恢复、书籍聊天、课程学习会话，复用既有14类block | 状态链、保存/刷新、资源/产物引用与三视口 |
| H2既有模块闭环 | 阅读媒体原视图与完整伴生过程、写作/Whisper、学习空间及产物消费 | 原功能/数据不丢、来源正确、完整参考交互 |
| H3伙伴/智能体 | 列表/创建/详情/群组/渠道、任务过程/工具/产物/历史 | 创建→执行→结果→恢复，等待/失败/取消/重试齐全 |
| H4精通/记忆 | 路径/节点/反馈/阶段；记忆总览/冲突/图谱/L1-L3 | 精通新轮区别于普通ask_user，数据与跨页联动完整 |
| H5账户/完整设置 | 本地身份权限视图、工作空间/解析/网络/记忆/任务模型等 | 身份模拟准确标注，设置锚点/搜索/历史与业务联动 |
| T1真实服务独立轨道 | R-13、三协议供应商、复杂主聊天真实事件、解析/扩展等按授权批接入 | 不把模拟升级真实、不无界加预算、不因缺某供应商凭证停止其他独立任务 |
| T2自有规划轨道 | /papers、/question-bank、/templates与现有模块关系 | 单独明确范围，不擅自改53项分母或删入口 |
| H6/H7总验收交付 | 全站缺口/动画补漏与最终交接 | 三矩阵逐项证据；工程、视觉、真实/模拟、兼容与阻断均有结论 |

当前批之外的路线是后续计划，不是一次性授权实现全部模块。遇到实际数据丢失、凭证不一致、错误会话归属或假成功先修；普通审计补证不应无限取代可见产品交付。

## 7. 历史保留与接手方式

- [2026-09-15整理前完整STATUS](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)：保留原R-01~13首败、模型38条/旧授权任务卡、6.1~6.10全文、测试数差异、真实服务与.env事件。旧章节号引用解释为此快照，不能当新任务入口。
- 2026-09-18 B-R05-SPACE-VISUAL v1 由外部队长在 ZCode 会话实施：子代理环境不可用（思考档位缺失）按协作提案降级为队长串行实施+黑盒自查留证，文件归属/提交/Git 仍按任务卡执行。
- [旧团队提示词](archive/PROMPT_HISTORY.md#snapshot-collaboration-20260915)、[旧接手入口](archive/PROMPT_HISTORY.md#snapshot-next-session-20260915)仅供追溯；[归档清单](archive/MANIFEST.json)记录来源提交、原始与规范化SHA256。
- 模型D1–D16稳定决定仍在 [PROJECT_GUIDE](PROJECT_GUIDE.md)，API和ROUTES仍维护现行契约；不因模型批历史归档删除功能范围。
- 新Agent从 [NEXT_SESSION_START](replica/NEXT_SESSION_START.md) 与 [团队协作提示词](MULTI_AGENT_COLLABORATION_PROPOSAL.md#队长启动提示词) 开始，先核对 [当前批次](#current-task) 是否已交付。明确授权且未完成才实施；已交付时接手现状并按用户新任务推进，不重做MODEL-EXEC/P0或旧视觉批，不等待Codex代写已授权代码。
- 产品能力和历史状态均有局限，不以批次pass、代码行数、测试总数推算产品完成率。
