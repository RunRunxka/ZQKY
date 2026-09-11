# 项目目标与工程说明

更新：2026-09-10。取代旧 ARCHITECTURE、DECISIONS、BASELINE 的现行说明；历史原文见 [项目历史](archive/PROJECT_HISTORY.md)。当前进度、完整阶段计划与下一动作只维护在 [STATUS](STATUS.md)。

## 1. 唯一目标

目标仓库 `H:\备份xuexi\智启课源`；功能、业务信息结构与动画参考 `F:\DeepTutor`，固定 **v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202**，只读且不自动更新版本。历史核对不替代后续每批的源码确认。

用智启课源名称和品牌资产，完成参考**全部产品前端页面、AI 交互、原有动画**。全站首页、列表、详情、弹窗和公共控件以当前学习问答为视觉基准，保留蓝色主题；各模块保留完成业务所需的信息结构。保留既有教案编辑、草稿恢复、Word/PDF 导出、模型管理、真实 SSE 问答及本地数据。首页 `/` → `/chat`，教案独立入口 `/lesson-plans`。

**允许模拟的是其他模块新服务的执行，不是删减前端；主聊天除外，生产只能调用真实服务。** 配置、输入、加载、流式/阶段、工具、等待用户、产物、失败、取消、重试、恢复、保存、跨页联动，凡参考存在的相关状态都要完整。服务边界显式注入，真实失败不回退模拟。主聊天复杂能力待真实通道接入后启用，不能把测试替身重新放回生产。

只完成部分材料视图、block 呈现或省略暂停/恢复，均不是用户批准的永久缩减；是否已有修复看 STATUS 与源码，不在目标文档重复保存待办。解析、安装、联网、转录、鉴权未接入时，保留前端状态和服务契约，演示结果明确标注。

## 2. 批准差异与统一规则

2026-09-10 最新决定：**所有板块整体界面以当前学习问答为准**，覆盖旧“主页外观仅限聊天”的范围说明。跨页全局侧栏共用尺寸、图标、排版、折叠状态和动画；学习记录独立位于导航与聊天之间。手机导航使用带遮罩、关闭入口和焦点管理的抽屉。统一外观不能删减模块状态或改变原业务功能；本次先修侧栏并完成交接，其余全站内容对齐列入 STATUS 计划。

2026-09-09 已批准服务差异继续有效：主聊天删除模拟模式、模拟服务与伪模型，生产仅走真实 FastAPI；原模拟浏览器数据库不清除，其他模块演示功能保留。凭证允许通过后端 `.env` 持久化；推理展示/折叠以固定 `F:\DeepTutor` 的 `AssistantActivity` 为依据，AI 正文与推理支持公式。

视觉来源顺序：当前学习问答实现 → 其来源包 `C:\Users\96022\Documents\Codex\2026-09-09\wo\outputs\deeptutor-page` → 固定 DeepTutor 的模块专属功能/交互/动画。来源、SHA256 与许可见 [资源说明](licenses/deeptutor-chat/README.md)。聊天输入区采用 912px 内容上限，不恢复旧 S2 的欢迎 768→会话 960 扩宽；其他业务工作区按内容需要布局，不把聊天宽度硬套到编辑器或阅读器。

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

三矩阵分别记录页面、AI 交互、动画；每条含参考源码、目标组件、状态与入口、保存/恢复、错误/取消、实际检查和证据。53 个现有非调试条目（50 参考产品页、1 自有教案、2 额外别名）是清单计数，不能当百分比；改分母须说明参考扫描依据。

静态截图核布局，录像/采样核开始—过渡—结束和中断；覆盖 1440×900、1920×1080、390×844、主题与减少动画。构建、自动断言、人工视觉和真实供应商分别记录。导航 `ready` 只表示入口可达，不代表完整复刻已验收。

## 6. Git 与恢复

基线 `b8cf71f`，标签 `checkpoint/pre-reading-review-20260908`；分支 `codex/replica-review-20260908`。这是带已知缺陷的审查前快照。当前用户已授权本地版本控制，每批小提交，不自动推送/部署，不全局修改 Git 身份。

流程：status/diff → 确定本批 → 实现/验证 → 显式暂存 → diff --cached --check 与产物/凭证检查 → 提交 → 更新唯一 STATUS。WIP 可以保存但不得标已验收。不覆盖用户或其他人的未提交修改。

```powershell
git log --oneline --decorate -8
git diff checkpoint/pre-reading-review-20260908 -- docs
git show checkpoint/pre-reading-review-20260908:docs/replica/HANDOFF.md
# 在共享工作区只读查看，不切换其他实例正在使用的分支：
git show checkpoint/pre-reading-review-20260908:README.md
```

撤销明确提交优先 `git revert <提交>`，不用 `reset --hard`、`clean -fd` 或批量覆盖。备份包在 `_work/git-backups/`，可 `git bundle verify <文件>` 校验。**Git/bundle 不含浏览器 localStorage/IndexedDB、忽略的运行数据与凭证**；数据迁移前另做可控导出与兼容验证，测试只用隔离数据。

## 7. 文档规则

README 做入口，PROJECT_GUIDE 管目标/架构/决定，STATUS 管进度/完整计划/下一动作，NEXT_SESSION_START 仅提供接手步骤。API、ROUTES 管现行契约，三矩阵管条目证据，独立 review 保留首败与修复依据。MULTI_AGENT_COLLABORATION_PROPOSAL 是可复用协作模板，不是项目进度副本。不再维护多份 TASKS/HANDOFF/FINAL 提示词。

19 份旧文档已合并为 [项目历史](archive/PROJECT_HISTORY.md)、[交付历史](archive/DELIVERY_HISTORY.md)、[审查历史](archive/REVIEW_HISTORY.md)、[提示词历史](archive/PROMPT_HISTORY.md)。2026-09-10 将旧 STATUS、旧 NEXT_SESSION_START、GAP_AUDIT 原文继续合入后三份归档，撤销 GAP_AUDIT 的独立状态维护入口。修复记录仍追加原 review，当前任务只更新 STATUS。清单保留原路径、原始与规范化 SHA256；旧相对链接以原文件目录解释，完整文件可从来源 Git 读取。原始规划/参考图/Word 保留。
