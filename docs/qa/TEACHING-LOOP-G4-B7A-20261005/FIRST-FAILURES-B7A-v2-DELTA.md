# B7-A 首败追加：独立报告封印helper

ROOT，2026-10-05。[首败矩阵v1](FIRST-FAILURES-B7A-v1.md)保持原件。本追加只记录后续报告封印失败，不能把它计作产品失败或重跑完整46工具CLI。

独立完整46轮已通过且SUMMARY SHA始终为`9190cbd7f30e98bc72f44a8b0c2e080b1a89aa4b9e35b58e0924f077bb284442`。其后内联只读封印helper处理作者PDF参考CSV的字符串路径时，sha函数按Path调用read_bytes，报AttributeError（stdin line83）。未发生材料SHA/字段失败，未发布AUTHOR/RESULT文件；原helper、Traceback、实际命令归因及未捕获PID/elapsed明确保存在[FINAL-SEAL-FIRST-FAILURE-v1.json](v00/b7a/FINAL-SEAL-FIRST-FAILURE-v1.json)。

ROOT允许仅转换`Path(p).read_bytes()`，冻结runner/guard/全部46业务判据/新旧工具不改。重新整包只读核273引用与空字段后，最终封印PID21500/613.1ms通过，见[独立结果](v00/b7a/RESULT-v1.md)。实际46轮仅一次；外层runner PID4488/exit0，其elapsed未单独捕获，46个子命令各有实际耗时，合计6950.558ms仅标为子耗时，不冒充外层耗时。TEMP与全部首败保留。
