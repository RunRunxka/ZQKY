# B5-STORE-RV：后台教案存储复查

日期：2026-10-03。范围为当前 B5-r8 的教案创建、旧稿导入、不可变修订、历史、CAS、提交回执、建议终结、0010 迁移及四库恢复。产品代码、旧 QA、冻结件、权威文档、Git 均未修改；未启动常驻服务或浏览器。

## 结论

本审查范围未确认新的可复现产品缺陷。成功回执优先于后来 CAS 和外部来源检查；正文、固定上下文和修订历史不可变；教师部分选择应用与新修订、当前指针、终结决定、提交回执同教学库事务提交。源码存在与本次窄检查通过不代表全业务、人工教学质量或正式数据演练通过。

## 实际执行

[PYTEST-first.txt](PYTEST-first.txt) 对应单轮 `55 passed`、退出码 0。其中新增独立正确行为 oracle 4 项，既有相关回归 51 项；没有挑取不同轮次的通过项拼接。新增 oracle 在 [test_storage_review.py](test_storage_review.py)，复用四库初始化夹具，但预期正文与命令包由审查者独立构造，不调用生产 merge 来计算预期结果。

执行命令（工作目录 `apps/api`）：

```powershell
$env:ZQKY_DATA_DIR = <新建的隔离临时根>
$env:ZQKY_ENV = 'test'
$env:PYTHONUTF8 = '1'
$env:ZQKY_CREDENTIALS_FILE = ''
uv run python -m pytest ../../docs/qa/TEACHING-LOOP-B5-REVIEW-20261003/storage/test_storage_review.py tests/test_lesson_plans_storage.py tests/test_lesson_plans_proposals.py tests/test_lesson_plans_concurrency.py tests/test_b5_public_foundation.py tests/test_b5_backup_recovery.py tests/test_sqlite_commit_rollback.py -q --basetemp <该隔离根>/pytest
```

实际保留数据根见 [DATA-ROOT.txt](DATA-ROOT.txt)。导入 `app.main` 之前已设置隔离环境；涉及标准装配的既有测试显式使用 `Settings(credentials_file=None)`。未读取正式 `.env`、正式数据根或真实浏览器草稿。

## 核查依据

| 边界 | 源码检查与实际断言 |
| --- | --- |
| 保存与上下文 | `lesson_plans/service.py` 的 `_preflight` 在同一读取快照核回执和当前 CAS；准备失败后再核竞争成功回执；`save_draft` 比较含正文、固定上下文、来源的 hash，同包重放不会倒退当前指针；来源或知识点顺序变化不被正文相同吞掉 |
| 旧稿导入 | 保留完整 v1 DraftEnvelope、旧稳定 process ID 与时间戳；updatedAt 按契约不参与提交身份，重放返回首次原 envelope；不触碰浏览器旧本地键 |
| 部分应用 | 仅替换教师选择的完整字段；未选字段与六个教师控制字段保持原值；未选 process 时不写其分钟 metadata；第一次应用终结候选，第二个提交不能补用未选部分；应用回执在后来另存后仍返回首次结果 |
| 失败原子性 | 在新增修订/指针/decision/receipt 边界注入失败后，正文、版本、历史与回执整体回滚；公共 transaction 对 deferred FK 导致的 COMMIT 失败也执行 ROLLBACK |
| 归属与版本 | lesson/revision/proposal 精确 owner 与文档身份；四列 current revision FK 同时约束 owner、document、version；不同包复用 submissionId 返回冲突，同包并发只创建一个修订与回执 |
| 0010 迁移 | 追加六表，不修改旧 0001～0009；未登记 B5 的合法 B4 库可通过基础门控后迁移；登记 B5 后缺表/索引/触发器或语义 SQL/JSON 路径变化拒绝启动 |
| 四库恢复 | 相关真实恢复测试重新执行 create/verify/restore：六个 B5 表的应用/拒绝/输入/回执行、旧教学行、知识/题库行、教材固定引用与受管资产逐行/散列一致；恢复后标准装配能读取教案与固定教材证据 |

上述四库恢复使用真实临时 SQLite 和 Blob，向量端使用既有 `FakeQdrantServer` 的声明 MockTransport；不称正式 Qdrant 已检验。

## 后续实现注意

`app/core/lesson_schema_gate.py` 当前对已经登记 0010 的库逐个比较 0010 原 CREATE SQL。这能拒绝本批结构损坏，但未来若通过新增迁移合法 ALTER 这些表，其 sqlite_master SQL 会变化。届时须让体检按已登记迁移版本验证合法新结构，并保留 B4/0010 旧版本分支；不能修改已登记 0010 声明或关闭体检来通过。这是未来迁移设计注意，当前不存在后续 ALTER 迁移，不计本批缺陷。

创建无固定学情的教案允许显式 subjectId，当前未单独校验其教材 taxonomy 存在；现行契约没有规定只能使用 taxonomy 的学科，且知识点域支持自定义 subject，因此没有将该现象认定为缺陷。若产品以后要求仅允许词典学科，应先冻结跨模块规则，再增加明确校验与兼容策略。

## 未执行

未执行全量 API/check/E2E、真实浏览器、真实收费模型、Word/WPS 人工排版、实际保存 PDF、正式 Qdrant、正式迁移或超基线压力。本次为只读代码复查及相关窄回归，不重述旧报告结果为新执行。

额外 HTTP 身份复核已在前批被自动审批拒绝；本次未重试该动作，未更换工具、命令、端口或 Agent 绕过。上述 TestClient 出现在既有四库恢复业务测试中，不执行被拒的 HTML/proxy 身份复核。

## 下一阶段建议

存储方面可保留当前六表、v1 正文与 v2 外层契约。下一阶段优先补课堂质量与可追溯证据，以及真实 Word/WPS/PDF 的可用性验收；如正式迁移被明确纳入授权，再做先备份、隔离副本演练、完整性与旧数据对账、可回滚恢复的实际迁移。不要因为技术链通过自动更换数据库、引入第二业务后端或重建既有教案编辑器。
