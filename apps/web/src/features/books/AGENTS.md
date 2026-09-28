# books 模块约定（书籍）

先读根 `AGENTS.md`。入口 `/books`（详情 `/books/[bookId]`、阅读 `/books/[bookId]/pages/[pageId]`），
为隐藏直达项（桌面侧栏高亮「教材资料库」）。**生成为本地确定性模拟执行器**，界面显式标注【模拟】；
无真实 LLM/解析。

## 结构与职责

- `BooksRoute.tsx`：列表 + 详情路由（书卡、生成活动条、归档）。
- `PageReader.tsx`：分页阅读（14 类 block、笔记、练习、书签、进度、导出 Markdown）。
- `BookGenerationStrip.tsx` / `BookPausedBanner.tsx` / `BookBlockFailure.tsx`：生成可观察/暂停/重试 UI。
- 仓储：`services/books-store.ts`（七态状态机：draft→spine_ready→compiling→ready→archived，
  compiling 可 paused/error）；执行器：`services/book-generation.ts`。
- 写一致性：`services/collection-lock.ts`（生产走 Web Locks，jsdom 单测走注入互斥）+
  `CommitResult` 提交结果契约——非 `committed` 一律不返回值。
- 样式：`books.css` + `styles/book-pipeline.css`（选择器以 `.book-pipeline-*` 起头，只消费既有类）。

## 关键不变量

- **七态语义不可退**：`paused` 不自动恢复；归档只读；旧四态数据读取期派生、不写回。
- **提交一致性**：全部写入口走锁内事务（读快照→变更→写修订号→写数据→双重写后校验）；
  失败保留输入与草稿可重试；缺 Web Locks 不降级写。**不宣称强原子性**（写后读回能发现窗口内并发改写并如实报 conflict，
  但不保证发现所有绕过协议的写入）。
- **租约**：单书同时只有一个执行器；失权即停、释放后可从断点恢复。
- **已知间歇 R-14**：双标签并发写不同书的写锁竞争 e2e 偶发失败，属「测试假设与既定行为不一致」，
  按 `docs/CURRENT_STATUS.md` 台账管理，不在常规修改中笼统加等待或断言反转。

## 修改后必测

`typecheck`/`lint`/`test:unit`（books-store、book-generation 单测）；e2e 跑
`books-courses.spec.ts`、`books-pipeline.spec.ts`、`books-harden.spec.ts`、`books-commit-safety.spec.ts`。
