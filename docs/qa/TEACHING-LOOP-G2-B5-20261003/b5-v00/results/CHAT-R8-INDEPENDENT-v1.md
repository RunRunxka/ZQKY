# B5-V00 CHAT r8 independent v1

独立接收原两 spec **14/14 功能单轮**。26原 PNG 已全部实际view、前后SHA0；CV01–03观察保留，**不宣称全视觉PASS**。V00只读离线，没有起停服务、重跑或新HTTP。

Candidate `c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007`；938source / 3061QA / 33frozen / 2004build，新build `FVU-OXmtBh9WBSHehixfE`。固定Node24、`b5-chat.external.config.ts`继承原config，原两spec/body/断言/预算未改。PID29548、exit0、42953.884ms；stats42195.064ms，14expected / 0skip / 0unexpected / 0flaky；每例1attempt、retry0、workers1、原45s/expect10s。性能case原单expect180s保留，test整体仍45s。

| 原title | actual ms | attempt/status |
|---|---:|---|
| 教学问答模型 经真实代理在最后分块释放前显示中文 | 1053 | 1 / passed / retry0 |
| Responses 模型 经真实代理在最后分块释放前显示中文 | 859 | 1 / passed / retry0 |
| Anthropic 模型 经真实代理在最后分块释放前显示中文 | 865 | 1 / passed / retry0 |
| 停止关闭实际上游，新会话无晚到文本 | 830 | 1 / passed / retry0 |
| 长回答 Markdown 公式与响应式布局 | 1061 | 1 / passed / retry0 |
| 模型发现追加、默认模型同步、表单冲突保留 | 1797 | 1 / passed / retry0 |
| 教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常 | 1982 | 1 / passed / retry0 |
| Responses 模型：推理先显示，正文出现后折叠，公式与恢复正常 | 2017 | 1 / passed / retry0 |
| Anthropic 模型：推理先显示，正文出现后折叠，公式与恢复正常 | 2084 | 1 / passed / retry0 |
| 正文公式：text.delta 原文逐字保留并在流中、终态及刷新后渲染 | 2052 | 1 / passed / retry0 |
| 正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占 | 7457 | 1 / passed / retry0 |
| 性能：20k 推理 + 正文公式受控流 | 5129 | 1 / passed / retry0 |
| 性能：50k 推理 + 正文公式受控流 | 6162 | 1 / passed / retry0 |
| 推理滚动：流式跟随、主动上滚暂停与回到底部恢复 | 7271 | 1 / passed / retry0 |

原完整运行覆盖三协议中文首块在最后释放前可见、真实upstream取消及新会话无晚到字；推理先展开→正文自动折叠→教师重开→完成保留→刷新恢复；流中已闭合公式/美元代码/未闭合raw、终态与恢复公式；text.delta逐字串及IndexedDB等值；正文后继续推理、手动上滚暂停/回底恢复；模型发现只追加、默认同步、revision冲突保留输入、刷新状态和1440/1024/390不溢出。以实际原case终态和完整源断言为证，不从PNG推断交互。原trace策略retain-on-failure，本轮pass不留trace，未为补trace另跑。

| 受控样本 | rendered chars | firstVisible ms | P50/P95/Max ms | frames / >50 / longTasks | raw streamMs |
|---|---:|---:|---|---|---|
|20k|21020|61|5.6 / 5.7 / 38.9|769 / 0 / 0|2.937|
|50k|52568|60.5|5.6 / 5.7 / 38.9|943 / 0 / 0|4.39|

两样本KaTeX80/errors0。仅本机受控一次采样；没有SLO阈值或付费provider表现结论。原fixture first/last是monotonic秒，原公式round((last-first)*1000)/1000仍是秒；字段名streamMs原样保留，不把2.937/4.39解释成毫秒。实际scroll日志保留18个不中断样本gap0/latestText true，用户暂停top123/gap169，恢复top292/gap0，正文后跟随gap0。

26张原图观察见CHAT-R8-VISUAL-v1.md/json：CV01手机“回到最新”遮代码字形、CV02设置空方框/灰色开关、CV03首段流中箭头/方形图形差异仍可见；只描述像素，不关闭交互台账。流中未闭合raw与终态/恢复渲染另列CV04。“reasoning-post-answer-paused”文件实际在47行恢复跟随之后拍摄，文件名不充当暂停oracle。

938/3061/33/2004、原v9 201件/原v11 221件SHA全部0漂移；runner源QA前后0、原logSHA exact、child/log closed，runner新TEMP保留。原两spec14所有输入/原图保持原样。

ROOT stream6564 server/watcher closed、ownedrunner18956 exit0、child/log closed、fixture样本保留。ROOT frontend manager26832/node4152 child/logclosed；child exit1来自受控Windows owned handle终止，非test失败。ROOT既有资源收据确认10services closed、182引用TEMP全部保留、5174/8001/8002无listener且无owned process；V00没有另查端口或起停。V00全部SQLite连接和文件handles已关闭。

原full153的本轮153/153由另一个独立reviewer核，V00不重复、不拼绿。新paidprovider/正式Qdrant、新额外身份HTTP（r2政策拒绝未重试）、all visualPASS、全面性能结论均not_run。

所有15汇总条件PASS，首败无；完整JSON/log、26原图及模型fixture/TEMP保留。证据与逐项SHA见CHAT-R8-INDEPENDENT-v1.json。**STOP：全部可执行QA/产品/HTTP/浏览器/SQLite/文件写入结束；仅后续正式卡允许新的nonexec核文档。**
