# 冻结前QA入口静态修正 v1

ROOT 2026-10-05登记，仅修J01/J02日志故障注入计数。此前准备版 `independent_executor.py` SHA `7d2a7213fa8f1d3c08e9bf764c5df9dd1552fea1a152f4451c6b8cf4a650e089` 和原准备SHA保存在 preparation-original/。

静态发现：patch controlled_ledger.os.replace 实际触及共享os模块，原计数未过滤ledger.json目的地，可能把新匿名来源资产replace计入次数。修正只在 `dst.resolve() == entered.path.resolve()` 时计数并按预定J01/J02注入；其它replace原样透传。

修正前后均未执行验收，没有首败或测试结果。64场景、oracle、产品字节与范围均不变。重新静态AST检查与准备SHA后STOP，待ROOT统一完整轮。
