# B5 candidate 证据路径修正 v1

2026-10-03，CTRL独占证据工具。第一次freeze预检 exit1，未生成候选或执行产品测试。原baseline v1把两份live REPORT/README以Windows反斜杠列入g2Evidence，却以正斜杠声明authorityDocumentsAtStart；已授权的当前进度更新被误报历史漂移。修前工具原字节、首败记录另存；baseline/G2 receipt/closing manifest不改。

新工具统一Path.as_posix归类，589件不可改G2证据逐项核原hash；另两件live authority的G2核准原字节改核已存在G2-DOC-CLOSE-CANDIDATE-v2/after对应快照，其hash必须等于baseline及authority声明，合计591件原字节继续受保护。当前两文档hash另列authorityPreservation，不借归类允许修改其他历史；4136历史、33冻结、6 G2契约、分支HEAD/next-env/build规则原样。新候选及最终独立审计必须复核这两份原快照和当前文档精确增量。

18:37 独立静态/文档复核补记：首次修工具把authorityDocumentsAtStart全集交集4项移入archive保护（587直接+4archive），其总591原字节都保持，但比本卡预期2例外更宽且实际分组不符。原工具/bin与prebuild-v1不改；完整check已结束source/QA0后，CTRL将唯一例外集合收窄并assert为当前README/REPORT两项，其余589（含原G2-CLOSE-MATRIX/TASK-CARDS）仍实时核原hash。原baseline/原关闭快照/首次候选均保持，新候选另版，旧check只绑定旧QA版本，不冒称执行了新tool。
