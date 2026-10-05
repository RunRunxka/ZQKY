B5-V00 · EXEC-prebuild-v4-unit-first-v1 · 独立只读核验 · STOP

ROOT/CTRL 实际执行一个完整 19 项单轮，V00 只读完整 JSON、收据、日志和冻结独立 oracle；没有重新运行或拼接旧轮通过项。19 passed / 0 failed / 0 pending / 0 todo；5 个实际文件，Vitest 汇总 8 suites。PID 25096，exit 0，2451.449 ms。首败 null。

候选 CANDIDATE-B5-prebuild-v4 SHA c51ff888e59f8dd68d43b8fb4fe8d6cdf1072bcfcbd7495e20806afc92bbf705。收据源 938 / QA 2413 前后映射逐项等于冻结清单，源 QA 变化各 0。next-env 本轮前后 SHA 完全相同。V7 QA manifest SHA a27778af31d750ac67d64a8fbcbd4884aa703bb76441b886c6ad79329e016555，104 清单文件实际只读哈希核对，变化 0。原 18 case 名称完整保留，新增 R06 case 1。

R06 新正确行为用例通过 185.652 ms：初次 getRunA 未完成时实际编辑 M2/61/手写要求，完成 A 后 UI 和 GenerationInputs 三项仍保留；真正换 B 且等待过程中编辑 M1/74/新要求，完成 B 后三项仍保留，旧教材证据/练习/KP/context 清空，新 KP 默认未选，固定同学科题仍保留，明确勾新 KP 才形成 B context/classReady。DTO 与预期由独立手写，实际 SourcePanel/Provider + 隔离 source capability，不用作者 merge 作 oracle。

R04 原完整 case 走完 422 和 503 循环，旧 M1 均 stale、采用禁用、apply 0。原 unknown 原包重试、缓存恢复、A→B→A、flush 窗口断言也全通过。R05 原三个后页 case 全通过：241 班/241 ready 报告/241 reviewed 固定练习，offset≥200 且 limit≤200；后页失败不得提供半份选择，明确刷新恢复全部。原 10 个存储/会话/Word/100ms print unit 均通过。JSON 没有逐断言值，按冻结顺序用例 + 单轮 passed 证明执行完成，不虚构调用转储。

childClosed/logsClosed true，独占 TEMP 样本仍存在且保留，JSON/日志原件保留。V00 无 TCP/服务生命周期/Git/产品/旧 QA 写入。所有旧首败和结果保持。

当前候选里的 EuGU-xptkS4Dv7wiXoxD4 是 R06 修复前旧构建；新 fullcheck/build 正由 ROOT 执行，此卡不宣称修后 browser 通过。完整 8 场景、真实下载/打印/四视口、额外 HTML identity、API42 再跑均未在此阶段执行。额外 r2 HTML identity 曾被审批策略拒绝，未绕过；后续仅按已授权 browser trace 原请求证明身份。等待 ROOT 新构建、next-env 精确恢复和 r3 冻结授权。
