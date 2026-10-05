# G5 后续代码审查与接续安排

2026-10-05，ROOT。现场 `main@b7f99ab09826c68724e281d01e15215e660c1ce0` 加当前未提交工作区。**G5两项原修复保持；新增确认一项P2，尚未修复。** 本次为产品只读审查、隔离窄验证和下一批提示词编写，不启动G6/B7-B、不Git写入。

## P2 / R-G5-CACHE-01：正常回执可能误删另一标签页的原操作恢复包

位置：[useLessonOperation.ts:61](../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts:61)。创建和导入分别使用固定共享恢复键，见 [DocumentsPanel.tsx:25](../../../apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx:25)。正常明确成功或失败直接 `write(null)`；同文件74行的归属核验只用于清理重试。

独立复现使用两个已完成加载的hook实例、真实browserOperationRecovery和共享隔离Storage。A发起等待回执，B再发起合法新操作，B的完整FrozenSubmission成为该键当前包；A成功或明确422直接清键，B随后网络status0仍为unknown、内存pending正确，但持久包已空。每个发送函数各调用一次，B包经生产validateOperation校验且等于实际发送包。没有伪造不合法缓存或仅让adapter返回异常值。

create/import × success/failure四条保持foreign字节的正确行为断言均失败；同文件四个自有包正常清理对照通过。实际结果是另一未明操作的持久恢复包被删除；刷新后无法从这个键恢复提交身份是由删除事实推导，本轮未实际刷新浏览器。**未证实正文或服务端数据丢失、实际重复HTTP，不扩大影响。** 此问题来自继承的正常清理路径，不重开旧“误跳上一次成功文档”修复。

建议正常ACK与公开重试共用owned-cleanup规则：读取并验证当前字节，只有missing或完整包属于本次outcome才清理；foreign、坏字节或不可读均拒删，保留本次成功/失败回执与现有公开恢复入口。无需新存储架构；读/删仍非跨进程原子CAS，有限修复不能宣称全体标签页竞争已解决。

见 [恢复分项报告](recovery/REVIEW.md)、[完整载荷反例](recovery/full-cache-owner.test.tsx)、[首轮4通过/4失败](recovery/full-cache-owner-first.json)。kind=write恢复可能覆盖foreign的静态观察未独立验证，本轮不计为第二项finding。

## 两项原修复与本次实跑

原R-G4-RECOVERY-01已改为本次cleanupOutcome成功/失败及真实操作身份，DocumentsPanel不再用共享历史result推断本次成功。原R-B7A-QUALITY-01先核CSV完整20列/key/string，再核空人审；Markdown核固定case/title/hash完整模板与210空槽。两原问题在本轮反例与回归中保持修复。

| 本轮验证范围 | 实际结果 | 证据 |
| --- | --- | --- |
| 原错跳反例/控制、G4与G5恢复、server-session/helper六文件，完整窄轮 | 71/71通过 | recovery/regression-first.json |
| 新完整create/import包归属场景，首轮 | 4自有对照通过、4foreign正确行为失败 | recovery/full-cache-owner-first.json |
| 新独立离线工具CLI完整轮 | 18次：4正常、14预期硬拒，全部符合oracle | tools/RESULT-second.json |
| 当前B7-A原材料独立实核 | 273引用、15×20空CSV、210 MD空槽、4native空行及13历史PDF行合格 | tools/CURRENT-PACKAGE.json |

各轮分开计数，不拼成一次全绿。本轮工具未确认新缺陷；两个原假通过输入原字节复制并重锚新的反例SHA，当前分别exit2/INVALID_FEEDBACK_SHAPE、INVALID_FEEDBACK_TEMPLATE，未发布MATERIALS。合法空表/BOM/CRLF/CR及CSV引号内空白换行正确接受。详见 [工具报告](tools/REVIEW.md)。四类网络/app/.env/数据库guard尝试0，子进程/日志已关闭。

恢复generic载荷最初诊断另2失败，完整合法载荷再跑4/4，原件均保留；不把重复诊断增加finding数。工具审查harness首轮误从RESULT读取本在MATERIALS的realModelCalls造成KeyError，属于审查入口错误。只修harness、新label完整18重跑；产品正确行为未改，首败见 tools/FIRST-FAILURE.json。

## 候选与验证边界

[开工散列](BASELINE.json)逐项核当前候选SHA `049ad4057540ba1e2bd6f383c3944bba738ff2e47acd2d1dde542d210506c533`：960源码/3660执行QA/33契约/970构建相符。build `2Gg_WxijBmV9IGIkY1vmG`，next-env SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`，HEAD/分支保持。

独立比较G5 built-r1/r2：源码、契约、整构建完全相同，仅v00/recovery.test.tsx与ctrl/close_receipts.py两QA文件差异。原报告明确check/102CLI/8/174的实际候选及适用转签，本次不将它们称为r2重跑。历史G5的1380单测、152组件、102CLI、8新浏览器及174E2E是原运行事实，本轮没有重跑全套。

本轮开工已有QA46771文件（排除本新审查目录及现行qa索引）；与G5报告“旧QA22207”是不同时间点/范围，不能冒充同一计数。旧QA、原材料、模板、v2任务/伪代码、PLAN/Guide/API/ROUTES及next-env在最终逐项保全。权威状态与索引仅增加当前审查，原字节保留，增量单列。

**本轮未执行**完整check/build/API/E2E、真实浏览器与多页storage事件、真实模型/教师/Word-WPS、物理SQLite/Blob/恢复、Qdrant/正式迁移及压力：本次是只读代码审查，窄hook/组件和离线CLI足以独立验证新反例；不以此替代真实浏览器或教学效果验收。未启动服务、浏览器或模型，未读真实草稿、凭证或正式库，未Git写入，不需要关闭用户进程。

## 下一阶段

[下一批总控提示词](../../design/teaching-loop-v1/B7B_总控启动提示词_20261005.md)已写好，但尚未执行：G6先补正常ACK缓存归属保护，B7-B补一次性受控执行器的离线技术条件；真实调用只在完整明确范围与可执行预算具备后进行。原273材料/15案例/四历史导出继续引用，不再次制作同一准备包。

[试评依赖报告](next/REVIEW.md)核对了现有LessonGenerationService/Resolver/Provider/JobEngine真实入口。当前没有试评总预算账本、发送审计/恢复停止协议；response.usage在生产教案execute中未保留。下一批可通过隔离实例依赖注入捕获与限制，正常无需另造prompt/API/业务表。预算先预留可信上界、记录响应和用量，再在完整合法时结算；未知用量/中断停止余例。同一授权累计额度不能因换run/label清零。这些是B7-B待实现条件，不列为G5已授权范围缺陷。

旧offline汇总器固定fixture具体分钟分配，不能直接判断live输出教学合格。Live按生产结构与固定学情事实核技术，教师按实际输出给理由和评价；填写后的真人表不能交只接受空表的prepare_review。Word/WPS实际版本/原生页码及逐页证据单列，原13PDF页不能替代。RAG-REL及原B6/B7整体、跨批观察、旧被拒额外HTTPprobe和缺物理源仍按原台账保持。

最终保全见 [FINAL-AUDIT.json](FINAL-AUDIT.json)，提示词独立后验见 [next/PROMPT-REVIEW.md](next/PROMPT-REVIEW.md)。本次止于审查和提示词，产品问题仍待修复，未启动下一批。
