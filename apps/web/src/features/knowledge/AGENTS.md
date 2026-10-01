# knowledge 模块约定（历史本地登记）

先读根 `AGENTS.md`。本指南仅约束历史本地登记组件及 `/knowledge-bases/[kbName]` 的只读兼容详情。当前 `/knowledge-bases` 由 `features/textbook/TextbookWorkspace` 承担真实教材管理，解析、目录、索引与 RAG 走 FastAPI；不要将下方历史模拟规则扩大到真实教材模块。

## 结构与职责

- `KnowledgeBasesSection.tsx`：列表页（知识库卡片、登记入口、书籍/课程直达链接 `.kb-library-links`）。
- `KnowledgeBaseDetailSection.tsx`：详情页（文档/索引版本、进度、取消/重试/恢复）。
- `styles/knowledge.css`：专属样式，全部以 `.kb-page` 或 `.kb-detail` 起头，在共享 `space.css` 之后引入。
- 仓储：`services/knowledge-catalog.ts`（目录 + 订阅）；解析/索引模拟：`services/knowledge-ingest.ts`
  （模块内注册表 + cancel + 定时推进，持久化走 catalog 的 write + subscribe 事件，单一仓储）。

## 关键不变量

- **历史模拟边界**：遗留登记不宣称真实解析/索引成功，不把模拟登记接入教材检索；生产历史详情只读。保留数据兼容，真实功能走 textbook 模块。
- **历史登记仓储**：本地登记目录只经 `knowledge-catalog`；读取失败/结构损坏走 `local-collection` 抛错路径，
  不当作空库、不覆盖。
- **样式作用域**：不改写共享 `space-*` 类；新增规则必须收窄前缀。
- 书籍（`/books`）与课程（`/courses`）作为隐藏直达项并入本模块：桌面侧栏在此类路由上唯一高亮「教材资料库」，
  列表页提供可达的书籍/课程入口。

## 修改后必测

`typecheck`/`lint`/`test:unit`；列表/详情与目录容错另跑 `knowledge-bases.spec.ts`、
`course-resource-faults.spec.ts`（含 390 视口横向溢出断言）。
