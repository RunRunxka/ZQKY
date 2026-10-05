# V00-P v1 独立产品行为结果

2026-10-05；负责人 g4_v00_product。**稳定候选的独立组件第三完整单轮 38/38 PASS，exit 0；本卡仅签 G4-E/S 产品正确行为及 ROOT 恢复阻断接线，不关闭 G4/B7 整体。** 未修改产品、旧 QA、权威文档或 Git。

候选 [CANDIDATE-G4-built-r3-qa](../../CANDIDATE-G4-built-r3-qa.json)，SHA `c0867d4e97b1097ee88c63f81f48491a238c1411fb3def8f122cca7a7b2d3bae`；956 源码、33 共享契约、970 active production 构建以及本目录7个准备文件在该轮前后均0差异。构建 `cIUfoiJQX6Dhw7umsfyyW`；不把 jsdom 测试当作此构建的真实浏览器。共享源码仍是三次 QA 候选的完全相同字节，r2/r3 只有明确记录的 QA 修正。

## 实际执行及首败

| 单独完整轮 | 实际事实 | 分类与保留 |
| --- | --- | --- |
| first | PID17148，386.881ms，exit1，0 tests；源码/契约/构建/自身QA0漂移 | Windows path.resolve 生成反斜杠绝对 glob，Vitest 未找到文件。仅 config.include 一行改为正斜杠相对 glob；[首轮日志](first/run.log)、[命令](first/command.json)、[原配置](first/vitest.config.ts.txt)保持 |
| second | PID10596，8634.995ms，exit1，38中35pass/3fail，0skip/todo；前后0漂移 | 三个 hook 用例同一错误额外 oracle：成功 ACK 后仍要求 pending 原包。共享 hooks 原契约明确成功2xx自动释放冻结；收到的实际 send 同原包、恢复前0 HTTP等断言已经通过。仅 ACK 后该行改为 pending null 且 phase succeeded，未删发送前/身份/readback断言。[首败日志](second/run.log)、[命令](second/command.json)、[原测试](second/operation-recovery.test.tsx.txt)保持 |
| third | **PID6236，2026-10-05T13:10:55.636307+08:00 → 13:11:04.400854+08:00，8764.69ms，exit0，38/38，0skip/todo/retry** | 同一轮 public14/source14/operation9+generation首次签名1全部通过。[日志](third/run.log)、[命令和前后绑定](third/command.json)、[完整JSON](third/vitest.json)。不拼 first/second 的通过片段 |

实际命令由独立 `run_independent.py` 调用项目 Vitest；Node24.19.0、Vitest3.2.4、`NODE_OPTIONS=--no-experimental-webstorage`、`--no-cache`、retry0。runner 使用显式候选与新label，拒绝覆盖结果目录；标准库 SHA 检查不导入应用。第三 log SHA `4d70a4c96d86ea5f84b2e7a3df9b9f2d504a7f89b12b564a7717ea750fb25bb6`，JSON SHA `4839cd370f904f093859de91ea0d0438b206c0dfd3137e83026ed62b15bfbd8a`。所有运行、退出子进程、完整原命令及文件散列在 [RESULT-v1.json](RESULT-v1.json) 绑定。

## 签收的正确行为

公共实际 LessonPlanWorkspace 14例只点击公开 UI 来发送/恢复/离开，注入独立 Map Storage 与手写 API 替身。临时 quota、离开对话框恢复、持续失败、静默丢写读回不一致、发送前 frozen save、unknown 原包重放、known ACK 清理、较新 CAS、坏 JSON/读异常、跨文档迟交全部通过。完整11字段与非空两段 secondary、context/source、edit/ACK/CAS、四类 operations均独立核。持久化恢复本身0保存调用；随后仅显式保存；ACK 清理不重复调用。

create/import 发送前写失败发布 recoveryBlocked，三种离开写决策都禁用。恢复先读回同 submissionId/payload/metadata 再解除同身份写阻断；显式重试才发送。明确 create ACK 清理失败保持离开阻断，恢复清理后打开已创建文档且总创建调用仍1，完整 legacy 字节保持。

SourcePanel 14例覆盖 getSource/verify 两阶段×null/非空清除、双清除、两类迟到错误、新核验先到、题库在途 owner、metadata在途 owner、年级/版本、discard、跨文档/store、下一片段参数原语义。清除后旧结果和旧错误均未采用，Q/practice/教师要求保留；新 intent 可采用。明确 clear 没有误取消 Q/metadata reader；discard 原有清题练习语义与明确 clear 区分。

操作接口9例补 generate/apply/reject 的可信冻结包恢复、known ACK 清理、unknown 已发送后再写失败、恢复时出现坏字节与初始坏读取；公开 ProposalPanel 另1例核首次 generation selectionKey/sourceEpoch。恢复期间改变后来的教师要求也不把新签名贴回原操作，原要求和 original submissionId 被实际发送，原签名保持。接口窄例不替代前述公开工作台。

## ROOT 接线与浏览器 oracle 核查

只读评估 `DocumentOperationState.recoveryBlocked?` 保留旧调用兼容；Gateway 以 `!!` 比较/发布规范化状态，pending publisher 的 owner/context/current 与 release 守卫拒绝旧会话更新。LeaveProtection 的 ask/local flush gate/三种决策均覆盖恢复阻断，DocumentsPanel 将 pre-send unsent 与 unknown、known ACK cleanup分开；独立公共14实际核到该接线。

ROOT `v00/browser/g4.spec.ts` 与 `source-clear.spec.ts` 的12条 oracle 已只读核：E四视口/键盘完整缓存恢复、持续失败、原包/unknown/CAS/坏字节；S持有 route.fetch 实际业务响应，明确清除/释放后不带旧证据，随后新生成只带新意图且题/练习保持。曾指出 unknown 仅切 Storage fault 不一定触发写，ROOT已在首次运行前增加真实 pagehide 持久化故障注入；未编辑 ROOT 浏览器文件。本卡**尚未签收其真实运行或截图**，也未执行完整174 E2E、API/恢复/导出/真实模型。

本Agent只用 jsdom 与隔离手写 API/Storage，不开服务/浏览器/网络，不导入 app.main、读 .env/正式草稿或数据库。Node子进程已退出；没有本Agent服务/浏览器资源；全部结果与失败目录保留。真实模型0，teacher_review pending，Word/WPS原生排版not_run，原B6/B7整体/RAG-REL和既有观察保持。ROOT工程检查与其他独立工具/实际浏览器证据分列，不能由本卡代签。

结果卡后新增文档是 post-run delta；原候选、原准备方案、首败、日志与测试输入保持，只由 ROOT 做最终整体保全与 G4关闭判断。V00-P 到此 STOP。
