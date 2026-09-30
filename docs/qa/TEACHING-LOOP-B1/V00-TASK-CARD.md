# TEACHING-LOOP B1 · V00 独立验收任务卡（只读）

- 版本：v1.0；建立：2026-09-30；验收者：独立验收 Agent（只读产品代码）
- 候选：B1 工作树（起点 `main@301fc356493db21d187ab85f32fd49dfffdc51ef` 的 B0 r2 工作树）；
  冻结指纹见 `docs/qa/TEACHING-LOOP-B1/FROZEN-CANDIDATE.json`
- 交付：`docs/qa/TEACHING-LOOP-B1/V00-REPORT-01.md`；探针放 `docs/qa/TEACHING-LOOP-B1/V00-probes/`
- 结果格式：每项 `pass` / `fail` / `not_run` + 命令、退出码、关键输出、证据路径；
  `fail` 给最小复现与首败证据（**不要**替实现者修复）

## 边界（违反即报告）

- 只读产品代码；探针自建在证据目录；不改 `apps/**`、`scripts/**`、现行文档、实现者测试与冻结记录；
  不提交、不推送、不改 `.env`。
- **所有探针与脚本必须先设 `ZQKY_DATA_DIR` 指向临时目录，再导入 `app.main`/`create_app`**（B0 教训：
  conftest 只保护 pytest 进程，独立脚本必须自己隔离）；不得读写正式 `.local-data`。
- 后端 `cd apps/api && uv run python -m pytest <file> -q`；前端定向 `NODE_OPTIONS=--no-experimental-webstorage npx vitest run <file>`。
- 不联网；模型一律受控替身；Qdrant 不启动。

## 必验项

| 编号 | 内容 | 建议手段 |
| --- | --- | --- |
| V1 迁移与门控 | ①新库应用 B1 迁移后新表齐备（知识点 7 表 + 教学 5 表，含触发器与部分唯一索引）；②"仅 B0 结构"的旧库**通过启动门控**（不判损坏），迁移后补齐；③重复应用幂等；④中途失败整体回滚；⑤`0001` 四个散列与 B0 记录逐字节一致（自算 `statement_digest` 或读正式库 `schema_migrations` 只读对比）；⑥损坏库仍被拒 | 自写探针（不复用 `test_b1_migrations.py` 的断言） |
| V2 知识点 CRUD/父树 | 创建/读取/列表分页；改名追加修订且旧修订不可变；`expectedRevision` 冲突 409 带 `details.currentRevision`；同 code 409；跨学科父/自指/环/缺父可定位；归档后新引用被拒；别名规范化与跨点同名只 warning | 自写探针或 `TestClient` + tmp 数据根 |
| V3 表格导入与确认 | XLSX/CSV 各一；自动与手工映射；预览持久化（行/issues）；阻断问题拒绝且**零写入**；确认成功（created/updated/ignored、批内父节点拓扑）；同 `submissionId` 重放返回原结果且不重复写；apply 失败整批回滚；空白不清空 vs `clearFields` 清空 | 自写探针 |
| V4 AI 候选 | 非法 JSON/未知引用/截断/配置失效/取消迟到各一例；候选只进 `source="ai"` 待确认批次（正式表零新增）；任务 succeeded 与候选写入同库同事务（可在 publish 中注入失败验证回滚）；教材证据不可用 → 503 且不建任务 | 受控替身（可参考 `tests/test_question_bank.py` 的 FakeLLMProvider，但断言自写） |
| V5 名单 | 0012 前导零；无学号/同名/重复行/姓名不符的建议分类；未给决定 → 422 逐行定位；重复行未消歧 → 422 且零写入；`link` 缺 studentId / `create` 带 studentId → 422；确认成功建立归属；**未出现的学生不动**；转班保留旧归属；重放幂等；整批回滚 | 自写探针 |
| V6 富内容解析 | 段落/表格合并单元格（rowSpan/colSpan）/图片（字节 sha256 与 `assets[].sha256` 一致、可读回）/OMML 原样（与原件 XML 相同）/未知对象进 issues/块顺序与定位；共同材料分组正确 | 自写样本 DOCX（**不要**直接用实现者样本，自己构一个含合并单元格+图片+公式的最小样本） |
| V7 富内容渲染 | 渲染产物可被 python-docx 重新打开；student 版无答案与解析、teacher 版有；共同材料只出现一次；图片关系新建（源文档 rId 集合与产物 rId 集合不相交）；OMML 节点存在；LaTeX-only 经 math2docx；非法 LaTeX → 422 `FORMULA_CONVERSION_FAILED` | 自写探针 |
| V8 施测契约 | `POST /api/v1/assessments` 返回 501 `FEATURE_NOT_IMPLEMENTED`（不是 200/空对象）；`UnavailablePaperReader` 抛 501 `PAPER_READER_UNAVAILABLE`；契约类型字段与 `docs/API.md` 一致 | HTTP + 直接调用 |
| V9 声明抽查 | 抽查 `docs/API.md` B1 节、`PROJECT_GUIDE §12`、`apps/api/AGENTS.md`、B1 任务卡的事实性声明（表名/错误码/迁移 id/依赖版本/门控语义/公开路由）与实际代码一致 | 读代码 + 命令 |
| V10 断言有牙齿 | 至少 2 处变异实验（在你自己的副本里）：例如把环检测触发器判定、或 `expectedRevision` 校验、或 student 版答案过滤去掉，证明对应用例/探针会失败；还原并复算哈希证明候选未污染 | 变异 + 还原 + sha256 对账 |

## 报告要求

- 开头：`FROZEN-CANDIDATE.json` 逐文件 sha256 复算对账（应 100% 一致；有差异立即 fail 并列出）。
- 每项结论 + 命令 + 退出码 + 输出摘录 + 证据路径；未执行写 `not_run` 与原因。
- 真实模型调用、真实 Word/WPS 排版检查、真实 Qdrant、真实 DOCX/XLSX 业务文件均 `not_run`（本批无此环境/授权）。
- 结尾：`observation` 列表、`not_run` 列表、以及"你最不确定的一处"。
