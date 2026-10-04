# B6-R01 / v2：在途明确报告意图优先于元数据自动复选

2026-10-04 14:30 CST。ROOT 实跑停止的 r1-pre-independent：942源/旧QA与新增独立QA前后0漂移，PID5720/3249.703ms，独立8例7pass/1fail。失败 S03 为真实 SourcePanel 的公开动作：已有A，教师选B而getRun B等待，随后刷新metadata先完成，load自动selectRun(A)取消B。第一修复和作者141通过历史保持，不能据此关闭B6-R01。

负责人与单写范围沿用v1：g3_impl只写SourcePanel及同一个b6-source-loading.test.tsx；V00独立8例原断言停写，ROOT独占文档/构建/服务。原v1报告、所有首败与源码快照保留。

必要修复是保护尚在途的教师明确报告选择意图：元数据刷新不能启动自动A读取撤销它；成功/失败/清关联/新意图分别只释放其自身owner；discard/document/store/session旧响应守卫不弱化。不得改独立正确行为或通过延长等待掩盖。可添加最小pending-report-owner并在finally只按其token释放，metadata自动复选须确认不存在正在处理的明确报告请求。

修后作者单轮相关完整141+新反例、直tsc、lint0；ROOT冻结r2后独立同8、新完整check/build、真实延迟B6五字段链、G3受影响来源/离开与完整153。新结果单轮记数，不拼r1七通过项。没有新DDL/后台/导出器或共享壳变更。
