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
