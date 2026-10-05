# G4-BROWSER-REVIEW v2：新11与原14真实材料独立复核

2026-10-05，g4_v00_product。**新 G4 fourth 单轮 11/11、原 G3 兼容 first 单轮 14/14 的实际资料均完成独立核查；完整174仍待完成和独立复核，当前不能关闭G4。** 本 Agent 只读产品、ROOT测试、原报告/trace/附件，只写本目录；未开停服务、未操作浏览器、未改业务断言、未执行真实模型。

候选均为 `CANDIDATE-G4-fix-built-r2.json` SHA `f81a0684abdf734b067a731c089f798a3aabfe66a1f5d336ea1bd1506db34d6e`，构建 `VeOLFBYrp-8v24Yjm-HFi`。两份命令的 source956、执行QA3493、build970 Before/After映射分别与该候选逐项相等；next-env原SHA前后一致、exit0、子进程/日志已关闭。旧两份G3测试原字节SHA也与冻结候选一致。核查没有合并轮次。

## 新 G4 fourth 单轮

ROOT命令PID10896，`2026-10-05T05:23:46.690187+00:00`至`05:24:00.333401+00:00`，13636.767ms。实际Playwright报告expected11、unexpected/skipped/flaky均0、全局错误0；每项只有一次passed结果、retry0。11个trace ZIP逐一CRC通过；独立解析实际业务请求/响应资源与完整附件，而非仅接受计数。检查数据见 [fourth-inspection.json](fourth-inspection.json)。

四视口390/1024/1440/1920：恢复前零保存，键盘Enter触发公开恢复，完整11字段/两个process.secondary/context/source保存一致；恢复后各一条实际PATCH200，固定历史各1→2，原历史正文完整不变，明确离开回旧本地稿。每视口焦点和恢复图共8张已以原分辨率逐张查看：恢复按钮焦点环完整可见且可达，恢复后红错误消失、保存可用，390动作自然换行。窄视口部分正文在工作台内部滚动区域，不把截图当全文保留证明；完整正文依据实际JSON与真实后台响应逐项确认。

持续quota：实际保存PATCH0，完整公开下载备份与当前输入相等、失败写入包完整；原Storage值本例为null，trace两次读取均null，保持其原值；后台当前稿/历史/固定版本完整响应未变。此例未假称已有缓存字节，坏原件另例覆盖。

pre-send：真实公开恢复按钮在原save写失败后可用；完整durable恢复包等于失败冻结包，operationId/submissionId保持；唯一PATCH在明确“重试原保存包”点击之后，请求与原payload+原submissionId逐项一致，后台完整正文保持、历史2。新真实同oracle通过，旧third持续disabled首败仍保留，未追改旧诊断。

unknown：原真实后台提交成功但浏览器ACK故障后，同包两次浏览器保存请求完全相等；恢复后后台当前稿/完整历史/所有固定正文与重放前整包相等，总历史2。trace有三条PATCH记录，是route.fetch内部成功、浏览器abort、明确重放成功；不误报三次业务提交。CAS：仅另一教师真实PATCH推进后台，缓存仍保留本机完整新输入和原CAS，人工冲突可见，无浏览器自动覆盖。

坏cache：新页init注入在首次读取之前，真实读取失败可见、编辑阻断；trace末次Storage结果等于原坏raw，PATCH0，当前稿/历史/固定版本完整响应相等。新设置到达正确前置条件，未改产品pagehide保存语义。

Source两阶段：分别持有真实get-source/verify的200响应，原响应体SHA256与trace原字节吻合；首次null清除和重复清除后旧[0,10)不采纳，旧范围生成0；明确新[10,20)以后每例只有一个实际POST，payload只含新范围且Q/practice、教师要求、43分钟与固定metadata/scope保留。get-source最终verify计数1、verify阶段2，包含随后新意图的核验，未误计为取消阶段计数。新proposals请求在用例核payload后关闭context，trace为-1且无响应体；这里签“实际新意图请求”，**不宣称这两请求生成完成或真实模型成功**。实际建议生命周期由其他适用场景与后续材料界定。

追加精确绑定：两包classId/analysisRunId/selectedKnowledgePointIds/profileId/Q与practice固定revision数组均逐项等于本轮seed，scope完整selection与唯一教材document/revision一致，normalized全文SHA等于seed原文SHA；verify包的完整scopeSnapshot等于held真实验证响应，get-source包的全文SHA等于held响应。证据见 [source-exact-binding-v1.json](source-exact-binding-v1.json)。

## 原 G3 兼容 first 单轮

PID13436，`2026-10-05T05:24:36.835444+00:00`至`05:25:21.085616+00:00`，44244.62ms。实际14项passed各一次、retry0、skipped/flaky/unexpected0，14个trace CRC通过，原g3.spec/source-late字节未改。检查数据见 [legacy14-inspection.json](legacy14-inspection.json)。

重复历史复制：一次实际持有GET、撤销完整复制，固定后台整包不变；真实后台CAS推进v3时不接受旧复制，原v1/v2固定正文仍一致；真实成功GET后仅运输丢失，明确重试完整恢复；跨文档A晚GET不能替换B，A/B后台完整整包都不变。

四视口明确放弃：真实Next200目标响应持有至少1500ms、期间恢复旧正文、缓存null、保存0，before/during/after完整后台相同；四视口历史GET晚响应：长正文超过5000字符、process设计与secondary完整保留，新编辑和原CAS保持，明确再复制/undo/redo后保存新v3与v4，原v1/v2各固定版本完整响应不变。

两个旧来源场景：真实另报告GET晚响应在明确放弃后不能复活来源，公开备份全11字段保持；BASE/另报告及两份固定成绩 beforeFacts/afterFacts完全相等。对照场景在同一保留子树中发起新的教师来源选择后，完整新cache/context与实际v2保存保持，唯一明确PATCH，原固定历史不变。这是实际Next成功提交前的新操作，未宣称最终导航失败/取消。

## 原件、隔离与后续

新轮31个附件（19PNG/12JSON）仅base64原字节解码或复制原附件，映射/SHA在 [fourth-attachment-map.json](fourth-attachment-map.json)；旧14的16个JSON原字节抽取映射在 [legacy14-attachment-map.json](legacy14-attachment-map.json)。原报告/trace/旧证据没有写入。终端Python stdout的中文显示曾失真，经原报告/附件U+FFFD计数0及Unicode精确核查纠正，原文件编码完整，无路径修复或字节重写。

只读审查器准备时修正了trace结果可能为scalar、键盘事件实际名keyboardPress、Storage原值serialized null三种解析形状，未改业务oracle或重跑浏览器；最终全11及全14只读核查分别通过，代码原件和结构化结果均保留本目录。

真实业务为隔离Next5174→FastAPI8001，新TEMP `zqky-b5-g4-g4-browser-r2-ahmhdx61/data`，四库在TEMP，Settings.credentials_file=None；只有生产Provider/RAG HTTP为显式Transport替身，live0，正式.env不读。服务收据PID4292已closed，server/watcher/transport/seedClient/log全关闭或恢复、TEMP保留、sourceDrift0；本Agent只核收据，没有操作服务。进程最终全端口资源后验由ROOT另签。

本卡签新11和原14所列行为；独立组件新38的RESULT-v2单独有效。完整174、其他适用门禁、G4总控关闭与B7-A放行由后续实际证据决定。教师评审pending、Word/WPS not_run、真实模型0，原B6/B7整体不代签。STOP；旧third 9/11诊断卡与所有旧首败保持原样。
