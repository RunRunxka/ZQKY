# H1-BOOKS-HARDEN v1 首败与修复台账

起点候选：`40491be`（`main`，开工工作区干净）。缺陷来源：[main 审查证据](../main-review-20260922/README.md)（`docs/STATUS.md` §3.1）。
每条先有"缺陷存在"的观察（隔离探针或源码定位），再有修复与**断言正确行为**的正式回归；探针原文件未改动，修复后运行输出见 [probe-reversal](probe-reversal/README.md)。

| ID | 缺陷（审查结论） | 首败/复现证据 | 修复 | 正式回归（断言正确行为） |
| --- | --- | --- | --- | --- |
| M22-01 | 读取异常被折叠成"空书"后 `drive` 直接 `return`：注册表、心跳、`pagehide` 监听与租约未释放；删除也不停止任务，恢复被旧句柄阻塞 | jsdom 探针 2 例（删除后仍 `running` 且心跳续租；读取被拒后仍 `running` 且租约 live）；`book-generation.ts` 旧 `freshBook` 的 `catch { return null }` + `if (!book …) return false` | 新增 `readBookForRun`（`ok/missing/denied` 三态）与**唯一收尾函数** `teardownRun`：任何非运行出口都释放合并写盘定时器、心跳、`pagehide`、注册表与**自有租约**，并取消本书在途修复；删除入口（`BooksRoute` 删除按钮 → `stopRun(id,'delete')`）先停任务再删记录；新增 `getRunExit` 记录收尾原因（读失败与删除区分开），界面如实提示 | `book-generation.test.ts`：删除收尾（含跨心跳周期不续租）、读取被拒收尾并可恢复续跑、`stopRun` 取消在途修复；e2e `books-harden.spec.ts`：生成中删除后租约立即释放且不再续租 |
| M22-02 | `regeneratePage`/`retryBlock` 为 fire-and-forget（返回 `undefined`），等待后**重新取当前 runId**，旧任务可借用新 runId 写入；无互斥、不可取消 | jsdom 探针 1 例（换入 `replacement-run` 后旧任务仍把第一块写成 ready；返回值为 `undefined`）；源码 `book-generation.ts:988-1043`（旧 `regenerateBlocks` 每步重读 `book.run?.runId`） | 修复入口改返回 `Promise<RepairResult>`（`completed/superseded/cancelled/skipped/failed` + `operationId/runId/writtenBlockIds/droppedWrites/error`）；**启动时冻结 runId**，每次写入前核对归属，身份变化即丢弃并计数；同页互斥：目标被在途操作覆盖 → 复用同一 Promise，否则取代；`cancelRepairs` 由删除/停止/收尾调用；界面按终态显示忙态与失败原因（不再静默无操作） | `book-generation.test.ts`：旧任务不得借用新 runId（`result.runId` 为冻结身份、`replacement-run` 下无块变 ready）、同目标复用同一 Promise、整页请求取代单块、`cancelRepairs` 终态 cancelled、写失败如实 failed；`PageReader.test.tsx`：failed/skipped 提示、忙态重复点击不重复调用、挂载时恢复在途忙态；e2e：同一 tick 连点「强制重新生成」互斥且页最终完整 |
| M22-03 | 租约"检查通过即写"，两标签页可同时通过；心跳盲写、失权不停止；多书共享集合的整表读改写可能覆盖其他书更新 | 源码确认（无真实双标签同时竞争复现）；本轮补：真实浏览器第二标签页接管租约 → 第一标签页停止且不再续租（e2e）；共享集合并发注入（单测） | 租约记录加 `nonce`：获取为**写入后读回校验**；每步驱动与每次心跳校验归属，失权即 `lease-lost` 收尾；清租约只在 owner+nonce 匹配时执行。共享集合写入改为**有界收敛**：写标记（sidecar 键 `zhiqikeyuan:<key>-write`）冲突检测 + 写前重放 + 写后读回校验（≤3 次），所有写入路径（含 `updateBook`/`setUserNote`/作答追加/创建/删除/演示载入）统一走该路径 | `book-generation.test.ts`：他标签页持活租约不启动、失权立即收尾且不动别人租约、可恢复；`books-store.harden.test.ts`：更新/创建/删除期间另一标签页对**其他书**的写入不被整表覆盖、连续写入单调收敛；e2e：双标签页失权与释放后恢复 |
| M22-04 | 首次读取目录失败只 `setError` 不 `setBooks`，被"正在读取书籍…"加载分支永久掩盖；成功后也不清旧错误 | 源码确认（`BooksRoute.tsx:469-475,549-557`） | 工作区渲染顺序改为：`books===null && error` → 错误面板（`role=alert` + 「重试读取」重复数据保护说明）；读取成功时清除旧 error；加载态只在既无数据也无错误时出现 | `BooksRoute.test.tsx`：首次读取失败显示错误与重试、加载文案不出现、失败期间不改写存储、重试成功后错误消失；e2e：真实浏览器注入读取失败（含 390 窄视口横向滚动差 ≤1px） |
| M22-05 | 最终完成写入异常被 `catch` 吞掉后仍设 `finished` 并移除句柄：内存谎报完成、持久层可能停在 compiling，恢复入口不明确 | 源码确认（旧 `stepOnce` 收尾块 `try { finishBookRun } catch {}` 后无条件 `state.status='finished'`）；本轮新增一次性注入开关复现 | 收尾路径区分三种结果：写入抛错 → `failTheRun(kind storage)` 落库失败原因（不设 finished），返回 `ready` → finished，返回非 ready → interrupted；新增模拟注入 `runScenario.storageFailureOnFinish`（一次性，失败过即不再注入）；界面在 `error` 状态显示原因 + 「重试生成」 | `book-generation.test.ts`：最终写失败后状态为 `error`（非 ready）、`run.failure.kind==='storage'`、句柄与租约释放、重试后真正完成、注入不污染存储；e2e：卡片显示「生成失败」而非「可阅读」，点「重试生成」后完成 |
| M22-06 | 编辑器方向键触发全局翻页：输入框/文本域/contenteditable/组合输入/修饰键均未排除 | 源码确认（`PageReader.tsx:153-164` 无条件 `router.push`） | 新增 `shouldIgnorePageKey`：排除 `input/textarea/select`、`isContentEditable`、`closest('[contenteditable]')`、`isComposing`、Ctrl/Meta/Alt/Shift 与已 `preventDefault` 事件 | `PageReader.test.tsx`：笔记输入框与 contenteditable 内方向键不翻页、组合输入与修饰键不翻页、普通阅读仍翻页；e2e：真实浏览器笔记输入框 + 真实可编辑元素 + 普通阅读两组键盘 |

## 本轮新增/改动的测试（与缺陷一一对应）

- `apps/web/src/services/book-generation.test.ts`：新增 `H1-BOOKS-HARDEN v1 缺陷回归（原探针断言反转）`（11 条，含 A1 挑刺后补的「修复期间归档不报 completed」）+ 租约拆分为 3 条（含失权）。
- `apps/web/src/services/books-store.harden.test.ts`（新建）：共享集合并发写入 4 条 + 笔记写入落地校验 1 条（A1 挑刺后补）。
- `apps/web/src/features/books/PageReader.test.tsx`：新增「全局翻页键的输入排除」2 条 + 「修复入口的真实异步结果」6 条。
- `apps/web/src/features/books/BooksRoute.test.tsx`（新建）：首次读取失败 2 条。
- `tests/e2e/books-harden.spec.ts`（新建）：6 条真实浏览器场景。

## 语义变化的已知边界（接手者必须知道）

1. **执行器收尾原因可查询**（`getRunExit`）：读失败/失权/删除/中断各有独立原因，界面提示随之变化；`finished` 不产生提示。
2. **`stopRun` 会取消在途页/块修复**：删除或停止后，先前点击的「重试块/强制重新生成」会以 `cancelled` 结束（这是有意的：不留幽灵任务）。
3. **修复互斥语义**：同页同目标（含"整页操作覆盖其中一块"）复用同一 Promise；需要更大范围时取代在途操作（旧操作终态 `superseded`）。
4. **新增 sidecar 键** `zhiqikeyuan:books-write`、`zhiqikeyuan:book-quiz-attempts-write` 与 sessionStorage 键 `zhiqikeyuan:books-tab`：仅用于跨标签页写冲突检测与本标签页身份，不改变书籍/作答数据格式，旧数据照常可读。
5. **`storageFailureOnFinish` 是模拟注入**（UI 开关「模拟最终完成写入失败」），只用于验证"最终落库失败不假报完成"，不代表真实存储故障或真实供应商行为。
6. **不宣称强原子性**：`localStorage` 无 CAS，租约与共享集合写入实现的是"写后读回校验 + 归属校验 + 失权即停 + 有界重放"，不是原子事务。
7. **修复写入被仓储静默拒绝（独立验收 A1 挑刺 2，已修）**：修复路径逐块写后读回校验——书籍在修复期间变为不可写（归档/暂停）时以 `failed` 结束、该块不计入 `writtenBlockIds`，不再可能出现"块没写成但报 completed"。
8. **失权文案（A1 挑刺 3，已修）**：归属校验失败可能是"别人接管"也可能是"租约读取被拒"，提示统一为「已失去或无法确认本书的生成所有权」，不再单方面断言是另一个标签页。
9. **收敛重放耗尽的残留边界（A1 挑刺 1，登记不改行为）**：`writeListConverged` 3 次重放后仍返回最后计算值（不抛错），以免在极端并发窗口向调用方抛未捕获异常；用户可见的两处"已保存/已完成"声明已改为写后读回校验（`setUserNote` 返回值、修复 `RepairResult` 的逐块读回），其余调用方（创建/更新/删除/已读登记）即便写入未落地也只表现为界面刷新后内容未变这种**可见失败**，不谎报成功。
10. **文档计数与口径（A1 挑刺 5/7，已按 A1 结论修正）**：窄视口写"横向滚动差 ≤1px"（e2e 断言 `<= 1`），新增界面计为三处（含模拟设置复选项）。
11. **r2 新发现 1（A1 复验，登记未改）**：修复路径"写入 → 读回"的极短窗口内若发生删除/读取被拒，终态归因会是 `failed` + "不接受生成"（准确应为 `cancelled` / 存储错误文案）。三种终态都不会报 `completed`，不构成假成功；建议下一批按 `after.kind` 分派。
12. **r2 新发现 2（A1 复验，登记未改）**：`finishBookRun` 自身写入未做读回，以内存返回值判定 `finished`/`interrupted`；若该次写入撞上第 9 条的重放耗尽窗口，退出原因可能记 `finished` 而存储仍为 `compiling`（界面仍诚实显示"已中断 + 继续生成"）。建议对最终完成路径同样加一次读回。
