# B6-R01 来源并发独立验收 v1

更新时间：2026-10-04T14:52:11.232360+08:00。责任人 g3_v00。**r2 组件行为独立签收；最终新构建门禁待 ROOT 完整复验，本报告不关闭 B6。** 本卡 STOP，独立测试保持原 SHA。

ROOT 实际完整单轮 `b6-r01-independent-eight-r2`：PID16396，2147.018ms，exit0，同一固定八例全部 pass，源及可执行 QA 前后零漂移。本人未重复运行，通过原 command/log SHA、全部八例结果与完整 SourcePanel 源码独立核对。候选 `CANDIDATE-B6-R01-r2.json` SHA `5eb04bd73a5e1ccc9b1f2e2294c240da8cfb9f523a756d54598b5d9a5b91c6d7`，SourcePanel SHA `bb4399c57492ea1a7b96ded0dc79a9f1aab5e648417ea2618fd83aa1aad1d9c8`。本轮身份是后续旧测试两处等待修正之前的 r2；后续新冻结及构建需另签新叶，不能把这轮冒称其运行。

| 案例 | 原正确行为 | 本轮实际 |
| --- | --- | --- |
| S01 | metadata未完成时明确清除报告，模型/分类仍采用并结束loading，旧A不回灌 | pass |
| S02 | metadata先开始，随后新B/KP明确选择，旧metadata不覆盖新意图 | pass |
| S03 | B GET先处于pending，再刷新metadata，后者不得撤销B或重新读取A | pass |
| S04 | 新metadata赢；旧metadata失败不得修改新error/loading | pass |
| S05 | discard撤销旧metadata，保留教师要求/分钟，新会话显式刷新仍可用 | pass |
| S06 | 旧document/store/session的metadata不得写入新owner | pass |
| S07 | 当前metadata失败可见、释放loading、保留输入并允许明确retry | pass |
| S08 | metadata期间教师改要求/分钟完整保持；模型不自动选择 | pass |

独立 QA SHA `ca149188acd9dea30b2ffb544a45497972c8e26ca0c5cfdddb79b887701cfcf8`，配置 SHA `4bce21167586fca40b52835261d3d01054af5b96ca7b526d64fc748694c16a1c`。三次前置结果完整保留：原 r1 PID5720 / 3249.703ms，7pass/1fail(S03)；QA2 PID23012 / 1820.195ms，8例均因不支持 fireEvent.toggle 在 setup 失败，不是业务结论；原断言 QA3 PID25016 / 3221.142ms，真实 open/toggle 后仍7pass/1fail(S03)。首版执行源按精确 helper delta 逆构核对为9b35359…，说明重建时序；QA2原字节为0113e48a…。两版本与旧收据未覆盖，QA delta只修真实details开启动作和支持的toggle事件，八项业务断言保留。

S03 是产品缺陷：已完成A来源之后教师明确B的GET先开始，随后metadata刷新完成；r1仅比较metadata起始source epoch仍相等，会再选择A并撤销B。r2采用独立metadata epoch与唯一pending report owner；metadata起始或完成时存在report intent均不自动回灌，旧report finally仅清自己owner。代码同时保留document/mode/store/session与discard/unmount守卫，新metadata胜旧结果、当前失败释放loading，教师输入使用latest快照。此结论来自完整源与真正S03反例修前失败/修后通过，不来自作者说明。

这些八例是实际SourcePanel配窄Document/Editor Context契约夹具，覆盖公共controls和来源意图，不宣称完整Workspace、恢复cache、历史/CAS或实际FastAPI写计数已由此覆盖。最终新build下同8复跑、真实成功UI/原153及受影响G3门禁正在ROOT准备，尚未在本报告执行。真实模型、真人质量、RAG-REL、Word/WPS排版边界保持。四例原公开导出材料继续绑定q84e且STOP，不改写为后续build新跑。

完整执行命令、候选、逐例与首败 SHA、判定及未执行边界见 [RESULT-v1.json](RESULT-v1.json)。
