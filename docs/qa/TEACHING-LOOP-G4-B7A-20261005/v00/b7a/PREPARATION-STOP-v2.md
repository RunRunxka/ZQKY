# B7A-V00 QA2 独立准备 STOP v2

2026-10-05，g4_s。ROOT批准仅修QA冻结定位。原runner已按原字节保存，SHA `6f6aa7f18576502d898be52538b75f593c5676cabc8d43d02a5552309df2b188`；原定位发现是静态前置，0工具CLI，runner尚未启动，未发生实际业务失败。v1/旧candidate/旧release不修改。

五件QA逐SHA核ROOT显式release.V00QA，只有guard/runner两个.py另核candidate.executableQaFiles。新增CLI参数为--release/--release-sha；释放文件自身SHA、offline状态、authorSTOP和candidateSHA都须一致。四工具原冻结守卫仍保留。

所有literal/46判据/拒绝oracle/guard均不改。PLAN/ORACLE/NEGATIVES/guard四件原SHA一致；AST逐方法确认除constructor外全等，main仅加两个release参数。完整diff和静态定位原件另存。

| 五件新冻结SHA | SHA |
| --- | --- | --- |
| `PLAN-v1.md` | `efb8d3ccf82c50b15de24a002ad8be94a0edfc0ddac3398453595be9db484b2a` |
| `ORACLE-v1.json` | `dceaf4997f94d02a19e50d7b3795d85203c3d8da5935c39fb150ce264b14c555` |
| `NEGATIVES-v1.json` | `68377bed743ce0dbde9f7a87cb60571a52e1ee97dc30a914f5747eff3b1ae8ec` |
| `guarded_tool.py` | `26238ae5ed2be7b3960093251a4a089561f2f25126b05f18879a4ce2955d1ec7` |
| `independent_review.py` | `de67a3d8d138feada0a50ff3e7f7af59feb235175866d1f4c1a52edf7abe5aa3` |

准备STOP：工具调用0，AST只解析通过，不基于作者测试签收。等待ROOT新candidate r2与release v2冻结及释放，才能从新first完整46次CLI开始。旧材料、Q工具、产品、原文件、服务、app/.env/正式DB/网络/Git均未改／未执行。JSON SHA `3d47f33d8b3e8ee036c0f50c9f574e3a43f0d71b55cda537c343cef0aed7efc8`。
