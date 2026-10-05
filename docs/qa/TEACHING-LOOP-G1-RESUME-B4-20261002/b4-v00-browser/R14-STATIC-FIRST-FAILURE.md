# B4 R-14 独立只读首败归因

任务：B4-R14-STATIC v1；独立核对者：G1-V00-FE。只新增本报告与同名 JSON；未执行测试、浏览器、服务、构建或恢复操作，未改产品、原 spec、可执行 QA 或旧证据。

本轮 `full-e2e-real-fixed-first` 实际结束：152 passed / 1 failed / 0 skipped / 0 flaky，PID 17920，exit 1，外层 497986.093 ms。唯一失败为原 `books-commit-safety.spec.ts:238`，单例 137679 ms、retry 0；真正失败断言在 **267:35，second / 书 B 的 `.book-pipeline-strip` count 0**，原 120000 ms 内一直收到 1。152 个成功不使本轮全量门禁通过。

这次证据支持「明确 interrupted 与原测试无条件完成假设不一致」。未观察到恢复尝试，不能认定恢复有效或失效，也不能认定新产品缺陷已排除。当前台账 `CURRENT_STATUS.md:103` 的 R-14 仍未关闭。

## 实际 trace 与画面

证据仅来自本轮 `b4-e2e-real-fixed-first/artifacts/books-commit-safety-H1-书籍提-8a985-签页并发写不同书：两边内容都在、无覆盖、结束后无悬挂锁/`。`trace.zip` SHA256 为 `c12b66d8e88bafaf806abb804a0ec65d5c60d389a48da1a1e97578ebad175aa3`，889 entries；Python stdlib `testzip()` 无 CRC 错误。目录没有独立 screenshot 文件。实际查看了 ZIP 内最后一张 B 页 screencast JPEG；未解压写入额外文件。

| 阶段 | 实际证据 | 结论边界 |
| --- | --- | --- |
| 初始保存 | call@1052 / call@1054 从真实 localStorage 读回两条正确笔记；31305.620 / 31310.735 ms | 原 258–263 两个 poll 已通过，证明完成前两笔记均在库 |
| 书 A 完成 | call@1056 / expect@68，31312.903→39227.732 ms，matches true / count 0 | 原 266 行通过 |
| 书 B 等待 | call@1058 / expect@69，39230.978→159247.039 ms，timedOut true / count 1；123 次解析为 1 | 原 267 行真实首败 |
| 书 B 最终 DOM | after@call@1058，159248.928 ms，B 固定 URL；文字「生成已中断（无执行器在跑）」、可见「继续生成」、计时 00:15，status 不含 breathing | 正式 interrupted UI；不是仅凭主页面 error-context 猜测 |
| 原 finally | call@1060，159251.273→159260.136 ms，second.close 成功 | 第二页已关闭；不代表未执行的锁卫生断言通过 |

书 A：`bk-mur5cyys-xaavl2` / `pg-mur5cz1s-cgwrjo`；书 B：`bk-mur5d29m-i5iot3` / `pg-mur5d2bh-bz5123`。`error-context.md` 是主 page A 的阅读器，已无活动条，不能据它否认 B 的中断。最后 B 的 JPEG 处于阅读器较低滚动位置：实际可读 B 的本地笔记及尚在生成的 deep_dive 块；活动条不在该帧画面内，**中断文字及按钮证据来自 DOM snapshot**。JPEG SHA 为 `357b9ed69c73cc8a61b20ceeccbf79cfd697bbc5f9e576da76a43e0077ff6564`。

trace 没有「继续生成」点击，也没有本例最终 `navigator.locks.query()` 或 lease 原值读取。后续原 270–279 行（生成后跨标签笔记、两个 bookId、held/pending 0 与无旧锁键）全部未执行。不能把保存前半程成功扩大成最终无覆盖、无悬挂锁通过；也不能把具体触发因果直接认定为集合写锁或租约失权。

## 源码依据

`books/AGENTS.md:20–26` 与当前 R-14 台账明确保留中断及断点恢复语义，禁止笼统加等待或反转断言。

- `BooksRoute.tsx:538–561` 同挂载已运行后不自动重启，保留中断及恢复入口；`1144–1158` 在 compiling、无本地 working、无 remoteLease 时派生 interrupted。
- `BookGenerationStrip.tsx:80–95,126–134` 显示准确中断文案及「继续生成」，点击走 onResume；`BooksRoute.tsx:704–722,1260–1272` 连接真实 resumeRun，失败有明确通知。
- `book-generation.ts:1342–1359` compiling 可重新启动断点执行器；`925–958` 对实际书状态/他方租约/读取/租约获取进行守卫。这里只核了调用路径，未实际验证恢复结果。
- `books-store.ts:1336–1358` 若仍有 pending/planning/generating/error 页，finishBookRun 保持 compiling 且 run stopped；`book-generation.ts:1101–1142` 收尾依据已提交书状态选择 finished 或 interrupted。`applyStored:571–592` 对写冲突返回可重试 conflict，不能由本次 trace 推定具体冲突曾发生。

原 spec、BooksRoute、BookGenerationStrip、books-store、book-generation、collection-lock 六个文件的当前 SHA 全匹配 r17，且 r1→r17 逐字相同（完整值见 JSON）。这六个关键源未被本轮 B4 修改。P 的正式 post 记录另核产品878、QA45、契约5、build2007 均零漂移，next-env 原字节一致；该全量 post 为 P 的证据，不冒充本独立任务新跑了全量冻结审计。

## 最小后续建议（尚未实施）

CTRL 可单独登记此原 case 的 QA 契约适配：每本书仅接受已完成（strip 0）或**准确 interrupted 且 enabled「继续生成」**两个分支；在中断分支先明确断言此合法状态及已保存笔记，再只执行一次真实 UI 继续动作。paused、error、读取拒绝、无法恢复通知不得被该分支吞掉。完整保留原两个 strip count 0、完成后跨标签笔记、双 bookId、held/pending 0 与旧锁键 null 的全部断言，以及 180000 总 timeout / 两个 120000 timeout；不加重试、固定 sleep、reload 或放宽完成条件。

用户已要求现在暂停。上述测试契约评估及后续执行均为未执行下一步，需用户恢复工作后由 CTRL 独立声明范围；暂停期间不实施。之后如获授权，应在新的稳定候选执行受影响用例与适用全量门禁，保留本轮原首败。若一次恢复返回空句柄、出现失败通知、仍不完成或笔记/锁检查失败，应以新实际证据报告具体产品问题，不能继续借 interrupted 语义解释。此次只读调查不关闭 R-14，也不把未执行的恢复与最终数据/锁检查算通过。

本任务没有持有服务、浏览器、数据库连接或后台进程；文档收口后停写。
