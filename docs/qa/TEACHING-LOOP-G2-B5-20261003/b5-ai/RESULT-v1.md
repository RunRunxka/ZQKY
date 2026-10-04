# T90-AI v1 结果卡

状态：**已实现、作者自检通过、待独立验收**。源码和私有测试已停写。未把作者测试当成独立验收、真实模型质量或 B5 关闭。

实际共享起点为 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`，未切分支/提交/推送/部署。冻结契约清单已核 SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db`。本实现 11 个源/测试文件的实际逐文件 SHA、停写时点和最后收据绑定见 [SOURCE-MANIFEST-v1.json](SOURCE-MANIFEST-v1.json)，该清单 SHA 为 `1cdd1d49beff30a24f9b3b09c45ec7996c5b6aa021208ae649a5b1b79f1b8498`。

唯一源码写入为新 `apps/api/app/services/lesson_generation/` 六文件，以及新 `lesson_generation_support.py` 和四个 `test_lesson_generation_*.py`。没有写 BE 保存/apply、main、共享 DTO/DDL、任务基础设施、迁移/备份、权威进度或旧 QA。B0～B4 原工作区改动保留。

实现了冻结构造和 prepare、insert_input_in、executor_for/execute、validate_for_apply、revalidate_prepared_refs。输入冻结固定 ready 报告/score/paper/run/inputHash、明确目标班和固定 KP 修订；目标班只投影选定 KP 的计数，绝不采用整个报告 selectionSnapshot 作为单班总数。生产 RagV2 核验教材范围、真实封存文本、散列和定位；题库归属显式注入，正式固定题与已审核练习使用公开固定 reader。contextSnapshot/scopeSnapshot/evidenceRefs 位于 frozen_input 顶层，source 保存受保护的完整来源，modelPayload 另做白名单。

所有入模教学文本、旧过程设计/二次备课、要求、教材/题目/练习文字均阻断报告已知姓名/学号/学生及人次 ID 和明确身份标记。Unicode NFKC/零宽字符检查、短 ASCII 名字的词边界及数字学号的数字边界用于防止偶然字符串碰撞；这只是已知来源的可验证阻断，**不声称全信息匿名**。旧过程 id 只发送 P1..Pn，含已知个人信息或不安全字符的旧 id 用确定性安全 id；模型新环节只用 new:N1..N12。三种真实 provider.complete 的 HTTP MockTransport 捕捉最终序列化 body，验证匿名白名单/单班范围与 tokens 上限。

候选仅有五个 whole fields；教师六字段不能入 patch。4..12 环节、四 phase、每环节整数分钟、精确总时长、每选定 KP 覆盖、真实依据别名、稳定 id 与元数据一一对应、必要 activity/check 都重新校验。未知 key/路径、null 模型字符串、非法 Unicode/分钟/别名、重复 JSON key、NaN、截断、超限一律可见失败，无默认模型/示例回退。输入限制同时核最终 wire 的 128000 UTF-16/256 KiB，输出 256 KiB，tokens 为 min(handle.max_output_tokens,16384)。Anthropic 推理配置若扩张实际 max_tokens 超预算，显式拒绝而不悄改模型设置。

执行器复用真实 model_runtime 句柄指纹及既有 provider、JobEngine 六态/租约/心跳/取消/显式 retry。首轮及 retry 都核冻结指纹。JobOutcome.publish 只 INSERT 不可变候选，JobStore.complete 与候选在同 teaching 事务，失败整体回滚，不提前 succeeded、不修改教案。SQL-only refs 复验禁止 Blob/网络/模型；相同 KP 的不同历史修订分别校验，避免共享 reader 的单调用缓存遗漏第二修订。BE 独占应用事务并调用纯 validator。

最后新单轮 [ai-r8-stable-command.json](ai-r8-stable-command.json)：**81 passed / 0 failed / 0 errors / 0 skipped，exit 0，36843.156 ms，PID 21748，11 源前后 sourceDrift=[]**。测试覆盖三真实序列化协议、PII、非法候选、固定来源/归属/归档、active 成绩改变仍引用原 ready 报告、原已审核练习修订不被后来 current 草稿替换、SQL-only 复验、超时/服务错误、取消、重启 interrupted 后显式 retry、首轮与 retry 指纹漂移/缺失、丢租约、2 次真实心跳、发布触发器故障回滚与重试、input 同事务/hash/owner/model 守卫。真实供应商教学质量未执行。

所有轮次日志、XML、收据和隔离输入均保留，未删除或拼接首败制造全绿：

| label | 单轮结果 | exit / ms / PID | 归因 |
| --- | --- | --- | --- |
| ai-r1-validation | pytest 未执行 | 1 / tool wall 275.911 ms / PID未记录 | runner --source误传目录，源散列前置 PermissionError；原工具输出保留在对话，样本 `zqky-b5-ctrl-ai-r1-validation-914cs4oc` 保留；没有伪造不存在的原 log/XML/source receipt |
| ai-r2-validation | 5 pass / 3 fail / 40 error | 1 / 17939.339 / 25872 | fixture 和实现误认 ModelProtocol values 为下划线；实际为短横线，已修；原全 log/XML/数据保留 |
| ai-r3-validation | 12 pass / 36 fail | 1 / 18188.806 / 28104 | 学号00000与系统提示100000偶然碰撞；按数字边界核并将提示限额写中文。另旧题 explanationMarkdown=null 投影需保留空文本，已修 |
| ai-r4-validation | 45 pass / 3 fail | 1 / 17936.890 / 5036 | 私有 fixture 向 JobStore.create_in 传了不存在的 input_hash 参数；删参数，由真实 JobStore 计算 |
| ai-r5-all | 67 pass / 2 error | 1 / 30119.021 / 14048 | 超长响应直接充当 pytest param id 导致 Windows 临时路径 setup/teardown 失败；改短 param id，未放宽正文预算 |
| ai-r6-all | 77 pass / 2 fail | 1 / 38208.632 / 1968 | 新 source fixture 题目缺 difficulty 导致真实练习审核拒绝；补显式 easy。未审核练习错误主码应为LESSON_INVALID、issue=PRACTICE_NOT_REVIEWED，修私有断言 |
| ai-r7-sources | 11 pass | 0 / 5718.206 / 19132 | source 窄复验 |
| ai-r8-stable | 81 pass | 0 / 36843.156 / 21748 | 当前 11 文件完整单轮，0源漂移；非拼接结果 |

每个已执行 pytest 的完整命令、isolated env、PID、UTC、单轮计数、源 SHA、日志 SHA、保留样本和 cleanup 守卫都在相应 `*-command.json`。新 OS TEMP 在导入 app.main 前设置 ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8/PYTHONIOENCODING，Settings.credentials_file=None；空教材源、Qdrant 16333/embedding 9 配置，实际仅内存向量和 MockTransport，没有正式 6333/Ollama/收费模型调用。最后样本根是 `C:\Users\96022\AppData\Local\Temp\zqky-b5-ctrl-ai-r8-stable-yb8csqiq`。runner 已退出、日志已关；scene finally 关闭 JobEngine、RagV2 和所有 catalog，没有起停共享 TCP/5174。全部临时根保留；没有读正式.env/凭证/.local-data/真实草稿，旧拒删根未触碰。

CTRL 可只读复用稳定 `tests.lesson_generation_support.Scene`：`await Scene.create(root,protocol='openai_chat'|'openai_responses'|'anthropic_messages')`，`scene.prepare()->PreparedGeneration`，`scene.job(prepared=None)` 同事务建 job/input，`await scene.run(job=None)->JobRecord` 经真实执行器发布候选。公开对象为 scene.catalog/lesson/body/rag/verified/practice_scene/analysis；`await scene.close()` 关引擎、RAG 和五个隔离 catalog。实际 lesson/analysis/input/proposal/decision 业务整链与备份 seed 的 application/decision 需使用 BE 已实现的 LessonPlanService，AI helper 不代替 BE apply oracle。

未执行：独立 V00、完整工程 check/API/E2E、浏览器/视觉、完整备份恢复、真实 Qdrant、真实模型质量、Word/WPS、正式数据迁移及压力门禁；这些由 CTRL/独立验收对稳定集成候选另跑，本卡不冒称通过。当前无公共端口缺口，root 的 RagV2/Practice 端口与0010已被实际测试使用；真实主装配、公共 retry HTTP、BE应用与FE链仍待本批集成独立验收。
