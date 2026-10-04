# B6 两等待适配独立签核 v1

结论：**PASS_SCOPE_REVIEW / STOP**。只读精确差分支持两处等待适配；本报告不代替正在运行的完整 check，也不关闭 B6。

当前冻结 `CANDIDATE-B6-R01-r2-qa3.json` SHA `a03ca240b84d0f16761b26897d94bdbb55483d6b8d64cecc0c986e3acff70021`（942 源项）。仅核测试及 SourcePanel 两文件绑定；typegen/build 运行期间未核整组或 next-env 一致性。

原 `lesson-workspace.test.tsx` 99942 字节 SHA `1f869cc95d897b344d22786755022f87754e6e2e2d239a358094671d8d8d74ef`；适配后 100030 字节 SHA `24ef1e1ee92c05e6230302f4f9fa2e10306d62f45a952a1ff27d5ea1e447c896`，与 qa3 精确匹配。独立用保留的原二进制，仅插入/包裹以下两处，重构整个文件后与当前文件逐字节一致：

1. 原 `findByText` 保存失败之后，增加 `await screen.findByRole('dialog', { name: '离开当前教案' })`，再执行原按钮及业务断言。
2. 原最终 `queryByRole(...).not.toBeInTheDocument()` 原断言保持，只包入 `await waitFor(...)`。

授权四决策块的原 15 个 `expect` 完整保留为 15 个；retry / keep / discard / cancel、正文、缓存原字节、router、save 次数及重试原包等值断言没有修改。块外前缀与后缀字节一致。未增加 hidden:true、sleep、skip、retry、timeout、fake timers 或 mock 改动。作者此前口述 12 不采用，以原二进制和 SCOPE 的实核 15 为准。

两轮原完整 check 首败保留：第一轮 discard 找不到可访问按钮，缺实际 dialog.open/effect 时间戳，不能将候选时序解释称为已证实环境原因；第二轮 retry 的日志实际仍含 open dialog，先前导航/重试/缓存断言已经完成，证明等待导航记录不能替代等待最终对话框关闭。两等待使测试直接等待原本要验的可访问状态，没有删除行为条件。详细事实及未知界限见 `B6-CHECK-DIAG-v1.md/json`。

作者自检 `b6-integration/check-qa/COMMAND-r1.json`：PID 8284（runner 16560）、10979.092ms、exit 0、完整文件 96/96，log SHA `d3039cd16b95cd0245169722600fa20a86d33065c16379115036ed950581dabd` 已核；sourceDrift/qaDrift 空、ownQADrift false、child/log 均 closed。这是作者自检收据的独立阅读，不是本 agent 重跑；不与原两完整失败拼绿。

当前 SourcePanel SHA `bb4399c57492ea1a7b96ded0dc79a9f1aab5e648417ea2618fd83aa1aad1d9c8` 与 qa3 精确匹配；两等待适配未改产品。本次未执行 QA、命令、服务、Git 或产品修改，仅新增本 leaf。ROOT 完整 check 仍待结束与恢复后全组签核。RAG-REL OPEN、live_run 待输入、teacher_review_pending 保持。

机器结果和所有输入 SHA 见同名 JSON。
