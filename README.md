# 智启课源

以 **智启课源品牌**完成全部产品前端、AI 交互和参考动画。**全站视觉以当前学习问答为准**；各业务功能和信息结构参考只读 `F:\DeepTutor` **v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202**。正式前端在 `apps/web`，真实后端在 `apps/api`。

**整体尚未完成。** 主聊天/模型已有真实接口，教案为本地规则，阅读/知识库/写作等保留批准的显式模拟。主页与导航、来源链接、凭证/目录数据保护和阅读滚动已有局部修复验收；全站内容视觉、未实现业务、真实复杂能力与动画仍有缺口。**当前主线是以学习问答统一视觉，详细当前任务与状态只看 [STATUS](docs/STATUS.md)**，不重做历史模型批。

## 文档入口

| 文档 | 唯一职责 |
| --- | --- |
| [开发规则](AGENTS.md) | 工作范围、数据保护和工程规则 |
| [项目说明](docs/PROJECT_GUIDE.md) | 当前目标、学习问答视觉基准、技术结构、数据流、允许差异、Git 恢复方法 |
| [当前进度](docs/STATUS.md) | 唯一进度与交接入口，代码审查、完整计划、验证边界、下一动作 |
| [新会话启动文本](docs/replica/NEXT_SESSION_START.md) | 接手步骤，不复制进度与计划、不扩大当次授权 |
| [阅读代码审查](docs/reviews/READING_REVIEW_2026-09-08.md) | 历史首败、修复和局部验收证据 |
| [协作任务模板](docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md) | 可复用任务卡与结果卡，不保存当前进度 |
| [页面矩阵](docs/replica/PAGE_MATRIX.md) · [AI 交互矩阵](docs/replica/AI_INTERACTIONS.md) · [动画矩阵](docs/replica/MOTION_MATRIX.md) | 逐项验收，不另抄阶段统计 |
| [路由索引](docs/ROUTES.md) · [后端 API](docs/API.md) | 运行时入口和真实接口 |

旧 HANDOFF、TASKS、规划和 review 已合并到 `docs/archive/`；2026-09-10 又将旧进度流水、续做长提示、有界差距审计合入原归档，映射与 SHA256 见 [归档清单](docs/archive/MANIFEST.json)。旧提示词和旧“已完成”结论不是当前指令。原始 `项目规划/` 和 Word/模板原件保留。

## 本地启动

```powershell
Set-Location 'H:\备份xuexi\智启课源'
npm.cmd ci
npm.cmd run dev
```

前端 `http://127.0.0.1:5173`，首页 `/chat`，教案 `/lesson-plans`。保持原浏览器来源；`localhost`、`127.0.0.1` 与不同端口的数据互不相同。已有依赖时无需重复 `ci`；不要停止归属不明的服务。

真实问答需另开终端运行 `npm.cmd run setup:api`（首次）及 `npm.cmd run dev:api`，后端监听 `127.0.0.1:8000`。在设置中配置连接和模型；API Key 保存到后端 `apps/api/.env`，重启后恢复。也可按连接编辑窗口显示的 `ZQKY_API_KEY_<连接ID>` 手动填写该文件后重启 API。主聊天生产模拟服务、入口及不可达文案/样式已清理（R-03）；旧模拟数据库留存但不读写，历史兼容类型和测试替身不代表可用模拟模式。其他模块已批准的显式模拟能力不变。生产预览用 `npm.cmd run build` 后运行 `npm.cmd run start`。

## 检查与版本

根命令：`npm.cmd run typecheck`、`npm.cmd run lint`、`npm.cmd run test:unit`、`npm.cmd run build`、`npm.cmd run test:e2e`。typecheck/build 顺序执行；浏览器检查使用隔离上下文与 5174，每批输出目录唯一。Node 26 下运行 jsdom 单测时设置 `NODE_OPTIONS=--no-experimental-webstorage`；阅读首败和专项回归见 [审查报告](docs/reviews/READING_REVIEW_2026-09-08.md)。

当前分支与本批起点见 [STATUS](docs/STATUS.md)，最新提交以 `git log -5 --oneline` 为准。旧标签 `checkpoint/pre-reading-review-20260908` 是带已知缺陷的历史快照，不是发布版。按“检查 → 小批改动 → 验证 → 明确范围提交”推进，不自动推送。Git 不备份浏览器数据库或运行时凭证。
