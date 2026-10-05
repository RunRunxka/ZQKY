# 后端与独立证据共同来源绑定准备 v1

状态：**共同源已核，最终前端/构建身份待新候选**。r12 候选 `CANDIDATE-b4-r12-ui-fixed.json` SHA256 `07a8900807a6cd58c4a5231c2f9dc0bfabd034bd7ea4366644617de4a28cfc54`（878 产品/43 QA/5 契约）与 r9/r10 产品差异严格为 LearningAnalysisWorkspace、其原单测、styles.css 三份前端文件。具体差异已在保留的 R11-R12-STATIC-REVIEW 收口；本报告没有读取或扫描变化中的 .next。

apps/api 全部源码/测试/后端夹具及 tests/fixtures 8 个原件合计 **368 项**，与 r9、r10 和当前实际字节逐一完全一致，0 漂移。43 执行 QA 当前 0 漂移且精确同 r11，全部5共享契约同 r9/r10；P 原4执行源同实际 r10，A 原4执行源同实际 r2。QA 新增 R11 诊断范围明确，不改变原后端验收集合。

CTRL 实际 r9 全 API 1698pass/1skip/exit0 原完整日志 SHA 与命令收据相符。P 实际 r10 owner-fixed-second 全64 pass、exit0，PID 实际退出、两个流关闭与日志独占读取证据完整；四 QA 执行源/全部当前后端与此原版本精确同源。独立 A 实际 r2 的8场景/165HTTP/exit0，全20k/100分页原结果保留；T70 作者14项与原作者/r2/r12实际字节精确同源，Analysis 运行路径的 owner 与源读取保持不变。上述证据均保留各自**原执行候选**，不是重新标成在 r12 执行，也不是本 Agent 新测。

root 通知 r12 check-ui-fixed-first 实际 exit1：typecheck 通过、lint 缺 resource 依赖警告，unit/build 未执行，next-env 已恢复。该首敗原文件散列已登记。root 正独占进行 stable reloadReport 解构的最小 lint 适配，将另冻结/构建。最终前端源、构建identity和前后审计必须在收到新 BUILD-IDENTITY 与停写通知后核查；本准备报告不替代这些步骤，旧构建不可充当新前端修改的验收。

仅写此准备 MD/JSON；未 .next/build 文件读取、未 app.main/test/collect/HTTP/service/data/Git 动作，也未改产品或可执行 QA。等待 CTRL 的新候选/构建身份。
