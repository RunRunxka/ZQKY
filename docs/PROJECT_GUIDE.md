# 项目目标与工程说明

更新：2026-09-08。取代旧 ARCHITECTURE、DECISIONS、BASELINE 的现行说明；历史原文见 [项目历史](archive/PROJECT_HISTORY.md)。当前进度只维护在 [STATUS](STATUS.md)。

## 1. 唯一目标

目标仓库 `H:\备份xuexi\智启课源`；只读参考 `F:\DeepTutor`，固定 **v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202**。本轮已核对参考 HEAD 与干净工作区，后续不自动更新参考版本。

用智启课源名称和品牌资产，完成参考**全部产品前端页面、AI 交互、原有动画**。保留既有教案编辑、草稿恢复、Word/PDF 导出、模型管理、真实 SSE 问答及本地数据。当前首页 `/` → `/chat`，教案保留独立入口 `/lesson-plans`。

**允许模拟的是新服务的执行，不是删减前端。** 配置、输入、加载、流式/阶段、工具、等待用户、产物、失败、取消、重试、恢复、保存、跨页联动，凡参考存在的相关状态都要完整。无服务不构成“前端不适用”的理由；通过同一接口注入 mock/real，真实不可用时明确表达，不静默回退模拟。

“只做文本材料”“书籍只做部分 block”“同步模拟所以省略暂停/恢复”“练习答案不保存”是**待补齐差距**，不是用户批准的永久缩减。解析、安装、联网、转录、鉴权未接入时，保留前端状态和服务契约，演示结果明确标注。

## 2. 批准差异与统一规则

2026-09-09 用户指定学习问答 `/chat`、`/chat/[sessionId]` 改为复刻本地 `C:\Users\96022\Documents\Codex\2026-09-09\wo\outputs\deeptutor-page` 主页：保留智启课源蓝色、名称与现有功能，其余布局、对应图标与动画以该包为依据。该覆盖仅用于学习问答，不改变其他模块的固定参考目标。来源、SHA256 与许可见 [本批资源说明](licenses/deeptutor-chat/README.md)。因此主输入区采用该包的 912px 固定内容宽度，不再使用旧 S2 的欢迎 768→会话 960 宽度变化；业务和数据契约不变。

| 项目 | 要求 |
| --- | --- |
| 品牌 | 智启课源；参考交互不等于沿用参考品牌 |
| MCP/Skills | 唯一管理实现 `/settings#mcp`、`/settings#skills` |
| 兼容地址 | `/mcp`、`/skills`、`/space/mcp`、`/space/skills` 只重定向设置 |
| 聊天扩展 | 保留选择及管理跳转，订阅同一 extension-catalog |
| 真实问答 | 保留 FastAPI、SSE、模型目录，不改为参考后端协议 |
| 运行隔离 | 模拟显式选择，真实失败不转模拟；轮次快照固定，历史不重放 |
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
| 聊天 | chat-repository，IndexedDB `zhiqikeyuan-chat` / `zhiqikeyuan-chat-mock` | 模式隔离、revision、会话草稿、轮次快照、串行 flush、终态守卫 |
| MCP/Skills | extension-catalog | 设置修改更新聊天候选，历史快照不变 |
| 人设/知识 | persona-catalog / knowledge-catalog | 业务页与聊天共享 id 和目录，失效引用提示 |
| 题库/笔记 | space-store / notebook-store | 聊天保存、列表、编辑、作答记录与导出同源 |
| 书籍/课程 | books-store / courses-store | 章节、进度和课程资源引用关联；删除资源显示不可用 |
| 阅读 | reading-store 五组 localStorage 键 | 材料/集合/批注/书签/会话；发到笔记本真实本地写入；当前缺陷见 review |
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
# 工作区干净时，新建恢复分支查看原基线，保留当前分支：
git switch -c codex/recovery-reading checkpoint/pre-reading-review-20260908
git switch codex/replica-review-20260908
```

撤销明确提交优先 `git revert <提交>`，不用 `reset --hard`、`clean -fd` 或批量覆盖。备份包在 `_work/git-backups/`，可 `git bundle verify <文件>` 校验。**Git/bundle 不含浏览器 localStorage/IndexedDB、忽略的运行数据与凭证**；数据迁移前另做可控导出与兼容验证，测试只用隔离数据。

## 7. 文档规则

README 做入口，PROJECT_GUIDE 管目标/架构/决定，STATUS 管进度/下一动作，NEXT_SESSION_START 管续做合同。保留 API、ROUTES、三矩阵和独立证据 review；不再维护多份 TASKS/HANDOFF/FINAL 提示词。

19 份旧文档合并为 [项目历史](archive/PROJECT_HISTORY.md)、[交付历史](archive/DELIVERY_HISTORY.md)、[审查历史](archive/REVIEW_HISTORY.md)、[提示词历史](archive/PROMPT_HISTORY.md)。[清单](archive/MANIFEST.json) 保留原路径、原始与规范化 SHA256；内容保留，换行按仓库规范转为 LF。旧相对链接以原文件位置解释，完整文件可从基线 Git 读取。原始规划/参考图/Word 保留。修复记录追加同批 review，不为每次重跑新造方案。
