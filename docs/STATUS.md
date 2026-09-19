# 当前状态与实施主线

更新：2026-09-18。本文件是唯一进度、问题、任务和后续计划入口。长期目标与稳定决定见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，逐项范围见三矩阵，历史首败与批次全文见 [整理前完整快照](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)。

## 1. 目标与当前结论

**以智启课源品牌完成固定 DeepTutor 的产品前端、AI 交互与原有动画；全站以当前学习问答 `/chat` 为视觉基准，保留蓝色主题及原业务功能。整体尚未完成。**

当前主线是 **R-05 内容视觉统一**。**第六批（B-R05-EXTEND v5，2026-09-19）为 R-05 收尾批**：阅读工作区（`/reading/[workspaceId]` 含 sessions 子页）与 `/space` 四子页完成推广，并同批受控诊断并修复了 R-09 滚动跟随的真实缺陷（详见 §3 R-09-FLAKY）。独立验收 A1 **pass 0 fail**（R-09 五例 5/5、压测 10/10、55 项浏览器实测）。**至此 R-05 的既有模块页视觉统一已全部覆盖，可关闭 R-05**（关闭依据与边界见 §5.3）。

- 最近产品提交：视觉六批（见 §4 批次表最终 SHA）；阅读补测修复 `a9ebcaa`。新接手者必须重新核对 `git status --short`、`git log -5 --oneline`，不能把文档提交当产品验收候选。
- 工作树中 `.zcode/agents/*.md` 是用户自己的改动，批次全程不触碰、不纳入提交。
- **R-13 是模型真实长答未关闭项，不是整个项目唯一剩余问题。** R-05 推广、未实现模块、真实复杂能力和未验动画仍属于最终交付范围。
- 主聊天仅真实 FastAPI；阅读、知识库和写作等批准的显式模拟仍保留。执行模拟不能省略交互状态，模拟通过不能标为真实供应商通过。

## 2. 模块现状与保留边界

| 模块 | 已有实现与局部成果 | 仍未完成或未验 |
| --- | --- | --- |
| 公共壳 | `/chat` 单一主页；220/56px侧栏、跨页折叠；隐藏页父菜单；手机模态抽屉；404一层壳；聊天独立学习记录中栏 | 全站内容视觉R-05；错误页reset运行时未验；部分过渡曲线未验 |
| 教案 | 本地规则填充、编辑、草稿恢复、Word/PDF导出 | 不是AI生成；全页视觉仍待按聊天基准验收；冻结旧版及原Word不改 |
| 学习问答 | 三协议SSE、推理/正文及公式、本地会话、模型选择；生产mock残留已清；来源消息定位与失效会话空态已修 | ask_user、工具、附件解析及复杂业务真实执行通道未接；不能以存量组件当可发起功能 |
| 模型与供应商 | contract-v1、38条注册（36现行+2 legacy）、6 backend、专用适配/受管认证、发现来源、推理控制、v1→v2迁移与凭证补偿；卡片/详情/发现/参数/默认选择闭环 | 真实仅DeepSeek指定场景有证据，其余37条注册项无独立真实通过；Codex真实登录条件仍需核实具备；R-13未关闭；模型动画partial |
| 学习空间/笔记/题库 | 会话历史、角色、题库、笔记编辑、跨页保存；真实sessionId回链+可选messageId定位，旧数据缺身份不猜测；**/space 首页视觉已按聊天基准迁移（B-R05，Lora标题/图标块磁贴/计数单位）** | `/space` 功能级完整验收（弹窗/错误/长文案逐状态）待补；其他列表/详情视觉待推广；CLI只本地登记，无真实执行 |
| 知识库 | 登记→解析→索引显式模拟，进度/取消/重试/恢复；局部状态与数据保护已有证据 | 不读真实文件、不做向量检索/RAG；完整页面视觉及进度动画未验 |
| 书籍/课程 | 14类block、练习保存、笔记、大纲、资源、进度/导出；课程目录读取失败三态及隔离已修 | compiling/paused/error、流式生成/暂停恢复、书籍聊天和课程学习会话缺口；部分block仅模拟形态 |
| 阅读 | 材料/集合、批注/书签/进度、显式模拟伴生；R-09滚动/会话历史/已测跨会话归属已修；READ-RETRY/READ-END 已修（2026-09-18） | 媒体原视图、完整过程/来源仍待补验 |
| 写作/Whisper | 自动保存、显式模拟AI预览/应用/取消/重试、撤销/版本、双席位房间 | DOCX导入、完整参考差距、页面视觉和动画 |
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
| R-05 | **可关闭（2026-09-19，依据见 §5.3）** | 全站**既有模块页**内容视觉已统一：公共变量层 + `/space` 首页与四子页 + 知识库/笔记本四页 + 书籍/课程四页 + 写作/阅读库四页 + 设置/教案两页 + 阅读工作区三栏（B-R05-SPACE-VISUAL v1 与 B-R05-EXTEND v1~v5）。**边界**：`待实现` 模块（partners/agents/mastery/memory/账户/管理视图）不属于 R-05 范围，实现时按基准直接建设；动画精度（逐帧曲线/中断）随 H6 总验收补齐 |
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

### 4.1 真实服务与数据事件

- 真实供应商证据目前限DeepSeek指定场景，普通JSON接口与SSE已分别测量；其他注册项不得标真实通过。2026-09-12与09-13的模型、推理开关和预算不同，历史Pro8192失败不与后续off/8192成功混为同配置结果。
- B-MODEL-ACCEPT受控浏览器样本首个可见中文1172ms、KaTeX12处0错误，停止/重试/刷新有证据；不是所有模型延迟保证。
- 早期探针曾误写正式.env一行，随后实施者报告按行恢复；缺早期前置散列，不能追认当时完全未写。后续修为内存凭证副本并有前后不变断言。完整事件、当时MD5与来源保留在归档，不删除、不改成“从未写入”。
- 正式384000预算配置在相应API报告中为not_run，不依据它保证日常无零正文；本次不读写正式配置。

### 4.2 测试环境与本次文档批

根测试命令与启动方式见 [README](../README.md)。Node26单测按已验证配置运行：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run test:unit
```

原阅读批使用临时localstorage文件获得292/292，裸命令失败数量在报告中有不同口径；原文完整归档，不据此改写成产品回归。后续只读审查使用上面的既有参数292/292通过，不需要升级依赖。该结论不声称裸命令已通过。

本次 **DOC-FOCUS v1** 只整理现行文档、归档、链接与任务；不修改产品、测试实现、依赖、凭证或浏览器数据。已验证3份完整归档原文/散列、现行文档链接、矩阵ID与数量、D1–D16及R-01～13和后续路线完整性，`git diff --check`通过；[机器检查结果](qa/docs-focus-20260915/verification.json)随Git保存。独立只读内容复核通过，提出的两处阅读矩阵措辞已收窄并改成现行索引；另对照源码订正API旧删除顺序描述。产品测试本轮未重跑（纯文档变更），上面的292项为先前同日只读产品审查结果。

## 5. 当前任务：B-R05-EXTEND v5（R-05 收尾批，已交付 2026-09-19）

**状态：已交付（实施 + 独立验收 pass 完成，检查点 `a9c28ea` 见批次表）。负责人：外部Agent队长（实施总控）。Codex负责交付审查。**

### 5.1 交付结果

1. **范围（用户锁定）**：组 A 阅读工作区（`P-reading-[workspaceId]`、`P-reading-sessions`、`P-reading-sessions-[sessionId]`）；组 B `/space` 四子页（`P-space-chat-history`、`P-space-questions`、`P-space-personas`、`P-space-cli-apps`）。
2. **组 A 铁律执行「视觉层可改、交互逻辑区不动」**：**交互保护区 19 条机制零语义改动**——follow-bottom effect、onScroll `<90` 阈值、回到最新、会话切换恢复跟随、`syncSessionUrl`/popstate、turnId-sessionId 守卫、`finalizedTurnsRef` 幂等、READ-RETRY 放行、`abortsRef` 归属、`draftOwnerRef` 草稿、`handleScroll` 300ms 节流、拖拽轨/抽屉键盘可达；`reading.css` 与 `reading-store` 零改动；改动仅 className/修饰类/新增关闭钮/本地 dismissed 状态。
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

### 5.3 R-05 可否关闭：**可关闭**（依据如下）

**判断依据（既有模块页视觉统一清单，逐项有独立验收证据）**：

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

## 6. 后续路线与推进规则

| 顺序/轨道 | 交付中心 | 出口 |
| --- | --- | --- |
| **R-05 已关闭（2026-09-19）**，下一批转 H1/H2 | **既有模块页视觉统一已完成**（依据见 §5.3）。建议转入业务闭环轨道：H1 书籍课程（compiling/paused/error、流式生成、暂停恢复、书籍聊天、课程学习会话）或 H2 既有模块闭环（阅读媒体原视图与完整伴生过程、写作/Whisper、产物消费） | 每批有限页面，逐状态视觉与数据/错误/取消/恢复同步验收 |
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
- 新Agent从 [NEXT_SESSION_START](replica/NEXT_SESSION_START.md) 与 [团队协作提示词](MULTI_AGENT_COLLABORATION_PROPOSAL.md#队长启动提示词) 开始，执行本文件第5节；不重做MODEL-EXEC/P0，不等待Codex代写。
- 产品能力和历史状态均有局限，不以批次pass、代码行数、测试总数推算产品完成率。
