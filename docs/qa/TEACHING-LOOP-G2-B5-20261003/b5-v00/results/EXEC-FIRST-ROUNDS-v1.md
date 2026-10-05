# B5-V00 首轮结果卡 EXEC v1

独立首轮未通过。三个轮次分别保留，不拼接为一轮全绿。

| 轮次 | Candidate SHA | actual | PID / exit / ms |
| --- | --- | --- | --- |
| v3 API42 | eeab0e2f6f58ea982d4ea9e1556fa43569061e79e4a42ba10d30dcb0d17c0246 | 42 passed，0 failed/error/skipped | 20076 / 0 / 40948.122 |
| v3 unit15 | 同上 | 11 passed，4 failed，0 pending/todo | 8056 / 1 / 6458.522 |
| v4 unit16 | 5700383f93f4df0cf0ae4c2dfc4aec10bfdf38042e815941a04c051f15223aa8 | 14 passed，2 failed，0 pending/todo | 26248 / 1 / 3292.472 |

v3 的三例 unknown 失败来自独立 fixture 漏必填 `LessonProposalView.jobId`，属于 QA 错误；v4 只补该字段，保留全部原断言，三例实际通过。原 v3 全部字节与失败 JSON 保留。

v4 两例产品失败均保留。R04：有效旧 M1 候选勾选字段，来源切 M2 后先确认旧候选 stale/采用禁用，再发新 M2；明确 422 失败后 stale/disabled/APIapply0 的联合正确行为 oracle 失败。JSON reporter 未输出实际标量向量，本卡不补造其各值。503 分支因首个 422 断言终止而未执行。R05：241 班级场景中 `后页真实班` option 缺失；完整失败 DOM 仍有首100班与 `class-240` ID 回退、ready=false。未放宽后页选择、完整分页与 ≤200 断言。

完整命令、隔离 env、输入/receipt/log/XML/JSON SHA、逐测试状态和时长在 `EXEC-prebuild-first-rounds-v1.json`。API pytest XML 为42例、40.552秒；runner 总时间另计。每轮 source938 前后 exact candidate、零变化；两轮 unit 的 QA1890/1892 前后 exact candidate、零变化。API runner 只记录 source；QA 已有独立启动前 preflight，本卡不虚构 API 结束时全局 QA 快照。v1–v4 自身清单各字节只读复核无变化。

资源与输入保全：三个独占新 label 的全部原 log、XML/JSON、sampleRoot 均保留。unit receipt 确认 childClosed/logsClosed；API run 已退出、日志关闭，TestClient/Scene finally 关闭连接并恢复 transport，未启动 TCP。API 用真实4DB/业务HTTP与生产 Rag，模型仅孤立传输替身；unit 使用真实 Provider/Panel 的注入能力接口，不能称真实网络浏览器。

明确未执行：8 个真实 browser、真实 Next 导航/四视口图片/trace，等待 CTRL 新构建与隔离8001/5174；独立 backup/restore 重跑，当前另做作者收据与保留样本直接 SQL 的只读审计；独立 check/build/fullAPI 由 CTRL 所有，不纳入本卡自己的执行次数。无产品、原 QA、Git、正式数据或凭证写入。

结论：向 CTRL 报告两项产品首败后停止执行和 frozen QA 写入；v5 新增准备另有明确授权，修后必须绑定新候选重新跑完整入口。
