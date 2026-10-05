# B4-R20-INDEPENDENT-STATIC v1

2026-10-03，独立审查者 `/root/g1_resume_browser`。候选 r20 SHA `fd6c32fb69d215c8d4cb5a36ceb9fa94253c0afedc248974257cdc636bd5b267`。

结论：**STATIC_READY_FOR_CTRL_RUNTIME_GATE_RELEASE**。r19 附件异常覆盖主体首败的静态红项已关闭，没有新增静态阻断。CTRL 可按当前卡显式放行实际门禁；本报告没有运行或通过业务门禁，B4 未关闭。

| 前后实际逐文件核验 | 结果 |
| --- | --- |
| 当前 source / executable QA / contracts / build | 879 / 53 / 5 / 2007，全部 SHA 零漂移 |
| 历史 protected / today prior | 3043 / 85，全部 SHA 零漂移 |
| 原 FE / 后端业务共同源 / T70 作者 | 451 / 367 / 14，全部相同；API AGENTS 文档差异仍明确排除 |
| 旧 QA / 原 1150 / 原构建 | 45 / 1150 / 2007，同原 SHA |
| 分支 / HEAD / next-env | main / `6aeb57280f6a7e0d7391cad4d150745479ea58ec` / 296 字节原件精确相同 |
| 构建 / actual rewrite | `Ji-Jz8X9yY2R_79JOPivD` / manifest 实际 8001 代理，与冻结值相同 |

r19→r20 产品、契约、全部构建字节相同；可执行 QA 清单不增减，仅两项 SHA 变化。r19 prior 原 64 项未改，新 r20 明示 85 项。两份修前原件 SHA 均等于 r19 清单的对应文件。

`b4-root/candidate.py` 仅扩展 freeze 的 prior 选择：收集全批 TXT，将 qa-types/qa-lint 前缀扩大到全部已完成收据，增加 GUARD-OUTPUT 收据；freeze 回显增加 priorDailyCount。Python AST 证明整个 audit else 分支及 freeze 外全部 AST 精确相同；baseline/next-env/manifest/count/旧与今日保护硬绑定没有改动。

`b4-v00-e2e/r14-recovery.spec.ts` 只将原附件 await 放入 try/catch，把附件或 JSON/Buffer 生成异常加入已有 cleanupFailures。已有主体失败时，原 catch 的 throw 保持，finally 不执行成功路径的清理断言，附件异常不能替代主体首败；无主体失败时，原 `expect(cleanupFailures).toEqual([])` 仍使附件失败如实失败。

独立 installed TypeScript AST 实际核验：两个标题、原 61 行包含 expect 的源码、60 个 matcher 全文逐项精确相同。将新增 try/catch 换回原 await 后，整个模块字节精确还原 r19，SHA `6ca6f9281f1e1e13861db15c85c860a126c5d7ca1e23557b5b92e9b4287777a8`；新 P SHA `b91844519626705be87c6ac6dcf9c6deae91d40bb144589799f2346faeadfc79`。没有业务 UI/操作/预算/helper 改动，未执行附件故障注入。

原 49/目标九个 matcher、六个标题、其他五个 callback、模块其他范围、目标预算、second.close 与 helper 业务深审，精确绑定保留的 r19 独立报告，未重复分析或冒称今日重跑。r19 MD/JSON SHA 仍分别为 `b75aeb5356165016d42370faa80132a9a0f96b0d8de09ae12d059861a2dac34f` / `1549f66c3d48f9458c6f80f74f0a0550b6c682aac7f61c4350244a5b03a9f5d2`，首次静态红项原样保留。

run_check/stream/keep/三 external config 与 r19 同 SHA，原隔离/协议/finally/输出唯一性/自有句柄异常收尾结论继续适用。三执行卡 v1.2 指向 r20、要求已审 launcher，均明确准备不是执行结果。API1698、P64、T70A8、check1110 和第六 B4 浏览器继续保留各自实际历史候选/收据；本轮不重新测这些业务。

实际 inline Python pre 核验 exit0 / 1614.516ms；窄 TypeScript AST exit0 / 23.6619ms；post 散列 exit0 / 893.796ms。全部 argv、前后逐文件 SHA、候选共同清单、两份完整 diff 和静态语义留 JSON。

未执行测试/collect/build/browser/HTTP/service/app，不读 formal env/data，不操作进程或创建可执行 QA；只写本报告 MD/JSON。静态收口后停写，等待 CTRL 明确下一门禁。
