# B5-R06-STATIC v1 · FE v4 稳定源码只读审查

结论：未确认新 P1/P2。迟到来源回调擦除教师新模型的已知原因在本次两文件源码中已移除。此为静态结论，不关闭 R06 或 B5。

审查者 `/root/b5_r06_review` 未参与实现、作者测试或独立可执行 QA。先读根/前端/教案 AGENTS、模块 README、用户原请求与 v4 卡，收到 FE STOP 后才读稳定产品 delta。唯一写入为本报告及同名 JSON；没有运行测试、产品、HTTP、SQL、服务、浏览器、模型或 Git，未读正式数据/凭证。

FE STOP：`2026-10-03T11:59:28.741973+00:00`。审查终点：`2026-10-03T12:04:00.047745+00:00`。参照 B5-r2 SHA `7800205803341a8e737e8d8ee7c0659bd6c264f78f72ce5e4f312ad3f39c5bec`；授权产品 delta 仅 SourcePanel 与 lesson-workspace.test。ROOT 后续新候选/check/build/browser 并非本报告执行范围。

## 静态核对

| 范围 | 稳定源码与判断 |
| --- | --- |
| 教师输入 | SourcePanel:27 的 `changeInputs` 在父 onChange 前同步 patch 最新 ref，只改明确给出的 fields。模型/分钟/要求/题/练习都经此入口，不再从旧异步闭包展开整份 value。 |
| 迟到采用 | load:61/selectRun:73 在原 alive/epoch/完整分页检查之后读取最新 selection；updateSelection:33 合并最新 inputs。同一报告重读保留当前仍合法 KP，真正换报告不默认沿用旧 KP。 |
| 来源失效 | updateSelection:34–37 意义比较：class/KP/subject/context 真变化清教材证据；subject 变化清固定题；analysis run 变化清固定练习。同来源合法重读保留现有证据/题/练习，教师 model/requirements/duration 始终来自最新值。ready/同 subject/目标 class/固定 KP 过滤保留。 |
| 分页及卸载 | readPages 本体与修前逐行相同：limit200、完整页、offset/total/空页/总数变化/不一致拒绝，四路仍共用；alive cleanup 增 epoch，各 async token 守卫、失败显示及选择变更增 epoch 保留，没有失败当空库采用。 |
| 核验过期 | verifySlice:88–99 保留固定 revision/范围、6段/16000字、captured 完整 selection/value 签名、alive/epoch；成功仅 patch evidence。教师输入变化后的迟到核验结果仍不采用。 |
| R04 | ProposalPanel SHA 仍 `8cf4d6b9be01348425ba3b71b5c188e3c980d04baadb1f18b65579675f96e02b`，原 accepted GET 首次 metadata/job/sourceEpoch 克隆及 stale 检查未变。M2 不再被来源回调倒退为 M1，旧候选仍由输入 epoch/signature 失效。 |

这些源码判断不能替代服务装配、真实时序或独立正确行为。

## 作者已有单轮证据（仅读取，未重跑）

修前完整106：101 pass / 5 fail / 0 pending，exit1，11466.86ms。五处先失败在真实模型 DOM（初次读取变空、三种同来源刷新与已选择旧候选时变回旧M1），各例后续分钟/要求等断言尚未执行。原首败/输入/log/JSON保持，不写成106个正确行为通过。

修后完整106/106，exit0，PID480，11399.79ms；typecheck exit0/PID5228/1837.024ms；lint exit0/PID6208/3354.146ms。实际 log/JSON计数及SHA与收据一致，源before/after相同；child/log closed、TEMP retained与原收据相符。作者测试只新增 import 与文件末尾11场景，旧95场景行内容无删除/改写；修前106和修后106的 QA SHA相同，只有产品 SourcePanel 改动，没有调作者断言获取通过。

## 独立 v7 QA 静态检查

新 late-source-input 用真实 SourcePanel UI、手写DTO和独立预期，不调用产品merge作oracle：pending A时改M2/61/要求，release A保持；pending B时改M1/74/新要求，release B保持，同时清旧证据/练习/KP、同科题保持，明确勾B KP后ready。unit config保留旧18新增1，10000ms预算保留。

完整8 browser没有把模型选择搬到来源等待之后、没有reselect掩盖R06；只增加教材verify真实POST200/固定revision和范围/已采用UI证据等待后再读取题，history clock.install提前到首次JSON下载前，dirty pause仍在初始完整正文确认后。原业务断言、完整8与原预算/零retry保留。这仅说明静态可接受，独立19/8和新check/build/153/14仍须ROOT/V00实际另证。

## 绑定与保全

2026-10-03T12:01:28.532813Z 实测938源相对r2只有授权两件差异；43作者私有源、33冻结、104 v7 QA、1946作者登记前序证据均零漂移。稳定读取观察的两件SHA与终点一致，终点其余937（除next-env生成项）也未见未授权漂移。

写报告前的全938 guard曾仅遇ROOT build临时生成next-env SHA `1862ac4bbbc5192d4bf562161df66ea547ed3e67173100656ab606ae9797db2b`，先停止写报告并向ROOT报告；没有修改next-env或任何产品。终点 next-env 仍是 ROOT 构建中的临时生成字节，实际 1862ac4bbbc5192d4bf562161df66ea547ed3e67173100656ab606ae9797db2b；恢复后保全由 ROOT 另核，本审查不宣称938全零。 原字节恢复与新构建质量不是本审查执行门禁。

| 证据 | SHA256 |
| --- | --- |
| FE RESULT-v4 | `c132a4db56b3f18bead40dd564b2685f5a8ae28a30fe8ac511612751431cb4c0` |
| FE PRIVATE-MANIFEST-v4 | `92f5b631d0e349a4c6960c5ac39f2484b922698c391d3d54e9bca0c6516b683b` |
| SourcePanel | `66c816abe01e12b680eed2776723e979d2bf184c87de4daff45bf2971a151337` |
| lesson-workspace.test | `138f73415291003b670d8687351c40369ed496d8e22b576666adc04622629f8d` |
| QA-MANIFEST-v7 | `a27778af31d750ac67d64a8fbcbd4884aa703bb76441b886c6ad79329e016555` |

下一动作：ROOT/V00在新稳定候选上完成独立迟到来源正确行为及全部适用门禁；本报告不作R06/B5关闭批准。
