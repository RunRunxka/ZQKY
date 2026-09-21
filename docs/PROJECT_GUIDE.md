# 项目目标与工程说明

更新：2026-09-20。取代旧 ARCHITECTURE、DECISIONS、BASELINE 的现行说明；历史原文见 [项目历史](archive/PROJECT_HISTORY.md)。当前进度、代码审查、完整阶段计划与下一动作只维护在 [STATUS](STATUS.md)。

## 1. 唯一目标

目标仓库 `H:\备份xuexi\智启课源`；功能、业务信息结构与动画参考 `F:\DeepTutor`，固定 **v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202**，只读且不自动更新版本。历史核对不替代后续每批的源码确认。

用智启课源名称和品牌资产，完成参考**全部产品前端页面、AI 交互、原有动画**。全站首页、列表、详情、弹窗和公共控件以当前学习问答为视觉基准，保留蓝色主题；各模块保留完成业务所需的信息结构。保留既有教案编辑、草稿恢复、Word/PDF 导出、模型管理、真实 SSE 问答及本地数据。首页 `/` → `/chat`，教案独立入口 `/lesson-plans`。

**允许模拟的是其他模块新服务的执行，不是删减前端；主聊天除外，生产只能调用真实服务。** 配置、输入、加载、流式/阶段、工具、等待用户、产物、失败、取消、重试、恢复、保存、跨页联动，凡参考存在的相关状态都要完整。服务边界显式注入，真实失败不回退模拟。主聊天复杂能力待真实通道接入后启用，不能把测试替身重新放回生产。

只完成部分材料视图、block 呈现或省略暂停/恢复，均不是用户批准的永久缩减；是否已有修复看 STATUS 与源码，不在目标文档重复保存待办。解析、安装、联网、转录、鉴权未接入时，保留前端状态和服务契约，演示结果明确标注。

## 2. 批准差异与统一规则

2026-09-10 起的稳定决定：**所有板块整体界面以当前学习问答为准**，覆盖旧“主页外观仅限聊天”的范围说明。`/chat` 是唯一默认主页；品牌入口、404 恢复入口和页面标题都应与此一致。跨页全局侧栏共用尺寸、图标、排版、折叠状态和动画；学习记录只在学习问答中作为导航与聊天之间的独立中栏。手机导航使用带遮罩、关闭入口、当前菜单语义和焦点管理的抽屉。统一外观不能删减模块状态或改变原业务功能。

2026-09-09 已批准服务差异继续有效：主聊天删除模拟模式、模拟服务与伪模型，生产仅走真实 FastAPI；原模拟浏览器数据库不清除，其他模块演示功能保留。凭证允许通过后端 `.env` 持久化；推理展示/折叠以固定 `F:\DeepTutor` 的 `AssistantActivity` 为依据，AI 正文与推理支持公式。

视觉来源顺序：当前学习问答实现 → 其来源包 `C:\Users\96022\Documents\Codex\2026-09-09\wo\outputs\deeptutor-page` → 固定 DeepTutor 的模块专属功能/交互/动画。来源、SHA256 与许可见 [资源说明](licenses/deeptutor-chat/README.md)。聊天输入区采用 912px 内容上限，不恢复旧 S2 的欢迎 768→会话 960 扩宽；其他业务工作区按内容需要布局，不把聊天宽度硬套到编辑器或阅读器。

### 全站视觉基准

| 层面 | 固定要求 |
| --- | --- |
| 品牌与色彩 | 保留智启课源名称与资产；主色使用现有 `--blue: #2563eb`，背景、表面、正文与分隔线沿用 `--surface / --ink / --line`，状态色只表达真实状态 |
| 字体 | 页面壳、公共导航、控件和普通正文参照学习问答的 Chat Geist 中文回退，聊天标题与助手回答参照 Chat Lora；复用公共字体变量，Chat Lora 不硬套到数据表、表单或教案密集编辑区。迁移与验收进度只看 STATUS 和页面矩阵 |
| 全局壳 | 桌面侧栏 220px 展开、56px 收起、200ms 切换；当前项有蓝色背景/文字、可访问的 `aria-current`；折叠偏好跨页保存 |
| 页面内容 | 首页、列表、详情、弹窗复用学习问答的留白、圆角、边框、阴影、图标线宽与文案语气；模块工作区按业务信息密度决定宽度 |
| 聊天专属 | 236px 学习记录中栏和 912px 对话内容上限只属于学习问答，不复制到阅读、教案或编辑器 |
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
