# G1-QB 实现结果卡

任务 `G1-QB v1.1`，负责人 `/root/g1_qb`，2026-10-02。起点 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` 加已保留的未提交 B3-FIX r7；各授权文件起点/当前 SHA 见 [FILE-HASHES.json](FILE-HASHES.json)，总控基线为上级 BASELINE.json。状态 **ready_for_review**：实现者自检通过，产品/测试已停止写入，等待 CTRL 冻结及独立 V00 验收；不把此卡当成“已验收”。仅实施 G1-R07，无 B4 模块开发。

## 实际改动

- `apps/api/app/services/question_bank/fingerprint.py`：新增纯计算 `duplicate_content_fingerprint(content, asset_hashes=None)`，算法常量 `DUPLICATE_ALGORITHM_VERSION = question-surface-v1`。它读取完整冻结 QuestionContent 的题型、按序权威共同材料、题干、选项、公式 LaTeX/原 OMML、表格结构/单元格、图片真实字节 SHA；支持内部 snake_case 与外部 camelCase 富内容。来源、随机块/材料 ID、答案、解析和教师专用图片不成为新题条件。普通段落 rich 与等价旧 plain Markdown 可比；结构化材料/公式/表格/图片不能被降级到丢信息的 plain 投影后判为相同。
- `apps/api/app/services/question_bank/service.py`：导入详情与单草稿响应的只读重复预览、确认计划、`edit_as_new` 和 `link_existing` 共用该身份口径。真重复按既有策略默认跳过或显式合并来源，候选答案仍在草稿，答案差异有教师复核说明，旧正式内容绝不覆盖。不同 1/2 mol/L 权威材料可分别确认。一次确认包内也追踪新题面身份：默认仅创建首题并保留重复说明；显式新题未解决时整体拒绝、零正式写入。确认与正式 PATCH 同事务登记新版本身份，重放优先于新校验。
- `apps/api/app/repositories/question_bank/catalog.py`：同 owner、confirmed 当前修订的新算法候选读取；已登记版本使用明确 `algorithm_version`，缺该版本的旧修订只读计算冻结内容。正式 PATCH 的新题面身份与新修订同事务写入，故障一起回滚。
- `apps/api/tests/test_g1_question_duplicate_identity.py`：新增22条真实 ASGI/临时四库正确行为用例：材料 default/edit_as_new；题干/选项/公式/表格/图片改变；来源/块 ID/答案变化的真重复；旧 plain/旧 rich 缺新指纹的只读兼容；不同存储键同图字节；成功收据先重放；发布与正式 PATCH 故障回滚；等价段落 plain/rich；同包去重/整体拒绝；教师解析图不改变题面身份。
- 授权 `rich.py` **未改动**。沿用已有真实字节/魔数/SHA 校验及 owner/引用限制、明确 null 与投影校验。任务引擎、公共 renderer、共享 contracts、迁移和 schema 未写。

CTRL 在任务卡 v1.1 登记共享测试例外后更新了 `test_question_generation.py` 的一个数量断言：分别核 derived-v1 和 question-surface-v1 各一行、总2；旧内容列、旧算法组成、缺行显式补算与幂等断言保留。该文件不是本实现者写入。

## 指纹比较/存量规则与 T80 交接

旧 `content_fingerprint` 算法、组成、历史列不变；`derived-v1` 算法、组成、历史行不变。新确认或正式 PATCH 只向现有 `question_content_fingerprints` 表追加新算法行，没有迁移/表结构变更、没有清空旧指纹。不同算法的散列不能直接比较；已有新算法值按同版本比较并从冻结内容纯计算复核，缺新算法的旧题以同一纯函数只读重算，不启动资产 IO 或隐式补写。

新请求继续先在 SQL 写事务/PublicationCoordinator 外执行原 `_derived_fingerprint` 的资产/投影预检；短事务只消费原草稿修订及冻结内容。成功 submission 同包重放先于当前资产、知识点与新身份校验；同键异包保持原409。确认和正式 PATCH 的知识点复核/归档保护保持 B3 原临界区，不增加第二把锁。现有 IO/竞态/归档回归实跑通过。

T80 可复用 `app.services.question_bank.fingerprint.duplicate_content_fingerprint`，传入**经正式 reader 取得的固定题修订内容**而非 current/active 指针。输入是完整 validated QuestionContent 映射；新未确认内容的真实资产验证须仍在发布锁外，由调用方先完成，再传真实散列表。历史内容使用其冻结声明/内容寻址键，未知旧资产 ID 沿用明确兼容占位，不称为真实字节 SHA。B4 公共 DTO/迁移/资产或选题修改交 CTRL，未在本任务中实施。

## 实际验证与首败

最终单次合跑 **119 passed、0 failed、0 deselected、1既有 warning，30.31s，exit0**：22新用例 +97既有确认、富内容、发布边界和生成/指纹回归，见 [accepted.log](accepted.log)、[accepted.xml](accepted.xml)、[accepted.exit.txt](accepted.exit.txt)。范围内 `git diff --check` exit0，仅 Git LF→CRLF 提醒，不是空白错误。

旧 R07 材料正确行为探针原文只读执行通过；当次合跑21个新用例+旧材料探针为 **22 passed、4公共任务用例 deselected、1 warning，7.95s，exit0**，见 [final-correct.log](final-correct.log)/[XML](final-correct.xml)。它不与最终119相加计数，也不宣称公共任务问题由此验收。

所有中间失败原文保留：[first.log](first.log) 为本次新算法未读内部富内容编码，11 failed/8 passed，修复后19 passed；[batch-first.log](batch-first.log) 为原计划同包创建两条真重复，2 failed，修复后正确行为通过；[regression-first.log](regression-first.log) 为新增第二算法导致旧总行数断言1失效，96 passed/1 failed，由 CTRL 正式登记改成两算法各一行后最终119全部执行通过。[regression-final.log](regression-final.log) 的118 passed/1 deselected仅是等待CTRL登记的中间收据，不作为最终门禁。每次完整参数、退出码、单次计数、耗时、XML与临时根记录见 [COMMANDS.md](COMMANDS.md)。未删测试、未放宽业务断言、未靠重复直至全绿掩盖首败。

## 未执行/残余边界与资源

not_run：本实现者没有运行全量 API/check/build/E2E、浏览器视觉、真实供应商教学质量、Word/WPS、Qdrant、正式库迁移/数据、压力规模或多进程 PublicationCoordinator。原因是 G1-QB 分配的后端窄修复，自检不替代 CTRL 全量门禁和独立 V00。算法不会猜测不同 LaTeX/OMML 写法的数学等价；不同真实结构保守区分，避免条件被静默丢弃。旧题大量缺新算法时有只读候选重算成本，本任务不冒称全库压力验收。

所有解释器在任何间接 app.main 导入前由 shell 设置全新临时 `ZQKY_DATA_DIR` 与 UTF8；新 ASGI harness 的 Settings 显式 `credentials_file=None`。既有 harness 的 Settings 默认凭证文件为 None，模块默认 app 未启动其正式凭证 lifespan。未读取正式 `.env`/业务库，未连接正式 Qdrant/教材源/真实模型。原审核探针自建的 bootstrap 也是新的系统临时根，未使用旧 policy 拒绝的六目录。

没有创建监听端口、浏览器、外部消息、提交、推送或部署。TestClient 正常退出，测试进程已结束、连接/线程随 harness 和解释器收尾；本批 shell 临时根路径分别登记在 `*-temp-root.txt` 和 `temp-root.txt`，保留脱敏样本，不递归删除未知数据，也未尝试删除旧六目录。产品/测试现在停止写入，仅该分配证据目录的结果卡收口；随后由独立 V00 只读验收。
