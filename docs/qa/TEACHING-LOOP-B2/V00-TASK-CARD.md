# TEACHING-LOOP B2 · V00 独立验收任务卡（只读）

- 版本：v1.0；建立：2026-10-01；验收者：独立验收 Agent（只读产品代码）
- 候选：B2 工作树（起点 `main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906`）；冻结指纹见
  `docs/qa/TEACHING-LOOP-B2/FROZEN-CANDIDATE.json`
- 交付：`docs/qa/TEACHING-LOOP-B2/V00-REPORT-01.md`；探针放 `docs/qa/TEACHING-LOOP-B2/V00-probes/`
- 每项 `pass`/`fail`/`not_run` + 命令/退出码/输出摘录/证据路径；`fail` 给最小复现（**不要**替实现者修复）

## 边界

- 只读候选；不改 `apps/**`、`scripts/**`、现行文档、实现者测试、冻结记录；不提交/推送；不改 `.env`。
- **所有探针先设 `ZQKY_DATA_DIR` 指向临时目录再导入 `app.main`**；不读写正式 `.local-data`。
- 模型一律受控替身；不联网；Qdrant 不启动；API 用 TestClient/隔离端点，不占 8001/5174。
- 前端：`NODE_OPTIONS=--no-experimental-webstorage npx vitest run <file>`；不跑 build/e2e（CTRL 组织）。

## 必验项

| 编号 | 内容 | 建议手段 |
| --- | --- | --- |
| V1 迁移与分期 | ①新库/B0 旧库/B1 旧库三路径升级、重复应用幂等、中途失败回滚、`foreign_key_check` 全空；②B0/B1 已登记散列自算与冻结记录一致；③**分期 CHECK**：`source_practice_revision_id`/`active_score_revision_id` 非空写入被拒、`source_file_id` 为空写入被拒；④触发器：`paper_confirm` 各分支（无叶子/总分不符/缺知识点/父容器计分）、`freeze_paper_*`（UPDATE 改归属与 DELETE 都拒）、`paper_cycle_*`、`assessment_confirmed_paper_insert`/`assessment_paper_fixed` | 自写探针（不只用 `test_b2_migrations.py`） |
| V2 T40 导入与草稿 | 块顺序/定位/图片 sha256/OMML 逐字节；规则拆题的父子与分值；PATCH 整表替换（新增/删除/复用 itemId）；题号重复/环/跨卷父/非叶子计分/分值非法（负、3 位小数、容器带分）逐项 422+定位；`expectedRevision` 409+currentRevision；跨库知识点失效 422 | 自写 DOCX 样本（含合并表格/图片/OMML/未知对象）+ TestClient |
| V3 T40 确认与不可变 | 确认闸门逐项拒绝（未归属块/blocking issue/无叶子/总分不符/缺知识点）→ 修正后成功；同 submissionId 重放；确认后**绕过服务**直写 UPDATE/DELETE（items/knowledge/blocks/issues）被拒；改已确认卷建新修订且旧修订逐字节不变；旧施测（若有）仍引旧修订 | 自写探针 |
| V4 T40 AI 建议与 reader | 非法 JSON/截断/未知知识点/未知 item/证据越界；应用前 revision 变化 → stale 409；apply 写入 `ai_confirmed`；reject；`ConfirmedPaperReader` 只放 confirmed（draft/无叶子/零总分 → 422）；publish 注入失败 → 零 proposals | 受控替身 |
| V5 T50 关联与生成 | 草稿关联整表替换、回到 needs_review、确认冻结正式关联且 `subject_id_snapshot` 正确；改内容复制旧关联/改关联替换；按知识点检索；生成链（独立 GenerateReply、非法/截断/未知/虚构证据/URL 路径各一例、同库事务、发布回滚、AI 原件来源）；候选不自动入正式表 | 自写探针 + 既有替身 |
| V6 T50 统一任务 | organize 经 JobEngine（attempt、六态视图、checkpoint 冻结）；model 名额并发上限；取消（queued 立即/running 批间停、迟到不发布）；重启收敛（造 running → reconcile → interrupted → 显式 recover 后 succeeded，且重启不自动重叫模型）；旧 checkpoint → `ORGANIZER_MODEL_RESELECT_REQUIRED` 且 provider 零调用 | 自写探针（含并发计数执行器） |
| V7 T30-b 施测 | draft/不存在/无非空计分叶子 → 拒绝；伪造姓名/学号（客户端快照字段）→ 定位错误；空名单 422；班级范围外/重复班级/不合法日期 422；历史归属不覆盖 `heldOn` → `PARTICIPANT_CLASS_UNCONFIRMED` → 带依据确认后成功且**归属历史未被修改**；同学生跨班重复人工选定；`(施测,学生,人次)` 唯一；补考新增人次且旧记录不变；学生改名/转班后快照不变；幂等重放；批量回滚；**名单→原卷确认→施测**真实链路（用 T30-a/T40 真 API，不只 mock reader） | 自写探针 |
| V8 F10-KP 页面 | 页面端到端（组件测试 + 你自写的最小浏览器/探针验证）：列表/筛选/失败重试、建立更新（409 保留编辑）、导入预览行定位与幂等确认、AI 六态与取消/重试、教材依据不可用文案、卸载停轮询；键盘；390 无页面级溢出；reduced-motion | 定向 vitest + 自写检查（build/e2e 归 CTRL，可引用其证据） |
| V9 声明抽查 | `docs/API.md` B2 节、`PROJECT_GUIDE §13`、`apps/api/AGENTS.md`、B2 任务卡的事实（迁移 id/分期 CHECK/触发器/路由/错误码/六态）与代码一致；`ROUTES.md` 与 `navigation.ts` 的 `/knowledge-points` 状态一致 | 读代码 + 命令 |
| V10 断言有牙齿 | ≥2 处变异实验（自建副本）：例如去掉 `paper_confirm` 的 ITEM_KNOWLEDGE_MISSING 分支、或把生成校验的 URL 正则去掉、或让 `reconcile` 跳过 question 域 → 证明对应用例/探针会失败；还原并复算哈希证明候选未污染 | 变异 + 还原 + sha256 对账 |

## 报告要求

- 开头：`FROZEN-CANDIDATE.json` 逐文件 sha256 复算对账（应 100% 一致；不一致立即 fail 并列出）；
  若存在 `postVerificationDocChanges` 按记录口径处理。
- 逐项命令/退出码/证据；结尾 `observation`、`not_run`（含真实模型/Word-WPS 排版/真实 Qdrant/正式数据迁移）、
  "你最不确定的一处"。
