# G5-V00 独立验收结果 v1 — STOP

R-G4-RECOVERY-01 与 R-B7A-QUALITY-01 两项 P2 问题均独立通过，可交 CTRL 按本轮限定技术范围关闭 G5。实际新候选为 built-r2，构建 `2Gg_WxijBmV9IGIkY1vmG`，960 源码／3660 执行 QA／33 契约／970 构建当前逐 SHA 无漂移。完整证据、命令、PID、轮次与边界见 [RESULT JSON](RESULT-v1.json) 和 [总核收据](FINAL-READER-v1.json)。

| 门禁 | 实际完整轮 | 身份／耗时 | 实际候选 |
| --- | --- | --- | --- |
| 独立组件 | 152/152，0 fail/skip/todo | Node PID 22752，23716.542 ms；outer PID 22760，24640.821 ms | built-r2 |
| 独立离线 CLI | 102 次唯一调用：5 正常、97 硬拒；四 guard 全 0 | outer PID 15400，47425.353 ms；子 CLI 合计 23765.440 ms 不是 outer 耗时 | built-r1 |
| 新真实页面故障序列 | 8/8，单次，无 retry/skip/flaky/error，四视口及 8 原字节截图已独立看图 | ROOT PID 19380，8985.670 ms | built-r1 |
| 原适用 E2E | 29 spec、174/174；174 trace 完整，原 21 UI 与 R14 保留 | ROOT PID 14648，492652.953 ms | built-r1 |
| 完整 check | 126 文件、1380 单测，类型检查、lint 0 警告及 build 通过 | ROOT PID 3792，105859.499 ms | prebuild-r2，产物冻结 built-r1 |

[组件新完整轮](product-second/command.json) 包含独立新 create/import 28 条、原审查反例 1 条与控制 2 条、原恢复 37 条、来源／历史 60 条及原公开恢复 24 条。连续操作第一成功后取消离开，第二明确失败及清缓存失败，恢复后当前文档、全部 11 字段、secondary、固定 context、source 与选择不变；实际新浏览器故障序列恰为两次 POST（201、422），没有用上一成功回执导航。第二成功只使用自己的回执，新编辑离开可保留／取消。发送前及未知回执保留原冻结身份，正常开始入口禁用，须公开重试原包。

[CLI 完整轮](run-quality-first/SUMMARY.json) 独立验证原正常 15 例、显式 14 例（C15 未运行）、合法引号空 CSV 与 BOM/CRLF。额外 CSV 单元、少字段、多字段、多余行、重复／乱序／错 case／SHA、不空人审字段及 Markdown 每个教师槽、标题、case 锚点、附加内容均硬拒，保留原 46 项验收要求及 aggregate/preflight 守卫。原两项 review 坏样本以原字节复制、仅隔离计划重锚后硬拒；5 正常材料仍引用原 273 个文件，15 空教师行、4 空 native 行、原 13 PDF 页单列。预检只核形状，未形成授权、执行器或实际预算控制。

[新 8 条实际审查](browser-review/RESULT-real-v1.json) 已逐核 HTTP、Storage、公示备份、完整正文、trace 及 390/1024/1440/1920 焦点／恢复图片。当前明确业务失败在清缓存成功后仍可见，当前稿件保留、动作恢复；没有把缓存恢复称为创建成功。[原 174 条实际审查](browser-review/RESULT-full-v1.json) 分清原真实隔离 FastAPI 6 例与受控 UI 场景，不能将全量称为全 mock；模型仍为受控 Provider，真实模型 0，fixture 数据是 TEMP/test 环境。本批未另跑全量 pytest，原隔离 200×100 浏览器样本不代表正式数据库压力验收。

实际 152 在 r2 重跑。102／8／174 保留实际 r1 收据，check 保留实际 prebuild 收据；[显式转签预览](../GATE-TRANSFER-REVIEW-v1.json) 已独立核对同源码／契约／整构建，只有 recovery QA 入口与 ROOT 收据工具两份非其执行闭包 QA delta；没有冒称旧门禁在 r2 重跑。正式转签由 CTRL 在接收本报告后生成。

首轮组件 150/152 的两处 QA 入口错误与原失败完整保留：[首败](PRODUCT-FIRST-FAILURE-v1.json)、[原 QA](recovery.first-original.test.tsx.txt)、[批准的两处入口差分](QA-LOCATOR-DELTA-v1.diff)。只改为公开“重试原包”，同时明确普通按钮禁用，原 0 HTTP／原包身份／完整正文／最后一次 HTTP 判据未改；最终 152 是新完整轮，未拼接。准备阶段缩进静态首败、ROOT 未执行 prebuild-r1 路径拒绝、[最终材料计数内联审查适配首败](AUDIT-INLINE-FIRST-FAILURE-v1.json) 也保留，没有删改原证据或静默重试业务门禁。

[历史引用凭证](../HISTORICAL-REFERENCE-v1.json) 原 60 路径为 59 原 SHA 精确引用与 1 个 MISSING_NOT_RUN，原 1056 材料和本次正常 273 引用当前逐 SHA 不变。backend410／chat186／exportCore11 保留同域历史引用；历史 pytest 为 1919 总数、1918 通过、1 规模 skip，另独立 42 通过，历史 chat14 通过；它们未在本批重跑。旧 exportStyles43 有 12 历史漂移，不能整域转签。R14 保留间歇台账，单次通过不宣称恒绿。

[ROOT 资源后验](../RESOURCES-final-v1.json) 4 原实例及 26 后代收据均闭合、5174/8001 监听 0；[两个 fixture](../RESOURCES-FIXTURE-CLOSURE-v1.json) 的 child/logClosed 分列，TEMP 和首败保留，未知用户进程未动。V00 只读核凭证，没有启动／关闭服务。

授权止于 G5。B7-B 未开始、模型 0、教师试评 pending、Word/WPS 原生未验、实体 SQLite/Blob 源 TEMP unavailable 未新验、RAG_REL OPEN、原 B6/B7 总体验收未由本批关闭；未动正式数据库/Qdrant/DDL/压力/Git/原 Word/教材。权威状态由 CTRL 更新，本验收者仅写 own v00 证据。现停止全部写入，等待 CTRL 收口。
