# G1接续门禁矩阵

2026-10-02，CTRL确认本次G1关闭。main@6aeb57280f6a7e0d7391cad4d150745479ea58ec，开工826源与g1-r2一致。B3F-R01～R08独立正确行为、check1088/API1599+1skip/规模专项保留明确原候选身份，不重复宣称本次执行。新审查未登记产品修复票。最终826+24QA候选与实际second/完整E2E共同业务及配置SHA绑定见G1-REPORT.md。

| 项目 | 本次状态 | 证据/依赖 |
| --- | --- | --- |
| 原候选/原字节/旧证据保护 | pass | BASELINE.json：826源0漂移，815旧QA文件保护，next-env原字节另存 |
| 用户持有5174就绪/归属 | pass | 用户已报告“启动好了”；root/frontend-listener.json，PID6836/127.0.0.1与start5174命令，绝不由CTRL停止 |
| 构建代理/实际API身份 | pass | BUILD-IDENTITY.json与root/actual-proxy.json；已构建proxy8001，新的隔离真API与固定卷实际通过同源代理读取 |
| 测试资源保留opt-in | pass（资源分支） | 实际afterAll保留/默认清理共4场景单轮通过，独立audit核业务集合及完整SHA；不计业务或浏览器通过 |
| 独立真实浏览器业务链 | pass（second） | 单轮2passed共7471ms，完整9格甲800/丙1000/丁800，zero dirty confirm、实际提交丢响应原包重放且只有1正式revision；SECOND-RESULT.md/second-business-audit.json。first0pass/2timeout保持原件 |
| R08真实富公式/三视口/键盘/减少动画效果 | pass（second） | 真DOCX上传/校对/确认3叶1000units（10分），x/y+默认竖线/显式逗号/竖线9图可见，三视口无页面横溢，实际焦点/Enter及150ms→reduce 1e-05s/no-running/stable-frame；两实际trace全242/95项CRC/SHA完整 |
| 完整原E2E | pass | r4单轮153passed/0failed/0skip/0flaky，366186.744ms；workers1，无webServer/fallback，独立8001先停止，各spec关闭自有child/log并KEEP1实际保留，user5174PID6836保留 |
| 额外stream聊天集成适用性 | not_applicable | 独立audit核87前端/19后端依赖闭包与13产品改动无交集；现有chat UI E2E仍在全量集合内 |
| trace运行环境适配 | pass（环境适配） | 同安装merge源码/两输入ZIP，Node26大型多流超时、现有Node24完整；原作者与独立标准库oracle核46条名称/完整解压SHA/CRC一致及42重复按原规则，实际second两trace也完整。只用已有Node24跑Playwright，未改依赖/trace/timeout/用户前端 |
| 独立最终候选审计 | pass | r5 freeze exit0/743ms：826/24QA/815旧证据/1979build零漂移；业务oracle exit0/299ms，51+35+helper1=87原文保留。QA首败与r2漏覆盖原件保留；只该oracle修正，不影响实际2pass/153pass共同业务/config SHA |
| 整体G1关闭 | 已关闭 | 所有必要实际门禁及最终独立审计已通过，CTRL确认；不以准备/收集/旧全绿关闭 |
| B4 | 现在授权进入 | 另立任务卡/契约/DDL后实施T70/T80，完成其自己的独立验收与最终门禁；本矩阵不代表B4实现 |

完整当前状态与下一动作只看CURRENT_STATUS；本矩阵仅记录本轮实际门禁事实。
