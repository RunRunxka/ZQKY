# G2-FE v1 实现与作者自检

2026-10-03，北京时间。**作者自检通过，产品源码已停写，待 CTRL 冻结 G2 候选及独立验收；不宣称关闭 G2。** main@6aeb57280f6a7e0d7391cad4d150745479ea58ec 未变。开工 B4 r21 全分组保全由 CTRL 实核；本结果的实际 11 项源绑定见 [JSON结果](RESULT-v1.json)，其中 8 项是本实现私有文件。

练习建立按 practiceSetId 独立本机恢复会话，发送前同步保存首次操作；读取损坏或缓存写失败均不当空稿覆盖，写失败明确阻止 HTTP。dirty 与 pending/unknown 分开；列表、固定历史、补题及路由分别接入私有离开确认和公共 guard。对话框允许取消、保存成功后离开、保留恢复稿离开、明确放弃；busy/unknown 不能直接放弃。刷新/关闭使用已声明的独立本机恢复稿，unknown 重载不自动发请求。

练习和备注用 CTRL 的 submitWithReceipt，首次 contextKey/editGeneration/loadGeneration 随原包冻结。unknown 重放只确认原操作；在途后分值、结构、约束、备注继续保持。服务器 known 最新版本与教师明确采用的可写 CAS 分离；dirty 读取高版本暂停新逻辑保存/建议/审核，unknown 原包恢复仍可执行。较旧 receipt 及同 CAS 不同固定修订身份都不能推进错误基线、hydrate、清 dirty 或 onSaved。固定身份冲突另存恢复稿并展示可信服务器固定修订对照，采用来源始终是当前可信读取 view，不是旧 receipt。

## 最终实际自检

| 检查 | 完整单轮结果 | 原收据 |
| --- | --- | --- |
| 相关作者单测 | **3 文件 / 32 passed / 0 failed / 0 pending / 0 uncaught，exit0，5051.389ms**；Vitest自身4.53s | [单轮命令](author-identity-fixed-command.json)、[日志](author-identity-fixed.log)、[JSON](author-identity-fixed-results.json) |
| 私有7TS/TSX lint | **0错误/0警告，exit0，2081.198ms** | [命令](author-identity-lint-command.json)、[日志](author-identity-lint.log) |
| 限定源码+测试传递类型检查 | **exit0，1570.459ms**；包含既有 tests/setup.ts matcher声明，非全仓check | [命令](author-identity-types-command.json)、[配置](author-identity-types-tsconfig.json)、[日志](author-identity-types.log) |

每条命令用显式 Node24 和 NODE_OPTIONS=--no-experimental-webstorage；argv/env/PID/UTC/exit/ms/日志SHA及前后11源SHA全部实际记录，三条最终检查源漂移均0。原32用例分别为 G2会话15、既有练习10、学情7；不把静态断言数当执行步数。覆盖首次200、unknown同包2→3/A→B、重复点击、切对象迟到、读高CAS后旧回执、equal固定身份、unknown重新加载、缓存读写失败、列表取消/保留/放弃、历史恢复和409/422/unknown保存后离开失败保上下文。真实补题/公共导航/nativeBack、成功保存后路由切换的浏览器链仍由 V00 执行，本单测不冒称浏览器已验。

## 首败、修复与保全

- 首轮 [author-first](author-first-command.json)：30断言全过但4个 dialog.close uncaught，CLIexit1/5757.419ms；JSONsuccess:true未作为通过依据。修对称关闭能力检查后，独立新label [30例](author-dialog-fixed-command.json) exit0/4872.272ms。原日志/JSON/11份精确首轮源快照保留，[逐SHA清单](author-first-source-manifest.json)。
- [首lint](author-lint-first-command.json) exit1/2768.969ms，1条effect依赖警告；拆稳定方法引用后 [lint0](author-lint-fixed-command.json) exit0/1964.614ms，不压警告。
- [首限定types](author-types-first-command.json) 子tsc exit2/2633.273ms，原因是限定配置漏了既有jest-dom测试声明；加入 tests/setup.ts后 [类型0](author-types-fixed-command.json) exit0/1469.838ms，没有放宽产品类型。
- CTRL静读发现新写未暂停高版本，保存 [修复前原文](PracticeEditor.before-baseline-choice.txt) 与 [SHA归因](baseline-choice-before.json)。补guard后 [32例首轮](author-baseline-fixed-command.json) 31通过1失败/exit1/4988.310ms：equal receipt-vs-known身份冲突已拒绝回填，但缺少专门冲突表示。补持久冲突 metadata/对照和暂停后，最终32例单轮全过；该失败输入 [11源快照SHA](author-baseline-first-source-manifest.json) 全与实际receipt一致，未覆写首败。
- 两次源快照整理曾因CRLF/LF逆向字节不匹配被SHA guard拒绝（共4个只读辅助错误），没有因此修改产品或改预期SHA；最终首轮与baseline首轮各11份均精确匹配实际收据。详见 JSON，未伪造辅助耗时。

12个有限检查子进程均退出并关闭日志；最终4824/18796/15832经CIM读未存在。12个系统临时根均保留，没有创建监听服务、结束用户5174、删除目录、访问正式env/data/真实草稿或Git写操作。原 B4 QA/报告/冻结件没有修改。本批全量check、build、API、独立真实浏览器及适用E2E **未执行**，由CTRL/V00依任务卡集成验收；本实现只标待独立验收，不开始B5。
