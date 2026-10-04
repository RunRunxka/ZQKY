# G3-BOUNDARY 源候选 r1 静态审核

2026-10-04。候选 `CANDIDATE-G3-source-r1.json` SHA `4d7b317d093b1a42840eb49a303fc7309b5446b07ded234a45e4ae592e31422b`。作者已 STOP；CTRL 的完整 check/build 正在执行。本审核不运行测试，不把临时 typegen/next-env 变化算入产品差异，也不改产品或旧证据。

## 精确来源

| 产品 | 原 B5-r8 SHA | 本候选 SHA |
| --- | --- | --- |
| useServerPersistence.ts | `8e4cf9e31e01aa6c2f965ba2b58e5d7efde3a171b9d59a80f953bdcbe84b895d` | `287242776ef5eba6e3b6632c4d1ed331f4e3ecfd8c29c477d8057a44c97562cc` |
| DocumentsPanel.tsx | `de66e6f5ae118bfa0c2d40165381cb4f062ff312ba1bf3d725afa7a0fd82b58d` | `d766b73ff2852432cdd3883f236935959fd7ddd3c779b11aee388985d2e99e45` |

旧源码分别取自原清单中相同 SHA 的 `b5-fe/before-v2-source/.../useServerPersistence.ts` 和 `b5-fe/f30-v6-lint-r1-source/.../DocumentsPanel.tsx`，逐字节核对后生成本目录两份 `.source-r1.diff`。没有靠当前 Git diff 推断原候选字节。

## 已见修复与作者覆盖

R01 同步清 timer、增加 writeEpoch、设置 paused，成功后从深克隆 known 恢复固定正文及上下文，并 hydrate 清 Undo 栈；严格核文档/CAS/固定 revision/version，拒绝较旧 known。persist/pagehide/keep/flush、save 完成及 auto 都新增暂停或代次门槛。删除失败保持 cache 和内存，只允许明确 save 或重试 discard 解除暂停；running/unknown/exclusive/auxiliary/cache_error 拒绝。

R02 深冻结首次 pendingCopy，冻结文档、store、load/edit/writeEpoch、原 CAS、固定正文 hash 和原 intent 引用/内容 key；返回前核同一 owner/session 与编辑代次，不以刷新后的 CAS 自证。双击受同步 symbol owner 阻断，finally 仅释放同一 owner；成功一次 replace 和 finishCopy 保留 Undo 新编辑语义。

作者最终单轮 5 文件/132 例（20 新场景、112 既有）和 type/lint 通过是作者自检，本审核只读其 RESULT-v1。作者 type 首败为新 mock 断言的 TS2339，原运行快照/日志保留，不能记为产品失败；不把作者自检代替独立或真实浏览器验收。原 navigation-guard、LeaveProtection、本地 writer 和公共契约未改。

## 待动态反例：旧来源回调可能恢复写权限

**状态：静态待复现，不记已确认缺陷，不给总体 PASS。**

`useServerPersistence.setContext` 未检查 paused/writeEpoch，调用 `store.set({})`。store 订阅把任何 revision 变化当新操作，会解除 `paused='discarded'`。而 `SourcePanel.selectRun` 的异步读取完成会调用 `updateSelection → setContext`，该旧来源读取没有绑定 server.writeEpoch。这条路径不一定来自放弃后的新教师编辑。

可实际验证的行为条件：

1. 隔离后台教案已有固定 BASE 学情上下文；SourcePanel 正常打开/读取 BASE。
2. 教师改选报告 A，把 A 的真实业务读取延迟；此时 selection 仍 BASE。
3. 编辑正文 A，明确放弃，恢复 BASE 正文/context，旧子树仍保留。
4. 旧 A 读取完成：selectRun 的 kept 为空时 updateSelection(context:null)，setContext(null) 触发新 revision 和自动保存。
5. 正确行为应是旧操作失权、服务器新增保存 0、固定正文/context/历史不变，恢复键不重建弃稿来源。若当前候选实际保存 BASE 正文+null 新上下文，应登记为本次 R01 未封存的来源入口，而非重开旧 B5 编号。

另需核 discard 后 doc.selection/SourcePanel 显示与已恢复 context 的一致性，以及教师在留页后明确的新来源选择如何作为新操作正常保存。两者应与旧异步回调区分。

已即时通知 CTRL，本审核不会修产品。待完整 check/build 和新冻结候选后运行手写 5 场景；上述来源反例由 CTRL 安排独立实际组件/浏览器复验。当前 G3 待验，B6 未启动。
