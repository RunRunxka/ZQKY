# G3-BOUNDARY r2 独立动态读判 v1

时间：2026-10-04T13:10:56.045976+08:00。结论：**BOUNDARY_COMPONENTS_PASS，G3 尚待真实浏览器门禁与 CTRL 关闭**。

本验收者准备原 5+1+1+1 共 8 例独立行为探针；ROOT 在作者 FINAL STOP、完整 check 及生产构建后冻结候选并执行。我只读完整日志、收据、三个完整 facts 块、实际源/QA/契约/build 字节，不重复执行 QA、不写产品。受测为真实产品组件/hook，服务是匿名受控替身；保存次数是 `saveLesson` 调用和受控固定版本回复，**不等同于真实 FastAPI 服务端写入计数或真实浏览器验收**。

## 候选与执行保全

- 候选 `CANDIDATE-G3-r2.json` SHA `80bc5a40d08c81a0b6cb5d62e19d4267ccf3c56e0c1d2c776fe89ce839860d22`；main@`6cb6a40db890390f0261d547213e319040f64785`，build `q84e_pxQoZ2_nwnws9QiI`。
- source 941、executable QA 3134、共享契约 33、生产 build 2161。独立读取各映射现有文件计算 SHA，四组全部 **零漂移**；计数是文件数，不是测试数。原 old candidate head `6aeb57280f6a7e0d7391cad4d150745479ea58ec`、旧 QA9196 与开工73条 dev cache差异没有被改写成本轮成功。
- ROOT `ctrl/g3-boundary-eight-r2-command.json` PID25060、exit0、4353.012ms；日志摘要 4 files / 8 tests passed，Vitest reported3.48s。receiptSHA `2076d4baba693ad7c951460da97c20ace8acf42d1f38b226442fc0b9186ef80f`；logSHA `a13b0807ee37241d5c35ead1c6a613811f41a67bc125fdbcf3a954f5cd87e43a`。source/QA 前后整图一致、changedSources/QA为空，next-env 前后原 SHA 相同；childClosed/logsClosed true。
- 原反例 `source-callback-boundary.test.tsx` SHA `bfc96c302b1ccb2581c11b6a6c9101389821d0d3de9844ff8e18c14f1420099d` 与首敗 r1 完全相同，未改断言。r1 PID19084 exit1/8软失败的日志与 `SOURCE-CALLBACK-FIRST-RESULT-v1` 保持。r2 原反例日志不再出现 context null、恢复键重建或多提交。
- `DYNAMIC-FACTS-r2-v1.json` 从日志单一 marker 精确解析保存三块实际 JSON；SHA `206e34f8cc19535a900341e25601630c0573b6f3321a780991208284ebb13e8f`。未以作者自测代替本轮独立证据。

## 8 例行为审查

| 例 | 独立行为条件 | 本轮读判 |
| --- | --- | --- |
| 1 | server成功discard可信完整11字段/context，Undo不复活A；keep/flush/pagehide/beforeunload/排队周期无旧写，newB可保存 | PASS，原断言不变 |
| 2 | 删除失败保留唯一完整A正文及原raw缓存；keep/flush/pagehide/自动周期隐式写暂停 | PASS，原断言不变 |
| 3 | 更高恢复CAS不接受更低known为saved基线，拒绝时保全稿件或明确封存 | PASS，原断言不变 |
| 4 | exclusive ownership阻止discard且不删恢复数据 | PASS，原断言不变 |
| 5 | local实际已保存信封恢复完整正文；卸载flush安静，newB正常保存 | PASS，原断言不变 |
| 6 | actual SourcePanel迟到报告回调不能改恢复BASE context、重建缓存或新建保存 | PASS；facts逐项确认11字段BASE、cache.context和displayedContext都BASE、recoveryRaw=null、3600ms后saveCalls=[]、CAS1/fixed1 |
| 7 | discard撤销旧run/KP/input回调，同时允许新的教师report/KP选择及正文B正常保存 | PASS；47分钟与人工requirements保留；旧KP清除、classReady=false；新A/KP明确操作后可classReady=true，合法保存2次：BASE正文/contextA CAS1→2，完整B/contextA CAS2→3 |
| 8 | actual完整LessonPlanWorkspace含ServerControls，经JSON导入完整A及已加载A/KP，公共nav/discard恢复可信BASE来源与正文；随后新编辑正常保存 | PASS；报告BASE、来源固定v1/fixed1/contextBASE，3600ms空恢复键/save0；只新标题B编辑后save1，payload除title全部11字段与过程ID为BASE、contextBASE、原CAS1→固定v2 |

前三块实际 facts 的 full11 正文由本验收者在独立标准库读取中重新组装匿名 A/BASE/B 期望值逐项比对，没有运行或导入测试实现。过程ID和长二次备课、中文及 `&<>` 内容均保留。第8例恢复时DOM对完整可见字段断言；后续仅标题新编辑的真实保存包进一步证明其它字段和原过程ID全部是可信BASE，没有把弃稿A残余包提交。

## 同候选其他适用组件回归

| ROOT执行 | PID | exit / elapsed | 日志实际摘要 | 分类 |
| --- | --- | --- | --- | --- |
| 原required两例定向 | 14024 | 0 /4064.218ms | 2 passed、4 filter skips，2files passed/1file skipped | 原两required复验；不能写6例全pass |
| V00独立矩阵 | 16652 | 0 /5644.926ms | 15 passed /2files | 独立组件行为矩阵 |
| 旧27相关回归 | 21000 | 0 /7154.447ms | 27 passed /6files | 原范围相关回归 |

以上三份收据也逐项核候选SHA、logSHA、前后source/QA、next-env及结束状态相符。作者137与ROOT1281完整check属于另一层证据，不与8/15/2/27重复相加成一个全量成功数字。

## 关闭边界和STOP

本轮可把 G3-BOUNDARY 组件行为子门槛记为 PASS；没有新的可复现产品缺陷。真实浏览器14例仍由ROOT执行，本报告没有读取其未完成结果，不写true-browser PASS，也不单独关闭G3。保存边界需要真实浏览器来源身份、服务隔离写计数与全链证据综合确认。B6没有提前启动，教学质量/人工live input与WPS/PDF验收不在本报告中变成已完成。

原四个测试文件、首敗、旧QA全部保持；新增仅本facts/报告/STOP结果。完成报告后 STOP：不改产品、不新增测试、不执行QA、不启动服务、不操作Git，待ROOT真实浏览器结果后按新卡只读综合审查。
