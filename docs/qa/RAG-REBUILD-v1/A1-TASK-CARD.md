# A1-VERIFY 独立验收任务卡（RAG-REBUILD v1.0）

```text
任务 ID：RAG-REBUILD-v1 / A1-VERIFY
版本：v1（r1 验收）
负责人：独立验收者（只读；不得边验边修）
角色：验收

开始候选：由总控在派发时给出（写入下方「冻结候选」段）
实现者停止写入：总控确认
独立数据与资源：
  测试前端 5174（构建产物来自本卡冻结候选）
  测试 API 8001（临时数据目录，非正式 .local-data）
  测试 Qdrant 16333（compose project zqky-rag-test，独立 volume）
  证据目录 _work/rag-rebuild-v1/A1/**；结论写 docs/qa/RAG-REBUILD-v1/A1-REPORT-01.md

可读范围：全部产品源码、测试、文档
可写文件：仅 docs/qa/RAG-REBUILD-v1/A1-REPORT-*.md 与 _work/rag-rebuild-v1/A1/**
禁止：修改产品代码、测试断言、权威文档、锁文件；执行任何写产品数据的命令；git 操作
```

## 必须独立验证的高风险边界

1. **唯一索引权威**：`catalog_state.active_generation_id` 是唯一「当前索引」指针；不得存在第二个模型/索引指针
   （检查 `/textbook-index/status`、`catalog_state` 表、Qdrant alias、`model-config.json`）。
2. **模型空间一致**：查询向量与教材向量必须是**同一** Embedding 配置指纹；换模型后未完成重建前**不得**开始检索新代。
3. **重建失败保留旧索引**：构造重建失败 → 旧代仍可检索、新代 `aborted`、`rebuild_job_id` 释放；
   重建期间删除的教材被标 `skipped_deleted` 且**不被复活**。
4. **范围不串库**：数学 A 版与 B 版同名册、以及不同学科之间互不出现；向量、BM25、邻块扩展使用**同一**范围
   （用真实数据构造：A 版 selection 检索结果中不得出现 B 版书册标题）。
5. **范围变化被拒**：删除书册 / 改分类 / 切换索引代后，用旧 `scopeSnapshot` 继续请求必须 409 `RAG_SCOPE_CHANGED`。
6. **引用绑定不可变原文**：`evidence.text` 必须与规范化文本 `[charStart, charEnd)` **逐字节相同**，
   含公式（`$...$`、`$$...$$`）与 emoji 的样本要覆盖；跨块合并后仍是连续原文切片。
7. **失败不伪装成功**：停掉 Qdrant → 检索报 `QDRANT_UNAVAILABLE`（不得变成 `no_evidence`）；
   停掉 Ollama → `EMBEDDING_UNAVAILABLE`/`RAG_SUMMARY_UNAVAILABLE`；未装配服务 → 503。
8. **详解语义**：详解使用用户所选模型；断开/停止关闭上游；`CONTEXT_TOO_LARGE` 时原题与追问不被截断；
   重启后既有证据仍可详解（不依赖定位缓存）；已删除教材的新详解被拒。
9. **澄清与引导分离**：澄清提交 `submissionId` 幂等（同键同载荷同结果、不同载荷 409）；
   详解引导不占用澄清轮数；「忽略」不调用 RAG reply/cancel/LLM。
10. **追问卡交互**：单选不自动跳题；「继续」才提交；未处理题跳回并提示；「忽略」只跳当前题；
    箭头不确认不清空草稿；`pendingSubmission` 期间锁定且只能用同一载荷重试；IME 组合期间 Enter 不提交。
11. **题库与教材隔离**：题干/答案不得进入教材 collection；AI 建议只是 `pending`，应用前核 `base_draft_revision`；
    编辑已校对草稿回到 `needs_review`；确认入库单事务 + 幂等；未归属原文块必须可见。
12. **历史兼容**：旧 `/knowledge-bases/[kbName]` 本地登记仍可读且**不参与真实检索**；
    旧聊天消息（v1 `rag` 形状）正常可读、不猜造 v2 引用；课程引用不受影响。
13. **视觉与可访问性**：1440×900 / 1920×1080 / 390×844 三视口在 `/knowledge-bases`、`/knowledge-bases/libraries/[id]`、
    `/question-bank`、`/question-bank/imports/[id]`、`/settings#embedding`、`/chat` 无横向溢出；
    键盘可达、焦点可见、异步错误用 `role="alert"`、`prefers-reduced-motion` 生效。

## 必须区分记录的维度

```text
工程检查（typecheck / lint / unit / build / e2e）
受控测试替身（pytest 与 vitest 的注入替身）
真实 Qdrant（16333 测试实例）
真实本地 Embedding（bge-m3）
真实本地知识点概括（qwen2.5:7b）
真实所选聊天模型详解（是否有可用凭证 / not_run）
人工教学质量（默认 not_run，不得用自动断言代替）
人工视觉（三视口实测截图 + 结论）
```

每项输出 `pass / fail / not_run`，附命令、退出码、触发条件与证据。构建通过、路由存在、截图存在
均**不是**验收结论。失败给最小复现交总控，不边验边改。

## 已知边界（实现者已如实登记，不需重复报为缺陷，但需核对真实性）

- 迁移覆盖**57 册**（源目录 58 个书册目录中，`人教A版数学必修第一册` 只有 OCR JSON、无 markdown）。
- 年级归属为**规则推断**（必修→高一、选修/选择性必修→高二），需教师在教材管理页确认。
- 规则拆题属启发式；AI 整理的真实模型形状未联调（单测为替身）。
- 单步耗时超过租约（90 秒）才会失权；正常单册远低于该值。
