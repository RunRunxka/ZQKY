# BOOKS-CS-FOLLOWUP v1 批次证据（有界前置补丁）

- 起点候选：`d2638f2`（`main`，开工工作区干净；未切分支、未合并、未推送）。
- 范围与冻结契约：[TASK-CARD.md](TASK-CARD.md)（只收口 H1-BOOKS-COMMIT-SAFETY v1 独立验收提出的 F3/F5/F6/F7/F8 与测试口径，不做引擎重构）。
- 依据：上一批 [A1 报告](../H1-BOOKS-COMMIT-SAFETY/A1-REPORT.md) 的挑刺段落。

## 1. 本补丁做了什么

| A1 挑刺 | 处置 | 关键文件 |
| --- | --- | --- |
| **F3 缺 Web Locks 时静默降级** | 集合锁改为**可注入 provider**：生产只认原生 Web Locks；缺失即 `withCollectionLock → {ok:false,reason:'unavailable'}`，仓储新增提交状态 **`unsupported`**（"本次修改未保存"，读取与草稿不受影响）。**localStorage 启发式回退锁整体删除**，不为 jsdom 保留不安全生产路径；单测经 `__setCollectionLockProviderForTests` 注入 in-process 互斥（注入是否生效可见） | `services/collection-lock.ts`、`services/books-store.ts` |
| **F5 控制操作未按提交结果分支** | `pause()` 返回 `{paused, message}`：只有 `committed` 才收尾为 paused 并报成功；未提交时执行器继续运行、UI 提示"暂停未保存"（不显示"已暂停"）。`resume()` 沿用既有 `resumeBookRun` 结果校验（未重写恢复逻辑） | `services/book-generation.ts`、`features/books/BooksRoute.tsx` |
| **F6 死分支** | `queueFlush` 显式分派 `applied/dropped/failed/conflict` 四类结果（原 `if (!applied) continue;` 恒不成立） | `services/book-generation.ts` |
| **F7 修复任务生命周期** | `startRepair` 内部异步任务整体 try/catch/finally + `finish` 幂等：任何抛出（含复位成功后计划读取被拒）都以终态 settle、注册项在 settle 时删除、界面忙态退出；取消/取代/runId 冻结/迟到写入语义未变 | `services/book-generation.ts` |
| **F8 启动重入** | 确认窗口成立（`registry.set` 在 `await setRunScenario` 之后）→ 在**第一个 await 之前**登记启动中占位，第二次并发调用复用同一次启动（不产生第二个执行器/不重复写租约） | `services/book-generation.ts` |
| **测试口径** | 原"双标签页并发写不同书"改名（实为同一本书不同页）；新增**真正不同 bookId、不同内容**的双标签页并发写、持锁暂停、二次并发 `startRun` 只启一个执行器等回归 | `tests/e2e/books-commit-safety.spec.ts`、`services/collection-lock.test.ts`、`services/book-generation.test.ts` |

## 2. 队长集成决定（超出实现者范围的补充，如实记录）

1. **范围外两个测试文件加 provider 注入**（各 2–3 行、只加注入不改断言）：`services/courses-store.test.ts`、`features/books/BooksRoute.test.tsx`——jsdom 无 Web Locks，不注入则写路径返回 `unsupported`。同时把 `features/books/PageReader.test.tsx` 迁移到新钩子，并**删除兼容 shim**（`__setCollectionLockOptionsForTests` 与废弃的 `CollectionLockOptions` 类型；此前保留只是为了让该文件不改动）。
2. **写冲突改为"预算内重试 + 背压"**（集成决策）：实现者原方案在 flush 拿到 `conflict` 时按有界计数重试，但驱动循环仍会抢先推进页/块，导致"锁被占"时整轮跑到收尾然后以存储失败终止——控制操作（暂停/恢复/停止）与"持锁失败→释放重试→刷新后保持暂停"的验收因此无法稳定成立。现改为：
   - flush 在冲突时把剩余事件放回队首、**等待 300ms 后整体重试**（`await queueFlush` 因此等价于"等到真正落库或预算耗尽"，驱动循环自然获得背压，不再抢先推进）；
   - 连续冲突预算 **20s**（可配置常量），预算耗尽才按 `kind storage` 失败并如实点名"写入冲突/另一个标签页"；
   - `pause()`/`stop()`/`stopRun()` 的写盘等待为**有界最尽力**（1s 上限），控制与停止流程不被写盘阻塞。
3. **新增两条冲突回归**（`book-generation.test.ts`）：① 其他标签页短暂持锁 1.2s → 冲突被预算吸收、整轮照常完成；② 全程取不到锁 → 如实终止（`getRunExit` 为 failed 且文案含"写入冲突/另一个标签页"）、无残留句柄与租约、存储停在 `compiling`（不假报完成），释放后可恢复跑完。

## 3. 实跑结果（本批，队长集成后）

| 维度 | 命令 | 结果 |
| --- | --- | --- |
| 类型 | `npm run typecheck` | 通过 |
| 静态检查 | `npm run lint`（`--max-warnings=0`） | 通过，0 警告 |
| 单元测试 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **49 文件 / 403 例通过**（上一批 48/389） |
| 构建 | `npm run build`（总控自跑） | 通过，`BUILD_ID = kuKTXV4Pi5WG0pN37WJCr`（迭代见 §4） |
| 书籍 e2e | `npx playwright test tests/e2e/books-commit-safety.spec.ts tests/e2e/books-pipeline.spec.ts tests/e2e/books-courses.spec.ts` | **26 例通过**（6 commit-safety + 14 pipeline + 6 courses） |
| 后端 | 未运行 | `apps/api` 零改动 |

未执行：全量前端 e2e（与课程批集成后由队长跑一次）、真实浏览器进程级并发（e2e 为同 context 双标签页）、CSS/视觉/动画（本批无样式改动）。

## 4. 迭代与首败（如实记录）

- 实现者首败：F7「Promise 未在 4000ms 内 settle + `planPage` 未处理异常」、F8「并发两次 startRun：其中一方返回 null」；修复后转绿。
- 队长集成首败：
  1. 背压缺失导致"持锁暂停"e2e 在第二段失败（执行器在锁被占期间跑到收尾并以存储失败终止）→ 引入背压 + 预算后通过；
  2. 同一条 e2e 另有**测试自身缺陷**：`getByText('生成已暂停')` 命中 3 个元素（横幅标题、横幅正文、活动条阶段）触发 strict mode violation → 断言改为限定容器（`.book-pipeline-paused` 与活动条）；该失败经页面快照确认"暂停其实已成功"，属测试写法问题而非产品缺陷。
- 构建迭代：`z5Qhnq8sK9Tm4rGTgWEtQ`（首轮）→ `kuKTXV4Pi5WG0pN37WJCr`（背压修复后）→ `YhmHpWDKx-EgSf1pGHkZh`（有界最尽力写盘后）→ 最终候选见 FROZEN 记录。

## 5. 边界与已知行为

- 无原生 Web Locks 的浏览器上书籍**写**功能不可用（读取/草稿/导出不受影响）——这是本补丁的明确取舍；如产品需支持旧浏览器，正解是引入真实 CAS 或服务端，而不是恢复启发式回退锁。
- 锁被长时间占用（>20s 连续冲突）时整轮按 storage 失败收尾；若此刻失败原因也写不进存储，书籍停留在 `compiling`（界面显示"已中断 + 继续生成"，不假报完成），释放后可从断点恢复。
- 仍不宣称强原子性：写后校验能发现写入窗口内的常见并发改写并如实报 `conflict`，但等价于同时写入的亚毫秒窗口无法证明；口径已在文档中订正（不得声称"必然发现所有绕过协议的写入"）。
- 未覆盖：真实两浏览器进程/两 profile 并发、>1.5s 空档长临界区的真实 Web Locks 实测、移动端与逐帧动画。
