# B4-T70 v1 作者结果 · ready / stopped

负责人 `/root/g1_resume_e2e`。起点与目前现场均为 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`；G1 已由 CTRL 关闭。本卡仅新增 analysis 服务/仓储/路由、专属 analysis 测试与本目录证据，不写共享 DTO/迁移/main/锁/依赖/权威进度文档，不作 Git 写入。

## 实现事实

接收显式固定 score revision 和参与人次选择，拒重复人次、同学生多个 attempt 和不属本 revision 的身份，返回定位 issues。完整源矩阵缺格/多格/超过满分报 500，不填空。输入包含成绩修订自己的 participant/leaf/cell、原卷固定标题/富题面/全 source blocks/material/assets、正式 KP revision/name/role 和真实 practice mapping。班级按历史 classId，班名永远 null，说明“该成绩未记录班名”。每 participant×leaf 保存一主体证据，全题覆盖 recorded（包括 0）、missing、absent、exempt，富内容按 item 规范化保存；多 KP 不倍计总分。

any_loss_v1 后端计算 needs_consolidation 优先，其次 no_evidence/incomplete/full_credit；informationIncomplete 独立，可与 needs 重叠。班级分母只含该 KP 至少一 recorded 的学生，分子 needs；无有效证据 ratio=null。整卷总分只在全部计分叶 recorded 时存在，每叶只计一次，不按 KP 重加。

创建 job/run/submission 用共享 create_in/execute_command 单事务。稳定请求 hash 不含 submissionId，选择集合排序且不去重；原包 replay 在源读取/资产 IO 之前。同 owner/inputHash 的新 submission 复用原 run/job，包括失败终态，走既有公共 retry，不偷起新任务。计算和资产核字节均在 SQL/publication 锁外。唯一 JobEngine/Registry teaching:analysis uses_model=false；原租约 CAS 同事务发布 participants/items/results/全 evidence、ready 与 job succeeded。取消、过期/旧租约、故障均不能留半报告；输入创建后不可改，ready 子表 INSERT/UPDATE/DELETE 全拒。备注只允许 ready/所属身份，append-only + submission replay。

HTTP 用统一 Page，全字段 camelCase/null，not-ready 409、无服务 503、错误 filter 422 issues、不存在/他 owner 404。T80 公开 read_ready_report 返回完整 run by_alias、originalQuestionRevisionIds、originalQuestionContents、students/classes；surface 字段无学生数据。lineage 通过真实 mappings→practice_items/selections→conversion 的固定 paper/item/practice/owner 复合归属读取，文件卷 null；同固定练习卷后来新建施测仍保留来源。

CTRL 明确后，原题已知 type 原样保留，文件卷未记 type 时省略，绝不填 other。literal 用真实未记 type 的固定卷与另一确记 short_answer 固定卷明确双分支断言；T80 对未知 type 比较是其排除规则，不回写 T70 原事实。最终 fixture 题面严格经 RichContentV2 验证，受管图片是新构造真实1×1 RGBA PNG（确定 header/压缩流/chunk CRC），非文本字节冒作PNG。

## 实际自检与首败

所有输出、stderr（空文件也保留）、elapsed、exit、PID、temp root、argv/env/cwd 分轮保存，见 *-receipt.json；不把多轮计数相加。外层在任何间接 app.main 前设 ZQKY_DATA_DIR 新 temp、ZQKY_ENV=test、PYTHONUTF8=1。后续 r5 起已明确 Qdrant=16333、embedding=127.0.0.1:9、空新 textbook-source、credentials=None；真实 HTTP 用 create_app(settings.credentials_file=None,bootstrap_textbooks=False,SecretStore()) 的进程内 TestClient，无 socket listener。

| 轮次 | 结果 | pytest 耗时 | 原输出与解释 |
| --- | --- | --- | --- |
| pytest-first | 7 failed / exit1 | 0.63s | fixture 调用 store_original 漏必填 media_type/original_name；原stdout/stderr/receipt保留 |
| pytest-r2 | 7 failed / exit1 | 0.97s | fixture 固定标题漏 title_snapshot_source；原日志保留 |
| pytest-r3 | 7 passed / exit0 | 1.03s | 第一组完整业务/回滚/封存自检 |
| pytest-r4 | 16 passed、1 failed / exit1 | 2.38s | QA 预期误认为 expired complete 返回 record；真实 port 抛 LEASE_LOST，修 QA 为精确错误并保零写入断言 |
| pytest-r5 | 19 passed、1 failed / exit1 | 9.30s | HTTP DTO 捕获作者误用 needs_practice；共享 Observation 固定是 needs_consolidation，改自有规则/字面期望，不动 DTO 或业务规则 |
| pytest-r6 | 20 passed / exit0 | 8.30s | 全20k矩阵/100页 HTTP 和故障一起实跑；命令9556ms |
| lineage-first | 1 passed / exit0 | 0.24s | 真 reviewed practice→confirmed paper→conversion mapping→该固定卷后来新施测/成绩→分析；命令1461ms |
| pytest-final | 21 passed / exit0 | 9.07s | unknown/known type 双分支加入后，六专属 test 文件单轮；完整输出保留 |
| pytest-final-r2 | **21 passed / exit0** | **8.53s** | 最终候选：fixture 图片改真实PNG/table cells遵共享契约，并显式 RichContentV2 shape验证后，同六文件单轮；不与前轮合计 |

首轮 receipt 的 command 简述用了 temp 占位，新增 pytest-first-complete-command.json 按原执行工具输入和真实 receipt 补确切 argv，未再执行、未伪补旧日志。早期 receipt.credentials_file=null 是调用方意图，非 Settings.from_env 的实测；CTRL 当时后续修 test env 全局路径为 None。早期只间接导入 global create_app，无 TestClient/lifespan，因此没有读取正式凭证。r4 的 textbook 环境变量曾误写 ROOT，真实配置接受 DIR，r5 起已修；原轮收据不覆盖。没有访问正式 Qdrant/Ollama。

## 性能与完整数据

pytest-final-r2-performance.json：200 学生×100计分叶=20,000主体，100规范化富题面，1000学生KP结果，5班级KP结果；100页每200逐条核 evidenceId 唯一、participant/item完整笛卡尔积、原富题表/公式/图片/共同材料、固定班名null。另实际 HTTP KP筛选4000、participant筛选100、尾页空，无漏页或重复。每轮 performance JSON 都保留，以下只引用最终一轮。

硬件见 hardware.json：Windows11 10.0.26200，Intel i5-14600KF 14核/20逻辑，33382008KiB 可见内存，Python3.12.14。首调用纯 aggregate=10.19ms、同进程第二调用=10.16ms（3s指标）；seed200.00ms、完整固定read77.39ms、accept含read/hash/资产/transaction192.22ms、job纯计算+同txn发布622.06ms、100页HTTP及筛选4462.32ms。纯计算“冷”指此样本首调用，不是声称冷 OS 缓存；HTTP全页没有3s承诺，分别如实计时。

## 资源与待验收

新 temp 分轮全保留，见 resources-final.json；全部作者 pytest 子进程实际 exited，stdout/stderr重定向流由该进程退出后关闭，未新增外部 app/API/frontend/listener。TestClient 的启动/关闭日志只代表进程内 lifespan。既有 conftest 自动生成并清理的本次全新自有 pytest-data 目录沿原测试生命周期，没有枚举或清理未知目录。未操作用户5174、8001服务、正式 .local-data/.env、旧六目录或旧G1 QA；唯一作者 unlink 是 test_missing_asset 的本轮 tmp fixture 自有 image blob，用于有意义故障验证。旧源/他人源均保留。

完整新改文件与 SHA256 见 SOURCE-MANIFEST.json（6产品Python +7专属测试Python +1 QA PowerShell，共14可执行源），证据见 EVIDENCE-MANIFEST.json（不含该manifest自身避免循环）。所有作者源均为新增，没有改其他作者或共享文件。

最终确切命令为 run-tests.ps1 -Label pytest-final-r2 -Targets 六专属文件；真实Python绝对 exe/argv/cwd/env/temp/PID/elapsed/stdout/stderr逐项见 pytest-final-r2-receipt.json。旧各轮输出与失败完整保留。独立 literal oracle/HTTP与闭环浏览器、全量check/API/build/E2E、备份恢复尚未由本作者执行，归 CTRL 后续门禁；本作者通过均为 selfcheck，不是独立验收。**B4-T70 v1 ready，已停止所有产品、测试、可执行QA源与证据写入，等待稳定候选独立验收；不宣称 B4 已完成。**
