# 当前状态与实施主线

更新：2026-09-18。本文件是唯一进度、问题、任务和后续计划入口。长期目标与稳定决定见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，逐项范围见三矩阵，历史首败与批次全文见 [整理前完整快照](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)。

## 1. 目标与当前结论

**以智启课源品牌完成固定 DeepTutor 的产品前端、AI 交互与原有动画；全站以当前学习问答 `/chat` 为视觉基准，保留蓝色主题及原业务功能。整体尚未完成。**

当前主线是 **R-05 内容视觉统一**。首批 **B-R05-SPACE-VISUAL v1 已交付（2026-09-18）**：公共变量层（字体/圆角/阴影/间距单一来源，字体资源一份）+ `/space` 首页按 `/chat` 基准迁移，前后对照与全回归见 [批次证据](qa/space-r05-20260918/README.md)；同批关闭阅读 READ-RETRY/READ-END 两项（`a9ebcaa`）。**第二批 B-R05-EXTEND v1 已交付**（知识库/笔记本四页，A1 首轮 needs_revision → 修复后复验 pass 14/14）。**第三批 B-R05-EXTEND v2 已交付**（书籍/课程四页，A1 一次通过 pass 0 fail）。**第四批 B-R05-EXTEND v3 已交付**（写作/阅读库四页，A1 pass 0 fail 31 项）。**第五批 B-R05-EXTEND v4 已交付（2026-09-19）**：全站最后两个既有模块页——设置与教案——按同一变量层推广，独立验收 A1 **pass（33 pass / 0 fail / 4 not_run）**，含**模型区 mock 成功态全链路**与**教案导出（verifyDocx 全项）/草稿/损坏草稿不覆盖**复核，见 [批次证据](qa/B-R05-EXT4/A1-REPORT.md)。**R-05 至此仅剩「阅读工作区三栏 + `/space` 其余子页」**，可规划 v5 作为收尾批。

- 最近产品提交：视觉五批（见 §4 批次表最终 SHA）；阅读补测修复 `a9ebcaa`。新接手者必须重新核对 `git status --short`、`git log -5 --oneline`，不能把文档提交当产品验收候选。
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
| R-05 | **未关闭，当前主线** | 全站内容字体/标题/卡片等未统一；已交付公共基础 + `/space` 首页 + 知识库/笔记本四页 + 书籍/课程四页 + 写作/阅读库四页 + 设置/教案两页（B-R05-EXTEND v1~v4）；**仅剩阅读工作区三栏与 `/space` 其余子页**，可规划 v5 收尾，不能整项关闭 |
| R-06 | 壳缺失修复已关闭；恢复另有未验项 | 404壳及返回主页已有浏览器证据；错误页reset只有代码/构建证据，运行时仍not_run |
| R-07 / R-08 / R-12 | 模型批实现并有相关回归 | 受控推理字段、独立清除凭证、作用域文案已修；R-07字段支持不等于全协议真实推理验收 |
| R-09 | 已关闭已复现的A/B/C | `a1fa16e`：上滚不被拉回、已测跨会话轮次显示/收尾、push/pop导航。正文媒体与全部异常终态合同不因本批升级 |
| R-10 | 已关闭A/B两部分 | `a5bb39c`会话身份回链；`aeacea8`消息定位/失效会话不回落最近会话；真实保存按钮路径有e2e |
| R-11 | 已关闭 | `2308822`：课程目录损坏/读取被拒不崩页、不冒充空、不丢引用；失败目录不阻断其他来源 |
| R-13 | **未关闭，真实服务轨道** | 默认2048+推理样本零正文；off/2048有正文但length截断；off/8192指定样本stop。不能自动关推理、无界加预算或断言正式384000配置必然成功 |
| READ-RETRY | 已关闭（2026-09-18） | 受控首败证明错误态"重试"被 turn 非空挡住（run 仍 1 次），`a9ebcaa` 放行错误态重试、保留流式防重入；组件级替身回归+全量单测 |
| READ-END | 已关闭（2026-09-18） | 首败证明重复/迟到 end 落库 2 份；`a9ebcaa` finalizeTurn 按 turnId 幂等（finalizedTurnsRef），旧轮迟到 end 不重复落库/不复活取消标注/不清新轮；R-09 会话归属语义未变 |
| R-09-FLAKY | **观察中（2026-09-19 新记，未关闭）** | `tests/e2e/reading.spec.ts:425`「R-09 滚动跟随」用例有低频 flaky。B-R05-EXT4 v1 实测量化：全量 e2e 首跑 **153/154**（仅此例失败，报 `expect(await body.evaluate((el) => el.scrollTop)).toBeLessThan(60)` 超时）；单独复跑通过（1.1s）；`--repeat-each=6` 复现 **2/6**；撤回测试改动后全量复跑 **154/154 通过**。**失败点在"用户上滚"断言**：`expect.poll` 等到容器可滚动后执行 `mouse.wheel(0, -600)`，但该例在复现轮中轮询同样无法使 `scrollTop < 60`（10s 超时），说明不是单纯读取时序问题——可能是自动跟随在等待期间把容器拉到底部、或 wheel 未命中容器。**队长试加 `expect.poll` 韧性无效，已撤回（不保留无效改动掩盖失败）**。本批对阅读模块零改动（`reading.css`/`ReadingWorkspace.tsx`/`reading-store` 均无 diff），故该 flaky 与本批候选无关，判定为既有时序竞争。**处置**：保持观察、不改断言语义、不改产品逻辑；如后续批要修，需单独立卡做受控稳定性诊断（含是否需调整用例的滚动触发方式而非改断言）。 |

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

## 5. 当前任务：B-R05-EXTEND v4（已交付，2026-09-19）

**状态：已交付（实施 + 独立验收 pass 完成，检查点 `d54bd93` 见批次表）。负责人：外部Agent队长（实施总控）。Codex负责交付审查。**

### 5.1 交付结果

1. **范围（用户锁定）**：`P-settings`（`/settings`）与 `P-lesson-plans`（`/lesson-plans`）——**全站最后两个既有模块页**。**阅读工作区三栏与 `/space` 其余子页不在本批**。本批后 R-05 仅剩这两类，可规划 v5 作为收尾批。
2. **双禁区（本批最高风险，均零改动）**：
   - **设置页模型区 = contract-v1 禁区**：`features/model-settings/**` 与 `features/chat/**` diff 全空；38 条注册/6 backend/专用适配/受管认证/发现来源/推理控制/迁移逻辑未触碰；模型区 DOM 结构未动（5 处高危可访问名称锚点原样）。
   - **教案页 = 导出与草稿禁区**：`print.css`、`@page lesson-plan`、Word 映射与模板校验、`DraftRepository`/600ms 防抖/flush、`schemaVersion=1` 与本地键、`FillProvider`、`services/pagination.ts`、`--serif` 回退链（密集编辑区不强制 Lora）全部未动；未新开 `@media print`。
3. **共享层边界**：`globals.css`/`space.css`/`motion.css` 只读；`settings.css` 与 `lesson-plan.css` 既有规则**零修改**，全部增量进新建 `settings-extend.css`（`.settings-*`）与 `lesson-visual.css`（`.lesson-*`），只消费既有变量、零 `!important`、注释无提前闭合序列。
4. **关键实施约束（E4 风险清单落地）**：I1 未使用会穿透命中模型区内层同名类的 `.settings-workspace` 后代选择器（`.settings-form` 等在两文件双定义），也未改 `SettingsWorkspace` 的 import 顺序（避免翻转 `model-settings.css` 层叠改变模型区表单布局）。
5. **设置页**：索引导航加图标 + hover/current 双态 + 焦点环（保留 `aria-current="location"` 与 160ms 既有参数）、搜索框 focus 态 + 清除按钮（新名称「清除搜索」，全仓唯一）+ 无结果空态、ExtensionManager 卡片/开关视觉、外观与关于分区排版与 Toggle 轨道。
6. **教案页**：表单分区/type-chip/模板缩略卡视觉、预览工具栏 hover/disabled 态、toast 与 storage-alert 视觉（**文案与 role 未动**）、导航分段微调、导出菜单进场 `lesson-menu-in 180ms`（对齐 /chat `chat-home-popup` 基准）。
7. **顺带修复**：390 视口设置页起点既有的 2 处页面级 `<a>` 溢出（索引条带内预期横向滚动），在候选下实测归零。
8. **证据**：[qa B-R05-EXT4](qa/B-R05-EXT4/)（任务卡含队长裁定 §8、E4 差距清单 34 条 + 双风险清单各 10 条、三视口前后 36 张 + 焦点图、A1 报告 35 项与 26 个独立证据文件）。

### 5.2 验证与边界

- typecheck/lint（0 警告）/`--no-experimental-webstorage` unit 297（与基线一致）/build/e2e 154 全过；api 未重跑（零后端改动，基线 181）。
- **独立验收 pass（33 pass / 0 fail / 4 not_run）**：A1 对候选 `d54bd93` 判 pass——与 `after/` 六组截图逐像素 0 差异、**模型区 mock 成功态全链路**（5 高危锚点、`用于问答` 仅触发 1 次默认写入）、**教案 Word 导出产物通过 `verifyDocx` 全项**、**损坏草稿不覆盖**、草稿恢复与跨页返回、两新 CSS 剥离注释后 `!important` 与 `@media print` 均为 0、390 页面级溢出归零。
- **A1 未执行项（如实记录）**：真实供应商模型调用（无凭证，**mock 通过不等于真实供应商通过**）、真实后端下模型区、打印实际调起（按任务卡）、build/e2e 全量（归队长，已跑）。
- **A1 备查观察（非缺陷）**：导出菜单不响应 Escape 关闭，属既有行为（`ExportMenu.tsx` 本批零改动），backdrop 关闭正常。
- **队长裁定（任务卡 §8）**：`§8.2` 明确保留现状的 10 类项——参考式导航分组折叠、页级草稿工具栏、页级加载/错误横幅、Overview 状态条/就绪面板/语言开关/Tour（含静态占位，避免展示不存在的状态）、导航失败红点、窄视口分组下拉、模型区任何结构与 CSS 选择器改动、共享 `Modal`/`modal.css` 弹层动效、教案硬编码色替换、教案预览缩放过渡、`M-settings-nav` 参数改动。
- **R-09-FLAKY 观察（顺手项结论）**：全量首跑 153/154（仅阅读 R-09 滚动用例失败），单独复跑通过、`--repeat-each=6` 复现 2/6、撤回测试改动后全量 154/154。队长试加 `expect.poll` 韧性**无效并已撤回**（不保留无效改动掩盖失败）；失败点在「用户上滚」断言且轮询同样无法使其满足，疑为自动跟随回拉或 wheel 未命中容器。**本批对阅读模块零改动，判为既有时序竞争**，保持观察、不改断言与产品逻辑，详见 §3 R-09-FLAKY 行。
- 本批只关闭 R-05 中这两个页面切片；**不关闭 R-05 全站**（尚余阅读工作区三栏 + `/space` 其余子页）。动画未逐帧采样曲线/中断（MOTION_MATRIX 条目保持「实现待验收」）；触摸真机、真实供应商不在本批范围。

## 6. 后续路线与推进规则

| 顺序/轨道 | 交付中心 | 出口 |
| --- | --- | --- |
| R-05收尾 v5 + H1（下一批） | **R-05 仅剩「阅读工作区三栏（`/reading/[workspaceId]` 及 sessions 子页）+ `/space` 其余子页」**——阅读工作区有 R-09 五例与 READ-RETRY/READ-END 已验收交互，需单独任务卡；或转入 H1 书籍课程业务闭环（compiling/paused/error、流式生成、暂停恢复、书籍聊天、课程学习会话） | 每批有限页面，逐状态视觉与数据/错误/取消/恢复同步验收 |
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
