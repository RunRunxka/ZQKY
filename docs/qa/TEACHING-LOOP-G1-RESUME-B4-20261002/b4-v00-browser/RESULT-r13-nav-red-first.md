# B4-F-R13-NAV — r13-nav-red-first

正确行为独立红测仅执行一次：实际1文件/2tests/2failed/0passed，childPID27264、exit1、3343.414ms，外层exit1。完整66169字节stdout/stderr合并原log及子收据在b4-root/r13-nav-red-first.log、r13-nav-red-first-command.json；log SHA256 4f80569e2ea06f03a127133ecb5f26a60646bc7e7f3727d6649296394da8d28c。没有启动/collection/type错误，失败落在预期产品行为。

第一例line89，1070ms：同挂载imports工作区收到显式tab=library、受控晚到重复hash后，library aria-selected仍false。第二例line115，1025ms：以legacy #library挂载的真实QuestionLibrary已选中，显式tab=generation后generation body仍不存在。实际serverpage/Workspace/QuestionLibrary均未替换，不把其他显式数据/面板替身作真实服务通过。后续manualtabs/query、legacy remount等在各首次失败之后没有执行，不能算已通过；原全部正确预期保留，未改QA或重试。

冻结r14 diagnostic SHA647a6607cb9d0b21a057739a18fdd118c8ebad1b5016c36de75482c05652163d。前审212ms/exit0，完整878产品/45QA/5契约0漂移、next-env一致。原后审oracle已完成206ms/0漂移并保存JSON/570字节stdout/0字节stderr，但收据包装器写end字段时NameError（timezone未定义），外层exit1；原结果和流不覆盖、不补造缺失PID/CLI elapsed/command receipt。

CTRL单独授权的新r13-nav-red-post-closure只重核冻结身份，不重跑业务：实际oracle203ms、包装CLI290.466ms、PID27996、exit0，自然退出；完整878/45/5仍0漂移、next-env一致，新JSON/命令/原流全部独占保存。原包装器错误单独保留在audit-r13-nav-red-first-after-wrapper-failure.json，不因闭合新增审计删掉首败或改口原外层0。

子进程和所有流/日志已自然结束，无自有监听或浏览器，无服务操作；新系统临时目录C:\Users\96022\AppData\Local\Temp\zqky-b4-r13-nav-red-first-hj_ng2um保留、不删。全部源码/原E2E/旧QA原样，当前只新增MD/JSON收口并停写，CTRL可实施产品。绿验收未执行，等待修复后新稳定候选。
