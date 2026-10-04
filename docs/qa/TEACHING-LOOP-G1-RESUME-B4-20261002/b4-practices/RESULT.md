# B4-T80 v1 · ready，作者已停写

Owner `/root/g1_v00_fe`。实现使用 B4-CONTRACT-v1 / B4-TASK-CARDS-v1 与 CTRL 授权 v1.1–v1.3 共享勘误；完整最终题号语义按 v1.3。2026-10-02 最终单轮自检于 11:46:58–11:47:19 UTC 执行，13 个专属产品/测试 Python 文件及本批 `run_tests.py` 均已停写。结果为**作者自检 ready，待冻结后的独立验收**，不替代 CTRL 的完整门禁或浏览器验收。

## 实现与身份

确切 14 个可执行文件、逐文件 SHA256/字节数及 7 个只读共享接缝的当前 SHA 见 [READY-SOURCES.json](READY-SOURCES.json)。本次未写其他智能体、共享契约、迁移、main、通用资产下载、既有测试、原 G1 audit/v00-fe 原件。

- 新 `services/practices/{__init__,common,selection,exports,conversion,service}.py`。
- 新 `repositories/teaching/practices.py` 和 `api/v1/practices.py`。
- 新 `tests/practices_support.py`、`test_practices_{selection,review_export,conversion,api}.py`。
- QA 执行输入/原始流收据由本批 `run_tests.py` 实际捕获。

API 构造、路由、nullable 字段和响应 DTO 按卡，公共 `JobEngine/JobStore` 及 executor registry 注入，提供 create/list/get/fixed revision/suggestions/CAS draft/review/new revision/export history/fixed asset/convert 全部路由。

正式题的历史修订读取从 shared FixedQuestionReader 获取。建议遍历同学科全部 confirmed 当前题，稳定按未覆盖目标数量、question/revision 身份选择；不会因为默认列表分页漏读。真实 coverage/gaps 返回，无自动生成、无暗中放宽教师约束。`question-surface-v1` 排除原题并查重，已知原题 type 严格匹配；unknown 原题仅比较时展开合法六 type，保留原始报告事实，题面实质差异不误排。

草稿显式整题/节点、sourceBlockIds、父子关系、正式 KP 子集和 Decimal 文本计分；源 stem/options 必须完整分配。完整最终 `node.questionNo` 原样保存，跨所有 selections 校验唯一，不拼接或隐式改号；总 ordinal 按顶层和局部顺序扁平化。节点预览保留 stem/option 分组与键，selection 保存完整富题。CAS 失败不改变草稿。审核题量/目标覆盖及 constraints 仍须满足，缺口要求明确补题/调整。IO、魔数/真实 SHA/媒体核验及受管字节复制位于 publication/SQL 之外，publication 内重读固定题身份/hash/状态与被发布 KP 活动状态，再短事务封存。

审核后的 revision、selection、item、KP 子表更新/删除/新增均有真实 DB 闸门；新草稿复制固定预览与结构为新 ID，旧版内容不变。重放先于当前 CAS、归档与资产读取，requestHash 不含 submission ID；集合次序 canonical，不用时钟定义固定事实。export inputHash 与 JobStore 冻结输入不含 frozenAt，模板显示的 frozenAt 来自不可变 export.created_at；相同完整固定事实的新提交复用历史 export。

DOCX 复用 T10 renderer。显示固定 selection 总分、全部真实 node 完整题号/叶分数，不丢原富题、图、公式、表格/合并单元格。共同材料按完整块内容/表格/公式/段落和图片真实 SHA/媒体/尺寸去重，来源 asset alias 不决定重复，不同 SHA 不合并。整 ZIP 学生版无答案、解析或教师专属图片字节，教师版保留并对缺答案显式标注。导出新字节在锁外，JobOutcome.publish 和公共 lease/attempt/CAS 在同一教学事务发布 file_asset + export_artifact + succeeded，失败/取消不发布逻辑件；失败重试使用原冻结输入。

score_template 必须是本固定练习真实 conversion 的 assessment。接受时读取真实当前 T30 参测人次/attendance/name/number 快照及固定 paper scored leaves，旧 job、重试、下载不刷新名单；新提交若名单变更，得到新 inputHash。前导零和公式形姓名/学号写为 XLSX 字符串，分数为空，固定映射页包含 paper/revision/leaf ID/完整题号/整数满分与参测身份。

conversion 在 submission 外层同一连接/事务中依序创建 practice-origin paper、直接复制 node 原 JSON/题号/ordinal/父关系/qrev/KP、确认 revision、调用真实 T30 create_in、登记 conversion/mappings。locator 包含 practiceRevisionId/practiceItemId。图片注册严格复核 owner、kind、managed blob key、SHA、媒体、字节数，T70 可继续读真实受管资产。任一步失败，paper/assessment/conversion/mapping/asset metadata/submission 均整体回滚；重放返回原身份。实际 T60 XLSX 上传/确认后的 T70 新报告读取真实 FK mappings、固定 question revision 及 practiceItem/revision，来源不依赖字符串猜测。

## 实际单轮自检

最终命令 cwd `H:\备份xuexi\智启课源\apps\api`：

```text
H:\备份xuexi\智启课源\apps\api\.venv\Scripts\python.exe -m pytest tests/test_practices_selection.py tests/test_practices_review_export.py tests/test_practices_conversion.py tests/test_practices_api.py -ra
```

[tenth-command.json](tenth-command.json)：**exit 0；64 passed；20,726 ms wall；pytest 19.48 s；PID 22180 已退出**。一条现有 starlette/anyio deprecation warning 原样保留，未忽略或改断言。

[tenth-stdout.log](tenth-stdout.log)、[tenth-stderr.log](tenth-stderr.log)、[tenth.log](tenth.log) 是实际原始流；stderr 实际为空。该 64 是本单轮 pytest 计数，不把其他轮、资源探针或 root 独立门禁并入。

覆盖包括：ready 来源/目标/owner、重放、61 正式候选全池/greedy/KP 覆盖/去重/缺口/unknown explicit、已知未知原题 type 与实质题面区别、tree/cycle/empty/source/KP/Decimal/CAS、旧 qrev 与当前题分离、归档发生在锁外资产预检之后、review 全子表 DB 封存含 insert、新草稿旧版保全、真实富 DOCX 整包及教师专属媒体隔离、共同材料实际 SHA 去重、资产错误不保存、导出失败/取消/元数据 rollback/重试、真实 roster 时间冻结、公式形字符串、完整题号/换序/多叶 DOCX+模板+固定 paper 一致、同 tx T30 与全 lineage、六种源篡改拒确认、映射写入故障整体回滚、标准 main 全 HTTP 链路/三导出下载/公共 registry retry。

每个直接 service 场景使用实际迁移后 teaching/knowledge/question_bank/textbook 四 SQLite，teardown 独立 PRAGMA integrity_check=ok / foreign_key_check=[]。标准-main API 例使用实际 state、真实数据库和 JobEngine；无 fetch/service/repository 业务替身。

## 首败与后续轮，全部保留

| 轮 | exit / 单轮计数 | wall ms | 真实原因 |
|---|---|---:|---|
| first | 1；38 passed、2 failed、40 teardown errors | 13244 | QA integrity helper 误用 QB.read_connection；QA 模板首项定位；产品转换缺教学图片登记，真实 T70 拒资产 |
| second | 1；44 passed、2 failed | 14238 | QA duplicate tie 误指定非稳定 ID；QA 把 unknown 原题当缺 type 的正式候选 |
| third | 0；46 passed | 14441 | 以上修正；首次实际 service T60 XLSX/confirm→T70 lineage 全过 |
| fourth | 1；46 passed、1 failed | 14535 | 新 standard-main QA helper 误用 KP 字段名 |
| fifth | 1；46 passed、1 failed | 14620 | QA helper 误用未实现 /jobs 路径，应 /workflow-jobs?domain=teaching |
| sixth | 1；49 passed、1 failed | 16273 | QA 下载 URL 已有 /api/v1，被重复前缀 |
| seventh | 1；53 passed、1 failed | 17260 | QA 误依赖未安装 PIL；后改 stdlib 有效 PNG chunk，没有新增依赖 |
| eighth | 0；56 passed | 18754 | 完整实际 main/HTTP/三导出/公共 retry 全过；当时仍是旧题号映射，不能冒称 v1.3 |
| ninth | 1；56 setup errors、1 failed | 5855 | CTRL 新共享 paper trigger 用不存在 practice_item_id；已立即上报，root 修 item_id，未修改共享 DDL |
| tenth | 0；64 passed | 20726 | 最新题号语义和 root 修正后的共享 DDL，完整全部专属例通过 |

各轮 `*-command.json` 与 `*-stdout.log/*-stderr.log/*.log` 原样保留，没有补造缺失首轮源冻结或把首败算为通过。此前没有保存每轮全源冻结清单；READY-SOURCES 是停写后的作者提交身份，后续由 CTRL 冻结并独立复验。

## 复用、资源与待独立项

`tests.practices_support.open_api_scene(root)` 返回上下文 `(app, client, settings)`，标准数据根为 `root/data/{textbooks,knowledge,question-bank,teaching,assets}`。`seed_api_loop(app,client,tag=...)` 保留 runtime/context 给调用者，返回全部 run/score/practice/notes/conversion/three exports/evidence 与四 catalog 绝对路径。只有初始固定原卷和正式题是明确 fixture seed（真实 repo/确认闸门），其余全真实 HTTP/JobEngine；可供 root 新隔离备份/恢复和 browser seed，作者未执行备份或浏览器。

调用者必须在 import app.main 之前设置新 ZQKY_DATA_DIR、ZQKY_ENV=test、UTF8、QDRANT16333/embedding9/空教材，Settings.credentials_file=None。作者所有轮 outer env 满足此要求，未读正式 .env/.local-data/草稿/旧六目录，未启动模型、服务监听、浏览器、build、全量测试、Git。测试原始文件/日志未读取用户数据。

作者未启动任何监听端口；TestClient 是本进程 ASGI 调用，main 生命周期日志中的“监听”不表示创建 socket。所有运行子进程已退出，最后 TestClient/context 已正常退出；ZQKY_DATA_DIR 独立根在各收据中记录并保留。pytest 的 tmp_path 受其既有保留策略管理，本报告不声称所有早期 case 根均永远保留。

锁外 IO 预检/渲染失败或取消时可能留下无 metadata 引用的受管内容寻址 blob，未主动清理未知资产；不会出现成功 artifact 或半件 DB 业务对象。旧 Markdown 文本/公式可明确派生为富块；未定位的 legacy 图片、HTML/Markdown 表格明确要求题库富内容校对，不返回丢图/丢表“成功”。

独立验收、完整 API/check/build/E2E、真实浏览器、root 离线备份恢复均 **not_run by this author**，由 CTRL 后续持冻结候选执行。当前所有本任务产品/测试/可执行 QA 源已停写，RESULT/JSON 为交接证据。
