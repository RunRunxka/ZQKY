# G4-E v2 最小补修作者结果卡

2026-10-05T13:20:40.838337+08:00：**AUTHOR VERIFIED / STOP，待 ROOT 冻结与独立验收**。本版只改 `model/useServerPersistence.ts` 与本批新增 `g4-recovery.test.tsx`，其余六产品文件、五份旧 QA、SourcePanel、共享契约与上下文、next-env 原字节均保持 v2 开工 SHA；v1 的 42 个 edit 原件及 RESULT-v1 保持原字节。作者不修改 ROOT QA、权威文档或 Git，不启动服务或模型。

第三轮真实浏览器原结果是 **9/11，两例失败**，原 log/command/trace/error-context 保留。pre-send 缓存写失败分支 notify 时 `running.current` 尚持有 promise，finally 清 ref 却没有重绘，公开恢复按钮与仅依赖 busy 的后台刷新按钮滞留 disabled。最小改动仅在同一 promise 被清理后，检查 mounted/documentId/loadGeneration/writeEpoch 当前会话再 notify；busy/exclusive、原 operation、0 HTTP 和完整缓存读回守卫保持。旧文档或旧加载的迟到结果不会通知新会话解锁。

坏缓存旧 QA 在已加载页面中注入后 reload，正常 pagehide 刷新可信内存覆盖了注入，故新页未进入坏读取保护；这是注入生命周期位置问题。ROOT 将改为新会话 init 注入并保持坏字节、blocked 与零后台增量断言；作者不改产品 pagehide，也未修改该 QA。本卡不能把原 9/11 或构建成功转签为浏览器通过。

新增两例经实际 ServerControls 验证公开行为：pre-send 故障异步结算后缓存恢复和后台刷新按钮可用，刷新及完整包恢复均无保存 HTTP，耐久包与首次失败包完全相同，显式原包重试仅一次且 submissionId/payload 不变；另通过相同 Provider 实例切文档，旧 A 保存迟到不解锁 B 的缓存恢复/刷新控件、不覆盖 B 唯一输入、不写 B 缓存或另发保存。原 G4 24 例及既有 132 例全部保留。

## 最终稳定源码完整验证

| 收据 / 日志 | PID / 耗时 | 实际结果 |
| --- | --- | --- |
| author-v2-regression-r2-command.json / .log | 9072 / 11818.742ms | 六文件 **158/158**，G4 26 + 既有132 |
| author-v2-types-r2-command.json / .log | 14152 / 7455.414ms | 直接 `tsc --noEmit --incremental false -p apps/web/tsconfig.json` 通过 |
| author-v2-lint-r2-command.json / .log | 6112 / 2128.723ms | 两个授权文件 lint 0 警告 |

三轮分别绑定最终两个授权文件及 QA 实际 SHA，18 个监测源/QA/共享文件前后零漂移，42 个 v1 edit 原件前后零漂移；所有子进程与日志已关闭。完整 argv、cwd、开始时间、PID、持续时间与逐文件前后 SHA 见 RESULT-v2.json 收据。

首次直接类型检查 **author-v2-types-r1** 为10条新增测试 TS2769：误把 Playwright 的 `exact` 选项用于 Testing Library ByRoleOptions。只去掉新增的不支持选项；RTL 字符串 name 的精确匹配与所有行为断言保留。原 log、command 与两源 txt 在 `first-v2-types-r1/` 保留。首轮回归158/158与lint通过仅为诊断，最终结果使用修正 QA 后完整新轮158/158和最终类型/lint，不拼绿或转签首轮源码。

## 精确重跑命令

从仓库根目录执行（bundled Node 绝对路径见 command JSON；单位测试要求 NODE_OPTIONS）：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
node node_modules/vitest/vitest.mjs run apps/web/src/features/lesson-plan/g4-recovery.test.tsx apps/web/src/features/lesson-plan/model/server-session.test.tsx apps/web/src/features/lesson-plan/model/lesson-operation.test.tsx apps/web/src/features/lesson-plan/model/g3-persistence.test.tsx apps/web/src/features/lesson-plan/g3-history-copy.test.tsx apps/web/src/features/lesson-plan/lesson-workspace.test.tsx --reporter=verbose
node node_modules/typescript/bin/tsc --noEmit --incremental false -p apps/web/tsconfig.json
node node_modules/eslint/bin/eslint.js apps/web/src/features/lesson-plan/model/useServerPersistence.ts apps/web/src/features/lesson-plan/g4-recovery.test.tsx --max-warnings=0
```

可用 `edit/run_author_v2.py <新标签> regression|types|lint` 生成独立收据，旧标签拒绝覆盖。Next typegen/build、完整 check、独立技术及真实浏览器新整轮**未执行**，由 ROOT 后置执行；不得据本卡关闭 G4。作者未导入 app.main、读取 .env 或正式数据、操作服务/用户进程、调用模型、修改 ROOT QA 或 Git；隔离样本与旧首败未删除。

## STOP 字节

| 文件 | SHA256 |
| --- | --- |
| `apps/web/src/features/lesson-plan/model/useServerPersistence.ts` | `32f52f32aa5d213ac9fb9d21541a566e531d580b4640619c357833ef79e36a21` |
| `apps/web/src/features/lesson-plan/g4-recovery.test.tsx` | `4cb6c55ddb29c8cb2c1cd2fa31668da0ca38554e67cbe8853ecc523a23c76e71` |

产品和测试已 STOP。作者只交付可独立验收候选，等待 ROOT 冻结、构建及 V00/browser 新整轮结果。
