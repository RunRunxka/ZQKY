# G3-TRACE 原 qa4 最终及 r4→r5 独立复核 v2

时间：2026-10-04T13:24:05.874735+08:00。状态：**R4_FINAL_FAILURE_PRESERVED_R5_DELTA_ACCEPTED_PENDING_FULL_RUN**。保留 `TRACE-READ-v1` 撰写时的现场状态，追加本最终复核，不回改首版。只读核验；没有QA执行、新exec文件或产品/依赖修改。

## 原14最终失败分类

`v00/results/run-g3-r2-qa4/browser-results.json` SHA `9f002406a6f4b00f1e1e9f7c9b08a9a669ea26c0b4c3a833364c86e7d3fd3551`、XML/log/command原件保留。最终14 unexpected timedOut、expected0/skipped0/flaky0；Playwright总714316.541ms。ROOT receipt PID16940、exit1、715061.223ms，receiptSHA `153d42bad81c43090a89e19b3e95001041584bccba5e7052d7a1946426e75e8f`、logSHA `207eaa50001bfed323e4d834616a1c87c1f4b5cb54896c071e39cb9622ecd180`，closed/logSHA/sourceQA前后核对一致。不可将原件写成14通过或有自动重试。

前13每例duration832–4783ms、各仅1个裸 `Test timeout of45000ms exceeded`；结合已安装tracingSlot、same-input Node26阻塞/Node24完整CRC输出及短用例业务事实，归于trace合并终结超时。第14duration45105ms，另有明确 `clock.pauseAt` timeout，定位原 `source-late.spec.ts:115`、publicFullBackup download之后：弃稿/迟到旧GET/1850ms多周期/无PATCH/full11备份等此前断言已过，后续fresh teacher source/newB/save1/revision2控制断言未到，登记未完成。

现场14个最终trace.zip均不能通过Python ZipFile读取/CRC，缺central/EOCD；逐文件SHA在JSON结果保全。现有OS临时Node24离线重组样本CRC通过不等于原14trace.zip被修复，也不替代真实测试重跑。

## r4→r5 精确差异

- 原r4文件保全 `v00/clock-first-source-r4/source-late.spec.ts.original.txt` SHA `94d4dd598e49a4210143a1898d4625e544b40d8636056307d1cab913993031b9`，与r2候选原文件完全相符；manifest绑定。
- 新r5 `v00/browser/source-late.spec.ts` SHA `e3eaa435bf5c63c0145f74bf694f90215fb002430471074bb55438a94004186f`；V00 delta `BROWSER-CLOCK-QA-DELTA-r5.json` 与实际unified diff相符。
- 仅把 control-only `clock.pauseAt(page Date.now()+100)` 从原control分支内（下载后）移至真实1850ms观察及 controls/sourceFooter/cache null/PATCH=[] 检查之后、publicFullBackup之前。后半仍执行原unroute/fresh select reportA/明确KP/newB/手动保存；沒有再调用第二次pauseAt。
- 验收者从旧文本删除原合并行的clock语句、从新文本删除新control-only clock行后，剩余程序文本逐字一致；expect调用文本/次数及所有业务断言没有变化。`g3.spec.ts` 与 `external.config.ts` 仍为原候选字节；14例、trace='on'、0retry未删改。

## 核心oracle保持

旧GET是真实FastAPI响应受控延迟≥1500ms，并非替身返回；读取完成后恢复BASE全控件snapshot/固定来源footer/空恢复键/save0与真实1850ms观察仍在暂停之前。完整11字段公开备份、后台current+history+每个固定revision、两个report与score facts逐项不变继续保留。新operation控制仍在真实Next目标响应延迟保留的页面子树中：重新真实读取报告与全部KP、完整正文仅新标题、cache context/data核对、明确保存等待真实PATCH200、revision2/当前full11/contextA、恰好PATCH1、旧固定revision保持；末尾真实路由目标放行后URL/chat也保持。不把该控制说成导航最终失败或取消。

静态差异可接受，能防下载之后重新pauseAt卡住这一已定位的QA控制问题，实际是否全部完成仍须新runtime绑定下完整14结果。未依据准备态把第14未到的业务断言记已验收。

## 新候选与下一门槛

ROOT新候选 `CANDIDATE-G3-r2-qa5.json` SHA `1ef1756283abc1fda103c2263c3a49034c5d3ffec4f06669c0735488134efcbb`，source941/QA3136/contracts33/build2161；source/build/sharedContracts与r2完全一致。旧候选已映射QA中只有上述source-late文件改变，差异明确归为QA代次；新增执行诊断/ROOT控制文件另由新候选归因，不隐藏作零差。

ROOT已使用现有Node24启动全新run的14例、trace on、0retry；本卡不读正在写入的结果为PASS，不执行或干预。G3关闭还依赖此14例与根153适用浏览器回归完成，以及ROOT综合证据/状态文档。G3-BOUNDARY组件8 PASS不被归档失败推翻，但true-browser G3尚未关闭；B6尚未开始。

完成后STOP：不新增测试/exec文件，不执行QA、不改产品/依赖、不启动/停止服务，等待ROOT完整新运行卡。
