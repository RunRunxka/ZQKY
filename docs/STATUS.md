# 当前状态与实施主线

更新：2026-09-23（UX-PERF-CLOSEOUT v1：长推理流性能收口 + 学习问答模式菜单 + 学习记录与导航与图标 + 教案工作台布局 + 全站双语字体；RAG 仍为未接入，仅界面入口占位）。本文件是唯一进度、问题、任务和后续计划入口。长期目标与稳定决定见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，逐项范围见三矩阵，历史首败与批次全文见 [整理前完整快照](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)。

## 1. 目标与当前结论

**以智启课源品牌完成固定 DeepTutor 的产品前端、AI 交互与原有动画；全站以当前学习问答 `/chat` 为视觉基准，保留蓝色主题及原业务功能。整体尚未完成。**

**当前工作：UX-PERF-CLOSEOUT v1（8 节用户批次）已本地实施并完成限定范围验收（2026-09-23），待交付审查。** 本批交付：① 长推理流卡顿收口（可复现取证 → 最小优化 → 前后实测：50k 字推理帧间隔 p95 **166.7→5.6 ms**、>50 ms 帧 **215→0**、主线程脚本 **28.3→1.1 s**，原始文本逐字节保留、19 项正确性回归全通过）；② 模式菜单单层化并修复面板横向滚动（1440/1024 实测 `clientWidth=scrollWidth`），以同级「RAG 模式」取代「更多能力」（**未接入、不可选、行内标注**，不发请求不返回模拟结果）；③ 学习记录并入全站左侧导航（删除 236px 中栏与手机第二套弹窗）、书籍并入教材资料库（唯一高亮）、正式品牌 favicon；④ 教案工作台去面包屑 + 编辑区/教案配置/预览顺序与单一折叠按钮；⑤ 全站双语字体 token 层（导航与学习问答用界面衬线、其余正文黑体、代码与公式局部例外，含阻断自托管字体的回退实测）。证据见 [批次证据](qa/UX-PERF-CLOSEOUT-20260923/README.md) 与 [可达性审计](qa/UX-PERF-CLOSEOUT-20260923/REACHABILITY-AUDIT.md)。**RAG 仍未接入**：菜单出现「RAG 模式」不等于检索能力完成，`get_rag_adapter()` 恒定不可用、capability 仍 `planned`。

上一批 CHAT-CONTEXT-BUDGET v1（请求统一预算）与 RAG-I0-PREP v1（RAG 只读准备）记录保留在 §5.B：预算侧把「课程上下文 + 历史 + 当前问题」放进**同一预算**并与后端硬限制（200 条 / 32000 单条 / 120000 总长）对齐，当前问题逐字不裁剪、放不下时发送前明确提示并保留输入；RAG 侧未启动任何推理，只在宿主 `apps/api` 定义 adapter 契约（`get_rag_adapter()` 恒定不可用、无假实现、无路由、capability 仍 planned）。**书籍仍为本地模拟执行器；RAG 未接入；真实供应商未外呼、未验证凭证有效性；均不代表模块或全站完成。**

R-05 内容视觉统一是 H1 之前已交付的批次。第六批 B-R05-EXTEND v5（2026-09-19）覆盖阅读工作区和 `/space` 四子页，并修复 R-09 滚动竞争。历史独立验收 A1 pass 0 fail 保留，R-05 只在 §5.3 登记范围内关闭，不扩大为全站逐状态完成。H1-BOOKS-HARDEN v1 已于 2026-09-22 交付（见 §5.E）；RAG 接入只完成宿主侧契约准备（见 §5.B、§6.1），见 [当前批次与下一动作](#current-task)。

- 本次审查代码基准：`main@7a394ef`，开始工作区干净；最近主要业务实现为 `f31d39f`，之后产品差异为公共导航字体。本批（H1-BOOKS-HARDEN v1）起点为 `40491be`，现场核对分支/HEAD 后开工，未切换或合并 `feat/glass-theme`。`main` 是个人分支，默认集成分支是 `feat/glass-theme`，本报告不计入后者的主题工作。
- `.zcode/` 已退出 Git 跟踪；本机配置继续保留、不触碰。
- **R-13 是模型真实长答未关闭项，不是整个项目唯一剩余问题。** 逐状态视觉缺口、未实现模块、真实复杂能力和未验动画仍属于最终交付范围。
- 主聊天仅真实 FastAPI；阅读、知识库和写作等批准的显式模拟仍保留。执行模拟不能省略交互状态，模拟通过不能标为真实供应商通过。

## 2. 模块现状与保留边界

| 模块 | 已有实现与局部成果 | 仍未完成或未验 |
| --- | --- | --- |
| 公共壳 | `/chat` 单一主页；220/56px 侧栏、跨页折叠；隐藏页父菜单（支持传递上溯）；手机模态抽屉（Tab 圈定含输入框/链接，无当前项时焦点回落关闭入口）；404 一层壳；**学习记录并入侧栏可滚动区域（UX-PERF-CLOSEOUT v1）**；**字体 token 层：导航与学习问答用界面衬线、其余正文黑体（含阻断自托管字体的回退实测）**；品牌 `src/app/icon.svg` favicon | R-05 收口范围见 §5.3；错误页 reset 运行时未验；部分过渡曲线未验；真实硬件触摸未验 |
| 教案 | 本地规则填充、编辑、草稿恢复、Word/PDF 导出；R-05 v4 有界视觉推广及导出/草稿回归；**UX-PERF-CLOSEOUT v1：去面包屑改同级直接标题、顺序改为编辑区 → 可折叠教案配置 → 预览、只留一个折叠按钮（不卸载、状态不丢）、打印与导出回归** | 不是 AI 生成；逐状态视觉与动画按矩阵保留未验项；冻结旧版及原 Word 不改；平板展开配置时预览列偏窄（已保证控件不裁切） |
| 学习问答 | 三协议SSE、推理/正文及公式、本地会话、模型选择；生产mock残留已清；来源消息定位与失效会话空态已修；课程会话归属、聊天页课程上下文与轮次课程快照进入真实请求（H1-COURSE-SESSIONS v1）；请求统一预算与课程字段限幅（CHAT-CONTEXT-BUDGET v1）；**长推理流性能收口：活跃流轻量呈现 + 增量合并（可见更新上限 80 ms）+ 写盘快照（UX-PERF-CLOSEOUT v1，50k 字帧 p95 166.7→5.6 ms、>50 ms 帧 215→0、原始文本逐字节保留）**；**模式菜单单层化并修复横向滚动，同级「RAG 模式」占位（未接入、不可选、行内标注）**；**学习记录并入全站侧栏** | ask_user、工具、附件解析及复杂业务真实执行通道未接；不能以存量组件当可发起功能；真实供应商证据范围不因本批扩大；课程资源仍为登记引用；**RAG 未接入（`get_rag_adapter()` 恒定不可用、capability 仍 planned）** |
| 模型与供应商 | contract-v1、38条注册（36现行+2 legacy）、6 backend、专用适配/受管认证、发现来源、推理控制、v1→v2迁移与凭证补偿；卡片/详情/发现/参数/默认选择闭环 | 真实仅DeepSeek指定场景有证据，其余37条注册项无独立真实通过；Codex真实登录条件仍需核实具备；R-13未关闭；模型动画partial |
| 学习空间/笔记/题库 | 会话历史、角色、题库、笔记编辑、跨页保存；真实sessionId回链+可选messageId定位，旧数据缺身份不猜测；`/space` 首页、四子页与笔记本列表/详情已列入视觉推广批 | `/space` 功能级完整验收（弹窗/错误/长文案逐状态）待补；笔记编辑器等参考差距按矩阵保留；CLI只本地登记，无真实执行 |
| 知识库 | 登记→解析→索引显式模拟，进度/取消/重试/恢复；局部状态与数据保护已有证据；R-05 v1 列表/详情视觉有界验收 | 不读真实文件、不做向量检索/RAG；全部分区/弹窗逐状态视觉及进度动画仍未完整验收 |
| 书籍/课程 | 14 类 block、练习保存、笔记、大纲、资源、进度/导出；**导航「书籍」并入教材资料库（路由/数据/业务不变，桌面唯一高亮教材资料库，教材资料库页新增书籍/课程入口）**；课程目录读取失败三态及隔离已修；**H1-BOOKS-PIPELINE v2 起书籍生成可观察/可暂停/可中断/可重试**（七态状态机 + 本地模拟执行器 + 活动条/展开详情/暂停横幅/块页重试/增量阅读/未完成导出标注）；集合写经互斥事务与提交结果契约（COMMIT-SAFETY v1 + FOLLOWUP v1 前置补丁）；**H1-COURSE-SESSIONS v1 起课程学习会话闭环可用**（课程页会话区 + 聊天页归属/返回课程 + 轮次课程快照） | 书籍生成仍为本地模拟（无真实 LLM/解析与真实供应商证据）；BookChatPanel、课程学习智能体工具与自动学习规划缺口；部分block仅模拟形态；逐帧动画与硬件触摸未验 |
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
| R-14 | **未关闭，跨批（书籍批次外观/时序）** | 2026-09-23 登记：`tests/e2e/books-commit-safety.spec.ts:238`「双标签页并发写不同书」在 `--repeat-each=3` 下 1/3 失败（队长与 A1 各自复现）：两个标签页同时生成两本书（同一集合）时集合写锁竞争，两次全量回归通过、加压后其中一次等待 `生成活动条消失`（120s）超时；失败快照显示书处于**「生成已中断（无执行器在跑）」+「继续生成」**的既有如实状态，内容与笔记未丢（快照可见正文与阅读进度）。判为**测试假设与既定行为不一致**（冲突预算耗尽即如实中断是本批既有设计），非数据丢失；本批不修（不属预算批范围），待书籍批次定性：或在测试内接受「已中断」再走继续生成，或调宽等待。 **UX-PERF-CLOSEOUT v1 复现更新（2026-09-23，候选 `ZkSw3NYEUtNUBATU0sde5`）**：全量 e2e 中再次失败一次（132s）；同文件 `--repeat-each=2` 第 1 轮失败、第 2 轮通过；隔离 `-g "双标签页并发写不同书" --repeat-each=3` **3/3 通过** → 间歇性、随负载出现。失败快照本次逐项取证：`生成已中断（无执行器在跑）`+`继续生成` 同时存在，**笔记内容与阅读进度完好**（摘录见 [R-14 证据](qa/UX-PERF-CLOSEOUT-20260923/r14/REPRO-EVIDENCE.md)）。本批**未修改该用例、未删除、未笼统加等待**，定性仍为「测试假设与既定行为不一致」，处置留待下一批（见 §6 路线第 2 步）。 |
| READ-RETRY | 已关闭（2026-09-18） | 受控首败证明错误态"重试"被 turn 非空挡住（run 仍 1 次），`a9ebcaa` 放行错误态重试、保留流式防重入；组件级替身回归+全量单测 |
| READ-END | 已关闭（2026-09-18） | 首败证明重复/迟到 end 落库 2 份；`a9ebcaa` finalizeTurn 按 turnId 幂等（finalizedTurnsRef），旧轮迟到 end 不重复落库/不复活取消标注/不清新轮；R-09 会话归属语义未变 |
| R-09-FLAKY | **已关闭（2026-09-19，含产品修复）** | 受控诊断确证**双层机制**：(a) CDP 层——`mouse.wheel` 派发与 `evaluate` 读值竞争（24 次决定性实验、wheel 到达延迟实测 20-30ms）；(b) **产品层真实缺陷**——流式拉底产生的 `scroll` 事件因 `dist<90` 把 `followBottom` 重置回 true，用户上滚被永久吞掉（现场探针抓到完整序列：上滚成功 top=0 → 5ms 后拉回 179 → 最终贴底 212）。修复（`a9c28ea`）：`userScrolledAwayRef` 同步记录用户意图、堵住 `setState` 提交延迟窗口；`programmaticScrollRef` 区分程序化拉底副作用与用户滚动；spec 侧仅一处 `expect`→`expect.poll`（**阈值 `<60` 与语义未变**）。验证：R-09 五例 5/5、`--repeat-each=10` 队长复测 **10/10**（修复前同环境 3/10 失败）、A1 独立复现 **10/10**、阅读 spec 17/17、全量 154/154。**队长注意**：v4 批曾试过"仅加 poll"并失败撤回——那次失败正是因为 poll 只吸收 CDP 层、会暴露产品层的 212 贴底值，此结论已归档 |

阅读两项（READ-RETRY/READ-END）已于 2026-09-18 受控补测并有界修复关闭。2026-09-15方向审查的事实已整理于本表；完整临时报告 `_work/review-direction-6d98718/REVIEW.md` 仅是补充，交接不依赖其存在。

其他仍需保留的边界：全站视觉/动画尚未通过；硬件触摸及部分快速中断未验；真实供应商/真实OAuth缺条件的项保持not_run；主聊天复杂能力缺真实通道；模型预算样本只证明对应模型/参数/问题。

### 3.1 main 审查（2026-09-22）与修复结果

候选 `7a394ef`；[源码依据、隔离复现与命令](qa/main-review-20260922/README.md)。常规检查：typecheck/lint 通过，unit **353/353**，API **181/181**（1 条第三方弃用警告）。另外 3 个探针均复现缺陷，**不计为产品通过**。本轮 build/e2e/视觉/真实供应商/RAG 模型与质量评测 not_run；原 168 项 e2e 只作历史证据。

**六项已于 H1-BOOKS-HARDEN v1（2026-09-22）修复**，修复内容、首败证据与断言反转回归见 [批次台账](qa/H1-BOOKS-HARDEN/DEFECT-LEDGER.md) 与 [§5.E](#harden-results)：

| ID | 原未修复项 | 修复后状态 | 证据层级 |
| --- | --- | --- | --- |
| M22-01 | 读取失败或删除后执行器退出但注册表/心跳/租约未释放，恢复被旧句柄阻塞 | 已修（统一收尾 + 删除/读失败/失权区分 + 恢复入口） | 原探针断言反转（租约已空、执行器已收尾）+ 单测 + e2e 删除收尾/读失败面板 |
| M22-02 | 页/块修复不返回 Promise，且旧修复任务等待后借用新 runId 写入 | 已修（Promise<RepairResult> + 启动冻结 runId + 每次写入核对 + 互斥/取消） | 原探针断言反转（探针第 3 条在「返回值应为 undefined」处即失败终止，不会执行到 runId 断言）+ **新增单测**（`replacement-run` 下无块变 ready、结果 runId 为冻结身份、同目标复用/取代/取消/写失败、修复期间归档不报 completed，共 7 例）+ e2e 连点互斥 |
| M22-03 | 租约非原子获取、无失权停止，多标签同时启动存在竞争；共享集合读改写可能覆盖他书 | 已修（写后读回校验 + 每步/心跳归属校验 + 失权即停）；**共享集合写一致性由 H1-BOOKS-COMMIT-SAFETY v1 补充修复**（见下） | 真实浏览器双标签页接管→失权停止/不续租/释放后恢复；单测共享集合 4 例 |
| M22-04 | 首次目录读取失败被书籍详情加载分支遮住，缺错误/重试 | 已修（错误面板 + 重试读取 + 成功清旧错误） | 组件测试 + 真实浏览器注入读取失败（含 390 视口横向滚动差 ≤1px） |
| M22-05 | 最终完成落库异常被吞掉，内存仍 finished | 已修（落 kind storage 失败 + 「重试生成」，绝不假报完成；一次性注入开关） | 单测（状态 error、重试后 ready）+ 真实浏览器（卡片非「可阅读」→重试完成） |
| M22-06 | 编辑笔记时左右方向键触发全局翻页 | 已修（输入框/可编辑/组合输入/修饰键全部排除） | 组件测试（输入框、contenteditable、isComposing、修饰键、已消费事件）+ 真实浏览器两组键盘 |

**M22-03 的补充修复（H1-BOOKS-COMMIT-SAFETY v1，2026-09-22）**：本批用脱敏探针复现确认，HARDEN v1 采用的"写标记 + 有界重放"只能**写前检测**冲突——另一写入者在"检测之后、写入之前"提交时，其已保存内容仍会被旧整表覆盖（丢失更新，可控交错即可复现，不依赖"同一毫秒"）；同时确认冲突预算耗尽后会返回内存候选值，使 `createBook` 返回幻影书籍。修复：集合写改为**互斥锁内的事务读改写**（生产走原生 Web Locks；jsdom 单测走测试注入的 in-process 互斥——本批当时的 localStorage 回退锁已在 BOOKS-CS-FOLLOWUP v1 整体删除，无互斥即 `unsupported`、不降级写），并引入 `CommitResult` 提交结果契约（非 `committed` 一律不返回值）。证据见 [CS 批次台账](qa/H1-BOOKS-COMMIT-SAFETY/DEFECT-LEDGER.md)、[真实双标签页 e2e](qa/H1-BOOKS-COMMIT-SAFETY/README.md)。**HARDEN v1 的租约归属/失权停止/读取三态/统一收尾语义全部保留**；“不宣称强原子性”的边界同样保留（口径已按 BOOKS-CS-FOLLOWUP v1 任务卡 §6 订正：写后读回**不**必然发现所有绕过协议的写入，详见 §5.D）。

边界：修复均为本地模拟执行器范围内的行为纠正；真实供应商、真实 LLM/解析、RAG 接入与动画精度不因本批改变。M22-03 的"同一毫秒并发写入"窗口无法用测试确定性构造，实现为写后读回 + 有界重放并如实标注（见 [批次 README §6](qa/H1-BOOKS-HARDEN/README.md)）。

原复刻目标当前估计 **48/100，区间约 45–51**，是排期判断而非验收结论；权重与依据见审查记录。22 个未实现页面、课程学习会话/书内聊天、R-13、真实复杂能力及动画缺口仍保留。RAG 是新增独立目标，未接入宿主，不能将其外部项目成果算进宿主完成度。

## 4. 已完成批次与证据索引

以下是**指定候选的历史验证**，不是本次文档整理重新运行的全部测试。实现者自检与独立验收范围以证据为准，不因提交或测试数增加扩大模块完成度。

| 批次 | 实现 / 收口提交 | 关键验证与独立范围 | 证据 |
| --- | --- | --- | --- |
| UX-PERF-CLOSEOUT v1（长推理流性能 + 模式菜单 + 学习记录与导航与图标 + 教案布局 + 双语字体） | 见 §5.A（起点 `3dcace8`；候选 `ZkSw3NYEUtNUBATU0sde5`，最终 SHA 见结果卡） | typecheck/lint(0 警告)/unit **52 文件 440 例**/build **`ZkSw3NYEUtNUBATU0sde5`**/e2e 全量 **199 通过 1 失败（唯一为既有间歇 R-14，已独立复现定性）**/后端 **217 passed**；性能前后实测（50k 帧 p95 166.7→5.6 ms、>50 ms 帧 215→0、脚本 28.3→1.1 s）+ 19/19 正确性回归 + 菜单三视口 `clientWidth=scrollWidth` + 导航与 favicon 独立取证 + 字体三视口 6 路由（含阻断自托管字体）；全量回归中还定位并修复了一个**真实产品缺陷**（打印媒体下公共壳栅格错位） | [批次证据](qa/UX-PERF-CLOSEOUT-20260923/README.md)、[任务卡](qa/UX-PERF-CLOSEOUT-20260923/TASK-CARD.md)、[可达性审计](qa/UX-PERF-CLOSEOUT-20260923/REACHABILITY-AUDIT.md)、[R-14 证据](qa/UX-PERF-CLOSEOUT-20260923/r14/REPRO-EVIDENCE.md)、[冻结记录](qa/UX-PERF-CLOSEOUT-20260923/FROZEN-CANDIDATE.json)；**真实供应商与真实 RAG 均 not_run** |
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
| H1-BOOKS-HARDEN v1（main 审查 M22-01～06 修复） | `40491be` → 本批提交（见批次 README） | typecheck/lint(0警告)/unit 48文件381例/build(BUILD_ID `cTTq7b-No7rnD-HNmoyQc`)/e2e **174 通过 0 失败**全过；3 个审查探针未修改、修复后 3/3 按预期失败（断言反转证据）；独立验收 A1 只读复验见批次报告 | [批次证据](qa/H1-BOOKS-HARDEN/README.md)、[首败台账](qa/H1-BOOKS-HARDEN/DEFECT-LEDGER.md)、[探针反转](qa/H1-BOOKS-HARDEN/probe-reversal/README.md)；**全部为本地模拟执行器与本地注入，不含真实 LLM/解析**；api 未重跑（零后端改动，基线181） |
| H1-BOOKS-COMMIT-SAFETY v1（书籍保存一致性） | `fedfa09` → 本批提交（见批次 README） | typecheck/lint(0警告)/unit **48 文件 389 例**（上一批 48/381，+8 例）/**build `AtxBYXEc_99FFQ8cGCtvu`**/e2e **178 通过 0 失败 0 flaky**（既有 174 + 新增 4 例真实双标签页）全过；原缺陷探针 2/2 按预期失败（缺陷假设不再成立）；独立验收 A1 r1 **可交付（条件通过）**，交付前项已处置、F5–F8 登记为已知边界 | [批次证据](qa/H1-BOOKS-COMMIT-SAFETY/README.md)、[首败与写入口盘点](qa/H1-BOOKS-COMMIT-SAFETY/DEFECT-LEDGER.md)、[脱敏探针](qa/H1-BOOKS-COMMIT-SAFETY/probe-reversal/README.md)、[A1 报告](qa/H1-BOOKS-COMMIT-SAFETY/A1-REPORT.md)；**全部为本地模拟执行器与本地存储，不含真实 LLM/解析**；api 未重跑（零后端改动，基线 181） |
| H1-COURSE-SESSIONS v1（课程学习会话闭环） | `d2638f2` → **`701d391`**（r2 交付候选，tree `d600f77c…`；r1 `8104654` 经 A1 r1 判需修订后关闭 F1/F2） | typecheck/lint(0警告)/unit **51 文件 416 例**/build **`93TKwQeZ9Av2qkSOC_8aR`**/e2e 全量回归 **191 passed / 0 failed / 0 flaky**（`course-sessions.spec.ts` 11 例：两课程互不串位、报文断言、写入失败可重试、跨任务二次点击不重复、列表读取失败可重试、流式中切换不污染、三视口/键盘/减少动画）；后端 `npm run test:api -- tests/test_chat_stream_api.py` **9 passed**（system 课程上下文经 FastAPI 逐条转发给 provider） | [批次证据](qa/H1-COURSE-SESSIONS/README.md)、[任务卡](qa/H1-COURSE-SESSIONS/TASK-CARD.md)、独立验收 [A1 r1 需修订](qa/H1-COURSE-SESSIONS/A1-REPORT-01.md) → [A1 r2 可交付](qa/H1-COURSE-SESSIONS/A1-REPORT-02.md)；**本轮未发起真实外呼、未验证凭证有效性**（not_run）；零后端产品代码改动 |
| CHAT-CONTEXT-BUDGET v1（请求统一预算） | `b16a825` → **`a9968cd`**（tree `60d64f33…`） | typecheck/lint(0警告)/unit **52 文件 436 例**/build **`dm5NJM2F0N_z9lp13FK0s`**（r3）/定向 e2e **15/15**；全量 e2e r1/r2 三次 **195/0/0**、r3 一次 **194/1**（唯一失败为跨批间歇 **R-14**）；冻结探针反转入 Git（原探针 2/2 按预期失败：D1 208 字、D2 1990≤2000；产品路径反转探针 3/3 通过） | [批次证据](qa/CHAT-CONTEXT-BUDGET/README.md)、[FROZEN](qa/CHAT-CONTEXT-BUDGET/FROZEN-CANDIDATE.json)；**数字均为字符估算，不宣称精确 token**；真实供应商未外呼（not_run） |
| RAG-I0-PREP v1（宿主侧契约 + 只读核对） | `a9968cd` → **`13a93ae`**（tree `a067b487…`） | 宿主 API 全量 **217 passed**（含新增 35 例合成数据契约测试）；RAG 仓库全程只读、HEAD/工作区前后对照留证 | [RAG-I0 报告](qa/RAG-I0-PREP/README.md)、[FROZEN](qa/RAG-I0-PREP/FROZEN-CANDIDATE.json)；**上游未启动模型/未重建索引/未跑评测；质量结论 not_run；结论=宿主侧准备完成、上游存在具体缺口（G1–G12）** |
| BOOKS-CS-FOLLOWUP v1（书籍前置补丁，单独提交/单独验收） | `d2638f2` → `a45b011` | typecheck/lint(0警告)/unit **49 文件 403 例**/build **`YhmHpWDKx-EgSf1pGHkZh`**/书籍 e2e **26 例通过**；F3/F5–F8 逐条处置并补回归（缺 Web Locks 不降级、控制操作按提交结果分支、修复任务收尾、启动重入去重、冲突预算重试） | [批次证据](qa/BOOKS-CS-FOLLOWUP/README.md)、[A1 报告](qa/BOOKS-CS-FOLLOWUP/A1-REPORT.md)（独立验收：代码与测试可交付，W1/W2 文档卡口已关闭）；**全部为本地模拟执行器与本地存储** |

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

<a id="commit-safety-results"></a>

<a id="chat-budget-results"></a>
<a id="ux-perf-closeout-results"></a>
### 5.A 本批实施：UX-PERF-CLOSEOUT v1（长推理流性能 + 模式菜单 + 学习记录与导航与图标 + 教案布局 + 双语字体），2026-09-23 本地实施与限定范围验收，待交付审查

**目标（用户锁定，八节）**：① 先对「模型思考过程较长时流式输出使界面与动画卡顿」做**可复现取证**再改实现，不得把静态推断写成已测根因；② 修复 `/chat` 模式菜单的横向滚动与左右滑动，并彻底移除「更多能力」入口/飞出层及其专属前端状态、目录项、配置表单、样式与已失效测试，在同级位置以「RAG 模式」占位（明确标注未接入，不发送到普通聊天冒充、不返回模拟检索结果）；③ 学习记录并入全站左侧导航（不再占独立中间列）、书籍并入教材资料库、增加正式品牌 favicon；④ 教案工作台去掉面包屑、改为编辑区 → 可折叠「教案配置」→ 预览且只留一个折叠按钮；⑤ 建立有名称与用途的双语字体 token 并清理全站硬编码字体；⑥ 文档整理与后续计划；⑦ 组织与交付门槛（任务卡、隔离资源、独立验收、小粒度提交）。

1. **P0 复现的缺陷（真实浏览器 + 受控上游）**：50k 字推理（30.9 s 流）帧间隔 p95 **166.7 ms**（约 6 fps）、最大 316.7 ms，**215 帧 > 50 ms、112 帧 > 100 ms**，主线程脚本 **28.3 s**，推理容器 DOM 更新 10 455 次，流式期间一次按键最慢 **71.7 ms**，堆峰值 102 MB。根因（按证据排序）：每个增量都对增长中的完整推理文本重跑 Markdown/数学/高亮解析；每个增量提交一次 UI 且重建会话列表；`flush()` 的 `while (dirty.size)` 在持续增量下把新脏数据不断接进同一轮循环（一次 50k 轮写盘 177～184 次 / 3.6～4.1 MB）；推理容器每次提交做同步布局读写。`ThinkingOrb` 成本单独测量（终态后 3 s 空闲窗脚本 126～134 ms、减少动画 7～8 ms）→ **不是**热点，未做任何删除或降级。
2. **最小优化**：① 活跃流与折叠未展开期间推理正文改为轻量纯文本，仅在「已结束且正在看」时一次性完成 Markdown/KaTeX；② 文本/推理增量「前缘立即 + 尾部合并」，**可见更新时延上限 80 ms**，按原顺序折叠，任何非文本事件与终止/停止/断流/切会话/落盘前先提交缓冲区；③ 滚动写入按帧合并且仅在跟随最新时执行；④ 流式期间 `flush()` 一轮只保存进入时脏快照，无活动轮次时仍循环到清空。
3. **前后实测（同一受控文本/探针/隔离浏览器）**：50k 推理帧 p95 **166.7→5.6 ms**、>50 ms 帧 **215→0**、>100 ms **112→0**、主线程脚本 **28.3→1.1 s**、DOM 更新 **10455→383**、首个可见增量 **69→43 ms**、堆峰值 **102.4→11.4 MB**；20k + 长历史帧 p95 **127.8→5.6 ms**、脚本 **10.8→0.7 s**、按键最慢 **71.7→2.0 ms**；5k/手机/平板/减少动画四场景 0 帧 > 50 ms。**唯一变差项是布局总量**（426→2302 ms，单文本节点每次提交整体换行），合入依据是帧间隔与长任务，不是单项布局总量。
4. **正确性回归 19/19**：流中 8 次采样均为原文前缀；**持久化推理原文与上游逐字节全等**；完成/折叠/展开公式（KaTeX 120 处、`katex-display` 22/22、0 错误）；停止（不再更新、已收内容落库、`stopped/client-stop`）；手动上滚不被拉回；受控断流落错误态并保留内容且有重试；流式中切会话原会话内容已落库；刷新后原文完整恢复且公式正确；减少动画过渡被压制。
5. **模式菜单**：首败实测 `.chat-cap-panel` 在 1440/1024 `clientWidth=278 / scrollWidth=514` 且 `scrollLeft` 可 0→60（横向滚动条 + 可左右滑动，溢出源是 `left: calc(100% + 6px)` 的飞出层）；修复后三视口 `clientWidth = scrollWidth`、`scrollLeft` 恒 0、页面级溢出 0；Escape 关闭后焦点回到触发器。「更多能力」与三项专属能力整体移除（可达性清单见 [审计](qa/UX-PERF-CLOSEOUT-20260923/REACHABILITY-AUDIT.md)），同级新增「RAG 模式」：**不可选**、行内徽标「未接入 · 规划中」实测未被裁切、`submit()` 另有专门阻断文案；**不发请求、不返回模拟检索结果**。
6. **学习记录与导航与图标**：学习记录并入全站侧栏可滚动区域（收起为 56px 图标栏时隐藏），独立中栏与其折叠/打开按钮、手机第二套弹窗删除；手机随同一导航抽屉（Tab 圈定已扩到输入框/链接，无当前项时焦点回落关闭入口）；书籍并入教材资料库（`/books`、`/books/[...]`、`/courses` 路由与数据不变，桌面唯一高亮教材资料库，手机抽屉仍有书籍/课程，教材资料库页新增可达入口）；新增 `src/app/icon.svg` + `metadata.icons`，`/icon.svg` 实测 `200 image/svg+xml`、刷新后 href 稳定。
7. **教案工作台**：面包屑改为同级直接标题（计算样式与 `/co-writer`、`/reading` 一致）；顺序改为编辑区 → 可折叠「教案配置」→ 预览；只保留编辑区顶部一个折叠按钮（`aria-expanded`/`aria-controls` 与状态一致），折叠只切 class 不卸载；打印/导出回归通过。
8. **字体**：token 层（`--font-ui` / `--font-display` / `--font-ui-serif` / `--font-document` / `--font-mono`，`--serif` 为兼容别名）；全站 CSS 具体字体名只剩 token 定义；左侧导航与学习问答用界面衬线、其余正文黑体、代码与公式局部例外；1440/1920/390 × 6 路由实测字体族一致、页面级溢出 0；**阻断自托管字体**后请求 0 条、中文回退系统宋体、页面级溢出仍为 0、按钮无文本裁切。
9. **实跑与边界**：见本节第 10 条（工程检查与 e2e）。**未执行**：真实供应商外呼（not_run）、真实 RAG（not_run）、移动端硬件触摸（not_run）、逐帧动画曲线（属 H6）。**RAG 仍为未接入**：`get_rag_adapter()` 恒定不可用、capability 仍 `planned`，界面出现「RAG 模式」**不等于**检索能力完成；`F:\ZQKY_RAG` 全程只读、未启动、未评测。探针限制：`longtask` 观察器在本机 msedge 无输出，改用帧间隔分布 + CDP 主线程时长为等价证据；受控上游最初因 `connection: keep-alive` 被代理整块缓冲，该轮数据作废并单独归档（不计入任何结论）。
10. **实跑结果（候选 `ZkSw3NYEUtNUBATU0sde5`）**：`npm run typecheck` 通过；`npm run lint`（`--max-warnings=0`）**0 警告**；`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` → **52 文件 / 440 例通过**；`npm run build` 通过（`BUILD_ID = ZkSw3NYEUtNUBATU0sde5`）；`npx playwright test` → **199 通过 / 1 失败**，唯一失败为跨批既有间歇 **R-14**（`books-commit-safety.spec.ts:238`，本轮独立复现并定性，见 §3 台账与 [R-14 证据](qa/UX-PERF-CLOSEOUT-20260923/r14/REPRO-EVIDENCE.md)：`--repeat-each=2` 1 失败 1 通过、隔离 `-g ... --repeat-each=3` 3/3 通过；失败快照为既有的「生成已中断 + 继续生成」**如实状态、笔记与进度完好**，未修改/未删除该用例、未笼统加等待）；后端 `npm run test:api` → **217 passed**（零后端改动，沿用基线）。全量回归中暴露并修复的**真实产品缺陷**（打印媒体下公共壳栅格错位导致内容区 0 高）与两处断言写法修正见 [批次证据 §8](qa/UX-PERF-CLOSEOUT-20260923/README.md)。**未执行**：真实供应商/RAG/硬件触摸/逐帧动画（not_run）。

### 5.B 上一实施批（历史）：CHAT-CONTEXT-BUDGET v1（请求统一预算）+ RAG-I0-PREP v1（RAG 只读准备），2026-09-23

**目标（用户锁定）**：① 为最终请求建立统一预算——课程上下文、历史消息、当前问题共同参与计算，预留输出预算，分别遵守后端单条/总长度限制，且**不把字符估算夸大为精确 token**；② 课程上下文所有动态字段受限，保留「资源仅登记，未解析未检索」说明，字段裁剪只影响发送内容、**不反向改写课程原始数据**；③ 优先缩减可省略的课程摘要与旧历史，**不静默丢掉当前问题、不拼接半条消息、不伪造完整上下文**，必要输入仍超限时在发请求前明确提示并保留输入可修改；④ 课程快照仍按轮次冻结（旧轮重试不读最新课程、新轮用新快照），**旧超长快照同样经安全构建、不要求清库**，如实记录发送时的裁剪行为且历史原文不变；⑤ 预算/构建失败不得留下 `sending=true`、空助手占位、无法重试状态或未处理 Promise；⑥ RAG 侧只做只读核对与宿主侧契约准备，**不启动模型、不重建索引、不填人工 verdict、不解封 held-out、不改 RAG 仓库**。同批不改变模型输出预算默认值、不自动关推理、不顺手处理 R-13、不引入 RAG 内容或模拟聊天。

1. **复现的缺陷（探针纳入 Git）**：D1「UI 可输入的超长大纲标题（32001 字）使课程 system 消息达 **32088 字**，同时越过 2400 承诺与后端 `MAX_MESSAGE_CHARS=32000`」；D2「课程块在 `contextBudgetChars` 裁剪**之后**追加，实测 2040 > 预算 2000」。探针原件与副本见 [probe-reversal](qa/CHAT-CONTEXT-BUDGET/probe-reversal/)（副本 md5 `18122b3c…` 与 `_work` 原件逐字节一致，未改断言）。
2. **修复**：新增 `features/chat/model/request-budget.ts`（唯一构建入口 `buildChatRequest()`；`BACKEND_REQUEST_LIMITS` 为 200/32000/120000 的单一事实来源；裁剪阶梯 ①课程字段 → ②整条丢最旧历史 → ③整体丢课程块；当前问题逐字不裁剪、放不下即**发送前** `ok:false`）；`store.send()` 预检（失败不清草稿、不入库用户消息、不建占位、不置 `sending`）；`requestBudget` 账目随助手消息持久化（刷新可核，只记发送时事实）；`retry()` 用同一构建器 + 旧轮冻结快照；`courseContextMessage` 渲染期限幅 `name≤80`/`nextTitle≤120`（授权最小补丁，归属与过滤语义未动）。
3. **实跑（r3 交付候选 `a5be128`，构建 `dm5NJM2F0N_z9lp13FK0s`）**：`typecheck` 通过；`lint` 0 警告；unit **52 文件 / 436 例**；定向 e2e **15/15**（新增 4 + 课程闭环 11）；全量 e2e 在 r1/r2 构建上三次 **195 passed / 0 failed / 0 flaky**，r3 构建一次 **194/1**（唯一失败为跨批既有间歇用例，见 §3 台账 **R-14**，与本批 diff 面无交集）；探针反转：原探针 2/2 **按预期失败**（D1 现 208 字、D2 现 1990≤2000），产品路径反转探针 3/3 通过。**独立验收三轮**：r1 可交付（附 1 条低危健壮性缺口）→ 关闭后 r2 可交付（附 F1 跨批间歇 + F2/F3/F4 残留）→ 关闭 F2/F3/F4/F5 后 r3 窄复验**可交付**（突变对照证明新增用例因果绑定；另登记一条已知边界：标签不可读但 kind/availability 可读的条目仍渲染空标签，仅契约外数据可达）。三轮报告与总控处置见 [A1 r1](qa/CHAT-CONTEXT-BUDGET/A1-REPORT-01.md)、[r2](qa/CHAT-CONTEXT-BUDGET/A1-REPORT-02.md)、[r3](qa/CHAT-CONTEXT-BUDGET/A1-REPORT-03.md)。证据见 [批次证据](qa/CHAT-CONTEXT-BUDGET/README.md) 与 [FROZEN 记录](qa/CHAT-CONTEXT-BUDGET/FROZEN-CANDIDATE.json)。
4. **RAG-I0-PREP v1（宿主侧契约 + 只读核对，候选 `13a93ae`）**：上游实际 HEAD `a0f9ade`（分支 `master`，父 `8ed22b8`），工作区 7→13 项漂移且**未确认停止写入**；冻结 `P8-FREEZE-20260922-190500` 的包/manifest/receipt 完好、`--verify` 退出码 1（失败仅为「当前树 vs 快照」漂移 18 项、脚本不比对 HEAD/porcelain）；现役配置 20/20 与 `configs/**` 一致；性能边界：热态检索 p95 210/369 ms 达标、**端到端 P95 22.7 s 未达标**；质量三类（证据充分性/段级/讲解）仍 `not_run`（评审者 0 人）。宿主侧交付 `apps/api/app/contracts/rag_adapter.py`（输入输出/引用坐标/状态与错误契约 + UTF-16↔码点转换纯函数）+ **35 例**合成数据契约测试，`get_rag_adapter()` 恒定抛 `RagAdapterUnavailable`（**无假实现、未注册路由**，capability 仍 `planned`）；宿主 API 全量 **217 passed**；12 项缺口 G1–G12 见 [报告](qa/RAG-I0-PREP/README.md) 与 [FROZEN 记录](qa/RAG-I0-PREP/FROZEN-CANDIDATE.json)。**结论：宿主侧契约/准备已完成，上游存在具体缺口；不标记 RAG 已接入。**
5. **边界与未执行**：全部预算数字为**字符估算**（1 token ≈ 2 字符），不保证不超模型自身上下文上限，只保证不超本轮输入预算与后端硬限制；`selectMessagesForRequest` 保留为兼容入口（非产品路径）；真实供应商**未发起真实外呼、未验证凭证有效性**（not_run）；上游 pytest/评测/模型加载/索引重建/held-out 解封/OS 级断网均 not_run；本批不宣称视觉通过（无样式规则改动）。
6. **不包含**：RAG 内容进入宿主、追问执行、教材上传、真实检索、第二套业务后端、全站动画重做。**I1 需用户明确解除冻结范围并确认上游停止写入后启动。**

### 5.C 更早实施批（历史）：H1-COURSE-SESSIONS v1（课程学习会话闭环，2026-09-22）

**目标（用户锁定）**：完成「课程 → 创建学习会话 → 真实问答 → 返回课程 → 恢复原会话」闭环，并同时交付有界前置补丁 BOOKS-CS-FOLLOWUP v1（见 §5.D）。冻结契约见 [任务卡](qa/H1-COURSE-SESSIONS/TASK-CARD.md)，实跑与首败见 [批次证据](qa/H1-COURSE-SESSIONS/README.md)。

1. **归属与数据**：`Conversation.courseId`（可选，稳定课程 id）+ `ConversationMeta.courseId` 贯通列表元数据；缺失/空串 = 未归属，**不按标题/最近访问/URL 猜测**、旧会话不被改写；`schemaVersion` 保持 1。课程删除/归档**不修改会话与消息、不自动换绑**（与参考「删除即清空归属」有意不同，理由：历史与归属可追溯）。
2. **课程页会话区**：本课程会话列表（只按稳定 id 过滤、按更新时间倒序）、空态/加载/读取失败重试；「新建学习会话」**保存成功后才跳转**（同一 tick 连点由同步 ref 去重、写入失败保留页面并给「重试新建」）；归档课程只读。
3. **聊天页课程上下文**：显示「所属课程：…」与「返回课程」；课程删除/目录读取失败时如实标注且**不回落其他课程**；切换会话不残留课程上下文。
4. **课程上下文进入真实请求（关键）**：发送时把课程名、约定（≤1200 字符）、大纲摘要与资源**登记**清单冻结为 `TurnCourseSnapshot`，渲染成一条 `system` 消息插在请求 `messages` 最前，经既有 `POST /api/v1/chat/stream` 送达供应商适配器（后端 `ChatMessageIn.role` 已支持 system，**未新增请求字段、未改后端产品代码**）；快照随助手消息持久化——**重试沿用原快照，课程修改只影响新轮**。
5. **如实边界**：资源仅登记引用（R-11 available/missing/unknown），**登记 ≠ 已解析 ≠ 已检索 ≠ 已随请求发送**；RAG 未接入；大纲 covered 为学员手判，不推断掌握度、不伪造学习规划。
6. **取证分层**：真实供应商调用**无凭证 not_run**；「浏览器 → 现有 FastAPI → 供应商适配器」三段分别取证（e2e 断言发往 `/api/v1/chat/stream` 的报文含 system 课程上下文；后端新增用例证明逐条转发给 provider 请求体；供应商适配器的 system 透传由既有 `test_providers.py` 覆盖）。
7. **不包含**：BookChatPanel、课程学习智能体工具、自动学习规划、精通/记忆、RAG 正式接入、真实书籍生成、全站动画重做，以及任何模拟聊天捷径。
8. **独立验收（两轮）**：A1 r1 判「需修订（有界）」——F1「保存已提交、导航卸载再次点击会创建第二条课程会话」（探针 gap=10/25ms）、F2「课程上下文警告跨会话残留」，另列 F3–F11（测试有效性/文档口径/结构）；修复批 `701d391`（守卫保持到卸载、四处切换点清除警告、预算内收缩保留免责句、补 2 例 e2e + 1 例单测、文档清扫）重新冻结后，A1 r2 判 **可交付**（F1/F2 经其独立探针确认修复、要求 4/5/6/7 重跑无回退、191 例全量 e2e 与 416 例单测由其本机重现）。报告：[r1](qa/H1-COURSE-SESSIONS/A1-REPORT-01.md)、[r2](qa/H1-COURSE-SESSIONS/A1-REPORT-02.md)。

### 5.D 更早实施批（历史）：BOOKS-CS-FOLLOWUP v1（书籍前置补丁）与 H1-BOOKS-COMMIT-SAFETY v1（书籍保存一致性）

**目标**：收口书籍本地仓储的**提交一致性**——写入口单一协议、互斥/事务读改写、提交结果可判定，调用方只在落库成功后展示成功。冻结契约与范围见 [任务卡](qa/H1-BOOKS-COMMIT-SAFETY/TASK-CARD.md)。

1. **复现的缺陷（脱敏探针纳入 Git）**：CS-01 冲突预算耗尽后返回内存候选值 → `createBook` 返回幻影书籍、调用方进入成功流程；CS-02 写标记只能写前检测 → "检测之后、写入之前"提交的对方内容被旧整表覆盖（可控交错复现，不依赖同一毫秒）。
2. **修复**：新增 `services/collection-lock.ts`（原生 Web Locks 主路径 + localStorage 取号/settle/读回校验回退路径 + 同标签页串行队列；**该 localStorage 回退路径已在 BOOKS-CS-FOLLOWUP v1 整体删除**，见本节第 6 条）；`books-store.ts` 全部写入口改为锁内事务（读快照→变更→写修订号→写数据→双重写后校验，校验不过整事务在最新快照上重做），统一返回 `CommitResult`（`committed/conflict/missing/skipped/read-failed/write-failed`，非 committed 的 value 恒为 null）。
3. **写入口与调用方**：书籍集合的创建/编辑/删除/笔记/作答/已读/书签/生成事件/页块修复/检查点/演示载入/场景设置全部走同一协议；`BooksRoute`、`PageReader`、执行器（`applyStored`/`flush`/`pause`/`stop`/收尾/修复复位）逐个迁移为等待提交结果；失败保留输入与草稿并可重试（真实浏览器验证了"持锁时创建失败保留输入、释放后重试成功"）。
4. **与租约的关系**：租约继续保证"单书只有一个执行器"，集合锁保证"整表读改写互斥"；引擎每批事件在锁内重读、`runWritable` 基于锁内快照，旧执行器迟到写入仍被 `runId` 拒绝（HARDEN v1 语义不变）。
5. **实跑结果**：`npm run typecheck` 通过；`npm run lint` 0 警告；`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` **48 文件 / 389 例通过**；`npm run build` 通过（`BUILD_ID = AtxBYXEc_99FFQ8cGCtvu`）；`npx playwright test` **178 例通过 / 0 失败**（既有 174 + 新增 `books-commit-safety.spec.ts` 4 例真实双标签页场景）；原缺陷探针 2/2 按预期失败（假设不再成立，见 [probe-reversal](qa/H1-BOOKS-COMMIT-SAFETY/probe-reversal/README.md)）；独立验收 A1 只读复验见 [A1-REPORT.md](qa/H1-BOOKS-COMMIT-SAFETY/A1-REPORT.md)。未执行：`apps/api` 测试（零后端改动，沿用基线 181）、真实供应商、硬件触摸、逐帧动画。
6. **边界**：生产路径用原生 Web Locks（真实互斥）；jsdom 单测走测试注入的 in-process 互斥（本批当时的 localStorage 回退锁已在 BOOKS-CS-FOLLOWUP v1 整体删除，无互斥即 `unsupported`、不降级写）。**不宣称强原子性**：写后校验能发现窗口内的并发改写并如实报 `conflict`（不静默丢失），但**不得声称「写后读回必然发现所有绕过协议的写入」**（BOOKS-CS-FOLLOWUP v1 任务卡 §6 订正口径，见 §5.D）。旧数据、损坏/读取被拒保护、R-11 三态、14 类 block、七态状态机、`paused` 不自动恢复、归档只读全部保留。不包含：课程学习会话、BookChatPanel、主题重做、`feat/glass-theme` 合并、推送/部署。
7. **独立验收 A1（r1 条件通过）**：修复在源码级、单测与真实双标签页浏览器三层独立成立，聚合数字与指纹由其本机复现；交付前已处置 4 条文档/卫生项（单测基线改记"上一批 48/381 → 本批 48/389（+8 例、无新文件）"、`next-env.d.ts` 提交前还原、探针失败原因按实测更正、`frozenAt` 标注为名义时刻）。**登记为已知边界、留待下一批**（改动会触及产品文件需重新冻结）：暂停/恢复未按提交结果分支（持锁时"提示已暂停但存储仍 compiling"，可恢复不丢数据）、`applyStored` 一处死分支、修复入口在读被拒极端时序下 Promise 可能不 settle、自动续跑罕见双入口（租约自愈，仅提示噪声）。全文见 [A1-REPORT.md](qa/H1-BOOKS-COMMIT-SAFETY/A1-REPORT.md)。
8. **下一业务批**：**H1-COURSE-SESSIONS v1**（课程内创建/恢复真实聊天、明确课程归属、课程与聊天往返、旧会话兼容及失效资源处理）——见 §6 路线；本批不顺手实施。

### 5.E 更早实施批（历史）：H1-BOOKS-HARDEN v1（2026-09-22）

<a id="harden-results"></a>

**目标（用户锁定）**：修复 §3.1 M22-01～06，保持书籍七态、14 类 block、笔记/练习/书签/导出、显式模拟标注及自动接管既定语义；先复现再修，不得只修改断言掩盖问题。

1. **范围与文件归属**：引擎 = `services/book-generation.ts`、`services/books-store.ts` 及其单测；UI = `features/books/BooksRoute.tsx`、`features/books/PageReader.tsx` 及其测试；总控（本会话）独占文档、共享契约、e2e（新建 `tests/e2e/books-harden.spec.ts`）、构建与 Git。先冻结契约（[TASK-CARD.md](qa/H1-BOOKS-HARDEN/TASK-CARD.md)：统一收尾/读取三态、`RepairResult` 与冻结 runId、租约归属、共享集合写协议、界面契约），再实施。
2. **六项结果**（逐项首败与修复证据见 [DEFECT-LEDGER.md](qa/H1-BOOKS-HARDEN/DEFECT-LEDGER.md)）：M22-01 统一收尾并把"删除/读取被拒/失权"分开处理（删除入口先停任务；读失败收尾后可从断点恢复）；M22-02 修复入口返回 `Promise<RepairResult>`、启动冻结 runId、每次写入核对归属、同页互斥与可取消；M22-03 租约写后读回校验 + 每步/心跳归属校验 + 失权即停 + 共享集合写标记冲突检测与有界重放；M22-04 首次读取失败显示错误与「重试读取」并在成功后清除旧错误；M22-05 最终完成写入失败落 `kind storage` 失败并给「重试生成」，绝不假报完成；M22-06 输入框/文本域/contenteditable/组合输入/修饰键不再触发全局翻页。
3. **探针反转**：三个审查探针**未修改**，修复后运行 3/3 按预期失败（不再复现缺陷），输出留档 [probe-reversal](qa/H1-BOOKS-HARDEN/probe-reversal/README.md)；正式回归断言的是正确行为。
4. **验证**：typecheck、lint（0 警告）、unit、build、相关 e2e、全量 e2e 与独立验收的实跑结果见 [批次 README §2](qa/H1-BOOKS-HARDEN/README.md) 与 §5.E.10；`apps/api` 零改动，API 测试未重跑（沿用本轮基线 181）。
5. **视觉/设计**：本批只新增"读取失败面板 + 重试"、"修复未完成提示"与模拟设置里的一个复选项，全部复用既有控件与变量（`space-banner`/`space-banner-row`/`space-button`/`space-toggle`/`book-reader-storage-error`），未改主题、未新增参考外动画；390×844 页面级横向滚动差 ≤1px 有 e2e 断言。按 `web-design-guidelines` 清单自查新增 UI（异步错误用 `role="alert"`、错误文案含下一步、无 `transition: all`、无布局读取），未发现需要修改项；未做全站改造。
6. **边界与未执行项**：真实 LLM/解析与真实供应商仍不接；RAG 未接入（`F:\ZQKY_RAG` 保持只读，仍需先完成 P8A 与可恢复版本交付）；未运行后端测试、移动端硬件触摸、逐帧动画曲线（属 H6）；"同一毫秒并发写共享键"窗口无法确定性构造，实现为写后读回 + 有界重放并如实标注，**不宣称强原子性**。不包含：课程学习会话、BookChatPanel、主题重做、`feat/glass-theme` 合并、推送/部署。
7. **独立验收 A1 结论与采纳（r1 → r2 两轮只读复验）**：r1 上核心 6 项与全部聚合数字独立成立（A1 自跑全量 e2e 得 174/0 复现），提出 2 条文档对账 fail 与 7 条挑刺；已采纳并修复 3 条（修复期间书籍变为不可写不得报 `completed`、笔记写入落地校验、失权文案不再单方面断言他人接管）并补 2 条回归，文档计数与口径 5 条按 A1 结论修正，1 条（`writeListConverged` 有界重放耗尽后仍返回最后计算值）如实登记为已知边界。r2 定向复验判 **可交付**（`48 文件 / 381 例`、`174 通过 / 0 失败 / 0 flaky`、探针 3/3 按预期失败、lint 0 警告、12 文件指纹与 BUILD_ID 均由 A1 本机独立复现）；其 r2 新发现的 2 条低危项（读回窗口终态归因、`finishBookRun` 读回）不构成假成功，已登记为已知边界并列入后续批次待办。全文与 not_run 清单见 [A1-REPORT.md](qa/H1-BOOKS-HARDEN/A1-REPORT.md)。
8. **不改变既有语义**：七态状态机、页/块状态、四类失败注入、`paused` 不自动恢复、自动接管时机、笔记/练习/书签/导出、归档只读、旧数据（缺 status 按 ready 读取期派生）全部保留；新增行为仅在"出口收尾、修复身份、租约归属、读失败可见、最终落库失败、键盘排除"六处，语义变化逐条登记在台账 §"语义变化的已知边界"。
9. **资源与隔离**：引擎单测在 jsdom 临时存储隔离运行；e2e 独占 5174（构建产物来自本批源码）；构建目录总控单写；未触碰正式 `.env`/`.local-data` 与用户浏览器草稿。
10. **实跑结果**：`npm run typecheck` 通过；`npm run lint` 0 警告；`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` **48 文件 / 381 例通过**（基线 46/353）；`npm run build` 通过（`BUILD_ID = cTTq7b-No7rnD-HNmoyQc`）；`npx playwright test` **174 例通过 / 0 失败**（既有 168 + 新增 `books-harden.spec.ts` 6）；审查探针 3/3 按预期失败（断言反转证据）；独立验收 A1 只读复验见 [A1-REPORT.md](qa/H1-BOOKS-HARDEN/A1-REPORT.md)。未执行：`apps/api` 测试、真实供应商、硬件触摸、逐帧动画。

### 5.0 最近实施批（历史）：H1-BOOKS-PIPELINE v2（书籍生成流水线与增量阅读闭环）

**状态：本批实现与本地验收完成，待交付审查（2026-09-20）。** 负责人：实施总控（本会话接手上任未收口工作）；独立验收 A1 只读。起点候选 `bf460ab`（接手前工作区改动快照见 §5.0.5，本批不提交、不还原）。完整任务卡、冻结契约（状态枚举/字段/仓储 API/执行器 API）、队长裁定、锚点与禁区清单在 [docs/qa/H1-BOOKS-PIPELINE/TASK-CARD.md](qa/H1-BOOKS-PIPELINE/TASK-CARD.md)，本节登记范围与边界，结果与语义变化见 §5.0.7–§5.0.9。

1. **需求（用户锁定）**：① 补齐 `draft/spine_ready/compiling/paused/ready/error/archived` 七态与页面/块的等待·生成中·完成·部分失败·失败状态，明确生产者、转移条件、持久化字段与恢复操作，区分局部块失败/页面失败/整轮失败/本地存储失败；② 可观察生成：新建→提案→确认大纲→逐章逐块生成，增量落库、阅读器可见已完成与未完成，活动条/阶段文案/章数/计时/展开详情/暂停横幅/正文提示对照固定参考，进度来自真实任务状态；③ 暂停与中断：用户暂停与**模拟**供应商连续失败暂停两类，均只在明确恢复后继续，刷新/选页不绕过暂停，对照参考 `maybe_resume_on_open` 仅对"compiling 且无活跃执行器"自动续跑；④ 失败与重试：单块重试、页面失败恢复、整页重生成，不暗中重建整本，部分失败如实显示；修复初次读取失败停在加载态；⑤ 数据与并发：旧数据兼容读取、损坏不覆盖、增量合并保护生成期间新增笔记/书签/进度、块身份稳定、作答版本关系、整书重建语义不变、事件绑定 bookId+runId+序号且重复/迟到不重复落库、同书单一执行者（双标签页不互相覆盖）、存储失败停止推进且不谎报已保存、生成进度与阅读进度分开、导出不伪装完整、课程 R-11 三态不回退。
2. **实现方式**：`books-store.ts` 扩状态机与持久化（唯一写入口 `applyRunEvent`）；新建 `services/book-generation.ts` 作为**可替换的显式模拟执行器**（增量事件 + AbortSignal + 确定性失败场景 + 每书租约），正常路径由事件逐块推进，不预先同步生成整本；`BooksRoute.tsx` 承载活动条/展开详情/暂停横幅/自动续跑/模拟场景设置；`PageReader.tsx` 承载块与页状态、失败重试、整页重生成、作答版本关系。不接真实 LLM，不新增第二套业务后端。
3. **文件归属**：I1＝`services/books-store.ts` + 新建 `services/book-generation.ts` + 两处单测；I2＝`features/books/BooksRoute.tsx` + 新建活动条/暂停横幅组件 + 新建 `features/books/styles/book-pipeline.css` + 组件测试；I3＝`features/books/PageReader.tsx` + 新建块失败组件 + 新建 `features/books/styles/book-reader-states.css` + `PageReader.test.tsx`；总控＝STATUS/三矩阵/必要决定、`tests/e2e/books-pipeline.spec.ts`（新建）、`books-courses.spec.ts` 异步语义改造、构建与 Git；A1＝只读独立验收。同一文件同一时段单一写入者。
4. **验收条件**：见任务卡 §7（正常链路、四类失败、暂停/恢复/中断/重试、数据兼容与并发、三视口与减少动画、模拟边界），必须运行 typecheck / lint(0 警告) / unit / build（队长重建记 BUILD_ID）/ e2e（既有 154 + 新增）。**不包含**：BookChatPanel、课程学习会话、真实 LLM/解析、真实 HealthBanner 数据、侧栏折叠、多用户权限、R-13、R-06 补测、14 类 block 全面重做、导航字体收口——这些范围不因本批通过而关闭。
5. **接手现场（§5.0.5）**：起点 HEAD `bf460ab`；`.zcode/agents/*.md`(3)、`apps/web/next-env.d.ts`、`apps/web/src/components/layout/workspace-shell.css` 为接手前改动，本批不提交、不还原、不清理；快照与校验值在 `_work/h1-books/handoff-snapshot/`（构建改写生成文件时按此恢复）。
6. **旧合同失效声明**：`books-store.test.ts`「确认提案→确认大纲完成模拟编译」与 e2e `books-courses.spec.ts` 第 2 例锁定"确认大纲即同步 ready"，本批以异步流水线取代，改为更强的异步状态断言，逐项在结果卡说明理由；不删测试、不放宽既有阈值、不保留第二条同步捷径。

<a id="h1-books-results"></a>

### 5.0.7 本批结果（实跑）

- 工程检查：`npm run typecheck` 通过；`npm run lint`（`--max-warnings=0`）**0 警告**；`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` → **46 文件 / 353 例通过**（基线 47 文件/344 中删去零断言探针 `zz-debug.test.ts`，本批净增 10 条）；`npm run build`（总控自跑）通过，`BUILD_ID = TPMei2ra-L9r31dqKSPpl`（迭代：r1 `hrsgX9VjAM3HhtDYpjgPj` → r2 `tqqP-RbOtTrgBVOXkRUET` → r3 修浮层裁切，见 §5.0.10）；`npm run test:e2e` → **168 例通过 / 0 失败**（既有 154 + 新增 `books-pipeline.spec.ts` 14 例，构建产物来自本批源码）。
- 独立验收 A1（只读，冻结指纹见 §5.0.10）：r1 **pass 32 / fail 0 / not_run 0**（含 4 项挑刺：无 run 记录书的整页重生成、笔记写入失败不谎报、provider 开关单独开启真暂停、interrupted 态恢复入口，全部成立）；A1 挑出的 `contentVersion` 生产路径从不写入已按建议修复 → r2 定向复验 **pass**（真实存储实测「作答 `blockVersion` == 块 `contentVersion`」）；r3（修活动条展开浮层被 46px 条裁切，台账 N10）定向复验记录见其报告。
- 视觉与动画（真实浏览器 msedge，三视口 1440×900 / 1920×1080 / 390×844）：浮层进场 `180ms cubic-bezier(0.16,1,0.3,1)`、呼吸文字 `1.8s`、reduce 下两项均被压制（`1e-05s`）、快速开关 0→1→0、展开中暂停后浮层仍可收起、活动条按钮焦点环 2px、390 页面级溢出 0。截图与量化证据见 [qa visual](qa/H1-BOOKS-PIPELINE/visual/evidence.json)。
- 证据索引：[批次 README](qa/H1-BOOKS-PIPELINE/README.md)、[首败与修复台账](qa/H1-BOOKS-PIPELINE/DEFECT-LEDGER.md)、[A1 报告](qa/H1-BOOKS-PIPELINE/A1-REPORT.md)、[冻结指纹](qa/H1-BOOKS-PIPELINE/FROZEN-CANDIDATE.json)。
- 未执行：`apps/api` 测试（本批零后端改动）、真实供应商链路、移动端硬件触摸、逐帧动画曲线（属 H6 总验收范围）。

### 5.0.8 语义变化（与旧实现不同的行为，接手者必须知道）

1. **「确认大纲」不再同步 ready**：`confirmSpine` 建骨架并写 run 检查点进入 `compiling`，由本地模拟执行器逐章逐块异步推进到 `ready`（旧同步断言已替换为更强的异步断言）。
2. **失败不再假完成**：仍有未完成页 → 书籍保持 `compiling`（无执行器即“已中断”，活动条显示「继续生成」）；本地写入失败 → `error` 并给「重试生成」。部分失败（partial 页）计入完成但卡片与导出如实标注。
3. **自动续跑时机收窄**：只在“打开/刷新书籍”或“他标签页租约失效”时自动接管一次；同一挂载内跑过执行器后不再自动重启——否则一次页失败后的“已中断”会被下一次轮询立刻自动接管，用户看不到中断态、失败原因与恢复入口。
4. **注入场景一次性**：块失败、整页失败、本地写入失败都是“首次失败、重试即成功”，不会在同一触发点无限失败；整页失败以页自身 `attempts` 为判据，刷新/续跑后不重复注入。
5. **UI 开关必须真的命中**：`'*first'` 通配在场景解析期展开为全书第一个块；「模拟供应商连续失败暂停」自身产生连续页失败直至阈值（此前单独开启时无任何效果）。
6. **归档书只读**：生成/重试/重新生成入口禁用并给出同一说明（不再出现“按钮可点但什么都没发生”）。
7. **块占位分两态**：`正在生成 X 块…`（真的在写，带旋转图标）与 `X 块等待生成…`（排队或当前没有执行器）。
8. **`contentVersion` 真实写入**：执行器按生成内容的确定性哈希写入块版本；作答版本关系由“永不触发”变为“内容变化则旧作答如实标记为旧版记录”（内容相同的重生成不误判为过期）。
9. **就绪书卡片状态徽标保持渲染**：视觉推广期曾改为“仅非 ready 渲染”，本批恢复为全状态渲染（既有 e2e 以卡片上的「可阅读」锁定就绪态，按“保留既有断言”处理；与参考的差异如实记录）。

### 5.0.9 数据兼容、恢复与边界

- 兼容：旧四态数据照常可读；缺 `status` 的页面/块按 `ready` 读取期派生、不写回；`run` 缺失表示无历史运行（演示书/旧就绪书的页/块修复会补一个只作写入容器的检查点，不改书籍状态与阅读进度）；损坏/结构非法/写拒仍走 `local-collection` 抛错路径，不当作空库、不覆盖、不谎报已保存。
- 恢复：`paused` 只能由用户显式恢复（刷新不自动续跑）；`compiling` 无执行器时按页状态续跑（不重复生成已完成页）；`error` 可续跑；双标签页靠租约保证单执行者。
- 边界：全部为本地模拟执行器与本地显式注入，**不接真实 LLM/解析**；本批通过不代表真实供应商能力、不代表书籍模块或全站完成。不包含：BookChatPanel、课程学习会话、真实 HealthBanner 数据（kb_drift/log_health）、侧栏折叠、多用户权限、R-13、R-06 补测、14 类 block 全面重做、导航字体收口。
- 保留风险（记录备查，非本批缺陷）：暂停/恢复/重试按钮忙态为固定 600ms 复位；活动条 UI 由 500ms 轮询刷新（事件落库与界面更新最大约 0.5s 延迟）；“缺 status 即 ready”是长期兼容约定，缺 status 但实际未完成的页会被按完成读取。

### 5.0.10 冻结候选

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
5. R-05 收口当时不覆盖 `P-books-pages-[pageId]`；该项后由 H1 v2 在其范围内升级为视觉部分验收（见页面矩阵），不等于全部 block 或本轮新发现通过。Whisper 等未有独立完整验收的范围继续保留。

<a id="roadmap"></a>

## 6. 后续路线与推进规则

| 顺序/轨道 | 交付中心 | 出口 |
| --- | --- | --- |
| **UX-PERF-CLOSEOUT v1（2026-09-23 已交付，见 §5.A）** | 长推理流性能收口 + 模式菜单（RAG 模式占位）+ 学习记录并入导航 + 书籍归属 + favicon + 教案布局 + 双语字体 token | 已完成（限定范围）；真实供应商/RAG 硬件触摸 not_run |
| **下一批（依赖顺序第 2 步）：现存业务与 R-14 的有界核查** | ① R-14（书籍双标签页并发写测试假设与既定行为不一致）定性并处置：要么在测试内接受「已中断」再走继续生成，要么调宽等待；② R-13（模型真实长答）只做有界核查，不无界加预算、不自动关推理；③ 现存业务问题按 STATUS §3 台账逐条有界处理 | 每条给出复现命令、定性（产品缺陷/断言问题）与处置；不借机扩大范围 |
| **下一批（依赖顺序第 3 步，前置未满足）：RAG 真实 I1 接入** | 需**用户先明确解除冻结并确认上游停止写入**，并在接入形态候选 A（独立进程边界）/ B（独立命名 wheel）中选定；`F:\ZQKY_RAG` 的漂移是用户侧进行中的开发，不是本项目的待修错误 | 前置满足前不启动；宿主 adapter 契约已就绪（§5.B、§6.1） |
| **最终阶段：真实服务、动画与全站总验收** | H6/H7：三矩阵逐项证据、逐帧动画曲线与中断、真实供应商按授权批接入 | 工程、视觉、真实/模拟、兼容与阻断分别有结论 |
| **H1-BOOKS-COMMIT-SAFETY v1（2026-09-22 已交付）** | 书籍保存一致性收口：集合写互斥事务 + 提交结果契约 + 全写入口/调用方迁移；见 §5.D | 已完成（限定范围，A1 条件通过并处置交付前项） |
| **H1-COURSE-SESSIONS v1（2026-09-22 已交付）** | 课程内创建/恢复真实聊天、课程归属、课程与聊天往返、旧会话兼容与失效处理；见 §5.C | 已完成（限定范围）；真实供应商调用 not_run；BookChatPanel 与课程学习智能体工具仍属后续 |
| **CHAT-CONTEXT-BUDGET v1（2026-09-23 已交付）** | 请求统一预算（课程块+历史+当前问题）+ 课程字段限幅 + 构建失败如实提示；见 §5.B | 已完成（限定范围）；真实供应商 not_run；精确 token 计数不在承诺内 |
| **RAG-I0-PREP v1（2026-09-23 已交付，宿主侧契约/准备）** | adapter 输入输出/引用坐标/状态错误契约 + 35 例合成测试；见 §5.B、§6.1 | 宿主侧完成；上游缺口 G1–G12 未清；**I1 需用户明确解除冻结并确认上游停止写入** |
| H1 课程闭环后续（未启动） | 课程学习会话的工具与产物、课程聚合进度、BookChatPanel；复用已交付的会话归属与轮次快照契约 | 真实执行通道按授权接入；不重复实施本次已交付的归属/快照/非破坏删除语义 |
| H1-BOOKS-PIPELINE v2 / H1-BOOKS-HARDEN v1（历史已交付） | 七态流水线与增量阅读闭环（§5.0）、M22-01～06 修复（§5.E） | 已完成（各自限定范围）；证据见对应 qa 目录 |
| H2既有模块闭环 | 阅读媒体原视图与完整伴生过程、写作/Whisper、学习空间及产物消费 | 原功能/数据不丢、来源正确、完整参考交互 |
| H3伙伴/智能体 | 列表/创建/详情/群组/渠道、任务过程/工具/产物/历史 | 创建→执行→结果→恢复，等待/失败/取消/重试齐全 |
| H4精通/记忆 | 路径/节点/反馈/阶段；记忆总览/冲突/图谱/L1-L3 | 精通新轮区别于普通ask_user，数据与跨页联动完整 |
| H5账户/完整设置 | 本地身份权限视图、工作空间/解析/网络/记忆/任务模型等 | 身份模拟准确标注，设置锚点/搜索/历史与业务联动 |
| T1真实服务独立轨道 | R-13、三协议供应商、复杂主聊天真实事件、解析/扩展等按授权批接入 | 不把模拟升级真实、不无界加预算、不因缺某供应商凭证停止其他独立任务 |
| T2自有规划轨道 | /papers、/question-bank、/templates与现有模块关系 | 单独明确范围，不擅自改53项分母或删入口 |
| H6/H7总验收交付 | 全站缺口/动画补漏与最终交接 | 三矩阵逐项证据；工程、视觉、真实/模拟、兼容与阻断均有结论 |

当前批之外的路线是后续计划，不是一次性授权实现全部模块。遇到实际数据丢失、凭证不一致、错误会话归属或假成功先修；普通审计补证不应无限取代可见产品交付。

### 6.1 RAG 接入阶段计划（宿主侧契约/准备已完成；真实接入未启动）

> 2026-09-23 UX-PERF-CLOSEOUT v1：`/chat` 模式菜单新增同级「RAG 模式」**入口占位**（未接入、不可选、
> 行内标注「未接入 · 规划中」，不发请求、不返回模拟检索结果）。该入口**不改变本节任何阶段状态**，
> 也不代表检索能力可用；`get_rag_adapter()` 仍恒定不可用、capability 仍 `planned`。

**2026-09-23 只读复核（RAG-I0-PREP v1）**——以下为现场实测，替代旧记录的相应结论（旧文保留在本节末尾）：

- **上游提交与工作区**：`F:\ZQKY_RAG` 实际 HEAD = `a0f9ade`（父 `8ed22b8`，分支 **`master`**）；开工时工作区 **7 项不干净**（`M docs/{EVAL,SCHEMA,START_PROMPT,STATUS}.md`、`M docs/qa/P8B-REVIEW-PROTOCOL.md`、`?? docs/START_PROMPT_P8B_HUMAN_REVIEW_V2.md`、`?? docs/qa/P8B-ROUND12-RULES-v2.md`——P8B 12 题裁定与真人复核入口材料**尚未提交**）。核对期间该数目升至 **13**：另一写入者新增 `src/evaluation/{annotation_v2,segment_metrics_v2,claim_review_v2,fullset_manifest,quality_report_v2}.py` 与 `tools/p8b_v2_packet.py`（mtime 14:14–14:20，伴随 CPython 3.14 的 `.pyc`）。**结论：未取得"上游已停止写入"的确认，任何"冻结/一致"只是时点观测。**
- **候选冻结**：`P8-FREEZE-20260922-190500`（用户 2026-09-22 明确"暂不安排，先冻结候选"）。冻结包 `data/derived/qa/P8-FREEZE-20260922-190500/` **完好**：`manifest.json`（144 归档成员 + 93 项指纹）与 `receipt.json` 可解析，receipt 对 `candidate.zip`/`manifest.json` 的 sha256 **逐一匹配**，`candidate.zip` 144 成员与 manifest **0 处不符**、`testzip()` 无错；`chunks.jsonl`/`questions.jsonl` 指纹与上游登记一致。`freeze_snapshot.py --verify` 经逐行判定为只读后运行：**退出码 1**，失败全部为"当前树 vs 快照"的源文件漂移（18 项），归档成员/归档内容/receipt 三类失败均为 **0**（快照自证一致）。**该脚本不比对 `manifest.git_head`/`git_status_porcelain`**（manifest 记 `3b132df` + 103 行 porcelain，与现状不符）——"与 HEAD/暂存一致"不是脚本结论。
- **现役配置**：冻结表 **20/20 与 `configs/**` 一致**；`configs` 未承载的项下钻到单一定义点核对一致（`hybrid_weighted`/`top_k=50`/`rerank=off`/`bounded_window`/`answer_policy=baseline`），**未发现配置漂移**。
- **性能边界（P8C 重新测量，不沿用历史 PASS）**：热态纯检索 p95 **210 ms(subject)/369 ms(all)**（判据 ≤500 ms，**通过**）；**无生成缓存端到端 P95 未达标**（实测 **22,675 ms**，判据 ≤15 s；首因为生成侧输出截断触发修复轮，同批检索 p95 146 ms）。P8C-GEN-1 主实验计数为 estimate、修复后 12 行子集为 exact，**不得合并宣布输入完整性全部通过**。
- **质量边界（不变）**：证据充分性/拒答质量、段级质量/讲解支持性、阈值选择全部 **`not_run`**（评审者 0 人、可用金标 0 条）；冻结文件明令不得用编码 agent 或同模型自评冒充人工评审。
- **本批交付的宿主侧准备（不启动上游）**：内部 RAG adapter 的**输入输出契约**（`apps/api/app/contracts/rag_adapter.py`：`RagQuery/ScopeRef/EvidenceItem/Citation/RagAnswer` + `RagAdapter` 端口 + `RagAdapterUnavailable`）、引用契约（半开字符区间、1 基闭行号、文件指纹、**Python 码点 vs 前端 UTF-16 不可混用**且提供双向转换纯函数）、错误/状态契约（`ok|no_evidence|stale_source|out_of_range|unavailable`，非 ok 时不得夹带载荷）、执行边界的**设计描述**（有界队列/超时分层/**取消等待 ≠ 停止底层推理**/迟到结果丢弃/模型不可用如实报错——**均未实测**）；合成数据契约测试 **35 例通过**；`get_rag_adapter()` 恒定抛 `RagAdapterUnavailable`，**无任何假实现、未注册路由**，capability 仍 `planned`。完整核对与 12 项缺口见 [RAG-I0-PREP 报告](qa/RAG-I0-PREP/README.md)。
- **仍未满足 / 未实测**：G1 无 tag/remote/bundle 的**受控可恢复版本包**（冻结包位于被 gitignore 的 `data/derived/`，不在任何提交里）；G2 上游并发写入者未停止；宿主锁定环境 vs 上游依赖/Python 兼容性未验证（宿主无 numpy/jieba/rank_bm25/PyYAML/httpx；3.12.14 vs 3.14.6）；未见并发/队列上限实现证据；"停止底层推理"能力未测量；held-out 解封未做；OS 级断网未执行（零云端为进程级证据 + 台账）。
- **I1 不得据本批自动启动**：需用户明确解除冻结范围（并确认停止上游写入）后，在报告 §4.4 的候选 A（独立进程边界，不动宿主锁文件）/ 候选 B（独立命名 wheel，需单独授权改依赖与锁文件）之间选择接入形态。

以下为 2026-09-22 的旧记录（保留历史，勿再据此判断现状）：用户原路径 `F:\ZQKY\_RAG` 不存在，实际核对项目为 `F:\ZQKY_RAG`（其 AGENTS 明确指向本宿主）。HEAD `3b132df`，但主要 P5–P8B 实现仍在未提交工作树（74 条脏文件、暂存为空），不能仅交付这个 SHA。**2026-09-22 只读核对订正**：其 STATUS 已记录 **P8A 十项（4 P1 + 6 P2）修复完成并独立复验 fixed 14/14**（含 4 项关联边界），**不再沿用"P8A 待修"的旧结论**；段级质量与讲解支持性**人工评审仍 not_run**（88 题全部 pending、金标 0、无评审者），性能属 P8C 未启动；**未发现可恢复版本交付物**（无 tag/remote/bundle/zip，指纹文件均在 gitignore 的 `data/derived/` 下、不在提交里）。历史本地检索 Hit@5 75.8% 为节级结果，重排未达门槛，默认 off。架构设计见 PROJECT_GUIDE §4.1，**接入准备核对清单（六项：可恢复版本、依赖/模型/索引指纹、服务输入输出、引用坐标、错误状态、资源与取消边界）见 PROJECT_GUIDE §4.2**。本轮未重跑其测试或评测。

| 阶段 / 负责仓库 | 实施内容 | 进入下一阶段的条件 |
| --- | --- | --- |
| R0：RAG 项目准备（**2026-09-23 更新**） | P8A/P8B/P8C/P8C-GEN-1 均已交付并登记（P8A 复验 fixed 14/14；P8C 热态检索 p95 210/369 ms 达标、**端到端 P95 22.7 s 未达标**）；候选冻结 `P8-FREEZE-20260922-190500` 完好；**仍缺：受控可恢复版本包（无 tag/remote，冻结包在被 gitignore 的 `data/derived/` 内）、上游停止写入确认、并发/队列上限与停止能力测量、人工质量评审（评审者 0 人）** | 需上游给出**受控版本包**并确认停止写入（G1/G2）；人工质量未过只能进受限技术预览，不能宣布教学质量完成 |
| I0：宿主合同与兼容验证（**2026-09-23 完成宿主侧契约/准备**） | 已交付：adapter 输入输出契约 + 引用坐标契约 + 状态/错误契约 + **未实测**的执行边界描述 + 35 例合成数据契约测试（`apps/api/app/contracts/rag_adapter.py`、`apps/api/tests/test_rag_adapter_contract.py`）；capability 仍 `planned`，`get_rag_adapter()` 恒定抛 `RagAdapterUnavailable`（**无假实现、无路由**） | 剩余：宿主 Python/uv 与上游依赖兼容**未验证**（G5）、并发/队列上限与停止能力**未测量**（G6/G7）、接入形态候选 A/B 待用户授权选择；同步检索不阻塞 FastAPI 的适配属 I1 |
| I1：只读教材定位接入 | 现有 FastAPI 内增加受控 RAG adapter，加载既有受信索引，返回引用和原文；按 book/file 范围在检索前过滤；可取消、有队列上限/超时，模型不可用明确失败 | 源码合同测试 + 真实本地新题 + 越界/失效索引/文件变化/取消/并发验收；原聊天仍可独立运行。仅支持既有教材，不能标成通用上传解析完成 |
| I2：/chat 真实追问闭环 | 用户显式选择教材定位/追问，连接 `wait-user`→回答确认→续答；证据独立结构化保存；引用点击原文定位；刷新/断线恢复、幂等、超时、取消与换会话归属 | 普通聊天回归；重复提交不重复生成、过期卡不复活、跨会话不串；后端重启时恢复或明确中断；三视口/焦点/公式与真实本地链路验收后才启用 capability |
| I3：质量与模块推广 | 完成预登记的分科段级/讲解人工审核和性能验收；再逐批复用到阅读、书内聊天、课程资源、题库/笔记来源 | 技术正确性与教学质量分别过门槛；可回滚、数据引用可恢复；不把节级 Hit@5 当解释正确率 |

实施次序（**2026-09-23 更新**）：宿主加固已完成；RAG 侧 P8A/P8C 已交付并进入**候选冻结**，宿主侧 I0 契约已完成。**当前不得启动** P8A 返工、模型实验、索引重建或 I1 真实接入——需用户明确解除冻结范围并确认上游停止写入后再定接入形态。R-13、动画、其他供应商继续独立登记。

（2026-09-22 原文，已过期，保留为历史：实施次序建议：立即宿主加固 + RAG P8A；随后 I0/I1 提供真实可见价值，I2 打通追问；课程会话可在独立文件内推进。不得据该旧建议自动启动 P8A 或任何模型实验。）

发布前的总验收仍包含原 H1–H7 范围；RAG 不替代缺失页面、动画或一般附件解析。主题/最终整合按用户既定 `feat/glass-theme` 分工进行；本次只在 main 记录审查和方案，合并操作另按用户指令执行。

## 7. 历史保留与接手方式

- [2026-09-15整理前完整STATUS](archive/DELIVERY_HISTORY.md#snapshot-status-20260915)：保留原R-01~13首败、模型38条/旧授权任务卡、6.1~6.10全文、测试数差异、真实服务与.env事件。旧章节号引用解释为此快照，不能当新任务入口。
- 2026-09-18 B-R05-SPACE-VISUAL v1 由外部队长在 ZCode 会话实施：子代理环境不可用（思考档位缺失）按协作提案降级为队长串行实施+黑盒自查留证，文件归属/提交/Git 仍按任务卡执行。
- [旧团队提示词](archive/PROMPT_HISTORY.md#snapshot-collaboration-20260915)、[旧接手入口](archive/PROMPT_HISTORY.md#snapshot-next-session-20260915)仅供追溯；[归档清单](archive/MANIFEST.json)记录来源提交、原始与规范化SHA256。
- 模型D1–D16稳定决定仍在 [PROJECT_GUIDE](PROJECT_GUIDE.md)，API和ROUTES仍维护现行契约；不因模型批历史归档删除功能范围。
- 新Agent从 [NEXT_SESSION_START](replica/NEXT_SESSION_START.md) 与 [团队协作提示词](MULTI_AGENT_COLLABORATION_PROPOSAL.md#队长启动提示词) 开始，先核对 [当前批次](#current-task) 是否已交付。明确授权且未完成才实施；已交付时接手现状并按用户新任务推进，不重做MODEL-EXEC/P0或旧视觉批，不等待Codex代写已授权代码。
- 产品能力和历史状态均有局限，不以批次pass、代码行数、测试总数推算产品完成率。
