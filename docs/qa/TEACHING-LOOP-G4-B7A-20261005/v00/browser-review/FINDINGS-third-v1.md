# G4-BROWSER-REVIEW v1 第三浏览器轮独立诊断

2026-10-05，g4_v00_product。只读产品、ROOT browser、旧材料与权威文档；仅写本目录。**第三完整单轮实际9/11通过、2失败，不能关闭G4，也不能把9例与下一轮拼绿。** 实际是 g4.spec 9例（四视口＋五故障）与 source-clear 2例共11；此前 V00-P 结果卡对尚未运行的浏览器写“12”是数量口误，本独立追加纠正，不追写旧卡或加无意义案例。

稳定候选 `CANDIDATE-G4-built-r5-browser-qa.json` SHA `5c90dee50d9dc05dd97cc77d4cf312adf256a7f3d4c7acbbdd59f95e5499c485`；956 source/33 contracts/970 build 与 r3 完全相同，build `cIUfoiJQX6Dhw7umsfyyW`，next-env 原 SHA0f706…。JSON stats：开始2026-10-05T05:12:36.482Z、duration35894.441ms、expected9/unexpected2、skipped0/flaky0、global errors0。独立逐 ZIP CRC 核11个 trace通过，提取调用/业务网络/快照在 [third-inspection.json](third-inspection.json)，原 JSON/trace/首败均只读。

## BROWSER-E01：真实产品公开恢复入口在发送前缓存失败后保留busy快照

实际工作台在可信完整新稿保存前注入“仅包含 save 原包的 setItem抛 quota”。trace 先填标题、安装真实 Storage.prototype fault，再点击公开保存；请求记录中该文档没有 PATCH，页面实际可见“发送前恢复缓存写入失败，尚未发送HTTP”，完整新输入仍在禁用的正文控件中。公开“重试恢复缓存”按钮已存在，但连续10秒仍 disabled；保存原包与读取后台最新按钮同样disabled。此为用户要求的公开恢复硬失败，不因jsdom38通过而代签。

只读源因定位：useServerPersistence 的 busy 包含 `save.busy || !!running.current || auxiliaryBusy.current`。失败分支执行 setError/setSyncState/notify 时 running.current仍持有本次promise；随后 finally 只清引用、没有发布一次状态更新。ServerControls由返回的busy快照禁用恢复和刷新按钮。真实浏览器可在finally前完成渲染，引用变false没有自动触发新渲染；jsdom act合并微任务并不能证明该生命周期条件已覆盖。快照本身未直接读私有exclusive字段，因此不能将失败仅称exclusive未释放；本轮直接证明的是公开busy相关控件持续禁用。

最小可写方向：仅本次promise仍为 running.current 时，finally清引用后以已有 mounted通知发布结束；不得无条件解锁readBlocked/unknown/exclusive，不清原包、不新建submissionId、CAS/ACK/正文保持。作者先形成STOP；全新check/build后，同一个原浏览器pre-send oracle必须完整通过，并核HTTP0→恢复读回同包→显式一次重放、完整正文/历史+1。原独立38及全部11也须新整轮，不能引用旧38作为新产品已验。

原证据：`../browser/g4-browser-third/g4-G4-E-pre-send-save-pack-242f1-fter-whole-cache-is-durable/error-context.md`；对应trace.zip；`../../ctrl/g4-browser-third.log` 第6例。本诊断不修产品。

## BROWSER-QA02：活会话注入坏字节后reload未证明新页读到了坏缓存

原QA先在已经运行的正常工作台 `localStorage.setItem(cacheKey,bad)`，约5ms后 reload；trace记录该注入和reload，reload后真实GET同文档均200，最终snapshot是“后台稿已保存”，没有“恢复缓存读取失败”。当前源码现有pagehide会 persist可信内存缓存。因此旧页离开时可把测试刚写的坏raw重新覆盖为当前可信包，新页读有效包并进入saved符合此设置。

该解释由注入时序、现有pagehide源码和最终saved快照支持；本trace没有直接记录pagehide之后的storage raw，故不把假设写成已捕捉坏raw被覆盖的逐字节事实，也不能由此宣称产品已经通过坏缓存边界。它尚未到达“新会话首次读取坏缓存”的必要前置条件。

QA最小方向：将坏字节注入新页init，在旧页pagehide完成之后、React首次cache读取之前写入；记录实际坏raw、坏读取可见错误、原raw最终不变、正文/恢复按钮阻断、该文档零保存请求及真实后台/历史全JSON不变。保留原失败设置/首败，不改产品现有lifecycle保存语义。独立jsdom初始坏读已通过只属于组件替身，不代替这例浏览器。

原证据：`../browser/g4-browser-third/g4-G4-E-corrupt-original-c-cb5c1-bytes-are-never-overwritten/error-context.md`；对应trace.zip；third-inspection 的evaluateExpression/reload与业务网络。

## 隔离、其他成功例与后续

API自有8001新TEMP先设置 ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8，Settings.credentials_file=None 后才导入app.main；四库均在该TEMP。seed raw SHA252f3dc8…与bound build一致。真实业务FastAPI、Next代理8001；只有生产Provider/RAG的HTTP Transport手写替身，live0，不能把两个真实生成请求称真实模型。服务只读收据明确旧被拒额外HTTP身份probe未运行。ROOT通知已按PID/出生/命令关闭自有5174/8001，TEMP保留；最终零监听资源后验由ROOT另签，本Agent未开/停任何服务。

第三轮其他9例实际通过，但本卡只做失败诊断，不将其图/数据代签整体通过。四视口及source two的完整附件还应在新全部11成功后独立核：全11字段/secondary/context/source、固定历史与计数、持有真实教材响应、取消源0生成与随后新源生成payload、8张恢复/焦点PNG。教师/WPS待验、live0、RAG-REL及原B6/B7整体状态保持。

原 first ESM __dirname 与 second worker重新加载输出目录保护均为准备/收集失败；各原命令/日志只读保留。third是首个实际11业务整轮，不能把前两轮称产品反例。当前结论FAIL；等待产品最小补修及QA设置分别新冻结后复验。
