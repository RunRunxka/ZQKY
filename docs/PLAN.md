# 智启课源 RAG 重构实施计划
## RAG-REBUILD v1.0 · 伪代码级规格与多智能体交接稿

本稿完整替代前两版计划，可连同末尾启动提示词交给其他智能体实施。

协作形式依据仓库现有的[多智能体协作模板](H:/备份xuexi/智启课源/docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md)。当前仍为规划阶段，未修改仓库、启动数据库、运行推理或执行测试。

---

## 一、已经确认的产品决定

以下决定已经由用户确认，实施者不需要重复询问。

| 项目 | 确定行为 |
|---|---|
| 部署 | 本机单用户；预留用户归属字段，暂不实现登录 |
| 向量数据库 | Qdrant，本机 Docker 服务，使用 named volume |
| 教材目录 | SQLite，管理分类、原文、修订、任务和任教配置 |
| 题库 | 独立 SQLite 数据库和附件目录，不进入教材向量库 |
| 基础教材 | 纳入当前全部人教版资料；数学 A/B 版分开 |
| 个人教材 | 用户在教材管理中自行导入，按年级、学科、版本管理 |
| 教材格式 | Markdown、文本 PDF、Word `.docx` |
| 扫描件 | 不实现 OCR；明确提示需要文本层或人工处理 |
| 任教范围 | 本轮实现年级、学科、版本及适用书册确认 |
| RAG 首答 | 知识点概览、适用条件、教材原文和出处 |
| LLM 详解 | 用户主动触发，使用当前聊天所选模型 |
| Embedding | 可配置多个本地模型，全站统一使用一个当前模型 |
| Embedding 运行时 | 首版使用本地 Ollama；默认已安装的 `bge-m3` |
| Embedding 切换 | 新建索引，完整重建成功后统一切换 |
| 追问界面 | 截图布局与当前输入框风格结合；同时支持澄清和详解引导 |
| 题目导入 | 本地提取、规则拆题、人工校对；按需点击“AI 整理” |
| 题库入口 | 侧栏“题库”紧跟“智能组卷”；题库页提供导入按钮 |
| 组卷 | 本轮不实现，继续标记规划状态 |

### 1.1 本轮不扩展的范围

- 不实现多教师登录、共享权限和远程部署。
- 不实现云端 Embedding、自动下载模型或模型不可用时的云端回退。
- 不实现 OCR、网页资料抓取、自动组卷、试卷排版导出。
- 不把课程标题、旧知识库名称或用户问题中的“高二数学”自动视为可信检索范围。
- 不把教材中的练习题自动导入题库。
- 不顺带升级框架、替换包管理器或重做其他业务模块。

### 1.2 参考与现场基线

本次只读调查时：

- 本仓库 HEAD：`c2f31ec0a70fc9b9e9d38479b6c193416c19befb`，工作区干净。
- 参考项目 HEAD：`38b39f641a5228673fc46a64c802307e2e6d5209`。
- [固定参考项目](https://github.com/weiwill88/Local_Pdf_Chat_RAG/tree/38b39f641a5228673fc46a64c802307e2e6d5209)仅用于借鉴解析、混合检索和模块划分，不直接移植其内存索引或 Gradio 界面。
- 实际源目录有58册、9个学科、10个目录。
- 旧索引有54册、11,608个正文块；4册需要新增解析。
- 旧文本块 ID 存在跨数学 A/B 版重名，不能直接作为向量数据库主键。

实施启动时必须重新读取 Git 状态和资产清单。这些数字是调查事实，不是要求回退到该提交或覆盖现场文件。

---

## 二、总体架构与不可破坏的不变量

### 2.1 数据流

```text
教材文件
  → 托管原件
  → 文本/结构/来源位置提取
  → 用户确认分类与解析结果
  → 不可变文档修订
  → 正文分块
  → 本地 Embedding
  → Qdrant
  → SQLite 发布有效修订

用户任教配置
  → 服务端解析允许的教材修订
  → 同范围向量检索 + BM25
  → RRF 融合
  → 原文证据重建
  → 本地模型概括知识点
  → 浏览器保存结构化结果

用户点击详解
  → 服务端重新核验引用
  → 当前聊天模型
  → SSE 详解
```

题库独立：

```text
试题文件
  → 本地解析
  → 规则拆题
  → 草稿与未归属文本
  → 可选 AI 整理建议
  → 人工校对
  → 独立题库确认入库
```

### 2.2 存储布局

以下为拟新增路径，相对于仓库根目录：

```text
.local-data/
  textbooks/
    catalog.sqlite3
    blobs/                 # 教材原件，按内容指纹保存
    normalized/            # 不可变规范化文本与来源映射
    assets/                # 教材图片等受控资源
    staging/               # 上传中及未发布产物
  question-bank/
    question-bank.sqlite3
    blobs/
    assets/
    staging/
  rag/                     # 旧资产，迁移后保留，不再由正式运行时读取
```

Qdrant：

```text
Docker named volume
  └─ textbooks_<generation_id> collection
```

Qdrant 数据目录不直接挂载 Windows 的 `H:\...` 路径。数据库连接、托管文件和测试目录均通过应用配置注入。

### 2.3 必须成立的不变量

1. **唯一后端**：真实业务仍全部位于 FastAPI；Next.js 只做现有代理和页面。
2. **唯一当前索引指针**：SQLite 的 `active_generation_id` 是唯一权威。
3. **模型空间一致**：查询向量与教材向量必须使用同一 Embedding 配置指纹。
4. **发布原子性**：向量全部写入并核验后，才切换教材有效修订。
5. **先限制范围再排序**：向量、BM25、邻块扩展和引用都使用同一教材范围。
6. **删除先失效**：先在 SQLite 停用，再清理向量；清理失败不影响逻辑删除。
7. **原文不可变**：引用绑定文档修订及规范化文本指纹，不绑定可变化的外部路径。
8. **失败不伪装成功**：服务不可用不能变成空库、模拟结果或普通聊天回退。
9. **旧数据保留**：旧浏览器登记、课程引用、聊天记录及源教材不被清空。
10. **题库独立**：题库服务不能通过任何自动路径将题目写入教材 collection。

---

## 三、数据模型与数据库约束

### 3.1 版本概念必须分开

| 概念 | 示例 | 用途 |
|---|---|---|
| 教材版本 | 人教A版、人教B版 | 分类与检索选择 |
| 出版版次 | 2019版、2024修订 | 书册说明 |
| 文档修订 | 同一本书重新上传后的 revision | 原文、引用、更新历史 |
| 分类修订 | 修改适用年级或书册信息 | 重建历史范围 |
| Embedding 配置 | 模型、digest、维度、前缀 | 向量空间身份 |
| 索引代 | 某次全站构建的 collection | 发布、切换与旧轮固定 |

不得用一个 `version` 字段承载以上所有含义。

### 3.2 教材数据库实体

以下是逻辑表规格。JSON 字段必须由严格类型校验后写入。

```text
catalog_state
  id = 1                         PRIMARY KEY
  active_generation_id           NULLABLE FK index_generations
  rebuild_job_id                 NULLABLE FK index_jobs
  catalog_version                INTEGER NOT NULL

embedding_profiles
  id                             PRIMARY KEY
  fingerprint                    UNIQUE NOT NULL
  adapter                        固定 "ollama"
  native_base_url                 本机 Ollama 原生地址
  model_name
  model_manifest_digest
  dimensions
  distance                       首版固定 cosine
  query_prefix
  document_prefix
  normalization
  options_json
  verified_at
  retired_at                     NULLABLE

index_generations
  id                             PRIMARY KEY
  profile_id                     FK embedding_profiles
  collection_name                UNIQUE NOT NULL
  chunk_policy_json
  state                          building | ready | aborted
  created_at
  published_at                   NULLABLE

libraries
  id                             PRIMARY KEY
  kind                           base | personal
  owner_id                       system | local-user
  grade_id                       NULL 表示尚未确认年级
  subject_id
  edition_id
  display_name
  revision                       乐观锁版本
  deleted_at                     NULLABLE

documents
  id                             PRIMARY KEY
  owner_id
  origin_key                     NULLABLE
  current_revision_id            NULLABLE FK document_revisions
  current_metadata_revision_id   FK document_metadata_revisions
  revision                       乐观锁版本
  deleted_at                     NULLABLE
  UNIQUE(owner_id, origin_key)

library_documents
  library_id                     FK libraries
  document_id                    FK documents
  PRIMARY KEY(library_id, document_id)

document_metadata_revisions
  id                             PRIMARY KEY
  document_id                    FK documents
  title
  stage_id
  grade_ids_json
  subject_id
  edition_id
  publication_label
  volume_label
  created_at
  # 写定后不修改

document_revisions
  id                             PRIMARY KEY
  document_id                    FK documents
  original_file_sha256
  normalized_text_sha256
  parser_version
  original_blob_id
  normalized_blob_id
  source_map_blob_id
  created_at
  # 原件、规范化文本和来源映射均不可变

chunk_sets
  id                             PRIMARY KEY
  document_revision_id           FK document_revisions
  policy_fingerprint
  manifest_sha256
  sealed_at
  # 不同分块策略可以对应不同 chunk_set，不修改旧修订原文

chunks
  chunk_set_id                   FK chunk_sets
  ordinal
  char_start
  char_end
  region                         body | exercise
  chapter_path_json
  text_sha256
  legacy_chunk_id                 NULLABLE，仅用于迁移核对
  PRIMARY KEY(chunk_set_id, ordinal)

generation_revisions
  generation_id                  FK index_generations
  document_revision_id           FK document_revisions
  chunk_set_id                   FK chunk_sets
  state                          pending | ready | skipped_deleted
  expected_chunk_count
  manifest_sha256
  PRIMARY KEY(generation_id, document_revision_id)

import_drafts
  id                             PRIMARY KEY
  owner_id
  target_document_id             NULLABLE
  expected_current_revision_id   NULLABLE
  metadata_json
  uploaded_blob_id
  parsed_artifacts_json
  state
  revision
  warnings_json

index_jobs
  id                             PRIMARY KEY
  kind                           ingest | rebuild | cleanup
  input_revision_id              NULLABLE
  target_generation_id
  base_generation_id             NULLABLE
  state                          queued | running | succeeded | failed | cancelled
  idempotency_key                UNIQUE
  request_fingerprint
  attempt
  lease_token                    NULLABLE
  lease_until                    NULLABLE
  checkpoint_json
  error_code                     NULLABLE

teaching_settings
  owner_id                       PRIMARY KEY
  selection_json
  revision
```

补充约束：

- 同一书册可加入多个年级对应的逻辑库，向量不重复复制。
- 分类不明确的基础教材进入“待确认年级”，完成书册确认后才能参与该年级检索。
- `owner_id` 由服务端决定，不接受前端自行声明身份。
- SQLite 开启外键、WAL和有限 `busy_timeout`。
- 网络请求、文件解析、模型推理不得放在 SQLite 写事务内。
- 修改已发布分类时创建新的元数据修订，保留旧快照解释能力。

### 3.3 Qdrant collection 与 point

```python
collection_name = f"textbooks_{generation_id.hex}"

point_id = uuid5(
    APP_NAMESPACE,
    f"{generation_id}/{chunk_set_id}/{ordinal}/{text_sha256}"
)

point = {
    "id": point_id,
    "vector": embedding,
    "payload": {
        "generation_id": generation_id,
        "document_id": document_id,
        "document_revision_id": revision_id,
        "chunk_set_id": chunk_set_id,
        "ordinal": ordinal,
        "owner_id": owner_id,
        "region": "body",
        "text_sha256": text_sha256,
    },
}
```

- 对 `document_revision_id`、`chunk_set_id`、`owner_id`、`region` 建立必要 payload 索引。
- 年级、学科、版本的权威筛选在 SQLite 中转换为允许的修订与块集合，再作为 Qdrant 预过滤条件。
- 不用文件名、旧 `chunk_id` 或数组下标单独标识向量。
- 不用 Qdrant alias 再维护一个“当前模型”指针。
- SQLite 保存可重建的原文；向量库不作为原件的唯一保存位置。

---

## 四、本地 Embedding 管理与全站重建

### 4.1 模型配置入口

在现有“模型与连接”中增加独立的“Embedding 模型”区域：

```text
当前模型
  模型名称 / 实测维度 / 模型身份 / 当前索引状态

可用配置
  发现本地模型
  检测
  保存配置
  重建并切换

重建任务
  当前阶段 / 已完成教材 / 已完成块
  失败原因 / 取消 / 重新发起
```

不要把 Embedding 配置硬塞进现有三种聊天协议。首版通过独立本地 Ollama adapter 调用原生 `/api/embed`，在同一设置模块展示。

默认地址为 `http://127.0.0.1:11434`，允许配置其他本机回环端口。

### 4.2 检测与配置指纹

```python
def verify_embedding_candidate(candidate):
    require_loopback_native_url(candidate.base_url)
    reject_redirects_and_proxy_forwarding()

    models = ollama.list_installed_models()
    model = require_installed_model(models, candidate.model_name)

    details = ollama.show_model(model.name)
    require_not_cloud_or_remote_model(details)
    require_embedding_candidate(details)

    digest_before = model.manifest_digest

    vectors = ollama.embed(
        model=model.name,
        input=["集合与函数", "物质的结构与性质"],
        truncate=False,
    )

    require(len(vectors) == 2)
    require(all_vectors_have_same_dimension(vectors))
    require(all_values_finite(vectors))
    require(all_vectors_nonzero(vectors))

    digest_after = ollama.get_manifest_digest(model.name)
    require(digest_before == digest_after, "EMBEDDING_MODEL_CHANGED")

    return VerifiedEmbeddingProfile(
        adapter="ollama",
        model_name=model.name,
        model_manifest_digest=digest_after,
        dimensions=len(vectors[0]),
        query_prefix=candidate.query_prefix,
        document_prefix=candidate.document_prefix,
        options=candidate.options,
    )
```

配置指纹：

```python
fingerprint = sha256(canonical_json({
    "adapter": profile.adapter,
    "modelManifestDigest": profile.model_manifest_digest,
    "dimensions": profile.dimensions,
    "distance": "cosine",
    "queryPrefix": profile.query_prefix,
    "documentPrefix": profile.document_prefix,
    "normalization": profile.normalization,
    "options": profile.options,
}))
```

规则：

- “发现到模型”不等于“具备 Embedding 能力”。
- 检测通过只证明接口能力，不代表教材检索质量已验收。
- 使用模型原生维度，首版不增加用户任意裁剪维度功能。
- 不同模型的查询／文档指令前缀可配置，并进入指纹。
- 编辑影响向量的字段时创建新配置，不能原地改写正在使用的配置。
- 同名 tag 的 digest 改变必须视为模型改变。
- 查询和入库均显式使用 `truncate=False`，避免默认截断。[Ollama 接口说明](https://docs.ollama.com/api/embed)
- 模型不存在、输出维度改变或本地服务不可用时明确失败，不换模型。

### 4.3 当前模型的唯一读取方式

```python
def get_active_embedding():
    generation_id = catalog_state.active_generation_id
    generation = generations.require_ready(generation_id)
    profile = embedding_profiles.get(generation.profile_id)
    return generation, profile
```

不能另存：

```text
model-config.json.defaultEmbeddingModel
catalog_state.activeProfileId
Qdrant active alias
```

来与 `active_generation_id` 竞争。

### 4.4 重建闸门

首版采用暂停发布的简单策略，不做新旧索引双写。

重建期间：

| 操作 | 行为 |
|---|---|
| 查询旧教材 | 正常，使用旧索引 |
| 上传文件、编辑导入草稿 | 允许 |
| 新教材正式入库、内容更新发布 | 暂停，保留草稿 |
| 改变检索范围的分类发布 | 暂停 |
| 删除或停用教材 | 允许，立即从 SQL 范围排除 |
| 修改任教选择 | 允许，只影响新查询 |
| 启动第二次重建 | 返回冲突 |

```python
def begin_rebuild(profile_id, request_key):
    profile = require_verified_profile(profile_id)
    probe_exact_local_model(profile)

    with db.begin_immediate():
        existing = find_idempotent_job(request_key)
        if existing:
            require_same_request(existing)
            return existing

        require(catalog.rebuild_job_id is None)
        require(
            no_queued_or_running_ingest_jobs(),
            "INDEX_MUTATION_BUSY",
        )

        target = create_generation(
            profile_id=profile.id,
            state="building",
        )

        job = create_rebuild_job(
            base_generation_id=catalog.active_generation_id,
            target_generation_id=target.id,
        )

        manifest = current_revisions_of_live_documents()
        save_generation_manifest(target.id, manifest)

        catalog.rebuild_job_id = job.id

    return job
```

### 4.5 重建执行与发布

```python
def run_rebuild(job, lease):
    target = load_generation(job.target_generation_id)
    profile = load_profile(target.profile_id)

    create_or_validate_collection(target, profile)

    for revision in frozen_manifest(target.id):
        assert_current_lease(job, lease)

        if document_is_deleted(revision.document_id):
            mark_skipped_deleted(job, lease, revision)
            continue

        chunk_set = prepare_immutable_chunk_set(
            revision,
            target.chunk_policy,
        )

        embed_and_upsert_revision(
            generation=target,
            profile=profile,
            revision=revision,
            chunk_set=chunk_set,
            job=job,
            lease=lease,
        )

        mark_revision_ready(job, lease, revision)

    verify_manifest_and_point_counts(target)

    with db.begin_immediate():
        require_valid_lease(job, lease)
        require(job.state == "running")
        require(catalog.rebuild_job_id == job.id)
        require(catalog.active_generation_id == job.base_generation_id)

        expected = current_revisions_of_live_documents()
        require(expected <= frozen_manifest(target.id))
        require(all_ready(target.id, expected))

        target.state = "ready"
        catalog.active_generation_id = target.id
        catalog.rebuild_job_id = None
        catalog.catalog_version += 1
        job.state = "succeeded"
```

失败或取消：

```python
def terminate_rebuild(job, lease, terminal_state):
    with db.begin_immediate():
        require_valid_lease(job, lease)

        job.state = terminal_state
        target_generation.state = "aborted"

        if catalog.rebuild_job_id == job.id:
            catalog.rebuild_job_id = None

        # 不修改 active_generation_id
```

闸门释放后，用户再次重试必须创建新任务、新索引代和新快照，不能复活旧重建任务。

成功切换后：

- 新查询使用新索引代。
- 尚未过期的旧定位轮继续使用其固定索引代。
- 本轮不自动删除成功发布过的旧 collection。
- 旧代不能作为无条件一键回滚目标；新增教材可能尚不在旧代中。回退同样需要校验覆盖范围。

---

## 五、教材解析、入库、更新与恢复

### 5.1 默认限制与分块规则

首版默认值：

| 项目 | 默认 |
|---|---|
| 单文件大小 | 100 MiB |
| 文件格式 | `.md`、文本 `.pdf`、`.docx` |
| 入库 worker | 1个 |
| Embedding 批大小 | 8，OOM时允许缩小批次，不换模型 |
| 普通文本目标块长 | 800个码点 |
| 普通文本最大块长 | 1200个码点 |
| 段落重叠 | 最多120个码点，按完整边界 |
| 公式、表格、代码围栏 | 不从中间强行截断 |
| 模型输入过长 | 返回具体块位置；重新分块生成新块集或明确失败 |
| 任务轮询 | 活跃时1秒；离页停止轮询 |

这些限制进入集中配置和测试，不散写在前后端组件。

解析规范：

- Markdown：保留标题、正文、公式、表格、行号。
- PDF：提取文本层，保存物理页码和来源块；混合缺页给出警告。
- DOCX：按段落和表格顺序提取；保留段落／表格位置与可提取资源。
- 不能可靠转换的公式、图表必须标记，不能静默删除后宣称完整解析。
- Markdown 外链不自动下载；本地资源只能从本次导入包或受控来源目录读取。
- 原文件指纹和规范化全文指纹分别保存。
- 规范化不任意压缩空白；换行处理规则固定并版本化。
- 教材正文和习题区保留区分；首版知识点检索只索引正文。

### 5.2 导入状态机

```text
uploaded
  → extracting
  → needs_review
  → queued
  → chunking
  → embedding
  → indexing
  → ready

extracting / queued / chunking / embedding / indexing
  → failed
  → cancelled
```

含义：

- `needs_review`：解析完成但尚未确认分类或警告。
- `ready`：SQLite 已发布有效修订，可以检索。
- 不得在 Qdrant 尚未完成时提前显示“入库成功”。

### 5.3 创建任务

```python
def submit_ingest(import_id, expected_revision, submission_id):
    draft = imports.require_revision(import_id, expected_revision)
    require_metadata_complete(draft)
    require_parse_review_complete(draft)

    # 文件封存可在事务外完成；孤立暂存产物后续可清理。
    revision = seal_document_revision(draft)

    with db.begin_immediate():
        existing = find_job(submission_id)
        if existing:
            require(existing.request_fingerprint == fingerprint(draft))
            return existing

        require(catalog.rebuild_job_id is None,
                "INDEX_REBUILD_IN_PROGRESS")

        require_document_not_deleted(draft.target_document_id)
        require_no_other_publish_job(draft.target_document_id)
        require_expected_current_revision_matches(draft)

        generation = require_active_generation()
        job = create_ingest_job(revision, generation, submission_id)
        add_generation_revision(generation, revision, state="pending")

    return job
```

空库第一次启动：

- 先检测并保存默认 Embedding 配置。
- 创建并验证空 collection。
- 在事务中将该空索引代置为当前。
- 此后所有入库仍使用同一正常流程。
- 空库的 `scopeReady=false`，不能因为数据库在线就宣称 RAG 可用。

### 5.4 批次写入与发布

```python
def embed_and_upsert_revision(generation, profile, revision,
                              chunk_set, job, lease):
    for batch in chunk_batches(chunk_set, size=8):
        assert_current_lease(job, lease)
        require_exact_model_digest(profile)

        texts = [
            profile.document_prefix
            + contextual_header(chunk)
            + "\n"
            + source_slice(revision, chunk.char_start, chunk.char_end)
            for chunk in batch
        ]

        vectors = embedding.embed(
            profile=profile,
            input=texts,
            truncate=False,
        )

        validate_count_dimension_and_finite_values(vectors, profile)
        require_exact_model_digest(profile)

        points = build_deterministic_points(
            generation, revision, chunk_set, batch, vectors,
        )

        qdrant.upsert(
            collection=generation.collection_name,
            points=points,
            wait=True,
        )

        checkpoint_batch_with_lease(job, lease, batch)
```

```python
def publish_ingest(job, lease):
    verify_expected_points_and_manifest(job)

    with db.begin_immediate():
        require_valid_lease(job, lease)
        require(job.state == "running")
        require(catalog.rebuild_job_id is None)
        require(catalog.active_generation_id == job.target_generation_id)

        document = require_live_document(job.document_id)
        require_expected_current_revision_matches(job)

        generation_revision.state = "ready"
        document.current_revision_id = job.input_revision_id
        document.current_metadata_revision_id = job.metadata_revision_id
        document.revision += 1
        catalog.catalog_version += 1
        job.state = "succeeded"
```

### 5.5 删除和更新

```python
def delete_document(document_id, expected_revision):
    with db.begin_immediate():
        document = require_document_revision(
            document_id, expected_revision,
        )
        document.deleted_at = now()
        document.revision += 1
        catalog.catalog_version += 1
        enqueue_cleanup(document_id)

    # 新查询从此不包含该教材，物理清理可异步重试。
```

- 更新失败：旧 `current_revision_id` 不变。
- 删除逻辑库：停用该库的关联；不再属于任何有效库的文档停用。
- 删除不影响题库。
- 旧修订原文保留用于历史引用；显式删除后禁止发起新的相关详解。
- 不通过重试、重建或迟到任务恢复已删除文档。

### 5.6 租约、幂等与崩溃恢复

```python
def claim_job():
    with db.begin_immediate():
        job = first_queued_or_expired_job()

        job.attempt += 1
        job.lease_token = uuid4()
        job.lease_until = now() + seconds(90)
        job.state = "running"

    return job, job.lease_token
```

- 每20秒续租。
- 所有 checkpoint、成功发布、失败发布必须校验当前租约 token。
- 短暂网络错误最多自动重试3次，退避2／10／30秒。
- 身份变化、维度错误、指纹损坏不自动重试。
- 相同幂等键和相同载荷返回原结果；相同键不同载荷返回409。
- 向量 upsert 成功、checkpoint 前崩溃：重做相同 point ID，不追加重复数据。
- SQL 发布成功、HTTP 响应丢失：同一幂等键返回已成功任务。
- 旧 worker 返回时只能留下不可达向量，不能修改有效修订或索引指针。
- 自动重试结束后释放重建闸门；手动重试按当前索引状态创建新任务。

---

## 六、检索范围、RAG 协议与 LLM 详解

### 6.1 任教范围

用户当前选择：

```ts
type TextbookSelection = {
  gradeId: string;
  subjectId: string;
  editionId: string;
  documentIds: string[]; // 明确确认的书册
};
```

默认行为：

- 一个当前年级、一个学科、一个教材版本。
- 基础书册由老师确认。
- 个人教材显式勾选加入。
- 同册可以配置到多个年级。
- 未配置或没有可用书册时阻止 RAG 发送，并保留输入。
- 改范围只影响新轮，不修改历史消息。

### 6.2 共享类型

```ts
type ScopeSnapshot = {
  schemaVersion: 2;
  selection: TextbookSelection;
  documents: {
    documentId: string;
    documentRevisionId: string;
    metadataRevisionId: string;
  }[];
  embeddingGenerationId: string;
  scopeHash: string;
};

type ScopeInput =
  | { kind: "selection"; selection: TextbookSelection }
  | { kind: "frozen"; snapshot: ScopeSnapshot };

type EvidenceRef = {
  evidenceId: string;
  documentRevisionId: string;
  normalizedTextSha256: string;
  charStart: number; // Unicode码点，[start, end)
  charEnd: number;
};

type TextbookEvidence = EvidenceRef & {
  documentId: string;
  title: string;
  editionLabel: string;
  chapterPath: string[];
  text: string;
  originalFileSha256: string;
  locator:
    | { kind: "markdown"; lineStart: number; lineEnd: number }
    | { kind: "pdf"; pageStart: number; pageEnd: number }
    | { kind: "docx"; blockStart: number; blockEnd: number };
  isSuperseded: boolean;
};

type RagResult = {
  contractVersion: 2;
  resultId: string;
  status: "ok" | "partial" | "uncertain" | "no_evidence";
  scopeSnapshot: ScopeSnapshot;
  points: {
    pointId: string;
    title: string;
    summary: string;
    evidenceIds: string[];
  }[];
  evidence: TextbookEvidence[];
  reason?: string;
};
```

`scopeHash` 用于检测快照意外变化，不是认证凭证。服务端必须重新检查归属、修订、分类和删除状态。

### 6.3 范围解析

```python
def resolve_selection(selection, current_user):
    with db.read_transaction():
        generation = require_active_generation()

        documents = catalog.require_documents(selection.documentIds)
        require(no_duplicates(documents))
        require(documents, "RAG_SCOPE_EMPTY")

        resolved = []

        for doc in documents:
            require(not doc.deleted)
            require(doc.owner_id in {"system", current_user.id})

            metadata = load_current_metadata(doc)
            require(selection.gradeId in metadata.grade_ids)
            require(metadata.subject_id == selection.subjectId)
            require(metadata.edition_id == selection.editionId)
            require(has_matching_live_library_membership(doc, selection))

            revision = require_current_revision(doc)
            require_generation_revision_ready(generation, revision)

            resolved.append((doc, revision, metadata))

        return immutable_scope_snapshot(
            selection, resolved, generation,
        )
```

新查询不允许客户端直接传：

```text
ownerId
collectionName
磁盘路径
未经校验的 SQL/Qdrant filter
```

### 6.4 检索算法

首版明确采用：

- 向量候选50。
- BM25候选50。
- RRF，常数60。
- 不新增重排模型，不开启网页补检和自动多轮查询改写。
- 最终证据按完整区间和上下文预算选择，最多20条、总证据不超过40,000字符。

```python
def retrieve(question, scope):
    require_sources_still_live(scope)

    generation = require_readable_generation(
        scope.embeddingGenerationId,
    )
    profile = require_exact_profile(generation.profile_id)

    qv = embed_query(
        profile.query_prefix + question,
        truncate=False,
    )

    allowed = allowed_chunks_for_scope(scope, generation)

    dense = qdrant.search(
        collection=generation.collection_name,
        vector=qv,
        filter=AND(
            revision_id_in(allowed.revision_ids),
            chunk_set_id_in(allowed.chunk_set_ids),
            region_equals("body"),
        ),
        limit=50,
    )

    lexical = bm25_for_scope(allowed).search(question, limit=50)

    ranked = reciprocal_rank_fusion(
        dense,
        lexical,
        k=60,
        tie_breaker="stable_chunk_identity",
    )

    spans = expand_evidence(
        ranked,
        allowed_chunks=allowed,
        never_cross_document=True,
        never_cross_section=True,
        never_cross_exercise_gap=True,
    )

    evidence = [
        verify_source_and_reconstruct_span(span)
        for span in spans
    ]

    require_sources_still_live(scope)
    return select_whole_spans_within_budget(evidence)
```

BM25：

- 从 SQLite 中相同允许块集合构建。
- 允许使用有界内存缓存。
- 缓存键包含索引代、修订集合和分词版本。
- 不从全库取结果后再过滤。
- 不加载用户上传的 pickle 文件。
- 新版本不以 `.npy` 或 pickle 文件作为正式索引存储。

### 6.5 知识点首答

```python
def answer_knowledge_points(question, scope):
    evidence = retrieve(question, scope)

    if not evidence:
        return RagResult(
            status="no_evidence",
            points=[],
            evidence=[],
            reason="当前教材范围没有找到足够依据",
        )

    proposal = local_summary_model.generate_structured(
        question=question,
        evidence=evidence,
        instruction="""
        只概括与题目有关的教材知识点、适用条件和原文依据。
        每条知识点必须引用提供的 evidenceId。
        不提供完整解题推导，不编造教材出处。
        """,
    )

    points = validate_and_filter_points(proposal, evidence)

    if not points:
        return partial_result(
            evidence=evidence,
            reason="知识点概括未完成，保留教材原文供核对",
        )

    return complete_result(points, evidence, scope)
```

- 概括模型首版沿用本地 `qwen2.5:7b`。
- 原文一致性验证与概括的教学正确性分别验收。
- 有合法原文但概括失败时显示明确的部分结果。
- 没有证据时不生成貌似有教材依据的讲解。

### 6.6 定位与详解的协议区别

定位保留现有事件编号与恢复语义：

```text
id: 1
event: message.start
data: {requestId, sessionId, turnId, messageId, scopeSnapshot}

event: rag.result
data: {...身份字段, result}

event: text.delta
event: wait-user
event: reply.accepted
event: message.end
event: error
```

要求：

- 前端必须消费并保存 `rag.result`，不能再只保存游标。
- 结构化结果、消息正文和游标在同一次会话持久化中提交。
- 断线不取消定位；显式 `/rag/cancel` 才取消。
- 事件重复去重，事件缺号或身份不符报协议错误。
- 后端重启后丢失的定位轮返回过期，不偷偷重新推理。

详解：

```ts
type RagExplainRequest = {
  requestId: string;
  sessionId: string;
  turnId: string; // 新详解轮次
  modelProfileId: string;
  originalQuestion: string;
  followUp: string;
  scopeSnapshot: ScopeSnapshot;
  evidenceRefs: EvidenceRef[];
  history: {
    role: "user" | "assistant";
    content: string;
  }[];
  maxOutputTokens?: number;
};
```

- 使用普通聊天 SSE 语义，无定位事件游标。
- 断开或停止关闭上游。
- 不经 `/rag/reply`，不再次自动检索。
- 不计入“首次定位＋最多两次澄清重定位”的上限。
- 详解模型在用户点击时冻结，失败重试不偷偷换模型。

### 6.7 服务端重建引用与详解

```python
async def explain(body):
    scope = authorize_frozen_scope(
        body.scopeSnapshot,
        purpose="explain",
    )

    evidence = []

    for ref in body.evidenceRefs:
        require(ref.documentRevisionId in scope.revision_ids)

        revision = catalog.require_revision(ref.documentRevisionId)
        require_document_live_and_owned(revision.document_id)

        text = load_immutable_normalized_text(revision)
        require(sha256_utf8(text) == ref.normalizedTextSha256)
        require(0 <= ref.charStart < ref.charEnd <= len(text))
        require_valid_body_interval(revision, ref.charStart, ref.charEnd)

        evidence.append(
            build_evidence_from_source(ref, revision, text),
        )

    require(evidence, "RAG_EVIDENCE_UNAVAILABLE")

    model = resolve_requested_chat_model(body.modelProfileId)
    request, budget = build_explanation_request(
        model=model,
        original_question=body.originalQuestion,
        follow_up=body.followUp,
        evidence=evidence,
        history=body.history,
    )

    return stream_through_shared_provider(
        model=model,
        request=request,
        context={
            "evidence": evidence,
            "budget": budget,
        },
    )
```

重建引用时：

- 不依赖定位结果的600秒缓存。
- 不要求 Qdrant 在线。
- 不要求旧 Embedding 模型仍安装。
- 不信任前端传来的引用正文、页码或磁盘路径。
- 引用可跨相邻正文块，因此不能只用单个 `chunkId`。
- 前端全文高亮必须将码点坐标转换为 UTF-16 下标。

### 6.8 预算

详解上下文包含：

```text
服务端规则 + 原题 + 当前追问 + 完整教材证据 + 历史
```

处理顺序：

1. 校验硬上限。
2. 删除最旧的完整历史消息。
3. 仍超限则返回 `CONTEXT_TOO_LARGE`。
4. 提示减少所选证据或选择更大上下文模型。

原题、当前追问和用户已选证据不静默截断。继续使用现有200条、单条32,000字符、总120,000字符的后端上限，并遵守模型预算。字符估算与精确 token 计数必须区分。

---

## 七、页面、追问状态机与历史兼容

### 7.1 教材页面

```text
/knowledge-bases
  基础库 / 我的教材 / 历史登记
  年级、学科、版本筛选
  导入教材
  入库任务

/knowledge-bases/libraries/[libraryId]
  分类与书册
  当前可用修订
  正在构建的修订
  更新 / 停用 / 删除
  来源预览
```

旧 `/knowledge-bases/[kbName]`：

- 保留为“历史本地登记”只读入口。
- 继续读取旧 localStorage。
- 不启动模拟索引定时器。
- 不把旧 `ready` 解释为真实可检索。
- 旧课程引用仍按旧 ID 打开，不按名字自动关联新教材。
- 本轮不扩展“将真实教材库附加到课程”的新能力。

目录加载：

```ts
type CatalogState =
  | { phase: "loading" }
  | { phase: "ready"; libraries: LibrarySummary[] }
  | { phase: "failed"; error: ApiError };
```

读取失败必须是 `failed`，不能变成空数组后覆盖数据。

### 7.2 追问卡结构

视觉要求：

- 当前输入框的字体 token、宽度、圆角、细边框和留白。
- 顶部：标签、问题、左右箭头、页码。
- 中部：编号选项，最后一项为自由输入。
- 底部：键盘说明、“忽略”和“继续”。
- 选中和主按钮使用现有蓝色主题，不照搬截图黑色按钮。
- 手机布局不横向溢出，长题文自然换行。

状态：

```ts
type DraftDisposition =
  | "unanswered"
  | "answered"
  | "skipped";

type AskDraft = {
  labels: string[];
  freeText: string;
  disposition: DraftDisposition;
};

type InteractionKind = "clarification" | "guidance";
```

新卡统一单选；历史多选内容只读兼容。

### 7.3 卡片交互伪代码

```ts
function pickOption(label: string) {
  if (locked) return;

  updateDraft({
    labels: [label],
    freeText: "",
    disposition: "unanswered",
  });

  // 不自动翻页
}

function editCustom(text: string) {
  if (locked) return;

  updateDraft({
    labels: text.trim() ? [] : current.labels,
    freeText: text,
    disposition: "unanswered",
  });
}

function continueCurrent() {
  if (pendingSubmission) {
    retryExactSubmission();
    return;
  }

  if (!hasValidAnswer(current)) return;

  setDisposition("answered");
  advanceOrSubmit();
}

function skipCurrent() {
  if (locked) return;

  updateDraft({
    labels: [],
    freeText: "",
    disposition: "skipped",
  });

  advanceOrSubmit();
}

function advanceOrSubmit() {
  if (!isLastQuestion()) {
    showNextQuestion();
    return;
  }

  const pending = firstQuestionWithDisposition("unanswered");

  if (pending) {
    showQuestion(pending);
    showNotice("还有问题尚未确认");
    return;
  }

  dispatchByInteractionKind(serializeAnswers());
}
```

页码箭头只浏览，不确认、不提交、不清空草稿。

键盘：

- 方向键只在选项列表中移动焦点。
- Enter／Space 选中选项。
- 不抢文本输入框光标。
- 中文输入法组合期间不触发确认。
- Tab 保持正常焦点顺序。

### 7.4 澄清提交

```ts
async function submitClarification(answers: AskUserAnswer[]) {
  const pending = interaction.pendingSubmission ?? {
    submissionId: createId(),
    answers,
  };

  await persistPendingSubmission(pending);
  // 本地保存失败时不发 HTTP

  try {
    await ragApi.reply({
      sessionId,
      turnId,
      interactionId,
      ...pending,
    });
  } catch (error) {
    if (requestDefinitelyNotConsumed(error)) {
      clearPendingAndAllowEditing();
    } else {
      keepPendingAndAllowExactRetryOnly();
    }
  }
}
```

- `reply.accepted` 到达后确认提交结果。
- 提交结果不确定时，改选、输入和忽略均锁定。
- 主输入框补充回答调用同一套“填当前题＋继续”动作，不再自动跳过其余题。

### 7.5 详解引导

详解引导在 RAG 终态后创建，不占用 `waitingInteractionId`。

```ts
async function submitGuidance(guidanceId: string, direction: string) {
  const guidance = getGuidance(guidanceId);

  if (guidance.targetTurnId) {
    retryExistingExplainTurn(guidance.targetTurnId);
    return;
  }

  const model = requireCurrentChatModel();
  const turnId = createId();

  await persistAtomically({
    guidance: {
      ...guidance,
      status: "dispatching",
      targetTurnId: turnId,
    },
    explainTurn: {
      turnId,
      modelProfileId: model.id,
      originalQuestion,
      scopeSnapshot,
      evidenceRefs,
      followUp: direction,
    },
  });

  startExplainStream(turnId);
}

function dismissGuidance(id: string) {
  persistGuidanceStatus(id, "dismissed");
  // 不调用 RAG reply、cancel 或 LLM
}
```

没有可用聊天模型时保留选择，并提示去配置；不能消耗卡片或创建空助手消息。

---

## 八、独立题库规格

### 8.1 题目类型

```ts
type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "fill_blank"
  | "short_answer"
  | "other";

type QuestionContent = {
  type: QuestionType;
  stemMarkdown: string;
  options: {
    key: string;
    textMarkdown: string;
  }[];
  answer: {
    choiceKeys?: string[];
    accepted?: boolean;
    textMarkdown?: string;
  } | null;
  explanationMarkdown: string | null;
  assetIds: string[];
};
```

综合题首版保留小问文本结构，使用 `other`；不实现复杂递归小题编辑器。

### 8.2 独立数据库

```text
question_imports
  id, owner_id, file_sha256, original_blob_id
  state, revision, warnings_json

question_source_blocks
  id, import_id, text, locator_json

question_drafts
  id, import_id, revision
  content_json, metadata_json, source_spans_json
  extraction_method
  review_state                  needs_review | reviewed | excluded
  missing_answer_acknowledged
  warnings_json

question_suggestions
  id, organization_job_id
  target_draft_id, base_draft_revision
  proposed_content_json
  source_block_ids_json
  state                         pending | applied | rejected

questions
  id, owner_id, current_revision_id
  status                        confirmed | archived

question_revisions
  id, question_id
  content_json, metadata_json
  answer_state                  provided | not_provided
  content_fingerprint
  confirmed_at

question_sources
  question_id, source_span_json

question_submissions
  submission_id UNIQUE
  request_fingerprint
  result_json

question_jobs
  id, kind, state, checkpoint_json, error_code
```

题库元数据包含：

```text
学段、年级、学科、教材版本、知识点标签
难度：unspecified | easy | medium | hard
```

### 8.3 导入流程

```python
def parse_question_file(file):
    original = save_original_file(file)
    extracted = extract_document(original)

    blocks = save_source_blocks(extracted)
    drafts, unassigned = split_questions_by_rules(blocks)

    for draft in drafts:
        draft.review_state = "needs_review"
        save(draft)

    return {
        "drafts": drafts,
        "unassignedBlocks": unassigned,
        "warnings": extracted.warnings,
    }
```

必须保留无法归属的原文块，不能为了显示“完成”而丢弃。

校对页提供：

- 原文位置与题目草稿并排查看。
- 修改题干、选项、答案、解析和分类。
- 拆分草稿、合并草稿、排除非题目内容。
- 补传缺失图片。
- 标记“原文未提供答案”。
- 标记“已校对”。

编辑任何已校对草稿后，重新变为 `needs_review`。

### 8.4 AI 整理

```python
def organize_questions(selection, model_id):
    snapshot = freeze_selected_blocks_and_draft_revisions(selection)
    job = create_organization_job(snapshot, model_id)

    for batch in pack_complete_blocks_within_budget(snapshot):
        result = selected_llm.generate_structured(
            input=batch,
            instruction="""
            整理提供的试题原文。
            返回题干、选项、原文已有答案和解析，以及 sourceBlockIds。
            不推断原文缺失的答案，不引用输入之外的来源。
            """,
        )

        suggestion = validate_result_against_source_blocks(result, batch)
        save_suggestion(job, suggestion)

    return job
```

默认限制：

- 每批不超过6,000输入字符，并进一步受所选模型预算限制。
- 输出预算不超过2,048 tokens及模型配置上限。
- 超长内容按带来源偏移的段落拆批。
- 非法 JSON、截断输出或未知来源 ID使该批失败，原文保留。
- 部分成功可展示建议；失败批可单独重试。
- AI 建议不直接覆盖人工草稿。

```python
def apply_suggestion(suggestion_id, expected_draft_revision):
    with question_db.transaction():
        suggestion = require_pending_suggestion(suggestion_id)
        draft = require_draft_revision(
            suggestion.target_draft_id,
            expected_draft_revision,
        )

        require(
            draft.revision == suggestion.base_draft_revision,
            "DRAFT_REVISION_CONFLICT",
        )

        draft.content = suggestion.proposed_content
        draft.review_state = "needs_review"
        draft.revision += 1
        suggestion.state = "applied"
```

### 8.5 重复题与确认入库

精确指纹：

```python
fingerprint = sha256(normalize({
    "type": question.type,
    "stem": question.stem,
    "orderedOptions": question.options,
    "assetHashes": question.asset_hashes,
}))
```

指纹不包含答案和解析；同题不同答案进入冲突校对。

允许操作：

- `skip`：默认跳过重复题。
- `link_existing`：增加来源，不覆盖已有题。
- `edit_as_new`：修改后重新检测，确实不同才作为新题。

```python
def confirm_questions(request):
    with question_db.transaction():
        old = submissions.find(request.submissionId)

        if old:
            require_same_fingerprint(old, request)
            return old.result

        drafts = require_exact_draft_revisions(request.items)

        for draft in drafts:
            require(draft.review_state == "reviewed")
            validate_question_structure(draft)

            if draft.answer is None:
                require(draft.missing_answer_acknowledged)

            validate_duplicate_resolution(draft)

        result = insert_confirmed_questions_and_sources(drafts)
        save_submission_result(request, result)

    return result
```

事务失败整体不确认，并返回逐条原因。缺失答案可以经人工明确确认后入库，但继续显示“答案缺失”。

---

## 九、HTTP 接口与错误语义

所有路径以 `/api/v1` 为前缀。新增请求使用严格 Pydantic 校验，未知字段拒绝。

| 接口 | 用途 |
|---|---|
| `GET /textbook-taxonomy` | 年级、学科、版本字典 |
| `GET/POST /textbook-libraries` | 列表、创建逻辑库 |
| `GET/PATCH/DELETE /textbook-libraries/{id}` | 详情、修改、停用 |
| `POST /textbook-imports` | 上传文件并创建解析草稿 |
| `GET/PATCH /textbook-imports/{id}` | 预览、分类、警告确认 |
| `POST /textbook-imports/{id}/commit` | 提交入库任务 |
| `GET /textbook-jobs/{id}` | 阶段、进度、错误 |
| `POST /textbook-jobs/{id}/cancel` | 请求取消 |
| `POST /textbook-jobs/{id}/retry` | 按当前状态创建合法重试 |
| `GET/PATCH/DELETE /textbooks/{id}` | 书册详情、分类修订、删除 |
| `GET /textbook-revisions/{id}/source` | 受控原文与定位 |
| `GET/PUT /teaching-settings` | 当前任教配置 |
| `GET /embedding-models` | 本地已安装候选 |
| `POST /embedding-probes` | 实际嵌入能力检测 |
| `GET/POST /embedding-profiles` | 配置列表与保存 |
| `POST /textbook-index/rebuilds` | 新建重建任务 |
| `GET /textbook-index/status` | 当前模型、索引代和重建状态 |
| 现有 `/rag/status/stream/reply/cancel` | 定位与澄清，扩展v2契约 |
| `POST /rag/explain/stream` | 所选模型详解 |
| `POST /question-imports` | 题目文件导入 |
| `GET /question-imports/{id}` | 草稿、原文、未归属块 |
| `PATCH /question-drafts/{id}` | 乐观锁编辑 |
| `POST /question-imports/{id}/split` | 拆分草稿 |
| `POST /question-imports/{id}/merge` | 合并草稿 |
| `POST /question-imports/{id}/organize` | 用户主动AI整理 |
| `POST /question-suggestions/{id}/apply` | 应用建议 |
| `POST /question-imports/{id}/confirm` | 幂等确认入库 |
| `GET /questions` | 筛选与分页 |
| `GET/PATCH/DELETE /questions/{id}` | 详情、修订、归档删除 |

公共约定：

```ts
type ApiErrorEnvelope = {
  code: string;
  message: string;
  requestId: string;
  retryable: boolean;
  details?: unknown; // 仅可展示、脱敏信息
};
```

| 错误 | HTTP | 行为 |
|---|---:|---|
| `REVISION_CONFLICT` | 409 | 保留用户编辑，要求刷新比较 |
| `IDEMPOTENCY_CONFLICT` | 409 | 同一提交键载荷不同 |
| `INDEX_REBUILD_IN_PROGRESS` | 409 | 保存草稿，暂不发布 |
| `INDEX_MUTATION_BUSY` | 409 | 等待当前入库结束后重建 |
| `EMBEDDING_MODEL_CHANGED` | 409 | 禁止继续使用错误模型空间 |
| `RAG_SCOPE_EMPTY` | 422 | 不回退全库 |
| `RAG_SCOPE_CHANGED` | 409 | 教材已停用或删除 |
| `RAG_TURN_EXPIRED` | 410 | 保留历史，显式重新定位 |
| `RAG_EVIDENCE_UNAVAILABLE` | 409 | 不自动替换引用 |
| `QDRANT_UNAVAILABLE` | 503 | 不冒充无匹配 |
| `EMBEDDING_UNAVAILABLE` | 503 | 不回退云端 |
| `CONTEXT_TOO_LARGE` | 413 | 保留输入，不截断 |
| `DOCUMENT_NEEDS_OCR` | 422 | 不生成空索引 |

`/rag/status` 分别报告检索、本地概括、原文访问状态；不能用一个 `localOnly: true`笼统描述可能使用云端聊天模型的详解。

---

## 十、迁移、启用与备份

### 10.1 旧索引迁移

```python
def migrate_legacy_assets(source_root, legacy_assets):
    manifest = discover_source_files(source_root)
    legacy = load_legacy_manifest(legacy_assets)

    validate_legacy_shapes_order_and_fingerprints(legacy)
    validate_legacy_embedding_identity(legacy)

    for source in manifest:
        origin_key = source_set_id + normalized_relative_path(source)
        document = get_or_create_document_by_origin_key(origin_key)

        original = copy_into_managed_store(source)
        revision = reconstruct_immutable_revision(original)

        if legacy_has_verified_vectors_for(source):
            chunk_set = reconstruct_legacy_chunk_set(source, legacy)

            for row in legacy_rows_for(source):
                new_point = namespace_legacy_row(
                    document=document,
                    revision=revision,
                    chunk_set=chunk_set,
                    legacy_row=row,
                )
                upsert_verified_legacy_vector(new_point)
        else:
            create_normal_ingest_job(document, revision)

    write_per_document_migration_report()
```

规则：

- 只迁移通过核验的旧向量。
- 复用向量时保留旧章节前缀和原文处理语义。
- `.npy`读取使用 `allow_pickle=False`。
- 旧缓存批次和旧 `chunk_id`不是可信新主键。
- 如果旧向量身份无法证明，重新嵌入该部分并记录原因。
- 58册逐册列出：已迁移、重新解析、失败、待分类。
- 不根据旧状态文档中的册数推断实际完成度。

### 10.2 正式启用顺序

1. 在隔离数据库和 Qdrant 测试 volume 完成工程与业务验收。
2. 对旧资产和新托管数据做本地备份。
3. 总控独占迁移窗口，将基础教材导入新目录。
4. 核对逐册清单、块数、引用和模型身份。
5. 切换生产 RAG 到新运行时。
6. 执行本机真实检索冒烟测试。
7. 保留旧资产，不在本批自动删除。

普通应用启动不能自动进行全量迁移或重建。

### 10.3 备份与恢复

增加明确命令入口：

```text
rag:db:start
rag:db:status
rag:migrate
rag:backup
rag:restore
test:rag
```

备份包含：

- SQLite 一致性备份，不直接复制正在写入的 WAL 数据库文件。
- Qdrant snapshot。
- 原件、规范化文本、来源映射、资源。
- 指纹清单和当前索引代。
- 独立题库备份。

恢复先写入新目录和新 volume并校验，不能直接覆盖正在使用的数据。凭证不混入教材或题库备份清单。

---

## 十一、多智能体任务卡与文件归属

### 11.1 公共任务卡字段

每个任务由“以下公共字段＋任务表中的专属字段”组成。总控派发时填写真实 agent ID和当时 SHA。

```text
总任务 ID：RAG-REBUILD
计划版本：v1.0
仓库：H:\备份xuexi\智启课源

开始候选：
  派发时执行 git rev-parse HEAD；
  同时记录工作区差异，不把本稿调查SHA当成强制起点。

用户授权：
  本计划一至十节确定的功能范围。

固定参考：
  Local_Pdf_Chat_RAG@38b39f641a5228673fc46a64c802307e2e6d5209
  DeepTutor@42fab3cf429a1fbf36b257ab8d116a3814964202，仅现有视觉参考
  当前项目 /chat 为视觉基准

禁止：
  修改原教材、原Word、无关模块、他人文件；
  切换共享分支、批量暂存、推送、部署；
  将真实失败改成模拟；
  将测试指向正式草稿、凭证或正式数据目录。

交付状态：
  实现者只能提交 ready_for_review；
  独立验收者给 pass/fail/not_run；
  总控确认是否已验收。
```

### 11.2 拟新增目录约定

以下均为拟新增实现目录：

```text
apps/api/app/providers/embeddings/
apps/api/app/services/document_parsing/
apps/api/app/services/textbook_ingest/
apps/api/app/services/textbook_index/
apps/api/app/services/question_bank/
apps/api/app/repositories/textbook_catalog/
apps/api/app/repositories/question_bank/

apps/web/src/features/question-bank/
apps/web/src/features/model-settings/embedding/
```

共享类型与公共接线由总控独占；业务实现不能自行修改共享契约。

### 11.3 任务表

| ID | 角色及独占范围 | 依赖 | 行为闭环与验收重点 |
|---|---|---|---|
| `C0-CONTRACT` | 总控；前后端共享类型、schemas、配置、路由注册、依赖、脚本、导航、权威文档 | 无 | 冻结类型、接口、状态和目录归属；提供测试注入入口 |
| `B0-CATALOG` | 后端实现；`repositories/textbook_catalog/`及专属测试 | C0 | SQL迁移、修订、分类、范围、事务、幂等、删除 |
| `B1-INGEST` | 后端实现；`providers/embeddings/`、`document_parsing/`、`textbook_ingest/`、`textbook_index/`及专属路由和测试 | C0、B0 | 模型检测→文件解析→入库→重建→切换→恢复 |
| `B2-RAG` | 后端实现；现有RAG服务、runtime、证据、详解执行层及专属测试 | C0、B0、B1接口 | 严格范围、结构化结果、旧轮固定、详解与预算 |
| `B3-QBANK` | 后端实现；`repositories/question_bank/`、`services/question_bank/`及专属路由和测试 | C0、B1解析接口 | 拆题→校对草稿→AI建议→确认→独立持久化 |
| `F0-TEXTBOOK` | 前端实现；教材模块、教材路由、教材API客户端、Embedding设置子目录及专属测试 | C0 | 真实上传、状态恢复、分类、任教配置、模型重建界面 |
| `F1-CHAT` | 前端实现；聊天模块、RAG与详解客户端、相关store和测试 | C0、B2接口 | 范围显示、结果持久化、追问卡、详解、旧记录兼容 |
| `F2-QBANK` | 前端实现；题库模块、题库路由、题库API客户端及专属测试 | C0、B3接口 | 导入校对、并排原文、拆合题、重复处理、确认管理 |
| `A1-VERIFY` | 独立验收；只读产品，独占验收报告和截图目录 | 稳定候选 | 按测试矩阵独立复现，不能边验边修 |
| `C1-INTEGRATE` | 总控；集成、文档、全量检查、迁移启用与Git | 全部实现 | 范围核对、兼容回归、正式迁移及最终结果卡 |

具体规则：

- `apps/api/app/main.py`、公共配置、所有共享 schema／contract、根包文件及锁文件由总控写。
- `F0-TEXTBOOK` 不直接修改设置总装配文件；向总控交付嵌入面板组件，由总控挂载。
- `F2-QBANK` 不修改公共导航；由总控将题库放到组卷下方。
- `B3-QBANK` 调用冻结的解析接口，不改共享解析器。
- `F1-CHAT` 独占聊天 store，其他任务不得同时编辑。
- 旧 `knowledge-catalog`和课程仓储原则上保留；确需兼容补丁时由总控单独分配写入窗口。

### 11.4 执行批次

```text
批次1：
  C0 契约与接线骨架
  B0 数据模型与仓储

批次2：
  B1 本地模型、解析、入库与重建
  F0 教材及Embedding界面
  F2 题库界面骨架与校对交互

批次3：
  B2 RAG与详解
  B3 题库后端
  F1 聊天范围与追问

批次4：
  总控集成
  各实现者按缺陷卡修复
  固定候选后 A1 独立验收

批次5：
  正式数据迁移
  本机真实验收
  文档与本地提交
```

同时活跃人数不超过工具实际容量；没有可靠并行能力时按同样任务卡串行执行。

### 11.5 运行资源

| 资源 | 所有者与规则 |
|---|---|
| 正式前端5173、API8000 | 不用于自动化验收，不停止用户进程 |
| 测试前端5174、API8001 | 总控统一启动与串行调度 |
| 正式 Qdrant6333 | 正式启用阶段由总控管理 |
| 测试 Qdrant16333 | 独立 compose project和named volume |
| `.next`、`.next-test` | 总控独占构建，不并行覆盖 |
| 单元测试数据库 | 各任务独立临时目录 |
| 浏览器 | 独立上下文，不读写用户会话 |
| 临时证据 | `_work/rag-rebuild-v1/<task-id>/` |
| 留存证据 | 总控整理至 `docs/qa/RAG-REBUILD-v1/` |
| Git | 仅总控操作 |

日志不得保存题目全文、模型凭证或完整上传文档。失败证据使用固定测试材料。

---

## 十二、验收矩阵与完成标准

### 12.1 必须覆盖的场景

| 编号 | 场景 | 通过条件 |
|---|---|---|
| E01 | 本地模型发现与探测 | 聊天模型不被误认成Embedding模型 |
| E02 | 远程地址或云代理模型 | 明确拒绝 |
| E03 | 同名模型digest改变 | 阻止错误写入和查询 |
| E04 | 换模型成功 | 全站指针一次切换，查询模型与collection匹配 |
| E05 | 重建失败／取消 | 原索引继续可用 |
| E06 | 重建期间删除 | 不被重建任务复活 |
| I01 | 三种教材格式 | 真实解析、预览、入库、引用可用 |
| I02 | 扫描PDF | 明确提示，不生成空成功索引 |
| I03 | 更新失败 | 旧修订继续检索 |
| I04 | 重复上传／重复提交 | 不重复发布 |
| I05 | upsert后崩溃 | 重试不增加重复point |
| I06 | 旧worker迟到 | 无权发布或清除新任务闸门 |
| M01 | 58册迁移 | 逐册状态可核对，54＋4差异明确 |
| M02 | 数学A/B重名块 | 无互相覆盖 |
| R01 | 高二数学与其他范围 | 向量、BM25、邻块均不串库 |
| R02 | 空范围 | 不回退全库 |
| R03 | 跨scope缓存 | 不返回其他范围结果 |
| R04 | 公式、CRLF、emoji | 原文与坐标一致 |
| R05 | SSE重复、缺号、串会话 | 去重或明确错误，不污染消息 |
| R06 | 结果与游标保存 | 刷新后不丢结构化依据 |
| X01 | 后端重启后详解 | 通过原文引用重建，不依赖600秒缓存 |
| X02 | Qdrant离线后详解 | 已有有效原文引用仍可详解 |
| X03 | 教材删除后新详解 | 拒绝，历史消息仍可读 |
| X04 | 预算超限 | 原题不截断，输入保留 |
| X05 | 模型首包／流中错误、停止 | 错误和取消契约正确 |
| U01 | 选中与继续 | 不自动跳题 |
| U02 | 忽略、回看、未处理题 | 状态明确，不暗中跳过 |
| U03 | 未确认提交 | 只能重试原载荷 |
| U04 | IME与键盘 | 不误提交、不抢光标 |
| Q01 | 试题导入校对 | 原文未归属内容不丢弃 |
| Q02 | AI与人工并发编辑 | 建议不覆盖新草稿 |
| Q03 | 缺答案／重复题 | 明确校对后处理 |
| Q04 | 确认事务与幂等 | 无半批确认和重复题目 |
| Q05 | 数据隔离 | 题目不进入教材向量库 |
| C01 | 旧知识登记、课程引用 | 可读、无同名误绑定 |
| V01 | 1440、1920、390视口 | 无溢出，符合当前/chat风格 |
| V02 | 减少动画与焦点 | 偏好生效，交互可达 |

### 12.2 工程检查

实施后执行：

```powershell
$env:NODE_OPTIONS = "--no-experimental-webstorage"
npm.cmd run check
npm.cmd run test:api
npm.cmd run test:chat
```

另增加并执行：

```text
test:rag
  隔离 Qdrant + API8001 + 测试数据
  构建 .next-test
  新教材/RAG/题库端到端场景
```

全量 e2e 必须使用隔离 API和测试构建，不能误连正式8000服务。

保留并回归已有课程、模型设置、导航和聊天用例。不要把新建测试写成“已有测试已通过”。

### 12.3 质量与交付门槛

分别报告：

```text
工程检查
受控测试替身
真实Qdrant
真实本地Embedding
真实本地知识点概括
真实所选聊天模型详解
人工教学质量
人工视觉
```

任何未执行项填写 `not_run`和原因。

首版为每个学科建立至少3个有明确期望书册／证据的受控样例，并增加数学A/B同题区分、无证据和缺条件样例。自动引用正确不等于概括或解题正确，人工教学质量单列。

实现者结果卡：

```text
任务 ID / 版本：
负责人：
开始 SHA：
候选 SHA 或差异标识：
状态：ready_for_review

修改文件：
行为闭环：
保留数据与兼容方式：

验证：
- command：
  result：
  evidence：

首败与修复：
未执行：
真实服务边界：
视觉边界：
剩余风险：
需总控决定：
仍在运行的进程与资源：
```

---

## 十三、可直接复制的启动提示词

### 13.1 实施总控启动提示词

```text
你接手“智启课源”，担任 RAG-REBUILD v1.0 实施总控。

工作目录：
H:\备份xuexi\智启课源

本消息附带的《智启课源 RAG 重构实施计划：
RAG-REBUILD v1.0 · 伪代码级规格与多智能体交接稿》
是本轮明确任务规格。按当前运行模式工作；进入可执行模式后，
完成该计划的实现、集成、验收组织、必要文档和本地提交。

先读：
1. 根 AGENTS.md。
2. docs/PROJECT_GUIDE.md。
3. docs/CURRENT_STATUS.md。
4. docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md。
5. docs/replica 下三矩阵。
6. 所修改模块的 AGENTS.md。

先执行只读现场核对：
git status --short
git log -5 --oneline
git rev-parse HEAD

保留用户与其他智能体的改动，不切换共享分支，不 reset/clean。
计划中的调查SHA不是要求恢复的目标。
本轮是新增任务，不因旧STATUS批次已完成而停在接手说明。

已经确认的目标：
- Qdrant本机Docker替换正式运行时.npy向量索引。
- SQLite管理教材目录、修订、任务和任教范围。
- 基础人教版全部现有书册与个人教材分开管理。
- Markdown、文本PDF、DOCX真实导入、校对和入库。
- 年级、学科、教材版本及具体书册严格限定检索范围。
- Embedding可配置多个本地Ollama模型，全站使用一个当前模型；
  默认bge-m3，换模型重建成功后切换，不能混用向量空间。
- RAG首答知识点概览和教材原文依据；
  用户主动使用当前聊天模型继续详解。
- 追问卡按用户截图布局、当前/chat视觉实现。
- 独立题库导入校对与管理，侧栏位于智能组卷下方。
- 本轮不实现登录、OCR、云Embedding或组卷。

仓库旧规则中的“禁止数据库”和“教材仅模拟登记”
已由本轮用户明确需求覆盖。同步更新适用规则，不为此重复询问用户。

你负责：
1. 将本轮任务登记到CURRENT_STATUS唯一当前任务入口；
   稳定决定写PROJECT_GUIDE，接口写API/ROUTES。
2. 冻结共享契约和文件/资源归属。
3. 按计划任务卡派发有限子任务。
4. 独占共享契约、main/config接线、导航、锁文件、权威文档、
   构建资源、正式迁移和最终Git。
5. 集成后固定候选，再安排独立只读验收。
6. 失败交回实现者修复，升级任务版本，再固定候选复验。
7. 完成适用检查、迁移、真实验收和本地小提交。

同一文件同一时段只能有一个写入者。
并行能力不足时按同样任务卡串行，不伪造独立验收。
不要等待另一名Codex替你完成普通接口或产品代码。

所有真实业务留在apps/api。
现有聊天Provider、SSE、模型管理、会话持久化和统一预算继续复用。
不要将详解接回/rag/reply；该接口只处理教材澄清。
不要把旧模拟知识库按同名自动迁成真实教材库。

测试使用5174、8001、独立Qdrant16333和临时数据。
不使用用户5173/8000会话做自动化，不清空正式草稿。
只停止本批创建的进程，不读取其他工具登录文件，不输出密钥。
正式资产迁移由你在隔离验收和备份完成后独占执行。

视觉任务使用frontend-design技能，实际查看当前/chat与附件参考。
功能、视觉、动画、受控替身、真实本地服务及人工教学质量分开报告。
未执行写not_run及原因，不能用build通过代替业务验收。

不新增重复HANDOFF/TASKS进度入口。
必要任务卡与结果卡按现有协作模板组织；
进度只在CURRENT_STATUS维护，脱敏验收证据归档docs/qa。
不修改旧历史证据来消除首败。

最终交付：
任务ID、开始/实现/最终SHA、改动范围、数据兼容、
各类检查和证据、迁移清单、pass/fail/not_run、
剩余问题、运行资源状态及下一动作。
不推送、不部署、不改全局Git身份。
```

### 13.2 后端实现者启动提示词

```text
你是 RAG-REBUILD v1.0 的有界后端实现者。

先读取总控分配的任务卡、根AGENTS和apps/api/AGENTS，
核对任务ID/版本、开始候选、共享契约版本、独占文件与测试资源。

只实现任务卡范围：
B0-CATALOG / B1-INGEST / B2-RAG / B3-QBANK 中明确分配的一项。
不要自行修改共享schema、main.py、公共配置、锁文件、权威文档或Git。
发现接口缺口，向总控提交具体类型/行为变更建议。

以计划中的SQL权威、不可变修订、全局active_generation_id、
范围预过滤、提交幂等和错误契约为约束。
所有外部I/O在SQL写事务外执行。
本地Embedding不得自动下载、调用云端或混用不同模型空间。
题库不得写入教材collection。
后端不得新增聊天题目或详解历史的持久化日志。

实现完整正常、错误、取消、重试、重启恢复路径。
测试注入临时目录和替身，不能使用正式.env或正式.local-data。
真实模型调用使用总控分配的窗口，不抢占他人的Ollama任务。

运行有意义的专属测试，保留首败与修复证据。
完成后按结果卡提交ready_for_review，列出差异、检查、
未执行项、风险和仍运行资源，然后停止写入。
不自行宣布模块已验收，不自行提交Git。
```

### 13.3 前端实现者启动提示词

```text
你是 RAG-REBUILD v1.0 的有界前端实现者。

先读任务卡、根AGENTS、对应模块AGENTS及冻结共享契约。
使用frontend-design技能，实际对照当前/chat和用户追问截图。

只修改总控分配的：
F0-TEXTBOOK / F1-CHAT / F2-QBANK 对应文件。
不修改共享contracts、导航、锁文件或权威文档。
需要公共挂载或导航调整时交总控集成。

视觉复用当前项目的字体token、蓝色主题、输入框圆角、
细边框与留白；不要新增独立主题或动画库。

所有真实状态来自FastAPI，生产不得用定时器伪造入库。
请求失败不能当空目录。
保存失败保留编辑，刷新恢复不能重新上传或重复提交。

聊天任务特别注意：
- rag.result结构化证据与正文、游标同次持久化。
- 澄清卡和详解引导有不同生命周期及请求通道。
- 单选不自动跳题，继续确认，忽略只跳当前题。
- pendingSubmission存在时不能改答案或创建新提交。
- 中文输入法、方向键和文本光标互不干扰。
- 详解冻结当前模型和证据，重试不换模型。
- 历史消息缺新字段时正常可读，不猜造引用。

教材任务保留历史登记与课程旧引用。
题库AI结果只能成为待校对建议，不能覆盖人工草稿或自动确认入库。

使用隔离浏览器和总控分配的构建/端口。
检查桌面与390px手机、错误/空态/等待/取消/恢复、
键盘焦点和减少动画。

完成后提交ready_for_review结果卡，列文件、验证、
截图、未执行项、数据兼容和资源状态，停止写入。
不自行提交Git或宣布整体验收。
```

### 13.4 独立验收者启动提示词

```text
你是 RAG-REBUILD v1.0 的独立验收者。

开始前要求总控提供：
任务版本、稳定候选SHA或明确差异标识、
实现者停止写入确认、隔离数据与运行资源归属。

先读计划验收矩阵、根和相关模块AGENTS。
只读产品代码，证据写入分配目录。
不得边验边修，不改断言掩盖失败，不修改权威文档或Git。

独立验证以下高风险边界：
- 查询模型和向量索引代始终匹配。
- 重建失败保留旧索引，删除不被迟到任务复活。
- 高二数学、其他学科、A/B版本和个人范围不串库。
- BM25、向量和邻块扩展使用同一范围。
- 引用绑定不可变原文，跨chunk、公式及Unicode坐标正确。
- 后端重启后的既有证据可以发起详解；
  已失去的定位轮明确过期，不偷偷重跑。
- 详解使用所选模型，取消关闭上游，超预算保留输入。
- 澄清提交幂等，详解引导不占RAG澄清轮数。
- 题库与教材向量库独立，AI建议不覆盖人工草稿。
- 历史知识登记、课程引用和聊天记录保持兼容。

实际查看页面和截图，检查交互全过程、焦点和减少动画。
构建通过、路由存在、截图文件存在均不是验收结论。

每项输出pass/fail/not_run、具体命令、退出码、触发条件和证据。
真实Qdrant、本地Embedding、本地概括、所选LLM、
受控替身、人工教学质量分别记录。
失败给最小复现交总控，由实现者修复后换新候选复验。

最后提交独立验收结果卡和准确未验范围。
不能复述实现者报告代替自己的验证。
```

