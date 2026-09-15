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


<a id="snapshot-status-20260915"></a>

## 2026-09-15 整理前快照：docs/STATUS.md

来源提交 `6d987181d5729dbd32a1c82314380d1138d41bfe`。以下逐字保留整理前原文（仅换行规范化）；其中当前/本轮/待办是当时叙述，不能作为新任务授权。相对链接仍按原路径 `docs/STATUS.md` 解释。

<!-- BEGIN snapshot-status-20260915 -->
# 当前进度、完整计划与项目交接

更新：2026-09-15。本文是唯一进度、代码审查、后续计划和交接入口；目标与长期决定见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，逐项证据见三矩阵，历史流水不在本文重复。

## 1. 当前结论

**整体复刻尚未完成，不能称为全部界面、全部 AI 交互或真实服务已经交付。** 当前学习问答 `/chat` 是默认主页和全站唯一视觉基准。全站视觉巡检未通过，已复现隐藏菜单、404 和内容风格差距。

**2026-09-13 MODEL-EXEC v3 完成模型供应商与模型管理 UI 落地（contract-v1）。** 在回退后的 `af9cb78` 代码上重新实现：后端 38 条供应商注册表 + 6 backend 分派、专用适配器（Azure/Codex/Copilot/CodeBuddy）、发现来源、推理控制、迁移 v1→v2、凭证补偿；前端供应商卡片 → 详情弹窗 → 发现多选 → 参数/推理表单；模型管理 UI 保留学习问答蓝色主题。

**同行独立审查（候选 1805397）结论为 needs_revision**，复现 16 项缺陷（MR-01~MR-16），已被修复并经两名独立验收者复验通过（见 6.3/6.4 节）。**B-MODEL-ACCEPT v1（起点 3dfc2fa）完成浏览器验收、真实链路核查与文档收口**：模型批的浏览器全链路、嵌套交互、R-13 真实复验均已执行。

**R-01 已正式关闭**（跨 .env/JSON 凭证一致性；独立复验覆盖并发回滚、删除孤儿、迁移备份三向，见 6.4）。**B-H0R-SHELL v1 关闭 R-02/R-04/R-06**（唯一主页 `/chat`、每个已实现路由唯一当前菜单、404/错误页统一壳且不重复嵌套；独立验收者在候选 e7fb2a4 上亲自浏览器复验，见 6.6）。当前**唯一验收阻断**是 **R-13**；R-02/R-04/R-06 已关闭，R-03/R-10 已由 B-H0R-CHAT-LINKS 与 B-CHAT-SOURCE-FINISH 关闭，R-11 已由 B-COURSE-RESOURCE-SAFETY 关闭，**R-09 已由 B-READING-NAV-SCROLL v1 关闭**（2026-09-15，三项子主张均先在浏览器复现再修复，见 6.10）。**R-13 仍未关闭**：默认预算下推理吃满导致零正文，关推理后默认预算正文出现但 `finishReason=length` 截断，受控 8192 才 `stop`；浏览器侧受控档首可见中文 1172ms、KaTeX 12 处 0 错误、停止/重试/刷新均通过。**整体仍未完成**：其他模块、其余供应商真实覆盖仍待后续批次。

- 本批起点：`57d111d`（产品代码起点 `af9cb78`）；contract-v1 首轮候选 `1805397`，本批修复候选以最新 `git log -1` 为准。
- 审查基线仍是 `21d9898`；本次不改变其结论，只在其后新增 contract-v1 实现与修复批。
- 用户当前未提交改动：`.zcode/agents/evidence-collector.md`、`.zcode/agents/independent-acceptor.md`，本批保留且不纳入提交。
- 页面矩阵现有 53 个非调试条目：功能标签为**已验收 4 / 实现待验收 21 / 部分实现 6 / 待实现 22**；这是条目分类，不是整体完成率。

## 2. 当前实际进度

| 模块 | 已有实现 | 尚未达到的边界 |
| --- | --- | --- |
| 公共壳 | 220/56px 桌面侧栏、根级折叠偏好、200ms 切换、手机模态抽屉；**B-H0R-SHELL v1 已收口**：单一主页 `/chat`（品牌/404/规划页/标题派生）、每个已实现路由唯一当前菜单（隐藏直达页桌面标父菜单、抽屉标自身）、404/错误页恰好一层公共壳且不重复嵌套；学习记录仍为聊天专属独立中栏 | 页面内容视觉尚未按学习问答统一（R-05，后续批） |
| 教案 | 本地规则填充、编辑、草稿恢复、Word/PDF 导出 | 不是 AI 生成；虽有功能验收，尚未按学习问答基准完成全页视觉验收 |
| 学习问答与模型 | FastAPI 三协议 SSE、真实模型目录、服务端 `.env` 凭证、本地会话；**contract-v1**：38 条供应商注册表 + 6 backend 分派、Azure/Codex/Copilot/CodeBuddy 专用适配、发现来源、受控推理、迁移 v1→v2、R-01/R-08/R-12 已修；模型管理 UI 重做为供应商卡片 → 详情弹窗（frontend-design，保留蓝色主题）；DeepSeek 真实普通/长答复验通过 | Responses/Anthropic 无可用凭证仅隔离测试；Codex 真实登录缺自有 OAuth 应用凭据；Copilot/CodeBuddy 缺用户令牌/Key；R-13 完整长回答仍需显式提高预算；主聊天 mock 残留和复杂能力真实事件未接 |
| 学习空间/笔记 | 会话历史、题库、角色、CLI 本地登记、笔记编辑与跨页写入 | 来源深链和历史身份仍需修复；CLI 不执行真实程序；视觉/动画未完整验收 |
| 知识库 | 登记→解析→索引显式模拟闭环；本次10项既有e2e通过，补查1920/390就绪、失败、解析中及系统减少动画样本 | 不读取真实文件、不做向量检索/RAG；全页风格未统一，进度动画完整时序/中断仍未验 |
| 书籍/课程 | 14 类 block、练习保存恢复、笔记、大纲、资源、进度与导出；**课程资源目录故障容错已修（R-11）**：读取失败显示错误与重试、不冒充空、不丢引用、不阻断其他来源 | 缺 compiling/paused/error、流式生成、书籍聊天和课程学习会话；部分 block 仅模拟形态 |
| 阅读 | 材料与集合、批注/书签/进度、事件驱动伴生模拟、草稿归属和手机面板；**R-09 已修**：滚动跟随由用户控制（上滚不被强拉回、「回到最新」显式触发且只滚伴生容器）、轮次按会话归属且迟到终态不跨会话、切会话产生前进/后退历史并经 `popstate` 同步空间/会话/草稿 | 媒体原视图、来源和完整过程仍需复核 |
| 写作/Whisper | 自动保存、AI 预览/应用/取消/重试、撤销/版本；双席位房间 | AI 为显式模拟；DOCX 导入、完整参考差距和视觉/动画未验 |
| 伙伴/智能体 | `/agents` 仅规划页 | 伙伴列表/创建/详情/群组和任务执行尚未实现 |
| 精通/记忆/账户 | 无完整业务路由 | 对应列表、详情、会话、状态、权限和数据联动均待实现 |
| 设置 | 外观、模型、MCP、Skills、关于五类已有 | 工作空间、解析、网络、记忆、智能体等配置未完整整合；扩展管理仍为本地模拟 |
| 全站视觉/动画 | 现有e2e含聊天三视口、思考球/面板中断/减少动画；本次36页面样本和8知识状态样本无页面级横向溢出 | 视觉巡检失败：隐藏菜单、404缺壳和模块内容风格差距已复现；未遍历全部详情/弹窗/主题，不等于全站验收 |

逐页、AI 与动画的状态分别以 [页面矩阵](replica/PAGE_MATRIX.md)、[AI 交互矩阵](replica/AI_INTERACTIONS.md)、[动画矩阵](replica/MOTION_MATRIX.md) 为准。`ready`、组件存在或历史测试通过均不能单独升级为完整交付。

## 3. 2026-09-12 代码审查

本轮未发现 P0。R-01至R-12在审查基线 `21d9898` 上由源码确认，R-13来自本次真实供应商补验。

**更新（2026-09-13 MODEL-EXEC v3）**：模型范围内的 R-01、R-07、R-08、R-12 已按 contract-v1 实现，并在独立审查后逐项修复（见 6.3 节）：
R-01 服务层跨存储原子性与补偿（首轮残留的并发/孤儿缺陷已修，`test_concurrent_update_cannot_roll_back_other_requests_credential`、`test_delete_failure_keeps_both_sides_and_is_retryable`）——**已由独立复验确认并正式关闭（2026-09-13）**；
R-08 `credentialAction:"clear"` 独立清除（`test_credential_clear_is_independent_from_empty_key`）；
R-07 受控推理字段（`test_profile_reasoning_fields_roundtrip`、`test_reasoning_disabled_with_effort_is_rejected`）；
R-12 capabilities 文案改为与 `.env` 实际一致。R-13 仍为验收阻断（复现并给出方向，未关闭）。R-02/R-03/R-04/R-05/R-06/R-09/R-10/R-11 本轮未动。

浏览器补验确认 R-02 的404返回入口、R-04 的三个隐藏页、R-05 的内容风格差距和 R-06 的404缺壳实际存在；R-09 仍未做针对性浏览器复现，不能以既有阅读12项e2e通过关闭它。

| ID / 级别 | 事实与影响 | 修复与验收要求 |
| --- | --- | --- |
| R-01 / P1 **已于 2026-09-13 关闭** | `model_connections.py:60-83` 在仓储事务中先写 Key，配置 JSON 随后失败时 Key 已变化；删除先删配置再删 Key，后一步失败会留下孤儿凭证。独立审查又复现并发回滚与删除孤儿（MR-04/MR-05）。 | 已建立服务层原子写与补偿：更新/删除在仓储同一临界区完成 revision 校验、文档变更与凭证写入，配置失败回滚凭证，删除时凭证清理失败整体不删可重试。独立复验覆盖三向（`_work/accept-560ac76/backend/ACCEPTANCE.md`、`RECHECK-4ef803b.md`）。**关闭依据：独立复验 pass。** |
| R-02 / P1 **已于 2026-09-13 关闭**（B-H0R-SHELL v1） | 根路由进 `/chat`，但 `WorkspaceShell.tsx:140-162` 的品牌按钮和 `not-found.tsx:6` 仍回 `/lesson-plans`，metadata 也仍称教案工作台 | 已建立单一主页来源（`navigation` 的 `home` 标记派生 `HOME_PATH`/`HOME_LABEL`），品牌按钮、404/规划页返回入口、默认标题与可访问名称全部由它派生；桌面/手机导航与 404 已回归（`tests/e2e/shell-home-nav.spec.ts`）。**关闭依据：独立验收 pass（6.5/6.6）。** |
| R-03 / P1 **已于 2026-09-14 关闭**（B-H0R-CHAT-LINKS v1） | 主聊天真实/模拟切换入口虽已移除，`contracts/chat.ts:13-14,187-188`、`ChatWorkspace.tsx:564-575`、部分组件与 CSS 仍保留 mock 分支并提示用户切换到不存在的模拟模式 | 只清理主聊天运行时/会话契约、不可达分支、无效文案和专用样式；阅读、写作等已批准的显式模拟继续保留并标注，必要时把共享服务类型拆成中性契约；测试替身只留 `tests/fixtures`，旧浏览器库不读写也不清除 |
| R-04 / P1 **已于 2026-09-13 关闭**（B-H0R-SHELL v1） | `navigation.ts` 将 `/whisper`、`/notebooks`、`/courses` 隐藏；`WorkspaceShell.tsx:80,111` 过滤后没有 `aria-current`，手机抽屉也无法聚焦当前菜单 | 隐藏直达页登记 `parentPath`，桌面侧栏标记可见父菜单、手机抽屉标记隐藏项自身；新增单一解析器 `resolveCurrentNavigationId`（最长前缀，任一界面最多一个当前项），并遍历已实现/隐藏/详情/404 路由回归。**关闭依据：独立验收 pass。** |
| R-05 / P1 | `chat-home.css` 的字体与内容骨架只作用于聊天；公共导航仍用 Arial/微软雅黑，设置、教案和其他模块保留各自旧壳 | 提取学习问答视觉 token 与内容骨架，按模块迁移；每批功能完成门槛同时包含视觉验收 |
| R-06 / P1 **已于 2026-09-13 关闭**（B-H0R-SHELL v1） | `not-found.tsx` 以及白名单遗漏或页面自包壳的错误场景可能离开统一 WorkspaceShell；根 `error.tsx` 本身不能证明所有错误都缺壳 | 新增 `ShellScope` 声明“是否已有公共壳”，`StatusShell` 仅在缺壳时补一层，404/错误页在任意路径都恰好一层壳、不重复嵌套；错误页保留可用恢复操作（reset）与返回主页入口。**关闭依据：独立验收 pass。** |
| R-07 / P2 | 后端可解析 reasoning/thinking，但模型设置仅允许数值参数，无法表达需要显式开启推理的供应商配置 | 按协议增加受控、强校验字段；不开放任意 JSON，真实供应商逐协议验证 |
| R-08 / P2 | 编辑连接时空 Key 表示“保持”，没有独立清除凭证动作 | 增加明确的移除凭证语义、确认与回归，不让空字符串兼任两个含义 |
| R-09 / P2 **已于 2026-09-15 关闭**（B-READING-NAV-SCROLL v1） | `ReadingWorkspace.tsx` 直接强制回底并使用 `replaceState` 切会话：流式中上滚被强拉回底部、切会话不产生前进/后退历史、生成中切走后旧轮次的"生成中"块与迟到终态污染新会话 | 三项子主张已用隔离浏览器复现（见 6.10）：A 上滚 `{top:212,max:212}`、B `turnBlocksInNewSession:1`、C 后退离开阅读板块。修复为跟随开关 + 用户触发的「回到最新」（只滚伴生容器）、轮次按会话归属 + 全事件 `sessionId/turnId` 守卫、`pushState`+`popstate` 同步空间/会话/草稿。首败转 5 项正式回归通过。**关闭依据：首败三例复跑通过 + 回归全绿。** |
| R-10 / P1 **已于 2026-09-14 关闭**（B-H0R-CHAT-LINKS v1 + B-CHAT-SOURCE-FINISH v1） | `NotebooksSection.tsx:504` 仍生成 `?mode=mock`；`QuestionBankSection.tsx:450` 用 messageId 作为聊天会话路径 | **会话回链**：改用真实 sessionId、去掉死参数、旧数据与删除会话明确不可用（B-H0R-CHAT-LINKS）。**消息定位**：链接带可选 messageId，先加载会话再在该会话内定位并提示，消息已删提示「原消息已不存在」，失效会话不自动打开最近会话（B-CHAT-SOURCE-FINISH）。真实保存链路用例证明 sessionId+messageId 实际落库 |
| R-11 / P1 **已于 2026-09-14 关闭**（B-COURSE-RESOURCE-SAFETY v1） | `courses-store.ts:250,311` 在渲染路径直接读取知识目录且无损坏兜底 | 已改为在 effect 中集中读取**容错快照**并区分三态（读取失败/合法空/目标缺失）；失败时课程正文、大纲与其他来源仍可用，显示错误与重试；重试恢复不需清数据；引用与课程数据逐字节未变。首败：知识目录损坏时整页被根错误边界接管。见 6.9 |
| R-12 / P2 | `capabilities.py:23` 仍宣称凭证只存进程，和 `.env` 实际实现不符 | 改为真实作用域说明并跑后端契约回归 |
| R-13 / P1 验收阻断 | 真实DeepSeek长回答样本：两模型未设输出上限时使用后端默认2048，均只有推理并报 `EMPTY_RESPONSE/length`；隔离副本改8192后Flash成功，Pro仍只有推理 | 按模型验证推理配置、预算与供应商行为；不能一律靠增加上限宣称修复。用户正式配置未改，纳入 B-H0R-MODEL/T1 |

审查确认无回归的关键点：可见详情路由使用路径前缀保持唯一当前菜单；桌面折叠偏好跨壳保存；手机使用原生模态抽屉并有遮罩、Escape、关闭按钮、焦点圈定与返回；学习记录仍在全局导航和聊天主区之间；生产创建真实 SSE store；推理和正文都经安全 Markdown/KaTeX 渲染；单次 `.env` 写入使用临时文件、fsync 和原子替换且不回显 Key。

## 4. 本轮实际验证与边界

### 4.1 2026-09-13 MODEL-EXEC v3（contract-v1 实现 + 审查修复批）

候选：`1805397`（首轮）+ 本批修复提交（`git log -1`）；合同版本 `contract-v1`（`_work/model-providers-v1/contract-v1.md`，含 6 个文件 sha256）。

**首轮候选 1805397 的独立审查结论为 needs_revision（16 项 MR）**，修复后的状态如下：

| 检查 | 结果 |
| --- | --- |
| `npm.cmd run test:api` | **通过 181/181**（首轮 164；本批新增 `tests/test_review_regressions.py` 17 项，逐条对应审查探针）；1 条 Starlette 弃用 warning |
| `npm.cmd run typecheck` | 通过，exit 0 |
| `npm.cmd run lint` | 通过，0 error 0 warning，exit 0 |
| `NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit` | 42 文件、**274/274 通过**（首轮 262；新增审查回归 11 项 + AuthPanel 接线 1 项） |
| `npm.cmd run build` | 通过，23/23 静态页面生成 |
| 浏览器 e2e（正式套件） | 模型批当时 **92/92**；B-H0R-SHELL 批后为 **119/119**（新增壳回归 27 项），见 6.6 |
| 真实联调 e2e（隔离后端 8001） | **5/5 通过**：真实 DeepSeek 连接卡片、UI 创建无默认地址供应商（先填地址再创建）、保存 Base URL 后表单保持新值、手机/1920 无横向溢出、减少动画 |
| 真实供应商（DeepSeek） | 普通调用通过；R-13 三档复验见 4.3，**R-13 未关闭** |
| 视觉检查 | 查看 6 张联调截图；首轮修复两处缺陷（操作按钮换行、误显示 Anthropic 提示），本批新增附加请求头编辑与创建草稿表单 |

**`.env` 写入记录（修正 MR-15）**：首轮真实探针把文件型 `SecretStore` 直接注入应用，`secrets.put` 曾**误写**正式 `apps/api/.env`（新增一行 `ZQKY_API_KEY_probe-deepseek-v1`）；当时按行删除后恢复为 150 字节，但**没有本批前置散列，独立审查不能追认该次恢复**。本批已把探针与 `_work/model-providers-v1/live-backend.py` 改为**纯内存凭证副本**（先读入内存，再构造 `scope='process'` 存储），并加运行前后**逐字节断言**：本批真实探针与真实联调各跑一遍，正式 `.env`（md5 `c56f6ffbbbc45bb99f04ce339d270f61`）与 `.local-data/model-config.json` **运行前后逐字节不变**。表述从"从未写入"更正为"曾误写、已恢复、本批用内存隔离并加断言"。

| 隔离/数据保护 | 8001 隔离后端（临时目录数据 + 内存凭证）、5174、`.next-test`（代理指向 8001）；正式 `.env`/`.local-data` 本批逐字节不变；`next-env.d.ts` 已还原；测试服务与端口已释放 |

### 4.2 2026-09-12 补验（历史，保留）

| 检查 | 2026-09-12 结果 |
| --- | --- |
| `npm.cmd run typecheck` | 通过，Next route types 生成成功，TypeScript exit 0 |
| `npm.cmd run lint` | 通过，0 warning，exit 0 |
| `NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit` | 41 文件、260/260 通过 |
| `npm.cmd run test:api` | 88/88 通过；另有 1 条 Starlette 依赖弃用 warning |
| `npm.cmd run build` | 通过，23 个静态生成进度完成，路由清单生成成功 |
| 浏览器 e2e（补验） | 16文件80/80通过，0失败/跳过/flaky，90.959秒；Edge隔离上下文。所需聊天响应由测试fixtures提供，单独记录真实供应商 |
| 视觉巡检（补验） | **整体fail，局部pass**：12入口×3视口=36样本，另4抽屉与8知识状态样本，共48张图；独立验收者实际查看20张代表图；隐藏菜单、404和内容风格不合格 |
| 真实供应商（补验） | **部分通过**：DeepSeek两模型普通/流式连接、Flash受控预算长回答/公式/恢复、真实停止与错误重试通过；默认预算和Pro长答失败，详见下表 |
| 真实解析、Responses/Anthropic供应商 | 未运行：知识库尚无真实解析服务；当前只有DeepSeek/openai-chat已配置连接，其他协议没有可用供应商凭证 |
| 隔离构建/数据保护 | 另构建 `.next-test` 并将同源代理指向测试FastAPI 8001；前端5174。配置副本+内存凭证，原模型JSON与`.env`前后SHA256相同；`next-env.d.ts`恢复到用户原有未提交版本；测试服务已停止 |

历史记录：typecheck/lint/单元/API结果来自同日早前审查，产品代码未变。历史H0的25项、B-H1-KB的80项等不再充作当前结果。

### 4.3 真实供应商结果（2026-09-13 复验，R-13）

实际链路：隔离进程内 FastAPI 8001 → `api.deepseek.com`；模型配置为临时副本，正式 `.env` 只读加载到内存 SecretStore，不回显。
产物 `_work/model-providers-v1/real-provider-probe-contract-v1.json`，脚本 `real_provider_probe_contract_v1.py`。

| 检查 | 实际结果 |
| --- | --- |
| 注册表 deepseek 普通调用（默认预算） | pass；正文 5 字、推理 101 字、首正文 1918ms、`finishReason=stop` |
| 旧连接（custom/openai_chat）普通调用 | pass；首正文 1280ms（迁移路径未回退） |
| **R-13** 长回答 + 默认预算 2048（推理开启） | **fail（预期复现）** `EMPTY_RESPONSE/length`；仅 2624 字推理、0 正文 |
| **R-13** 长回答 + 默认预算（推理显式关闭） | pass 出现正文：3176 字、首正文 **1080ms**，但 `finishReason=length` — **答案被截断，不算完整成功** |
| **R-13** 长回答 + 推理关闭 + 受控预算 8192 | pass：正文 7760 字、首正文 1421ms、`finishReason=stop`（完整结束） |

**R-13 结论**：默认预算下推理占用全部额度导致零正文；受控推理开关让正文在默认预算内即可出现，但**完整长回答仍需显式提高预算**。不采用"无界加预算"或"自动关推理掩盖失败"。

### 4.4 真实供应商结果（2026-09-12 历史，保留）

实际链路：隔离Edge → Next同源代理5174 → 现有FastAPI8001 → `api.deepseek.com`；没有伪造回答、重放SSE或浏览器路由替身。只向供应商发送固定验收问题。模型连接测试会写能力标记，因此使用模型配置副本；真实密钥仅在测试后端内存中。

| 检查 | 实际结果 |
| --- | --- |
| 模型发现 | pass；返回 `deepseek-v4-pro`、`deepseek-flash` |
| 普通连接/流式连接 | 两模型各2项，共4/4 pass；普通调用约2148/1249ms；短流式各3个正文分块。短回答分块接近同时到达，不能单独证明边生成边显示 |
| 原配置长中文回答 | **2/2 fail**；两模型 `maxOutputTokens=null`，实际默认2048；分别收到2048个推理增量、0正文，前端正确显示预算耗尽错误，问题与推理保留。保留首败，测试等待正文的120秒超时不等于供应商网络超时 |
| 测试副本8192：Flash | **pass**；465个汉字、588个正文增量、3031个推理增量；首个可见中文13820ms，结束15428ms，提前1608ms显示；27处KaTeX、0公式错误。推理自动开→正文出现关→手动开后保持、刷新后默认关且可恢复内容，三视口无页面级溢出 |
| 测试副本8192：Pro | **fail**；8192个推理增量、0正文，约79秒后 `EMPTY_RESPONSE/length`；未继续无界增加预算。连接可用不代表此长答场景可用 |
| 真实停止 | pass（Flash）；收到152个推理增量后停止，浏览器读取以AbortError终止，显示已停止；新建会话等待2秒无晚到消息。未获得供应商服务端计算/计费终止证明 |
| 真实上游错误→重试 | pass（Flash）；仅将测试副本modelId临时改为不存在值，真实上游HTTP400→应用HTTP502/UPSTREAM_ERROR，用户问题保留；恢复副本配置后点重试得到“重试成功”，旧失败尝试保留 |
| 独立公式样本 | pass（Flash、测试预算8192）；实际模型输出2个公式，KaTeX错误0，刷新及1440/390视口通过，未强制替换供应商正文 |

### 视觉范围、证据与复跑

正常入口包括chat、教案、设置、学习空间、知识库、书籍、课程、笔记、阅读、写作、Whisper；另测未知404。三视口为1440×900、1920×1080、390×844。36页面与8知识状态样本均无页面级横向溢出；正常页桌面侧栏220px。Chat抽屉焦点为学习问答；三隐藏页焦点为关闭按钮且无当前项，但Tab圈定、Escape、遮罩/按钮关闭后的焦点返回均通过。知识库1920/390的就绪、失败和解析中样本可读，系统减少动画下仍完成35%→就绪；这不证明进度条300ms动画、中断或全站全部主题已验。

关键证据随Git保存：[机器结果](qa/acceptance-20260912/summary.json)、[视觉测量](qa/acceptance-20260912/visual-measurements.json)、[焦点/知识状态探针](qa/acceptance-20260912/visual-probes.json)、[真实公式手机图](qa/acceptance-20260912/real-formula-390.png)、[Flash长回答](qa/acceptance-20260912/real-flash-answer-1440.png)、[Pro预算8192首败](qa/acceptance-20260912/real-pro-budget8192-failure.png)、[隐藏菜单](qa/acceptance-20260912/courses-drawer-no-current-390.png)、[404缺壳](qa/acceptance-20260912/404-no-shell-390.png)。完整48张巡检图及原始JSON/运行脚本在 `_work/acceptance-20260912/`，现有e2e图片在 `test-results/acceptance-20260912-e2e/`，这些完整本机产物不随Git分发。

本机复跑命令记录：`npx.cmd playwright test --config _work/acceptance-20260912/e2e.config.ts`；`node _work/acceptance-20260912/visual-audit.mjs` / `visual-probes.mjs`；测试后端 `apps/api/.venv/Scripts/python.exe _work/acceptance-20260912/provider_server.py`；供应商 `provider_probe.py`、`browser-provider.mjs`、`browser-provider-budget.mjs`、`provider-formula.mjs`。供应商复跑会产生实际请求，先确认测试副本预算和8001/5174归属；原始长答用2048，预算复测用隔离副本8192，不能混记。首次e2e临时配置启动失败发生在用例运行前，修正临时配置后80项首跑全绿；单独保留该启动日志。浏览器补验启动命令的一次自动审批拒绝以只绑定回环的启动脚本解决，未影响产品用例结果。

## 5. 完整实施计划 v4

每个阶段都必须以当前学习问答为视觉入口和完成门槛；H6 只做跨模块补漏及总验收，不把视觉统一推迟到最后。每批先更新对应矩阵规格，再实现、回归、独立验收和本地小提交。

| 顺序 | 范围 | 可核验出口 |
| --- | --- | --- |
| 首要：B-MODEL-CONTRACT v1 | ✅ 已落地 contract-v1（`registry.py` + schemas + 前端 contracts/services，散列见 `_work/model-providers-v1/contract-v1.md`） | 前后端字段/枚举/样例/兼容规则明确；文件和端口各有单一负责人，不各造一套目录 |
| 首要任务 1：B-MODEL-UI v1 | ✅ 已实现（frontend-design）：供应商卡片→详情弹窗→发现多选→参数/推理表单，保留蓝色主题与既有数据；e2e 88/88 含三视口与减少动画 | 供应商卡片、详情、模型发现/配置/默认切换、保存失败恢复和移动焦点闭环；三视口视觉/e2e 通过 |
| 首要任务 2：B-LLM-PROVIDERS v1 | ✅ 已实现：38 条注册表 + 6 backend 分派 + 专用适配（Azure/Codex/Copilot/CodeBuddy）+ 发现来源 + 受控推理 + 迁移/补偿 | 逐供应商实现和隔离上游证据；可用凭证下真实测试独立记录；没有真实凭证的条目保持 not_run |
| B-MODEL-INTEGRATE v1 | 外部队长已在本批内串行联调（8001 隔离后端 + 5174 + `.next-test`）并留证；交本Codex只读审查 | 同一目录从管理到真实聊天可用，旧配置兼容，R-01/R-07/R-08/R-12/R-13逐项复核；未通过项保留阻断 |
| 后续：B-H0R 审查阻断收口 | ✅ R-02/R-04/R-06（B-H0R-SHELL）、R-03（B-H0R-CHAT-LINKS）、R-10（B-H0R-CHAT-LINKS + B-CHAT-SOURCE-FINISH）、R-11（B-COURSE-RESOURCE-SAFETY）、R-09（B-READING-NAV-SCROLL v1）均已关闭；**剩余仅 R-13**（模型真实长答预算），纳入 B-H0R-MODEL/T1 | 全站主页唯一为 `/chat`（已达成）；所有已实现路由有唯一当前菜单/抽屉焦点（已达成）；主聊天生产路径无 mock 模式、其他模块批准的显式模拟保留且标注（已达成）；来源回链以真实 sessionId 定位、可选 messageId 会话内定位（已达成）；阅读伴生不抢占滚动、会话有前进后退历史、迟到事件不跨会话（已达成）；凭证故障可回滚；相关前后端与浏览器回归通过 |
| B-H0R-MODEL 原任务并入首要两项 | R-07/R-13 的受控 reasoning/thinking、模型预算和耗尽行为并入模型前后端任务，不再另开重复实现批；R-01/R-08/R-12也在该范围处理 | 历史缺陷编号与首败保留，只有实际回归通过才关闭；不能以Flash隔离8192成功关闭全协议验收 |
| H1 书籍与课程闭环 | 补 compiling/paused/error、流式生成、暂停恢复、书籍聊天和课程学习会话，复用既有 14 类 block 与保存数据 | 状态链、取消、失败重试、刷新恢复、资源/产物引用完整；三视口按聊天基准通过 |
| H2 既有模块收口 | 阅读媒体原视图与伴生过程，写作/Whisper，学习空间/笔记/题库来源，S3 产物来源 | 损坏读取、配额、多键失败和过期事件不丢数据；跨页身份正确；各模块视觉和动画有证据 |
| H3 伙伴与智能体 | 列表、新建、详情、群组、渠道、任务过程、工具、产物和历史 | 创建→执行→结果→恢复可演示；等待、失败、取消、重试齐全；配置单一来源 |
| H4 精通与记忆 | 路径/节点/会话/反馈/阶段交接；记忆总览、冲突、图谱和 L1/L2/L3 | 精通新轮与普通 ask_user 区分；进度、编辑、引用和恢复完整 |
| H5 账户与完整设置 | 登录/注册/资料/管理的本地身份与权限视图；补齐工作空间、解析、网络、记忆、任务模型等设置 | 本地身份明确标注；校验、加载、错误和权限状态完整；设置搜索/锚点/历史/业务联动通过 |
| H6 全站视觉与动画总验收 | 集中补齐所有首页、列表、详情、弹窗和公共控件 | 1440×900、1920×1080、390×844、主题、长文/空态/错误、键盘/焦点、减少动画；检查开始/过渡/结束与快速中断 |
| T1 真实服务轨道 | 三协议实际供应商；主聊天复杂能力真实事件/后端；解析、MCP/Skills、STT 等按批接入 | 首段在末包前可见、reasoning、停止、错误/重试、模型选择与历史恢复分别有证据；生产主聊天绝不回退模拟 |
| T2 自有规划轨道 | `/papers`、`/question-bank`、`/templates` 与现有题库/书籍/教案模板关系 | 单独确定范围和矩阵，不混入 53 项参考统计，不移除现有入口 |
| H7 最终交付 | 必需页面、AI 交互、动画、数据兼容和阻断问题全部闭环 | 全量工程/API/浏览器检查，三矩阵逐项证据；真实与模拟边界清楚后才生成最终验收报告 |

停止规则：出现数据丢失、错误会话归属、凭证不一致或假成功时，先修阻断问题再扩展。主聊天复杂能力仍全部禁用时只能交付受限阶段，不能称“全部 AI 交互完成”。

## 6. 首要任务卡与接手顺序

### 6.1 历史授权 MODEL-EXEC v3（2026-09-13 已完成，保留日期与当时状态）

> 本节记录授权与断点当时的表述；其执行已完成（见 6.2/6.3/6.4/6.5）。下方“当前代码起点实测af9cb78；尚无registry.py”“下一动作由外部队长执行MODEL-EXEC v3”等是**当时**状态，不代表现状。

用户要求由其他Agent完成代码落地，本Codex只做交付审查。回退后旧启动文本恢复了“等Codex冻结合同”的限制，这是本次重复停在P0的原因。本节明确替代旧启动提示词、P0-handoff子任务卡中与之冲突的写权限/暂停要求；其技术取证继续参考，不以旧权限阻塞实施。

- 当前代码起点实测af9cb78，分支codex/replica-review-20260908；尚无registry.py。用户改动仅.zcode/agents/evidence-collector.md与independent-acceptor.md，必须保留。外部P0 v2的draft-2、覆盖表和handoff在_work/model-providers-v1/，本Codex不覆写它们。
- 本Codex当前没有产品代码写入、构建或测试进程；本次文档提交完成即释放本批文档/Git写入权。外部队长接收MODEL-EXEC v3后，指定单一合同/文件/资源负责人，直接继续实施，不只回复确认再等待。
- **外部队长拥有完整实施权**：模型管理UI（使用frontend-design）、LLM供应商、app/schemas、前端contracts/services、model_views、路由/main/lifespan、仓储/凭证迁移、必要依赖与锁文件、测试和集成。无需本Codex代写共享契约或批准P1/P2/P3阶段切换。
- 外部队长按PROJECT_GUIDE的D1–D16决定自行定稿完整contract-v1，同步Python/TS/HTTP规格并记录文件散列；这是本队内部实现基线，不是发回用户等待签字的文档。接着连续完成P1/P2/P3、模型UI、联调和独立验收，不能以提案/注册表/假接口当作全部完成。
- 按根AGENTS允许的临时负责人授权，外部队长本批独占STATUS、PROJECT_GUIDE、API、三矩阵、必要锁文件及本地Git提交；本Codex后续只读审查。子实现者不自行提交，队长检查范围、生成物和秘密后小提交，不推送/部署。
- 运行资源由外部队长管理8001、5174、.next-test及隔离浏览器；不使用用户8000/5173，不改正式.env/.local-data或真实浏览器草稿，不读取他人登录文件。各并行角色分开数据、日志和输出，依赖构建/共享测试串行。
- 完成适用typecheck/lint/test:unit/build、test:api/test:chat、视觉/e2e和可用凭证下真实供应商验证；实现、模拟上游、视觉、真实服务分别记录。缺真实登录条件只阻塞对应实测，继续其他独立代码；不得伪造成功、自动关推理掩盖问题或删掉专用供应商。
- 最终交付代码提交号、修改文件、38条实现/隔离/真实覆盖表、命令/退出码/证据、未完成与风险，以及写入/服务释放状态。独立验收者只读稳定候选，发现问题交实现者修复复验；不在只有文档时结束整个执行任务。

P0待决历史项：

| 项 | 本轮处理 |
| --- | --- |
| H1旧提交 | 尊重用户回退，不cherry-pick/恢复d678ef3，也不清理悬空对象或_work参考产物。从af9cb78现有代码重新实施。实查d678ef3父提交是cc32b8a（已转交代码实施权），因此不能按回退后的旧任务卡反推其当时越权；这也不构成对该代码质量的认可。 |
| H2旧探针 | 作为R-13的P3待复验线索保留：外部报告推理关闭/2048时正文较早出现；来源是已回退候选，本轮未复验，不计验收。固定模型/提示/配置，比较默认、显式开关与受控预算，并检查finishReason=length的截断，不能只看字数判定完整成功。用户正式模型配置不改。 |

本轮仅更正执行授权和提示词，未写或恢复产品代码、未重新运行产品/供应商测试（**当时状态**）。下一动作由外部队长执行MODEL-EXEC v3，不再重新做一轮P0等待本Codex冻结。**该执行已于 2026-09-13 完成并通过独立验收，见 6.2–6.5。**

### 6.2 MODEL-EXEC v3 执行结果（2026-09-13，外部队长交付）

状态：**ready_for_review**。候选为本批本地提交（`git log -1`）；合同版本 `contract-v1`。

| 项 | 结果 |
| --- | --- |
| 合同 | 自行定稿并落地；散列见 `_work/model-providers-v1/contract-v1.md` |
| 后端 | 注册表 38 条（`registry.py`）、6 backend 分派、Azure/Codex/Copilot/CodeBuddy 专用适配、发现 source、受控推理、迁移 v1→v2、R-01 补偿/R-08 清除/R-12 文案 |
| 前端 | 供应商卡片 → 详情弹窗 → 发现多选 → 参数/推理表单；contracts/services 同步；保留蓝色主题与既有数据 |
| 测试 | `test:api` 164/164、unit 262/262、e2e 88/88、typecheck/lint/build 通过（证据见第 4.1 节） |
| 真实 | DeepSeek 普通/长答复验通过；R-13 复现并给出受控推理开关结论（第 4.3 节） |
| 覆盖表 | `_work/model-providers-v1/provider-coverage-38-implemented.md`（38 行实现/隔离/真实三态） |
| 未完成 | Responses/Anthropic 无可用凭证、Codex 真实登录缺自有 OAuth 应用凭据、Copilot/CodeBuddy 缺用户令牌/Key（均 `not_run`，范围未删）；R-13 完整长回答仍需显式提高预算 |
| 资源 | 8001/5174 已释放；正式 `.env`/`.local-data` 未被写入；`.zcode/` 用户改动保留 |

首败与风险：R-13 默认预算零正文（预期复现，非回归）；Copilot 真实调用需用户自行获取 GitHub 令牌，属产品流程而非实现缺陷。

### 6.3 独立审查 MR-01~MR-16 修复结果（2026-09-13）

审查报告 `_work/review-1805397/REVIEW.md`。逐项修复、回归与状态：

| MR | 修复位置 | 回归证据 | 状态 |
| --- | --- | --- | --- |
| MR-01 协议分派 | `factory.create_provider` + 新增 `resolve_effective_format`；openai_compat 的 Responses 格式不再固定落 Chat | `test_explicit_and_migrated_responses_both_use_responses_endpoint`、`test_openai_compat_provider_responses_format_is_not_downgraded_to_chat`、`test_migrated_responses_connection_keeps_protocol_after_repository_roundtrip` | pass |
| MR-02 本机免 Key | 新增 `services/model_readiness.py`；`base.resolve_api_key` 按注册表判定；`chat.py` 与视图改用 `callable`；前端按 `callable` 禁用 | `test_local_provider_is_callable_without_key`、`test_readiness_distinguishes_local_cloud_and_managed`、`test_connection_view_exposes_callable_flag`；前端 MR-02 两项 | pass |
| MR-03 受管键持久化 | `secrets.scoped_key`（`__` 命名）；codex/copilot 改用并兼容历史冒号键 | `test_managed_keys_are_writable_in_file_secret_store`、`test_legacy_colon_managed_keys_are_still_read`、`test_managed_auth_keys_survive_file_store_in_http_flow` | pass |
| MR-04 并发回滚 | `ModelConfigRepository.run_atomic/update_connection_atomic`：revision 校验+写入+凭证同临界区 | `test_concurrent_update_cannot_roll_back_other_requests_credential` | pass |
| MR-05 删除孤儿 | `delete_connection_atomic`：先清凭证再落盘，失败整体不删 | `test_delete_failure_keeps_both_sides_and_is_retryable`、`test_delete_connection_reports_credential_cleanup_failure` | pass |
| MR-06 迁移备份 | `_backup_once` 失败抛 `CONFIG_BACKUP_FAILED` 并阻止写入 | `test_migration_backup_failure_blocks_write` | pass |
| MR-07 保存回退旧值 | `saveConnectionDetail` 用 PUT 返回值重建草稿与基线 | 前端「保存后用服务端返回值刷新表单」、真实联调「保存 Base URL 后表单保持新值」 | pass |
| MR-08 跨连接草稿 | `draftConnectionId` 隔离；`saveProfile` 切到目标连接草稿 | 前端「模型移到另一连接后详情加载目标连接草稿」 | pass |
| MR-09 迟到换票复活 | `CodexOAuthService._generation` + 换票后重校验；`invalidate` 用于取消/退出 | `test_codex_logout_during_exchange_prevents_relogin`、`test_codex_cancel_during_exchange_prevents_relogin` | pass |
| MR-10 Copilot 退出遗漏 | `ModelAuthService.logout` 清本连接全部来源（含 connectionId Key、历史键） | `test_copilot_logout_clears_the_connection_credential` | pass |
| MR-11 Codex 过期/续期 | `CodexOAuthService.refresh_tokens/get_access_token`；provider 走 `_build_headers`；过期状态报 `AUTH_EXPIRED` | `test_codex_expired_token_is_not_used_and_requires_reauth`、`test_codex_expired_token_refreshes_when_refresh_succeeds` | pass |
| MR-12 关闭绕过确认 | 统一 `requestOverlayClose` + 放弃确认对话框 | 前端「X 关闭在有未保存更改时先确认」 | pass |
| MR-13 导入失败隐藏 | `importModels` 返回成功/失败；`ModelListPicker` 仅成功清空并展示父层错误 | 前端「导入失败保留勾选并在弹窗内显示错误」 | pass |
| MR-14 附加头功能丢失 | `ConnectionDetail` 恢复附加请求头编辑（非敏感白名单，定义于后端） | 前端「详情可维护附加请求头」 | pass |
| MR-15 探针可写正式 .env | 探针与 live-backend 改纯内存凭证 + 运行前后逐字节断言；文档记录更正 | 探针内 `_isolation` 断言 + 本批 `.env` md5 前后一致 | pass（记录已更正） |
| MR-16 无默认地址无法创建 | 新增 `NewConnectionForm`：先收集必填草稿，失败保留输入 | 前端 3 个参数化创建 + 「创建失败保留表单与错误」；真实联调「UI 创建无默认地址供应商」 | pass |

当时状态：R-01 待独立复验、R-13 待回真实长答复验。**R-01 已在 6.4 复验通过后关闭**；R-13 仍未关闭（见 4.3 与 6.5）。

### 6.4 独立验收结论（2026-09-13）

两名独立验收者分别对后端数据/凭证一致性与前端 UI 行为只读复验，覆盖 MR-01~MR-16：

- 候选 `560ac76`（diff 散列 `d877b881944c3d64…`）；两方复验结论均为 **pass**（9 项后端 / 7 项前端，均基于自建探针，不复用实现者断言；后端另复跑全量 181 passed）。
- 验收者指出两处残留并由队长修复为 `4ef803b`：`ConnectionDetail` 的 `AuthPanel onChanged` 曾是 no-op（受管认证完成/退出后目录不刷新）；`_work` 内 `real_backend_server.py`、`provider_probe_v2.py` 仍注入文件型 SecretStore（MR-15 点名项）。两方对 `4ef803b` 再做只读增量复验。
- 未覆盖：真实供应商调用（无凭证）、Codex 真实 OAuth 登录、视觉/动画/e2e 曲线 —— 均 `not_run`，不据此升级视觉或真实服务验收。
- R-01 复验通过，**已于 2026-09-13 关闭**；R-13 仍未关闭。

### 6.5 B-MODEL-ACCEPT v1 结果（2026-09-13，起点 3dfc2fa）

目标：完成模型批尚未覆盖的浏览器验收与真实链路核查。**不重做 P0、不改已通过合同实现、不扩展其他模块。**

#### 功能 / 视觉 / 动画 / 真实服务分级结论

| 维度 | 结论 | 证据 |
| --- | --- | --- |
| 功能（后端 API） | **pass** | 普通非流式与 SSE 分开测量（纠正上轮用 SSE 冒充普通调用）：`/model-profiles/{id}/test` `stream:false` 返回 `application/json` 单 JSON、`ok:true`；`/chat/stream` 为 `text/event-stream`。`test:api` 181/181。见 `docs/qa/model-accept-20260913/r13-api-report.md` |
| 功能（浏览器全链路） | **pass** | 创建连接 → 发现/手添模型 → 保存 → 普通/流式测试 → 设默认 → 聊天选择 → 刷新保持；真实隔离后端 8001 + 真实 DeepSeek。 |
| 功能（嵌套交互） | **pass（本批修复）** | 发现并修复两处缺陷：二级面板打开会替换详情导致 Escape 连关两层；详情有未保存修改时经二级面板 Escape 会静默丢草稿。修复后 4/4 正式 e2e 通过（`tests/e2e/model-settings-nesting.spec.ts`）。 |
| 视觉 | **pass（本人实际查看）** | 1440/1920/390 三视口截图（`_work/accept-model-v1/shots/`，关键 6 张入 Git `docs/qa/model-accept-20260913/`）；无横向溢出；蓝色主题与供应商图标/留白/分隔线符合当前学习问答基准。 |
| 动画 | **partial（未做曲线采样）** | 150ms 卡片过渡、active scale .995、`prefers-reduced-motion` 关闭过渡；减少动画下详情可用。未录制开始—过渡—结束曲线与快速中断，不据此升级全站动画验收。 |
| 真实服务 | **partial（仅 DeepSeek）** | DeepSeek 普通/SSE/长答均真实通过；Codex 真实 OAuth 登录、Copilot/CodeBuddy、其余 36 条供应商 `not_run`（缺凭证/本机服务）。 |

#### R-13 真实复验（模型与问题固定）

API 三档（临时副本改 profile，不改正式配置；仅 DeepSeek）：

| 模型 | 档 | 预算 | 推理 | finishReason | 正文 | 推理 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pro | 默认 | 2048 | 默认 | 无 | 0 | 2738 | 零正文（`EMPTY_RESPONSE`） |
| pro | 显式关推理 | 2048 | off | length | 3210 | 0 | **截断，不算成功** |
| pro | 受控 | 8192 | off | stop | 8433 | 0 | **完整结束** |
| flash | 默认 | 2048 | 默认 | 无 | 0 | 2671 | 零正文（`EMPTY_RESPONSE`） |
| flash | 显式关推理 | 2048 | off | length | 3033 | 0 | **截断，不算成功** |
| flash | 受控 | 8192 | off | stop | 4585 | 0 | **完整结束** |

浏览器侧（真实 DeepSeek，隔离后端）：受控 8192 档**首个可见中文 1172ms**（限助手正文气泡，排除占位"正在等待模型回复"）、KaTeX **12 处 0 错误**、推理折叠为"已完成"、**停止**显示"已停止"并保留已生成内容、默认预算档如实显示 `EMPTY_RESPONSE` 与**重试**入口且重试可用、刷新后内容恢复。

**R-13 结论（仍未关闭）**：默认预算下推理吃满全部额度 → 零正文；显式关推理可在默认预算内产出正文但 `finishReason=length`（截断）；完整长回答需**显式提高预算**（受控 8192 才 `stop`）。**未采用**自动关推理掩盖失败、无界加预算或把 `length` 记为成功。

#### 隔离与资源

- 浏览器与 API 均用隔离后端 8001（临时目录配置副本 + **内存型凭证**，`scope=='process'`）；前端 5174 + `.next-test`。
- 正式 `apps/api/.env` md5 `c56f6ffbbbc45bb99f04ce339d270f61` 与本批前后一致；正式 `.local-data/model-config.json` 未被写入。
- 真实供应商调用为低调用量固定问题；三档对照在**临时副本**上改 profile，未动正式配置。
- 8001/5174 已释放；未推送/未部署。

#### 独立验收（候选 9965592）

独立验收者对 `9965592`（diff 散列 `6c6f198f0fcc6f4e1c1168d67e12c590`）只读复验，结论 **pass**：
- 复跑通过数与 STATUS 一致：`test:api` 181/181、`test:unit` 274/274、官方 e2e 92/92（跑前先 `npm run build`）。
- 嵌套交互 4 用例为期望行为断言、纯 fixture；overlay/child 改造经源码复核未发现状态不一致。
- R-13 证据可核：普通与 SSE 确为分开测量，`firstVisibleChineseMs` 限定助手正文气泡，三档 `finishReason` 如实（无把 `length` 记成功）。
- R-01 关闭依据为独立探针（并发/删除/备份三向），且后端自复验候选以来零改动。
- 脱敏与范围通过：密钥模式 0 命中、无完整连接 ID；改动仅在模型相关文件。

独立验收者**未运行**：真实供应商调用（无凭证）、浏览器视觉/动画曲线（未实际操作，仅核 2 张截图）、typecheck/lint。记录中"视觉 pass"仅为队长本人实际查看的结论，独立验收不予背书。

### 6.6 B-H0R-SHELL v1 结果（2026-09-13，起点 b360d7c）

目标：处理 R-02/R-04/R-06，统一全站主页入口、公共导航与错误页外壳。**不改模型协议/凭证/推理预算，不重做各模块业务内容。**

#### 逐项结论（均以**独立验收者在候选 e7fb2a4 上亲自浏览器复验**为准）

| 项 | 结论 | 实现与证据 |
| --- | --- | --- |
| R-02 唯一主页 `/chat` | **pass / 已关闭** | `navigation` 仅一条 `home: true`；`HOME_PATH`/`HOME_LABEL` 从它派生，运行时断言必须存在。品牌按钮（头部+侧栏）、404 与规划页返回入口、默认标题、可访问名称全部改由它派生。grep 确认无残留把 `/lesson-plans` 当主页（仅教案模块自身引用与 `/api/v1/lesson-plans/fill` 端点）。 |
| R-04 唯一当前菜单 | **pass / 已关闭** | 新增单一解析器 `resolveCurrentNavigationId`（最长前缀），桌面侧栏与手机抽屉共用；隐藏直达页登记 `parentPath`：桌面标父菜单、抽屉标自身。独立验收者亲验命中表：/whisper→协同写作、/notebooks→学习空间、/courses→书籍，其余已实现路由各自命中，404 无当前项，每个路由 `[aria-current="page"]` 恰好 1 个。 |
| R-06 统一壳的 404/错误页 | **pass / 已关闭（含区分）** | 新增 `ShellScope`（声明是否已有公共壳）+ `StatusShell`（仅在缺壳时补一层）。**404 已实测**：未知路径与独立模块深层 404 都恰好一层 `.app-shell` 且保留侧栏（e2e `shell-home-nav.spec.ts`）。**错误页 reset 的运行时触发未验**：生产构建下无法在不改产品代码的前提下注入客户端错误，仅以源码与构建产物确认 `重新尝试`（reset）与 `返回主页` 两个恢复入口存在；reset 的实际恢复行为记为未执行。 |

#### 验证与边界

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` / `lint` | 通过（0 warning） |
| `npm run test:unit` | **278/278**（新增 `navigation.test.ts` 唯一主页/解析器/父菜单 4 项） |
| `npm run test:api` | **181/181**（本批未改后端） |
| `npm run build` | 通过，23 静态页 |
| 浏览器 e2e | **119/119**（新增 `tests/e2e/shell-home-nav.spec.ts` 27 项；并更新 `lesson-plan.spec.ts` 断言品牌入口改回 /chat） |
| 三视口视觉 | 1440×900 / 1920×1080 / 390×844 逐路由无横向溢出；实际查看 404（桌面/手机）、whisper 父菜单高亮、chat 1920 截图；减少动画下壳可用（`docs/qa/shell-accept-20260913/`） |
| 折叠/手机抽屉 | 折叠偏好跨页保持（含 404 与独立模块）；抽屉焦点落当前项、Escape 关闭并返回触发按钮；**Tab/Shift+Tab 焦点圈定已有既有用例** `tests/e2e/sidebar-chat-fixes.spec.ts:76-79`（Shift+Tab 从关闭按钮回绕到「设置」、Tab 再回到关闭按钮），本批未重复新增；学习记录 236px 中栏仍仅聊天 |

未运行：错误页 `reset` 的运行时触发（生产构建无法在不改代码下注入客户端错误；已用源码与构建产物确认恢复入口存在）；动画曲线逐帧采样（仅静态截图与类名断言，标 partial）。

#### 独立验收（候选 e7fb2a4）

diff 散列 `b262f98c84a885158ddef691e5f79312…`。独立验收者结论 **pass**：四套件通过数与实现者一致（e2e 119 / unit 278 / api 181）；自己 grep 确认 R-02 无残留、读源码判断 R-04 解析器不可能多项命中、R-06 补壳方向安全；**亲自在 1440/1920/390 遍历 14 个路由 + 404 + 抽屉**，给出命中表与 11 张截图；范围仅公共壳/导航/状态页/测试/证据，未触碰模型协议与凭证。其未运行项：错误页运行时触发、动画曲线。

### 6.7 B-H0R-CHAT-LINKS v1 结果（2026-09-14，起点 957730d）

目标：处理 R-03（主聊天生产模拟残留）与 R-10（笔记/题库到聊天的错误来源链接）。**不改模型协议/凭证/推理预算，不扩展其他模块。**

#### R-03 主聊天生产仅真实

| 项 | 结论 | 证据 |
| --- | --- | --- |
| 不可达 mock 分支与残留参数 | **pass** | 移除 `ChatWorkspace` 的 `const mode='real'` 与所有 `mode` 依赖、`mock={false}` 参数（InfoPanel/ComposerContextChips）、`withMode` 变量；`InfoPanel` 的"模拟模型"整块与 `ComposerContextChips` 的 `mock &&` 人设胶囊（无入口的死状态机，人设改由空间菜单直达）一并删除。 |
| 误导文案 | **pass** | 两处"请切回…或使用模拟模式"改为不再指向已删功能（能力不可用→"请切回对话能力"；附件不支持→"请移除附件后再发送"）。 |
| 专用 CSS 死规则 | **pass** | 删除 `.chat-mode-switch*`、`.chat-banner.mock`、`.chat-mode-chip`、`.chat-stale-notice`（TSX 零写入者，已 grep 核实）；确认 reading 复用 `chat.css` 的其他规则未受影响。 |
| 契约注释 | **pass** | `ChatServiceKind`/`Conversation.mode` 保留但注明：生产恒为 `real`，`mock` 仅用于**读取历史**与测试替身注入，不存在运行时模拟分支。 |
| 真实失败不回退模拟 | **pass（隔离验收）** | 隔离后端 8001 上把默认问答 profile 指向不存在的 `modelId`：浏览器显示 `生成失败 1s` + `上游返回错误（HTTP 400）(UPSTREAM_ERROR)` + 「重试」，原问题保留，**无【模拟回复】**。见 `_work/chat-links-v1/`。 |
| 旧模拟库不读不写不清空 | **pass** | 全仓无 `zhiqikeyuan-chat-mock` 引用；未新增任何清库逻辑。 |
| 他模块显式模拟保留 | **pass** | reading/writing/knowledge/whisper 的显式模拟与标识未改；其 `kind:'mock'` 为各自独立字面量，仅 reading 共享 `ChatServiceEvent`（未改形）。 |
| 测试替身仅测试路径 | **pass** | `tests/fixtures/scripted-chat-store.ts` 等仅被 `*.test.ts(x)` 引用，生产 bundle 零引用。 |

#### R-10 来源回链按真实 sessionId

| 项 | 结论 | 证据 |
| --- | --- | --- |
| 保存链路补记 sessionId | **pass** | `ChatWorkspace` 构建产物条目时带 `store.activeId`；经 `ArtifactPanelItem.sessionId` 传到 `QuizArtifactView`/`ReportArtifactView`，随 `saveQuizEntries`/`saveNotebookEntry` 落库（`QuizBankEntry.sessionId?` / `NotebookEntry.sessionId?`）。 |
| 题库链接修正 | **pass** | 原 `href=/chat/${messageId}?mode=mock`（把 messageId 当 sessionId 且带死参数）改为 `SourceSessionLink`：仅当条目带可靠 `sessionId` 且会话存在时渲染真实深链。 |
| 笔记链接修正 | **pass** | 去掉 `?mode=mock`；改用 `useSourceSessionLink(metadata.sessionId)` 做异步存在性校验。 |
| 旧数据兼容 | **pass** | 无 `sessionId` → 不显示链接、保留内容、不报错；会话已删除 → 显示"来源会话已不存在"并保留内容，**不猜测绑定、不建假会话**；空串/非字符串身份视为缺失；顶层扁平 `sessionId`（未来回填）也能读取。单测：`notebook-store.test.ts`/`space-store.test.ts` 新增 7 项。 |
| 单一拼装点 | **pass** | 新增 `services/chat-source.ts` 的 `conversationSourceHref()`，业务页不得各自拼 URL；`useSourceSessionLink` 复用仓储 `load()` 校验存在性。 |

#### 验收覆盖与边界

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` / `lint` | 通过（0 warning） |
| `npm run test:unit` | **285/285**（新增 R-10 兼容单测 7 项） |
| `npm run test:api` | **181/181**（本批未改后端） |
| `npm run build` | 通过 |
| 浏览器 e2e | **128/128**（新增 `tests/e2e/chat-source-links.spec.ts` 9 项：正确会话/旧链接/会话删除/缺失身份/重名内容/刷新/前进后退/笔记两态） |
| R-03 隔离验收 | 2/2 通过（真实失败路径截图 `_work/chat-links-v1/shots/r03-error-path.png`） |
| 真实供应商 | 本批为前端契约/链接与文案清理，未新增真实供应商断言；沿用模型批 DeepSeek 结果，其余 `not_run` |

#### 独立验收（候选 a5bb39c）

独立验收者对 `a5bb39c`（diff 散列 `3e16d77e2d1205039d40a0b68838a4a0…`）只读复验，结论 **pass**：
- 四套件通过数与实现者一致（e2e 128 / unit 285 / api 181）；`apps/api` 零文件改动。
- R-03：生产 store 只建 `{ real }` 单 store、`mode` 恒 `real`；残余 `ChatServiceKind/mode` 引用仅历史读取与测试替身；4 类死 CSS 源码零写入者，reading 复用 `chat.css` 的规则（如 `.chat-status-text`、`.chat-banner` 基础样式）未受删除影响；旧模拟库无生产引用且未被清空。
- R-10：亲自浏览器验证来源链接：真实 sessionId → `/chat/<sessionId>` 且点击到达该会话；无/空串/数字身份 → 不显示；会话删除 → "来源会话已不存在"且内容保留；重名两条各指向各自会话；刷新与前进后退目标正确；旧链接 `/chat/<messageId>?mode=mock` → 明确提示不存在、无模拟回答。
- 范围与脱敏通过。

**独立验收者提出的非阻断观察**：旧深链未命中时，聊天会打开最近会话并显示明确横幅（"已打开最近会话"）；该行为在起点 `957730d` 已存在、本批未触碰，属"带提示的回落"而非静默猜测；是否停留空态属产品措辞决定，留待后续批次。

未运行（独立）：错误页 reset 运行时、动画曲线、三视口视觉、真实供应商——均 `not_run`。

未执行：错误页 `reset` 的运行时触发（见 6.6 说明）；动画曲线逐帧采样（沿用既有 partial）。旧链接（`/chat/<messageId>?mode=mock`）在 e2e 中确认**不静默落到最近会话**，而是显示"链接指向的会话不存在"。

### 6.8 B-CHAT-SOURCE-FINISH v1 结果（2026-09-14，起点 97c6992）

目标：在上一批"来源回链"基础上补齐**消息定位**、失效会话不可用态，并用**真实保存链路**证明身份落库。**不重做 R-03、不改模型/凭证/预算。**

#### R-10 分项结论

| 分项 | 结论 | 证据 |
| --- | --- | --- |
| **A. 会话回链**（上批） | **pass** | `services/chat-source.ts` 单一拼装；`useSourceSessionLink` 用仓储 `load()` 校验会话存在；无身份不显示、会话删除提示不可用。 |
| **B. 消息定位**（本批） | **pass** | 链接现同时携带 `sessionId` 与可选 `messageId`（`/chat/<sessionId>?message=<messageId>`）；`app/chat/[sessionId]/page.tsx` 透传 `searchParams.message`；`ChatWorkspace` 先加载会话，再在 `[data-message-id]` 中**仅于该会话内**查找并 `scrollIntoView`，给出"已定位到来源消息"提示。`Message.tsx` 根元素新增 `data-message-id`。 |
| B1 只在该会话内查找 | **pass** | e2e「另一会话有同名内容也不会被选中」：打开 sess-b 并定位 n2，断言 sess-a 的 m2 不在 DOM。 |
| B2 消息已删除 | **pass** | 找不到时提示"原消息已不存在，已打开所属会话"，会话内容与原题目保留（e2e 覆盖）。 |
| B3 遵守减少动画 | **pass** | `scrollIntoView` 的 behavior 与高亮过渡按 `document.documentElement.dataset.motion === 'reduced'` 或 `prefers-reduced-motion` 决定；e2e 在 reduced 下仍定位并提示。 |
| B4 竞态防护 | **pass** | 位置 effect 依赖 `[targetMessageId, initialSessionId, deepLinkHandled, sessionUnavailable, store.activeId]`；切换会话/新建时清空目标与提示；e2e「切到别的会话不会定位到错误消息」验证。 |
| **C. 失效会话不可用态**（本批） | **pass** | 深链与 popstate 遇到不存在的会话时调 `store.deactivate()`：清当前会话、**不自动展示最近会话、不创建/保存新会话**，显示"来源会话已不存在或已被删除，无法打开"。**学习记录列表与"返回学习问答"保留**。正常进入 `/chat` 的既有行为不变。 |

#### 真实保存链路（本批新增，证明身份落库）

e2e 在浏览器内**点击产物视图的真实保存按钮**（走生产 `saveAll`/`save`），再在业务页读取回链：
- 题库：`/chat/sess-real` 打开产物 → 点"保存到题库"→ `/space/questions` 的链接为 `/chat/sess-real?message=real-save-ai` → 点击后定位到该消息。证明 **sessionId 与 messageId 均由真实保存路径落库**。
- 笔记：报告产物 → "保存到笔记" → `/notebooks` 链接为 `/chat/sess-report?message=real-report-ai` 并定位成功。
- 上一批的"直接注入仓储种子"用例仍保留，两类证据分开记录。

#### 验证边界

| 检查 | 结果 |
| --- | --- |
| `typecheck` / `lint` | 通过（0 warning） |
| `test:unit` | **286/286**（新增 `deactivate` 无副作用单测 1 项） |
| `test:api` | **181/181**（本批未改后端） |
| `build` | 通过 |
| 浏览器 e2e | **140/140**（新增 `chat-message-locate.spec.ts` 12 项；同步更新 `chat-deeplink.spec.ts`、`chat-source-links.spec.ts` 中因 URL 增加 `?message=` 与失效文案变更而失效的旧断言） |
| 真实供应商 | 本批为前端定位与链接行为，未新增真实供应商断言；沿用模型批结果，其余 `not_run` |

未执行：错误页 `reset` 运行时、动画曲线逐帧采样、三视口全站视觉——沿用既有未验状态，不扩大通过范围。

#### 独立验收（候选 aeacea8）

独立验收者对 `aeacea8`（diff 散列 `939a71192961d4fe256f556b8db1666b…`）只读复验，结论 **pass**：四套件通过数一致；亲自在自建 5174 上跑 7 个场景并给出结果表（带 messageId 定位成功；另一会话同名内容不被误选；messageId 已删提示"原消息已不存在"且会话保留；仅 sessionId 无定位提示；失效会话不泄漏最近会话内容且侧栏仍列学习记录；刷新不产生新会话；正常 `/chat` 行为不变）；确认 `deactivate()` 无持久化副作用、真实保存链路用例走的是生产保存按钮；确认本批未改模型/凭证/预算且 R-03 未回退。

独立验收者提出的一点补充已采纳：`deactivate()` 原仅由 e2e 覆盖，本批补了一条单测（counts 286）。其 `not_run`：真实供应商调用（本批无要求）、像素级视觉声明。

### 6.9 B-COURSE-RESOURCE-SAFETY v1 结果（2026-09-14，起点 4869e88）

目标：复现并处理 R-11——知识目录损坏或读取失败时课程页保持可用，不把失败当空数据覆盖，不丢课程与资源引用。

#### 首败（修复前，隔离浏览器注入）

| 注入 | 修复前表现 |
| --- | --- |
| 知识目录 JSON 损坏 | **整页被根错误边界接管**（"页面暂时无法打开"）：课程标题、大纲、资源、约定全部不显示；`CourseDetail.tsx:87` 渲染体调用 `courseResourceStates()` → `readKnowledge()` 抛错且无 try/catch |
| 合法 JSON 但结构非法（非数组） | 同上 |
| 存储读取被拒 | 同上 |
| 添加资源面板 | 弹窗挂载即 `useMemo(() => listResourceCandidates())` 渲染期抛错，整页崩溃（`CourseDetail.tsx:448`） |
| 目录有效但目标已删除 | **本就正确**：显示"不可用：目标已删除或未载入"，未误报错误 |

四例中课程存储 **逐字节未变**（探针断言 `stored === JSON.stringify([COURSE])`），证明当时是"崩溃"而非"覆盖"。

#### 修复

- `services/courses-store.ts`：新增 `readResourceDirectories()`——三个目录**各自独立**读取，失败目录记为 `null` + 错误信息，不阻断其他目录；快照作为参数传入 `listResourceCandidates(snapshot)` 与 `courseResourceStates(course, snapshot)`，渲染路径不再读目录。新增 `subscribeResourceDirectories()` 汇总三目录事件。
- 资源状态由二值改为三态：`available` / `missing`（目录成功但目标不存在，**保留原"不可用"语义**）/ `unknown`（目录读取失败，**不断言目标已删除**）。
- `features/courses/CourseDetail.tsx`：目录快照在 effect 中集中读取（不再渲染期读取），资源区与附加弹窗显示失败原因 + **重试**（`refreshDirectories`）；弹窗在部分目录失败时**仍列出成功目录的候选**（修复了实现过程中"一处失败即隐藏全部候选"的自我引入缺陷）。
- 不自动删除失效引用；修复数据后重试即恢复，不需清空浏览器数据。

#### 验证

| 检查 | 结果 |
| --- | --- |
| `typecheck` / `lint` | 通过（0 warning） |
| `test:unit` | **292/292**（新增 R-11 容错单测 6 项：损坏/非法/读拒/三态/数据保护/不阻断） |
| `test:api` | **181/181**（本批未改后端） |
| `build` | 通过 |
| 浏览器 e2e | **149/149**（新增 `course-resource-faults.spec.ts` 9 项：两类损坏 + 读拒 + 目标已删 + 故障→重试→修复→恢复 + 弹窗不阻断 + 正常增删改 + 其他目录不阻断 + 手机视口） |
| 数据未丢失 | 每例断言课程存储与注入前逐字节相同；引用未被自动删除 |
| 桌面/手机 | 1440 与 390 均检查；保留公共壳与"返回课程列表"，无横向溢出 |

脱敏截图（修复后形态）随 Git 保存于 `docs/qa/course-r11-20260914/`。

未执行：动画曲线逐帧采样、真实供应商、其他模块——沿用既有未验状态，不扩大通过范围。

#### 独立验收（候选 2308822）

独立验收者对 `2308822`（diff 散列 `939276be32a025829fc76d1f3d9e551f…`）只读复验，结论 **pass**：
- 四套件通过数一致（e2e 149 / unit 292 / api 181）；`git diff` 确认 knowledge/notebook/books 的严格读取接口与 local-collection **零改动**（其他调用方语义不变）。
- 源码复核确认三目录独立捕获、失败记 `null`+错误、快照化后渲染期不再读目录、`subscribeResourceDirectories` 汇总三事件、无自动删除失效引用。
- **亲自浏览器实测 7 例 22 断言全通过**（自建脚本，非实现者 spec）：a) JSON 损坏、b) 非数组、c) 读取被拒 → 课程正文/大纲/约定可见 + 错误与重试 + "暂无法确认"且无"目标已删除"字样、无未捕获异常；d) 目标已删 → 显示"不可用"且无目录错误；e) 故障→重试仍败→修复数据→重试恢复（全程不清数据）；f) 故障时弹窗仍列出成功目录的书籍候选（自修复点实测确认）；g) 正常附加/打开/解除/刷新正确；h) 390 视口可读、公共壳与返回入口保留、无横向溢出。每例课程存储与注入前**逐字节相同**。
- 脱敏通过（`docs/qa/course-r11-20260914/` 仅 3 张截图，无密钥）。

其 `not_run`：真实供应商（本批不涉及）、动画曲线与像素级视觉、notebook 目录单独注入（与 knowledge/books 同构代码路径，风险低）。

### 6.10 B-READING-NAV-SCROLL v1 结果（2026-09-15，起点 e7cd87f）

目标：复核并处理 **R-09**——阅读伴生聊天是否抢占用户滚动位置、丢失会话导航历史，或在切换/卸载后被迟到事件污染。不重做视觉、不接新 AI 服务、不改模型与凭证。

#### 首败（修复前，隔离浏览器 + 应用自带演示数据 + 真实伴生服务）

| 子项 | 修复前表现（可复现证据） |
| --- | --- |
| A 滚动抢占 | 流式进行中用户上滚到顶（`scrollTop=0`，容器确实可滚动），后续增量把视口强拉回底部：`{rightAfterManual:0, top:212, max:212}`，截图 `A-scroll-pulled-back.png` |
| B 迟到事件污染 | 生成中切到新会话，**新会话立即显示旧会话的"生成中"块**（`turnBlocksInNewSession:1`）；迟到 `end` 到达前旧内容可见于新会话，截图 `B-late-end.png` |
| C 会话历史丢失 | 切会话用 `replaceState`，后退直接离开阅读板块：`{before:"/reading/demo-reading-ws", created:"/sessions/rss-…", afterBack:"/reading"}`，未回到上一会话，截图 `C-history.png` |

三例均在**隔离上下文**（端口 5174、`.next-test`、演示数据）中复现，未读取或修改用户 5173 会话与真实草稿。首败脚本与截图保留在 `_work/reading-r09/`（不进正式测试目录）。

#### 修复（`apps/web/src/features/reading/ReadingWorkspace.tsx`、`reading.css`）

- **滚动跟随**：新增 `followBottom` 状态，仅"跟随最新"时自动滚到底；伴生容器 `onScroll` 距底 <90px 视为手动上滚并关闭跟随。自动滚**只作用于伴生消息容器**，不碰阅读正文容器与整页。
- **回到最新**：仅在上滚后出现、由用户点击触发，恢复跟随并只滚动伴生容器（修复过程中发现该按钮在早期编辑里丢失、仅剩注释，已按契约补回）。
- **会话归属轮次**：`turn` 单一状态改为 `turns: Record<sessionId, CompanionTurnState>`；每个会话各自持有轮次与文本缓冲，切走后旧会话继续生成并只写回自身，新会话立即可用。
- **终态守卫**：`turn-start/process/stage/text/usage/error/end` **全部**校验 `sessionId + turnId`，`end`/`error` 不再豁免；收尾回调只在属于该会话该轮时清理状态，且只释放自己的 `AbortController`（不会夺走新轮次的取消能力）。
- **会话历史**：新增 `syncSessionUrl(id, 'push'|'replace')`（地址一致时不写历史），`focusSession` 与新建会话改走 `pushState`；新增 `popstate` 监听，按 URL 重新定位空间/会话，切换前 `flushDraft()` 保证草稿归属正确；后退到 `/reading/<ws>`（无会话）时回落到该空间默认会话。
- **取消语义不变**：取消仍保留已生成内容并标注「（已取消）」落回**原会话**，不重复持久化、不丢草稿。
- **移动端**：`.reading-drawer .reading-companion` 改为填满抽屉高度并允许消息区自行滚动（原先抽屉内容器不滚动，导致"上滚"在移动端根本不成立），与桌面行为一致。
- 已批准的显式模拟保留并仍标注【模拟回复】；未把任何测试控制接口带入生产路径。

#### 验证

| 检查 | 结果 |
| --- | --- |
| `typecheck` / `lint` | 通过（0 warning） |
| `test:unit` | **292/292**（Node 26 下需 `--localstorage-file`；见下方环境说明） |
| `test:api` | **181/181**（本批未改后端） |
| `build` | 通过 |
| 浏览器 e2e | **154/154**（新增 `reading.spec.ts` R-09 五例；既有 17 项阅读用例全通过）——实现者自检；独立验收者另用自写黑盒 8/8 与 reading.spec 17/17 复验 |
| 首败三例复跑 | A/B/C 全部转为通过（同一 `_work/reading-r09` 脚本） |
| 桌面/手机/减少动画 | 1440 与 390 均覆盖；移动端用例在 `reducedMotion: reduce` 下执行 |
| 数据保护 | 全程隔离上下文与演示数据；未触碰用户 5173、官方 `.env`/`.local-data`、真实草稿 |

**环境说明（非本批缺陷）**：本机 Node v26 下 jsdom 的 `window.localStorage` 默认不可用，`npm run test:unit` 会因 `Cannot read properties of undefined (reading 'clear')` 出现 86 项失败。已在**干净工作树**上复现同样失败，确认与本批改动无关；加 `NODE_OPTIONS=--localstorage-file=<tmp>` 后 292/292 通过。这是环境/工具链问题，不改测试代码。

未执行：动画曲线逐帧采样、真实供应商、媒体原视图与阅读视觉验收——沿用既有未验状态，不扩大通过范围。

#### 独立验收（候选 a1fa16e，diff 散列 a21c4e9d…）

独立验收者对 `a1fa16e` 只读复验，结论 **pass**：

- 核对候选与范围：改动 12 文件（ReadingWorkspace.tsx / reading.css / reading.spec.ts / 三份文档 / docs/qa 证据）；`app/schemas`、后端、锁文件、其他模块**零改动**。验收期间 HEAD 前移至 `33ecd58`（纯文档），已用 `git diff a1fa16e 33ecd58 -- apps/ tests/ scripts/ package.json` 确认为 0 行，不影响源码结论。
- 静态复核：`end/error` 与增量同受 `sessionId+turnId` 守卫；`turns` 按会话存放且文本用本地闭包；`syncSessionUrl` 地址一致即返回、用户动作走 push；`popstate` 切换前 `flushDraft`；**`scrollIntoView`/`saveReadingPosition`/`handleScroll` 均不在 diff**（正文滚动未被本批改动）。
- **自写黑盒 8 例全通过**（非实现者用例）：A 真实滚轮上滚后位置保持 + 正文/整页不动 + 「回到最新」只滚伴生容器；A2 底部正常跟随；B 生成中切会话新会话立即干净、迟到 end 落旧会话、切回完整；B2 取消收尾；C 历史+重复切换不加历史+popstate 同步会话与草稿；C2 深链/reload 零额外 push 且无效会话沿用既有提示；F 刷新按会话恢复、不重放生成；G 390+reduce 抽屉一致。
- 实现者回归复验：`reading.spec.ts` **17/17**（含 R-09 五例）。
- 数据保护：`docs/qa/reading-r09-20260915/` 5 张截图逐一目检无密钥；5173 全程无监听。
- 脱敏与范围通过。

其 `not_run`：全量 e2e 154 例（仅复验 reading.spec 17 + 自写 8）、硬件级触摸、动画逐帧、无凭证真实供应商、`test:unit` 在本机 Node v26 的全绿收口（见上方环境说明）。

### 原需求与验收任务卡（技术要求保留，负责人按6.1）

以下取代原“先 B-H0R-UI”的建议；其他页面修复保留在后续计划。**模型两项（B-MODEL-UI / B-LLM-PROVIDERS）已实现并通过独立验收，见 6.2–6.5**；本节技术任务卡作为实现依据保留。开始实施时记录当时 HEAD 和工作树差异，不把文档提交号当产品已验收候选。

### B-MODEL-CONTRACT v1：前后端共同前置

负责人：外部队长指定的合同实现者，直接落地共享代码；不止提交提案。先读根及 apps/web、apps/api 的 AGENTS、README、PROJECT_GUIDE、本文、三矩阵、现有 `docs/API.md` 和实际源码。

当前数据是 `ModelConnection(protocol/baseUrl)` + `ModelProfile(connectionId/modelId/params)`，不是参考的 provider/profile 同名结构。以现有 ID 和目录为骨架，冻结以下增量语义后才能并行修改依赖它的代码：

| 合同项 | 实现要求（设计提案，尚非已上线 API） |
| --- | --- |
| 供应商目录 | 后端单一注册表提供稳定 providerId、名称、别名、认证类型、可选 API 格式及各格式默认 URL、参数/能力约束、发现策略；前端按元数据展示，不维护另一份 URL/能力真值 |
| 连接 | providerId 与 API 格式分开；保留既有 protocol 兼容映射，Azure 等专用认证字段强类型化；自定义 URL 不被切换控件静默覆盖；凭证输入保持/替换/清除语义独立 |
| 模型 | 保留 profileId、connectionId、modelId、默认模型引用；上下文、输出预算、推理开关/深度按供应商约束，区分未知、人工声明、实测证据；模型存在不意味着支持全部能力 |
| 认证 | API Key 的状态接口不回显；OAuth/设备或本机凭证的开始、等待、成功、失败、取消、过期、断开按参考实际流程映射；令牌仅服务端，不能复制用户其他工具的登录态充作测试数据 |
| 保存与迁移 | 版本迁移保留旧三协议、ID、revision与历史；无providerId的旧连接按显式协议映射自定义兼容类型，不猜供应商并换URL。跨.env与JSON写入锁/补偿处理R-01，删除及清除处理R-08 |
| 错误/SSE | 保持现有HTTP错误信封和message.start/text.delta/reasoning.delta/usage/message.end/error事件；取消关闭上游；预算耗尽、认证缺失/过期、未支持能力均不能假成功或回退模拟 |

外部队长保留P0原件，按PROJECT_GUIDE决定直接完成Python schemas、前端contracts和服务接口、API文档的一致落地，内部定稿contract-v1并记录文件散列。随后继续实现，不等本Codex冻结或应用补丁；合同变更由外部队长同步版本和写入者。

### B-MODEL-UI v1：DeepTutor 模型管理界面

**负责人：外部前端实现者；使用 `C:/Users/96022/.codex/skills/frontend-design/SKILL.md`。** 保留以下需求，UI实现与视觉尚未验收。

参考固定为 `F:/DeepTutor` SHA `42fab3cf429a1fbf36b257ab8d116a3814964202`。主要源码为 `web/features/settings/sections/models/{ConnectionsSettingsSection,LlmSettingsSection}.tsx` 和 `web/components/settings/{ConnectionsEditor,ServiceConfigEditor,ModelCards,ModelListPicker,ModelCapabilityFields,ProviderIcon}.tsx`，认证状态参考 `CodexOAuthCard`、`CodeBuddyAuthCard`。实施前还需在隔离浏览器实际核对参考界面，不能只凭组件名宣称视觉复刻。

需求与实现方式：

1. 在现有设置的模型区域保留“连接 / LLM 模型”层级，连接凭证可被多个模型复用。页面展示供应商卡片、图标、名称、模型摘要、当前使用状态和新增入口；供应商卡片打开详情弹窗。**打开/编辑卡片不得切换默认模型**，只有明确“使用此模型”动作才更新默认；会话级模型选择继续沿用现有语义。
2. 详情依次呈现供应商/连接字段、认证状态、API 格式与地址、模型列表。模型卡片支持重命名、展开参数、使用、删除；发现模型支持加载、搜索、多选、去重、空列表、失败重试，保留手工添加任意合法 modelId。不能用静态候选冒充发现结果。
3. 保留当前真实连接/模型增删改、普通测试/流式测试、默认选择、revision 冲突、配置失败时保留输入、刷新恢复和聊天目录联动。表单草稿与服务器已保存态分开；成功响应前不能显示已保存，关闭含未保存更改的详情有明确保留/放弃行为。删除有关联模型/默认模型时先说明影响；Key 空值保持，清除凭证单独确认，不展示已存Key。
4. 由 contract-v1 驱动 API 格式、认证控件、推理深度、输出预算和能力提示。缺后端能力显示真实不可用原因，不能靠 UI 填表声称供应商可用；测试fixtures只能在测试路径。处理 R-07/R-08/R-13 的表单与错误展示，保留原长答首败用于联调复验。
5. 按 frontend-design 先提炼当前学习问答的 4–6 个颜色 token、标题/表单字体层级和桌面/手机布局草图，再实现。蓝色 `#2563eb` 与现有 surface/ink/line 复用；主标题可用现有阅读字体，密集表单用现有无衬线。参考以细分隔线、留白、紧凑卡片为主，不增加无关仪表盘、渐变装饰或新动画库。模型专属 CSS 限定作用域，其他设置与业务页严格不变。
6. 桌面保持原公共壳，供应商网格自适应；详情里的模型网格至多两列，手机单列且弹窗可滚动，操作始终可达。参考图标/动画按实际源文件复用并记录许可。保持150ms卡片颜色/边框过渡、按下scale .995与箭头反馈；弹窗/折叠的其他参数先核来源再写矩阵。键盘Enter/Space、Escape、焦点圈定/返回、aria-expanded与减少动画同时覆盖。

可写：`apps/web/src/features/model-settings/**`、`features/settings/SettingsWorkspace.tsx` 的模型挂载/锚点、必要的模型作用域样式、`tests/e2e/model-settings*.spec.ts`、模型专属测试与经核许可的图标资源。公共壳、导航、聊天渲染及其他业务不在本任务修改范围；共享契约由外部队长指定单一实现者；必要依赖/锁文件由外部队长集中维护，不升级无关依赖。

资源：外部队长统一分配5174、8001、.next-test与隔离浏览器；证据_work/model-ui-v1/。fixtures和真实联调分开记录，禁止操作用户5173。

验收：新增连接→发现/手添模型→保存→普通及流式测试→设默认→聊天可选择→刷新仍正确；覆盖重名/重复、缺凭证、超时/失败、取消、删除关联、revision冲突与旧配置。1440×900、1920×1080、390×844逐状态截图并实际查看；焦点、键盘、减少动画和快速开关有断言。运行根typecheck/lint/test:unit/build及相关浏览器测试；真实联调属于INTEGRATE，不以fixtures替代。实现结果只交 `ready_for_review`。

### B-LLM-PROVIDERS v1：参考已有 LLM 供应商

**负责人：外部Agent团队，含共享契约及集成代码；本Codex仅审查交付。** 启动文本和队内角色提示词见 [团队协作提示词](MULTI_AGENT_COLLABORATION_PROPOSAL.md#可复制的外部团队提示词)。

固定参考同上。注册表 `deeptutor/services/provider_registry.py` 实查38条，其中36现行、2旧兼容；以下分组用于任务拆解，不把条目数量写成已实现数量：

| 分组 | 必须覆盖的 providerId |
| --- | --- |
| 自定义与专用API | `custom`、`azure_openai`、`anthropic` |
| 网关/聚合与区域方案 | `openrouter`、`orcarouter`、`edenai`、`aihubmix`、`siliconflow`、`novita`、`atlascloud`、`volcengine`、`volcengine_coding_plan`、`byteplus`、`byteplus_coding_plan`、`nvidia_nim` |
| 标准云供应商 | `openai`、`deepseek`、`gemini`、`zhipu`、`dashscope`、`moonshot`、`minimax`、`mistral`、`stepfun`、`xiaomi_mimo`、`groq`、`qianfan` |
| 本机服务 | `vllm`、`ollama`、`lm_studio`、`llama_cpp`、`lemonade`、`ovms` |
| 专用认证 | `openai_codex`、`github_copilot`、`codebuddy`（CodeBuddy/WorkBuddy） |
| 旧条目兼容 | `custom_anthropic` → custom + anthropic格式；`minimax_anthropic` → minimax + anthropic格式；不作为重复新增选项，旧ID/别名仍可解析 |

需求与实现方式：

1. 先逐条核对注册表、`services/llm/provider_factory.py`、`provider_core/*`、`reasoning_params.py`、`request_compat.py`、`services/config/provider_runtime.py` 和设置发现/认证路由。建立38行核对表，包含参考源位置、别名、默认URL/各格式URL、认证、后端适配器、发现方式、推理及特殊参数、实现/隔离/真实三种状态。不能从图标清单猜范围，也不能将Gemini强行改成参考未使用的原生协议（固定参考走兼容端点）。
2. 在现有 `apps/api/app/providers/llm` 维护单一供应商注册表和分派层，复用三个传输适配器；专用Azure、Codex、Copilot、CodeBuddy按参考真实实现扩展，不做38份重复HTTP代码。不复制DeepTutor进程全局环境注入/可变会话；请求明确携带连接快照并释放客户端，连接A的认证和参数不得污染B。
3. 实现别名/旧配置兼容、各API格式默认地址、用户自定义地址保留、模型名前缀规则、Azure deployment/api-version、受保护请求头、局部无Key服务及云服务缺凭证分支。元数据支持选格式不等于所有上游模型都支持该格式；未支持组合要明确拒绝。维持公网HTTPS和HTTP仅回环约束。
4. 完成发现与普通/流式测试的真实后端路径；无发现API的供应商按参考采用有来源的目录或手工输入并标记来源，不能返回假发现成功。能力证据继续只在实测后verified。SSE拆包、推理/正文分离、usage、终态、空回答、错误、超时、取消与连接关闭保持现有合同。
5. 推理控制按供应商/模型映射，处理thinking_type、enable_thinking、reasoning_split等参考差异，以及不支持stream_options、max_completion_tokens、固定温度/移除参数等约束。不可让前端传任意JSON。用DeepSeek历史失败复验默认预算和Pro只有推理问题，记录首正文时间；不得无界加预算或自动降级为模拟来通过。
6. 专用认证作为单独适配阶段：核对参考实际使用的OAuth/设备码/本机认证方式，补开始、轮询或回调、状态、刷新、取消、过期、断开与错误清理；API Key型与本机无Key型分别处理。不得读取其他工具的真实登录文件作为测试fixture；真实交互登录缺用户操作时记录阻塞并继续可独立的实现/隔离测试，不能删去这三个供应商范围。
7. 在统一secret store上补R-01的两文件补偿、R-08明确清除、R-12实际状态说明；测试用临时目录/内存。模型JSON、API响应、日志、trace/截图不得泄漏凭证。普通调用与流式验收分别报告；没可用凭证/本地服务的真实用例写not_run与原因，不能把全部供应商标为真实通过。

可写：`apps/api/app/providers/llm/**`、模型专属 `app/api/v1/model_*.py`、必要的 `chat.py`/`capabilities.py` 模型接入、`app/core/secrets.py`、`app/repositories/model_config_repository.py`、新增模型服务层、对应 `apps/api/tests/**`；外部队长先列实际文件归属。共享schemas、前端contracts/services、必要路由/lifespan/设置及依赖也属外部实施范围；外部队长分配唯一写入者，并集中更新权威MD、矩阵、锁文件及本地Git。

资源：外部后端团队独占 `127.0.0.1:8001`，数据/凭证全在临时目录或内存，证据 `_work/model-providers-v1/`；各子角色再分子目录，只有后端队长启停服务。不得使用8000/5173或修改正式`.env`、`.local-data`。前端Next/.next-test也由外部队长分配，保留next-env.d.ts的用户改动。联调由外部队长完成，交验时停止写入并释放测试服务。

建议内部顺序：P0只读取证/合同提案 → P1注册表+兼容/三协议 → P2专用认证 → P3发现/推理/凭证一致性 → V独立验证。可并行取证；实现并行必须有不重叠文件清单，工厂/注册表/secret store只有一位写入者。每个子任务用 `B-LLM-PROVIDERS-Pn v1` 标识；不得默认递归扩队。

验收：38条元数据与别名逐条核对；各适配器有成功/认证失败/不支持/流式拆包/断连测试；专用认证有状态机与过期取消隔离测试；旧三协议、默认模型和revision保留；跨连接并发不串Key/参数；故障注入证明.env/JSON失败恢复。运行 `npm.cmd run test:api`，SSE变更加 `npm.cmd run test:chat`。真实供应商仅用已授权且可用凭证发送固定验收问题，低调用量并记录预算；一项失败不能被更大预算的成功覆盖。

交付：按协作结果卡返回 `ready_for_review`、候选HEAD+补丁/文件散列、contract版本、修改文件、38行覆盖表、命令/退出码/证据、首败、not_run、剩余风险与资源释放状态。证据写专属_work；外部队长选择必要脱敏证据纳入Git、更新权威状态并作本地提交，不能以局部通过宣称全体验收。

### B-MODEL-INTEGRATE v1：联合验收与提交

外部队长固定两项稳定候选、完成集成并串行联调8001/5174；独立验收角色不边验边改。逐项检查模型配置→默认/会话选择→真实SSE→推理/公式→取消/重试/刷新，并回归受影响的设置及原聊天。UI、动画、隔离上游、真实供应商分别给pass/fail/not_run；缺凭证不阻碍记录实现结果，但不能升级真实验收。

外部队长组织适用根检查，更新本文和三矩阵；审查暂存范围、敏感数据与生成物后，显式暂存本批文件并运行 `git diff --cached --check`，作本地小提交，不推送/部署。用户当前未提交改动保持原样。团队提示词只是执行约定，不能代替宿主工具实际的文件权限、锁、消息与任务回传能力；平台不支持时用单一后端写入者加只读取证/验收。

## 7. 本次文档整理

- README 只保留项目状态、启动方式和权威入口，并如实说明主聊天运行时已只走真实服务、主聊天会话契约/文案/CSS 残留仍待修。
- PROJECT_GUIDE 固化学习问答的色彩、字体、全局壳、页面内容、手机、动画与错误态基准，删除已过期的批次措辞。
- 本文删除 H0/H1 的重复长流水，改为当前代码审查、当前验证、完整计划和唯一下一动作；历史实现仍可从 `93a2a06`、`21d9898` 及归档追溯。
- 页面矩阵把功能状态和学习问答视觉状态分开；AI 矩阵将“模拟模式已移除”校正为“主聊天运行时已移除、主聊天残留待修”，并保留其他模块批准的显式模拟；动画矩阵为历史候选补日期和范围。
- ROUTES 校正知识库“显式模拟已有、真实解析未接”；API 契约补充凭证跨文件一致性缺口；后端 README 不再重复端点状态。
- 486 行多智能体提案压缩为 115 行稳定任务/结果模板，删除旧 HEAD、旧工作树和演练断点；旧全文保留在 Git 提交 `6e3f642`。
- 早前修正教案模块的已归档 QA 链接和 infra 对现有 FastAPI 的过时描述；当时NEXT_SESSION_START建议的 `B-H0R-UI` 断点已由本次任务重排替换，当前只跟随第6节。
- 本批没有修改产品业务代码、依赖、锁文件、浏览器数据或凭证；用户的 `AGENTS.md`、`apps/web/next-env.d.ts`、`.zcode/` 保持未提交。
- 随后按用户要求完成 `B-ACCEPT-20260912`：补跑80项e2e、48张图的有界视觉巡检、DeepSeek实际请求与配置变体验证；更新本节及三矩阵，新增可随Git交接的脱敏机器证据和8张关键截图。所有测试在隔离数据中完成，正式配置未改。
- 本次任务重排批 `B-MODEL-PLAN v1`：读取frontend-design及固定DeepTutor模型管理/供应商源码，确认38个注册条目；将模型UI与供应商设为首要任务，补合同前置、文件/资源归属、实现步骤、验收及外部团队启动/角色提示词。同步PROJECT_GUIDE、接手入口和三矩阵，历史验收与首败保留。检查文档差异、相对文件链接和供应商清单覆盖；本批没有产品代码变更，未重新运行工程、浏览器或真实供应商测试，旧结果不算本批新验收。

## 8. 文档职责

| 文档 | 唯一职责 |
| --- | --- |
| README | 项目入口、启动方式和权威文档导航 |
| PROJECT_GUIDE | 唯一目标、学习问答视觉基准、架构、数据/服务边界和验收定义 |
| STATUS | 当前进度、代码审查、完整计划、最近验证和下一动作 |
| NEXT_SESSION_START | 可复制接手步骤，不复制进度或路线图 |
| PAGE / AI / MOTION 三矩阵 | 逐项功能、视觉、真实/模拟与动画证据 |
| ROUTES / API | 当前运行时路由和 HTTP 契约 |
| archive / reviews | 历史原文、首败和修复证据，不作当前指令 |

协作任务卡与结果卡见 [协作模板](MULTI_AGENT_COLLABORATION_PROPOSAL.md)。旧 TASKS/HANDOFF/长提示词只在归档或 Git 历史中追溯。
<!-- END snapshot-status-20260915 -->
