# G6 → B7-B 新提示词独立后验

2026-10-05，只读核 [新提示词](../../../design/teaching-loop-v1/B7B_总控启动提示词_20261005.md)、[恢复实证](../recovery/REVIEW.md)、[试评接续源码核对](REVIEW.md)及相应现行源码。没有产品修改、网络/模型、app.main 导入、数据库/凭证读取、服务/浏览器启动或测试执行；只新增本文件，并将 REVIEW 开头按并行新恢复证据澄清。此后验核的是任务设计，不是 G6/B7-B 实现或验收通过。

## 当前后验结果与身份

**提示词限定设计后验通过，无遗留阻塞建议。** 最新核对字节 SHA 为 `316d88418424511038632f2387d5b6a53f03081de2f969ffa5bbcbc384ee9eba`。初审两处执行细节已由 ROOT 采纳，第一次修订的 SHA `e3e0001c5445789ec4d2ba8c69355420d3e2df8bd44b420f894f5d484f2df982` 保留为本文件核查过程身份；第二次修订进一步明确真实双标签 BrowserContext 和人工交接字段。

总 REVIEW/README 首次后验时未落盘；本次最终后验已实际读取，并核总报告/README、recovery/tools/next 分项、新提示词六个入口均存在，提示词顶部两个相对链接指向已落盘的总报告与 next/REVIEW。总报告中的下一批提示词与 next 分项/本后验链接正确。最终保全 JSON 由 ROOT 单独生成核验，本后验不提前签收该收据。

## 已核实的任务事实与边界

| 项目 | 当前判定 | 依据 |
| --- | --- | --- |
| G6 问题身份 | 正确 | 正常 ACK 在 useLessonOperation.ts:61 直接 write(null)，重试 :74 有归属核验；恢复分项四 foreign 反例失败、四 own 对照通过，旧窄回归 71 通过。不重开 G5 旧误跳或声称正文/HTTP 已丢失 |
| G6 最小设计 | 可执行 | 正常 ACK/公开 cleanup 重试共用判据；同当前 session、完整 FrozenSubmission 身份才删，foreign/坏读拒删并保留明确本次 outcome。承认 localStorage 读删非跨进程原子 CAS，不扩成通用锁架构 |
| B7-B 归属与依赖 | 正确 | 新 CLI/专属账本/测试，生产代码只在注入不足有明确必要性时最小登记；live 依赖 G6 独立关闭 + 执行器独立门禁 + 明确授权范围 |
| 生产链注入 | 正确 | 用 LessonGenerationService.prepare/build_request/execute、Resolver、真实 Provider.complete、JobEngine；不新建 prompt/API/表，不直接把旧 fixture modelPayload 发模型 |
| 发送前预算 | 正确 | 明确 prove_supported_billing_upper_bound → durable_reserve_before_network；无可靠输入/输出/费用上界发送 0，不凭体积上限/事后 usage 声称硬 cap |
| 实际发送计数 | 正确 | 计可能到达上游的实际发送，失败仍计；HTTP 内部重试/redirect 禁止或逐次计，Provider 方法调用不冒称网络发送次数 |
| 模型/wire 漂移 | 正确 | 既有 fingerprint + 实际 profile/model/exact request + wire 上限检查；与旧指纹不覆盖全部请求参数的源码事实相容 |
| response/usage 捕获 | 修订后明确 | durable 记录 response/raw usage 早于候选 JSON 校验；不完整/非法/超预留保留 reservation 并停，只有已核 usage 才结算并释放已知余量 |
| 未知/重启 | 正确 | reserved/dispatched 未结算为 unknown，不自动重发；timeout/cancel/response journal failure 留预留并停止。原成功 receipt 重放 0 新调用 |
| 跨 label 累计 | 修订后明确 | 同授权/scope 共用账本与锁，换 run/output label 不清预算或次数；新增独立反证要求，不允许相同授权开空 ledger |
| Live 独立 oracle | 正确 | 明确旧 aggregate 的 fixture stageMinutes 不当 live 硬条件；生产结构/固定学情事实独立核，旧 expected/raw 不改，不用模型回填 oracle |
| 真人反馈 | 正确 | 有身份/hash/评分/理由的新 label；不能把填写后材料交只接空表的 prepare_review；自动化只核完整性，未返回仍 pending |
| Native/RAG/总体门禁 | 正确 | Word/WPS 实際页数/应用版本/逐页核与历史 PDF 参考分开；RAG-REL 未实际试验仍 OPEN；离线通过不关闭原 B6/B7 整体 |
| 无授权 live | 正确 | 范围缺失只完成 G6 与离线技术条件；不以合法 scope、已配置连接、用户未回复推断授权。teacher/native 明确可独立 pending，不阻塞已授权合格预算技术分支 |

## 初审建议及当前处置

1. **Usage 验证必须在结算释放之前。** 初审伪代码先调用 durable_settle 再判断 unknown/invalid usage，有释放未知额度的实现歧义。ROOT 已改为先 durable_record_response_and_raw_usage，核缺失/非法/不一致/超预留；失败留 reservation/STOP，合格才 settle。取消和响应记录失败也并入 unknown。该修订满足本轮设计要求。
2. **锁/账本不能绑定新输出 label 形成预算重置。** 初审“同 scope/run 输出 label 仅一执行者”容易实现成每个 run 自有空账本。ROOT 已明确同授权/scope 累计 ledger，换 label 承接旧额度/未知预留/次数，并有独立反证。该修订满足本轮设计要求。
3. **浏览器双标签验收措辞已明确。** 初审第三节的“双上下文共享Storage”可能误导两个独立 Playwright BrowserContext，但它们天然隔离同源 localStorage。ROOT 当前已改为同一个全新隔离 BrowserContext 内两个已打开 Page，共享真实同源 localStorage，并明确两个独立 Context 或共享替身不能冒充实际跨页场景。组件反例的 Map Storage 可以保持，浏览器需测试真正同源键归属；该修订满足本轮设计要求。

4. **人工交接字段与 strict 模型范围已分开。** 当前 common.live_scope 只接受五必需模型范围字段与两个预算字段，未知键会被拒绝。ROOT 当前明确 teacherFeedback/nativeReview 用另行文字或交接文件记录，二者可并行 pending，不是 live scope 必需字段，不塞进 strict scope JSON。无需为收两项备注改旧 preflight；该修订满足本轮设计要求。

本文件不是新产品 finding，也不要求重建离线包。任何技术候选真正实现后，仍必须按本提示词独立实跑，不凭本次静态后验签成 G6/B7-B 已通过。
