# B4-V00-A v1.1 · T70 独立第二轮通过

候选 `CANDIDATE-b4-a2.json` SHA256 `7358ab17ca0d84b285e60e03cef65bd4e24701f8452e882abd95c2a63c57c4a5`；877产品、15可执行QA、4共享契约，共896逐文件身份。PRE-AUDIT-second.json 与 run-second/probe/candidate-before.json／candidate-after.json 均 **0漂移**，next-env原字节。A scope明确不包含正在准备的P/F独立QA。验收者此前为前端作者，本轮仅独立验T70，未参与T70实现。

正式命令为冻结 `run-probe.ps1 -Candidate <本批顶层CANDIDATE-b4-a2.json绝对路径> -Run second`。原 first 候选和44文件、样本、原 probe 字节保持原样；唯一v1.1适配为错误信封通用必填键移除可空details，定位错误的details.issues检查保持严格。第二轮 **exit0，8/8完整场景，165真实HTTP请求，首败null**。

## 实际通过

| 场景 | 用时ms | 独立核验事实 |
| --- | ---: | --- |
| literal与真实HTTP／错误变体 | 1315.067 | A9/Bnull/Cnull/D8分（900/null/null/800单位），8学生KP行、2班KP行，K1 2/3、K2 1/3，全部12证据含满分／missing／absent／0和全固定富题面／共同材料／asset/sourceBlocks；14响应深拷贝错误变体全部拒绝；接受／pending错误／重放／复用／冲突／筛选／分页／历史列表／错误信封／原始备注及服务缺失 |
| 额外缺失／免测／明确补考 | 693.928 | recorded loss与missing同在时need和informationIncomplete同时保留；全missing／exempt为no_evidence、分母0且ratio=null；重复人次／同学生双attempt／外来人次均422字段定位且无半件；显式attempt2全分1000单位、3全证据 |
| 多班与历史保持 | 364.237 | 两固定班4班级KP行，班／人次冲突定位，当前名／学号、班名、转班、KP改名修订和归档、原卷当前标题及active成绩变更后旧报告逐字段完全相同；班名始终null；原提交仍复用原run |
| 损坏源与创建事务故障 | 631.527 | 自有临时缺格、image blob损坏／缺失均真实500错误；0 job/run/submission半件；创建分析行后注入故障整事务回滚，原方法恢复后真实完整成功 |
| 封存全子表 | 218.879 | 五个ready子表各INSERT／UPDATE／DELETE全部明确IMMUTABLE_REVISION；pending输入／删除、非法ready、ready撤回及备注改／删拒绝；23条SQL拒绝证据，报告不变 |
| 发布事务故障／取消／公共重试 | 560.243 | 原真实publish全部写完且ready后注入故障，五子表全部回滚、jobfailed；真实注册公共retry同job到attempt2，全12证据；running cancel拒绝已算完晚结果，原包重放不另建job，公共retry到attempt2成功，不占model名额 |
| 租约与原attempt CAS | 166.295 | 独立时钟过90秒租约；过期complete及heartbeat拒绝，reconcile后重试attempt2；原lease不能写入或覆盖新attempt，当前attempt自行重新执行并完整封存 |
| 200×100全规模 | 8109.172 | 200人、100叶，DB20,000证据；100页HTTP每页200，全部20k唯一组合／ID和固定状态／分值／题号／KP／富题面／来源核；1000学生KP行全部5页、5班KP行，完整选择快照及班／人次／KP筛选 |

literal oracle仅标准库，独立手写预期；fixture复用仅用于真实新DB和实际JobEngine，不提供oracle。错误变体只改响应JSON深拷贝，不改产品。故障仅包装本验收实例的原repo方法，恢复后走原实现及公共HTTP重试；没有改生产源码或聚合实现。

## 规模计时与硬件

| 阶段 | ms |
| --- | ---: |
| 固定样本准备 | 207.860 |
| 完整固定输入读取 | 72.233 |
| 独立新进程第一次冷aggregate | 18.827 |
| 同进程同输入第二次热aggregate | 11.969 |
| 真HTTP创建接受 | 254.076 |
| 实际executor（验签／取消检查／计算） | 58.328 |
| 租约事务内完整publish | 373.984 |
| claim→executor→publish→complete实际job | 606.395 |
| 全100页HTTP+完整JSON留存+每条独立核对 | 6051.301 |
| 剩余5学生页／班页／筛选HTTP+独立核对 | 329.943 |

冷／热计时子进程PID3020，每次调用的生产返回值丢弃，仅计时，未参与预期计算。输入完整JSON SHA `4749e3cbe2b8add83d48c4f85ab70eb65b2bcf777b08f26c51ee22c0aac9d859`。纯计算两次都低于3秒，完整job也低于3秒；HTTP100页6.05秒包含Pydantic响应、JSON完整证据落盘与逐条oracle，不把它冒称为纯计算耗时。

硬件：Windows11专业版10.0.26200，Intel Core i5-14600KF，14核20逻辑处理器，TotalVisibleMemorySize33382008KiB；Python3.12.14现有venv。完整轮探针12436.526ms，Python进程12746ms。硬件、逐页HTTP用时及冷暖原始JSON保留。

## 资源、身份与证据

2026-10-02T12:22:13.6308980Z 至12:22:27.7989462Z；launcher PID16952／probe PID6024已退出，benchmark PID3020同步运行已退出；TestClient所有上下文已关闭。启动监听服务0，无连接既有8001／5174；HTTP日志的8001为TestClient base_url。未启动／停止用户前端、未触碰正式数据／旧受保护QA／Git。

新样本根：`C:/Users/96022/AppData/Local/Temp/zqky-b4-v00-a-4fc60882e3eb4eee85a858bf9e4a1499` 保留。任何app.main或fixture导入前外层test／UTF8／全新runtime／空教材源／Qdrant16333／embedding9／PYTHONDONTWRITEBYTECODE及Settings.credentials_file=None均留证；HTTP使用真实create_app、自己的真实catalog/service/JobEngine和内存SecretStore，无业务HTTP成功mock。

4可执行QA哈希：

- benchmark_compute.py：419385083014d98315bed4be3b90343bbc172fed5d3c3435a7d3d95877845a3e
- literal_oracle.py：c0af7a439818c3a244a12e82a6ad9f16bbadd6cacaf06ddaf099069997bf93d1
- probe_analysis.py：464a737b05e4c9ec6ebb1393361c1a126491e999b80a0864fca03a678de7b49f
- run-probe.ps1：0b392b7c9557ba975e582fe109598ccce09763cc6331cbe5fdc34597c5dc25fe

证据run-second共194文件、86,991,591字节。入口：receipt.json、stdout.log、stderr.log、hardware.json；probe/result.json、checks-so-far.json、candidate-before/after.json、全部http/0001…0165.json、literal-base-full-packet.json、oracle-rejected-wrong-outputs.json、四额外状态包、历史before/after及multi-class包、seal-rejections.json、publish-fault/retry-terminal.json、lease-cas.json、scale-frozen-input.json、scale-compute-benchmark.json、scale-timings.json及benchmark stdout/stderr。结果JSON登记所有原件SHA。

## 验收边界

本轮仅确认冻结a2候选在A卡八场景的T70行为。未执行T80真实练习闭环／导出／转换／备份或前端浏览器；它们由P/F卡独立验收，不据本轮关闭B4。没有验证真Qdrant、真模型质量、Word/WPS版式、正式用户迁移或全工程恒绿。其他卡已登记的产品反例仍由CTRL管理，不被本A通过覆盖。

本轮完成后产品／可执行QA继续停写；等待CTRL确认A验收归档及最终候选适用复验。
