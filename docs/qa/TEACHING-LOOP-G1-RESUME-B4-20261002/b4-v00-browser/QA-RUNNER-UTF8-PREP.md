# B4-F-RUNNER-UTF8 v1

READY，执行源全部停写，等待CTRL冻结。仅run.py在import sys之后、argparse执行之前新增两条顶层语句：`sys.stdout.reconfigure(encoding="utf-8")`、`sys.stderr.reconfigure(encoding="utf-8")`。

原件run.r9-before.txt SHA256 `af9f103c6080d55b634779661d4bd8a5f1b52173d2288bf15fe88d719c55b779`；新run.py SHA256 `f30ef3002b6ec2e974806ff77b713b6b524d630360b602a44d1c9830915fa6d0`。去掉这两条语句及新增空行逐字节还原原件；AST中所有原顶层语句完全一致，CLI/env/子命令/收据/退出码逻辑不动。

seed.py SHA256 `f84e424d40dcbc6ed4d03f08116374175072d3b84278fe2a14d6ec713d654ada`，全部6原assert保留；real-browser.spec.ts SHA256 `66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156`，原115 matcher与R08精确导航await保持原样。静态准备exit0、内部16.012ms，完整命令和输出见同名JSON。未执行新seed/browser或启动服务。

第三轮业务actual1passed/childexit0/24628ms，outerecho GBK编码exit1原错误和完整原流/收据/trace均保留，不冒称outer0；此次准备不抹去旧失败。须由新冻结、新种子和下一单轮真正验证outer0。

