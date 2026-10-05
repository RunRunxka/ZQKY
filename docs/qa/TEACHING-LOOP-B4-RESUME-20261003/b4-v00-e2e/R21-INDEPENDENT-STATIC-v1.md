# B4-R21-INDEPENDENT-STATIC v1

**STATIC_READY_FOR_CTRL_RUNTIME_GATE_RELEASE**。本轮仅静态核查；P未运行浏览器、服务、HTTP、业务测试、collect、build或新版恢复场景。r21未因此获得运行验收，R14/B4尚未关闭，固定两UI单轮需CTRL另行正式放行。

候选SHA e558dfbf4af33790328c7c036edfee0aa38c1371da5cb65f6ac8c448ba7c4d39。独立pre/post审计均exit0：879 source、53 executable QA、5 contracts、2007 build、3043历史证据与191今日旧证据全零漂移；源/QA/build无新增。P另外自行逐文件重算SHA（约906.297ms），与r21 map全同。原r17 451前端、367后端业务scope（含原已冻结路径集）、2007构建实际SHA均相同；原next-env、BuildID Ji-Jz8X9yY2R_79JOPivD和实际8001 rewrite身份保留。367的路径集取原R20独立报告，预期SHA重新从原r17候选取出、实际SHA由P重算；没有重复附带旧3MB来源报告，也不重新验收曾由P实现的T70业务。

r20→r21仅两项期望变化，其余全部原字节一致：

|scope|唯一变化|核查|
|---|---|---|
|879源码|tests/e2e/helpers/book-interrupted-recovery.ts|删除161B/三行busy按钮判定；cb6407c…a072→73a6eb08…00087；完整SHA及diff在JSON|
|53执行QA工具|b4-root/candidate.py|仅扩大freeze的completed-prior收集；0f72641d…b29d→8ab62806…e0f9；capture块以外逐字一致，audit else AST全同|
|契约/构建|无|5/2007全部SHA相同|

helper原before13,227B/现13,066B。将唯一完整删除块还原，逐字精确恢复r20；公共API、arm/offered/at-most-one真实Continue/capture计数、保存note/书page身份严读、异常/暂停/损坏/失踪/拒绝恢复/绝对deadline拒绝、storage ready且strip0才能成功、cleanup等待result/释放observer/timer/listeners/dispose及错误传播完全保留。busy“正在继续…”不再置resumed；resumed仍仅在真实click后观察到preparation或compilation阶段置true，之后若又回到interrupted可点击状态仍拒绝。没有增加第二次点击、宽松ready、写存储、设状态或延长预算。

原books-commit-safety.spec.ts在r20/r21均SHA b36e6b41…ae27f9；P spec均SHA b9184451…dfc79；P config均SHA 2a4e680a…6f393。安装的TypeScript AST只读复核：原49个业务matcher按原顺序完整保留（当前52含既有新增ready2+cleanup1），六标题相同；除双书目标case外另外五callback printer-normalized body全同。所有原总预算120000/180000/150000/150000，双书两个120000 strip等待、既有最早绝对deadline不变。P两标题/60 matcher、两180000及120000完成等待均原字节不变；静态matcher数不冒充运行断言数。原case集合/其余5case与两P场景本轮不改。

candidate.py仅扩大completed-prior捕获；85旧今日条目在191新保护集内全部保持SHA，无丢失/改动。首次R14的results JSON/JUnit、两trace、4PNG、error-context、真实note/click/cleanup事实、完整日志/进程/收据/报告均冻结；聊天完整结果和stream生命周期收据亦保留。191中30PNG=26原visual+4R14首轮。3043历史全部重算一致。冻结后新增视觉说明或本轮static说明不伪装成191旧文件；其后final binding由CTRL单独登记。

首轮时间线边界：紧邻单次trustedclick的82个frame snapshots里，disabled busy后enabled旧interrupted持续到35179.272；稍后的error-context.md已有compilation/Pause/首失败页排队。这是不同观察时点，不能写“所有原件完全没有compilation UI”，也不能由稍后UI推出持久化ready/最终note/ID/locks。首轮failed结果和未执行后置断言原件保持不变，后续绿测若放行必须生成全新label及输出。

只读schema探索保留两项内部读取失败说明：最初猜测r17文件名不存在，rg后定位原CANDIDATE-b4-r17-nav-final.json；r17候选没有buildFiles字段，按原BUILD-IDENTITY-b4-r17.json文件映射核查。均未执行业务、未改源；最后全部来源及静态核查通过。CTRL联合六TS type/lint的实际exit0收据仅引用现有结果，P未重跑。

本轮结果JSON包含唯一diff、全部counts/drifts、before/after audit与局部AST口径；原报告不覆盖。已停写源、执行QA与报告，等待CTRL正式运行放行。
