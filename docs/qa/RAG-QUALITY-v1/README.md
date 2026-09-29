# RAG-QUALITY v1.1 批次证据（图片清洗 / 紧凑首答 / 证据窗口 / 题库模型 / 备份恢复）

批次：`RAG-QUALITY` v1.1
规格：仓库根 `docs/PLAN.md`；任务卡与文件归属见 [TASK-CARD.md](TASK-CARD.md)
验收基线：`2f27841`（= `eee2799` + 命中率测量脚本）
总控：本会话

## 1. 本批范围与交付

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| C0-CONTRACT | 预算常量单一事实来源（`app/core/rag_budget.py`）、共享模型解析（`model_runtime.resolve_chat_model` + `ChatModelHandle` 唯一实现）、schema 新字段（`readable` / `presentation` / `reasonCode`）、题库 `modelProfileId` 必填 | 完成 |
| B0-TEXT-PROJECTION | 可读文本投影（清洗图片 Markdown、映射回原文坐标、不变量齐全）+ 24 组跨语言样例 | 完成（203 例；含 v1.1 崩溃修复） |
| B1-RAG-ANSWER | 有界证据窗口、`PromptPack` 准入集合、简短首答（≤3 点/≤250 码点）、presenter 只渲染知识点、详解清洗 | 完成（109 例） |
| B2-CLEAN-INDEX | 清洗版本进入分块指纹、块级「原文坐标 + 索引文本」分离、Qdrant 新 payload、BM25 按代取清洗文本 | 完成（143 例；含 v1.1 三项修复） |
| B3-ORGANIZER-MODEL | 题库 AI 整理改回「当前聊天模型」（本地/云端）、async + 有界线程、任务冻结与旧任务不自动恢复、错误分类 | 完成（73 例） |
| B4-BACKUP-RESTORE | 数据根跨进程锁、离线一致性备份（SQLite backup API + 引用文件 + staging + 快照对账 + `status`）、按运行布局恢复 | 完成（24 例） |
| F0-COMPACT-CHAT | 单一消息投影、消除重复展示、来源两级折叠、复制/历史紧凑、历史兼容六行、追问卡精简 | 完成（325 例） |
| F1-ORGANIZER-UI | 聊天模型接线与冻结、云模型提示、错误码文案、去掉 `/rag/status` 依赖 | 完成（85 例） |

## 2. 实施中发现并修复的真实缺陷

都是**真实数据/真实运行**发现，不是静态推断。逐条首败与修复见 `_work/rag-quality-v1/<任务>/RESULT.md`。

| # | 缺陷 | 首败证据 | 修复 |
| --- | --- | --- | --- |
| 1 | **图片清洗器在真实教材上死循环，阻塞正式重建** | 正式重建第一册卡住：100% CPU **21 分钟**、checkpoint 0/58；逐步定位到 `project_readable(321,905 字)` 240 s 未完成；最小复现 `project_readable('4x-5<3\n\n![](images/abc)')`（对照 `'x < 3\n\n![...]'` 正常） | `_parse_html_tag` 属性循环里空属性名时游标不前进；修根因 + 新增 `_step_cursor` 结构性防护（游标严格递增）+ 标签名必须字母开头 + 属性不跨空行；顺带把保护区判定改单调游标（**4.31s → 0.425s**）。修复后 58 册清洗+分块 **12.2s**（最慢 0.60s）（B0 v1.1） |
| 2 | **BM25 在全空词元语料上构造即崩** | `BM25Okapi([[]])` → `ZeroDivisionError`（构造期）；合法语料（纯符号/公式块）会让整条检索以 `RAG_UNAVAILABLE` 失败 | 过滤空词元条目并按同序重建映射；过滤后为空则词法为空、**不构造 BM25、不判不可用**，稠密与 RRF 照常（B2 v1.1） |
| 3 | **`chunk_count` 兜底取不到旧分块集** | 旧口径分块集且无代链接时按新默认指纹查 → 显示 0 块（`assert 0 == 2`） | 改为「该修订最新已封存分块集」（`sealed_at DESC, rowid DESC`）（B2 v1.1） |
| 4 | **整册清洗后为空时草稿仍显示「可提交」** | `canCommit=True, warnings=[], chunkCount=0` → 用户点到注定失败的提交 | 解析阶段算清洗后可用文本；为空则加可读警告 + `canCommit=false` + commit 前以 `NO_INDEXABLE_TEXT`(422) 拒绝（不复用 `DOCUMENT_NEEDS_OCR` 文案）（B2 v1.1） |
| 5 | **验收脚本会改用户配置/建空库** | `verify_retrieval.py` 调 `set_teaching_settings` 落库、脚本 `migrate()` 会建空库 | 新增 `TextbookCatalog.open_existing()` 与 `core.sqlite.open_readonly()`；三个验收/测量脚本一律只读打开，范围改为请求内联传入**不落库**（总控 C1） |
| 6 | **总控驱动脚本漏了「先恢复被中断的重建」** | 强杀重建 worker 后闸门仍指向 running 任务，`begin_rebuild` 直接 `INDEX_MUTATION_BUSY`；而 API 路由是先 `recover_pending_jobs` 再 begin | `scripts/rag/rebuild_index.py` 改为先 `recover_pending_jobs()`（与 API 同序）；孤儿任务被**续跑**而不是死锁（总控 C1） |

## 3. 真实数据结果（旧代 → 新代）

**固定质量集**（`tests/fixtures/rag-quality-set.json`，10 个高一分组 × 2 正向 + 1 边界）：
问题用自然问法；正向标签 = 目标书册 + **锚点短语**，锚点**先对语料校验存在**，
不存在即整份数据集失败（拒绝自证式标签，回应独立验收 Q8）。

**旧索引代**（清洗未入索引，但展示侧清洗已生效）：

```text
29/30 ok；正向 19/20 ok；正向锚点 Hit@5 = 20/20
预算：零越界（≤3 点 / ≤250 码点 / ≤6 条证据 / ≤16000 码点）
正文含原文块 0 条；正文含长 ev-id 0 条（Q1 重复展示已消除）
readable 清洗后仍含图片语法 0 条（原文含图片语法 28 条，属封存切片不改）
唯一 partial 为 Q08，原因码 SUMMARY_INVALID（本地模型输出越界，保留原文）
```

**正式重建与切换**：先离线一致性备份（350 文件 + 1 collection 快照，校验通过），
再以**同 Embedding 身份、新清洗策略**重建新代并原子切换。三代并存（均 `ready`）：

```text
932d34c9  textbooks_3ff98a4b…  10,482 点   批前（旧清洗、旧划分规则）——保留不删
a6eb3569  textbooks_62373e59…  10,477 点   **操作冗余**：我第一次重建被 B0 死循环中断，
                                            重试时脚本先 recover 使该孤儿任务跑完并发布；
                                            内容与最终代相同
42e42518  textbooks_e2cfc638…  10,477 点   ← **当前活动代**（批后清洗）
```

**冗余是我造成的**（`rebuild_index.py` 先恢复后建新任务，没有在恢复成功后提前收手），
多花了一次全量重建（约 13 分钟）。数据无损失，但留下一个重复代；
按计划「保留旧代、不自动清理」未做删除，建议下一批用 cleanup 流程清掉重复代。

**新代结果**（同质量集、同范围、同 Embedding 身份）：

```text
28/30 ok；正向 18/20 ok；正向锚点 Hit@5 = 20/20（与旧代持平，满足计划 ≥18/20 且不低于旧代基线）
预算零越界；正文含原文块 0；正文含长 ev-id 0；readable 清洗后含图片语法 0
2 个 partial 均为 SUMMARY_INVALID（本地模型输出越界，保留原文）
```

**索引清洗的独立核验**（可复算）：取一个含 5 个图片节点的真实块
（`【人教版】高中必修 第一册数学电子课本` ordinal=0，原文 817 字 → 清洗后 407 字）：

```text
Qdrant payload.text_sha256      = 799650e1b118d4efc0dc…   （原文切片，未变）
Qdrant payload.indexTextSha256  = 978e4373316462eded78…   （清洗后嵌入文本）
我独立重算 sha256(project_readable(raw).text) = 978e4373316462eded78…  → **逐位一致**
payload.textProjectionVersion   = rag-readable-v1
两个哈希不同 → 索引/BM25 输入是清洗文本，而引用仍绑定不可变原文切片
```

## 4. 未修复的高优先级发现（交下一批）

**R1（中高）：缺少相关性闸门 —— 范围外问题仍返回 `ok`。**
质量集里 10 个边界问题（范围外/证据不足/依赖图片）**全部返回 `status=ok`** 并给出知识点，
而不是 `no_evidence`/`uncertain`。用户会看到"教材里没有的内容"被当作有依据回答。

原因：检索固定取向量 50 + BM25 50，任何问题都会得到"命中"，概括模型也总能产出点什么；
**没有"证据是否真的回答了这个问题"的判定**。

我做了阈值可行性实测（30 问的稠密 top1 分数分布）：

```text
正向 top1：min 0.577 / 中位 0.704 / max 0.772
边界 top1：min 0.451 / 中位 0.512 / max 0.595   ← 边界最高 0.595 > 正向最低 0.577
```

**两组分布重叠**，简单余弦阈值**不可靠**（要挡下边界就会误伤 Q20「一般现在时…」这类真实问题；
而且阈值是在我自建的小样本上标定的，泛化风险高）。因此本批**没有**shipping 一个零余量的阈值，
而是把它作为实测到的缺口交下一批处理。可行的方向（未实施、未验证）：
把"证据是否切题"交给概括模型显式判定（要求它指出证据如何支持问题，否则返回空 points），
配合"图依赖问题明确回答缺少图中条件"（PLAN §3.5 已有要求，量化验收未做）。

**R2（口径）：单条证据「清洗后 ≤1600 码点」紧于「原文 ≤6000 码点」**，
纯文本教材里"命中块 ±1 邻块"经常超 1600 而退化为整命中块（B1 实测）。
这是计划给定的预算数字，本批**不擅自调整**，如实记录后果。

**R3（边界）：`_release_stale_gate` 只释放"任务缺失/已终态"的闸门。**
被强杀的 `running` 重建任务不会释放闸门，需靠 `recover_pending_jobs` 续跑或 API 路由自愈；
操作侧已按正确顺序规避（见 §2 第 6 条），但"闸门自愈"本身只覆盖终态任务。

**R4（历史数据）**：历史导入草稿没有 `cleanedTextEmpty` 标记，
清洗后为空的老草稿仍由任务层 `DOCUMENT_NEEDS_OCR` 兜底拒绝（文案不是最贴切）。

## 5. 证据索引

| 内容 | 位置 |
| --- | --- |
| 任务卡与文件归属 | [TASK-CARD.md](TASK-CARD.md) |
| 首败：清洗死循环（栈 + 最小复现） | `_work/rag-quality-v1/B0-TEXT-PROJECTION/probe-hang-v11.log`、`_work/rag-quality-v1/probe-hang*.log` |
| 58 册清洗/分块实测 | `_work/rag-quality-v1/probe-scale.log` |
| 质量集（旧代） | `_work/rag-quality-v1/quality-oldgen.json` |
| 分数分布（相关性闸门可行性） | 本文件 §4 R1 表（原始输出见会话记录） |
| 离线一致性备份 | `_work/rag-backups/rag-20260929-130007-pre-clean-generation/`、`_work/rag-quality-v1/backup.log` |
| 新代重建 | `_work/rag-quality-v1/rebuild*.log` |
| 各任务结果卡 | `_work/rag-quality-v1/<TASK-ID>/RESULT.md` |
| 冻结候选 | [FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)（98 文件 + sha256，BUILD_ID `WXHZTQm_Ma2tbqT2sRCUY`） |
| 独立验收报告 | [A1-REPORT-01.md](A1-REPORT-01.md) |

## 6. 总控过程问题（如实登记）

1. **覆盖了上一批的冻结记录**：`scripts/rag/freeze.py` 的输出路径原本硬编码为
   `docs/qa/RAG-REBUILD-v1/FROZEN-CANDIDATE.json`，我在冻结本批时**把上一批的证据文件覆盖了**。
   已从 `eee2799` 恢复为逐字节一致（`git diff` 为空），并改为 `--batch <目录名>` 必填、
   目录不存在即拒绝，杜绝再次写到别的批次。
2. **多跑了一次全量重建**：本批第一次重建被 B0 的死循环中断，重试脚本先 `recover` 使孤儿任务跑完并发布
   （生成 `a6eb3569`），随后又新建并发布了 `42e42518`。内容相同、数据无损，但浪费约 13 分钟并留下一个重复代。
   正确做法应是恢复后先检查目标是否已达成再决定是否新建。
3. **R-15 已按计划修掉**：`tests/integration/chat-live.spec.ts` 的陈旧 selector 按 contract-v1 的新设置页重写，
   `npm run test:chat` 由「13 passed + 1 failed」变为 **14 passed / 0 failed**；
   两处表达方式改变（发现弹窗不再自动关闭、无逐模型「默认」徽标）在结果卡里写明了等价性与原因。
