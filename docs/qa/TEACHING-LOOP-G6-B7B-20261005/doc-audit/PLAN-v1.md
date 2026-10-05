# G6/B7B-D00 独立文档与保全后验准备 v1

ID D00，版本 v1，负责人 g6_doc_audit。起点 main@b7f99ab09826c68724e281d01e15215e660c1ce0，唯一可写范围为本目录；产品、其他 QA、六份权威文档、旧材料和 Git 全部只读。当前只是准备，不签 PASS。ROOT 冻结全部候选并明确释放最终 REPORT/CLOSE/HANDOFF/六状态后，才填写独立 INPUTS-final-v1.json 和逐项人工观察。最终整轮由 ROOT runner 执行，argv/PID/出生/起止/elapsed/exit 以实际记录为准。

后验以开工 OPENING-v1.json 及 opening-bytes 为基准。六份权威文档仅剥离精确 `G6-B7B:20261005` 状态块与紧随的新增空行，余下完整原字节必须相同，包括 v2 原任务、伪代码及历史旧块。其他十八项 authority 中稳定文件或原不存在状态保持；原 Word、next-env、Guide/API/ROUTES/PLAN 与锁文件不改。HEAD/main 直接读取本地 Git 引用，无 Git 命令和写入。

逐 SHA 重核旧 QA 46952 文件、原材料 1056 文件、273 条固定引用及最终 source/执行 QA/contract/build 域。文件数与测试数分列。旧 VISUAL-REVIEW 缺件保持 MISSING_NOT_RUN，旧 SQLite/Blob 源 TEMP 缺件保持 not_run_source_temp_unavailable；新 TEMP 生产 SQL 不能补签旧物理恢复。所有首败与 TEMP 保留。

最终报告必须分列 G6、B7-B 离线技术、授权 live、教师、native、RAG-REL 六分支 pass/fail/not_run 与理由；G6/B7B 限定技术关闭须有独立稳定候选收据。保留 G6 作者274、独立211、check127文件1463、browser16、现行29spec174 的实际轮次与候选身份；首启动 WinError193/测试0、首完整8pass/8fail与最终新完整16不拼接。后加 QA/文档差异单列，不把实际 built-r1/prebuild-r1 身份写成 all/r2 重跑。B7B 正确硬拒计为预期结果，fixture/live 与 actual wire/method 调用/attempt/usage分别核对。

API/聊天专项/导出本批未执行，backend410/chat186/exportCore11仅逐SHA适用历史引用；旧export43有12漂移不能整体转签。真实模型未授权，当前 CLI 缺模型计费 proof registry/可信 live host、费用不支持，必须 hard-refuse/real0，不称任意真实模型 ready。教师/native/RAG-REL及原B6/B7整体和R14/CV01～03/OBS-LP-MODE-LABEL/原环境观察保持待验或OPEN；13历史PDF页不替代Word/WPS原生核查。

自动检查新增状态块与当前 ROOT 文档的相对链接存在及文件 SHA，可识别明示历史缺件；历史旧块不追改、不作为最新 oracle。人工核对当前报告/收据/交接/六状态的语义、计数、实际候选、限制、首败和停止边界。脚本输入须显式 SHA 绑定全部核对对象，并以预先 oracle 和真实原件为依据，不能从输出反造期望。机器或人工任何不一致均 FAIL，给具体文件/行；ROOT修正后新label整轮，不覆盖失败证据。

准备 STOP 前冻结 PLAN/ORACLE/脚本 SHA。正式命令为 `python -B audit_documents_v1.py --label <新label> --inputs <独立索引绝对路径>`，结果为 `runs/<label>/RESULT-v1.json` 和 `RESULT-v1.md`。脚本不自改输入，不重新执行产品门禁。最终资源/INTEGRITY/封印由 ROOT 在审计后追加，审计仅注明后追加边界，不提前引用不存在产物，不冒称后追加材料在此前候选内。
