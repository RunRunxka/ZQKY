# B5-F30-L-v6 / R08 在途导入转unknown的离开UI状态同步

ID/version B5-F30-L-v6；负责人g2_fe；ROOT授权时点 2026-10-03T13:17:41.114311+00:00

独立r7完整27为26pass/1产品fail（5266.989ms/PID10640）；新React适配有效、原测试判断正确。导入在途时开LeaveProtection，真实useLessonOperation status0转unknown后DocumentsPanel只effect改pendingOperation.current，Gateway没有响应状态或订阅，兄弟dialog不重绘。guard读取即时ref仍有效；已观测unknown提示缺失，后续button/cache断言未执行，不夸大为越权或丢稿。R08 P2，不能改独立27等待/文案/assert来掩盖。

唯一可写产品：apps/web/src/features/lesson-plan/model/DocumentContext.tsx；components/DocumentGateway.tsx；components/DocumentsPanel.tsx；lesson-workspace.test.tsx。这四件不在冻结33，ROOT保留共享公共契约唯一归属；private DocumentController的状态通知能力在本卡明确授权。LeaveProtection的R07修复、公共NavGuard、useLessonOperation、API/DTO/后端/原27/原153/权威文档/旧QA不改。若需要别文件先具体报。

目标：由文档控制器拥有响应式状态/稳定订阅发布能力，DocumentsPanel在busy/unknown变化时同步发布给控制器，保持guard的即时ref语义、让已开dialog在无额外教师编辑/取消重开时实时反映busy→unknown、unknown→retry busy→known success/failure。不用轮询、浏览器全局事件或隐藏强制编辑触发render。清理/卸载/StrictMode不得用旧producer清掉新上下文状态；只通知有变化的当前operation，避免渲染环。成功旧receipt/current=false不得误导航/重放新包；原import envelope/metadata及本地最新11字段保持，不提前flush/write/discard。UI未知提示与恢复控件按最新状态展示，server/print/坏稿保护与正常localflush能力保持。

先保全四件修前源与既有2198+v5新增/冻结33；新增meaningful作者完整workspace回归（原121保留），修前捕此UI正确行为失败，后同QA完整新单轮/type/lint0。私有独立27是原r7确诊oracle，不采用作者merge；ROOT后续在新稳定候选重新完整27/新checkbuild/完整8/原153/14。

所有上一轮runtime已结束，ROOT自有服务全closed/样本保持；作者唯一窗口OPEN。只b5-fe新v6私有QA/快照/结果可写，不build/TCP/HTTP/新agent/Git。写前读模块AGENTS。结果卡列ID/version/四文件真实delta/每cmd PID exit single count ms/sourceQA前后0/连接子进程日志闭合/TEMP留存/首败与所有旧原件/STOP。状态只AUTHOR_VERIFIED_PENDING_INDEPENDENT。
