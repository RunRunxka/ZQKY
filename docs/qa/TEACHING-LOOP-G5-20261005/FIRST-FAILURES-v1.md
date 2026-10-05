# G5 首败与复验保全（2026-10-05）

每轮原命令、真实 PID/时间/退出、日志和候选身份保持原件。通过数只取最终各自完整单轮；不将前轮通过项拼入后轮。没有真实捕获的 PID 明确留空，不推造。

| 归属 | 保留的首败与实际原因 | 处理与最终完整轮 |
| --- | --- | --- |
| 原审查反例 | [旧连续操作 stale-ack](../TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/stale-ack-first.log)误采用前次成功 result；[旧工具结果](../TEACHING-LOOP-G4-B7A-REVIEW-20261005/tools/RESULT.json)两条重锚 SHA 的非空反馈被错误接受 | 原件只读；新 G5 先复现再最小修复，原反例重新执行，正确拒绝单列 |
| G5-E 正确行为 | [original-counterexample-first](edit/original-counterexample-first/command.json)、[new-sequences-first](edit/new-sequences-first/command.json)、[author-first](edit/author-first/command.json)：原 stale-ack、新连续操作及同 context 外来缓存防护首败；一个缓存就绪等待定位同时保留 | 修复当前结果与包身份/会话绑定，公开 oracle 不变；[最终作者结果](edit/RESULT-v1.json)最后完整 126/126 |
| G5-E QA/类型 | [author-second-complete](edit/author-second-complete/command.json)112/126，14 例 JSX 配置 React 未定义；后续测试 mock 类型形状失败均保留 | 只适配 QA 配置及 mock 类型；最终完整 126/126、lint 0、非增量 TS 通过，前轮不拼绿 |
| G5-E 证据适配 | [FINAL-SEAL-FIRST-FAILURE](edit/FINAL-SEAL-FIRST-FAILURE-v1.json)：证据 helper 默认编码解码失败，未形成成功结果 | 保留原 helper，显式 UTF-8 适配，实际产品/QA 不变 |
| G5-Q 原两绕过 | [作者结果中的 firstFailure](quality/RESULT-v1.json)：新 label 的 CSV 额外格、Markdown 评语均显式重锚 SHA，修前实际 exit0 假通过 | 严格核 CSV 形状及固定 MD 模板；两反例最终 exit2 正确硬拒；完整 prepare 49 单测/80 CLI、legacy 52 单测/53 CLI 分列 |
| G5-Q 证据计数 | [SEAL-FIRST-FAILURE](quality/SEAL-FIRST-FAILURE-v1.json)：原编译器把 80 次 CLI 推为 75，短进程 PID 复用导致部分 guard 文件名碰撞 | 保存原件，唯一 PID+time_ns 标签与实际 argv 计数修正；全新 r2 两完整轮重验，四 guard 实际尝试均 0 |
| ROOT 冻结准备 | [FREEZE-PREPARATION-FIRST-FAILURE](ctrl/FREEZE-PREPARATION-FIRST-FAILURE-v1.json)：专属 Python 测试路径漏 `tests/`，候选发布前拒绝 | 保留原 helper，仅纠正白名单路径；prebuild-r1 未执行，后续明确扩展执行 QA 域后发布 prebuild-r2 |
| V00 静态准备 | [PREPARATION-STATIC-FIRST-FAILURE](v00/PREPARATION-STATIC-FIRST-FAILURE-v1.json)：CLI 审查脚本缩进错误 | 保留原准备文件；修静态准备，冻结后执行，不计为产品门禁通过 |
| V00 组件第一轮 | [PRODUCT-FIRST-FAILURE](v00/PRODUCT-FIRST-FAILURE-v1.json)：完整 150/152，两原包恢复用例误找普通创建/导入按钮，未到达最后 wire 断言 | 174 结束后只改两处公开 replay 入口定位，普通按钮 disabled 与全部业务断言保留；[QA 定位差异](v00/QA-LOCATOR-DELTA-v1.diff)单列；built-r2 上新完整 [152/152](v00/product-second/command.json)，不拼原 150 |
| V00 最终材料 helper | [AUDIT-INLINE-FIRST-FAILURE](v00/AUDIT-INLINE-FIRST-FAILURE-v1.json)：将四项 nativeFeedbackStarterRows 列表误按整数 4 比较，尚未写最终签收 | 仅按实际列表长度核四起始行，原材料、全部门禁原件不改；[只读最终核查](v00/FINAL-READER-v1.json)独立记录 |

完整 check、新 8 页面场景和现行完整 174 E2E 各自首次完整轮通过，没有静默 retry/skip。102 独立 CLI 的 97 项预期非零退出属于正确硬拒，不能称 102 个命令 exit0。原 TEMP、旧 policy 拒删目录及全部首败保留，未删除或覆盖。
