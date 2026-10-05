# B7B-R-V00 独立结果关联门禁准备 v1

唯一写入本目录；G6 已冻结执行 QA、产品、作者 QA、旧材料、权威文档、Git 与服务只读。X/R STOP 后接口只读，ROOT 完整 all 候选冻结并释放之前只准备，不执行。预算/最终发送/锁与恢复专项由另一独立验收者签收，本卡不代签。

单入口：`apps/api/.venv/Scripts/python.exe -B docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/result-independent/result_probe.py <全新label> <ROOT-all-candidate路径> <候选SHA>`。ROOT 使用自有 run_command 记录外层实际 argv/PID/birth/起止/elapsed/exit/前后冻结组与 build；本卡不另造外层 runner。此入口含 76 个固定独立 oracle、77 次 checker 子 CLI（existing-output 项含先成功再拒绝两次）与 1 个 fixture preparation 子进程。每子进程实际 owned handle GetProcessTimes 捕获出生、原 stdout/stderr 分文件、关闭/新 TEMP 保留、相关源 QA 前后 SHA。

准备基底调用生产 SourceScene、LessonGenerationService.prepare/build_request/execute、JobEngine、真实三协议 Provider serializer/parser，但最终网络传输为明确 MockTransport。旧 QA builder 与作者测试不导入。本卡手写新回答，40/45/5 分钟分别采用 `[2,16,18,4]`、`[3,14,23,5]`、`[1,2,1,1]`，均与原 stageMinutes 不同；原事实、范围、完整字段选择继续取原 15 canonical case facts。新自有 TEMP 生成 15 原案例完整实际包，再独立单 C14 chat 与单 C01 responses/anthropic 共 18 fixture wire；realModelCalls 0。技术基底核准后仅在本批副本进行关联篡改，不改原收到的 raw/wire/usage/job/ledger 包以迎合 oracle。

固定 76 条：技术正向 10、技术关联/保留/假通过反证 40、teacher 返回 13、native 返回 13，唯一名字与预期详见 ORACLE-v1.json。正向覆盖实际 15、三协议、合法非旧分钟、缺 apply、选中未运行、失败已知 usage、失败 hash-only、合成 DOCX 字节完整性与 canonical 同事实重排。反证覆盖文件 SHA、重绑后的 raw/candidate 与 wire/modelPayload、raw/normalized usage、attempt ticket/job/fingerprint/inputHash、源码最小闭包、scope SHA/深层对象重算、完整 selected/unselected/order、case.status/job.state、manifest/ledger stopReason、settled usage、bool/负数/漏 ticket、failed/unrun 借 applied/DOCX、六教师字段及三未选 AI 字段保持、所选 process.secondary 整字段、fixture 冒 live 与已有输出不覆盖。

Teacher/native 只用标明 SYNTHETIC_INTERFACE_ONLY 的新 DOCX、1 像素合成图与合成人工返回测试完整性。正向 shape 不产生真人授权、教师接受或原生打开结论；teacher/native 仍 pending、RAG-REL OPEN。教师检查评分类型/范围、八维完整性、位置/理由、硬失败与结论、reviewerKind、输出/候选/案例/DOCX/时间身份。Native 检查逐页覆盖、重复/页数、真实图片字节与 SHA、secondary/中文符号等检查位置理由、Word/WPS 身份与总体/逐页结论。

全过程原 15 case-spec 文件 SHA `353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55`；273 materialReferences 前后逐字节核查，新 label 不覆盖旧 QA。source/executableQA/sharedContract/build 四组完整前后快照绑定 ROOT 实际 candidate，相关子 CLI SHA 单列，不拼轮。首败保留并汇报 ROOT；失败时不得边验边修。

Guard 分列：fixture 子进程合法 production imports/TEMP SQLite 的实际次数应大于 0，asyncio 内部 self-pipe 实际计数；正式 .env/数据/SQL/main/真实 network 尝试 0，credentialsFile=null、app.main 未导入。Checker 子 CLI 禁止 SQL/网络/main/.env，其四 guard 0，同时实际 productionModulesImported 列表保留，不能将全部 guard 都写 0。未执行真实模型/真人教师/原生 Word-WPS/真实教材 RAG 相关性，原因是无相应输入授权。

准备 STOP 后 ROOT 另冻结 all，显式释放才运行。最终本卡只签结果关联与返回完整性；B7-B 有限技术关闭还需要预算专项及 ROOT 全批原件一致。
