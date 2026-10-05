# G2-V00-QA v5 · explicit-discard 目标身份等待

2026-10-03，北京时间。CTRL 已明确批准最小修正；v5 PREPARED_NOT_RERUN。先创建并固定 RESULT-v2.md/json 后才改 QA；v2 单轮 22/23 unit、10/11 API 的首败与原源码/工具 logs/XML/TEMP 全部保留，不追改为通过。API 同包并发 409 已由 CTRL 确认为产品缺陷，由 BE 修复；本 v5 不改 API 正确行为或源码。

唯一可执行差异 unit/leave-recovery.test.tsx（原 SHA 9d6ae70a34e0280c2bda1507e2ee5ebf3c93b1237c08df659d9c7e5cffe78257；现 SHA c27f2208d8de58ce5face6460389fedae7bbcfa5abc8660b796463e7d8e8ff52）。只改 explicit-discard 场景：由等待 A/B 共用的满分 '1'，改为在同一原 waitFor 窗口同时等当前链条 → 练习 practice-a、固定练习 heading，以及完整 editor 的全部 5 个编辑字段恢复值。原满分 '1'/题量 1 断言保留，新增节点满分 '1'/节点题号 '1'/知识点 ID kp-1；业务动作、明确放弃选择及其他 5 场景完全未改，未增加超时。

STATIC-REVIEW-v5.json 只做 text/hash 比对，无执行 QA 模块/产品。6 场景名称、23 unit/11 API/8 browser 原预算、retries0、所有配置保持。API 文件仍 SHA 6086dcf5c2aea0a159fe447719b54a62264015d7df50fa2850bcfb5ccfeca629，并发双200/一false一true/oncewrite 全保留。其余 8 可执行 QA 原字节不变。

v2 原 9 份源码已保留在 run-api-fixed/source-snapshot，哈希与冻结 v4/r2 表一致。RESULT-v1 与 RESULT-v2、长 argv 启动失败、真实并发首败 HTTP 回包、独立 readonly DB 诊断、44 个四库 integrity/FK 完整证据全部保留。本 v5 没有重跑 pytest/Vitest/Playwright/check，没有写产品、旧 QA、权威文档、Git 或起停服务。QA 已再次停写，等待 BE 修后公共新候选与新运行卡。
