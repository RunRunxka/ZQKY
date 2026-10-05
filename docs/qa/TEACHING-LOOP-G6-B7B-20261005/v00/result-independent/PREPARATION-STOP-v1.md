# B7B-R-V00 准备 STOP

PLAN/ORACLE/单入口 QA 已完成，全部执行未运行。固定 76 个 checker oracle：技术正向 10、技术反证 40、teacher 13、native 13；77 次 checker child CLI（含已有输出先成功再拒绝）及 1 fixture setup child。预计生产 fixture wire 18，realModelCalls 0。执行前须 ROOT all 冻结并显式释放；禁止依作者自检转签。

静态仅 AST parse/compile，未执行模块，PID 20880、33.1667 ms、exit0。执行文件 STOP：

- `fixture_bundle.py` SHA `3751e5b240d85f56ff0f95c48280740d105af365f5ee1599e8963ff712a0f670`
- `result_probe.py` SHA `f758c71bbcd5ca3248ee19101d2766e75b8bd0dd3b2a5af2068ba9508264a1f3`
- PLAN SHA `9678ffb12918e18b871023c4c2b7ecec00f9da0d0e89ab149856b3209b02dc65`
- ORACLE SHA `4df6882f23ecaeaffdc71fd1e3e53f7a0cad5e1b8e0312894b49dfae56fc195c`
- 实际只读 result checker SHA `1367ed17beb2b5d1bc214c297f26c8a70b4f04c25399b0dbe16fd57776972b25`

ROOT 单入口实际命令：`apps/api/.venv/Scripts/python.exe -B docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/result-independent/result_probe.py <新label> <all candidate完整路径> <all candidate SHA>`。ROOT own run_command 负责外层 argv/PID/birth/冻结四组/build/TEMP 原收据；本卡 CLI 子进程自行保留原 stdout/stderr、actual owned-handle birth、关闭/新 TEMP 与相关 source QA SHA。

G6 已有执行 QA STOP 不变，本次只新增本子目录。独立材料回归范围为新 TEMP 生产基底和原 273 材料字节核查；合成 DOCX/页图/返回只验接口，真人 teacher/native 与 RAG-REL 不关闭。预算/发送/恢复专项交另一独立验收者。
