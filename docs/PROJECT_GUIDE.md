# 项目目标与工程说明

更新：2026-09-20。取代旧 ARCHITECTURE、DECISIONS、BASELINE 的现行说明；历史原文见 [项目历史](archive/PROJECT_HISTORY.md)。当前进度、代码审查、完整阶段计划与下一动作只维护在 [STATUS](STATUS.md)。

## 1. 唯一目标

目标仓库 `H:\备份xuexi\智启课源`；功能、业务信息结构与动画参考 `F:\DeepTutor`，固定 **v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202**，只读且不自动更新版本。历史核对不替代后续每批的源码确认。

用智启课源名称和品牌资产，完成参考**全部产品前端页面、AI 交互、原有动画**。全站首页、列表、详情、弹窗和公共控件以当前学习问答为视觉基准，保留蓝色主题；各模块保留完成业务所需的信息结构。保留既有教案编辑、草稿恢复、Word/PDF 导出、模型管理、真实 SSE 问答及本地数据。首页 `/` → `/chat`，教案独立入口 `/lesson-plans`。

**允许模拟的是其他模块新服务的执行，不是删减前端；主聊天除外，生产只能调用真实服务。** 配置、输入、加载、流式/阶段、工具、等待用户、产物、失败、取消、重试、恢复、保存、跨页联动，凡参考存在的相关状态都要完整。服务边界显式注入，真实失败不回退模拟。主聊天复杂能力待真实通道接入后启用，不能把测试替身重新放回生产。

只完成部分材料视图、block 呈现或省略暂停/恢复，均不是用户批准的永久缩减；是否已有修复看 STATUS 与源码，不在目标文档重复保存待办。解析、安装、联网、转录、鉴权未接入时，保留前端状态和服务契约，演示结果明确标注。

## 2. 批准差异与统一规则

2026-09-10 起的稳定决定：**所有板块整体界面以当前学习问答为准**，覆盖旧“主页外观仅限聊天”的范围说明。`/chat` 是唯一默认主页；品牌入口、404 恢复入口和页面标题都应与此一致。跨页全局侧栏共用尺寸、图标、排版、折叠状态和动画；**学习记录自 2026-09-23（UX-PERF-CLOSEOUT v1）起并入全站左侧导航的可滚动区域**，不再是导航与聊天之间的独立中栏（手机随同一个全站导航抽屉，不另开弹窗）。手机导航使用带遮罩、关闭入口、当前菜单语义和焦点管理的抽屉。统一外观不能删减模块状态或改变原业务功能。

2026-09-09 已批准服务差异继续有效：主聊天删除模拟模式、模拟服务与伪模型，生产仅走真实 FastAPI；原模拟浏览器数据库不清除，其他模块演示功能保留。凭证允许通过后端 `.env` 持久化；推理展示/折叠以固定 `F:\DeepTutor` 的 `AssistantActivity` 为依据，AI 正文与推理支持公式。

视觉来源顺序：当前学习问答实现 → 其来源包 `C:\Users\96022\Documents\Codex\2026-09-09\wo\outputs\deeptutor-page` → 固定 DeepTutor 的模块专属功能/交互/动画。来源、SHA256 与许可见 [资源说明](licenses/deeptutor-chat/README.md)。聊天输入区采用 912px 内容上限，不恢复旧 S2 的欢迎 768→会话 960 扩宽；其他业务工作区按内容需要布局，不把聊天宽度硬套到编辑器或阅读器。

### 全站视觉基准

| 层面 | 固定要求 |
| --- | --- |
| 品牌与色彩 | 保留智启课源名称与资产；主色使用现有 `--blue: #2563eb`，背景、表面、正文与分隔线沿用 `--surface / --ink / --line`，状态色只表达真实状态 |
| 字体 | **单一 token 层（UX-PERF-CLOSEOUT v1，2026-09-23）**：`--font-ui` 界面正文黑体（其余模块页面、表单、卡片、表格；拉丁 Chat Geist、中文黑体回退）、`--font-display` 标题与展示衬线（Chat Lora + 明确中文衬线回退）、`--font-ui-serif` 界面衬线（= display 族；**左侧导航与学习问答的全部界面文字**）、`--font-document` 文档内容宋体族（教案纸面，与导出 Word 一致）、`--font-mono` 代码与等宽。局部例外：公式保留 KaTeX 自带字体族、图标为 SVG。**页面不得再散写具体字体名**；硬编码字体族已全部收敛到 token |
| 全局壳 | 桌面侧栏 220px 展开、56px 收起、200ms 切换；当前项有蓝色背景/文字、可访问的 `aria-current`；折叠偏好跨页保存。**侧栏内主导航下方为独立可滚动的「学习记录」区域（仅学习问答提供），底部导航始终可见** |
| 页面内容 | 首页、列表、详情、弹窗复用学习问答的留白、圆角、边框、阴影、图标线宽与文案语气；模块工作区按业务信息密度决定宽度 |
| 聊天专属 | 912px 对话内容上限只属于学习问答，不复制到阅读、教案或编辑器；**不再有 236px 学习记录中栏**（已并入全站导航） |
| 手机 | 使用模态抽屉、遮罩和显式关闭入口；打开时聚焦当前菜单或明确的回退控件，Tab 不逃逸，关闭后返回触发按钮 |
| 动画 | 延用参考已有的时长、缓动、进入、退出和中断；系统与本地减少动画设置均生效，不为统一外观臆造动画 |
| 错误与空态 | 正常页、错误页和 404 均保留统一导航和品牌语义；文案说明下一步，不显示不存在的操作 |

这套基准是 H1–H5 每一批的完成条件之一；H6 只集中补漏和做全站总验收。

| 项目 | 要求 |
| --- | --- |
| 品牌 | 智启课源；参考交互不等于沿用参考品牌 |
| MCP/Skills | 唯一管理实现 `/settings#mcp`、`/settings#skills` |
| 兼容地址 | `/mcp`、`/skills`、`/space/mcp`、`/space/skills` 只重定向设置 |
| 聊天扩展 | 目录和管理只维护一套；当前未接入执行项明确不可用，不能把保留组件写成可用能力 |
| 真实问答 | 保留 FastAPI、SSE、模型目录，不改为参考后端协议 |
| 运行隔离 | 主聊天仅真实执行；其他模块演示明确标识；真实失败不转模拟，轮次快照固定，历史不重放 |
| 教案 | 原功能与数据兼容，冻结旧版和 Word 原件不改 |
| 动画 | 逐组件核对属性、时长、缓动、退出与中断；原版没有则不添加 |
| 减少动画 | 系统偏好与本地设置均生效，保留反馈和焦点；不加第二套动画库 |

## 3. 工程结构

### 模型管理与供应商决定（2026-09-12）

- 模型管理的信息结构和交互以固定 DeepTutor 的 `ConnectionsEditor`、`ServiceConfigEditor`、`ModelCards`、`ModelListPicker` 为准：连接可复用，供应商卡片打开详情，详情中配置连接及模型；打开编辑不等于切换当前模型。视觉仍使用智启课源学习问答的蓝色、字体和公共壳。仅调整模型相关设置，不借此重做其他设置与业务页。
- 供应商身份、认证方式、API 格式和模型参数分层。供应商清单以固定源码 `deeptutor/services/provider_registry.py` 的注册表为依据；图标存在、通用三协议可调用均不代表已实现该供应商。旧别名和配置必须兼容，不按模型名猜测并改写用户显式连接。
- 在既有 FastAPI Provider 工厂、模型目录和 SSE 事件上扩展，保留连接/profile ID、revision、默认模型与历史引用。旧数据迁移可回退；不照搬 DeepTutor 的配置文件结构或将 Key 镜像到非敏感模型 JSON。凭证只经服务端 secret store，前端只见状态；OAuth/本机认证需专门服务端生命周期，不能当普通 API Key 下拉选项实现。
- 本轮模型范围只含 LLM 连接、模型配置和其必要认证/发现/推理能力。Embedding、搜索、TTS/STT、图像/视频生成、任务模型分配及其他业务模块不因参考页面包含它们而自动纳入。供应商实际请求格式以固定参考核对后实现；实测发现上游变化时单独记录差异，不静默更换参考版本。

```text
apps/web/src/
  app/                   Next 薄路由、布局、错误/规划页
  components/            公共壳、导航、通用控件
  features/
    chat/                输入、消息、过程、追问、产物、轮次 store
    lesson-plan/         既有教案、草稿与导出
    model-settings/      真实连接与模型管理
    settings/            统一设置与扩展管理
    space/               学习空间、历史、题库、角色、CLI
    knowledge/ notebooks/ books/ courses/ reading/
  services/              API、共享目录、模块仓储
  contracts/             共用契约
apps/api/                现有 FastAPI 三协议业务后端
assets/templates/source/ 模板副本及校验信息
tests/e2e/               正式浏览器回归
tests/review/            独立审查复现，修复后迁入正式测试
scripts/                 启动、模板与检查工具
docs/                    当前规范、进度、矩阵、历史
infra/                   部署规划
项目规划/                 原始规划和参考原件，非执行入口
_work/ test-results/      本机日志、截图、trace、备份（Git 忽略）
```

延用 npm workspace、Next App Router、React、TypeScript、Tailwind、Lucide、Zustand，版本以根锁文件为准。业务进 features，路由保持薄层，服务明确注入；不在服务端共享用户可变状态，不新建第二套业务后端。

## 4. 数据与联动

### 实施授权与模型稳定决定

用户要求外部Agent队长完成当前任务的产品代码、集成、验收组织、权威文档及本地提交；Codex负责交付审查，用户另外要求的文档整理可由Codex执行。用户本轮明确任务优先，其余范围以STATUS中已授权且未完成的当前任务为准；已交付记录与后续路线不能推导为重复实施或所有模块无限授权。共享文件和运行资源仍需单一负责人，不等待Codex定稿或代写常规契约。

下面保留2026-09-13模型批D1–D16稳定决定，供维护与兼容使用，不是重新执行P0的任务。模型实现与验收候选、未验范围统一见 [STATUS](STATUS.md)。当时合同原始散列在 `_work/model-providers-v1/contract-v1.md`；即使本机产物缺失，也可从本表、版本源码及API核对，不将不可迁移的_work作为唯一交接依据。

| 项 | 模型稳定决定（原draft-2裁决） |
| --- | --- |
| D1 | providerId落库；旧连接缺字段时按原protocol映射custom，不猜供应商、不改URL、ID和默认引用。别名仅来自显式别名表，keywords是匹配词，二者分开。 |
| D2 | apiFormat连接级，profile覆盖不纳入本批；非法新请求组合报明确错误，不静默换协议。旧配置规范化与新请求校验分开。 |
| D3 | 支持请求开始前按供应商/模型/端点解析auto；OpenAI官方端点限制与Copilot专用规则分开。显式格式优先，记录本轮实际协议；流开始后不得切协议重放，认证/配额错误不被fallback掩盖。 |
| D4 | Azure modelId复用deployment，运行时归一到/openai/v1并按参考走Responses；存储URL原值不改。apiVersion独立字段，参考仅preview实际转发，其他值不得显示为已生效。 |
| D5 | 现有validate_base_url已允许路径，无需放宽。继续禁止query/fragment/内嵌凭证；版本走apiVersion字段，公网HTTPS、HTTP仅回环。 |
| D6 | reasoningEnabled三态与reasoningEffort独立；reasoningStyle只读派生、不接受写入、不落库。effort覆盖参考含xhigh/max的受控全集，再按供应商/模型限制子集；明确关闭与非关闭effort冲突应校验。 |
| D7 | 保留temperature/top_p，推理不放任意JSON；后端删除或固定参数时给出可解释状态，不暗示保存即上游已采用。 |
| D8 | schema、Python/TS合同和仓储迁移均由外部队长指定负责人直接落地。读取v1不自动覆盖文件，首次写v2保留可恢复原配置并测失败回滚；不能只靠版本分支宣称可回退。 |
| D9 | 接受model-providers与auth/status/start/cancel/logout路径方案；外部团队可调整模块拆分并修改main/lifespan挂载，无需本Codex加include。既有SSE事件与错误信封保留。 |
| D10 | 认证四态可用，增加有定义的操作ID、过期/取消语义和可用方式；迟到回调不能复活已取消授权。不仅实现静态状态，须按实际流程完成生命周期和隔离测试。 |
| D11 | Codex客户端常量存在不证明它属于DeepTutor或必需自有应用，实施者核对官方支持方式后实现；缺必要真实登录条件时精确记录。不得凭假设将三个专用供应商全部缩成API Key。 |
| D12 | 发现返回upstream/catalog/manual来源；catalog注明来源/版本，manual明确无发现能力。认证/网络失败不能吞成空列表或回退静态候选冒充成功。 |
| D13 | 接受提案新增认证/格式/操作错误类别；外部合同负责人同步HTTP状态、retryable、幂等语义和前端处理。 |
| D14 | model_views、schemas、前端contracts/services及必要路由接线都归外部团队，文件各自单一写入者，不再只交diff建议。 |
| D15 | 不向产品UI暴露原始backend作为选择或业务判断依据；下发apiFormats、认证方式、模型能力与实现/配置状态即可，backend保留服务端分派。 |
| D16 | 不自动读取第三方CLI/IDE登录文件。CodeBuddy按参考已有API Key通道实现；Copilot的GitHub令牌交换与普通模型API Key不同，可对智启课源自身受管令牌存储实现注入和交换并用测试凭证隔离验证。真实获取/导入需用户操作时给具体步骤，未具备路径标不可用，不能伪造已支持或删供应商范围。 |

共同约束：不新增isCustomProvider布尔来混合供应商类型和URL编辑状态；providerId=custom表达前者，显式baseUrl始终保留，默认地址替换由用户操作。目录支持多认证方式和可选无Key本机服务，不能用单一oauth/api_key枚举决定全部控件。以上决定供外部队长直接实施，剩余常规字段和文件组织由其自行完成；确实超出用户范围或需要用户登录时再提出具体问题。

| 数据 | 当前实现 | 保持的关系 |
| --- | --- | --- |
| 聊天 | chat-repository，当前仅 IndexedDB `zhiqikeyuan-chat`；旧 `zhiqikeyuan-chat-mock` 留存但不读写 | revision、会话草稿、轮次快照、串行 flush、终态守卫；不得清旧数据解决兼容问题 |
| MCP/Skills | extension-catalog | 设置修改更新聊天候选，历史快照不变 |
| 人设/知识 | persona-catalog / knowledge-catalog | 业务页与聊天共享 id 和目录，失效引用提示 |
| 题库/笔记 | space-store / notebook-store | 聊天保存、列表、编辑、作答记录与导出同源 |
| 书籍/课程 | books-store / courses-store | 章节、进度和课程资源引用关联；删除资源显示不可用 |
| 阅读 | reading-store 本地仓储 | 材料/集合/批注/书签/会话及会话草稿；发到笔记本真实本地写入；当前问题见 STATUS，历史首败见 review |
| 教案 | 模块内 repository/store | 原格式兼容，读取失败不覆盖，编辑/恢复/导出可回归 |
| 模型 | 既有 model-catalog / 后端 | 配置、普通调用、流式供应商验收分开，凭证不进入 Git |

演示数据按稳定 id 合并，不能重写用户集合。读取失败/结构损坏不能当空库后覆盖；写入失败保留编辑并可重试。多键操作考虑中途失败恢复。切材料/会话/工作区时撤销旧异步任务和过期上下文，不能串数据。数据库格式变更须迁移与旧数据回归，不能清库解决。

### 4.1 教材 RAG 接入设计（2026-09-22，规划，尚未实施）

用户计划接入教材 RAG。实际发现路径为 `F:\ZQKY_RAG`，区别于原消息 `F:\ZQKY\_RAG`；不修改或搬迁该仓库。阶段状态、修复门槛和下一动作只记 STATUS §6.1。以下为拟采用架构，现行 API 与 capability 不因此变为已实现。

1. **单一业务后端**：浏览器 → 现有 `apps/api` → 内部 RAG adapter → 可注入的 `locate_and_explain`/检索服务 → 本地模型运行时。复用现有错误信封、回环访问检查和生命周期，不新建 FastAPI 或 Next 业务后端。RAG 发布为固定版本、独立命名的 Python 包或一次受控源码引入，I0 决定其一；不永久 `sys.path` 指向可变的 `F:\ZQKY_RAG\src`，不把通用 `src` 命名空间散入宿主。
2. **保持本地执行策略**：RAG 默认本地检索融合 alpha=0.5、rerank off；embedding 与讲解用固定身份的本地模型，不因聊天默认模型是云端就将教材或题面转给云端。普通聊天维持原 provider 行为。模型/权重/索引身份、能力就绪与数据来源分别记录；不自动下载权重、不偷偷启用云端回退。embedding/rerank 保持独立接口，不伪装成 LLM chat adapter。
3. **运行隔离**：I0 先验证宿主锁定 Python/uv 环境。CPU/同步检索不得直接堵塞 async 路由；采用有界线程/任务执行，GPU 模型访问设置并发/队列上限，显式超时与协作取消。取消 HTTP 等待不等于取消底层推理，实际停止能力必须测量；取消后的结果永不落入新轮次。独立本地推理进程可复用，不增加第二套业务服务；不能依赖未记录的个人 system-site-packages。
4. **语料与索引**：教材根目录和受信索引目录由服务端配置，教材就地只读，不进 Git；权重、向量、缓存和原始评测题不入 Git。冻结包记录代码/模型/语料/chunks/索引/schema 指纹，加载失败明确不可用，不自动重建或静默换模型。仅接受部署方生成的受信索引，特别是 pickle 产物，禁止用户上传后直接反序列化。首版接入既有教材，不自动扩大成任意附件解析/通用知识库上传。
5. **证据合同**：保留 `LocateResult.status` 与 EvidenceSpan/Citation；绑定书册唯一标识、相对 file、章节、原文 sha256、字符/行区间、原文和教材外补充。字符区间是归一化 Python str 的 Unicode 码点 `[start,end)`，行号是1起闭区间，原文散列是文件原始字节；前端 UTF-16 下标不可直接套用，优先由后端返回核验后的片段及定位。score 是未校准排序值，不能显示为正确概率。引用 ID 只在单结果内唯一，宿主须连同 resultId/sessionId/turnId 绑定。
6. **引用读取边界**：前端通过受控 citation/result ID 请求来源片段，服务端在限定语料根内解析并重新检查散列/区间；拒绝路径穿越、绝对路径和链接逃逸，不开放任意读盘接口。教材文本与模型输出视作不可信数据，原文不能成为工具指令。来源变更需明确失效，不继续展示为已验证引用。
7. **追问是完整状态合同**：当前 AskUserCard 与 store 可复用，真实服务仍拒绝 submitReply。I0 必须确定 sessionId/turnId/interactionId/operationId、版本、幂等、TTL、状态查询、等待和终态事件；等待用户时可以关闭 SSE 并释放模型连接，不能把连接 EOF 自动当最终完成。续答走新请求并验证原交互身份，重复请求返回同操作状态；崩溃中断不冒充 exactly-once，也不自动重放耗时生成。
8. **恢复与隐私先决策**：优先沿用客户端 IndexedDB 保存题面/回答/卡片快照，服务端只保留最小交互身份、revision、状态、期限与结果引用；客户端快照须有服务端完整性校验和范围重验，不能信任任意回传上下文。I0 明确后端重启恢复或“已中断可重试”的合同。若实现必须持久化原始题面/回答/教材原文，先明确数据保存、清理和授权决定，不默认突破现有“对话内容不在后端落盘或记录日志”规则；不引入数据库作为隐藏前置。
9. **界面落点**：/chat 显式教材定位/追问入口，普通聊天不强制检索；原文与定位作为结构化引用/来源面板，追问卡承载知识点确认和纠偏，可展示摘要，不把全部证据只拼进 prompt 文本。真实本地、模拟、缓存状态分别呈现；AskUserCard 的“本地模拟”改为来源驱动，历史模拟卡标记必须保留。仅端到端真实闭环验收后启用相关 capability。
10. **质量与上线分开**：原文可核验、零云端、接口可用属于工程出口；段级定位与讲解质量另按冻结金标、分科指标和人工审核验收。真实本地可运行不等于教学正确，历史节级 Hit@5 不等于答案准确率。未过质量门槛只允许明确边界的技术预览。

### 4.2 接入准备核对清单（2026-09-22 只读核对 `F:\ZQKY_RAG`，事实与缺口）

**2026-09-23 更新（RAG-I0-PREP v1）**：上游实际 HEAD `a0f9ade`（父 `8ed22b8`，分支 `master`），工作区 7→13 项漂移（含 P8B 12 题裁定材料未提交；核对期间另一写入者新增 `src/evaluation/*_v2.py` 等），**未确认停止写入**；候选冻结 `P8-FREEZE-20260922-190500` 的包/manifest/receipt 完好（144 成员、receipt sha256 逐一匹配），`freeze_snapshot.py --verify` 退出码 1 且失败仅为“当前树 vs 快照”漂移 18 项、**不比对 HEAD/porcelain**；冻结配置表 20/20 与 `configs/**` 一致；性能：热态检索 p95 210/369 ms 达标、**端到端 P95 22.7 s 未达标**；质量三类结论仍 `not_run`（评审者 0）。宿主侧 I0 已完成：内部 adapter 契约（`apps/api/app/contracts/rag_adapter.py`：输入输出/引用坐标/状态与错误 + 双向 UTF-16↔码点转换）、**35 例**合成数据契约测试、`get_rag_adapter()` 恒定不可用且无路由；**执行边界（有界队列/超时/取消等待≠停止推理/迟到结果/模型不可用）仅为设计描述、全部未实测**。以下表格为 2026-09-22 的现场记录（保留为历史）：

以下为**只读核对**得到的事实（未修改 RAG 仓库、未运行其测试/评测、未加载模型、未启动服务），供 I0 决策使用；事实若与 RAG 侧文档不符，以现场为准并去更新本表。

| 项目 | 现场事实 | 缺口 / 待办 |
| --- | --- | --- |
| 可恢复版本 | **未发现可恢复版本交付物**：无 tag、无 remote、无 bundle/zip/pack；`git tag -l` 空、`count-objects -v` 显示 `in-pack: 0`。唯一提交基线 `3b132df` 只覆盖到 P4-LOCAL；`git status --porcelain -uall` 为 74 条（18 modified + 56 untracked），暂存区为空——`src/service.py`、`src/config.py`、`src/llm/`、`src/retrieval/{evidence,rerank,execution_policy}.py`、`src/locate_cli.py` 等**尚未跟踪** | 宿主 R0 的进入条件要求"可恢复提交或受控版本包"：需由 RAG 侧先产出（本批不代做、不提交其工作区） |
| 依赖指纹 | 直接依赖 pinned（`numpy==2.5.3`/`httpx==0.28.1`/`jieba`/`rank_bm25`/`PyYAML`/`pytest`；本地重排另有 `transformers/tokenizers/…`）；**无 `--require-hashes`**，主环境无全量 freeze；本地重排 venv 依赖基础解释器的 `--system-site-packages` 提供 torch | 与宿主锁定环境的重装与导入验证属 I0；不接受未记录的个人 site-packages |
| 模型/索引指纹 | 有：reranker 权重逐文件 sha256 + 固定 revision（`P5-LOCAL-RUNTIME/weights_manifest.json`）、Ollama `bge-m3` blob digest、索引 `chunks_fingerprint`；但索引建于 2026-09-19 时**未记录权重 digest**（该次构建身份为历史未知，等价性靠重嵌位级一致支撑）。这些指纹文件位于被 gitignore 的 `data/derived/`，**不在任何提交里** | 冻结包需携带指纹清单；索引/权重/缓存不入 Git，加载失败必须明确不可用 |
| 服务输入输出 | 入口是**同步纯函数**：`locate_and_explain(question, *, deps=ServiceDeps(...), subject/book/file, top_k, pool, alpha, rerank='off') -> LocateResult`；无 HTTP 框架/端口/凭证依赖，全部 I/O 经 `ServiceDeps` 注入；`SERVICE_CONTRACT_VERSION = "p8a-v1(evidence:v1,schema:p7-v2)"`；`rerank != "off"` 直接 `ValueError` | 宿主侧仍需在 `apps/api` 内做"同步检索不阻塞 async 路由"的有界执行与取消适配（I0/I1） |
| 引用坐标 | `EvidenceSpan{citation_id,file,book,path,source_sha256,char_span,line_span,text,chunk_ids,method,selection_score,score_kind,expansions}`；`char_span` 是**归一化 str 的 Unicode 码点** `[start,end)`（非字节偏移、非前端 UTF-16 下标），`source_sha256` 是**原始文件字节**散列，`line_span` 1 起闭区间；`citation_id` 只在单结果内唯一 | 前端展示/定位需由后端返回核验后片段；宿主须绑定 resultId/sessionId/turnId |
| 错误状态 | `LocateResult.status ∈ {ok, partial, uncertain, generation_failed, model_unavailable, invalid_citation}`（`contracts.py` 冻结 6 值）；服务层映射含证据为空→uncertain、预算不足→partial、模型/查询向量化不可用→model_unavailable、有解释但引用全失败→invalid_citation，另有 `failure_stage ∈ {context_budget, embed_query, retrieval, evidence}` | 宿主 capability/错误信封映射与前端呈现需在 I0/I1 落地；当前 `capabilities.py` 的 `rag` 仍为 planned |
| 资源与取消边界 | 配置了超时（embedding 120/60s、rerank worker 600s、云端 rerank 60s+重试、生成 300s）与生成预算（`num_ctx/num_predict/safety_margin`、发送前拒绝并 `refused=true`）；生成器支持 `cancel_token`（请求前/返回后/身份核验后各检一次），rerank worker 单请求在飞、OOM 降级且**绝不回落云端**；台账含取消后计次规则 | **未发现并发/队列上限实现**（无 Semaphore/max_workers/队列深度限制），也无"实际停止能力"测量证据；宿主 §4.1 第 3 条要求的队列上限与停止能力测量需在 I0/I1 补齐并测量 |
| 质量口径 | RAG 侧 STATUS 记录 **P8A 十项（4 P1 + 6 P2）已修复并独立复验为 fixed（14/14）**；段级质量与讲解支持性**人工评审 not_run**（88 题全 pending、金标 0、`human_reviewer: null`），性能属 P8C 未评估 | 质量门槛未过只能进受限技术预览；宿主不得把"节级 Hit@5"当解释正确率 |

### 4.3 课程学习会话与课程上下文（H1-COURSE-SESSIONS v1，2026-09-22 稳定决定）

参考 `F:\DeepTutor` @ `42fab3cf` 的对应形态是"会话 preferences 里的 `course_id` + 每轮现读课程渲染 system 提示块 + course_study 状态摘要"。本宿主无服务端会话库，契约按下列稳定决定落地（与参考的差异随行说明）：

1. **归属字段**：`Conversation.courseId`（可选，稳定课程 id）。缺失或空串 = **未归属**；旧会话保持未归属，**不按标题、最近访问或 URL 猜测**，也不因出现在某课程页而被改写。`ConversationMeta.courseId` 贯通列表元数据，课程页只按 `meta.courseId === course.id` 过滤（与参考"拉全量会话后客户端过滤"一致）。`schemaVersion` 不变（读取期容错、不迁移、不回填）。
2. **会话库唯一**：课程会话复用既有 IndexedDB `zhiqikeyuan-chat` 与 `ChatRepository`，课程页与聊天页共用 `buildNewConversation` 形状；**不建第二套课程会话库、不做模拟问答**。创建走"保存成功后才跳转"，同一 tick 连点由同步 ref 去重。
3. **课程上下文的进入方式（有意差异）**：发送时把课程名、约定（`instructions`，截 1200 字符）、大纲摘要与**仅登记形态**的资源清单冻结为 `TurnCourseSnapshot`，渲染成**一条 `system` 消息**插在请求 `messages` 最前，经既有 `POST /api/v1/chat/stream` 到达供应商适配器（`ChatMessageIn.role` 已支持 system，不新增请求字段、不改后端协议）。快照随助手消息持久化：**重试沿用原快照**，课程修改只影响**新轮**——参考为"每轮现读"，本宿主按用户要求采用轮次冻结以避免"重试读到新配置"。
4. **课程删除/归档不修改会话**（有意差异）：不级联删除、不清空 `courseId`、不自动换绑；展示层如实标注"所属课程已删除或不可用"并**不回落其他课程**（参考在删除时把命中会话的 `course_id` 清空）。归档课程会话区只读（新建禁用），既有会话仍可打开。
5. **能力边界如实**：课程资源只是登记引用（R-11 三态 available/missing/unknown；目录读取失败不得当成"目标已删除"），**登记不等于已解析、已检索或已随请求发送**；RAG 未接入；大纲 `covered` 为学员手判，**不推断掌握度**（参考同样明令 covered 由学习者决定）。
6. **不变量**：主聊天仅真实服务（无 `?mode=mock` 捷径）；R-10 来源回链、深链失效不回落最近会话、turnId/sessionId 事件守卫、归档会话不入侧栏等既有语义不受本批影响。

### 4.4 学习问答请求的统一预算（CHAT-CONTEXT-BUDGET v1，2026-09-23 稳定决定）

一次真实请求到底发送什么，由 `features/chat/model/request-budget.ts` 的 `buildChatRequest()` **唯一构建**；`features/chat/model/store.ts` 只透传，不再二次裁剪。稳定口径：

1. **预算口径**：`inputBudgetChars = min(contextBudgetChars(contextTokens, maxOutputTokens), maxTotalChars)`，其中 `contextBudgetChars = max(2000, contextTokens*2 - maxOutputTokens*3)`（1 token ≈ 2 字符的**保守字符估算**）。后端硬限制的单一事实来源是同模块的 `BACKEND_REQUEST_LIMITS`，对应 `apps/api/app/schemas/chat.py` 的 `MAX_MESSAGES=200` / `MAX_MESSAGE_CHARS=32000` / `MAX_TOTAL_CHARS=120000`。**不得把字符估算表述为精确 token 计数，也不承诺不超模型自身上下文上限——只承诺不超本轮输入预算与后端硬限制。**
2. **裁剪阶梯（固定顺序）**：① 课程块动态字段限幅 → ② 整条丢弃最旧的旧历史 → ③ 整体丢弃课程块（`courseDropped=true`，本轮**不携带**课程上下文，界面如实提示）。**绝不拼接半条消息、绝不静默截断历史正文**；课程块被丢弃时不得发送残缺上下文冒充完整。
3. **当前问题不可裁剪**：`question` 逐字发送；若超过 `min(inputBudget, maxMessageChars)` 则**发送前**返回 `ok:false`，store 只设置可读提示（`budgetNotice`），**不清草稿、不入库用户消息、不创建助手占位、不置 `sending`**，用户改短后可重发。失败路径不得留下 `sending=true`、空助手占位、不可重试状态或未处理 Promise。
4. **课程块字段上限**：`name ≤ 80`、`nextTitle ≤ 120`、`conventions ≤ 1200`、资源 ≤ 12 条且单条标签 ≤ 80、整体 ≤ `min(2400, maxMessageChars-1)`；「内容未解析、未检索、未随本请求发送」免责句是**固定前缀，不被砍尾**。限幅只作用于发送内容，**不回写课程原始数据（`StudyCourse`）与历史消息正文**。
5. **轮次冻结不变**：新轮用新快照、旧轮重试用**冻结在助手消息上的原快照**（`ChatMessage.courseContext`）；历史遗留的超长快照同样经同一构建器安全渲染（限幅/整体丢弃），**不要求清库**。
6. **账目可核**：`ChatMessage.requestBudget`（`RequestBudgetRecord`）随助手消息持久化，记录 `totalChars/inputBudgetChars/maxMessageChars/maxTotalChars/historyDroppedMessages/courseTrimmedFields/courseDropped`，只反映**发送时**事实；历史原文不变。
7. **不改动**：模型输出预算默认值、推理开关、R-13 处理范围、供应商选择；不引入 RAG 内容或模拟聊天。

---

### 4.5 内部 RAG adapter 契约（RAG-I0-PREP v1，2026-09-23 宿主侧稳定决定）

宿主侧契约落在 `apps/api/app/contracts/rag_adapter.py`（**仅契约与纯函数**），稳定口径：

1. **能力可用性**：`get_rag_adapter()` **恒定抛 `RagAdapterUnavailable`**；不注册路由、不在任何现有端点调用，capability 状态保持 `planned`。**禁止给任何"返回演示成功"的生产入口**；未接入期间宿主不得声称已检索教材。
2. **输入输出**：`RagQuery{question, courseScope, maxEvidence}` → `RagAnswer{status, answer, evidence, citations, warnings}`；契约 `extra="forbid"` + `frozen`，指纹只收 64 位小写 hexdigest。
3. **状态**：`ok | no_evidence | stale_source | out_of_range | unavailable`；**非 `ok` 一律 `answer=None`、`evidence=[]`、`citations=[]` 且 `warnings` 非空**。`unavailable` 不得降级成 `no_evidence` 冒充"没有内容"。
4. **引用坐标**：字符区间半开 `[charStart, charEnd)`、行号 1 基闭区间 `[lineStart, lineEnd]`；RAG 侧与宿主后端是 Python **码点**下标，前端是 **UTF-16 码元**下标，**不得直接混用**，换算必须走 `codepoint_to_utf16_offset` / `utf16_offset_to_codepoint`；`fileFingerprint` 是**原始文件字节**的 SHA-256，与字符下标是两套语义。
5. **越界不裁剪**：区间倒置、引用超出证据区间、指纹格式非法、引用悬空、状态夹带载荷一律抛错；`validate_answer_payload()` 只校验、不归一化、不做 I/O。
6. **执行边界（设计约束，均未实测）**：有界队列（不得无界排队）、超时分层（总超时 vs 子超时）、**取消只保证"取消等待"，不声明能中断底层推理**、迟到结果按 `requestId/turnId` 丢弃、模型不可用时如实报错。未实测的能力**不得写成已支持**。

---

### 4.6 长推理流呈现、模式菜单、学习记录归属与字体 token（UX-PERF-CLOSEOUT v1，2026-09-23 稳定决定）

1. **推理流的呈现与提交**：活跃流期间（`status === 'streaming'`）与推理折叠未展开时，推理正文以
   **轻量纯文本**呈现（`pre-wrap`，字号/行高/颜色与展开后一致）；仅在**已结束且用户正在看**时做一次
   完整 Markdown/KaTeX 渲染。文本/推理增量按「前缘立即 + 尾部合并」节流，**可见更新时延上限 80 ms**；
   缓冲按原顺序折叠进消息，任何非文本事件与终止/停止/断流/切会话/落盘前必须先提交缓冲区。
   **不得**为此丢增量、截断原文、关闭动画或把真实失败改成模拟；折叠与自动跟随语义不变。
2. **写盘语义**：持续流式期间 `flush()` 一轮只保存“进入时的脏快照”，其余脏数据留在集合中由
   `change()` 重排的 400 ms 定时器与终态 flush 处理；**无活动轮次时仍循环到清空**，
   「显式 flush 落全部」的契约在刷新/离开/切会话/停止/错误路径上不变。
3. **模式菜单为单层**：「更多能力」二级飞出层及其三项专属能力（deep_solve / deep_research /
   immersive_watching）已整体移除（不可达产品代码）。菜单固定为
   `对话 / 追问澄清 / 智能出题 / 可视化 / RAG 模式`，**不再开二级菜单或选择弹窗**。
4. **RAG 模式的可用性行为（总控裁定）**：入口与其余模式**同一行样式与同一选中语义**，
   **不可选（disabled）**，原因以**行内徽标「未接入 · 规划中」直接可见**（不只在 `title` 里），
   与后端 `/capabilities` 的 `feature="rag", status=planned` 一致；`ChatWorkspace.submit()`
   另保留专门阻断文案作纵深防御。**任何情况下都不得把该模式发到普通聊天冒充检索成功、
   不得返回模拟检索结果**；真实 RAG 未接入前，`get_rag_adapter()` 恒定不可用。
5. **学习记录归属**：`/chat` 的学习记录并入全站左侧导航内的可滚动区域（`WorkspaceShell.sidebarContent`），
   桌面侧栏收起为 56px 图标栏时该区域隐藏；手机随同一个功能导航抽屉呈现（复用其遮罩、关闭入口、
   焦点圈定与 Escape 语义），**不另建第二套弹窗**。独立中栏的折叠/打开按钮与状态已删除，
   只保留全站导航本身的折叠按钮；新建/搜索/切换/重命名/删除/归档/深链/课程会话往返/本地保存行为不变。
6. **书籍归属**：`/books`、`/books/[...]`、`/courses` 的路由、数据与业务不变；左侧导航不再把「书籍」
   作为与「教材资料库」并列的顶级项——书籍与课程为隐藏直达项，桌面在这些路由上**唯一高亮「教材资料库」**
   （父菜单解析支持传递上溯），手机抽屉仍列出「书籍」「课程」，教材资料库页提供清晰可达的书籍/课程入口。
7. **字体与排版**：见 §2 全站视觉基准的字体行（token 层为唯一来源）。
8. **教案工作台**：不再显示「备课空间 > 教案工作台」面包屑，改为与协同写作/沉浸阅读同级的直接页面标题；
   面板顺序为 **编辑区 → 可折叠「教案配置」→ 教案预览**，折叠按钮只保留编辑区顶部一个
   （`aria-expanded`/`aria-controls` 与状态一致），折叠只切 class **不卸载**（表单值/预览/撤销历史/焦点不丢）。

---

## 5. 验收定义

页面矩阵分开记录功能状态与学习问答视觉状态；AI 矩阵区分前端组件、显式模拟、真实通道和供应商验收；动画矩阵记录参数、中断、退出与减少动画。每条按适用范围补参考源码、目标组件、入口、保存/恢复、错误/取消、实际检查和证据。53 个现有非调试页面条目（50 参考产品页、1 自有教案、2 额外别名）是清单计数，不能当百分比；改分母须说明参考扫描依据。

静态截图核布局，录像/采样核开始—过渡—结束和中断；覆盖 1440×900、1920×1080、390×844、主题与减少动画。构建、自动断言、人工视觉和真实供应商分别记录。导航 `ready` 只表示入口可达，不代表完整复刻已验收。

## 6. Git 与恢复

基线 `b8cf71f`，标签 `checkpoint/pre-reading-review-20260908`；分支 `codex/replica-review-20260908`。这是带已知缺陷的审查前快照。当前用户已授权本地版本控制，每批小提交，不自动推送/部署，不全局修改 Git 身份。历史基线仅供只读追溯，不能当新任务起点或自动恢复目标。

**分支与远程改名（2026-09-21，用户决定）**：工作分支由 `codex/replica-review-20260908` 改名为 **`main`**——仅 `git branch -m` 加一次普通推送，**提交 SHA 未变、历史未改写**（改名时点 `17e3a09`）；当时远程默认分支一度切为 `main`，旧名分支已删除，`feat/glass-theme` 不受影响。仓库地址改为 `https://github.com/RunRunxka/ZQKY.git`（GitHub 提示仓库已更名），本地 `origin` 的 fetch/push 已指向新地址。本段以上及 `docs/qa/**`、`docs/archive/**` 中其余旧分支名是**当时批次的历史记录**，按证据原则保持原样，不代表当前分支。

**分支分工（2026-09-21 用户裁定，以此为准）**：**默认（集成）分支 = `feat/glass-theme`**——它已完整包含 `main` 的历史（`git merge main` → `191c1ad`），并承载主题四提交与根目录 Word 原件恢复（`cb0bfd8`）；GitHub 默认分支按此设置，本地 `origin/HEAD` 已同步为 `origin/feat/glass-theme`。**`main` 是用户个人分支**，只承接本线小提交（分支改名记录 `b4604d7`、在 `main` 补回 Word 原件 `c7df565`；`main` 上 `npm run template:verify` 曾因该文件缺失而退出码 1，`c7df565` 后恢复为 `{"original": true, "source": true}`）。主题与整合工作以 `feat/glass-theme` 为准，不要把 `main` 当作另一条主线。

流程：status/diff → 确定本批 → 实现/验证 → 更新唯一STATUS及对应矩阵 → 显式暂存 → diff --cached --check 与产物/凭证检查 → 本地提交。最终SHA在结果卡报告，后续接手现场读取Git。WIP 可以保存但不得标已验收。不覆盖用户或其他人的未提交修改。

```powershell
git log --oneline --decorate -8
git diff checkpoint/pre-reading-review-20260908 -- docs
git show checkpoint/pre-reading-review-20260908:docs/replica/HANDOFF.md
# 在共享工作区只读查看，不切换其他实例正在使用的分支：
git show checkpoint/pre-reading-review-20260908:README.md
```

撤销明确提交优先 `git revert <提交>`，不用 `reset --hard`、`clean -fd` 或批量覆盖。备份包在 `_work/git-backups/`，可 `git bundle verify <文件>` 校验。**Git/bundle 不含浏览器 localStorage/IndexedDB、忽略的运行数据与凭证**；数据迁移前另做可控导出与兼容验证，测试只用隔离数据。

## 7. 文档规则

README 做入口，PROJECT_GUIDE 管目标/架构/决定，STATUS 管进度/代码审查/完整计划/下一动作，NEXT_SESSION_START 仅提供接手步骤。API、ROUTES 管现行契约，三矩阵管条目证据，独立 review 保留首败与修复依据。MULTI_AGENT_COLLABORATION_PROPOSAL 保留可复用任务卡、结果卡和团队启动/角色提示词，详细任务引用STATUS，不保存当前 HEAD、进度或断点。不再维护多份 TASKS/HANDOFF/FINAL 提示词。

19 份旧文档已合并为 [项目历史](archive/PROJECT_HISTORY.md)、[交付历史](archive/DELIVERY_HISTORY.md)、[审查历史](archive/REVIEW_HISTORY.md)、[提示词历史](archive/PROMPT_HISTORY.md)。2026-09-10 将旧 STATUS、旧 NEXT_SESSION_START、GAP_AUDIT 原文继续合入后三份归档，撤销 GAP_AUDIT 的独立状态维护入口。修复记录仍追加原 review，当前任务只更新 STATUS。清单保留原路径、原始与规范化 SHA256；旧相对链接以原文件目录解释，完整文件可从来源 Git 读取。原始规划/参考图/Word 保留。

2026-09-15再次整理：旧STATUS和模型专用启动文本原文追加到既有交付/提示词归档并登记散列；现行STATUS只维护目标下的模块现状、问题、批次索引、当前任务及后续路线。禁止以“唯一模型阻断”为由隐藏全站视觉和未实现业务。
