# G4 / B7-A 后续代码审查

2026-10-05，ROOT。审查现场为 `main@b7f99ab09826c68724e281d01e15215e660c1ce0` 加当前未提交 G4/B7-A 工作区。本轮**发现两项 P2，未修改产品，修复尚未执行**。原 G4 四项限定技术关闭、B7-A 正常材料及历史收据保留；原 B6/B7 整体、真实模型质量、教师评价和 Word/WPS 仍未关闭。

## 1. P2 / R-G4-RECOVERY-01：第二次失败后的缓存清理误用第一次成功结果

位置：[DocumentsPanel.tsx:66](../../../apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx:66)，相关导航在70行；根因辅助位置 [useLessonOperation.ts:51](../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts:51) 与共享 [hooks.ts:291](../../../apps/web/src/features/assessments/hooks.ts:291)。

实际复现：打开当前后台教案，创建请求等待期间继续编辑；第一次创建成功后取消离开。第二次创建明确422，操作缓存删除暂时失败；点击“重试创建操作恢复缓存”，实际跳转到**第一次**创建的 `first-created` 文档。正确行为应仅清理第二次失败包，保持当前文档与正文，不再调用创建。

`cleanup` 同时用于明确成功和明确失败，但 `operation.result` 是跨请求保留的最后一次成功值。新请求/失败没有清除此值，因此恢复入口不能据它推断本次成功。清理失败记录应保存本次操作身份和成功/失败类型；仅本次成功 receipt 才能触发相应打开，且继续经过原有离开保护。默认无需改变共享 hook 在其他模块保留 result 的语义。

实际独立组件反例首跑失败，精确记录一次错误 `router.push('/lesson-plans?lessonPlanId=first-created')`；创建次数仍为2。**未证实正文丢失或重复HTTP，不扩大影响。** 同 helper 用于导入，下一批须补导入两操作反例；本轮没有独立复现导入版本。

见 [恢复分项审查](recovery/REVIEW.md)、[正确行为反例](recovery/stale-ack.test.tsx)、[原首败](recovery/stale-ack-first.log)。首次成功/首次明确失败的两个独立清理对照通过，说明缺口是连续操作，而非所有缓存恢复均不可用。

## 2. P2 / R-B7A-QUALITY-01：非空评语可被标为“原空人审材料”

位置：[prepare_review.py:79](../../../scripts/teaching-quality/prepare_review.py:79) 至89行、[138行](../../../scripts/teaching-quality/prepare_review.py:138)，相关输出在194/243行。

两条独立路径：

- 合法CSV表头下，C01行末多出一格非空结论。`DictReader` 将其放入 `row[None]`；校验只遍历已知列，漏查额外格。
- CSV仍为空，仅将Markdown中C01的“真人结论：____”填写为结论。Markdown只核路径/SHA，没有核空槽位与案例身份。

两次实际CLI均 `exit0 / OFFLINE_MATERIALS_PREPARED`，仍输出 `humanFieldsFilled=0`；Markdown还被列为 `originalEmptyFeedbackMd`。独立反例复制至新label并明确更新自己的artifact manifest/SHA，以验证内容判据；没有绕过或修改原旧冻结件。已知CSV reviewer列非空的对照正确exit2，原需求矩阵也明确要求非空伪评语失败闭合。

修复应严格核CSV每行完整形状，并核Markdown固定案例/hash与全部人审槽位；空占位可接受，实际评分/身份/时间/理由/建议/结论或未知评语拒绝。只有两个输入均核为空才能发布空材料结论。SHA证明字节身份，不能替代该内容判断。

当前原包经本次独立核查仍合格：273条引用、严格20列×15行原空CSV、15例原空Markdown、四行native空表及13页历史PDF索引均一致。**不推翻正常材料包，不将反例当作真实教师评价发生。** 见 [工具分项审查](tools/REVIEW.md)、[两个失败闭合反例及对照](tools/RESULT.json)、[当前包核查](tools/CURRENT-PACKAGE.json)。

## 本轮实际验证与保全

| 本次执行 | 实际结果 | 证据 |
| --- | --- | --- |
| 原G4恢复与server-session窄回归，单轮 | 37/37通过 | recovery/regression-first.log |
| 独立首次success/首次422清理对照，单轮 | 2/2通过 | recovery/cleanup-controls-first.log |
| 连续两次创建的正确行为反例，首轮 | 1失败，错误导航被捕获 | recovery/stale-ack-first.log |
| 来源、metadata、session、历史复制五文件，完整窄单轮 | 60/60通过，retry0 | sources/vitest.json |
| 新独立工具CLI，31次 | 29次预期一致；2次实际假通过 | tools/RESULT.json |
| 当前离线材料包独立实核 | 273引用/15空表/4native空行/13历史PDF行合格 | tools/CURRENT-PACKAGE.json |

以上分别计数，不拼成一次“全绿”。来源审查未确认新缺陷；显式教材清除的独立verifyIntent、两阶段迟到响应/错误、报告与metadata分离、discard间隔和正常历史复制保持，详见 [来源分项审查](sources/REVIEW.md)。两工具反例都是预先给定拒绝oracle，不将其实际exit0计入通过数。

[开工核对](BASELINE.json)：候选SHA `3a73dd766c2e23e57e5726e157f7ef5ef1efe9a7c5f815429b3774ca24568297`，959源码/3496执行QA/33契约/970构建逐项相符；build `VeOLFBYrp-8v24Yjm-HFi`，next-env `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。本轮开工实际已有QA文件21976项（排除本新审查目录与现行qa索引），不能将原批19169的时间点计数冒充当前总数。原qa在收尾逐项核对，权威文档新增状态与索引单列。

本轮仅新增审查证据、下一批MD提示词和权威状态/索引；不编辑产品/原测试/历史QA/原材料/原模板/v2任务与伪代码/依赖，不Git写入。只读stdlib散列核对与隔离Vitest/工具子进程均已结束；未启动服务、浏览器或模型，不需要释放用户进程。

**本轮未执行**完整check/build/API/E2E、真实浏览器、模型/教师/Word-WPS、物理SQLite/Blob/恢复检查、Qdrant/正式迁移及额外压力：本次为产品只读审查，用窄组件与离线CLI验证新反例。原报告1354单测、174E2E等是历史运行事实，本次不声称重跑。缺源文件、旧被拒额外HTTP身份probe、RAG-REL、R14及原观察均保持各自not_run/OPEN，不将这些待验本身列为代码bug。

来源探针准备时首次写错helpers.tsx路径，Vitest未启动；已在新目录保留原输出，仅修runner路径。此准备错误与上方实际产品失败分开记录。

## 下一批

建议只执行 [G5总控启动提示词](../../design/teaching-loop-v1/G5_总控启动提示词_20261005.md)：两项修复可并行，独立正确行为复验、完整check、新构建浏览器与完整E2E及文档保全后停止。本文与提示词不代表已执行或用户已授权下一批。

G5之后直接承接实际B7-B待验条件，不重复建设离线准备包。真实模型范围、可执行预算及执行器尚未具备；合法preflight不创造授权。教师反馈与原生分页来自真人实际填写/查看，不能由自动化代填或用历史13页PDF替代。原B6/B7整体继续按实际证据推进。

最终逐字节保全及本轮文档增量见 [FINAL-AUDIT.json](FINAL-AUDIT.json)；下一批提示词的独立后验见 [PROMPT-REVIEW.md](sources/PROMPT-REVIEW.md)。
