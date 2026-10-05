# B5R-R07-STATIC-v2 — 本地先 flush 稳定候选独立静态审查

- 负责人：/root/b5_r06_review；仅新增本 MD／JSON 两文件。
- 结论：本次静态范围未确认新增 P1/P2。普通本地稿先串行 flush，成功无需额外人工决定；失败与后台／打印／来源变更保护保持。作者结果是待独立验收，静态审查不关闭 R07／B5。
- 未运行测试、浏览器、HTTP、SQL、服务或 Git；ROOT 的独立测试、source check/build 和新完整浏览器门禁另证。

## 稳定身份与范围

作者 STOP UTC 2026-10-03T12:58:29Z。PRIVATE-MANIFEST-v5 SHA-256 78a0a7387246bf933ece3a7d885173fe122dd46f94a30299a777dd2c1683494a，RESULT-v5 JSON SHA-256 7bfd231b2fbe19eb28860753b96948d60a8521da2e8c4d3db0091bdc3c7d0d47。独立本轮读窗口 2026-10-03T13:02:33.114869+00:00 → 2026-10-03T13:03:21.959700+00:00，两文件与最终 manifest 一致：

| 文件 | 修前 SHA-256 | 稳定候选 SHA-256 |
| --- | --- | --- |
| LeaveProtection.tsx | 11ffd5e0fcf4dd5976f85cd2f656ded93196e106850711646701a02d3a160a8c | 6fa64d6ef42b6e24e56c2b9f10079fbd337d0999687875cd4df7dca98a866e77 |
| lesson-workspace.test.tsx | 138f73415291003b670d8687351c40369ed496d8e22b576666adc04622629f8d | 4c6637c342ed181b315c1550a310cb47ff1b381a3faa066a1c579c1e9eaf2ee8 |

作者 scope 43 对 BEFORE-v5 仅这两项改变；对最终 manifest 43 项零漂移。public read-only 6（含 navigation-guard）、冻结契约 33、旧 v9 QA 原件 201、前序证据 2198 均 raw SHA 零漂移。原 source/public 导航代码、writer、DocumentGateway、后端及 R04/R06 不在增量中。

本报告精准绑定两文件及冻结契约／私有保全组。ROOT 可能并行生成 next-env 与新 build；这些属于 ROOT 的 check/build 归属，本审查未对完整 938／build 做新阶段关闭或把派生 next-env 判成未知写入。

## 本地分支与保护核对

ask 首先确认 active，捕获当前 editor/store、mode/documentId 与 epoch；打印快照仍直接阻断。已有人工 promise 保持复用，自动 flush 的第二次请求由 flushing 拒绝，避免新增重复离开。

canFlushLocal 仅在 local mode，且无 server/history、存储 block、打印、create/import busy／unknown 时成立。存在 localPending 才进入现有 flushDraft；它使用原串行 writer，等待在途保存、drain 更新。每次 awaited flush 后验证 active／epoch／原 store／mode／documentId，再读最新 editor/doc；若还有正常 local pending 则继续 flush。来源更换或卸载直接 false，不能晚到导航。

失败不当成功：失败信息保存，最新输入和 pending 留存，进入原四种人工选择。正常成功后重查所有 dirty／unknown／busy／storageBlocked／pendingOperation 状态；期间 unknown／busy 仍走原保护，期间 printSnapshot 仍提示并保持当前页。flush finally 只释放同 epoch 的 flushing/saving，不对过期实例 setState。

server dirty／conflict／unknown、固定历史、坏稿及打印原路径与四决策按钮保持。public guard 的 mounted／epoch／registration／entry 身份检查未改；DocumentGateway 的 sequence／alive 等原检查未改。未找到需要放宽旧导航安全守卫的证据。

## 新 15 与旧 106

新 15 个展开实例核对为：

- 普通快速本地导航 provider false／true 两例；打开后台前先保存本地稿一例。
- 延迟 ACK 一例；延迟中第二代新编辑串行落库一例；文档身份更换后旧 flush 不导航一例。
- 保存失败 retry／keep／discard／cancel 四例，核原包与原旧键／输入保持。
- 坏旧字节不覆盖一例；本地 operation busy／unknown 两例；flush 期间变 unknown 一例；flush 期间打印一例。

这些使用实际 createDraftWriter 路径与受控 repository ACK／拒绝，断言导航之前落库、串行 revision、最新输入、原旧键及未知／坏稿阻断，不只是镜像状态字段。backend 原分支由保留旧测试覆盖，本审查不冒称重跑。

剔除新增两 import 与新增 helper/describe 区段后，旧 workspace 测试原始字节与 v4 完全相同；没有更改旧 assertion/body/budget。其他四作者测试文件保持。修前同组 121 的 10 失败均属新正确行为，旧 106 无失败；新 5 保护实例原先已能通过。

## 原失败、作者两轮与 lint 修正分列

原独立完整 153 first 仍保持 151／2 产品失败，两条旧本地浏览器用例不改、不适配、不豁免；新候选须重新独立执行，不能拼原 151 绿。

| 已有作者记录 | PID | exit | 单轮结果 | ms |
| --- | --- | --- | --- | --- |
| 修前 unit-before | 12772 | 1 | 121：111 pass／10 fail | 25409.818 |
| 修后 unit-r1 | 13520 | 0 | 121／121，5 文件 | 13259.966 |
| 最终 unit-r2 | 28488 | 0 | 121／121，5 文件 | 13359.631 |
| type-r1 | 10876 | 0 | 类型检查 | 1807.890 |
| type-r2 | 24564 | 0 | 类型检查 | 1838.577 |
| lint-r1 | 11532 | 1 | 新 QA 两个 hooks immutability 错误／0 warning | 3107.214 |
| lint-r2 | 8892 | 0 | 0 error／0 warning | 3229.847 |

修前→unit-r1 的 source 48 映射仅 LeaveProtection 改变，测试 QA SHA 同为 4694bac0a5b98f79c57ce416d194fd2d32148ca3c4d898882ebde47a28d75c00，确认产品修复使同断言通过。lint-r1 首失败原件保留；unit-r1→r2 仅新增 QA helper 内 pendingOperationRef 别名，并把两个操作设置按钮改为同 ref.current，断言／计数／预算／operation 状态不变。最终 QA SHA 为 4c6637c342ed181b315c1550a310cb47ff1b381a3faa066a1c579c1e9eaf2ee8，产品 SHA 不变。

已独立读取上述回执、结果 JSON、日志与源快照；各命令自身 sourceBefore／sourceAfter 相同，changedSources 空，日志／结果 SHA 与回执一致，child/log closed，隔离 TEMP 保留。作者绿色结果不是本审查运行所得，也不是独立浏览器验收。

## 本轮结论边界

只有静态无确认新增 P1/P2；新 R07 正确行为、原两浏览器失败、完整 153／聊天适用门禁及整个新 source/build 身份由 ROOT 的独立证据决定。本轮停止写入；R07 与 B5 保持未关闭。

