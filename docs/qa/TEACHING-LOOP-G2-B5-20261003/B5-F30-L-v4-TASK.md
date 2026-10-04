# B5-F30-L v4 · B5R-R06 迟到来源读取覆盖教师新选择

OPEN 2026-10-03，负责人g2_fe，ROOT集成；独立V00为b5_v00。实际起点B5-r2 SHA7800205803341a8e737e8d8ee7c0659bd6c264f78f72ce5e4f312ad3f39c5bec，938源/2196可执行QA/33冻结/2004构建。r2完整8已结束3pass/5fail、exit1/104856.084ms，全部日志/trace/源QA保全；自有API18736已专属stop正常退出。不是边验边修。

独立反例：1440实际model select call@105成功，after@105 M1选中；尚未完成的固定run/class/practice读取返回后，after@107模型回到placeholder，课堂43和后续要求仍在。SourcePanel.load→selectRun→updateSelection在async回调用捕获旧value整体onChange，擦掉其间教师模型选择。该行为是产品缺陷，不能用浏览器等待掩盖。

唯一可写产品：apps/web/src/features/lesson-plan/components/SourcePanel.tsx、apps/web/src/features/lesson-plan/lesson-workspace.test.tsx；新私有b5-fe/v4及RESULT-v4/PRIVATE-MANIFEST-v4。禁止ProposalPanel/公共contracts/route/AGENTS/锁/其他模块/Git/权威文档/旧QA及结果。先读模块AGENTS。只修来源异步采用时保留最新教师inputs，来源相关字段按明确意义更新；继续保留epoch、unmount、同班/同学科/固定ready/KP校验、全分页、不完整不采用、真实核验证据过期保护。不得更改生成已提交包/source签名/幂等语义。

成功：读取尚未返回时选M1或改M2、43分钟及教师要求，异步来源返回后保持当前选择；同来源合法question/practice选择保留，真正换学科/报告仍清应失效的选择/证据；新模型变更仍让旧candidate不可应用。失败/未知/取消读取不采用半份，也不擦新inputs。作者新增受控延迟自检并完整保留原95场景，不生产merge当oracle。记录完整单轮unit/type/lint、PID/exit/ms/日志/source前后/33与旧1593+后续证据保全、新TEMP保留/连接closed。

独立V00另建v7受控迟到来源的正确行为反例，旧18/42/8全部保持。作者STOP后才整体新候选/独立unit与新check/build/browser8/153/14。另四viewport核验证据race及history download后clock.install为QA适配，由V00唯一负责新QA版本，产品此卡不顺手改变下载/时钟。修复不等于独立关闭；B5结束前所有必要门槛实际通过。