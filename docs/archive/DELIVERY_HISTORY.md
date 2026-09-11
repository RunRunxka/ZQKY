# 历史合并归档：DELIVERY_HISTORY.md

归档日期：2026-09-08。以下为过去记录原文，含已作废目标、旧状态与旧提示词，**不是当前执行指令**。当前目标见 [项目说明](../PROJECT_GUIDE.md)，当前进度见 [STATUS](../STATUS.md)。

原文件字节哈希见 [MANIFEST.json](MANIFEST.json)，保留原文内容、换行按仓库规范转为 LF；旧相对链接按原文件所在目录理解。完整原路径版本可从 Git 基线 b8cf71f 查看。

<a id="source-1"></a>

## 原文件：docs/TASKS.md

<!-- BEGIN ORIGINAL docs/TASKS.md -->
# 当前任务清单

## 当前状态：S3、S4、S5-A、S5-B、S5-C、S5-D 已完成（2026-09-08），按用户指令暂停，恢复后推进 S5-E→I →S6→S7→S8

S5 批次 D「沉浸阅读」完成：/reading（集合列表+演示载入+新建/删除）、/reading/materials（文本材料库+分配/删除级联）、/reading/[workspaceId]（三栏工作区：材料 Tab+大纲/书签/批注导航+文本阅读器（quote 批注高亮/滚动进度保存恢复/选区浮条 高亮五色·笔记·书签·问 AI）+伴生模拟 AI（显式【模拟回复】+replaceState 会话深链））、/reading/[workspaceId]/sessions(/[sessionId])（会话深链）。新建 `reading-store.ts`（五库+事件订阅）、`notebook-store.ts` 扩展 `createNotebookRecord`（发到笔记本真实跨页写入）。正式单测 **206/206**、全量 e2e **92/92**（87 基线 + 5 项 `reading.spec.ts`，默认 `test-results/`）、typecheck/lint/build 通过（30 路由含 5 新增）。矩阵：实现待验收 22、待实现 25（含本次补正 S5-B 时漏改的 knowledge/notebooks 四条目行）。**用户指令：S5-D 完成后暂停，不自动进入 S5-E。**

S5-C 批次记录（历史）：/books（目录+统计+演示载入+新建模拟提案+状态化 CTA）、/books/[bookId]（hub-and-spoke：提案确认→大纲确认→同步模拟编译→阅读器，自动续读/重建/导出）、/books/[bookId]/pages/[pageId]（Block 子集渲染+翻页/键盘/书签/已读进度+无效页码报错）、/courses（进行中+归档折叠+新建；主导航按参考隐藏）、/courses/[courseId]（大纲 covered 手判+资料跨目录附加"不可用"态+约定+编辑/归档）。新建 `books-store.ts`/`courses-store.ts`。单测 197/197、e2e 87/87。关键排障：e2e 中未处置的悬挂下载对象会压垮 headless Edge（下载必须 saveAs/cancel）。

下一步（待用户指示恢复）：S5-E 写作/whisper → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户 → S6 设置整合 → S7 视觉动画三视口 → S8 最终验收交付 FINAL_ACCEPTANCE.md。真实供应商/MCP/Skills/解析/STT 未验证。

前几轮（S5-B/S5-A/S4/S3）记录：S5-B 教材资料库/笔记本（登记仅元信息、默认笔记本虚拟项），e2e 81/81、单测 188/188；S5-A /space 六路由+会话归档+跨模式深链，77/77、178/178；S4 四大能力模拟闭环 69/69、164/164；S3 多标签工作区 65/65、157/157。详见 replica/HANDOFF.md 历史节。

本轮仅审查、探针和文档；日志/截图在 _work/review-s2-s3-20260908。未提交Git、未动参考和真实数据。以下为历史报告，旧计数与“下一动作”不作为当前指令。

## 历史记录：2026-09-07 FINAL 首批执行（历史快照，状态以当前源码为准）

| 批次 | 状态 | 结果 |
| --- | --- | --- |
| S0 R11–R16 | 已完成（历史） | 身份守卫/统一投影/预览补全/等待权/互斥/动画依据；探针 7/7+1/1，单测 114，e2e 38/38；teardown 未复现根因未知 |
| S1 规格与矩阵 | 部分完成（历史） | 框架完成（三矩阵稳定 id+状态词汇+证据）；页面规格未逐页补齐，不能记“S1 全部完成” |
| S2 深链切片 | 已完成（历史） | /chat/[sessionId] 定位+无效提示；R17 新建/切换不回跳；URL 同步已在收尾批补齐 |
| S2 完整输入区等 | 未完成 | 业务模式/附件/persona/语音/首次发送过渡——下一条可执行动作见 replica/HANDOFF |
| S3–S8 | 未完成 | 消息/产物工作区、复杂能力模拟、全部业务页面、设置整合、视觉验收、FINAL_ACCEPTANCE |

真实服务验证边界不变：真实供应商/真实 MCP/Skills 未调用。详见 docs/replica/HANDOFF.md 最新一节。

## 2026-09-07 追问卡片与同轮续答（复刻阶段，已完成）＋R10 修复

| 事项 | 状态 | 结果 |
| --- | --- | --- |
| R10 外部点击监听 | 已修复 | 条件写反导致打开时不监听；修正+正式回归（组件级+e2e）；R5–R9 探针复跑通过 |
| wait-user 结构化事件 | 已完成 | interactionId/intro/questions/status；preview 只读→waiting 开放；同 id 就地更新不覆盖草稿 |
| submitReply 统一接口 | 已完成 | 模拟挂起点唤醒同轮；真实显式 REPLY_NOT_SUPPORTED；submissionId 幂等 |
| 追问卡交互 | 已完成 | 单选跳下一未答/多选不前进/自由文本互斥/上下题导航/跳过/提交锁定/失败保留重试/已答摘要/中断只读 |
| 主输入框同轮回答 | 已完成 | 等待时路由同一接口；空输入显示停止（取消等待） |
| 状态与恢复 | 已完成 | 取消/终态/刷新中断标记；草稿答案随会话持久化；旧历史兼容；revision 保留 |
| 验证 | 已完成 | typecheck、lint 0 警告、单测 107（基线 95）、build、e2e 38（基线 32）全过；探针 R10+R5–R9 全过；chat-motion teardown 3 连跑未复现超时（如实记录） |

未做：产物工作区、mastery 新轮问答、真实 ask_user 通道、390px 追问长文本专项人工复核。详见 docs/replica/HANDOFF.md 最新一节与 docs/replica/NEXT_PHASE_ASK_USER.md。

## 2026-09-07 扩展审查修复（R5–R9，已完成）

docs/replica/REVIEW_EXTENSIONS_2026-09-07.md 的 R5–R9 已全部修复，先探针复现后修复，场景迁移正式测试：

| 问题 | 状态 | 修复 |
| --- | --- | --- |
| R5 再选历史复活 streaming/running | 已修复 | `normalizeLoaded()` 统一 init 与 selectConversation 恢复语义；保留数据不重放 |
| R6 390px 工具栏溢出 | 已修复 | 已选扩展独立换行区、长名称省略、说明横排、发送常驻；390/1440/1920 断言+截图 |
| R7 收起详情可聚焦 | 已修复 | 详情 `inert={!open}`；收起时焦点回头部；动画保留 |
| R8 无退场动画/缓动混淆 | 已修复 | 菜单 160ms 进出场（原版参数）；`--ease-standard` 区分过程展开缓动；录像+定格帧人工查看 |
| R9 打开菜单绕过发送禁用 | 已修复 | 发送开始自动关闭菜单+选项禁用；键盘路径回归覆盖 |

验证：typecheck、lint 0 警告、单测 95（基线 93）、build、e2e 32（基线 26）全过；独立探针修复后 2/2+4/4。未验证：真实供应商/真实 MCP、`test:api`（后端零改动）。详见 docs/replica/REVIEW_EXTENSIONS_2026-09-07.md 修复记录。

## 2026-09-07 聊天扩展目录联动＋工具过程面板（复刻阶段，已完成）

| 事项 | 状态 | 结果 |
| --- | --- | --- |
| 事件契约判别式联合 | 已完成 | tool 事件必带 callId/kind/name/status；增量必带数据；真实 SSE 协议未变 |
| 扩展目录接入（模拟） | 已完成 | ExtensionPicker 复用 extension-catalog 单一来源；分区/搜索/选中态/管理链接；失效选择提示移除 |
| 快照冻结与重试 | 已完成 | 发送冻结快照随消息持久化；重试沿用原快照；目录变化只影响后续发送 |
| 模拟执行场景 | 已完成 | 无/单/多扩展、技能上下文加载、一次工具失败（MOCK_TOOL_ERROR）、执行中取消，确定性脚本 |
| 工具过程面板 | 已完成 | callId 去重、手动展开态固定、安全 Markdown 详情、收尾不留运行中、历史恢复不重放 |
| 动画与可访问性 | 已完成 | 300ms/160ms 已登记 token；减少动画全局接管；Escape/焦点恢复/可访问名称；手机布局 |
| 验证 | 已完成 | typecheck、lint 0 警告、单测 93（基线 77）、build、e2e 26（基线 22，含手机截图）全部通过 |

未做：真实供应商验证、真实扩展执行/安装/授权/检测、录屏、追问、产物工作区。范围外未动：教案、依赖版本、数据库。详见 docs/replica/HANDOFF.md 最新一节。

## 2026-09-07 聊天审查修复（R1–R4）

docs/replica/REVIEW_2026-09-07.md 的 R1–R4 已全部修复并验证，未进入新功能开发：

| 问题 | 状态 | 修复 |
| --- | --- | --- |
| R1 组件卸载未取消生成 | 已修复 | ChatProvider cleanup 幂等 dispose 两个 store（取消+保存），兼容 StrictMode；不依赖 pagehide |
| R2 固定模式 store 读两库 | 已修复 | 单一 `repository` 注入（mock 默认库 `zhiqikeyuan-chat-mock` 不变）；真实库挂起不阻塞模拟 store；跨模式同 ID 隔离 |
| R3 终态后过程事件改写消息 | 已修复 | generation token 增加 terminal；end/error/取消/断流后拒绝 stage/process/usage 等后续事件 |
| R4 隔离测试断言无关对象 | 已修复 | 注入被测 spy 仓储/服务再断言；复现探针迁移为正式回归并扩充用例 |

验证：typecheck、lint（0 警告）、单测 77（基线 68）、后端 84、构建、e2e 22（基线 21，新增浏览器卸载取消回归）、`_work/review-chat` 独立探针 4 项，全部通过。真实供应商未验证（本轮不涉及）。“事件类型判别式联合”留待下一轮。详见 docs/replica/HANDOFF.md 最新一节。

## 2026-09-06 当前增补

问答流式生命周期、会话存储安全、输入输出 UI、按连接的完整问答模型管理、发现/参数/默认模型/统一选择器已实现。检查：54 前端、78 后端、17 常规浏览器、6 网络集成通过，类型/Lint/构建/模板校验通过。[完整 review 与截图](CHAT_MODEL_REVIEW.md)。真实供应商流式验收待可用凭证；不将旧 D04 的“已完成”解释为供应商验证完成。

下表保留阶段性历史记录，测试数字不是当前累计值。后端当前已运行实现，D05–D09 未因本次任务自动开展。

### 本次任务明细：问答修复与 DeepTutor 式模型管理

| 任务 | 状态 | 本次结果 |
| --- | --- | --- |
| D01–D04 已有实现 review | 已完成 | 记录流式验证不足、会话串写/丢失、重试覆盖、存储事务与版本、上游错误回显等问题及处理 |
| 三协议流式与取消修复 | 已实现，隔离验证通过 | 真实 HTTP 上游→FastAPI→Next→浏览器链路；末块未释放前显示首段中文，停止关闭上游 |
| 会话生命周期与重试 | 已完成 | 请求绑定会话/消息；切换停止保存；保留部分回答，重试不重复追加用户问题 |
| 本地会话持久化 | 已完成 | 合并串行保存、事务完成、revision 冲突保护；保存草稿/模型，刷新恢复中断；存储失败保留内容 |
| 问答输入输出 UI | 已完成 | 教案白灰蓝风格；Markdown、数学公式、表格、代码高亮与复制；自动增高输入框、阅读跟随、手机抽屉 |
| 导航顺序 | 已完成 | 学习问答第一、教案第二；默认首页仍为教案 |
| 连接与问答模型管理 | 已完成 | 三分区、按连接分组、搜索/展开/编辑/删除、凭证状态和关联删除保护 |
| 模型发现与参数 | 已完成 | 服务发现、多选追加、去重、手动添加；保留已有配置，保存实际参数，不推断能力 |
| 默认模型与共用目录 | 已完成 | 全局默认、会话选择优先、统一分组选择器；模型失效不静默换供应商 |
| 测试证据与保存冲突 | 已完成 | 普通/流式测试分开，版本变化不写回旧证据；提交锁、失败反馈、冲突保留表单 |
| 自动化与视觉复核 | 已执行 | 54 前端、78 后端、17 常规浏览器、6 网络集成；类型/Lint/构建/模板校验通过；1440/1024/390px 截图 |
| 文档和交接 | 已完成 | review、API、DECISIONS、IMPLEMENTATION_PLAN、HANDOFF、TASKS、README 与当前规范更新；前后截图存档 |
| 用户实际供应商流式验收 | **待完成** | 缺可用进程凭证；隔离测试不等于实际供应商故障已解决 |
| 补充浏览器边界验收 | 待完成 | 发现超时/空列表、完整双标签 UI 冲突及全部触控组合；现有覆盖边界见 review |

验证命令与接手步骤见 [HANDOFF.md](HANDOFF.md)，问题清单和截图见 [CHAT_MODEL_REVIEW.md](CHAT_MODEL_REVIEW.md)。本次仅补写任务文档，不把此前测试记作重新执行。未提交、推送、部署，未开展 D05–D09。

## 历史阶段记录

更新：2026-09-06。状态按实际实现和本次验证记录。

| 任务 | 状态 | 结果 |
| --- | --- | --- |
| 正式npm工作区和Next.js工程 | 已完成 | 根目录统一命令，apps/web为唯一前端工作区 |
| 教案迁移与组件拆分 | 已完成 | 公共壳与教案业务分离，原界面关系保留 |
| 实例状态与草稿保存 | 已完成 | 原格式兼容、串行写入、离开路由前刷新 |
| 导出与打印隔离 | 已完成 | Word结构检查和PDF实际生成通过，其他页面打印不受影响 |
| 开发规范和交接 | 已完成 | 根、前端、教案分层AGENTS.md及文档 |
| 冻结旧版与原件保护 | 已完成 | 仅新增ARCHIVED.md；源模板校验通过 |
| 本地Git初始化 | 已完成 | 未创建提交或远程，未推送 |
| Codex沙箱权限修复 | 已完成 | 恢复.git根目录所有者；普通沙箱读写恢复，209个Git文件内容校验无变化 |
| 类型、Lint、单元和生产构建 | 已完成 | 15项单元测试；生产构建通过 |
| 浏览器回归 | 已完成 | 7项场景通过，隔离端口和浏览器上下文 |
| 后端、部署目录与接口规划 | 已完成 | 只有说明文档，没有运行服务 |
| Agent工作台完整开发计划 | 文档已完成 | IMPLEMENTATION_PLAN含D01–D09、接口草案和AI任务包；业务未实施 |
| D01 统一模块导航与规划页面 | 已完成 | 新增组卷/题库/模板中心/Agent/MCP/Skills等入口，全部规划页可达；教案保持可用；23项单元+12项浏览器测试通过 |
| D02 精简后端和接口骨架 | 已完成 | FastAPI health/capabilities真实实现+501占位+来源检查；前端同源代理与HTTP适配器；18项后端pytest、29项前端单测、12项e2e通过 |
| D03 统一模型调用与模型设置 | 已完成 | 三协议Provider适配层+模型设置页+连接测试；52项后端pytest、32项前端单测、13项e2e通过；真实供应商验收待用户提供凭证 |
| D04 真实学习问答 | 已完成 | /chat流式对话+会话历史(IndexedDB)+停止/重试；68项后端pytest、47项前端单测、18项e2e通过；经代理流式不缓冲实测；真实供应商验收待凭证 |
| 新对话发送静默失败排查与首页调整 | 已完成 | 根因=默认模型凭证失效+ready竞态导致静默丢弃；send等待初始化、受阻提示即时反馈；首页默认改为学习问答；55项前端单测、17项e2e通过 |
| EMPTY_RESPONSE 诊断增强与推理过程展示 | 已完成 | 三适配器识别 reasoning_content/thinking 并差异化报错；reasoning.delta 透传+前端折叠展示；84项后端pytest、56项前端单测通过 |
| replica 统一聊天事件服务＋最小模拟闭环 | 已完成 | ChatService 统一事件模型（真实SSE+本地模拟）；模拟会话独立存储与标识；停止/重试/隔离/刷新恢复验证；68项前端单测、21项e2e通过；真实供应商未验证 |
| 用户界面复核 | 待反馈 | 用户可在原地址查看正式版本 |
| Word/WPS人工版式验收 | 待完成 | 结构检查不代替实际排版检查 |
| 多教案列表和服务端草稿 | 未开始 | 单独立项，需文档ID与版本冲突方案 |
| 真实AI填充 | 未开始 | 需后端、模型配置、结构校验和确认流程 |
| 账号、资料问答、练习和笔记 | 未开始 | 按原项目规划分阶段实施 |

## 最新开发队列（全部尚未开始）

详细范围与提示词见 [完整开发计划](IMPLEMENTATION_PLAN.md)。下表是开发目标，不替代上面的实际完成记录。

| 任务 | 范围 | 状态 |
| --- | --- | --- |
| D01 | 模块导航、统一状态、规划页面 | 已完成（2026-09-06，见HANDOFF） |
| D02 | 无数据库的精简FastAPI与契约 | 已完成（2026-09-06，见HANDOFF） |
| D03 | 统一Provider、模型设置、凭证与协议测试 | 已完成（2026-09-06，见HANDOFF；真实供应商验收待凭证） |
| D04 | 学习问答真实流式对话和本地历史 | 已完成（2026-09-06，见HANDOFF；真实供应商验收待凭证） |
| D05 | DOCX模板与A3/A4排版验证 | 未开始 |
| D06 | 本地组卷、纸张切换、右侧实时预览 | 未开始 |
| D07 | 模板中心和正式DOCX/PDF导出 | 未开始 |
| D08 | 教案兼容接入共用模板能力 | 未开始 |
| D09 | 集成、真实联调与使用验收 | 未开始 |
| F01–F03 | 真实双库、RAG、教材备课、题库选题、Agent/MCP/Skills | 后续，非本期 |

下一位开发者接收用户指定的一个任务；建议从D01开始，不一次开展所有待办。本期不安装数据库或Redis，学习问答的真实API调用与数据库无依赖关系。

## 2026-09-06 前端复刻首批实施

设置改为分类与锚点内容；MCP、Skills 从主导航收进设置，旧路径重定向。扩展管理为独立本地模拟目录，模型管理保留真实服务。减少动画偏好已实现。完整八阶段尚未完成，实际范围、检查与剩余工作见 docs/replica/HANDOFF.md。

<!-- END ORIGINAL docs/TASKS.md -->

<a id="source-2"></a>

## 原文件：docs/HANDOFF.md

<!-- BEGIN ORIGINAL docs/HANDOFF.md -->
# 正式工程迁移交接

## 当前状态：2026-09-08 独立复核，先修 R19–R25 再连续推进到最终验收

完整前端尚未交付。唯一接续入口是 [replica/NEXT_SESSION_START.md](replica/NEXT_SESSION_START.md)，最新证据是 [replica/REVIEW_S2_S3_2026-09-08.md](replica/REVIEW_S2_S3_2026-09-08.md)。S1 规格部分完成；S2 已实现但有缺陷；S3 基础已有，剩余工作和 S4–S8 未完成。页面矩阵53个非调试条目，4已验收/1实现待验收/2部分实现/46待实现。

本轮实际：typecheck/lint/build、153单测通过；旧终态2/2、URL刷新1/1探针通过；正式e2e **53通过/1个录像context teardown超时**。独立新探针7浏览器+2单元场景复现R19–R25，尚未修产品代码。先修提交清理/真实附件提示、确认门控、会话归属、面板选择、文件并发、产物身份、耗时，再直接继续S3→S4→S5-A至I→S6→S7→S8。真实供应商/MCP/Skills/解析/STT未验证，test:api本轮未执行。

本轮仅审查、探针和文档；日志/截图在 _work/review-s2-s3-20260908。未提交Git、未动参考和真实数据。以下为历史报告，旧计数与“下一动作”不作为当前指令。

## 历史交接：R10 修复＋追问卡片与同轮续答（2026-09-07 傍晚，用户指定）

先修 R10（ExtensionPicker 外部点击监听条件写反，打开时不注册），再实现模拟追问卡片与同轮续答（ask_user 语义：同轮暂停→回答→继续，不另开轮次）。完整记录见 docs/replica/HANDOFF.md 最新一节、docs/replica/NEXT_PHASE_ASK_USER.md 与 REVIEW_EXTENSIONS 修复记录。

- 契约：wait-user 事件结构化（interactionId/questions/status）；`ChatService.submitReply` 可选能力（模拟接受后同轮续写，真实显式 REPLY_NOT_SUPPORTED）；消息新增 `asks`（问题/草稿/答案/状态/逐卡续写正文）。
- 交互：预览→可答、单选跳下一未答题、多选不前进、自由文本、多题导航、跳过、提交锁定、失败保留草稿可重试、已答摘要；主输入框等待时走同一提交接口；同轮两卡只有当前卡可答。
- 状态与恢复：submissionId+submittingReply 幂等；取消/终态/切会话/刷新后卡标记中断不可提交；不重放；旧历史兼容；revision 保留；等待上下文不持久化。

验证（实际执行）：typecheck、lint（0 警告）、`test:unit` 107 项（基线 95）、build、`test:e2e` 38 项（基线 32）全部通过；R10 与 R5–R9 探针全部通过。chat-motion 录像 teardown 超时本轮 3 连跑未复现（复核轮曾出现 1 次，已如实记录诊断边界）。真实供应商与真实 MCP/Skills 未验证；`test:api` 未复跑（后端零改动）。产物目录 `tests/.e2e-output-20260907-askuser2/`。

## 交接：扩展审查 R5–R9 修复（2026-09-07 下午，用户指定）

仅修复 docs/replica/REVIEW_EXTENSIONS_2026-09-07.md 的 R5–R9，不进入新功能。逐条代码依据、探针复现、截图/录像证据与未验证项见该报告“修复记录”一节及 docs/replica/HANDOFF.md 最新一节。要点：历史载入恢复语义统一（R5）、390px 输入区重排（R6）、折叠详情 inert 焦点处理（R7）、菜单退场动画与缓动区分（R8，含 WebM 录像与定格帧人工查看）、发送开始自动关闭菜单（R9）。

验证（实际执行）：typecheck、lint（0 警告）、`test:unit` 95 项（基线 93）、build、`test:e2e` 32 项（基线 26）全部通过；独立探针修复后单元 2/2、浏览器 4/4 通过；390×844、1440×900、1920×1080 均有断言与截图；每轮浏览器测试使用新独立产物目录（…-r5/…-r9/…-r12 等）。真实供应商与真实 MCP/Skills 未验证；`test:api` 未复跑（后端零改动）。下一阶段仍为“追问交互”。

## 交接：聊天扩展目录联动＋工具过程面板（2026-09-07，用户指定复刻阶段）

本次实施 docs/replica/HANDOFF.md 所列“下一轮 B”：模拟扩展接入聊天与消息内工具过程展示。完整修改清单、验证记录与已知限制见 docs/replica/HANDOFF.md 最新一节。要点：

- 事件契约改为 type 判别式联合（tool 事件带 callId/kind/name/status，状态 running/done/error/cancelled）；请求增加本轮扩展快照；真实 SSE 协议未变，快照不发给真实后端。
- 模拟模式新增扩展选择器（MCP/Skills 分区、搜索、管理链接 /settings#mcp、#skills、键盘可达）；发送冻结快照、重试沿用原快照；目录变化只影响后续发送，失效待发送选择明确提示并移除；真实模式明确“未接入”，不自动回退模拟。
- 消息内工具过程面板按 callId 去重更新，手动展开态不被正文增量重置；取消/错误/断流/刷新恢复时运行中卡片一律收尾，不重放历史；过程随会话持久化，旧历史兼容。
- 新增 `ExtensionPicker.tsx`、`ToolProcessPanel.tsx`、`model/extensions-snapshot.test.ts`、`ExtensionPicker.test.tsx`；修改 `chat-service.ts`、`store.ts`、`Message.tsx`、`ChatWorkspace.tsx`、`contracts/chat.ts`、`chat.css`、`tests/e2e/chat-mock.spec.ts`。

验证（实际执行）：typecheck、lint（0 警告）、`test:unit` 93 项（基线 77）、build、`test:e2e` 26 项（基线 22，含减少动画+手机布局闭环与截图）全部通过。已知限制：真实供应商未验证；扩展为本地模拟（无真实安装/授权/联网检测/远程执行）；录屏未完成。下一阶段：追问交互（提示词见 docs/replica/HANDOFF.md）。

## 交接：聊天审查 R1–R4 修复（2026-09-07，用户指定）

任务：仅修复 docs/replica/REVIEW_2026-09-07.md 的 R1–R4，不进入新功能开发。详见该报告“修复记录”与 docs/replica/HANDOFF.md 最新一节。

- R1：ChatProvider 承担唯一卸载清理责任（cleanup 中对两个聊天 store 幂等 dispose，取消生成+冲正保存），客户端路由卸载与浏览器返回不再依赖 pagehide；兼容 React StrictMode。修改 `apps/web/src/features/chat/model/ChatContext.tsx`、`ChatWorkspace.tsx`（移除重复 effect）。
- R2：固定模式 chat store 只实例化/加载/读写自己的仓储；`ChatDeps` 移除 `mockRepository`，mock 默认库仍为 `zhiqikeyuan-chat-mock`（历史数据兼容）。修改 `apps/web/src/features/chat/model/store.ts`。
- R3：generation token 增加 terminal 标志；end/error/取消/断流收尾后拒绝 stage/process/usage 等一切后续事件。
- R4：隔离测试注入被测依赖后断言；复现用例迁移为正式回归（`mock-mode.test.ts`、`ChatWorkspace.unmount.test.tsx`），新增卸载取消（含 StrictMode）、卸载保存、dispose 幂等、初始化互不阻塞、跨模式同 ID、迟到事件、不自动回退模拟用例；`_work/review-chat` 探针按修复后语义改写。新增 e2e 浏览器回归“生成中浏览器返回→取消且内容冻结”（`tests/e2e/chat-mock.spec.ts`）。

验证（实际执行）：`npm run typecheck` 通过；`npm run lint` 通过（0 警告）；`npm run test:unit` 77 项通过（上一基线 68）；`npm run test:api` 84 项通过（后端未改动）；`npm run build` 通过；`npm run test:e2e` 22 项通过（上一基线 21）；`_work/review-chat` 独立探针 4 项通过。接口无变化。未执行项：真实供应商验收仍待用户在设置页重填凭证后完成；“事件类型判别式联合”改造留待下一轮。e2e 本次以 `--output=tests/.e2e-output-20260907` 运行（沙箱批量删除守卫拦截旧 `test-results/` 清理；该目录已加入 .gitignore，既有产物未动）。

下一阶段：聊天扩展目录联动＋工具过程面板（提示词见 docs/replica/HANDOFF.md 最新一节）。

## 交接：新对话发送静默失败排查 + 首页默认学习问答（2026-09-06，用户指定）

任务ID：无编号（用户直接指定的排查与调整；基于上一节完成模型管理重构后的代码）。

现象：新建对话后发送，有概率不显示模型回复。

根因（已复现与验证，非流式竞态）：

1. **默认模型凭证失效 + 静默返回**：`defaultChatProfileId` 指向的连接凭证只存后端进程（D03 既定决策），后端重启即失效。此时 ChatPage 的 `selection=null`（`valid` 要求 `hasCredential`），`submit()` 静默返回——按 Enter 后消息不进列表、草稿不清空、无任何反馈。旧会话若显式选过可用模型则正常，因此表现为“新建对话才有概率失败”。后端重启/凭证补填都会改变现象，形成“有概率”观感。
2. **`ready` 竞态**：页面刚加载 `init()` 未完成时 `send()` 因 `!get().ready` 静默丢弃。

修复（不做静默模型回退，沿用“不静默改用其他供应商”决策）：

- `apps/web/src/features/chat/model/store.ts`：`init` 逻辑抽为 `runInit()`（memoized 不变）；`send` 在未就绪时 `await runInit()` 后重查守卫（已就绪时保持原同步语义，lifecycle 测试不受影响）。
- `apps/web/src/features/chat/ChatWorkspace.tsx`：`submit()` 发送受阻时（缺凭证/未选模型/目录读取中/目录读取失败）在输入框旁即时显示原因 + “打开设置”入口（`.chat-blocked-notice`，selection 恢复有效时自动清除）；草稿保留。
- `apps/web/src/app/page.tsx`：根路径 `/` 改为跳转 `/chat`（用户指定“首页默认学习问答”）；品牌按钮行为未变（仍回教案工作台）。
- 测试与文档：`store.test.ts` 新增“初始化未完成时发送会等待”回归；`lesson-plan.spec.ts` 首页断言改为 `/chat`；README、ROUTES、DECISIONS 同步。

验证：压测脚本（`_work/stress-chat.mjs`，模拟流式上游）原环境 10/10 复现“无回复”，默认指向有效模型后 10/10 成功；修复后浏览器实测缺凭证时 Enter 显示“当前模型缺少凭证，请到设置补充后重试。”且草稿保留（`_work/fix-blocked-notice.png`），有效模型下新对话发送成功。前端 55 项单测、`typecheck`、`lint`（0 警告）通过；`test:api` 78 项未受影响。

未执行项：真实供应商验收仍待用户在设置页为 deepseek 连接重新填写凭证（后端重启会丢失，属 D03 决策范围）后完成一次真实对话。

给用户的操作提示：打开设置页 → deepseek 连接 → 重新填写 API Key 并保存，问答即可正常使用；也可以把默认问答模型改为任一“有凭证”的模型。

补充（同日用户报告“模型未返回正文（EMPTY_RESPONSE）”）：排查确认该错误来自 Provider 流干净结束但零正文的判定。三种触发形态（推理模型把内容放进 reasoning_content、输出预算在推理阶段耗尽、兼容服务返回分块式 content）此前要么误报要么诊断不可操作。修复：三适配器识别推理增量并以 `reasoning.delta` 事件透传（前端在消息内折叠展示推理过程，不算正文）；EMPTY_RESPONSE 按“推理耗尽预算 / 仅推理内容 / 纯空响应”给出含当前输出上限的可操作文案；正文兼容分块形态。前端 store 增加 reasoning 累积。`test:api` 84 项、`test:unit` 56 项通过；事件协议与错误码已更新至 docs/API.md。真实 deepseek 触发路径未复现（无进程内凭证），已用模拟上游覆盖三种形态。

## 交接：问答流式修复与完整问答模型管理（2026-09-06）

已完成当前用户批准范围的实现：三协议流生命周期、会话安全保存和重试、Markdown/公式输出、DeepTutor v1.6.4 式连接分组模型管理/发现/默认/统一选择器、移动端布局与抽屉。详见 [review、截图和验收](CHAT_MODEL_REVIEW.md) 与 [接口增补](API.md)。

当前实际结果：前端 54 单测、后端 78 测试、17 常规浏览器用例、6 真实网络隔离集成用例通过；类型/Lint/构建/模板校验通过。真实供应商验收未执行，当前没有可用进程凭证；不能把模拟结果视为用户供应商故障已解决。

启动沿用 `npm run dev:api` 和 `npm run dev`，设置页先补凭证。无数据库、RAG、附件或工具。原教案/Word 保留，不自动提交。下方是此前 D04 的历史记录，其中测试数量、纯文本输出、能力和 start 时机以本次记录与源码为准。

### 本次修改与接手入口

| 范围 | 已做修改 | 主要源码 |
| --- | --- | --- |
| 流式调用 | 上游连接建立后发送 start；三协议增量转发、空回答/断流/截断处理、错误脱敏；停止关闭上游连接 | `apps/api/app/providers/llm/`、`apps/api/app/api/v1/chat.py`、`apps/web/src/services/chat-stream.ts` |
| 会话与历史 | 请求绑定会话和消息 ID；新建/切换先停止保存；重试保留部分回答；串行合并写入、事务完成确认、版本冲突保护、输入草稿及刷新中断恢复 | `apps/web/src/features/chat/model/store.ts`、`apps/web/src/services/chat-repository.ts` |
| 问答页面 | 可折叠会话栏、收起详情、自动增高输入区、统一模型选择、阅读跟随控制；Markdown/公式/表格/代码高亮与复制；移动端 dialog | `apps/web/src/features/chat/`、`apps/web/src/components/ui/Modal.tsx` |
| 模型管理 | 连接分组卡片、搜索、手动添加、发现多选追加和去重；参数编辑、默认问答模型、普通/流式测试分离；表单提交锁与冲突内容保留 | `apps/web/src/features/model-settings/`、`apps/api/app/api/v1/model_catalog.py`、`model_profiles.py`、`model_connections.py` |
| 公共壳与安全 | 学习问答第一、教案第二，首页不变；修正手机布局；忽略 `.local-data/`，限制附加请求头，凭证不回显 | `apps/web/src/services/navigation.ts`、`apps/web/src/styles/globals.css`、`.gitignore` |

接口增补：`GET /api/v1/model-catalog`、`GET /api/v1/model-connections/{id}/models`、`PUT /api/v1/model-defaults`；模型配置增加实际 `params`，删除支持预期版本，测试增加 `stream` 选项及首末文本时序。详见 [API.md](API.md)。保留原连接、模型、聊天接口和本地数据，不新增第二套后端。

### 实际运行与验证

以下是本次实现期间实际执行结果，本次补写文档没有重跑业务测试：

- `npm run typecheck`、`npm run lint`、`npm run build`：通过。
- `npm run test:unit`：54 项通过；`npm run test:api`：78 项通过，1 条依赖弃用警告。
- `npm run test:e2e`：17 项通过，含教案导航、草稿、Word/PDF 导出回归。
- `npm run test:chat`：6 项通过。三协议均在模拟上游末块尚未释放时，浏览器已显示首段中文；停止验证实际上游断开。另含模型发现追加、默认模型、版本冲突与响应式检查。
- `npm run template:verify`：original/source 均 true。

隔离测试端口为 5174/8001/8002，使用临时配置和独立浏览器上下文；构建目录 `.next-test` 与正式 `.next` 分开。测试及旧截图预览服务已关闭，没有保留模拟服务供日常使用。前后截图位于 `docs/qa/chat-models/`，完整说明见 [CHAT_MODEL_REVIEW.md](CHAT_MODEL_REVIEW.md)。

### 待接手事项与限制

1. **补做用户实际供应商验收**：在运行的后端进程中重新填写凭证，分别做普通测试、流式测试、长中文问答、停止和重试。现有结果不能证明用户“等待后一次性显示”的供应商根因已解决。
2. 发现超时/空列表、全部移动触控组合尚未逐一完成浏览器验收；双标签竞争使用两个仓储实例验证事务冲突，并非完整双标签 UI 用例。
3. 应用内导航等待保存；浏览器强制退出仍可能丢失最后 400ms 尚未提交内容。存储失败时保留页面内容并允许备份，不静默覆盖。
4. D05–D09、数据库、RAG、附件、工具及未来任务模型分配未开展；没有 Git 提交、推送或发布。原教案草稿和 Word 模板保留。

更新：2026-09-06。项目根当前为 `H:\备份xuexi\智启课源`（此前文档写 F:\智启课源，以本仓库实际位置为准）；正式前端 apps/web；后端 apps/api；教案业务位于 features/lesson-plan。

## 历史交接：D04 初始实现（2026-09-06）

任务ID：D04。

实际完成范围：按 IMPLEMENTATION_PLAN 第4.2、7、11.4 节与 D04 任务包，实现 `/chat` 学习问答：左侧会话列表（新建/重命名/删除确认）、中间消息与输入区（模型选择、发送/停止、流式显示、失败重试、复制）、右侧信息面板（当前模型与能力、会话信息、RAG/附件/MCP/Skills 如实标注规划中）。后端新增三协议流式适配与 `POST /api/v1/chat/stream` SSE 端点。对话历史存浏览器 IndexedDB；未接数据库、未实现 RAG/附件/工具，无假来源。前端导航 chat → `ready`。

修改文件及作用：

- `apps/api/app/providers/llm/base.py`：新增 `LLMStreamEvent`（start/text/usage/end）、`stream()` 统一入口（基类先产出 start，参数与凭证检查在任何事件之前）、`iter_sse`（SSE 行解析，含 CRLF/多行 data/注释）、`open_stream`（建立上游流，非 2xx 抛规范化 ProviderError，finally 关闭连接使取消传播）。
- `apps/api/app/providers/llm/openai_chat.py`、`openai_responses.py`、`anthropic_messages.py`：各新增 `_stream`——openai-chat（stream+include_usage、[DONE]）、openai-responses（output_text.delta/completed/incomplete/failed）、anthropic（message_start/content_block_delta/message_delta/message_stop/error）。
- `apps/api/app/api/v1/chat.py`、`app/schemas/chat.py`（新增）：SSE 端点——先 `__anext__` 推进流（上游 HTTP 失败转换为流前 HTTP 错误），再以 StreamingResponse 输出事件；流中失败发 `error` 事件；`CONTEXT_TOO_LARGE`(413)、`MODEL_NOT_CONFIGURED`(400)、`UNSUPPORTED_PARAMETER`(422)。
- `apps/api/app/api/v1/capabilities.py`：chat → `ready`。
- `apps/api/tests/test_providers_stream.py`、`test_chat_stream_api.py`（新增）：UTF-8 跨块、分块时序、事件顺序、取消传播（任务取消后生成器关闭）、上游 401/429/500/超时映射、端点事件协议与错误路径。
- 前端新增：`src/contracts/chat.ts`（含 `contextBudgetChars`）、`src/services/chat-sse.ts`（SSE 文本解析器）、`src/services/chat-stream.ts`（fetch+ReadableStream+TextDecoder(stream:true)）、`src/services/chat-repository.ts`（IndexedDB + 内存实现）、`src/features/chat/`（ChatWorkspace/SessionPanel/InfoPanel/model/store+ChatContext/context-budget/styles）。
- `src/services/navigation.ts` chat → `ready`；`src/app/chat/page.tsx` 静态页面；`globals.css` 手机端品牌文字不换行（小修）。
- 测试更新：`navigation.test.ts`、`navigation.spec.ts`、`lesson-plan.spec.ts`（学习问答入口名称与页面断言）；新增 `chat.spec.ts` 4 项（流式显示+刷新恢复+截屏、停止、错误保留输入可重试、未配置模型提示去设置）。
- 文档：API（chat/stream 事件协议）、ROUTES、DECISIONS、TASKS、本文件、README、apps/api README/AGENTS。

新增/改变的公共契约：`POST /api/v1/chat/stream`（事件协议见 docs/API.md）；前端 `ChatRepository`、`streamChat`、`createSseParser`、`contextBudgetChars`、chat 导航状态 `ready`。D03 接口未变。

当前可用入口与启动方式：`npm run dev:api` + `npm run dev` 后访问 [http://127.0.0.1:5173/chat](http://127.0.0.1:5173/chat)；需先在设置页配置模型并保存凭证（凭证仅当前后端进程有效）。

实际执行的检查、结果与证据路径：`npm run test:api` 68 项通过；`typecheck`/`lint`(0 警告)/`test:unit` 47 项/`build` 通过；`test:e2e` 18 项通过。集成实测：本机模拟流式上游（`_work/mock-upstream.py`，分块 0.4s 延迟）下，经 5173 代理的 SSE 逐段到达（0.04/0.44/0.84/1.24/1.64/2.05s），**代理未缓冲**；浏览器→代理→后端→模拟上游真实链路截图 `_work/chat-real-1440.png`、`chat-real-390.png`（手机无横向溢出）；未配置凭证的连接发送时准确报 `MODEL_NOT_CONFIGURED` 并可重试。

未执行的检查及原因：**真实供应商流式对话与停止的真实验收未执行**——未获授权的真实 API 凭证；协议行为由 MockTransport 与本机模拟上游覆盖，接入凭证后需补做（发送、中文流式、停止、断线重试）。数学公式/Markdown 富渲染未实现（纯文本范围，见 DECISIONS）。

数据兼容与回退说明：对话数据在浏览器 IndexedDB（新库 `zhiqikeyuan-chat`），不影响教案 localStorage 草稿；后端 `.local-data/model-config.json` 结构未变。回退只需删除新增文件并还原 navigation/capabilities/lesson-plan.spec 小改动。

仍为规划中的能力：RAG 与教材来源引用、附件/图片解析、MCP、Skills（页面内如实标注）；组卷、模板中心、教材库、题库等导航仍为规划页。

已知问题：无阻塞问题。Windows 后台停 npm 包装进程后子进程可能残留监听端口（同 D02/D03 记录）；后端日志中能看到 e2e 运行时若 8000 被占用产生的代理拒绝日志，属预期。

下一任务与前置条件：D05 DOCX 与 A3/A4 排版验证（前置 D02/D04 已满足；不依赖模型凭证，可与真实供应商验收并行补做）。

## 交接：D03 统一模型调用与模型设置（2026-09-06）

任务ID：D03。

实际完成范围：按 IMPLEMENTATION_PLAN 第7节与 D03 任务包，在后端建立三协议供应商适配层（openai-chat / openai-responses / anthropic-messages，工厂按协议实例化，其余协议明确 `UNSUPPORTED_PROTOCOL`）、模型连接与模型配置 CRUD、真实连接测试接口、进程内凭证存储与本地 JSON 配置仓储；前端 `/settings` 由规划页替换为真实设置页（模型连接/模型配置/测试/其余设置组规划中）。未接数据库/Redis；未实现对话接口（D04）、模型列表自动发现、磁盘加密凭证。

修改文件及作用：

- `apps/api/app/providers/llm/`（新增）：`base.py` 统一 Provider 基类（参数能力校验、凭证检查、`post_json` 错误规范化与脱敏）、`openai_chat.py`、`openai_responses.py`、`anthropic_messages.py` 三适配器、`factory.py`。参考 DeepTutor v1.6.4（固定提交 `93df3d48…`，Apache-2.0）接口设计，自有实现未复制代码。
- `apps/api/app/core/secrets.py`（新增）：进程内 SecretStore，只写入/has/delete，无读取明文出口。
- `apps/api/app/repositories/model_config_repository.py`（新增）：单文件 JSON 仓储，`threading` 串行、临时文件+`os.replace` 原子写、全局 revision、`expectedRevision` 冲突 409、损坏文件报 `CONFIG_CORRUPTED` 不覆盖。
- `apps/api/app/schemas/model_config.py`、`model_requests.py`（新增）：连接/配置实体、协议与参数枚举、Base URL 安全校验（公网必须 https，http 仅回环）、请求头白名单校验。
- `apps/api/app/api/v1/model_connections.py`、`model_profiles.py`、`model_views.py`（新增）：CRUD + `POST /model-profiles/{id}/test`（上游成败均返回 200 `ok:true/false`，成功后 `chat` 证据→`verified`）；响应脱敏（无 apiKey、extraHeaders 只回名称）。
- `apps/api/app/core/exceptions.py`（新增）、`main.py`、`core/config.py`（新增 `data_dir`，默认项目根 `.local-data/`）、`api/v1/capabilities.py`（新增 `model_settings=ready`，chat 保持 planned 并更新说明）。
- `apps/api/tests/test_providers.py`、`test_model_settings_api.py`、`test_model_config_repository.py`（新增）+ 原测试更新：共 52 项。
- 前端新增 `src/contracts/model-settings.ts`、`src/services/model-settings-api.ts`、`src/features/model-settings/`（ModelSettingsPanel/ConnectionForm/ProfileForm + 模块级 CSS）；`src/app/settings/page.tsx` 替换动态规划路由匹配；`services/api-client.ts` 支持 204；`services/navigation.ts` settings → `ready`。
- 测试更新：`services/navigation.test.ts`、`tests/e2e/navigation.spec.ts`（设置不再标规划中）；新增 `tests/e2e/settings.spec.ts`（后端不可用时的准确错误）。
- 文档：API、ROUTES、DECISIONS、TASKS、本文件、根 README、apps/api README/AGENTS。

新增/改变的公共契约：HTTP model-connections / model-profiles / test 接口（见 docs/API.md）；错误码新增 `UNSUPPORTED_PARAMETER`、`UNSUPPORTED_PROTOCOL`、`MODEL_NOT_CONFIGURED`、`UPSTREAM_*`、`RATE_LIMITED`、`CONFLICT`、`REVISION_CONFLICT`、`CONFIG_CORRUPTED`；前端 `ModelProtocol`/`ModelConnectionView`/`ModelProfileView`/`ModelTestResult` 等契约与 `settings` 导航状态 `ready`。

当前可用入口与启动方式：`npm run setup:api`（首次）→ `npm run dev:api` 启动后端 → `npm run dev` 启动前端 → 访问 [http://127.0.0.1:5173/settings](http://127.0.0.1:5173/settings)。凭证仅当前后端进程有效，重启后重新填写。

实际执行的检查、结果与证据路径：`npm run test:api` 52 项通过（协议请求形状/中文/取消/超时/鉴权/限流/不支持参数/工厂/仓储/接口脱敏与冲突）；`typecheck`、`lint`（0 警告）、`test:unit` 32 项、`build`、`test:e2e` 13 项全部通过。集成实测（127.0.0.1:5173 代理 → 8000）：创建连接响应 `hasCredential=true` 且无密钥回显；`test` 接口对真实 httpx2 客户端 + 本机协议模拟上游（`_work/mock-upstream.py`，仅测试用）返回 `ok:true`、中文往返、latencyMs；配置文件（`.local-data/model-config.json`）不含凭证明文；截图 `_work/settings-1440.png`、`settings-390.png`、`test-results/settings-*/settings-backend-down.png`。

未执行的检查及原因：**OpenAI / Anthropic 等真实供应商连接验收未执行**——未获用户授权的真实 API 凭证；协议行为已由 MockTransport 与本机模拟上游覆盖，接入真实凭证后需补做“真实连接验收”。模型列表自动发现未实现（手动 model ID 已支持）。Word/WPS 人工版式验收不涉及。

数据兼容与回退说明：草稿键、教案模块、D01 导航结构未动（settings 除外，按计划转正）；`.local-data/` 仅新增数据目录且已 gitignore。回退只需删除新增文件并还原 navigation/capabilities 相关小改动。

仍为规划中的能力：学习问答对话（D04 将在本次适配层上实现 `/chat/stream`）、组卷、模板、教材库/题库/RAG、Agent/MCP/Skills；设置页内的相应分组如实标注。

已知问题：无阻塞问题。Windows 后台停 npm 包装进程后 uvicorn/next 子进程可能残留（同 D02 记录）；`.local-data` 损坏时后端拒绝启动并提示备份修复，不会自动覆盖。

下一任务与前置条件：D04 真实学习问答（前置 D03 已完成；需要 `/chat/stream` SSE、IndexedDB 会话存储与真实模型凭证）。

## 交接：D02 精简后端与接口骨架（2026-09-06）

任务ID：D02。

实际完成范围：按 IMPLEMENTATION_PLAN 第5、6、11节与 D02 任务包，在 apps/api 建成可运行 FastAPI 服务：真实 `/api/v1/health` 与 `/api/v1/capabilities`（10 项能力全部如实 `planned`）、统一错误信封、本机 Host/Origin 访问防护、其余 `/api/v1/*` 一律 501 `FEATURE_NOT_IMPLEMENTED`。前端建立 Next 同源代理、手写契约与 HTTP 适配器。没有接入任何数据库/Redis/模型凭证，没有新增 Next 业务 Route Handlers，未动教案与冻结目录。

修改文件及作用：

- `apps/api/pyproject.toml`、`uv.lock`、`.python-version`（3.12）、`.env.example`：依赖与配置基座。锁定 fastapi 0.141.1、uvicorn 0.52.4、pydantic 2.13.5、starlette 1.6.0、pytest 9.1.1、httpx2 2.12.0（uv 托管 CPython 3.12.14）。
- `apps/api/app/core/config.py`：`Settings.from_env`——`ZQKY_API_HOST/PORT/ALLOWED_ORIGINS/ENV`，非回环 host、非法端口直接拒绝。
- `apps/api/app/core/http_safe.py`：ASGI 中间件——非回环 Host → 400 `INVALID_HOST`；带 Origin 但不在允许列表 → 403 `FORBIDDEN_ORIGIN`；无 Origin 的本机工具直连放行。
- `apps/api/app/schemas/errors.py`：错误信封生成（code/message/requestId/retryable/details + `X-Request-Id` 头，details 只放脱敏内容）；`app/schemas/capabilities.py`：能力状态模型（planned/ready/unconfigured/unavailable）。
- `apps/api/app/api/v1/health.py`、`capabilities.py`、`app/main.py`：路由与应用工厂（lifespan 日志、501 catch-all、HTTP 异常与 422 统一信封化）。
- `apps/api/tests/`（conftest + 5 个测试文件，18 项）：health 字段与不泄露配置、capabilities 全 planned 且无假成功、Host/Origin 防护、未来路由 501 信封、配置默认值回环安全与环境覆盖。
- `apps/api/AGENTS.md`（后端规则）、`apps/api/README.md`（由规划说明改写为实际启动/接口/参数文档）。
- `apps/web/next.config.ts`：rewrites 将 `/api/v1/:path*` 代理到 `ZQKY_API_ORIGIN`（默认 `http://127.0.0.1:8000`）。
- `apps/web/src/contracts/api.ts`（手写契约，与后端 schemas 对齐）、`apps/web/src/services/api-client.ts`（同源相对路径请求；网络失败→`SERVICE_UNAVAILABLE`“后端服务未运行或无法连接。”；代理 5xx 非 JSON→`SERVICE_UNAVAILABLE`“后端服务不可用。”；后端信封→保留 code/requestId）+ 6 项单测。
- 根 `package.json` 新增 `setup:api`、`dev:api`、`test:api`；`.gitignore` 增加 `__pycache__/ .venv/ .pytest_cache/`。
- 文档同步：docs/API.md（新增“后端已实现接口”一节，后续草案按阶段标注）、docs/DECISIONS.md（D02 决策）、TASKS、本文件、根 README 启动步骤。

新增/改变的公共契约：HTTP `GET /api/v1/health`、`GET /api/v1/capabilities`、统一错误信封与 501 占位；前端 `ApiError`、`API_BASE_PATH`、`fetchHealth/fetchCapabilities`。未动 `LessonPlanServices`、`DraftEnvelope`、导航契约。

当前可用入口与启动方式：根目录 `npm run setup:api`（首次）→ `npm run dev:api` 启动后端 127.0.0.1:8000；`npm run dev` 启动前端 127.0.0.1:5173。浏览器通过 `http://127.0.0.1:5173/api/v1/*` 同源访问；后端不启动时教案与全部页面照常可用。

实际执行的检查、结果与证据路径：`npm run test:api` 18 项 pytest 通过（唯一警告来自 starlette 内部 TestClient 对 anyio 别名的弃用提示，非本项目代码）；`npm run typecheck`、`npm run lint`（0 警告）、`npm run test:unit`（29 项）、`npm run build`、`npm run test:e2e`（12 项）全部通过。集成实测：直连 health 200；经 5173 代理带前端 Origin 请求 health/capabilities 200；`/api/v1/models` 经代理返回 501 信封；`Origin: http://evil.example` 直连返回 403 信封；停止 uvicorn 后经代理返回 HTTP 500 纯文本，前端适配器单测覆盖该场景。后端启动日志仅含 host:port 与 env，无凭证。

未执行的检查及原因：未做真实模型调用与 SSE 流式验证（属 D03/D04，本期无模型凭证与相关代码）；未验证 POST 流式经代理不被缓冲（无流式接口，D04 接入时验证）；未执行 Word/WPS 人工版式验收（不涉及）。

数据兼容与回退说明：草稿键、schemaVersion、导航与教案逻辑未动；rewrites 仅影响 `/api/v1/*`，前端无页面自动调用它。回退只需删除 apps/api 新增文件并还原 next.config.ts/package.json/.gitignore。

仍为规划中的能力：模型连接/学习问答（D03/D04）、模板与正式导出（D05–D07）、教材库/题库/RAG、Agent/MCP/Skills；/capabilities 中均如实标注 planned。

已知问题：无阻塞问题。注意 Windows 下用后台方式停 `npm run dev:api`/`npm run start` 时 npm 包装进程被杀后 uvicorn/next 子进程可能残留监听端口，需按 PID 结束（本次验证时手动处理过）。

下一任务与前置条件：D03 统一 Provider、模型设置、凭证与协议测试（前置 D02 已完成）；需要用户提供至少一个真实模型连接凭证才能完成“真实连接验收”，没有凭证时该项将如实标注未执行。

## 交接：D01 统一模块导航与规划页面（2026-09-06）

任务ID：D01。

实际完成范围：按 IMPLEMENTATION_PLAN 第3节和第13节 D01 任务包，新增智能组卷、题库、模板中心、Agent任务、MCP、Skills 六个入口，`/knowledge-bases` 名称由“知识中心”改为“教材资料库”（路径不变）；全部新业务为统一规划状态页，教案工作台保持本地可用；主菜单、底部菜单、折叠导航与新增的手机导航使用一致的状态和可访问名称。未实现模型、后端、组卷、数据库，未新建空业务目录，未修改冻结模块。

修改文件及作用：

- `apps/web/src/contracts/navigation.ts`：登记项由 `available:boolean` 演进为 `status: 'planned' | 'local' | 'ready'`，新增 `ModulePlan`（用途简介+能力清单）与图标、分组字段的类型；planned 状态强制要求 plan 内容。
- `apps/web/src/services/navigation.ts`：全站模块唯一登记源，扩为 13 个入口并携带图标、分组和规划页文案；新增 `groupMainNavigation()`。WorkspaceShell 的固定图标表已删除，不再有缺图标风险。
- `apps/web/src/components/layout/WorkspaceShell.tsx`：导航按钮改为读取登记表图标；可访问名称与 title 统一为“模块名（规划中）”（修复了底部菜单 title 写死“规划中”的问题）；侧栏加分组标题与内部滚动；新增手机端页头“功能导航”抽屉（Escape/遮罩/按钮关闭，导航前仍执行草稿 flush）。
- `apps/web/src/components/layout/PlannedModulePage.tsx`：新增共用规划页组件（徽标、名称、简介、以后接入的能力、返回教案入口），无示例数据、无假提交控件。
- `apps/web/src/app/[planned]/page.tsx`：改为按 `status === 'planned'` 匹配登记表并渲染共用规划页，新增页面级 metadata。
- `apps/web/src/styles/globals.css`：新增导航分组标签、侧栏滚动、手机菜单按钮与抽屉、规划页内容样式；补齐规划页 `.small-badge` 此前无样式的遗漏；≤767px 媒体查询只增不改，教案模块移动端样式未动。
- `tests/e2e/navigation.spec.ts`（新增）：12条登记路由直达+刷新、无假提交控件、收起/展开/底部可访问名称一致、教案经新入口往返不丢草稿、1440/1024/390截图与手机抽屉流程、未知路径404。
- `tests/e2e/lesson-plan.spec.ts`：仅把导航按钮定位更新为新的可访问名称“学习问答（规划中）”，场景未改。
- 新增单测 `apps/web/src/services/navigation.test.ts`（登记表完整性：唯一id/路径、图标、planned 必有简介与能力、分组连续）与 `apps/web/src/components/layout/WorkspaceShell.test.tsx`（渲染全部入口、状态名称、展开分组、抽屉开关）。
- 文档同步：`docs/ROUTES.md`、`docs/DECISIONS.md`（新增D01决策）、本文件、TASKS。

新增/改变的公共契约：`NavigationItem`（status/group/icon/plan）、`ModuleStatus`、`ModulePlan`、`PlannedNavigationItem`；`groupMainNavigation()`。教案模块接口未变。

当前可用入口与启动方式：`npm run dev` 后访问 http://127.0.0.1:5173/lesson-plans ；所有规划入口从左侧导航或手机页头菜单进入。

实际执行的检查、结果与证据路径：`npm run typecheck` 通过；`npm run lint` 通过（0警告）；`npm run test:unit` 23项通过（原15项+新8项）；`npm run build` 通过；`npm run test:e2e` 12项通过（原7项教案回归+新5项导航场景）。截图证据在 `test-results/navigation-*/`（planned-1440/1024/390、mobile-drawer）与 `test-results/lesson-plan-*/`。

未执行的检查及原因：无。本轮未涉及模板与导出改动，`template:verify` 未重复执行（原件未触碰）。

数据兼容与回退说明：草稿键、schemaVersion 与教案模块逻辑未动；`/chat` 等原规划路径行为不变。回退只需还原上述前端文件。

仍为规划中的能力：学习问答、智能组卷、教材资料库、题库、模板中心、协同写作、沉浸阅读、学习空间、Agent任务、MCP、Skills、设置；教案的真实AI填充仍为规划，现有填充保持“规则”标注。

已知问题：无阻塞问题。注意后续 D03+ 启用设置页或新增模块时，直接在 `services/navigation.ts` 登记即可，不要再在 WorkspaceShell 里建固定表。

下一任务与前置条件：D02 精简 FastAPI 与契约（前置 D01 已完成）；建议先核对 apps/api/README.md 的规划再实施。

## 交接：完整开发计划文档（2026-09-05）

用户要求先写可交给其他AI执行的详细Markdown。本轮新增 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)，同步README、DECISIONS、TASKS及旧规划阅读入口，未修改业务源码、锁文件、原Word或冻结模块。

最新路线：D01导航和规划状态 → D02精简FastAPI → D03模型Provider与设置 → D04真实学习问答 → D05模板排版验证 → D06 A3/A4本地组卷 → D07正式导出 → D08教案模板兼容 → D09集成。每项的前置条件、实施范围、可复制提示词和验收都在完整计划中。

数据库暂不接入，包括PostgreSQL、SQLite、向量库、Redis；教材库、题库、RAG、MCP、Skills等先定义接口和“规划中”入口。UI以当前教案为准，组卷右侧实时预览，A3默认试卷、A4默认课堂小练。现有学习问答/设置仍是规划页，本文没有将其接通。

DeepTutor参考版本经过GitHub API核实：v1.6.4标签对象为e5f2d38…，实际提交为93df3d48…，纠正历史混称。完整计划附源码来源与未验证边界。

本次用Node只读检查了6份Markdown、41个本地链接、17个目录锚点和9个任务提示词，未发现断链、锚点缺失或代码围栏未闭合；核对了纸张、规划状态、模型、双库接口与导出等需求覆盖。未执行前端测试、模型调用、数据库连接或文档转换。下一位AI先按完整计划第16节提示词执行D01；若用户指定其他任务，核查其前置条件。

## 已完成

独立Vite教案已迁入Next.js 16.3.4/React 19.2.8，拆分公共导航与页头、配置、编辑、填充、导出和弹窗。前端保留Tailwind3.4和原视觉。模块不在顶层读取window，编辑状态通过工厂创建；草稿格式和127.0.0.1:5173地址保持兼容。

添加了串行异步写入、离开路由前刷新、坏草稿暂停覆盖和保存失败重试机制。样式限定教案根，PDF使用命名A4页面，其他页面打印不受影响。共享导航接入Next路由，未来入口展示明确规划状态。

根AGENTS.md为规范入口；agent.md仅指引。apps/web和教案模块各有补充规则。根docs记录结构、接口、任务与验证，apps/api和infra只有规划文件。

## 验证

15项单元测试、7项浏览器测试通过。浏览器回归包括直接访问、刷新恢复、路由切换即时保存、规则确认与撤销、环节排序、JSON/Word/PDF导出、长文、多视口、坏草稿和打印隔离。具体证据见QA_REPORT。

曾因备份按钮的无障碍名称包含说明导致测试定位超时，修复测试定位后通过。测试服务改为同一Node进程启动Next CLI，避免测试退出时遗留监听端口。期间本地Git初始化触发了Codex沙箱刷新故障，后续文件操作和验证在工具获批的系统shell执行；没有改动用户全局配置。

## 启动和继续

### 2026-09-05 沙箱故障修复

已定位此前 `setup refresh had errors`：沙箱刷新在给 `.git` 添加拒绝访问规则时，`SetNamedSecurityInfoW` 返回错误5。该目录由 `CodexSandboxOffline` 创建，当前桌面用户无法调整其权限规则。

经用户授权，先备份 `.git` 共359个文件/目录的安全描述符及文件SHA256，再通过Windows管理员授权仅将 `.git` 根目录所有者恢复为 `ASUSA-XIAOHU\96022`，未递归修改所有者，也未手工放宽访问规则。修复脚本确认DACL保持原样，随后Codex正常刷新并添加了自己的保护规则。备份、脚本与结果在 `_work/sandbox-repair-20260905/`，属于本机临时资料，不提交。

实际验证：普通沙箱进程启动、工作区文件写入和读取、apply_patch文件编辑均恢复；209个Git文件SHA256与修复前一致；`git status --short`正常退出。Git仍提示无法读取用户级 `.config/git/ignore`，这是沙箱读权限警告，与此次初始化失败不同，未扩大用户目录权限。没有改动全局Codex配置或业务代码，本次未重复运行前端测试。

根目录 npm.cmd ci 后运行 npm.cmd run dev。正式地址 http://127.0.0.1:5173/lesson-plans。浏览器测试需先build，使用5174，不要将真实用户草稿注入测试上下文。

Node26.2.0是本次验证环境，命令使用项目npm依赖，无个人缓存包路径。用户安装的Edge用于Windows自动化；其他环境可安装Playwright Chromium。

本地Git已初始化，没有提交或远程配置。原目录冻结且未改业务源码；不要在旧目录继续开发。根Word及正式源副本校验一致。不要清空用户已有浏览器草稿。

后续以顶部最新交接和完整计划为准，按用户指定任务实施。真实AI、云端保存、账号、多教案、后台和公开部署均未实施；Word/WPS人工排版仍待验收。

## 2026-09-06 前端复刻首批实施

设置改为分类与锚点内容；MCP、Skills 从主导航收进设置，旧路径重定向。扩展管理为独立本地模拟目录，模型管理保留真实服务。减少动画偏好已实现。完整八阶段尚未完成，实际范围、检查与剩余工作见 docs/replica/HANDOFF.md。

<!-- END ORIGINAL docs/HANDOFF.md -->

<a id="source-3"></a>

## 原文件：docs/replica/HANDOFF.md

<!-- BEGIN ORIGINAL docs/replica/HANDOFF.md -->
# 前端复刻实施交接

## 当前入口：S5-D 已完成（2026-09-08），按用户指令暂停，等待指示后进入 S5-E→I →S6→S7→S8

S5 批次 D「沉浸阅读」完成。全量回归：正式单测 **206/206**（197 基线 + reading-store 9 项）、全量 e2e **92/92**（87 基线 + S5-D 新增 5 项 `tests/e2e/reading.spec.ts`，产物默认 `test-results/`）、typecheck/lint 0 警告、build 通过（30 个路由含 /_not-found 与 /[planned]，其中 5 个为 S5-D 新增）。**用户指令：S5-D 完成后暂停，不自动进入 S5-E。**

S5-D 实施要点（后续批次不得回退）：
- **服务层**：新建 `services/reading-store.ts`（localStorage `zhiqikeyuan:reading-materials/workspaces/annotations/bookmarks/sessions` 五库 + `zqky:reading` 事件订阅）。材料仅文本形态（`sourceKind:'text'`，参考的 PDF/EPUB/网页/媒体解析走服务端——不接入，新建表单与页面描述均显式标注）；批注按 quote 锚定（对照参考 TextQuoteSelector 思路，无几何 rect，原文变更时导航点击提示"无法定位"）；伴生回复 `simulateCompanionReply` 为本地确定性模板并显式【模拟回复】；`organizeNotes` 为本地模板聚合；`sendToNotebook` **真实写入 notebook-store**（跨页联动）。`notebook-store.ts` 新增 `createNotebookRecord` 写入端（校验目标笔记本存在）。
- **/reading 集合列表**：卡片（材料/会话计数）、演示载入幂等（1 工作区+2 材料+批注/书签/会话各 1，`loadDemoReading`）、新建/删除确认；链接 `打开阅读集合 <title>`。
- **/reading/materials**：全部/未分配双页签、新建文本材料（标题+正文，`# ` 行按标题渲染）、分配到集合（无候选显式空态）、删除确认（级联清批注/书签/工作区引用）。
- **/reading/[workspaceId] 三栏工作区**：材料 Tab 条（切换/移除 X/添加 Modal/材料库跳转）+ `reading-layout` grid。左栏 `SourceNavigator` 大纲/书签/批注三页签（大纲解析 `#{1,4}` 行 locator=`h-<行索引>`，与演示书签 `h-4` 一致；点击 scrollIntoView；批注/书签可删除）。中栏 `ReaderPane`：标题层级渲染（#/##/###→h1/h2/h3）、段落 `data-loc`、批注 quote 在段落内渲染为 `<mark data-annotation-id>`（五色 MARK_COLORS）、滚动 300ms 节流保存 positionPct + 进入恢复上次位置、选区浮条（高亮五色/笔记 textarea/书签/问 AI，`onMouseDown preventDefault` 防浮条点击丢失选区）。右栏 `CompanionPane`：会话 select 切换 + 新会话、发送→appendMessage+simulateCompanionReply（Enter 发送带 isComposing 守卫）、首条消息后会话标题取前 24 字、**会话创建/切换用 `history.replaceState` 改写 `/sessions/<id>`（Next 不感知，组件 state 驱动，无闪烁）**、深链 routeSessionId 首次同步（无效提示并回退最近会话）、`zqky:reading-ask` 事件把选中文本预填输入框并携带为消息 quote。
- **路由**：5 个 page.tsx re-export（`/reading`、`/reading/materials`、`/reading/[workspaceId]`、`/reading/[workspaceId]/sessions`、`/reading/[workspaceId]/sessions/[sessionId]`）；`navigation.ts` reading 升 ready（教学工作台组，BookOpen）。
- **有意差异/边界（均显式标注）**：材料解析/转录不实现（仅文本）；伴生 AI 为模拟（无真实模型/检索）；整理笔记为本地模板聚合（页面标注"未接入模型整理"）；课程作用域仅 `?course=` 展示（会话课程标记未接入）；参考的 ReadingContext 跨 URL 保活因本实现 store 驱动状态而天然满足，省略。

S5-D e2e 排障记录：
- navigation.spec 两处随实现状态适配：`plannedRoutes` 移除 `/reading`、导航名清单加入"沉浸阅读"。中途一次 Edit 工具报成功但 plannedRoutes 修改未落盘，导致复跑仍失败——**用 grep 复核文件内容后才算改完，不以工具成功回执为准**。
- 伴生会话消息断言不能用 getByText（select option 的会话标题与消息文本同串，strict mode 冲突），改 `.reading-msg` filter 定位；书签条目按钮与删除按钮 aria-label 同含 quote，用 `.first()`。
- 弹窗「关闭」按钮与 Modal 头部「关闭对话框」图标按钮同字，需 `exact: true`。

下一条动作：**已按用户指令暂停**。恢复后：S5-E 写作/whisper → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户 → S6 设置整合 → S7 视觉动画三视口 → S8 最终验收交付 FINAL_ACCEPTANCE.md；每批参考源码研究先行，不等待批次间授权（除非用户另行指示）。

## 历史：S5-C 已完成（2026-09-08），正在连续执行 S5-D→I →S6→S7→S8

S5 批次 C「书籍与课程」完成。全量回归：正式单测 **197/197**（188 基线 + books-store 5 项 + courses-store 4 项）、全量 e2e **87/87**（81 基线 + S5-C 新增 6 项 `tests/e2e/books-courses.spec.ts`，产物 `tests/.e2e-output-20260908-s5c/`）、typecheck/lint 0 警告、build 通过（20 路由含 5 个新路由）。

S5-C 实施要点（后续批次不得回退）：
- **服务层**：新建 `services/books-store.ts`（localStorage `zhiqikeyuan:books`：Book/Chapter/Page/Block/阅读进度内联一档；演示书编译产物确定性构建，页 id=`<bookId>-p<n>`）与 `services/courses-store.ts`（localStorage `zhiqikeyuan:courses`：大纲/资源/颜色/归档；资源候选实时聚合本地知识库+笔记本+书籍目录——真实跨页联动）。
- **书籍状态机（显式模拟）**：draft（创建即生成模拟提案）→确认提案→spine_ready（章节登记）→确认大纲并编译（同步模拟，每章 2 页，含 section/text/callout/quiz 四类 block，内容显式"模拟生成"）→ready；重建=重新模拟编译并清进度。pause/resume/health 属长流水线特性，不适用（无 WS 流水线），如实记录。
- **/books**：统计条（共/进行中/可阅读/章节）、演示载入幂等、新建 Modal（重名拒绝 `BookValidationError`）、状态徽标+阅读进度条+状态化 CTA（继续创建/确认大纲/继续阅读）、删除确认；就绪书卡片链接 `打开书籍 <title>`。
- **/books/[bookId]**（hub-and-spoke 单组件 `BooksRoute.tsx`，对照参考三路由 re-export 模式）：按状态分流视图；无效 id 显式报错；就绪书无页码时自动续读（当前页→首页 `router.replace`）。
- **阅读器**：Block 分发渲染（14 种中的 4 种子集，有意缩减见矩阵备注）；上一页/下一页+←/→ 键盘翻页；书签切换（侧栏"签"标记）；打开即 `markVisited` 登记已读；章节 rail 显示 visited/bookmark；练习块本地判定（正确/错误+解析），**不持久化作答**（参考为服务端 attempt，已显式标注）；`PageReader key={pageId}` 重置页内状态；无效页码"章节页不存在或已被重建"；导出 Markdown 真实下载。
- **/courses**：进行中卡片+已归档 `<details>` 折叠；新建（名称/简介/颜色）。**主导航入口按参考隐藏**（`hidden: true` ready 项，路由可达；参考 nav-entries.ts L75-77 注释同款决定）。
- **/courses/[courseId]**：大纲（textarea"标题 | 主题1, 主题2"逐行编辑、保存重建并重置 covered、covered 学员手判勾选、下一单元高亮）；资料（附加/移除，候选=本地目录实时枚举，目标消失显"不可用：目标已删除或未载入"，可跳转 /knowledge-bases/<name>、/notebooks/<id>、/books/<id>）；约定 instructions；编辑/归档/恢复/删除确认。**课程学习会话未接入**：参考按 session.preferences.course_id 过滤，聊天侧未携带课程标记——页内横幅如实标注（延后批次决策，未伪装）。
- **导航**：`books` 升 ready 进侧栏（教学资源组，图标 BookMarked）；`courses` ready+hidden；navigation.test 就绪清单与隐藏断言已适配。

S5-C e2e 排障记录（重要，避免重蹈）：
- **悬挂下载对象压垮 headless Edge**：`waitForEvent('download')` 拿到 Download 后若不 saveAs/cancel，下一个用例 `browser.newContext` 报 "Target page, context or browser has been closed"（稳定复现、与用例顺序无关的触发点在下载步骤）。处置：`await download.saveAs(...)` 落盘后再断言内容（顺带强化验证）。此前误判为顺序依赖的二分结论作废。
- 演示数据 id 前缀重复（`demo-${base.id}` 当 base.id 已含 demo 前缀）导致种子进度引用错页——演示数据 id 必须与页 id 公式一致。
- 详情类页面经 `router.replace`/状态切换重挂载后 notice 不保留：编译/重建后的断言以 URL 与页面内容为准，不依赖 status 横幅。

下一条动作：S5-D（阅读 /reading*）→ E 写作/whisper → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户 → S6 设置整合 → S7 视觉动画三视口 → S8 最终验收交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S5-B 已完成（2026-09-08）

S5 批次 B「教材资料库与笔记本」完成。全量回归：正式单测 **188/188**（178 基线 + notebook-store 5 项 + knowledge-catalog 5 项新增）、全量 e2e **81/81**（77 基线 + S5-B 新增 4 项 `tests/e2e/knowledge-notebooks.spec.ts`；全量跑中 navigation.spec 1 项因导航名称适配失败，修正断言后复跑 5/5，产物 `tests/.e2e-output-20260908-s5b/`），typecheck/lint 0 警告，build 通过（build_exit=0，17 路由含 4 个新路由）。

S5-B 实施要点（后续批次不得回退）：
- **/knowledge-bases 列表**：知识库/检索引擎双页签；引擎三组静态展示且显式标注（本地=内置未接入、服务端=LightRAG/WeKnora 演示、云端=IMA 演示）+外部来源（Obsidian/MarginNote 未接入）；横幅显式"解析与索引服务未接入：文档登记仅保存名称与大小"；演示知识库显式载入（幂等，`loadDemoKnowledge`）；新建 Modal（`KnowledgeValidationError` 重名拒绝）。
- **/knowledge-bases/[kbName] 详情**：分区导航 文档/登记文档/外部来源/索引/设置；文档卡带"未解析 · 未索引"标记、大小与登记时间；登记文档仅存文件名+大小（file input 元信息，不读内容）；外部来源 github/web 登记不同步抓取，空地址报错；索引分区显式空态（依赖解析/向量检索服务，未接入）；设置分区改名/简介/删除确认、设为默认库（幂等唯一，默认库星标）。**改名成功后 `router.replace` 同步新 URL**（修复重命名后按旧名查找落"不存在"页的边界 bug）。
- **/notebooks[/[notebookId]]**：双栏 rail+记录区；默认笔记本"学习笔记"为虚拟项（`DEFAULT_NOTEBOOK_ID='notebook-main'`，无存储自动带出、不可删除）；无 notebookId 的记录（含聊天"保存到笔记"旧数据，normalize 补齐）归默认库；URL 深链选中（pushState），指向不存在笔记本明确报错；记录展开（摘要/提问/正文/打开原会话 `/chat/[id]?mode=mock` 深链）、编辑、删除确认、移动/复制（副本标题加"（副本）"、保留来源 metadata）、笔记本内搜索（>8 条出现）；笔记本新建/编辑（名称/简介/颜色）/删除（记录回默认库）、导出 Markdown（下载 `笔记本名.md`，空库仅标题）。页面显式不提供"新建记录"（记录由聊天/研究产生）。
- **服务层**：新建 `services/notebook-store.ts`（localStorage `zhiqikeyuan:notebooks` + `zhiqikeyuan:notebook-entries`，后者与聊天"保存到笔记"共用同一仓储与身份）；`knowledge-catalog.ts` 扩展 docs/sources/isDefault/createdAt + CRUD（`zqky.replica.knowledge.v1`，与聊天知识来源同目录）；两 store 均事件订阅（`zqky:notebooks`/`zqky:knowledge`）+ storage 跨页同步。
- **导航**：`knowledge`（教材资料库）升 ready 进侧栏（原 planned）；`notebooks` 升 ready 保持 hidden（参考亦不在侧栏显示）。
- **有意差异（按参考边界）**：KB 详情无"引用到聊天"动作（RAG 查询在聊天 composer，知识来源为范围声明不执行检索）；聊天侧已有入口不复制第二套管理。

S5-B e2e 排障记录：改名 `router.replace` 后详情页组件重挂载回默认"文档"分区（断言需重新进入"设置"分区再删除，与真实用户路径一致）；navigation.spec "教材资料库（规划中）"断言适配为"教材资料库"（随实现状态更新，同 S5-A /space→/notebooks 的处理）。

**S5-B 收尾补修（直达路由 CSS 断链）**：space.css 仅由 SpaceMain.tsx 引入，/notebooks、/knowledge-bases 的路由模块图不含它——预渲染 HTML 的 CSS chunk 无 `.space-page` 规则，直达访问整页无样式（S5-A 子页因与 SpaceMain 共享 webpack chunk 侥幸带上了样式）。修复：KnowledgeBasesSection/KnowledgeBaseDetailSection/NotebooksSection 显式 `import '@/features/space/styles/space.css'`（bundler 幂等去重）；重建后 /notebooks 预渲染 HTML 已加载含 space 规则的 chunk；knowledge-notebooks.spec 增加样式回归断言（`.space-page` 计算样式为 flex）。**教训：跨模块复用样式时每个使用组件都要显式引入；预渲染 HTML 的 CSS chunk 内容可用于实证检查**。

下一条动作：S5-C（书籍 /books、/books/[bookId]、/books/[bookId]/pages/[pageId] + 课程 /courses、/courses/[courseId]；参考研究报告已备：书籍=hub-and-spoke 单组件+Block 分发阅读器+状态机 draft→spine_ready→compiled，后端生成流水线需显式模拟；课程=聚合状态+大纲/资源/会话，/courses 参考中隐藏主导航）→ D 阅读 → E 写作 → F 伙伴/智能体 → G 精通 → H 记忆 → I 账户 → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S5-A 已完成（2026-09-08）

S5 批次 A「学习空间」完成。全量回归：正式单测 **178/178**（164 基线 + 14 新增）、全量 e2e **77/77**（69 基线 + S5-A 新增 8 项 `tests/e2e/space-pages.spec.ts`，产物 `test-results/e2e-full-s5a2/`），typecheck/lint 0 警告，build 通过。

S5-A 实施要点（后续批次不得回退）：
- **/space 仪表盘**（hub-and-spoke，对照参考 SpaceDashboard）：3 组磁贴（会话与资料/个性化）+实时计数（双仓储会话数、题库/笔记/角色/CLI/扩展计数）；whisper 磁贴按参考行为隐藏（树外插件能力本地不存在）。
- **/space/chat-history**：双仓储（真实+模拟）全量列表，搜索/模式/归档三重筛选、内联重命名（Enter/blur 提交）、删除确认、归档/恢复；重开按模式带 `?mode=mock` 深链。
- **/space/questions**：范围栏（全部/答错/未掌握/书签/未分类/各分类）+计数；250ms 防抖搜索、排序；卡片含选项对错标色、解析折叠、书签/已掌握/归类/删除、出处会话链接（演示题不显示）；批量（全选/已掌握/归类/移出/删除）；分类管理（增改删，删除分类题目回未分类）；演示题目显式载入（幂等）。数据与聊天"保存到题库"同 `space-store` 仓储。
- **/space/personas**：卡片网格+Modal 查看/新建/编辑/删除（重名校验 `PersonaValidationError`）；与聊天输入区人设共用 persona-catalog（新增 content/source/createdAt 字段，旧数据兼容）。
- **/space/cli-apps**：已安装/目录双页签；本地登记安装（横幅与提示均显式"模拟安装，不下载或执行任何程序"）、启停/卸载、内置/第三方徽标。新服务 `services/cli-apps-store.ts`（localStorage `zhiqikeyuan:cli-apps`）。
- **/space/mcp、/space/skills**：重定向 `/settings#mcp` / `/settings#skills`（参考为独立管理页；按既定决策"管理只在设置"重定向，记为有意差异）。
- **会话归档位**：`Conversation.archived?: boolean`（契约扩展，存储往返已测）；store `publish()`/`latestConversation()` 过滤已归档会话（侧栏不显示，深链仍可打开）。
- **跨模式深链**：`/chat/[id]?mode=mock` —深链定位前先切模式（一次性守卫不被误标记）；`syncSessionUrl` 在模拟模式写 `?mode=mock`，刷新后保持模式与定位。
- **导航**：space 登记为 ready；新增隐藏 planned `/notebooks`（`NavigationItem.hidden` 不进侧栏但保留 [planned] 解析）。
- space-store 扩展：书签/已掌握/分类/来源字段 + 分类 CRUD + `loadDemoQuizEntries` 显式演示载入；`updateQuizEntry`/`removeQuizEntries`。

S5-A e2e 排障记录：`规划中`文本断言会撞侧栏隐藏 small 标记（改用规划页正文）；演示题目与种子题目文本要错开避免 strict mode 冲突；navigation.spec 的 plannedRoutes 移除 /space 加入 /notebooks（随实现状态更新）。

下一条动作：S5-B（知识库 /knowledge-bases* + 笔记本 /notebooks*，参考源码研究进行中）→ C 书籍/课程 → D 阅读 → E 写作 → F 伙伴/智能体 → G 精通 → H 记忆 → I 账户 → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S4 已完成（2026-09-08）

S4 逐能力模拟闭环全部完成。全量回归：正式单测 **164/164**、全量 e2e **69/69**（65 基线 + S4 新增 4 项 `tests/e2e/chat-capabilities.spec.ts`，产物 `test-results/e2e-full-s4c/`），typecheck/lint 0 警告，build 通过（build_exit=0）。

S4 实施要点（后续批次不得回退）：
- **能力阶段序列**（对照参考 v1.6.5 manifest）：deep_solve=planning→reasoning→writing；deep_question=exploring→planning→quizzing（每题 `quiz_question_emitted` 增量）；deep_research=rephrasing→decomposing→researching→reporting（两段式：大纲确认卡→检索报告）；visualize=analyzing→generating→reviewing（manim 路由 concept_analysis→concept_design→code_generation→code_retry→summary→render_output）；ask_questions 能力复用纯追问双卡流程。
- **轮内阶段 `TraceStageRecord`**（contracts/chat.ts）：按 stageId 原地更新（start 置 running、end 置 done），end/error/stop 经 `closeRunningStages` 收口为 done/cancelled；`TraceStages.tsx` 时间线（running 旋转/done 对勾/cancelled·error 叉，终态不渲染）。
- **结构化产物**：`ChatArtifact.kind` 扩展 quiz/report/chart/mermaid + `data` 字段。QuizArtifactView（选择题点选判定、填空/概念本地比对、简答不判分、保存到题库）、ReportArtifactView（markdown+子问题+引用 CIT-x-x 定位、保存到笔记）、ChartPreview（Chart.js，失败回退配置原文）、MermaidPreview（mermaid@11 动态导入，失败回退源码）。ArtifactPanel 分发与扩展名已接。
- **空间仓储 `services/space-store.ts`**：localStorage `zhiqikeyuan:quiz-bank` / `zhiqikeyuan:notebook-entries`，幂等保存 + 作答记录；S5 业务页（题库/笔记）共用同一仓储与身份，不另造静态副本。
- **能力轮部分失败重试**：每个能力首阶段后 `failCapabilityTurn()`（`MOCK_CAPABILITY_ERROR`，retryable，可按原快照重试）。
- **分流修正**：纯追问条件加 `!hasExtensions && !capabilityDrivesArtifact` 守卫（否则带能力/扩展的工具卡被追问流程截断）；组合流条件相应收紧。
- **新依赖**：chart.js@4.5.1、react-chartjs-2@5.3.1、mermaid@11.14.0（锁文件已更新）。
- e2e 排障沿用 S3 记录：轮次结束信号=停止按钮消失；次要能力"更多能力"用 hover 不用 click。

下一条动作：S5 批次 A（/space 学习空间：chat-history/questions/personas/cli-apps + mcp/skills 迁移）→ B 知识/笔记 → C 书籍/课程 → D 阅读 → E 写作 → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户，每批独立浏览器验收后继续；随后 S6→S7→S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S3 已完成（2026-09-08）

S3 消息与结果工作区全部完成。正式 e2e **65/65 通过**（61 基线 + S3 新增 4 项 `tests/e2e/chat-workspace.spec.ts`，产物 `test-results/e2e-full-s3/`），正式单测 **157/157**，typecheck/lint 0 警告，build 通过。出口要求"工具→追问→同轮续写→产物→下载→刷新恢复"组合回归通过（chat-workspace.spec.ts:45）。

S3 实施要点（后续批次不得回退）：
- **WorkspacePanel（ArtifactPanel.tsx 重写）**：标签页形态——活动主页常驻第一（不可关闭），产物标签可关闭；关闭=移除标签（ChatWorkspace `closedTabs` 集合，产物本体保留，点产物 chip 恢复标签）并回退相邻标签/主页；会话/模式切换重置标签与关闭态。
- **宽度拖动**：左缘把手 pointer+rAF 合帧写 `--viewer-width`，400–960px 钳制（软上限 `innerWidth*0.7`），持久化键 `zhiqikeyuan:viewer-width`；<768px 隐藏把手（手机整幅抽屉）；220ms `chat-workspace-in` 展开动画；ESC 关闭。
- **活动主页**：InfoPanel + CapabilityConfigCard（R22 配置请求激活主页并定位配置卡）。
- **消息操作**：用户消息复制/复用（`.chat-msg-actions`）；assistant 来源与上下文块 `.chat-sources`（persona/knowledge/historyRefs/attachments/mcps/skills 条目，如实"未真实检索/未读取"说明）。
- **mock 组合流**（chat-service.ts）：纯追问（无能力且无扩展）走原双卡流程；带能力/扩展的追问走 S3 组合流——MCP 工具卡→单张追问卡（ask-combo-*）→同轮续写→能力产物（出题 markdown/可视化 SVG/研究报告）。**注意：must 保持该分流条件，否则工具卡被追问流程截断**。
- **R19 可用性收口**：capBlocked 时发送按钮保持可点击（标签"先确认能力配置"），点击走 submit 的 capBlocked 分支打开配置卡；修复了"无输入时按钮禁用导致必须先输入文字才能确认配置"的死锁。
- **R25 迁入**：`apps/web/src/features/chat/message-duration.test.tsx`（4 项）。

S3 排障记录（避免重蹈）：
- e2e 断言"轮次结束"不能用空输入下的发送按钮 enabled 态（发送后输入清空，按钮本来就该禁用）；用"停止按钮消失"作信号。
- SVG 产物走 data-URL `<img>` 安全渲染，其中文字不是 DOM 文本；断言用 `img[alt]` 可见性而非 toContainText。
- `getPropertyValue('--viewer-width')` 返回 "700px"，用 parseFloat 提取。
- 后台 shell 里 `next build` 偶发失败（环境文件锁竞争），前台重跑即过；e2e 必须确认 build_exit=0 后再跑，否则测的是旧产物。

下一条动作：S4 逐能力模拟闭环（deep_solve/deep_question/deep_research/visualize/数学动画/mastery_path，对照参考源码提取阶段与结果样式；结构化题目/报告渲染；保存到业务页同一仓储）→ S5 A–I → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：R19–R25 已修复并迁移正式回归（2026-09-08）

R19–R25 全部修复，独立复现探针（单元 2、浏览器 7）全部通过后迁入正式回归；正式 e2e **61/61 通过**（54 原有 + 7 迁入边界场景，`test-results/e2e-migrated-run1/`），上轮报告的 chat-motion context teardown 超时本轮未复现（判定为环境相关偶发，S8 全量复验时如实记录）。正式单测 **157/157**（153 + R25 耗时终态 4 项，含复核要求的恢复路径独立回归）。typecheck/lint 0 警告/build 通过。

修复要点（后续批次不得回退）：
- **R20 提交契约**：store.send 接受空文字但必须携带附件/引用快照（用户消息以 `[附件] …`/`[引用会话] …` 明确标识）；新增 onAccepted 同步回调，一次性选择只在轮次被接纳时清理；真实模式附件/仅引用发送显式阻断并保留输入（不静默转纯文字）。
- **R19 配置确认**：门控改为 `needsConfig && (!confirmed || errors)`，任意字段变更撤销确认（桌面+手机共用 handleCapFormChange）。
- **R21 会话归属**：人设/知识/会话引用/附件按「模式+会话 id」归属（ChatWorkspace pendingRef），新会话明确空默认，切回恢复；欢迎页暂存随首个会话迁移。
- **R22 面板选择**：右面板显式单选 panelView（info/config/artifact），配置请求激活配置视图并定位聚焦，不再被产物视图遮挡；手机抽屉同语义。
- **R23 文件并发**：串行接纳队列 + 读取占位（reading）预留配额；完成核对批次身份（发送/移除/卸载后不插回）；失败释放占位并提示；粘贴/拖入统一走队列且拒绝原因显式。
- **R24 产物身份**：结果工作区以复合 key（消息 id:产物 id）打开/tab/复制/下载，不同轮同 id 各自正确；旧历史兼容。
- **R25 耗时**：Message 标题区为唯一耗时渲染点（正文出现后不消失）；patchError 补 finishedAt；normalizeLoaded 以会话 updatedAt 冻结恢复/旧历史耗时（多次载入稳定）。

迁移的正式回归：`apps/web/src/features/chat/message-duration.test.tsx`（4 项）、`tests/e2e/chat-composer-boundaries.spec.ts`（7 项，验收语义未削弱，原始探针证据保留在 `_work/review-s2-s3-20260908/fix-run1/`）。

下一条动作：S3 剩余（引用/来源定位、消息菜单、多标签工作区、宽度拖动、跟随滚动收口）→ S4 能力闭环 → S5 A–I → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

历史摘要：53 非调试条目中 46 待实现的口径仍以三矩阵为准；真实供应商/MCP/Skills/解析/STT 未验证。上一轮（2026-09-08 复核）记录见下节。

## 历史：2026-09-08 独立复核（R19–R25 复现，未修）

当前完整前端未交付；S2 已实现但需修复，S3 部分实现，S1 规格仍需随批补齐。最新依据为 [REVIEW_S2_S3_2026-09-08.md](REVIEW_S2_S3_2026-09-08.md)，全部后续执行指令已统一在 [NEXT_SESSION_START.md](NEXT_SESSION_START.md)。上一轮终态 2/2、URL 刷新 1/1 探针通过；正式 typecheck/lint/build、153 单测通过；本次正式 e2e **53 通过、1 个录像 context teardown 超时**。新探针 **7 浏览器+2 单元场景失败**，对应 R19–R25，尚未修改产品代码修复。

下一条动作：运行 `_work/review-s2-s3-20260908` 两份探针配置，先修提交清理/真实附件提示和配置门控，再处理会话归属、面板选择、附件并发、产物身份、耗时。修复后迁移回归，立即继续 S3 引用/消息/多标签/可调宽度 → S4 能力闭环 → S5 全业务页 → S6 设置 → S7 全站视觉动画 → S8 最终验收，不等待每批授权。详细命令和完成条件见当前入口。

实际矩阵：53 非调试条目，4 已验收、1 实现待验收、2 部分实现、46 待实现；不能用历史44或旧测试数。真实供应商/MCP/Skills/解析/STT未验证，test:api本轮未执行。证据在 `_work/review-s2-s3-20260908/`；本轮仅审查/探针/文档，无产品修复、无提交。下方均为历史实施记录，旧“下一动作”不再作为当前任务。

## 历史：2026-09-07 收尾批 + S2 输入区 + S3 基础实施记录

交付复核（[REVIEW_DELIVERY_2026-09-07.md](REVIEW_DELIVERY_2026-09-07.md)）所列收尾问题已修复并迁移正式回归；S2 输入区和 S3 基础已实施。以下保留当时报告，当前缺陷与验收状态以 2026-09-08 独立复核为准。

### 收尾批完成内容与证据（2026-09-07 晚）

- **终态顺序两处 P2**（store.ts）：
  - `submitReplyAnswers` 归属校验区分业务终态与 Promise 生命周期——`turnAlive` 要求 `endReason === null`；error/stop/disconnect 已到达（即使 run Promise 未返回）时迟到 accepted ACK 一律拒绝。提交异常路径同样只在未终态时改写卡片。
  - `patchStoppedIfStreaming` / `patchError` 幂等进入：已有明确终态（end/error/stop）时通用断流兜底不再覆盖 `endReason`，合法同步续答的迟到确认可保留答案（卡 answered）。
  - 探针迁移正式回归 2 项（`ask-user.test.ts`，现 23 项）：error 先到 run 挂起时迟到 ACK 拒绝；正常 end 后 run 返回时合法 ACK 接受。
- **深链 URL 同步**（ChatWorkspace.tsx）：用户主动选择/新建/删除/切换模式经 `history.pushState/replaceState` 同步地址（选择=push，新建/删除/模式切换=replace；pushState 不触发 Next 软导航，与 R17 一次性深链定位不冲突、无双向循环）；`popstate`（前进/后退）按 URL 在当前模式 store 重新定位，指向已删除/其他模式会话时显示明确提示。探针迁移正式 e2e 3 项（`chat-deeplink.spec.ts`，现 7 项）：选择后 URL 同步且刷新恢复、后退/前进重定位、新建后地址指向新会话且刷新无“不存在”提示。
- **Lint**：删除 `ask-user.test.ts` 未使用的 `emitWaiting` 声明；0 警告。
- **文档**：根 TASKS/HANDOFF 当前摘要已与本节对齐；FINAL 首批执行表标注为历史快照（S1=部分完成、53 条目口径）。

### 收尾批验证（实际执行）

typecheck 通过；lint 0 警告；`test:unit` **119/119**（基线 117 + 终态顺序 2）；`npm run build` 通过；`test:e2e` **45/45**（基线 42 + 深链 3，产物目录 `tests/.e2e-output-20260907-deliveryfix/`）；复核探针 **terminal-order 2/2、route-refresh 1/1**（`_work/review-delivery-20260907/fixcheck-02/`）；上轮探针复跑 **ask-user 单元 7/7、浏览器 1/1**（`_work/review-ask-user-20260907/fixcheck-03/`）。本轮录像 teardown 超时未复现（历史 2 次，逐次记录，根因未定位）。真实供应商/真实 MCP、Skills 未验证；`test:api` 未复跑（后端零改动）。

### S2 完整输入区批次完成与证据（2026-09-07 深夜）

新组件：`CapabilityMenu.tsx`（能力 chip+主列表+更多能力飞出层）、`CapabilityConfigCard.tsx`（出题/可视化/研究三表单+确认门控）、`ComposerSpaceMenu.tsx`（“添加内容”菜单+引用树）。新服务：`capability-catalog.ts`（对照 v1.6.5 目录与配置类型/默认值/校验）、`persona-catalog.ts`、`knowledge-catalog.ts`（演示目录：显式“载入演示数据”，不自动写入）、`doc-attachments.ts`（对照参考 classifyFile/selectAttachmentFiles，20MB/25MB 上限）。契约：`TurnExtensionSnapshot` 增加可选 capability/persona/knowledge/historyRefs/attachments（旧快照兼容）。

- **能力门控**：needsConfig（出题/可视化/研究）未确认时发送按钮为 blocked 态，点击打开右面板配置卡而非静默失败；切换能力使确认失效；任何字段编辑重置确认。
- **真实/模拟分离**：真实模式仅对话能力可选，非对话能力禁用并标注“真实服务未接入”，不静默转模拟；切回真实模式时明确提示并重置为对话；真实模式不支持仅附件/引用发送并有明确提示。
- **快照冻结**：发送冻结 capability+config+persona+knowledge+historyRefs+attachments（深拷贝），重试沿用；一次性引用与附件发送后清空（同参考），人设/知识为会话级。
- **模拟复述**：mock 服务按快照复述能力配置摘要、人设、知识来源（“仅声明检索范围，未执行真实检索”）、引用会话、附件（“未读取文件内容——当前无解析服务，不伪装上传成功”）；阶段行显示“按「X」能力准备”。
- **附件**：选取/拖入（虚线覆盖层）/粘贴/类型与配额校验（错误 4s 自动清除）/图片 SVG 缩略图与文档卡/预览弹层（无解析服务如实说明）/移除。
- **语音**：明确“未接入”说明+带标识演示转写插入，不采集音频。
- **发送按钮**：改为参考的单按钮整轮语义（idle/blocked/ready/streaming，箭头↔方块 200ms 同格交叉淡变）——修复 650ms 宽度过渡期间两按钮互换导致的点击竞态（连续发送回归曾复现误发第二轮，trace 定位后按参考设计消除）。
- **650ms 过渡**：max-width 768→960、cubic-bezier(0.16,1,0.3,1)（对照参考）；textarea minHeight 64→28、0.15s 高度过渡；窄屏恢复 100%。
- **窄屏**：工具行 flex-wrap，390px 发送按钮换行不溢出（R6 断言通过）。

测试：新增 `capability-catalog.test.ts`（6）、`doc-attachments.test.ts`（6）、`composer-snapshot.test.ts`（3：冻结深拷贝/模拟复述/重试沿用）、`CapabilityMenu.test.tsx`（5）；e2e 新增 `chat-composer.spec.ts` 8 项（能力门控闭环/附件/语音/真实模式禁用/650ms 中间帧采样/三视口截图+溢出断言）；`chat-mock.spec.ts` 停止点击改 force（650ms 过渡期间按钮移动，actionability 重试会落到流结束之后——验收语义不变，已在测试注释说明）。单元 **142/142**、e2e **53/53**（chat-mock+chat-composer 27/27 先行验证，全量后 53/53），typecheck/lint 0 警告/build 通过。三视口截图与宽度采样见 `tests/.e2e-output-20260907-s2f/chat-composer-*`（1440/1920/390 已人工查看：欢迎区布局、工具行换行、无横向溢出）。

边界：真实供应商未验证；真实文件解析/STT/persona/知识库服务未接入（均为明确模拟或不可用状态）；能力模拟的完整阶段流程在 S4；三矩阵已同步（A-capability/A-attachments/A-voice/A-persona、M-composer-width/M-first-send、P-chat/P-chat-[sessionId]）。

### S3 切片 1：结果工作区基础（2026-09-07 深夜，已完成）

- **契约**：`ChatArtifact { id, kind: 'markdown'|'svg'|'html'|'text', title, content, createdAt }`（contracts/chat.ts）；artifact 事件负载 `ChatArtifactPayload = Omit<ChatArtifact,'createdAt'>`（store 落盘时补 createdAt）；消息新增 `artifacts?`（旧历史兼容）。
- **store**：artifact 事件按 id 幂等更新（同 id 覆盖=增量/完成、createdAt 保留；新 id 追加）；终态/取消守卫拒绝迟到事件（复用现有 emit 守卫）；随会话持久化、恢复不重放。
- **mock**：出题→markdown 出题结果、可视化→SVG 图表、研究→markdown 报告（内容含配置摘要与“模拟/未访问”标识）；对话/求解等无产物；失败轮不产产物。
- **UI**：`ArtifactPanel.tsx` 右侧结果工作区（与 InfoPanel 共用右栏位；手机走 Modal）：产物列表 tab、markdown（AnswerMarkdown 安全渲染）/svg（data-URL img，img 上下文不执行脚本）/html（空 sandbox iframe 禁脚本）/text 渲染；复制（clipboard，2s 已复制态）与下载（Blob+download 属性，真实内容+安全文件名）。消息内产物入口 chip（图标+标题+kind）定位打开。
- **关键修复——flush 串行队列（数据丢失级）**：旧实现“保存中直接返回在途 Promise”会取消挂起的防抖 timer，保存期间到达的变更（如点击面板/下载触发的 blur→flush、流式增量）无人重排，刷新后数据丢失。改为链式排队：后到 flush 在前一保存完成后处理剩余脏数据；单测回归覆盖（保存中到达的变更必须由后续 flush 落盘）。
- **轮级耗时（切片 2 已完成部分）**：消息新增 startedAt/finishedAt（占位创建/五收尾点记录，持久化）；trace-timing.ts（对照参考 formatTurnDuration：Xs/Xm Ys/Xh Ym，先取整）；流式状态行逐秒滴答、完成后标签行冻结显示（单一状态行设计，不在每个过程卡重复显示——参考明确 per-trace 时长嘈杂）；trace-timing.test.ts 4 项。
- **测试**：`artifact.test.ts` 6 项（幂等 upsert/终态拒绝/持久化恢复/三类能力产物）；store.test.ts 新增保存队列回归 1 项；e2e 1 项（出题轮 chip→预览→下载真实内容→关闭→等轮次完成后刷新→恢复不重放；测试在轮次完成后再 reload——流式中途 reload 的 fire-and-forget 保存不可靠，取消语义由其他用例覆盖）。
- **验证**：单测 **153/153**、e2e **54/54**（`tests/.e2e-output-20260907-s3full/`、`-s3t2/`）、typecheck/lint 0 警告/build 通过。
- **S3 剩余（切片 2 续）**：引用/来源定位、消息菜单（消息级操作）、问题编辑复用细化、跟随底部/回底提示核对、artifact 渲染器扩展（quiz/报告结构化等随 S4）、标签页多开与宽度可调（对照 SessionViewerPanel：220ms 展开、400–960px 持久化宽度，localStorage `dt:viewer-width`）、移动端抽屉细节。耗时显示已完成（轮级单点，对照参考）。

### 下一动作：S3 切片 2（引用定位/消息菜单/过程面板补全），随后 S4–S8

按 FINAL S3：引用/来源定位、消息菜单、跟随底部与回底、过程面板补全（阶段/耗时/状态顺序）、artifact 消费方与右侧结果工作区（按 artifactId/sessionId/turnId 幂等更新、渲染器按能力分批、复制下载用真实内容、历史恢复不重放、HTML/SVG 等安全渲染、桌面分栏/窄屏抽屉）。先读参考 SessionViewerPanel/SessionActivityPanel 及消息列表相关源码，补规格后实现。下面是前次实施记录，不能代替本次独立检查结果。

## 最新交接：续审 R17/R11补充/R13补充/R12补充/R18 修复完成（2026-09-07 夜）——因上下文硬限制暂停，整体未完成

正在执行 FINAL 总任务（S0–S8）。本会话累计完成：S0（R11–R16）、S1 框架（三矩阵 id 化）、S2 深链切片，以及本轮**续审 6 项修复**（R17、R11 补充、R13 补充、R12 补充、R18）。**因会话上下文达到硬限制暂停**；S2 完整输入区与 S3–S8 未开始实施。逐条证据见 [REVIEW_S0_S2_2026-09-07.md](REVIEW_S0_S2_2026-09-07.md) "修复记录（2026-09-07 晚，继续批）"。

### 本轮（续审修复批）完成与证据

- **R17 深链锁死**已修复：`ChatWorkspace.tsx` 深链改一次性定位（`deepLinkHandled` 守卫），新建/切换/删除后不再被 URL 回跳；刷新/前后导航重新挂载按 URL 重定位；lint 依赖以 disable+理由处理。浏览器探针 A/B 通过；迁移 e2e 2 项（`chat-deeplink.spec.ts` 现 4 项全过）。
- **R11 补充**已修复：token 增加 `endReason`（stop/end/error/disconnect 五收尾点记录）；提交归属=未中止 ∧ 未被顶替 ∧（轮次活跃 ∨ endReason='end' 正常完成）∧ 提交身份 ∧ 同会话——error/断流后迟到 accepted ACK 拒绝、中断卡不被改写；正常两卡同步续答保留。迁移回归 2 项（error/disconnect）。
- **R13 补充**已修复：waiting/failed 后的过期 preview 不覆盖完整题目/选项/引言（仅 preview→preview 允许补全）；草稿保留。迁移回归 1 项（状态/题目/选项/引言/草稿五维断言）。
- **R12 补充**已修复：`Message.tsx` 复制按钮可用性改用 `conversationProjection`——纯追问续答可复制，空白占位不显示。
- **R18 文档修正**：PAGE_MATRIX 统计 **53 非调试条目（参考产品页 50 + 目标自有 1 + 兼容别名 2）：已验收 4 / 实现待验收 1 / 部分实现 2 / 待实现 46**；S1="框架完成、规格部分完成"；深链条目降为"实现待验收"；DECISIONS 默认入口行标记历史并统一 `/`→`/chat`。
- 迁移回归：单元 3 项入 `ask-user.test.ts`（现 21 项）、e2e 2 项入 `chat-deeplink.spec.ts`。

### 本轮验证（实际执行）

typecheck 通过；lint 0 警告；独立探针 3/3 单元 + 3/3 浏览器（fixcheck-01）通过；原探针（ask-user 7、extensions 2、复制 1）与 chat 正式测试 72 项通过；build 通过；深链 e2e 4/4。**全量 e2e 修复后未重跑**（恢复后先全量，预期 40/40；chat-motion teardown 若再现按既往记录处理）。

### 恢复点：下一条可执行动作

1. 全量回归：`npm run test:e2e -- --output=<新目录>`（预期 40/40）。
2. **S2 完整输入区**（先读 `F:\DeepTutor\web/components/chat/home/ChatComposer.tsx`、`ComposerInput.tsx`、`CapabilityConfigCard.tsx`）：
   a. 业务能力选择（chat/deep_solve/deep_question/deep_research/visualize）与 real/mock 服务模式分离；能力目录建议新文件 `services/capability-catalog.ts`（订阅机制参照 extension-catalog）；发送时冻结 capability 进快照（复用扩展快照冻结模式）。
   b. persona/附件（选取/拖入/粘贴/校验/预览/移除）/引用/语音入口（权限与无服务状态准确，不后台采集）。
   c. 欢迎区→首次发送 650ms 过渡（逐属性核对）；真实模式选非 chat 能力发起前明确"暂无真实服务"。
3. 之后按 FINAL 提示词 S3→S8 循环（每批：实现→单测→build→e2e 新目录→更新 HANDOFF+三矩阵）。
4. 最终交付 `docs/replica/FINAL_ACCEPTANCE.md`（页面/交互/动画/模拟验证/真实服务验证五列）。

### 已知风险与边界

- chat-motion 录像 teardown 超时：复核轮与本轮复核各 1 次，本会话 3 连跑未复现——根因未知，独立文件隔离，逐次记录。
- 真实供应商未验证（无凭证）；真实 MCP/Skills 未接入；`test:api` 未复跑（后端零改动）。
- Git 零提交、大量文件未跟踪，不能以 diff 证明历史改动边界。

## 前置批：R10 修复＋追问卡片与同轮续答（2026-09-07 傍晚，用户指定）

按 docs/replica/NEXT_PHASE_ASK_USER.md 执行：先修 R10，再实现模拟追问。逐条证据见 REVIEW_EXTENSIONS_2026-09-07.md 的"R10 修复记录"；本节记录追问阶段。

### R10（前置，已完成）

`ExtensionPicker.tsx` 外部点击监听条件写反（`!mounted || open`）导致打开时永不注册——修正为打开时注册、关闭/卸载移除；外部点击 `closePanel(false)` 不抢焦点。探针先复现后通过；正式回归落在 `ExtensionPicker.test.tsx` 与 `chat-mock.spec.ts`（R10 用例）。原 R5–R9 探针 2/2+4/4 复跑通过。

### 追问卡片与同轮续答（模拟，已完成）

- **契约**：wait-user 事件结构化（interactionId/intro/questions/status；preview 只读、waiting 开放，同 id 就地更新不覆盖草稿）；`ChatService.submitReply`（可选能力，ChatServiceReplyRequest 含 sessionId/turnId/interactionId/submissionId/answers/signal）；真实服务显式 REPLY_NOT_SUPPORTED。契约新增 `AskUserQuestion/AskUserOption/AskUserAnswer/AskUserInteraction/AskUserDraft`（contracts/chat.ts），消息新增 `asks?: AskUserInteraction[]`（含逐卡 `followUp` 续写正文），正文→提问→回答记录→续写按序渲染。
- **语义（对照原版源码逐条核对）**：单选选中跳下一未答题、多选不前进、自由文本单选互斥、未答提交为跳过、提交中锁定；卡片级失败保留草稿与选项可重试（MOCK_REPLY_ERROR）；已答只读摘要。主输入框等待时路由到同一提交接口（第一道未答题计入自由文本，其余按草稿/跳过）；等待+空输入显示停止（取消等待），有输入显示提交回答。
- **等待上下文**：模拟 run 经挂起点保持活动（不提前返回、可取消）；submissionId+submittingReply 幂等；取消/断流/切会话/卸载/终态后卡标记 interrupted 并拒绝提交；等待/提交状态只在运行期存在，不持久化运行对象。
- **持久化与恢复**：问题、草稿、确认答案、状态、续写随会话保存；`normalizeLoaded` 将未完成等待标记中断（init 与再选共用）；不重放、可显式重试原问题开新尝试；旧历史兼容。
- **模拟场景（确定性，模拟横幅"模拟追问/模拟提交失败"布防，无隐藏关键词）**：同轮两卡、单选+多选/自由文本、续写反映实际选择、全部跳过、一次提交失败可重试、等待中取消、提交时取消。
- **修改/新增文件**：`contracts/chat.ts`、`features/chat/model/chat-service.ts`、`model/store.ts`、`features/chat/AskUserCard.tsx`（新）、`features/chat/Message.tsx`、`features/chat/ChatWorkspace.tsx`、`styles/chat.css`、`ExtensionPicker.tsx`（R10）、`model/ask-user.test.ts`（新 11 项）、`ExtensionPicker.test.tsx`（+R10）、`tests/e2e/chat-mock.spec.ts`（+6：R10 与追问五场景）。

### 验证（全部实际执行）

- typecheck、lint（0 警告）、`test:unit` **107** 项（基线 95）、build：通过。
- `test:e2e`：**38/38** 通过（基线 32；+6）。产物目录 `tests/.e2e-output-20260907-askuser2/`（首轮 askuser 目录中"减少动画+手机布局"用例失败 1 次，未复现——同用例复跑 2 次及全量复跑均通过，按偶发 flake 如实记录，未改断言）。
- 探针：R10 探针修复前失败/修复后通过；R5–R9 原探针 2/2+4/4 复跑通过。
- **chat-motion 录像 teardown 超时诊断**：复核轮报告的 `Tearing down "context" exceeded the test timeout` 在本轮连续 3 次独立复跑（4.4–4.8s/次，产物 teardown-teardown-1/2/3）均未复现；录像用例独立成文件，业务断言不受其影响。未复现原因无法进一步定位（疑似录像文件收尾与环境负载相关），如实记录。
- 未验证项：真实供应商、真实 MCP/Skills（模拟边界）；`test:api` 未复跑（后端零改动）；WebM 未逐帧播放（此前定格帧已人工查看）；390/1920 追问专项截图未单独补（布局组件复用已验证的响应式规则，追问长文本 390px 人工复核待做）。

### 下一阶段

产物工作区或其他能力待用户指定；旧提示词中"提交后以新轮次继续"已作废（以本节与 NEXT_PHASE_ASK_USER.md 的同轮续答语义为准）。

## 扩展审查 R5–R9 修复（2026-09-07 下午，用户指定）

仅修复 docs/replica/REVIEW_EXTENSIONS_2026-09-07.md 的 R5–R9，未进入追问/产物新功能。逐条代码依据、探针复现与修复后证据见该报告“修复记录”一节。要点：

- **R5**：`store.ts` 新增 `normalizeLoaded()`，初始化与 `selectConversation()` 共用恢复语义——再次选择历史不再复活 streaming/running；保留 revision、消息、快照与工具历史，恢复不重放。
- **R6**：输入区重排（`ChatWorkspace.tsx` + `chat.css`）——已选扩展独立 `.chat-ext-row` 可换行、长名称省略+title、移除按钮可见、说明横排、发送按钮常驻；390×844/1920×1080 断言+截图通过，无裁切隐藏。
- **R7**：`ToolProcessPanel.tsx` 详情 `inert={!open}`——收起即移出焦点顺序与可访问树，收起时焦点自动回头部；动画与快速开关保留。
- **R8**：扩展菜单补退场动画（对照原版 AnimatePresence 160ms cubic-bezier(.16,1,.3,1)，退场 y4/scale.97）；新增 `--ease-standard`（Tailwind ease-out cubic-bezier(0,0,0.2,1)）用于过程展开，与弹出层缓动区分；快速开关/中断/减少动画验证；WebM 录像 + 定格帧截图均已人工查看。
- **R9**：发送开始自动关闭已打开菜单并禁用全部选项，程序化关闭不抢焦点；键盘路径（Shift+Tab×2 回输入框 Enter）正式回归覆盖。

验证：typecheck、lint（0 警告）、`test:unit` 95（基线 93）、build、`test:e2e` 32（基线 26）全部通过；独立探针修复后单元 2/2、浏览器 4/4 通过。真实供应商与真实 MCP/Skills 未验证（模拟边界）；`test:api` 未复跑（后端零改动）。e2e 产物 `tests/.e2e-output-20260907-r5/`、录像 `…-r12/`（每轮新独立目录）。

期间修正的回归：扩展行初版位于工具行之后，破坏 Shift+Tab 两步回输入框路径——已移至输入框与工具行之间。工具链：`npx playwright install ffmpeg` 安装了 Playwright 自带辅助二进制（用户缓存，不动项目依赖与锁文件）。

下一阶段仍为“追问交互”，提示词见本文件“扩展目录联动＋工具过程面板”一节（适用前提 R1–R9 均已修复）。

## 聊天扩展目录联动＋工具过程面板（2026-09-07，用户指定）

### 实际完成内容

- **事件契约**：`ChatServiceEvent` 改为以 `type` 为判别字段的联合类型（`chat-service.ts`）——text/reasoning 必带 `delta`，tool 必带 `call`（callId/kind/name/status，状态 running/done/error/cancelled），end 必带 finishReason，error 必带 error；sessionId/turnId 与终态守卫保留。`ChatServiceRequest` 增加 `extensions?: TurnExtensionSnapshot`；真实服务不读取、不向真实后端发送该字段（真实 SSE 协议未变）。
- **快照冻结与重试**：发送时由当前选择构建快照（`ChatWorkspace.buildSnapshot`，纯数据拷贝），store 再次深拷贝随消息持久化；重试沿用原消息快照（`retry` 读取 `last.extensions`），不读取最新目录；目录变化只影响后续发送。
- **扩展选择器**（`ExtensionPicker.tsx`，仅模拟模式）：复用 `services/extension-catalog.ts` 单一来源与变更订阅；MCP 与 Skills 分区展示、搜索、选中态（aria-pressed）、移除；“管理 MCP / 管理 Skills”链接定位 `/settings#mcp`、`/settings#skills`；Escape 关闭并恢复触发按钮焦点；空态指引。选中项在输入区以 chips 展示可移除。目录变化后失效的待发送选择明确提示（`已移除失效的扩展选择：…`）并移除，不静默替换。真实模式输入区显示“扩展 · 真实模式尚未接入”，不执行真实扩展、不因真实服务错误切模拟。
- **模拟执行**（`createMockChatService`）：确定性脚本——技能逐个“技能上下文已加载（模拟）”（加载记录，不伪装远程调用）；MCP 逐个 running→done（卡片带“模拟工具调用 · 未连接真实服务”标识）；`armFailure()` 布防后首个 MCP 以 MOCK_TOOL_ERROR 明确收尾（保留过程，可按原快照重试），未选 MCP 时保持原 MOCK_ERROR 行为；无扩展时与原流程一致；取消由信号中止触发，运行中卡片由 store 收尾。
- **工具过程面板**（`ToolProcessPanel.tsx`，对照 DeepTutor `TracePresentation.tsx` 行内活动行）：按 callId 去重原地更新（重复更新不新增卡片）；卡片终态（done/error/cancelled）后不接受重开或改写；手动展开/收起固定（卡片组件态 keyed by callId，正文增量不重置）；详情用 AnswerMarkdown 安全渲染（skipHtml），不执行扩展返回内容；展示工具名、状态、模拟标识与可展开摘要；技能加载记录与 MCP 工具记录以 kind 区分（MCP/Skill 徽标）。
- **收尾与持久化**：end/error/取消/断流时所有运行中卡片收尾为“已取消”（store `closeRunningTools`）；过程随会话写入 IndexedDB；刷新只恢复记录不重放（init 不触发服务），历史中仍为 running 的卡片恢复时收尾为 cancelled；旧历史无 toolCalls/extensions 字段按空集合处理，不清空不重置。重试保留带过程记录的失败尝试（`superseded` 标注），即使该轮无正文。
- **动画与可访问性**：卡片展开用已登记 `--motion-trace` 300ms ease-out grid+opacity（对照原版），选择器弹出层用 `--motion-pop` 160ms；状态切换只改类名，不在正文增量时重播；减少动画由 motion.css 全局（prefers-reduced-motion + zqky.motion）接管；选择器键盘可达（Escape、焦点恢复、清晰可访问名称）；上滚阅读不强制滚底行为未变；未引入新动画库。

### 修改与新增文件

- 契约：`contracts/chat.ts`（TurnExtensionSnapshot、ToolCallRecord、ChatMessage.extensions/toolCalls）
- 服务与状态：`features/chat/model/chat-service.ts`（判别式联合、请求快照、模拟脚本）、`features/chat/model/store.ts`（send/retry 快照、tool 路由、closeRunningTools、init 归一化）、`model/ChatContext.tsx`（未改，沿用 R1–R3 机制）
- 界面：`features/chat/ExtensionPicker.tsx`（新）、`features/chat/ToolProcessPanel.tsx`（新）、`features/chat/Message.tsx`（接入面板）、`features/chat/ChatWorkspace.tsx`（目录订阅、选择状态、失效提示、chips、真实模式提示）、`features/chat/styles/chat.css`（面板与选择器样式）
- 测试：`model/extensions-snapshot.test.ts`（新 9 项）、`features/chat/ExtensionPicker.test.tsx`（新 4 项）、`tests/e2e/chat-mock.spec.ts`（新 4 项浏览器用例）

### 实际命令与结果（2026-09-07 全部实际执行）

- `npm run typecheck` 通过；`npm run lint` 通过（0 警告）。
- `npm run test:unit`：93 项通过（上一基线 77；新增快照冻结/重试快照/callId 去重/终态收尾/取消与断流收尾/工具失败重试/历史恢复与兼容/真实路径不带快照/选择器交互等 16 项）。
- `npm run build` 通过。
- `npm run test:e2e`：26 项通过（上一基线 22；新增：扩展选择→发送→卡片→展开稳定→刷新恢复不重放；工具失败→错误收尾→按原快照重试；执行中取消→运行中卡片全部收尾→刷新仍收尾；减少动画+390px 手机布局完整闭环+截图）。e2e 产物目录 `tests/.e2e-output-20260907-r4/`（沙箱批量删除守卫会拦截旧产物目录清理，每轮使用新目录，既有证据未删除；手机截图 `chat-extensions-390.png`）。
- 中途修复：e2e 发现重试会丢弃“零正文的失败占位”，而工具失败轮的过程记录因此丢失——已改为保留带过程记录的失败尝试并有单测覆盖。

### 已知限制与边界

- 真实供应商未验证（本轮未调用真实模型；扩展能力整体为本地模拟，无真实安装、授权、联网检测或远程执行）。
- 录屏未完成（沿用此前限制，未重试 REPLICA_VIDEO）；动画符合性以参数与截图为证，人工视觉审阅待做。
- 发送中扩展选择入口禁用（`disabled={store.sending}`）；在途轮次不可增减扩展（快照冻结语义）。
- 卡片详情为本地脚本生成的演示内容；扩展“内容”字段仅作为技能上下文摘要展示，不做检索或执行。
- 等待用户（wait-user）、产物（artifact）事件仍为预留类型；追问、产物工作区、MCP/Skills 商店与真实检测留待后续阶段。

### 下一阶段执行提示词（追问交互，可直接复制）

> 项目 H:\备份xuexi\智启课源。先读根与 apps/web 的 AGENTS.md、docs/replica/REVIEW_2026-09-07.md、docs/replica/HANDOFF.md 最新一节（扩展目录联动与工具过程面板已完成）；聊天动手前先读 apps/web/src/features/chat/ 全部源码，以当前源码为准；参考仓库 F:\DeepTutor 只读（提交 42fab3cf…）。本次只实施“追问交互”：在统一事件服务的 wait-user 事件上实现消息内追问卡（提问列表、作答输入、提交后以新轮次继续，不伪造远程工具调用），对照原版追问组件的行为与动画（复用已登记 160ms/300ms token 与减少动画机制）；追问沿用本轮扩展快照与统一事件路由，遵守既有终态守卫（迟到事件不重开卡片、不修改已完成过程）、卸载清理幂等（含 StrictMode）与单一仓储机制，不得回退。模拟脚本覆盖“无追问/单问题/多问题/作答后继续/追问中取消”，过程与作答随会话持久化，刷新恢复记录不重新执行；真实模式明确显示未接入。运行 typecheck、lint、test:unit、build、test:e2e（浏览器用隔离上下文与固定测试数据，使用新的独立产物目录），更新 docs/replica 三个矩阵、HANDOFF 与 docs/TASKS。不实现产物工作区与其他页面，不接真实 MCP/Skills，不动教案模块，不升级依赖，不自动提交 Git。

## 审查 R1–R4 修复（2026-09-07，用户指定“下一轮 A”）

本次只修复 docs/replica/REVIEW_2026-09-07.md 中的 R1–R4，未进入新功能开发。修复内容、行为变化、验证命令与结果、未完成项（含“事件类型判别式联合”留待下一轮）详见 [REVIEW_2026-09-07.md](REVIEW_2026-09-07.md) 的“修复记录”一节。要点：

- **R1 卸载清理**：ChatProvider effect cleanup 对两个 store 幂等 `dispose()`（取消生成+冲正保存），客户端路由卸载/浏览器返回不再依赖 pagehide；兼容 React StrictMode。ChatWorkspace 内重复 effect 已移除，beforeNavigate 保留。
- **R2 单一仓储**：固定模式 store 只注入/加载/读写自己的仓储（`ChatDeps.repository` 取代 `repository`+`mockRepository` 双注入；mock 默认库仍为 `zhiqikeyuan-chat-mock`，数据兼容）。真实库挂起不阻塞模拟 store；跨模式同 ID 不串扰。
- **R3 终态守卫**：generation token 增加 `terminal`；end/error/取消/断流收尾后拒绝 stage/process/usage 等一切后续事件。
- **R4 测试修正**：隔离测试注入被测 spy 仓储/服务再断言；复现探针迁移为正式回归并新增卸载取消（含 StrictMode）、卸载保存、dispose 幂等、初始化互不阻塞、跨模式同 ID、三类迟到事件、不自动回退模拟用例。

验证：typecheck、lint（0 警告）、`test:unit` 77 项、`test:api` 84 项、build、`test:e2e` 22 项（新增浏览器“返回离开页面→生成已取消且内容冻结”回归）、`_work/review-chat` 独立探针 4 项，全部通过。真实供应商仍未验证。e2e 本次以 `--output=tests/.e2e-output-20260907` 运行（沙箱批量删除守卫拦截旧 `test-results/` 清理，未删除既有产物；该目录已进 .gitignore）。

### 下一阶段执行提示词（下一轮 B，已于本日下一阶段实施，留档）

> 项目 H:\备份xuexi\智启课源。先读根与 apps/web 的 AGENTS.md、docs/replica/REVIEW_2026-09-07.md（R1–R4 已修复，读“修复记录”）、docs/replica/HANDOFF.md 最新一节；聊天动手前先读 apps/web/src/features/chat/ 全部源码，以当前源码为准。本次只实施“聊天扩展目录联动＋工具过程面板”：把 services/extension-catalog.ts 的变更订阅接入模拟聊天服务，展示已启用的 MCP/Skills；在统一事件服务的 tool/process 事件上实现消息内工具过程展示（按 callId 更新，覆盖 running/done/error/cancelled，重复更新不产生重复卡片，取消/终态不留“运行中”）；发送时冻结本轮配置快照，重试沿用原快照，设置变更只影响下一轮；真实模式继续明确“未接入外部工具”，零外部调用。严格遵守 R1–R3 修复语义：卸载/取消清理幂等（含 StrictMode）、固定模式 store 单一仓储、终态后拒绝阶段/过程事件，不得回退；事件类型可在本轮改为 type 判别式联合（审查“下一轮 A”遗留项），并保证 text.delta、tool.call 必要字段不可缺失。模拟脚本覆盖无扩展、单扩展、多扩展、一次失败、取消；过程持久化，刷新显示历史而不重新执行。对照原版 trace 展开动画，使用已登记的 300ms 参数及减少动画机制，不在每次正文增量重播卡片动画。运行 typecheck、lint、test:unit、build、test:e2e，更新 docs/replica 三个矩阵、HANDOFF 与审查报告状态。不接真实 MCP/Skills 服务，不动教案模块，不升级依赖，不自动提交 Git。

## 统一聊天事件服务＋最小模拟对话闭环（2026-09-06，用户指定阶段）

### 实际完成内容

- 统一聊天事件服务（`features/chat/model/chat-service.ts`）：定义 `ChatService` 接口与 `ChatServiceEvent` 联合类型，事件覆盖开始、正文增量、推理增量、过程增量、阶段、工具、等待用户、产物、用量、完成、错误；全部事件携带 `sessionId + turnId`。分类对齐参考仓库 v1.6.5 `web/contracts/generated/turn-protocol.ts` 的 `StreamEventType`（thinking→reasoning、content→text、done→end 等），工具/等待用户/产物为预留类型（类型已定义、消费方待后续阶段接入）。
- 真实实现 `createRealChatService`：包装现有 `streamChat` SSE 客户端，真实路径行为不变；旧测试的 `stream` 依赖继续兼容。
- 模拟实现 `createMockChatService`：纯本地脚本流式输出，回复带【模拟回复】标识；支持 `armFailure()` 布防一次失败（先输出部分文本再返回可重试 `MOCK_ERROR`）；不访问真实模型、MCP 或外部工具。
- store 双模式改造（构造时固定 `mode`，模式切换由上层在两个 store 实例间选择）：会话仓储按模式分离——真实走原 IndexedDB 库，模拟走独立库 `zhiqikeyuan-chat-mock`；会话列表按模式过滤；`send/retry` 在模拟模式接受无模型档案；事件消费带 turnId/sessionId 守卫，取消后、切换会话后的迟到事件一律丢弃。
- 界面闭环：工具栏新增“真实 / 模拟”分段切换；模拟模式下显示蓝色横幅（含“模拟一次失败”布防按钮）、模型选择器替换为“模拟模式 · 不访问真实模型”标识；输入→发送→流式→完成全流程可用，停止/重试/切会话/刷新恢复均验证。
- 过程增量（process）与阶段（stage）事件已消费：模拟回复前显示“正在组织回答”阶段与过程说明行；工具过程完整工作区待后续阶段。

### 修改文件与新增接口

- 新增：`features/chat/model/chat-service.ts`、`features/chat/model/chat-service.test.ts`、`features/chat/model/mock-mode.test.ts`、`tests/e2e/chat-mock.spec.ts`。
- 修改：`features/chat/model/store.ts`（双模式双仓储双服务、事件路由守卫）、`features/chat/model/ChatContext.tsx`（双 store 会话上下文、模式切换）、`features/chat/ChatWorkspace.tsx`（模式切换、横幅、发送分支）、`features/chat/Message.tsx`（stage/process 展示）、`features/chat/InfoPanel.tsx`（模拟说明）、`features/chat/styles/chat.css`、`contracts/chat.ts`（`ChatServiceKind`、会话 `mode`、消息 `stageLabel/processNote`）、`services/chat-stream.ts`（`reasoning.delta` 事件，本阶段早前完成）。
- 新增公共接口：`ChatService`/`ChatServiceEvent`/`createRealChatService`/`createMockChatService`（chat-service.ts）；store 构造项 `mode`/`mockRepository`/`services`。

### 实际运行命令和结果

- `npm run typecheck`、`npm run lint`（0 警告）、`npm run test:unit`（68 项通过，含新增 chat-service 4 项与 mock-mode 5 项）、`npm run test:api`（84 项通过）、`npm run build` 通过。
- `npm run test:e2e`：21 项通过，含新增 `chat-mock.spec.ts` 3 项（发送→流式→完成→隔离→刷新恢复；连续发送不重复+停止后不再追加；模拟失败→明确错误→重试成功）。
- 截图证据：`test-results/chat-mock-模拟模式发送…/chat-mock-1440.png`（模拟模式完整界面）；每次 e2e 运行自动重新生成。

### 已知问题和未完成项

- 真实供应商未验证：本轮未调用真实模型供应商，真实 SSE 行为由既有单测与浏览器回归覆盖。
- 工具事件、等待用户、产物工作区仅有类型与扩展位置；聊天中与模拟扩展目录（`services/extension-catalog.ts`）的联动未接入。
- 追问交互、过程完整工作区、聊天与面板的完整动画（MOTION_MATRIX 其余条目）待后续阶段。
- 模式切换在生成进行中被禁用（需先停止）；未做生成中后台切换。
- e2e 中中文输入法真实组合输入无法模拟，Enter/Shift+Enter 与 `isComposing` 守卫以代码审查+单测覆盖。

### 下一阶段执行提示词（可直接复制）

> 项目 H:\备份xuexi\智启课源。先读根与修改目录 AGENTS.md、docs/replica 四份文档与 docs/replica/HANDOFF.md 最新一节。本次只实施“聊天扩展目录联动＋工具过程面板”：把 services/extension-catalog.ts 的变更订阅接入模拟聊天服务，在统一事件服务的 tool/process 事件上实现消息内工具过程展示（运行/完成/失败状态），保持真实问答路径不变、模拟标识清晰；覆盖启用/禁用扩展后的行为差异、事件迟到与取消的回归；运行 typecheck、lint、test:unit、build、test:e2e 并更新 docs/replica 三个矩阵与 HANDOFF。不接真实 MCP/Skills 服务，不动教案模块，不自动提交 Git。

## 上一阶段：设置分类、MCP/Skills 本地模拟与减少动画（2026-09-06）

完成参考基线、路由扫描矩阵、AI 交互和动画待办登记；落地设置分类、搜索、锚点定位、MCP/Skills 旧入口重定向及本地模拟管理。
已实现模拟扩展添加、编辑、搜索、启用、删除确认和检测说明；同一目录提供变更订阅，尚未接入聊天选择器。
减少动画偏好支持系统设置、用户覆盖、刷新及跨标签页同步；列表进入动画已实现。

验证：

- TypeScript、Lint、生产构建通过。
- 单元测试 59 项通过，包含原有聊天、教案、模型管理测试及新增模拟目录测试。
- 原导航与设置浏览器测试 6 项通过，含教案编辑后导航往返不丢草稿。
- 新增设置流程浏览器测试通过，覆盖重定向、启用保存、刷新、分类定位和手机无页面横向溢出。
- 查看了桌面和手机截图。录屏尝试在浏览器上下文关闭时超时，未完成动态录像验收；`REPLICA_VIDEO=1` 可单独重试。
- 未调用真实供应商或真实 MCP 服务，未运行本轮 Word/PDF 完整导出验收。

未完成（不可标为完整复刻）：

全量页面和原版视觉、全部设置分类、MCP 商店、Skills 标签与商店、统一 ChatService、聊天能力选择联动、复杂事件模拟、追问与产物工作区、聊天及面板完整动画、全部响应式主题与综合验收均待后续实施。
当前属于阶段 01/02 的部分落地，不代表用户要求的八阶段已全部完成。

工程状态：

目标仓库原有文件多数未被 Git 跟踪，保持现状，未自动提交。参考仓库未改动。
目标模型服务未启动时仍显示准确错误，不以模拟模型代替。

<!-- END ORIGINAL docs/replica/HANDOFF.md -->


<a id="snapshot-status-20260910"></a>
## 2026-09-10 合并快照：docs/STATUS.md

历史原文，仅供追溯；现状与计划以 docs/STATUS.md 为准。原文内相对链接以原文件目录解释。来源提交 6e3f642。

# 当前进度与唯一交接

## 2026-09-10 本次交付：通用多智能体协作规划

按用户要求完成 [协作方案与可复制提示词](MULTI_AGENT_COLLABORATION_PROPOSAL.md)：四类角色及调度用短说明、共用与角色系统提示词、AGENTS.md 注入及可选补充片段、任务卡/结果卡、文件与运行资源分配、独立验收返工、平台启用步骤和智启课源适配示例。用户已明确平台尚未选定，因此采用通用内容格式，未声称可以直接导入某个平台。

这是可复用的配置提案，不是新的项目续做合同。未修改根或目录 AGENTS.md，未配置常驻智能体，未继续历史产品待办。项目整体完成状态及既有业务验收边界不变；下一步是在选定平台后按文档配置并用一个有界任务试运行，本次没有启动该演练。

文档核对：目录锚点及本地链接均可定位，代码围栏成对，UTF-8 无替换字符。独立文本审查发现的总控委派规则歧义、逐条验收状态枚举不一致已修正。仅文档变更，typecheck、lint、test:unit、build、test:api 和浏览器测试未执行，因为产品代码、依赖及运行配置未变。按现有授权仅对本方案与本节作明确范围的本地提交，不推送或部署。

## 2026-09-09 本次交付：侧栏与学习问答逻辑修复

**仅完成用户本次指定范围：统一侧栏、恢复独立学习记录、手机抽屉、删除主聊天模拟执行、后端 .env 凭证、推理折叠和 LaTeX 展示。其他模块业务没有扩展。此节覆盖下方此前主页交付中关于“学习记录嵌入导航、双 store/模拟模式保留”的历史说明。**

### 详细改动

1. **全站导航**：WorkspaceShell 提取共用 workspace-shell.css，沿用学习问答图标、蓝色当前项、品牌与菜单样式。桌面展开 220px、收起 56px，偏好保存在 zhiqikeyuan:nav-expanded；子路由用路径边界匹配当前菜单。教案保留原编辑/预览/顶栏操作，各断点仅替换导航列宽。原本没有全局导航的写作、阅读、空间、知识库、书籍、课程、笔记本与 Whisper，由根布局中的 ModuleWorkspaceShell 接入同一个壳，不复制菜单或改写各模块业务组件；打印时不输出新增导航。
2. **学习记录归位**：从 WorkspaceShell.sidebarContent 移回 ChatWorkspace 的独立 aside，位于全局导航与聊天内容之间，宽 236px。全局导航折叠不再隐藏记录；记录仍可单独收起、搜索、新建、重命名、删除、备份和恢复，手机继续使用原会话列表弹层。
3. **手机抽屉与焦点**：全站功能导航改为原生 dialog.showModal，具备遮罩和可见关闭按钮，支持遮罩点击与 Escape；打开优先聚焦 aria-current=page 菜单，Tab/Shift+Tab 限制在抽屉按钮，关闭回到入口；背景由模态机制隔离并锁定 body 滚动，跨到桌面断点自动关闭并清理。系统/本地减少动画生效。
4. **主聊天模拟模块删除**：移除真实/模拟切换、失败/追问布防、本地脚本生成、模拟配置/扩展入口、第二个 ChatProvider store、默认模拟服务与免密 MOCK_CHAT_PROFILE；store 仅持有真实服务与真实会话仓储。脚本化事件与旧回归的伪档案迁到 tests/fixtures，只能由测试显式注入，生产代码无反向引用。原协议事件、历史消息渲染和真实 SSE 生命周期仍保留。空间会话历史与统计停止读取/创建模拟数据库、移除模式筛选和模拟重开。**没有清理用户旧模拟 IndexedDB**，真实会话数据格式及持久化键不变；阅读/写作/Whisper/题库等其他模块的显式演示能力不在本次删除范围。
5. **API Key 的 .env 持久化**：沿用 FastAPI 设置接口，非空 apiKey 保存到 apps/api/.env 的 ZQKY_API_KEY_<连接ID>，各连接独立；设置编辑窗显示变量名，响应仅包含是否配置/作用域/变量名，密钥不回显。应用真正启动时读取文件，重启恢复；也支持手动编辑后重启，进程环境变量启动时优先（兼容 Windows 环境变量大写）。保留其他文件行，写入使用临时文件、flush/fsync、原子替换；删除连接移除对应项。写失败不替换内存旧 Key，更新先校验版本及字段，Key 文件失败不提交本次连接变更。读取/写入错误脱敏；默认注入测试仍用内存 SecretStore，导入 create_app 不读取用户 .env。未读取或迁移用户当前进程里的真实 Key，未向实际 .env 写入测试值。
6. **推理输出与折叠**：对照只读 F:\DeepTutor（42fab3cf429a1fbf36b257ab8d116a3814964202）的 TracePresentation.tsx / AssistantActivity / ScrollableTraceBody，新增 ReasoningDisclosure，将推理放在回答之前。推理期间自动展开，正文开始或轮次结束后自动收起；用户点击固定本条消息的选择，后续增量不抢回。状态行复用原思考球与唯一耗时，标题区可点击并携带 aria-expanded/controls；详情为 Markdown、左侧引导线、180px 滚动区，用户向上滚动时停止跟随。折叠使用 grid rows + opacity、300ms、cubic-bezier(0,0,0.2,1)，关闭区域 inert，减少动画无过渡。
7. **LaTeX 修复**：AnswerMarkdown 在展示层归一化模型常用的反斜杠圆括号/方括号公式分隔符，再交给原 remark-math/KaTeX；原有美元公式继续支持。保留行内代码、缩进代码、已完成或未闭合代码围栏的原文；流式未闭合公式可在后续分块完成后正常渲染。正文与推理共用，原始消息、复制、导出不被改写；长块公式只在自身区域横向滚动。
8. **回归与文档维护**：新增公式、推理手动优先、.env 保存/重启/失败/脱敏测试及全站侧栏、焦点、三协议推理门闩用例。卸载测试改为真实路径注入测试上游；旧模拟产品专用的 4 个 e2e 文件随功能删除，混合用例保留真实附件拒绝、语音说明及能力禁用验证。旧源码/测试可在父提交 9905447 查阅，删除的模拟用例不计为本次通过。更新 README、API、PROJECT_GUIDE、三矩阵与本节，不扩大既有产品完成状态。

### 验证结果与证据

| 检查 | 本次结果 |
| --- | --- |
| npm.cmd run typecheck | 通过 |
| npm.cmd run lint | 通过，0 警告 |
| npm.cmd run test:unit | 40 文件、245/245 通过 |
| npm.cmd run test:api | 88/88 通过；仅既有 Starlette/anyio 弃用警告 |
| npm.cmd run build | 生产构建通过；隔离测试构建亦通过 |
| 相关浏览器集合 | 43 个场景最终逐项通过：集合运行 42/43，唯一旧断言要求聊天桌面顶栏可见；改为核对现有 chat-toolbar 后单独复跑 1/1。侧栏截图改为等待动画稳定后另复跑 5/5。并非一次全量 e2e 绿灯 |
| npm.cmd run test:chat | 最终 9/9，通过本地 HTTP 上游 → 正式 FastAPI → Next 代理 → 浏览器；三协议推理在正文释放前可见、正文在末块释放前可见、自动折叠/手动展开/停止/刷新/公式通过 |
| 视觉与手机焦点 | 1440/1920/390 主页回归，1280 推理、390 抽屉与恢复截图人工核对；全站 13 个代表路由/子路由导航样式及当前项一致；1024 长答案与模型页由 HTTP 集成覆盖 |
| 真实供应商 | 未执行；没有使用实际 Key 调用外部模型，不能据测试上游推断供应商验收通过 |

第一轮浏览器发现独立模块缺少共用壳、旧主页宽度断言与独立记录列冲突；补壳并更新该范围预期。第二轮折叠尺寸断言取到动画中间帧，改为等待最终 CSS 宽度。截图也改为等待展开动画结束，避免把中间空白/半屏抽屉当最终外观。上述失败均已保留在 _work/chat-fixes-20260909 日志中并完成对应复跑。

固定截图及验收索引：[docs/qa/chat-fixes-20260909](qa/chat-fixes-20260909/README.md)。日志位于忽略目录 _work/chat-fixes-20260909（unit.log、api.log、build.log、typecheck.log、lint-final.log、browser-final.log、browser-rerun.log、sidebar-final.log、integration-final.log）；不将临时产物或凭证入库。浏览器均为隔离上下文和 5174/8001/8002 测试端口；用户 5173 标签仅只读核对，未输入、清空或覆盖用户会话。

### Git 与使用交接

本批在 codex/replica-review-20260908 作本地提交，包含上述代码、对应测试、进度与截图，不推送或部署。保留任务开始前 apps/web/next-env.d.ts 的开发类型引用改动，不纳入提交；依赖及锁文件未改变，旧版 Vite/Word 原件未改。

生效方式：开发前端按现有热更新；运行中的 API 需要重启以使用新的 SecretStore，之后在设置中保存 Key 即写入 .env，或按连接变量名手动填入文件再重启。没有替用户创建或填写真实凭证。本次没有继续旧计划中的其他待办，后续工作以用户新指令为准。


## 2026-09-09 本次交付：学习问答主页视觉复刻

**本次用户指定范围已完成：`/chat` 与 `/chat/[sessionId]` 按指定本地主页复刻，保留蓝色品牌和原有功能；不表示整个项目的 S5～S8 已完成。** 产品代码及首版交接提交：`723e20f`（`feat(chat): replicate requested home UI with blue theme`），检查点标签：`checkpoint/chat-home-20260909`；随后仅追加本节 Git 完整性记录。无远程推送、部署。

### 参考与范围

- 本次视觉依据：`C:\Users\96022\Documents\Codex\2026-09-09\wo\outputs\deeptutor-page`，核读 `REFERENCE.md`、`src/main.tsx`、`src/style.css`、字体和 vendored 动画；在独立 5175 页面查看参考。版本与 SHA256 见 [资源与许可说明](licenses/deeptutor-chat/README.md)。
- 保留智启课源名称、蓝色 `#2563eb`、原导航功能/规划标识与教案入口。参考中没有对应现有功能的入口不接成假业务；未复制参考示例对话进用户历史。
- 页面仍调用原 FastAPI / ChatService / 模型目录，真实与模拟双 store、IndexedDB、本地目录与原会话数据格式不变；没有数据库迁移、供应商协议改动、依赖升级或第二套后端。

### 详细改动

| 区域/文件 | 本次实际变化 | 保留的能力与边界 |
| --- | --- | --- |
| `WorkspaceShell.tsx`、navigation contract/catalog | 增加可选单侧栏布局与内容插槽；学习问答默认 220px 导航，收起 56px；品牌移入左上，学习记录整合入左栏；聊天深链继续高亮学习问答；对应功能切换 House、PenLine、BookText、LayoutGrid、Library、Settings 图标，统一条目维护 | 其他模块保持原壳默认布局；原名称、路由、规划状态、导航前保存回调保留；手机功能导航与会话列表继续可达 |
| `chat-home.css` | 所有新样式限于 `.chat-home-shell`；白/浅灰/蓝色、56px 标题栏、912px 消息与输入内容列、27px 输入框圆角、24px 用户气泡；Geist 工具栏与 Lora/系统宋体正文，正文 17px/1.9；手机 390px 适配 | 保留空白会话欢迎语、建议提问、错误/模拟标识和生成内容核对提示；修正旧全局 Grid 优先级导致手机只占 220px 的问题；不影响教案打印样式 |
| `ChatWorkspace.tsx` 输入区 | 紧凑能力/附件/角色/模型/上下文/语音/发送排列；真实模式增加直接附件选取入口（仍受原真实附件发送守卫保护）；textarea 单行起始、39px 最小显示高、180px 上限、150ms 高度过渡；发送/停止同按钮圆形显示 | 发送、流式、停止、重试、同轮追问、扩展、能力确认、附件粘贴/拖入/配额/移除、引用、人设、语音说明与演示转写仍接原逻辑；没有添加真实文件解析或 STT |
| `ComposerContextChips.tsx` | 角色快捷菜单读取原 persona-catalog，选择仍写入原会话 pending；上下文胶囊显示由当前消息和输入计算的估算，详情解释约 2 字符/token、模型上限和未计入部分 | 角色仅在原支持的模拟模式生效；未知模型上限显示 `—`，没有硬编码参考的 1% 或声称精确计费；不改变原历史截断/输出预留 |
| `ModelSelector.tsx`、`ModelBrandIcon.tsx` | 学习问答采用向上弹出的 290px 模型菜单；搜索、连接分组、默认模型/会话模型、管理跳转保留；Escape/选择后恢复触发按钮焦点，外点关闭，生成时关闭菜单并禁用选项；按实际模型 ID 显示对应品牌 SVG，未知用 CPU | 使用原真实模型目录，未复制参考包的展示模型配置；其他调用位置仍默认使用原 Modal |
| `Message.tsx`、`vendor/thinking-orbs/` | 复制参考 Canvas 思考球：20px 预设、18px 显示盒、3 倍超采样；等待 working、正文流式 solving、终态 breathing，终态 speed=0.5；状态行、衬线正文、左侧消息操作与用量排布对齐参考 | 消息模型/用量、轮级耗时、错误/停止标记、推理、工具、阶段、追问与产物仍读取原消息；复制仍用 conversationProjection；Canvas 离屏/隐藏暂停并释放资源 |
| `ArtifactPanel.tsx` 与工作区呈现 | 面板整幅滑入与聊天避让 220ms；退出保留 220ms DOM 并 inert，支持关闭未结束时再次打开；继续默认 620px、400–960px 偏好钳制及宽度保存，实际布局保留聊天空间；拖动时关闭避让缓动；pointerup/cancel/卸载清理监听、rAF、光标与选择状态 | 原活动页、能力配置、复合身份产物标签、关闭回退、预览、复制、下载、保存及会话归属保留；手机仍走 Modal |
| 动画与减少动画 | 左栏 200ms；菜单入场 180ms cubic-bezier(.16,1,.3,1)，保留原退出 160ms；推理内容 180ms；思考文字 1.8s 呼吸；发送/停止图标原位交叉淡变 200ms；弹窗主体 200ms、遮罩 160ms | 系统减少动画与 `html[data-motion="reduced"]` 同时控制 CSS 和 Canvas；不引入第二套动画库。指定参考输入区固定 912px，替代旧 S2 欢迎 768→960 的横向扩宽；首次发送连续采样验证位置稳定 |
| 资源/文档 | 项目内保存字体、品牌图标、MIT Canvas 源码与许可证；新增本节、目标覆盖说明、三矩阵证据、三视口截图和动画录像 | 运行不依赖用户给出的 C: 参考路径；原始参考与 Word 模板未改；本次不改真实浏览器数据 |

### 实际验证与证据

最终检查针对本批最终产品代码，测试使用隔离浏览器与 5174，输出 `_work/chat-home-20260909/`。

| 检查 | 本次结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run lint` | 通过，0 警告 |
| `npm run test:unit` | **241/241 通过，38 个文件**；本机 Node 26 使用 `NODE_OPTIONS=--no-experimental-webstorage`。Canvas 视觉由浏览器测试负责，原计时/卸载单测只替身 Canvas 绘制 |
| `npm run build` | 通过；最终浏览器回归使用此后重新构建产物 |
| 聊天、输入/边界、能力、深链、工作区、模拟、动画、导航、设置专项 e2e | **65/65 通过（1.4 分钟）**，`final-e2e.log` / `final-e2e/`；未将此数称为项目全量 e2e |
| 新增主页浏览器用例 | 三视口发送/刷新恢复/模型搜索切换/工作区/历史入口；220/56px 侧栏、912px 内容列、手机全屏与发送按钮同行；Canvas 像素随时间变化、系统与本地减少动画静止；面板退出 inert、快速重开、拖拽中 Escape 清理 |
| 视觉检查 | 实际查看 1440×900、1920×1080、390×844 的空态/有消息/面板；查看面板退出中间帧、菜单退出与过程详情关键帧，以及录像抽帧；修复手机挤窄和发送按钮换行后复验 |
| 真实服务 | 未调用真实供应商；SSE 界面回归使用路由模拟上游，复杂能力使用原显式模拟；日志中的 8000 ECONNREFUSED 来自未启动真实后端的场景；`test:api` 未运行（本批未改后端） |
| 项目全量回归 | 未运行，本批执行上述相关 65 项；前轮全量 102/102 仅作为下方历史记录 |

已提交的视觉证据：[1440 页面](qa/chat-home-20260909/home-answer-1440.png)、[1920 页面](qa/chat-home-20260909/home-answer-1920.png)、[390 页面](qa/chat-home-20260909/home-answer-390.png)、[右侧工作区](qa/chat-home-20260909/home-panel-1440.png)、[退出中间帧](qa/chat-home-20260909/viewer-exit-mid.png)、[动画录像](qa/chat-home-20260909/menu-motion.webm)。同目录保存各视口空态、面板和减少动画截图。

### 首败记录与处理

保留首败，不用最终通过覆盖历史：

1. 初次视觉探针 3/4，发现旧全局导航宽度优先级（60 而非 56）；人工截图另发现手机列宽被挤成 220px。修正壳级选择器，新增主区域实际宽度断言。
2. 首次相关回归 **60 通过 / 4 失败**：菜单旧 160ms 断言与新参考 180ms 不同；数学动画最后阶段短于轮询间隔而漏采；整幅滑入时测试在面板尚未就位处拖动；录像 context teardown 超时。前两项按新参考/真实 DOM 阶段观察修正测试，拖拽从动画结束位置执行。
3. 中间专项 **30 通过 / 2 失败**：第二次刷新后的拖拽也需要等待面板就位；录像环境问题仍在。随后 9 项专项与最终 65 项均通过。
4. 录像根因已在本机定位：Playwright 缓存 `ffmpeg-1011/ffmpeg-win64.exe` 为不可执行文件，直接 `-version` 报“不是此 OS 的有效应用”，纯空白页录像也无法关闭。旧文件备份在 `_work/chat-home-20260909/ffmpeg-win64.before.exe`，SHA256 `1B5B32021F6F95C5A7CC85FC555B28910C66ACEA828D13FEA9BCD8B8ECBD0A84`。Node 26 安装过程下载后停在解包；改用 Codex bundled Node **24.19.0** 执行项目锁定的 `playwright install --force ffmpeg`，成功恢复 **v1011**（附带其依赖 winldd v1007），新文件 SHA256 `5B8F3F59BA61685828939FF3C833109748ADBDEA2FFF4B4AE570C9FC0FC1FF4D`。随后 `-version`、空白页录像关闭、正式动画录像均通过。没有修改全局 Node 版本、项目依赖或测试超时。
5. 提交 `723e20f` 成功，但提交后的 `git show-ref` / `git fsck` 发现 `.git/packed-refs` 第 3 行只有残缺短哈希 `46a832c`，缺少完整对象 ID 和 ref 名称。备份到 `_work/chat-home-20260909/packed-refs.before-repair.txt` 后，只移除该无效行，保留所有合法引用，并用同目录锁文件与原子替换写回。随后 `git show-ref`、`git fsck --no-reflogs --no-dangling` 均通过；当前分支、提交链和新检查点标签均可读取。未重置历史或修改远程引用。原有 `apps/web/next-env.d.ts` 开发类型路径改动已保留在工作区、未纳入提交。

本次范围已结项。后续若继续全项目复刻，按下方既有模块差距另行推进；本次没有顺带实施 S5-F～I / S6～S8。

---

更新：2026-09-09。目标与结构见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，续做合同见 [NEXT_SESSION_START](replica/NEXT_SESSION_START.md)。进度：审查基线 `b8cf71f` → R26–R31 修复完成（2026-09-09，见 review 修复记录）；**下一步：R32 与 S3/S4/S5-A～C 差距核查，随后 S5-E→I、S6→S8**。

## 当前结论

**完整复刻未交付。** R26–R31 已修复并全量回归通过；R32 前端差距（伴生 AI 服务化、材料类型、会话草稿、移动端布局）与既有模块差距核查未开始。复杂能力允许显式模拟，但缺失的前端流程仍须补齐。

| 阶段 | 当前可信状态 | 尚需完成 |
| --- | --- | --- |
| S0 历史缺陷 | 修复记录和正式回归已有 | R1–R25 按历史修复记录与回归核对，不把旧“待修”段落重复当现状；不声称本轮逐条重审 |
| S1 规格 | 框架已建，规格仍部分完成 | 按参考补齐每页状态、入口、接口及动画证据；不能把路由数当功能完成率 |
| S2 输入与主聊天 | 主要切片已有 | 完整视觉/动画、真实供应商、服务不可用状态及逐项参考差距验收 |
| S3 结果工作区 | 多种产物、标签、宽度、操作已有实现记录 | 来源定位、各渲染器与消息联动逐项验收；不再把已实现切片重复列为“从零开始” |
| S4 复杂能力 | 确定性模拟脚本及产物闭环已有 | 参考配置/阶段/失败/取消/保存/恢复完整性审计，精通关联随 S5-G 完成 |
| S5-A 学习空间 | 实现待验收 | 目录/题库/历史/角色/CLI 与主聊天的端到端联动及视觉 |
| S5-B 知识与笔记 | 实现待验收 | 导入/解析/索引等参考前端流程；无真实服务时仍需显式模拟闭环 |
| S5-C 书籍与课程 | **部分实现→主要差距收口中** | Block 14 类覆盖与练习作答/页内笔记持久化已闭环（2026-09-09，见 GAP_AUDIT）；开放：生成流水线暂停/恢复/流式过程、课程学习会话联动、书籍内聊天待核查 |
| S5-D 沉浸阅读 | **R26–R32 已补齐（2026-09-09）；实现待验收** | 伴生 AI 已走统一 ChatService 事件模型（流式/取消/失败/重试）；材料类型与解析为显式模拟闭环；会话草稿按会话归属；移动端抽屉就位。剩余：媒体播放器原视图未复刻（显式模拟边界）、S7 三视口/动画验收 |
| S5-E 写作/whisper | **已实现（2026-09-09）；实现待验收** | 协同写作：文档列表/编辑/即时自动保存/选区与全文 AI 修改（流式/取消/失败重试/应用前快照）/撤销/版本恢复；whisper：双席位密室/房间结束态/危机引导卡；均为显式模拟；视觉/动画归 S7 |
| S5-F 伙伴/智能体 | 待实现 | 列表/配置/群组/会话/任务/过程/产物；配置进设置 |
| S5-G 精通之路 | 待实现 | 路径/节点/学习会话/回答反馈/阶段交接/进度保存 |
| S5-H 记忆 | 待实现 | L1/L2/L3、冲突处理、图谱与业务内容操作 |
| S5-I 账户 | 待实现 | 登录/注册/资料/管理前端与权限状态；模拟身份不冒充真实鉴权 |
| S6 设置整合 | 部分实现 | 分类连续内容、搜索/锚点/高亮/历史同步，全量配置；MCP/Skills 只维护一套 |
| S7 三视口视觉动画 | 待全面验收 | 每条静态/过渡/最终状态、主题、减少动画、快速中断与焦点 |
| S8 最终验收 | 未开始 | 回归与真实边界报告，所有必需前端项闭环后生成 FINAL_ACCEPTANCE |

页面精确计数以 [PAGE_MATRIX](replica/PAGE_MATRIX.md) 的实际行统计为准；其“已验收”旧标签有范围边界，不表示参考所有细节或真实后端已接通。

## 本轮发现与下一动作

详情、源码位置及复现见 [阅读审查报告](reviews/READING_REVIEW_2026-09-08.md)（修复记录在文末）。

1. ~~先修 R26、R27 数据保护~~ **已完成（2026-09-09）**：严格读取 + 多键原子写入回滚 + 演示无损合并；探针迁入正式回归并复跑通过。
2. ~~修 R28–R31~~ **已完成（2026-09-09）**：真实路由跳转与前进/后退、segments 批注定位与旧数据歧义提示、零位置恢复与 rAF/timer 身份化清理、收起导航两列布局与伴生栏拖拽/键盘。浏览器探针 4/4 迁入正式 e2e 并通过。
3. ~~补 S5-D 参考差距 R32~~ **已完成（2026-09-09，第二批）**：伴生 AI 服务化（流式/取消/失败/重试）、材料类型与模拟解析闭环（失败/取消/重试）、会话草稿归属、移动端抽屉；见 review「修复记录 · R32」。
4. **下一动作（顺序）**：① ~~跨库存储保护加固~~ 已闭环（2026-09-09，local-collection 四库接入）；② 知识导入/解析/索引模拟阶段闭环；③ 书籍生成流水线状态（compiling/paused/error + 流式过程）；④ 课程学习会话联动；⑤ S5-F→G→H→I→S6→S7→S8。结论见 [GAP_AUDIT_2026-09-09](replica/GAP_AUDIT_2026-09-09.md)。
5. S5-E 已实现（协同写作 + whisper，显式模拟），已随第四批提交；e2e `writing.spec.ts` 3 条 + 导航回归同步更新。
6. 不以“没有真实后端”删除前端验收项；媒体播放器原视图与真实解析保持显式模拟边界。

没有授权调用的真实供应商或不可用外部服务不阻塞其余前端工作；最终分别写“前端模拟可验收”与“真实服务未验证”。

## 最近一轮实际检查（S5-E + 存储加固，2026-09-09）

| 检查 | 结果/边界 |
| --- | --- |
| typecheck / lint | 通过 / 0 警告（每批复跑） |
| 正式单测 | **241/241 通过**（S5-E 后 237；存储加固 +4：local-collection 契约） |
| build | 通过（每批一次；注意：修改产品代码后必须重建再跑 e2e，第五批曾因旧构建误判 e2e 失败） |
| 正式全量 e2e | 第五批后 **102/102**（`_work/storage-hardening-20260909/`；含 writing ×3 与导航回归更新） |
| 独立探针复跑 | 存储 3/3、浏览器 4/4 通过（第一批后，`_work/reading-fix-20260909/`） |
| 真实供应商/MCP/Skills/解析/STT | 未调用，未验证 |
| test:api | 未执行，后端未改 |
| Git 事件 | H: 盘同步异常反复删除 loose refs：已用 packed-refs 固化 + 每批提交后校验；第 2/4 批提交后各恢复一次 |

审查轮（2026-09-08）检查记录见 review 原文；上轮全量 e2e 91 通过/1 失败（teardown 超时）保留作历史，不以本轮复跑覆盖。

## 文档与 Git

19 份旧文档已合并为 4 份历史归档（内容保留，换行规范为 LF），保留源路径、原始与规范化哈希；原规划、Word、模板与产品代码未改。README + PROJECT_GUIDE + STATUS + NEXT_SESSION_START 是当前入口，三矩阵记录条目证据；旧双 HANDOFF/TASKS 不再更新。

审查前基线：`b8cf71f`；标签 `checkpoint/pre-reading-review-20260908`；分支 `codex/replica-review-20260908`。整理审查检查点用标签 `checkpoint/reading-review-20260908` 定位（实际提交可用 git log 查看），可独立撤销，没有远程推送。Git 不包含浏览器数据，未来改存储前须数据兼容与备份验证。
