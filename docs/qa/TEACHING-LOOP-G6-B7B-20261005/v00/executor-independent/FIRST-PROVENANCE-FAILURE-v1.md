# V01 full-r1 并发执行身份首败

ROOT统一runner实际 b7b-budget-r1/full-r1 exit0，启动器PID25412、elapsed35249.18ms；入口实际workerPID26408、elapsed34953ms。64场景按原oracle全部通过，actual fixture sends27、real0，源码/QA/build零漂移。

独立原件后核发现 P01 出生身份不能绑定实际锁持有者：children.json 的owner PopenPID23544/contender17836及其GetProcessTimes出生值对应venv启动器；owner-result.json实际锁脚本PID12940、contender-result.json实际锁脚本PID22176。实际owner/LEDGER_BUSY行为成立，两launcher实际wait/reap/日志关闭；不能把这些出生值冒称为两锁worker出生身份。入口的P01未交叉核这组PID，因此64自动化通过不足以签收完整并发生命周期证据。

原因是Windows uv venv python.exe启动器另起实际Pythonworker。ROOT已核同源base为 C:/Users/96022/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe。最小运行设施调整为ROOT下一完整轮直接调用该base、PYTHONPATH显式原venv/Lib/site-packages；此时入口与嵌套sys.executable实际base/Popen句柄PID应等于lock_child os.getpid。无需改冻结QA/oracle/产品，不安装或换依赖。

full-r1全部原件、新TEMP与准备版保留；不追溯伪补worker出生值、不拼绿。当前限定结论：预算/发送/恢复64自动化通过，独立签收仍待新完整轮实际worker身份核验。由ROOT登记并统一运行，V01不另执行。
