# V01 / B7B-X 独立预算与发送验收计划 v1

负责人：b7b_budget_v01。任务起点 main@b7f99ab09826c68724e281d01e15215e660c1ce0。唯一写入目录为本 executor-independent/；产品、作者QA、旧QA、原273、权威文档、Git与服务只读。

状态：PREPARED STOP；ROOT 冻结并明确释放前不运行入口。源码静态整理不是产品验收。ROOT 使用其统一 run_command.py 调用 `apps/api/.venv/Scripts/python.exe <本目录>/independent_executor.py --output <本目录>/<全新完整轮label>`，采入口 actual Popen 句柄 OS birth/PID/argv/elapsed/exit/日志关闭。入口另保存内嵌两个真实 OS 锁进程的 GetProcessTimes/实际 wait/logClosed 身份。

预登记 64 个有意义场景，详见 ORACLE-v1.json。一个完整轮按此顺序全部执行，每场景独立 outcome，不将重复断言或文件数算为场景。首次失败原件与所有新 TEMP 保留；有入口瑕疵先保存字节、首败及最小修正说明，等 ROOT 登记再修与新完整轮，不拼绿。产品发现回交 ROOT，不修产品。

独立规则从用户的预算/教学闭环约束推导：实际 MockTransport delegate 进入次数才是 sends；生产 method calls、预留 ticket、尝试次数与 sends 分开。仅 SourceScene 可复用为新匿名生产依赖建立器，其响应 handler 和答案均被独立手写响应替换；不导入作者测试/旧QA builder。三协议完整实际 body/method/endpoint/cap 与独立协议对象比较，所有线上边界使用有限 MockTransport，没有真实网络。

每个有限成功或已知业务失败使用 input31/output17/total48；冻结输出cap4096+fixture输入upper1000=5096预留。成功生产 receipt 重放新增0发送。坏JSON/length/分钟bool结构失败仍实际1send并已结算48。坏usage/超界/网络未知/取消/第二发送/响应日志故障保留5096并硬停。最后case在5100总预算下第一例消耗48后余5052不能预留5096，第二例发送0。换授权相同的run/output label不可清attempt或已花预算。reserved/dispatched/responded重启转unknown，既有unknown拒绝继续；损坏账本原字节不覆盖。

入口在任何生产导入前创建新TEMP并设置 ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8=1；credentials_file=None，独立审计禁止正式.env、正式数据、非TEMP SQL、未隔离main及真实网络。合法production import/TEMP SQL/Windows asyncio内部selfpipe实际计数单列，不写成全0。生产app.main不导入。子锁进程只导入本批scope/ledger标准库组件，不导入业务模块、不访问服务。

CLI live缺授权/缺已注册proof是实际拒绝，给定authorization路径不得读取；费用模式和fixture冒live拒绝。CLI固定控制namespace只读核查，真实参数解析拒绝外部 --ledger-root；DI账本只在新TEMP创建，避免写作者control-state。当前live registry/trusted host缺失、费用不支持，离线通过也不声称真实模型ready。teacher/native/RAG-REL未执行，不关闭原B6/B7整体。

交付：每场景cases/*.json与生产OBSERVED/artifacts、入口前后源码SHA、GUARD、RESULT、实际两个OS进程记录、ROOT入口COMMAND及stdout/stderr。源闭包比对零漂移；禁止项尝试0；合法隔离行为按实际报告。
