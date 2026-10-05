# G4-E v1 作者结果卡

2026-10-05T13:00:27.172510+08:00：**AUTHOR VERIFIED / STOP，待独立技术与真实浏览器验收**。B6F-R01 是继承路径的新发现问题，未重开旧 G3/B6。只写授权七个产品文件和一个新行为测试；SourcePanel、公共契约、后台、锁文件、权威文档、旧 QA 与 Git 未写。

后台可读内存包临时写失败提供“重试恢复缓存”，完整正文11字段/secondary/context/source/四类原操作与编辑、ACK、CAS身份先写入并读回核验，跨会话或输入变化不解锁。更高后台读取保留 cache_error 入口，成功恢复后仍转人工冲突。坏读取拒绝覆盖，持续失败与假成功写入均无 HTTP。缓存成功不冒称后台保存成功，后续仍是原保存与 CAS 流程。

原操作区分读取阻断、发送前可信冻结包写失败、明确结果后的清理失败。发送前恢复保留首次 submissionId/payload/metadata，随后显式原包重放；已有 HTTP 未知结果不会被下一次缓存失败改称尚未发送。明确 ACK 清理只处理缓存，不重发业务或模型请求。create/import 的恢复阻断经 ROOT 可选 recoveryBlocked 接线进入离开保护；未知与尚未发送状态分开。

生成首次 operation/selectionKey/sourceEpoch 在首次冻结时保留，后台原包或独立签名失败可恢复，后来来源不会重建原签名。可信 Job 回执的观察签名和原包清理失败保留实际 Job，恢复不再次调用生成端口。应用、拒绝和历史复制的业务语义保持。

## 实际单轮验证

| 命令原件 | PID / 耗时 | 结果 |
| --- | --- | --- |
| author-regression-r2-command.json / .log | 3840 / 11345.110ms | 六文件 **156/156**：新24 + 既有132；source/QA前后零漂移 |
| author-types-final-v1-command.json / .log | 19276 / 1833.985ms | **直接 tsc --noEmit** 通过；没有执行 Next typegen/build |
| author-lint-final-v1-command.json / .log | 3156 / 2271.765ms | 授权七文件及新测试 lint 0 警告 |

新24例含实际工作台公开缓存恢复、持续/假写零HTTP、真实离开对话框、坏原字节、CAS、更换文档迟到、原保存包及后来编辑；五类原操作原包、未知结果、可信ACK清理、跨操作迟到；公开create/import恢复及create ACK；生成双缓存失败保首签名、可信Job清理、公开应用/拒绝恢复。既有五份 QA 原字节与开工相同，不改旧断言。

首次新测试 r1/r2 各19/2：采用与拒绝恢复时 auxiliary busy 尚未收敛，完整后台重试按守卫拒绝。恢复按钮补 server.busy 可见禁用，与实际拒绝条件一致；QA等待按钮实际启用后点击，原包/HTTP/字段断言保持。r1直接tsc的测试Mock类型与ByRole参数准备错误已修；首次代码副本和日志保留。受影响整轮 r1 为155/1，旧生成测试要求“首次生成来源签名写入失败”定位文案，修复时恢复具体文案，可信ACK仍独立文案；旧QA不改。r3新21/21、此前类型/lint成功均为诊断，最终收据只绑定当前156整轮及最终tsc/lint，不拼绿。

## 可独立重跑

从仓库根目录以 bundled Node 24、NODE_OPTIONS=--no-experimental-webstorage 执行：

```powershell
node node_modules/vitest/vitest.mjs run apps/web/src/features/lesson-plan/g4-recovery.test.tsx apps/web/src/features/lesson-plan/model/server-session.test.tsx apps/web/src/features/lesson-plan/model/lesson-operation.test.tsx apps/web/src/features/lesson-plan/model/g3-persistence.test.tsx apps/web/src/features/lesson-plan/g3-history-copy.test.tsx apps/web/src/features/lesson-plan/lesson-workspace.test.tsx --reporter=verbose
```

每轮实际 Node 绝对路径、argv、cwd、PID、退出码、持续时间、逐源/QA SHA及关闭状态见 command JSON；ROOT 可用新 label 调用 `edit/run_author.py <new-label> regression`，已有 label 拒绝覆盖。全 check/build、真实浏览器/服务与四视口故障由 ROOT 后置，作者未执行，不能据本卡关闭G4。未导入app.main、读.env/正式数据、模型调用或管理用户进程；所有作者子进程和日志关闭。next-env保持开工原 SHA，旧材料与首败未删。

## STOP 字节

| 文件 | SHA256 |
| --- | --- |
| `apps/web/src/features/lesson-plan/model/useServerPersistence.ts` | `70db2c7c8ea8e13fa2e76050934c215fa8d14b3e7b4a59e26a3957e53741fcb0` |
| `apps/web/src/features/lesson-plan/model/useLessonOperation.ts` | `a856ff60419d5ca4894e1e331234203ff424274192d9163eda5b3e206011d977` |
| `apps/web/src/features/lesson-plan/model/EditorContext.tsx` | `7362210890284a53151ce80506517a8bc9419a59d66efa8bf8aa30df99d986cc` |
| `apps/web/src/features/lesson-plan/components/ServerControls.tsx` | `0f55c9cb0e2c7af39df707ede943d3e6addfeddda25fc9434f8f03f264c9e9b9` |
| `apps/web/src/features/lesson-plan/components/LeaveProtection.tsx` | `ade07889c1396f7cb942281ab85eacca439d4c58dd1adeb65b91a47e9c752b95` |
| `apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx` | `f367a999ac56be86fb5569d4657f28c2d73a56c56dd7d5e66582f4910c05482f` |
| `apps/web/src/features/lesson-plan/components/ProposalPanel.tsx` | `cbb74dff97a301dd943f41e8f8d892323395424335e87c173f7fb59bfb0c7cc8` |
| `apps/web/src/features/lesson-plan/g4-recovery.test.tsx` | `b15a48f3cc970c96db961adb451c1931bb1952704727ca99ad78091b2aabbd53` |

共享两文件由ROOT独占，本文只绑定读取时SHA，未代写。完整机器收据见 RESULT-v1.json。STOP后不继续写产品或测试，等待ROOT独立结果及必要新修复卡。
