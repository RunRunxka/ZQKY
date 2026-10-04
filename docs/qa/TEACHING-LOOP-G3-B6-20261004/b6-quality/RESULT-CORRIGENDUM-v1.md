# B6 质量结果调用计数勘误 v1

原RESULT-v1.md一句“每例15次合法Provider transport调用”存在表述错误。准确计数为：**15例各1次合法Provider HTTP transport替身调用，合计15次**；真实模型和外部网络调用均为0。

独立核原SUMMARY.json的15条结果，每条providerTransportCalls=1，合计15；原seed-wires目录有15个实际wire文件，逐文件SHA登记在本JSON。原RESULT-v1.json没有将每例调用数改成15；手写expected、病例、生成结果、原收据与旧报告字节保持。此处仅追加文档勘误，不重跑或改QA、不回写旧记录。

原报告SHA `fc130de233c56361d3666075382e567469a88ec9520a580c16b4725eec604d89`，原JSON SHA `328de280d10103afe5afedc99c69f89caf00101b4bd4b9b8f540e887f55f441a`。当前未发现其它需要勘误的陈述。独立验收请结合本勘误引用原结果；真人teacher_review_pending、live_run待输入、RAG-REL OPEN保持。

STOP。
