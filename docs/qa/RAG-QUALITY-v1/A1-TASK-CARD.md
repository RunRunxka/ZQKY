# A1 独立验收任务卡（RAG-QUALITY v1.1）

```text
任务 ID：RAG-QUALITY-v1 / A1-VERIFY
版本：r1
负责人：独立验收者（只读；不得边验边修）
角色：验收

开始候选：见 FROZEN-CANDIDATE.json（98 文件 + sha256；BUILD_ID WXHZTQm_Ma2tbqT2sRCUY；基线 2f27841）
实现者停止写入：总控确认（本批全部实现卡已停止写入）
独立资源：
  测试前端 5174（构建产物来自冻结候选）
  测试 API 8001（临时数据根，非正式 .local-data）
  测试 Qdrant 16333（compose project zqky-rag-test）——恢复演练用
  正式 Qdrant 6333 只读参考（**不得写入**）
  证据目录 _work/rag-quality-v1/A1/**；结论写 docs/qa/RAG-QUALITY-v1/A1-REPORT-01.md

可读范围：全部产品源码、测试、文档、`_work/rag-quality-v1/**`
可写：仅 docs/qa/RAG-QUALITY-v1/A1-REPORT-01.md 与 _work/rag-quality-v1/A1/**
禁止：修改产品代码/测试/权威文档/锁文件；执行 git 写操作；读写正式 .local-data 与正式 Qdrant；
      为测评修改用户任教配置（脚本已改为只读+请求内联范围）
```

## 必须独立验证的高风险边界

1. **图片清洗进入索引且原文不变**（本批核心）：取一个含图片节点的真实块，独立重算
   `sha256(project_readable(raw).text)`，与 Qdrant payload 的 `indexTextSha256` 比对；
   同时确认 `text_sha256` 仍等于原文切片散列、两者不同；payload 带 `textProjectionVersion`。
   **不接受**只复述我方数字。
2. **不重复展示**：真实 `rag.result`（`points` + `evidence` + `presentation`）渲染后，
   知识点文本在消息流中**只出现一次**；教材原文正文**默认不出现**在消息流里，只在来源面板展开后可见；
   正文不含 `> ` 原文块、不含长 `ev-…` 标识。
3. **预算与状态语义**：首答 ≤3 点 / 合计 ≤250 码点 / 证据 ≤6 条 / 原文 ≤16000 码点；
   有命中但装不下 → `partial` + `EVIDENCE_UNIT_TOO_LARGE`，**不得**报"没有找到教材依据"；
   清洗后无文本 → `uncertain` + `EVIDENCE_TEXT_EMPTY`。
4. **引用只用准入集合**：构造/复现"模型引用了被预算排除的证据 id" → 该点**整点拒绝**（不是删掉非法 id 继续用）。
5. **图片地址不外泄**：可见首答、默认复制、来源预览、送给模型的文本里**不得**出现 `![`/`images/`；
   封存原文切片（`evidence[].text`）**允许**含图片语法（那是不可变原文）。
6. **题库 AI 用当前聊天模型**：`organize` 的 `modelProfileId` 是聊天 profile id；
   本地与云端两种 profile 都能走通（替身）；不存在/不可调用 → 可读错误且**0 次上游调用**；
   认证/限流/网络失败**不得**说成"试题内容无效"；进行中切模型不影响已冻结任务。
7. **备份恢复（必须真的演练，不能只看代码）**：
   - 用自己的隔离数据根与 16333 实例做一次 `create → verify → restore` 全流程；
   - restore 必须生成**应用能读的运行布局**（`textbooks/catalog.sqlite3` 等），
     用 `Settings(data_dir=恢复目录)` 打开能读到活动代与文档；
   - `--isolated-qdrant 6333` 或缺失 → **拒绝**；目标已存在 → 拒绝；清单里路径穿越 → 拒绝；
   - 缺被引用文件 → `status:"failed"` + 非零退出 + **不打印"完成"**；
   - `restore-state` 处于 `incomplete` 时应用**拒绝启动**。
8. **数据锁**：备份在 API 持有锁时返回 `DATA_LOCK_BUSY`（非零退出、不写文件）；
   API 生命周期持同一把锁；进程被杀后锁能再取得（OS 锁不是"文件存在即占用"）。
9. **历史兼容**：旧 v1/v2 聊天消息仍可读、不被误截；`readable` 缺失时降级到原文并标注；
   `/knowledge-bases/[kbName]` 旧登记只读且不参与检索。
10. **视觉与可访问性**：三视口（1440×900 / 1920×1080 / 390×844）在
    `/chat`（真实 RAG 首答 + 来源展开 + 追问卡）、`/knowledge-bases`、`/question-bank`（含校对台）、
    `/settings#embedding`；无横向溢出、键盘可达、`role="alert"`、减少动画生效、**无图片网络请求**。
11. **崩溃类回归**（本批真实踩到过）：确认 `project_readable` 在含不等式 + 图片的真实文本上**不再是死循环**
    （用你自己的输入构造，不要只跑我方给的样例）。

## 必须区分记录的维度

```text
工程检查（typecheck / lint / unit / pytest / build / e2e / test:chat）
受控替身（pytest 与 vitest 的注入替身）
真实 Qdrant（6333 只读参考 + 16333 写入演练）
真实本地 Embedding（bge-m3）
真实本地概括（qwen2.5:7b）
真实所选聊天模型（题库 AI 整理，本地或云端，按你的可用条件）
人工教学质量（默认 not_run）
人工视觉（三视口实测截图 + 你自己的结论）
```

每项 `pass / fail / not_run` + 命令 + 退出码 + 触发条件 + 证据。构建通过、路由存在、截图存在都不是结论。

## 已知边界（我方已如实登记，你需核对真实性）

- **R1 无相关性闸门**：10 个边界问题（范围外/证据不足/依赖图片）在质量集里**全部返回 `ok`**。
  我方实测分数分布重叠（正向 top1 min 0.577 vs 边界 max 0.595），故**未**ship 阈值。请核对并给出你的判断。
- **R2**：单条证据清洗后 ≤1600 码点紧于原文 ≤6000，纯文本教材里"命中块 ±1"常退化为整块。
- **R3**：`_release_stale_gate` 只释放"任务缺失/已终态"的闸门；被强杀的 running 任务靠 `recover_pending_jobs` 续跑。
- **R4**：历史导入草稿无 `cleanedTextEmpty` 标记，仍由任务层 `DOCUMENT_NEEDS_OCR` 兜底。
- 三个索引代并存（`932d34c9` 批前 / `a6eb3569` 我方重复 / `42e42518` 当前活动）。
- 人工教学质量 `not_run`；`chapter_path` 章节标签在真实教材上不完全准确（行号准确）；
  30/58 册未识别习题区（其练习被当正文索引）。

## 输出

1. 报告写 `docs/qa/RAG-QUALITY-v1/A1-REPORT-01.md`：结论（pass / needs_revision / blocked）
   + 逐项 `pass/fail/not_run` + 命令/退出码/证据路径 + 最小复现（若有失败）+ 未验范围 + 你点名的口径问题。
2. 按维度分开记录（见上）。
3. 回报简短总结，并列出你启动/停止的进程与资源（测试 Qdrant 16333 请保持运行）。
