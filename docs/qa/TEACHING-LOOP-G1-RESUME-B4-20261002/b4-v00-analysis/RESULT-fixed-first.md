# B4-V00-A v1.1 · r2 来源／DDL修复后完整适用复验

本轮独立验收绑定完整新候选 `CANDIDATE-b4-r2.json`，SHA256 `665d4857d7da692c753b813a99f028eaab082b6f32bbd3f48c6171e8bfd4e26b`。CTRL v1.4修改papers.reader内部practice来源标记、scores.service来源完整题号分支与core.migrations.b4来源关系触发器后停写，授权完整A卡受影响复验。虽然分析DTO／聚合未改，仍使用全新样本重新执行，没有把a2通过结果冒充新候选证明。

冻结4个A执行QA原字节不改；沿用手写literal oracle、全部14响应错误变体、8场景和20k门禁。PRE-AUDIT-fixed-first.json与探针candidate-before/after各核 **916项：877产品、34全部可执行QA、5共享契约，0漂移**，next-env原字节未改。

正式命令 `run-probe.ps1 -Candidate <本批顶层CANDIDATE-b4-r2.json绝对路径> -Run fixed-first`；**exit0，8/8完整场景，165真实HTTP，firstFailure=null**。探针14468.063ms，Python进程14785ms。原run-first首败、v1.1单行适配、run-second/a2通过证据均原样保留，未合并单轮计数。

| 全部实际场景 | ms | 本轮核验 |
| --- | ---: | --- |
| base_http_and_wrong_output_oracle | 1385.949 | A900/Bnull/Cnull/D800整数单位（9/null/null/8分），8学生KP、K1 2/3/K2 1/3及2班KP、全12题证据和固定富内容／材料／资产／sourceBlocks，14错误包拒绝；真实202/pending错误／同包重放／异包409／固定输入复用／筛选分页／原始备注／服务缺失 |
| edge_states_and_explicit_retake | 828.740 | 额外loss+missing、全missing／exempt分母0与ratio=null、非法双attempt／重复／外来人次422定位无半件、显式attempt2全1000单位和三证据、完整选择快照 |
| multiple_classes_and_history | 429.499 | 两班四班KP与筛选冲突；改名／学号／班名／转班／KP修订归档／原卷标题／active变更后旧报告逐字段不变和原提交重放、历史className=null |
| damaged_sources_and_atomic_create | 738.400 | 自有缺格／损坏image／缺image真实500且0job/run/submission半件；创建行后故障全事务回滚，恢复原实例方法后完整成功 |
| seal_all_children | 254.403 | 5个ready子表INSERT/UPDATE/DELETE、pending输入／删除／非法ready／ready撤回、备注改删共23明确SQL拒绝；封存报告保持 |
| cancellation_and_publish_fault_retry | 661.952 | 全publish/ready后故障使5子表与ready回滚；真实公共retry同job到attempt2，running cancel抑制已完成晚结果，原包不另建job再公共retry成功，uses_model=false |
| expired_and_original_attempt_cas | 217.140 | 过90秒失效租约complete/heartbeat不能续权，reconcile/retry后原attempt不能写新attempt，当前attempt自行重算并完整封存 |
| scale_200_by_100_all_pages | 9356.216 | 200×100全20k证据、全部100页每页200，全部唯一人次×叶和evidenceId／固定状态分值／路径KP／富面来源核；1000学生KP完整5页、5班KP及筛选、完整选择快照 |

oracle没有生产应用导入或聚合计算。AnalysisScene只复用真实迁移／种子／调度工具，不提供预期。错误变体仅响应JSON深拷贝；故障仅本验收repo实例包装原方法，不改产品／聚合源码。HTTP为真实create_app+自己的catalog/service/JobEngine的TestClient；8001只是base_url，没有启动TCP服务或接既有8001/5174。

## 全规模阶段计时

| 阶段 | ms |
| --- | ---: |
| fixture准备 | 224.897 |
| 完整固定输入读取 | 71.222 |
| 独立新Python进程首个cold aggregate | 21.534 |
| 同进程同输入第二次warm aggregate | 11.601 |
| 真HTTP接受 | 262.698 |
| executor验签／取消检查／计算 | 58.786 |
| 原租约事务内完整publish | 480.262 |
| claim至executor/publish/complete实际job | 726.921 |
| 100页HTTP+全JSON留存+逐条oracle | 6976.912 |
| 剩余学生／班级／筛选HTTP+oracle | 492.835 |

两次纯计算和完整job都低于3秒。100页HTTP用时6.98秒含响应验证、完整JSON落盘和逐条核对，不冒称纯计算耗时。计时子进程PID19984实际调用冻结aggregate并丢弃返回，不作oracle；完整同输入SHA `4749e3cbe2b8add83d48c4f85ab70eb65b2bcf777b08f26c51ee22c0aac9d859`。本轮P独立套件并行，计时如实保留，不套用旧轮较快数据。

硬件收据为Windows11专业版10.0.26200／Intel Core i5-14600KF／14核20逻辑处理器／33382008KiB，现有venv Python3.12.14。冷暖、逐页耗时和原stdout/stderr留存。

## 资源与证据

2026-10-02T12:48:56.3239718Z至12:49:12.5679661Z；launcher PID5232、probe PID19808已退出，计时PID19984同步退出；TestClient全部上下文关闭，无所属监听，启动监听服务0。没有启动／停止用户前端或root服务，没有碰正式数据、旧受保护QA或Git。

新临时根 `C:/Users/96022/AppData/Local/Temp/zqky-b4-v00-a-9279a7dc79b0432d87e013b750e160f8` 保留。app.main／fixture导入前test／UTF8／全新runtime／空教材源／credentials_file=None／Qdrant16333／embedding9／PYTHONDONTWRITEBYTECODE留证。

run-fixed-first共194文件、86,997,648字节。入口：receipt.json、stdout.log、stderr.log、hardware.json；probe/result.json、checks-so-far.json、candidate-before/after.json、http/0001…0165.json、literal-base-full-packet.json、oracle-rejected-wrong-outputs.json、edge/historical/multi-class包、seal-rejections.json、publish-fault/retry-terminal.json、lease-cas.json、scale-frozen-input.json、scale-compute-benchmark.json、scale-timings.json、冷暖stdout/stderr。RESULT-fixed-first.json登记全部原始artifact SHA与8场景结果，不覆盖旧轮。

本A执行源仍为：benchmark_compute.py SHA419385083014d98315bed4be3b90343bbc172fed5d3c3435a7d3d95877845a3e；literal_oracle.py SHAc0af7a439818c3a244a12e82a6ad9f16bbadd6cacaf06ddaf099069997bf93d1；probe_analysis.py SHA464a737b05e4c9ec6ebb1393361c1a126491e999b80a0864fca03a678de7b49f；run-probe.ps1 SHA0b392b7c9557ba975e582fe109598ccce09763cc6331cbe5fdc34597c5dc25fe。

## 适用边界

本轮重新确认r2完整A卡T70行为及新迁移读取固定文件卷的兼容性；练习来源多叶完整题号及新增映射触发器的专属真实回流反例由P卡验证，不据本A三叶文件卷fixture冒称P反例已关闭。T80/P、前端实际浏览器/F、全工程门禁、备份恢复、真Qdrant／真模型质量／Word-WPS／正式用户迁移均非本A执行范围。等待CTRL按P/F及门禁独立证据确认B4最终验收。

结果收口后产品、契约和全部执行QA继续停写。
