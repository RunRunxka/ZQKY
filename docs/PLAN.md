# RAG-QUALITY v1.1：验收结论与详细整改计划

## 一、验收结论与本次目标

**本轮结论：需要整改（needs_revision）。**

SQLite 教材目录、Qdrant、任教范围隔离、独立题库等基础实现已经落地，现有自动化检查能够通过。但你反馈的图片链接和回答过长，均是可以从代码和样本中确认的问题；另外发现了证据预算、备份恢复和题库模型选择方面的缺陷。

本轮进行了只读检查，没有修改业务代码、正式教材或向量数据。检查结束时工作区干净。

### 1.1 本轮实际验证范围

| 检查 | 本轮结果 |
|---|---|
| 当前代码基线 | `2f27841`；相对交付提交 `eee2799`，仅增加检索命中率测量脚本 |
| 冻结候选核对 | 重新计算清单中 205 个文件的 SHA256，与当前文件一致 |
| 后端 pytest | **574 passed**；1 条第三方弃用警告 |
| 前端 Vitest | **69 文件、575 passed** |
| TypeScript | **通过** |
| ESLint | **通过，0 警告** |
| 图片、长度、预算边界 | 代码审查、纯内存探针和历史真实样本重新统计 |
| build、e2e、test:chat | **本轮未重跑**；上一批结果不能算成本轮结果 |
| 真实模型完整链路、浏览器视觉、人工教学质量 | **本轮未重新验收** |

上一批报告中的 `test:chat` 失败仍属于未关闭项，不能把整体状态写成“全部测试通过”。

### 1.2 已确认的问题

| 编号 | 问题 | 证据与影响 |
|---|---|---|
| Q1 | **知识点和原文重复展示** | 后端 [presenter.py](/H:/备份xuexi/智启课源/apps/api/app/services/rag_v2/presenter.py:33) 已拼接知识点和全部原文；前端 [Message.tsx](/H:/备份xuexi/智启课源/apps/web/src/features/chat/Message.tsx:240) 又展示完整依据面板，造成第二次展示。 |
| Q2 | **图片 Markdown 进入模型和界面** | 原文未经清洗进入检索、概括与详解；[RagEvidencePanel.tsx](/H:/备份xuexi/智启课源/apps/web/src/features/chat/RagEvidencePanel.tsx:85) 又把 Markdown 直接作为纯文本显示，因此图片路径和公式标记原样露出。 |
| Q3 | **证据扩展没有实际窗口限制** | [evidence.py](/H:/备份xuexi/智启课源/apps/api/app/services/rag_v2/evidence.py:169) 沿同章邻块持续扩展。探针中一个 800 字命中扩成 40,800 字，随后因超预算被整段丢弃，最终返回零条证据。 |
| Q4 | **首答缺少总长度约束** | 每个知识点允许 4,000 字，没有知识点数量和总字数限制；纯内存探针可通过 100 个知识点。 |
| Q5 | **允许引用未实际提供给模型的证据** | [summary.py](/H:/备份xuexi/智启课源/apps/api/app/services/rag_v2/summary.py:484) 使用全部证据校验引用，而不是预算打包后实际进入提示词的证据。替身探针确认可接受被排除的引用。 |
| Q6 | **恢复目录不符合应用读取布局** | [backup.py](/H:/备份xuexi/智启课源/scripts/rag/backup.py:205) 恢复成 `sqlite/`、`files/`；应用读取的是 `textbooks/`、`question-bank/`。按照脚本提示启动会找不到已恢复的数据，并可能创建空库。备份还遗漏教材草稿所需的 `staging` 文件。 |
| Q7 | **题库 AI 模型策略偏离原计划** | `modelProfileId` 实际被当作 Ollama 模型名称使用。你本轮已确认：恢复为当前聊天所选模型，可为本地或云端。 |
| Q8 | **现有质量测量不足以证明回答质量** | 新测量脚本实际按任教范围检索，却标为“全库竞争”；章节标题自生成问题和自标签不能替代真实题目金标集。 |

图片与长度不是少量偶发样本：

- 重新统计历史四科 12 问：**每问都是 20 条证据，原文合计 17,377–33,812 字符**。
- **9/12 问的回答前 600 字符已经出现 Markdown 图片链接**。
- 对 58 份规范化教材做只读语法扫描，全部含图片 Markdown；识别到约 **12,601 个内联图片节点、100 个 HTML 图片标签**。这些语法约占全文字符的 12%，该数字是语料统计，不是每次回答占比。

### 1.3 本轮已确认的产品决定

1. **首答最多 3 个知识点，目标约 150–250 字。**内容简单时允许更短，不为凑字数补充背景。
2. 首答保留必要公式、适用条件和简短引用编号。
3. 教材原文默认折叠，详细讲解由用户追问触发。
4. Embedding 始终使用本地模型；本地概括保持现有本地模型路径。
5. 题库“AI 整理”使用点击时的当前聊天模型，本地或云端均可；结果仍需人工审阅、应用和确认入库。

---

## 二、目标体验与接口契约

### 2.1 首答界面

默认展示结构：

```text
教材知识点                         高二 · 数学 · 人教A版

1. 空间向量数量积
   a·b = |a||b|cosθ，可用于求夹角及判断垂直。[1]

2. 垂直判定
   对两个非零向量，a·b = 0 时二者垂直。[1][2]

查看教材依据（2 条） ▸

┌ 继续追问  你想进一步了解哪一步？                ‹ 1/1 › ┐
│ 1. 解释公式与适用条件                                   │
│ 2. 结合这道题讲解思路                                   │
│ 3. 输入你的问题……                                      │
│                                      跳过    继续       │
└────────────────────────────────────────────────────────┘
```

固定行为：

- 知识点只展示一次。
- 显示 `[1]`、`[2]`，不把长 `ev-...` 标识暴露为主要阅读内容。
- 点击引用编号，展开对应来源并定位；不请求模型。
- 展开“教材依据”后，先显示书名、版本、定位和短预览。
- 单条原文需要再次点击才能展开。
- 原文中的公式使用现有 KaTeX 渲染。
- “人工教学质量尚未验收”等工程状态保留在验收文档或能力说明中，不作为每条回答的固定尾注。
- 追问卡合并重复标题和介绍，保留截图中的标签、题干、分页、选项、输入和底部操作。
- 不改变选择不自动提交、IME 输入保护、草稿保留、重试幂等语义。

### 2.2 三种文本必须明确区分

| 文本 | 用途 | 是否可变 |
|---|---|---|
| 封存原文 | 来源验证、原始坐标、历史引用重建 | 不可变 |
| 清洗文本 | Embedding、BM25、模型上下文、来源预览 | 按清洗版本派生 |
| 简短回答 | 用户首答、默认复制、后续历史投影 | 按回答策略生成 |

**不能直接删除封存原文中的图片 Markdown。**否则已有 SHA256、行号、字符位置和历史引用都会失效。

### 2.3 兼容性接口

继续使用现有 RAG v2，不重做 SSE 协议。新增可选字段，旧消息仍可读取：

```ts
interface EvidenceReadable {
  version: 'rag-readable-v1';
  text: string;                 // 已清洗 Markdown，保留公式和正文结构
  removedImageCount: number;
}

interface TextbookEvidence extends EvidenceRef {
  // 现有字段全部保留：
  text: string;                 // 仍然是可逐字验证的封存原文切片
  // title、locator、chapterPath、isSuperseded 等不变

  readable?: EvidenceReadable; // 新服务端必须提供；旧历史允许缺失
}

interface RagPresentation {
  version: 'compact-v1';
  answerStyle: 'brief';
  bodyCharCount: number;
}

interface RagResultV2 {
  // 现有字段不变
  presentation?: RagPresentation;
  reasonCode?: string;
}
```

约束：

- `EvidenceRef`、`scopeSnapshot`、原文哈希、原始字符区间不改。
- `readable.text` 不能作为客户端回传的可信证据。
- 详解仍只接受引用，由后端重建原文、核验并清洗。
- 新字段同步更新后端 schema、前端类型和运行时校验器。
- 保持 `rag.result`、正文和事件游标原子持久化。
- `text.delta` 改为简短正文，兼容旧客户端；新前端不再同时展示这份正文与结构化知识点。

---

## 三、后端实现：清洗、证据窗口与简短回答

### 3.1 清洗器：派生文本，不修改原文

新增共用文本投影模块，服务于索引、检索上下文、概括、详解和来源展示。

本批不新增 OCR、图片识别、图片下载或远程图片代理。

清洗规则：

| 输入 | 处理 |
|---|---|
| `![](images/hash.jpg)` | 删除整个图片节点 |
| `![加速度与力关系图](...)` | 保留有意义的说明文字，删除图片地址 |
| 引用式图片 `![说明][fig1]` | 解析引用后按同样规则处理 |
| 图片引用定义 | 仅被图片使用时删除；普通文字链接仍使用时保留 |
| `<img>`、`<picture>` 图片内容 | 删除图片元素及地址；保留有意义的 alt |
| 点击图片的外层链接 | 若删除图片后无文字内容，一并删除空链接 |
| 空 alt、文件名、路径、长哈希、泛化占位词 | 不作为说明文字保留 |
| 图片下方正文图注 | 保留 |
| 数学公式、表格、正文、普通文字链接 | 保留 |
| 代码围栏、行内代码中的字面示例 | 不误当成实际图片节点 |
| 清洗后仅剩空白的片段 | 不作为文本检索证据 |

采用有状态扫描器识别删除区间：处理转义、嵌套括号、引用定义、代码和数学保护区。不得用一个贪婪正则直接替换整篇 Markdown。

```python
@dataclass(frozen=True)
class TextProjection:
    version: str
    text: str
    source_segments: tuple[SourceSegment, ...]
    removed_image_count: int


def project_readable(raw: str, *, absolute_start: int = 0):
    protected = scan_code_and_math_ranges(raw)
    definitions = scan_reference_definitions(raw, protected)
    images = scan_image_nodes(raw, definitions, protected)

    replacements = []
    for node in images:
        replacement = meaningful_alt_or_empty(node.alt)
        replacements.append(
            Replacement(
                raw_start=node.start,
                raw_end=node.end,
                replacement=replacement,
            )
        )

    projection = apply_replacements_with_source_mapping(
        raw,
        replacements,
        absolute_start=absolute_start,
    )
    return normalize_blank_lines_only(projection)
```

实现不变量：

```python
assert immutable_text_before == immutable_text_after
assert raw_sha_before == raw_sha_after

for segment in projection.source_segments:
    assert segment.references_original_codepoint_offsets()
```

Python 和 TypeScript 均按 Unicode 码点定义计数；前端不能直接用 UTF-16 的 `string.length` 冒充后端码点数。

同一组 JSON 样例用于验证前后端清洗结果。前端清洗只承担旧历史兼容，后端仍是新结果的权威来源。

### 3.2 清洗进入索引，使用新索引代

仅在界面隐藏图片不能解决向量和 BM25 中的噪声，因此本批包含一次**同模型、不同清洗策略的新代重建**。

具体决定：

- 新策略增加 `textProjectionVersion: "rag-readable-v1"`。
- 历史缺失字段按 `raw-v0` 解释。
- 历史策略重新序列化时保持旧格式，不能改变旧指纹。
- 未知清洗版本明确报错，不能默认套用新规则。
- 新分块仍记录原文区间，`text_sha256` 仍验证原文切片。
- 图片清洗后完全为空的块在生成分块清单时排除，不留下“有块无向量”的计数差异。
- 仅含有效公式的块不能被当成空块删除。
- 新向量输入和新代 BM25 使用同一清洗策略。
- Qdrant payload 增加清洗版本和索引输入文本哈希，原有原文哈希字段含义不变。

```python
raw_piece = normalized_text[chunk.start:chunk.end]
assert sha256(raw_piece) == chunk.text_sha256

projection = project_by_generation_policy(raw_piece, generation.policy)

if projection.text.strip() == "":
    # 在构建 chunk manifest 阶段排除，而不是 upsert 阶段偷偷跳过
    exclude_from_new_chunk_manifest()
else:
    vector = embed(
        profile.document_prefix + projection.text,
        truncate=False,
    )
    upsert(
        deterministic_point_id(generation, chunk),
        vector,
        payload={
            **existing_payload,
            "textProjectionVersion": projection.version,
            "indexTextSha256": sha256(projection.text),
        },
    )
```

BM25 缓存键包含索引代和清洗版本。旧代继续使用其登记的策略，新旧代不能混用词法文本。

重建沿用现有租约、写入闸门、断点恢复、对账和单指针发布机制。失败或取消时保留旧活动代；不就地改写旧 collection。

### 3.3 有界证据窗口

保留向量 50、词法 50、RRF 的召回入口。本批不通过简单缩小召回数量掩盖问题。

首答证据采用以下固定预算：

| 项目 | 默认值 |
|---|---:|
| 返回首答证据 | 最多 6 条 |
| 邻块扩展 | 左右各最多 1 块 |
| 单条证据清洗后长度 | 最多 1,600 码点 |
| 首答入模证据总长度 | 最多 6,000 码点，且不能超过模型实际预算估算 |
| 单条原文切片 | 最多 6,000 码点 |
| 首答原文证据总量 | 最多 16,000 码点 |
| 历史详解请求兼容上限 | 保留现有 20 条引用及原有硬限制 |

实施顺序：

1. 从排名靠前的命中块开始。
2. 裁到当前允许的正文区间。
3. 同修订、同章节、同区域内，尝试左右各补一个块。
4. 合并重叠窗口；不得合并成超过预算的大段。
5. 超长块按完整段落或句子选取命中附近窗口，不能从公式、表格行、代码块中间截断。
6. 单个受保护单元本身过长时保留定位，报告无法完整装入；继续尝试其他候选。
7. 清洗后为空则跳过，继续考察后续候选。
8. 按排序和总预算选取最多 6 条。

```python
def select_evidence(candidates, frozen_scope):
    selected = []
    saw_text_hit = False
    oversized_units = []

    for candidate in candidates:
        seed = verify_and_clip_to_body(candidate, frozen_scope)
        if seed is None:
            continue

        saw_text_hit = True
        window = bounded_window(
            seed,
            left_neighbours=1,
            right_neighbours=1,
            protected_boundaries=True,
        )

        for span in fit_window_without_breaking_units(window):
            raw = read_and_verify_immutable_span(span)
            readable = project_readable(raw, absolute_start=span.start)

            if not readable.text.strip():
                continue
            if not fits_single_evidence_budget(raw, readable):
                oversized_units.append(span.locator)
                continue

            selected = add_or_merge_within_budget(selected, span, readable)
            if len(selected) == 6:
                break

        if len(selected) == 6:
            break

    if selected:
        return EvidenceSelection(selected)

    if oversized_units:
        return partial("EVIDENCE_UNIT_TOO_LARGE", locators=oversized_units)

    if saw_text_hit:
        return uncertain("EVIDENCE_TEXT_EMPTY")

    return no_evidence("NO_MATCH")
```

**有命中但因预算无法使用，不能再返回“没有找到教材依据”。**

### 3.4 首答长度与引用验证

固定规则：

- 最多 3 个知识点。
- 单点标题和说明合计不超过 90 码点。
- 所有点标题和说明合计不超过 250 码点。
- 目标 150–250 字，不设置最低字数门槛。
- 长引用 ID、Markdown 格式符不纳入用户正文计数；公式源码纳入码点预算。
- 每点最多引用 2 条证据。
- 不输出完整解题过程，不追加教材原文。
- 不用字符串截断处理公式或半句话。
- 本地概括默认 `num_ctx=8192`、`num_predict=1024`，预算统一由这两个参数计算。
- 模型超长、重复或格式错误时最多修正一次；不能无限重试。

`PromptPack` 必须返回真实准入集合：

```python
@dataclass(frozen=True)
class PromptPack:
    prompt: str
    admitted_evidence_ids: frozenset[str]
    admitted_evidence: tuple[TextbookEvidence, ...]
    skipped_evidence_ids: tuple[str, ...]
```

生成流程：

```python
pack = pack_clean_evidence(
    question=question,
    evidence=selected_evidence,
    max_evidence_chars=6000,
    model_budget=summary_budget,
)

proposal = local_summary_model(pack.prompt)

for attempt in range(2):
    checked = validate_proposal(
        proposal,
        allowed_ids=pack.admitted_evidence_ids,
        max_points=3,
        max_point_chars=90,
        max_total_chars=250,
        max_refs_per_point=2,
        reject_image_nodes=True,
    )

    if checked.valid:
        return checked.points

    if attempt == 0:
        proposal = local_summary_model(
            correction_prompt(
                original_question=question,
                same_evidence=pack.admitted_evidence,
                violations=checked.violation_codes,
            )
        )

# 保留完整、合法且能装入预算的知识点，不截断单点
points = choose_complete_valid_points(checked, total_budget=250)
if not points:
    return partial("SUMMARY_INVALID", evidence=selected_evidence)

return partial("SUMMARY_PARTIAL", points=points, evidence=selected_evidence)
```

引用约束：

```python
for point in proposal.points:
    if not point.evidence_ids:
        reject(point)

    # 整个点拒绝，不能仅删掉非法 ID 后继续使用可能依赖它的内容
    if not set(point.evidence_ids).issubset(pack.admitted_evidence_ids):
        reject(point)
```

网络或模型不可用继续保留现有明确错误语义；不能伪装成成功的短答案。

`prompt_eval_count` 只作为诊断信号。验收文案使用“样本未观察到窗口饱和”，不再写“这个数字证明绝未截断”。

### 3.5 详解路径

详解继续使用用户主动选择的聊天模型，不套用首答的 250 字限制。

但必须：

- 重建原文后使用同一清洗器。
- 不把图片地址送入模型。
- 不重复粘贴全部原文作为回答。
- 保留必要的公式和教学步骤。
- 如果问题依赖图中信息，而文本无法提供，明确指出缺少图中条件；不能依据文件名猜图。
- 继续保留删除检查、历史修订提示、上下文预算、取消传播和服务端来源核验。

---

## 四、前端实现：单一正文、折叠来源与历史兼容

### 4.1 建立统一消息投影

显示、复制和后续上下文使用同一个投影入口：

```ts
function projectMessage(message: ChatMessage): MessageView {
  if (isRagResultV2(message.ragResult) && !message.ragExplain) {
    return projectCompactRag(message.ragResult);
  }

  return {
    kind: 'markdown',
    markdown: message.content,
    copyText: message.content,
    historyText: message.content,
  };
}
```

结构化 RAG 分支：

```ts
function projectCompactRag(result: RagResultV2): RagMessageView {
  const evidence = result.evidence;
  const readable = evidence.map(resolveReadableEvidence);
  const points = selectCompactDisplayPoints(result.points);
  const citations = numberCitationsByFirstUse(points, evidence);

  return {
    kind: 'rag',
    points,
    citations,
    sources: readable,
    status: result.status,
    userNotice: mapResultNotice(result),

    copyText: renderPointsWithShortSources(points, citations),
    historyText: renderPointsWithShortSources(points, citations),

    sourcePanelInitiallyExpanded: false,
  };
}
```

具体修改：

- `Message` 的结构化首答分支只渲染 `RagAnswer`。
- `RagEvidencePanel` 只负责来源，不再渲染知识点。
- `ragResult.evidence` 为结构化来源事实，`ragEvidence` 仅承担旧数据兼容。
- 默认复制内容为简短知识点和紧凑出处，不包含整段教材原文。
- 单条来源提供独立“复制摘录”，复制清洗后的完整摘录。
- 后续普通聊天历史和详解历史均使用同一投影。
- 消除 `asks?.length` 决定是否走投影的旁路。
- 不改变普通聊天、详解正文的内容处理规则。

### 4.2 来源交互

来源面板两级展开：

```text
查看教材依据（3 条）
  ├─ [1] 书名 · 版本 · 第 xx–xx 行
  │      最多 160 字的完整句预览
  │      展开摘录 / 复制摘录
  ├─ [2] ...
  └─ [3] ...
```

规则：

- 预览在完整句或结构边界结束；不能截半个公式。
- 找不到合适短预览时，只展示标题和“展开摘录”。
- 点击 `[n]` 展开来源面板及对应条目，并移动焦点。
- 教材历史修订提示保留在对应来源上。
- 图片清洗造成信息缺失时，在来源展开区显示一次简短提示，例如“已省略图片，未识别图中内容”。
- 不启用图片网络加载。
- RAG 专用 Markdown 渲染使用“省略图片”策略，普通聊天的渲染行为不变。

### 4.3 历史消息兼容

| 历史情况 | 行为 |
|---|---|
| 有完整 `ragResult` 的旧 v2 首答 | 即时使用新投影，不改 IndexedDB 原记录 |
| 旧知识点本身很长 | 优先展示能完整装入预算的知识点；其余放入“展开旧答” |
| 单个旧知识点都无法装入 | 显示知识点标题和展开入口，不伪造新摘要 |
| 普通回答、详解回答 | 保持原正文 |
| 无结构化结果的旧 v1 | 保持原正文，不靠 Markdown 标题猜测并删除内容 |
| 只有孤立 `ragEvidence` | 附加折叠来源，不推断正文结构 |

禁止通过查找“教材原文摘录”等字符串，直接截掉历史消息的一部分。

### 4.4 追问卡精简

本批只压缩重复信息，不重写状态机：

- 顶行：标签、题干、分页。
- 中间：编号选项和自由输入。
- 底部：必要键盘提示、跳过、继续。
- 普通状态不重复显示相同含义的标题和 intro。
- 异常和待重试状态保留必要说明。
- 选择选项不自动提交、不自动跳页。
- 正常来源展开、收起不会触发追问或模型调用。

---

## 五、题库模型恢复与备份恢复修复

### 5.1 题库 AI 使用当前聊天模型

恢复 `modelProfileId` 的真实语义：

```python
class OrganizeRequest:
    modelProfileId: str  # 必填，真实聊天模型 profile ID
    draftIds: list[str]
    includeUnassigned: bool = False
```

前端：

- 复用聊天的模型选择规则与配置来源。
- 点击时冻结当前有效 profile ID。
- 没有显式选择时使用聊天配置的默认模型。
- 已显式选择但模型失效时提示修复，不能悄悄切换。
- 按钮附近显示“使用〈模型名〉整理”；云模型可标注“将所选题目文本发送至该模型服务”。
- 页面打开、导入、解析和编辑不会自动调用模型。
- 不增加重复确认弹窗。
- 删除题库对 `/rag/status.summarization.model` 的依赖。

后端：

- 将现有详解的模型解析逻辑提取到共享 `model_runtime`。
- 复用 `build_llm_config`、`build_provider` 和 `provider.complete`。
- 不调用内部 HTTP 聊天接口。
- 不把 profile ID 解释成 Ollama 模型名称。
- 不配置默认本地模型回退。

```python
async def organize(import_id, request):
    prepared = await db_call(
        prepare_source_blocks_and_draft_revisions,
        import_id,
        request.draftIds,
        request.includeUnassigned,
    )

    model = resolve_chat_model(request.modelProfileId)
    batches = pack_with_model_budget(prepared.blocks, model)

    job = await db_call(
        create_job,
        checkpoint={
            "contractVersion": 2,
            "modelProfileId": model.profile_id,
            "modelFingerprint": model.public_fingerprint,
            "draftRevisions": prepared.revisions,
            "batches": serialize_batches(batches),
            "nextBatchIndex": 0,
        },
    )

    for batch in batches:
        await db_call(require_job_running, job.id)

        reply = await model.provider.complete(
            model.config,
            build_organize_request(batch, model),
        )

        parsed = validate_complete_reply(reply, allowed_blocks=batch.block_ids)

        await db_call(
            commit_suggestion_and_progress,
            job_id=job.id,
            batch_index=batch.index,
            expected_draft_revision=prepared.revisions[batch.draft_id],
            suggestion=parsed,
            state="pending",
        )

    return await db_call(read_job, job.id)
```

必须同时处理：

- `organize`、执行和恢复入口改为 async；数据库操作通过有界线程执行，不在事件循环里 `asyncio.run()`。
- 网络调用不进入 SQL 写事务。
- 任务进行中切换聊天模型，不影响已冻结任务。
- checkpoint 不保存密钥、认证头或完整含凭证配置。
- 恢复任务时重新解析同一 profile，并检查非敏感配置指纹。
- 旧“模型名语义”未完成任务停止自动恢复，标记需要重新选择模型；保留已有建议。
- 输出 `length`、非法 JSON、未知来源块不能生成可应用建议。
- 认证、限流、网络失败不能误报成“试题内容无效”。
- 每批 6,000 字符预算包含来源标签和分隔符。
- 建议写入与批次进度推进放在同一个短事务内，检查任务未取消和草稿 revision 未变化。
- 人工应用建议时再次执行现有 CAS 校验。
- 教材 RAG 向量库与题库继续完全隔离。

### 5.2 备份采用可验证的离线一致性方案

本批不宣称支持跨 SQLite 与 Qdrant 的原子热备。

固定方案：

1. 增加数据根目录跨进程文件锁。
2. API 生命周期和写数据的 CLI 持有同一排他锁。
3. 备份拿不到锁时返回 `BACKUP_BUSY`，不自动停止用户进程。
4. 检查没有未结束的入库/重建任务，不擅自修改遗留任务状态。
5. 使用 SQLite backup API 生成两库副本。
6. 从**备份后的数据库**读取活动代、文件引用和 collection 清单。
7. 复制所有被数据库引用的文件，逐文件计算大小与 SHA256。
8. 为所需 Qdrant collections 创建快照并验证点数、维度和 payload 对账。
9. 全部通过后才把 manifest 标为 `complete`。

必须包含：

```text
textbooks/catalog.sqlite3
textbooks/blobs/<原件>
textbooks/normalized/<规范化正文及来源映射>
textbooks/staging/<未发布草稿引用的完整产物>

question-bank/question-bank.sqlite3
question-bank/blobs/<原件>
```

不把未完成的 `tmp-*.part` 当成有效草稿产物。

新清单采用 `schemaVersion: 2`：

```python
manifest = {
    "schemaVersion": 2,
    "status": "complete",
    "activeGenerationId": ...,
    "files": [
        {
            "logicalRole": ...,
            "archivePath": ...,
            "restorePath": ...,
            "bytes": ...,
            "sha256": ...,
        }
    ],
    "collections": [
        {
            "generationId": ...,
            "collectionName": ...,
            "dimensions": ...,
            "distance": ...,
            "pointCount": ...,
            "snapshotPath": ...,
            "snapshotSha256": ...,
            "pointManifestSha256": ...,
        }
    ],
}
```

任一必需文件、原文哈希或快照缺失，保留失败记录并非零退出，不能输出“备份完成”。

### 5.3 恢复生成真正可读取的数据目录

```python
def restore_backup(backup, new_root, isolated_qdrant):
    manifest = read_and_validate_manifest(backup)

    require_new_empty_target(new_root)
    verify_all_paths_stay_inside_roots(manifest)
    verify_all_required_files_before_restore(manifest)

    write_restore_state(new_root, status="incomplete")
    restore_files_to_runtime_layout(manifest, new_root)

    for collection in manifest.collections:
        new_name = unique_restore_collection_name(collection)
        require_collection_absent(isolated_qdrant, new_name)

        restore_snapshot(
            target=isolate_qdrant,
            collection=new_name,
            snapshot=collection.snapshotPath,
            priority="snapshot",
            wait=True,
        )
        verify_collection_against_manifest(new_name, collection)
        remap_collection_in_restored_catalog_only(
            new_root, collection.generationId, new_name
        )

    verify_sqlite_integrity_and_foreign_keys(new_root)
    verify_all_referenced_blobs(new_root)
    verify_draft_previews(new_root)
    verify_revision_and_point_manifests(new_root)

    write_restore_state(new_root, status="ready")
```

Qdrant 恢复使用新 collection 名称，明确设置 snapshot 优先级，并完成点数核验；参考其[官方快照恢复说明](https://qdrant.tech/documentation/operations/snapshots/)。

验收实例使用现有隔离端口 `16333`。不得覆盖正式 `6333` 的 collection。

旧 manifest：

- 只读兼容，不改原文件。
- 将旧归档布局映射到正确运行目录。
- 内容寻址文件通过 blob ID 校验实际内容。
- 缺少草稿产物或必要快照时明确失败。
- 标记 `legacy_revalidated`，不能补造历史备份完整性结论。
- 现有迁移前备份可以证明其覆盖的旧资产状态，不能证明当前 58 册完整灾备已经成立。

恢复目录处于 `incomplete` 时，应用启动必须明确拒绝，避免自动创建空库掩盖恢复失败。

**代码回退与数据恢复分别说明，不再写“revert 即完整回滚”。**

---

## 六、验收、发布与多智能体执行

### 6.1 新增验收矩阵

| 范围 | 必测场景与通过条件 |
|---|---|
| 清洗 | 内联图片、引用式图片、HTML 图片、嵌套括号、转义、中文 alt、哈希路径；图片节点地址不进入索引输入、模型证据、可见首答和默认复制 |
| 内容保真 | 公式、表格、代码和正文图注保留；原文文件与引用 hash、坐标不变 |
| 证据窗口 | 长章节单个命中不扩成整章；超长受保护单元产生可解释状态，不误报无依据 |
| 首答 | 1–3 点，总计不超过 250 码点；重复点、100 点、超长输出和图片输出均受约束 |
| 引用 | 引用未入模证据必须拒绝；伪造 ID、错误 hash、删除教材继续拒绝 |
| 前端 | 同时包含旧 `content` 和 `ragResult` 时只显示一次；来源默认折叠 |
| 复制与上下文 | 默认复制和后续历史不包含整段原文；有追问卡、无追问卡都覆盖 |
| 历史兼容 | 旧 v2 自动使用紧凑视图且不重写数据库；普通回答、详解、旧 v1 不被误截 |
| SSE | 断流、重连、刷新恢复、终态、取消、重复事件不造成重复正文 |
| 题库 | 本地与云 profile、三协议替身、模型冻结、错误分类、人工编辑冲突、pending 建议、旧任务兼容 |
| 备份恢复 | 已发布教材、教材草稿、题库草稿、正式题目和 Qdrant 一起恢复；缺文件、坏 hash、错维度、已有目标必须失败 |
| 索引代 | 同模型新策略重建、失败/取消保留旧代、旧历史引用可读、未知策略报错 |
| 数据隔离 | 测试不改正式任教范围、草稿、凭证和向量 collection |

视觉验收必须覆盖真实内容状态：

- 390×844、1440×900、1920×1080 三个视口。
- 简短成功首答、partial、no_evidence。
- 来源关闭、来源展开、单条摘录展开。
- 图片密集教材、公式密集教材、长书名。
- 追问卡、详解流式输出、历史恢复。
- 题库校对工作台及当前模型说明。
- 无横向溢出，键盘焦点可达，没有图片网络请求。

### 6.2 真实质量样本

建立固定 30 问集：现有 10 个教材分组各 3 问，其中每组 2 个正向知识点问题、1 个边界问题。

要求：

- 使用自然题目或教师问法，不直接拿章节标题充当问题。
- 正向金标标注 `documentRevisionId + 原文区间`，不依赖当前不完全准确的 `chapter_path`。
- 边界包含范围外问题、证据不足、依赖图片条件等。
- 在同一书册范围、相同 Embedding 身份下比较旧代与新代。
- 正向证据 Hit@5 至少 18/20，且不得低于旧代基线；关键原本命中的样本不能无说明退化。
- 30 问全部满足图片清洗、长度和不重复展示要求。
- 教学适用性单独记录，由教师复核；不能由格式校验替代。

新增测量脚本的“全库竞争”“叶子命中”“上界”等表述按实际算法订正。旧测量结果保留，标为结构定位代理指标。

验收脚本必须支持只读或隔离目录，不能再为了测评调用 `save_teaching_selection` 修改用户配置，也不能对正式库执行 `migrate()`。

### 6.3 工程检查与候选冻结

执行顺序：

```text
相关单测
  → typecheck / lint / 全量 unit / pytest
  → build
  → test:chat 与相关 e2e
  → 隔离真实模型、Qdrant、恢复演练
  → 三视口人工检查
  → 冻结候选
  → A1 独立验收
```

要求：

- 单测继续使用 `NODE_OPTIONS=--no-experimental-webstorage`。
- Next 生成文件的变化由总控核对，只恢复本次命令产生的副作用。
- 新测试使用真实 presenter 输出构造前端消息，不能再只放一句占位 content。
- 记录候选 SHA、dirty diff 指纹、构建 ID、索引代、模型 digest、清洗版本、测试命令和退出码。
- 修改候选后，受影响证据必须重跑。
- 缺样本、跳过关键断言、零样本测评均不能 PASS。
- 旧 R-15 单独处理：确认旧 selector 后修复该测试定位并实跑，不能直接删除断言。

### 6.4 发布与回退顺序

1. 完成清洗和紧凑展示，在旧索引代上验证。
2. 完成备份修复及隔离恢复演练。
3. 取得无业务写入的维护条件，生成当前数据的完整备份。
4. 使用相同本地 Embedding 创建新清洗索引代。
5. 对账、真实检索与质量样本通过后，原子切换活动代。
6. 保留旧代、旧原文和备份，不自动清理。
7. 完成教师流程检查：任教范围 → 提问 → 来源 → 追问详解 → 教材更新 → 题库整理与确认。

回退时先核对旧代是否覆盖当前书册和修订。覆盖不足时不能直接切回旧指针并宣称恢复成功；应在保留当前新增数据的前提下恢复兼容索引，或使用已验证备份恢复到新目录。

### 6.5 多智能体任务卡

全部任务遵循现有[协作模板](/H:/备份xuexi/智启课源/docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md)。任务版本统一为 `RAG-QUALITY v1.1`。

| 任务 | 负责人角色 | 写入范围与交付 | 依赖 |
|---|---|---|---|
| C0-CONTRACT | 总控 | 冻结新增字段、预算、策略版本、错误语义、共享类型和 API 文档 | 无 |
| B0-TEXT-PROJECTION | 后端实现者 | 新增清洗投影模块、来源映射、跨语言样例；不改原文 | C0 |
| B1-RAG-ANSWER | 后端实现者 | 证据窗口、PromptPack、简短概括、presenter、详解清洗及相关测试 | B0 |
| B2-CLEAN-INDEX | 后端实现者 | 清洗策略进入分块和索引代；Embedding/BM25 接线、重建兼容 | B0 |
| F0-COMPACT-CHAT | 前端实现者 | 单一消息投影、来源折叠、复制与历史、追问卡紧凑化 | C0、B0 样例 |
| B3-ORGANIZER-MODEL | 后端实现者 | 共享模型解析、异步 Provider 调用、任务冻结和建议事务 | C0 |
| F1-ORGANIZER-UI | 前端实现者 | 当前聊天模型接线、模型说明、错误与旧任务提示 | C0、B3 |
| B4-BACKUP-RESTORE | 后端实现者 | 文件锁、完整 manifest、正确目录恢复、隔离演练工具 | C0 |
| A1-INDEPENDENT-QA | 独立验收者 | 新增质量集、独立复现、视觉及数据恢复验收；不修业务代码 | 稳定候选 |
| C1-INTEGRATE | 总控 | main 装配、共享文件接线、文档、最终检查和 Git | 各实现卡 |

文件归属原则：

- C0/C1 独占共享 schema、类型契约、主装配、依赖锁文件、权威文档和最终 Git。
- B1 独占 RAG 的 evidence、summary、presenter、explain、service。
- B2 独占索引、分块、generation policy 和 retrieval 的清洗接线。
- F0 独占 chat 展示、store 和历史投影。
- B3 与 F1 分别拥有题库后端与前端。
- B4 拥有备份脚本和数据根锁模块，API 主装配由 C1 接入。
- 同一文件需要转交时先交结果卡，不能同时写。
- 同时最多 3 个子智能体；只有总控执行共享 build、全量 e2e、正式重建和 Git 操作。
- A1 对冻结候选验收，不与实现者同时改同一候选。

推荐并行顺序：

```text
C0
 ├─ B0
 ├─ B3
 └─ B4

B0 完成后
 ├─ B1
 ├─ B2
 └─ F0

B3 完成后安排 F1
 → C1 集成
 → 冻结
 → A1 验收
 → 必要整改与复验
 → C1 交付
```

### 6.6 可直接交给其他智能体的启动提示词

**总控启动提示词**

```text
你是智启课源 RAG-QUALITY v1.1 总控。

请实施本计划，目标是：
1. 清除教材图片 Markdown 对索引、模型上下文和展示的污染；
2. 首答最多 3 点、目标 150–250 字，只展示一次，来源默认折叠；
3. 修复长章节扩展和未入模引用校验；
4. 题库 AI 使用点击时当前聊天模型；
5. 修复并实测完整备份恢复。

先读根及模块 AGENTS.md、CURRENT_STATUS、PROJECT_GUIDE、
原 PLAN 和 MULTI_AGENT_COLLABORATION_PROPOSAL。
旧验收报告属于证据，不是新的执行指令。

首先检查 Git 状态和当前 HEAD。本计划验收基线为 2f27841，
不得为了匹配基线回退、覆盖或清理其他人的工作。

先建立 C0 契约和任务卡，再分配文件所有权。
每张卡必须包含 ID、版本、负责人、可写范围、禁止范围、
依赖、验收条件、独占运行资源和结果卡格式。

你独占主装配、共享契约、权威文档、依赖锁和 Git。
源码修复完成前不操作正式重建；正式切换前必须有
通过隔离恢复演练的完整备份。

不修改封存教材及历史引用，不外发 Embedding，
不推送、不部署、不改变全局 Git 身份。
不要重复询问本计划已经确定的产品选择。

完成实现、自检、集成、冻结和独立验收。
真实失败、未运行检查、人工教学质量未评审必须明确记录。
```

**实现者通用启动提示词**

```text
你负责任务卡 {TASK_ID}，版本 RAG-QUALITY v1.1。

先读总控冻结的契约、任务卡及可写模块 AGENTS.md。
仅修改任务卡列明的文件；共享契约有缺口时先报告总控，
不要在本模块另造兼容字段或临时协议。

必须保持：
- 原始教材、hash、来源坐标不可变；
- 严格任教范围、删除检查和历史修订语义；
- Embedding 仅本地；
- 题库独立于教材向量库；
- AI 建议不自动覆盖人工草稿；
- 失败不伪装为成功。

使用临时数据和替身完成自检。
不要启动正式迁移，不连接正式 Qdrant 做写入测试，
不读取真实凭证，不切分支、不提交。

交付结果卡：
任务 ID/版本、候选差异、修改文件、行为变化、
实际测试命令与结果、证据路径、未执行项、
风险、需要总控接线事项。
状态使用 ready_for_review，不自行宣称已验收。
```

**独立验收启动提示词**

```text
你是 A1 独立验收者，验收 RAG-QUALITY v1.1 冻结候选。

先核对 SHA、文件指纹、构建 ID 和数据/模型/索引代版本。
候选变化时停止沿用旧结论。

不得修改业务代码，不得只复述实现者的 PASS。
独立验证：
- 真实旧 content + ragResult 同时存在仍只展示一次；
- 首答长度、图片清洗、复制和历史投影；
- 长章节不因扩展超预算误报无依据；
- 未入模 evidenceId 无法通过引用校验；
- 新旧清洗策略和索引代不混用；
- 题库使用冻结聊天 profile，建议仍需人工确认；
- 已发布教材、两类草稿、题目和 Qdrant 的完整隔离恢复；
- 三视口真实内容状态、刷新恢复和追问交互。

测试只使用隔离数据根、浏览器上下文及测试端口。
禁止为测评改正式任教设置，禁止用真实失败替换成模拟通过。

输出 pass / needs_revision / blocked。
每个问题提供优先级、代码位置、复现步骤、实际结果、
预期结果和证据。区分本轮实测、历史证据、代码推断。
人工教学质量没有教师评审时必须保持 not_run。
```

### 6.7 最终交付物

- 完整实现及本地提交。
- 本计划对应的任务卡和结果卡。
- 图片清洗与紧凑回答前后对照。
- 固定质量集、逐问结果与新旧索引比较。
- 独立验收报告及三视口截图。
- 当前数据的备份清单和完整隔离恢复报告。
- 代码回退、索引切换、数据恢复三者分别说明。
- 更新唯一进度入口、稳定决定和 API 契约；原历史报告保持原样。

已知的习题区识别不足和章节标签不准继续保留台账。本批不能因为回答变短、链接消失，就把这些问题或人工教学质量一并标成通过。
