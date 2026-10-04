# 本批首败与诊断（保持原记录）

- 开工 `capture_opening.py`，进程父2928/实际20040，120704.0ms，exit1：逐文件核发现73个既有 `.next/dev` 开发缓存差异；五分组逐项保留于BASELINE-v1。不是产品源码失败，不回写旧候选。
- 并行短核OPENING-FIVE-GROUPS-v1同样在严格全零断言exit1；源码938/可执行QA3061/契约33/prior1702零差异，2004构建中的73项均dev。归因见OPENING-ATTRIBUTION-v1，生产FVU-OXmtBh9WBSHehixfE/proxy8001/next-env原SHA保持。
- ROOT只读进程诊断首命令PowerShell foreach语句直接接pipe产生ParserError/exit1；使用结果数组后只读查询成功，无进程结束或产品改动。

不删除首败，不将严格断言失败静默计为全候选零漂移；归因后OPENING-ACCEPTED-v1只放行新授权产品写入。

- r1独立V00单轮15例中13pass/2fail，PID6184、4838.506ms。首败日志与命令原件在ctrl/g3-v00-unit-r1；local场景与跨文档列表场景待独立归因，不删测试/放宽断言。原两required behavior已变2pass，来源迟到回调静态风险待新反例验证。

- G3-R01额外实际SourcePanel诊断首败：PID19084、2020.119ms，1case失败（8个soft断言），旧来源读取在discard后context→null、恢复键重建、serverRevision1→2/save1。只是受控组件反例，不冒称真实FastAPI浏览器；r2最小修复登记后重新独立复验。

- 首次真实browser命令未收集到case：g3-browser-r2-first/PID23368/814.678ms/exit1，external.config.ts六层相对路径错误，导入ROOT上级不存在playwright.config，ERR_MODULE_NOT_FOUND。0业务case，不当作业务fail/pass、也不是policy拒绝。V00独立保留3QA原字节，仅修import depth，原断言保持后新标签完整14复验。

- Node26真实browser归档故障诊断：同两只读fragment、同installed Playwright1.58.2 merge核心代码，Node26 v26.2.0 7s未完成ZIP/exit1；已安装bundled Node24 v24.19.0 18ms完成/exit0。本行为仅离线运行环境诊断，非业务PASS；未改产品、依赖、trace开关或任何业务断言。两fragment是Playwright自有临时文件，随后worker cleanup已移除，不能称原fragment字节仍在；运行时inputSHA保持，Node24合并完整14entries/CRC通过及Node26不完整ZIP均另存ctrl/TRACE-MERGE-ENVIRONMENT-v1。原qa4首轮/未闭合trace/日志保持，新增13个进行中快照明确live不当关闭收据。

- ROOT只读/文档诊断补记：曾猜不存在helpers.ts及旧zipBundle路径（exit1），未修改任何产品；读取运行中最终trace.zip出现BadZipFile后改为只读local-header诊断，未重写原ZIP。状态检查点手填13:17比实际receipt13:15早用，已用独立clock-correction delta精确改新增状态文字为13:15，原v2任务不变。

- 真实browser qa4完整首轮已结束：PID16940/exit1/715061.223ms，0pass/14timeout/0skip/0retry，source941与QA3134前后零漂移。前13仅归档slot超时；第14另在source-late.spec.ts115下载备份后clock.pauseAt超时，fresh-source保存尚未到达。全部JSON/XML/日志与不完整ZIP保持，不拼单项assert成通过。V00获r5仅移动control暂停时钟到下载前（实际多周期放弃验证之后）准备授权；产品不改、原14和断言/trace保留，ROOT之后换bundledNode24并使用新TEMP seed完整重验。

- 原完整153E2E首轮：PID21988/exit1/388290.997ms，152pass/1fail/0skip/0retry，source941/QA3136前后0漂移。唯一knowledge-point键盘dialog失败；真实trace必需chunk0az8vxg2gfuhm.js=-1/net::ERR_NO_BUFFER_SPACE，其余脚本200，页面仍SSR/知识点正在读取、未有业务API。79entry trace CRC正确，实际资源失败不改成pass。自有PW已退出/只读无残留automation browser、loopback TIME_WAIT59、可用内存21572692KiB（只说明检查时，未断言失效时根因），未杀用户进程/改网络设置。原同case新进程诊断1/1pass PID21752/2456.962ms，不拼152+1；之后全新完整153 second仍0retry同原断言，未结束不宣称G3关。

### B6开始时ROOT离线诊断补记（产品无变更）

- 第一次原计划剥离状态的regex多吃一个原换行，65518/65519断言失败；没有输出证明或改文件。修正opening marker范围后逐字节65519相等，见ctrl/PLAN-ORIGINAL-PRESERVATION-full153-v1.json。
- 误猜g3-seeded-r2-qa5-server.json不存在（实际服务收据suffix为-service.json）；该只读Get-Content失败未操作服务或进行HTTP重试。
- bind_recovery.py要求原早期五源全部等当前而失败：四源相等、原B5后修的lesson_schema_gate不同。v1收据保留，result字符串不作为成功结论，详见ctrl/B6-RECOVERY-REFERENCE-FIRST-FAIL-v1.md。
- bind_recovery_v2.py首次误将全API938映射与后台410子映射直接等同，断言失败、未写合格收据；首源和诊断单列。改为核全938 before/after相等，再逐项抽取后台410核对，v2进程3748/44.374ms完成。当前410同源后期fullAPI真实恢复case与旧56样本/16库全列只读审计分列；未冒称早期五源全相同或本批新恢复。

### B6-R01 r2 ROOT门禁首败与诊断

- 完整 check 首轮 PID23004/97601.115ms/exit1；typecheck/lint通过，1285单测通过、原local flush discard一例失败，build未执行。完整日志保留；旧整文件原断言新诊断PID26172/11088.591ms/exit0、96/96，不能拼为完整通过。对话框可访问性时序正独立核查，未断言环境根因已证实。
- ROOT将G3 8/15两组与check typegen并行，next-env在该窗口为受控生成字节1862ac…，不同于冻结候选0f706…；两组即使8/15通过也仅记诊断，不计候选验收。生成字节保留、ROOT runner已恢复0f706原字节；稳定新构建后重新完整执行两组。
- 14:45:11的追加状态手填诊断数65错误，实际原日志96/96；新增计数勘误，不改运行日志、原任务或旧状态原件。
- 第二完整check PID21976/98102.674ms/exit1，1285/1，原同组retry在路由/save2/原包与缓存断言之后同步检查dialog关闭失败；原dialog open日志保留。独立差分核查后仅补原dialog打开/关闭等待，原15断言不变，作者新原整文件96/96；新候选check PID16920/105612.417ms完整1286/type/lint0/build单轮通过，不与前两轮拼结果。
- 新built source独立命令最初误猜`source-loading.test.tsx`不存在，在sourceBefore读取时FileNotFound，0业务case、receipt/log尚未建立；TEMP `zqky-g3-ctrl-b6-source-independent-built-drd_woy9` 保留。原输出由本项记录绑定；先rg确认实际`metadata-required.test.tsx`后另新标签b6-source-independent-built-r2完整8/8通过，未改QA或复用失败标签。
# ROOT 后续只读材料路径准备失误

2026-10-04 15:15 的并行只读查阅中，ROOT 手写 `b6-quality/RUBRIC-v1.md` 路径不存在；实际教师试用入口明确为 `b6-quality/RUBRIC.md`。工具 `Get-Content` 报 Cannot find path，未执行任何应用/QA/服务操作，也没有据缺失路径作通过判定。后续只读采用已核文件名；原输出保留。此项与业务首败分列，不算测试运行。
