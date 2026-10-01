# H1-BOOKS-HARDEN v1 任务卡与冻结契约

- 起点候选：`40491be`（分支 `main`，开工工作区干净）。现场 HEAD 以实际核对为准，本文件不把审查文档提交当作当前 HEAD。
- 范围：只修 `docs/STATUS.md` §3.1 的 M22-01～M22-06，保持 H1-BOOKS-PIPELINE v2 已交付的七态、14 类 block、笔记/练习/书签/导出、显式模拟标注与 `paused` 不自动恢复语义。
- 不包含：RAG 接入、课程新功能、模型预算调整、主题重做、`feat/glass-theme` 合并、任何推送或部署。
- 文件归属：引擎 `services/book-generation.ts`、`services/books-store.ts` 及其单测；UI `features/books/BooksRoute.tsx`、`features/books/PageReader.tsx` 及其测试；总控（本会话）独占文档、共享契约、e2e、构建与 Git。
- 根因证据：[main 审查证据](../main-review-20260922/README.md)（三个隔离探针复现 M22-01～03，M22-04～06 为源码确认）。

## 1. 执行器生命周期契约（M22-01 / M22-05）

每一个非运行出口都必须走**唯一收尾函数** `teardownRun(state, exit)`，不得在分支里各自 `return`：

| 出口 reason | 触发 | 落库动作 | 收尾要求 |
| --- | --- | --- | --- |
| `finished` | 全部页处理完且最终状态写入成功 | `finishBookRun` 成功（书籍 `ready`） | 全部释放 |
| `interrupted` | 走完全部页但仍有未完成页 | `finishBookRun` 保持 `compiling`（既定"已中断"语义） | 全部释放 |
| `failed` | 本地写入失败 / 最终完成写入失败 | `failBookRun(kind storage)` | 全部释放，给出显式恢复入口 |
| `paused` | 用户暂停 / 模拟供应商连续失败暂停 | `pauseBookRun` / `run-paused` 事件 | 全部释放 |
| `stopped` | 显式 `stop()`、书籍状态已非 `compiling`、运行身份变化 | 不改书籍状态（保留断点） | 全部释放 |
| `deleted` | 步骤中发现书籍已被删除 | 不写（书不存在） | 全部释放，不复活 |
| `read-denied` | 读取最新记录被存储拒绝 | 尝试一次 `failBookRun(kind storage)`；写也被拒则只留内存记录 | 全部释放 |
| `lease-lost` | 归属校验发现租约已不属于本标签页 | 不写（无权写） | 全部释放，停止续租 |

「全部释放」= 合并写盘定时器清零 + 心跳停止 + `pagehide` 监听移除 + 注册表删除 + **自有租约按归属清除** + 本书在途页/块修复取消。

- 读失败与删除必须区分：`readBookForRun(bookId)` 返回 `{kind:'ok'}` / `{kind:'missing'}` / `{kind:'denied'}`，不再把读取异常折叠成 `null`。
- 最终完成落库失败（M22-05）**不得**把内存状态设为 `finished`、不得只清句柄：走 `failed` 出口，落库 `kind storage` + 明确文案，界面显示「重试生成」。
- 新增模拟注入字段 `runScenario.storageFailureOnFinish?: boolean`（模拟执行器设置开关）：**一次性**注入（`run.failure.kind === 'storage'` 后不再注入），保证重试能真正完成。
- 收尾原因经 `getRunExit(bookId)` 暴露，供界面如实提示（读失败/失权不是静默停止）。

## 2. 页/块修复契约（M22-02）

```ts
export interface RepairResult {
  status: 'completed' | 'superseded' | 'cancelled' | 'skipped' | 'failed';
  operationId: string;
  bookId: string;
  pageId: string;
  runId: string | null;        // 启动时冻结的运行身份；写入必须与之一致
  blockIds: string[];          // 本次操作目标块
  writtenBlockIds: string[];
  droppedWrites: number;       // 归属校验失败而丢弃的写入次数
  error?: string;
}
export function retryBlock(bookId, pageId, blockId): Promise<RepairResult>;
export function regeneratePage(bookId, pageId): Promise<RepairResult>;
export function getRepair(bookId, pageId): RepairSummary | null;
export function cancelRepairs(bookId, reason?): number;
```

1. **真实异步结果**：返回 Promise，完成/被取代/被取消/不可写/写入失败都有终态；写入失败以 `status:'failed'` **resolve**（不 reject），界面据此显示失败而不是假装成功。
2. **冻结身份**：启动时冻结 `runId`；每一步写入前重新读取记录，`book.run.runId !== 冻结 runId` → 丢弃并计数，**绝不借用新 runId 写入**（迟到写入被拒）。
3. **互斥与取消**：同一 `bookId::pageId` 同一时刻只有一个操作。
   - 同一目标块集合且在途 → 返回**同一个 Promise**（重复点击不产生第二遍生成）；
   - 目标不同 → 取代在途操作（旧操作剩余写入丢弃，终态 `superseded`）；
   - `cancelRepairs(bookId)` 由删除、停止、暂停、失败收尾调用，终态 `cancelled`。
4. 页/块身份、`user_note` 内容、作答版本关系语义不变（仓储层未改）。
5. UI（`PageReader.tsx`）按 Promise 终态驱动忙态与失败文案；`startRun` 返回空句柄时给出显式提示（不静默无操作）。

## 3. 租约与多标签契约（M22-03）

- 租约记录增加 `nonce`；获取租约为**写入后读回校验**：读回不是本标签页本次 `nonce` 即视为未取得（多标签同时启动时落败方不启动执行器）。
- **每步驱动与每次心跳都校验归属**；`lease.owner !== 本标签页 owner` 或 `nonce` 不匹配或记录已消失 → `lease-lost` 收尾，停止续租、不再写入。
- 清除租约只在 owner+nonce 匹配时执行（不误删其他标签页的租约）。
- **如实边界**：`localStorage` 没有 CAS，本批实现的是"写入后读回 + 每步/心跳归属校验 + 失权即停"，**不宣称强原子性**；两个标签页真正在同一毫秒写入时仍由"后写者胜 + 败者在下一次校验停止"收敛。
- 多书共享集合（`zhiqikeyuan:books`）的读改写：写前在新快照上重放本次变更、写后读回校验，有界重试（≤3），避免用过期整表覆盖其他标签页对**其他书**的更新；被并发覆盖时收敛重放，不静默丢失。

## 4. 界面契约（M22-04 / M22-06）

- `BooksRoute` 工作区：首次读取失败 → 可见错误 + 「重试读取」入口（不得被加载分支掩盖）；读取成功后清除旧错误；加载态只在既无数据也无错误时出现。列表页删除书籍前先 `stopRun(bookId,'delete')`。
- `PageReader` 全局 `←/→` 翻页必须排除：`input` / `textarea` / `select` / `contenteditable` 目标、组合输入（`isComposing`）、修饰键（Ctrl/Meta/Alt/Shift）与已 `preventDefault` 的事件；普通阅读上下文仍然有效。
- 新增 UI 只复用既有控件与变量（`space-banner` / `space-button` / `--blue` 等），不重做主题、不新增第二套样式定义。

## 5. 验收条件

1. 三个审查探针改造为正式回归时**断言正确行为**（不再断言缺陷存在），并在修复后运行原探针证明缺陷不再复现（断言反转的原始记录保留在 `docs/qa/main-review-20260922/`）。
2. 新增：真实双标签竞争/失权停止、存储读取失败收尾、删除收尾（无心跳残留）、迟到写入被拒、重复点击互斥、笔记方向键不翻页、最终完成写入失败不假报成功且有恢复入口。
3. `npm run typecheck`、`npm run lint`（0 警告）、`npm run test:unit`、`npm run build`、相关 E2E；候选冻结后跑全量 E2E，未执行项如实记录。
4. 稳定候选交独立验收者只读复验；自检不得写成独立验收。
