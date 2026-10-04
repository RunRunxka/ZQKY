# B4 今日门禁矩阵

更新：2026-10-03。G1与B4均已完成独立验收并由CTRL关闭。各轮单独保存，不拼全绿。

| 门禁 | 实际依据 | 今日状态 |
| --- | --- | --- |
| 起点/来源/构建/保全 | r21 879/53/5/2007、3043历史及191今日旧证据 | 前后0漂移；全量已完成，F最终来源/运行/资源绑定通过 |
| R14窄QA适配静态 | 原49断言/6标题/另5case/原预算；仅busy3行删除 | strict type0/725.347ms，lint0/1221.149ms；独立STATIC_READY |
| R14首轮实际 | r20 2attempt/1pass1fail/retry0skip0 | 首败保留，fault后置终态未执行 |
| R14固定后两UI完整新单轮 | r21 2attempt/2pass、0重试/跳过 | 通过，exit0/38236.733ms；正常0/故障1真实Continue，终态/笔记/ID/锁/清理全完成 |
| 原2spec14chat | 14原标题/14attempt、三协议/取消/长内容/公式/推理/滚动 | 通过，exit0/43832.314ms；独立实际核＋26逐图观察保留 |
| 原24spec153case | 原全目录/配置/预算/retry0，新single run b4-e2e-resume-first | 通过：153attempt/153pass，0fail/skip/retry/flaky/errors[]，exit0/371554.846ms |
| 既有B4 T70/T80/浏览器/check/API | 同r17业务/common-source与2007构建，原实际8/64/1/1110/1698+1skip | 历史执行精确绑定；F最终实际运行/资源binding通过，未冒称今日重跑 |
| 最终资源/文档与CTRL关闭 | 当前入口/收据/首败/临时根/PID/日志/实际端口 | P/F最终报告与独立文档窄delta通过；CTRL确认关闭B4 |

用户5174 PID21816继续保留；后续CTRL启动自有测试前端已明确授权，具体审批拒绝不得绕过。跨批R-14不据本次适配验收宣称产品触发根因已修或恒绿；CHAT-VISUAL-v1像素观察不被技术14通过抹掉。范围止B4，不B5/Git写/外部发布。
