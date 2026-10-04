# G2 修复与 B5 教案增量 · 2026-10-03

本批按新授权先完成 G2-R01～R03，独立关闭后才实施 T90/F30。G2已独立关闭，B5共享契约已冻结；BE/AI/FE v2均停写，prebuild候选已冻结，完整check/API及独立API42通过，unit11/4失败，R04/R05残余待窄修；浏览器未执行。R01～05来源、身份与导航问题见[B5集成修复卡](B5-CTRL-FIX-DELTA-v1.md)；旧 B4 关闭、审查、首败和冻结件保持历史原件。

[任务卡](TASK-CARDS.md) · [G2 契约](G2-CONTRACT-v1.md) · [当前报告](REPORT.md) · [G2 矩阵](G2-CLOSE-MATRIX.md) · [B5 矩阵](B5-CLOSE-MATRIX.md) · [开工保全](ctrl/BASELINE.json)。当前唯一进度入口为 [CURRENT_STATUS](../../CURRENT_STATUS.md)。

范围止 B5，不提交、推送、切分支或部署。隔离测试前端由 CTRL 管理；现有用户进程不得结束，具体审批拒绝不绕过。系统临时根登记保留，正式数据、凭证和真实草稿不访问。每日按北京时间增建目录，已完成的运行记录不追改。

2026-10-03 18:38补记：prebuild-v1完整check已结束，118文件/1202单测、类型、零警告lint/build通过，exit0/110566.057ms/PID6308，938源/1890QA前后0，next-env原字节恢复；完整API1918pass/1既有规模skip、exit0/392504.479ms/PID21200，938源0。独立API42/42、exit0/40948.122ms/PID20076；unit首轮11pass/4fail、exit1/6458.522ms/PID8056。三失败是新模拟proposal缺必填jobId，v4仅补真实DTO且保留原断言；后页班case确认SourcePanel.load首100遗漏为R05残余。独立static v3又确认R04新M2生成明确失败时旧M1候选复活，准备独立正确行为首败再窄修。当前原候选/首败/新构建均保全，不进入browser，不关闭B5。证据工具二次修严格限定两live authority，589实时原件+2核准归档快照保护，原首次587+4分类及prebuild-v1不追改。
