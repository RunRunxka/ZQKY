# 06 关系模式与数据表设计

本文件对应 `sql/` 下的参考 DDL，含全部 39 张新增表。SQL 是设计验证附件，未接入应用迁移。列级值域 CHECK 与表级约束共同生效；完整 SQL 可逐表核对。

## 公共约定

新业务实体 ID 使用 TEXT UUID，学科 ID 复用现有项目学科键；分数以百分之一分 INTEGER 保存；时间为 UTC ISO 8601；日期为 YYYY-MM-DD。新增主键显式 NOT NULL。EXT 是跨数据库逻辑引用，SQL 不伪造跨库外键。JSON 列仅保证 JSON 语法，有类型契约的结构由服务验证。已有表保留现行 DDL，不在本设计中重建。

`version` 是内容修订序号，`revision` 是可变实体编辑锁，两者不能混用。试卷草稿修改任何小题或标注时，服务在同一事务检查并递增所属 `papers.revision`；教案/练习草稿同理使用所属 `lesson_plans.revision` / `practice_sets.revision`。`ai_proposals.base_revision` 取请求时所属稳定实体的编辑锁，而不是内容版本号；成绩导入草稿使用自身 `score_imports.revision`。确认后内容封存，修改建立新修订。

## knowledge

### subjects — 学科字典

关系模式：`subjects(id, code, name, status)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 复用现有项目学科键，不另造不兼容身份 |
| code | TEXT | 否 | — | — | 稳定学科代码，复用项目已有 subjectId |
| name | TEXT | 否 | — | — | 学科名称 |
| status | TEXT | 否 | 'active' | — | 启用或归档 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### knowledge_points — 知识点身份与目录位置

关系模式：`knowledge_points(id, subject_id, code, parent_id, current_revision_id, sort_order, status, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK；FK → knowledge_point_revisions.knowledge_point_id | 稳定 UUID，由服务端生成 |
| subject_id | TEXT | 否 | — | FK → knowledge_points.subject_id；FK → subjects.id | 所属学科 |
| code | TEXT | 否 | — | — | 学科内稳定业务代码，不编码教材路径 |
| parent_id | TEXT | 是 | — | FK → knowledge_points.id | 上位知识点，可空；不代表教材章节 |
| current_revision_id | TEXT | 是 | — | FK → knowledge_point_revisions.id | 当前知识点内容修订 |
| sort_order | INTEGER | 否 | 0 | — | 同层显示顺序 |
| status | TEXT | 否 | 'active' | — | 归档后保留历史引用 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(subject_id,code)`
- `UNIQUE(id,subject_id)`
- `FOREIGN KEY(parent_id,subject_id) REFERENCES knowledge_points(id,subject_id)`
- `FOREIGN KEY(current_revision_id,id) REFERENCES knowledge_point_revisions(id,knowledge_point_id) DEFERRABLE INITIALLY DEFERRED`
- `CHECK(parent_id IS NULL OR parent_id<>id)`

### knowledge_point_revisions — 知识点不可变内容修订

关系模式：`knowledge_point_revisions(id, knowledge_point_id, version, name, description, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| knowledge_point_id | TEXT | 否 | — | FK → knowledge_points.id | 知识点身份 |
| version | INTEGER | 否 | — | — | 从 1 递增的内容版本 |
| name | TEXT | 否 | — | — | 正式知识点名称 |
| description | TEXT | 否 | '' | — | 定义与范围说明，不记录学生掌握概率 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(knowledge_point_id,version)`
- `UNIQUE(id,knowledge_point_id)`

### knowledge_aliases — 知识点检索别名

关系模式：`knowledge_aliases(id, knowledge_point_id, alias, normalized_alias, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| knowledge_point_id | TEXT | 否 | — | FK → knowledge_points.id | 正式知识点 |
| alias | TEXT | 否 | — | — | 人工确认的同义名称 |
| normalized_alias | TEXT | 否 | — | — | 服务端规范化后的检索词 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(knowledge_point_id,normalized_alias)`

### textbook_knowledge_links — 教材依据与知识点的可选关联

关系模式：`textbook_knowledge_links(id, knowledge_point_id, knowledge_revision_id, document_revision_id, locator_json, locator_hash, title_snapshot, source, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| knowledge_point_id | TEXT | 否 | — | FK → knowledge_point_revisions.knowledge_point_id | 本库知识点身份 |
| knowledge_revision_id | TEXT | 否 | — | FK → knowledge_point_revisions.id | 本库知识点修订 |
| document_revision_id | TEXT | 否 | — | EXT | EXT：教材目录 document_revisions.id |
| locator_json | TEXT | 否 | — | — | 章节或原文区间定位，服务端核验范围 |
| locator_hash | TEXT | 否 | — | — | 定位规范化 JSON 的 SHA-256 |
| title_snapshot | TEXT | 否 | — | — | 关联时的教材标题 |
| source | TEXT | 否 | — | — | 人工标注或确认后的 AI 建议 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `FOREIGN KEY(knowledge_revision_id,knowledge_point_id) REFERENCES knowledge_point_revisions(id,knowledge_point_id)`
- `UNIQUE(knowledge_revision_id,document_revision_id,locator_hash)`

## teaching

### file_assets — 本模块文件登记

关系模式：`file_assets(id, owner_id, kind, blob_key, sha256, original_name, media_type, byte_size, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| kind | TEXT | 否 | — | — | 名单、成绩、原卷、导出或配图 |
| blob_key | TEXT | 否 | — | — | 受管相对文件键；禁止外部任意路径 |
| sha256 | TEXT | 否 | — | — | 原始字节 SHA-256 |
| original_name | TEXT | 否 | — | — | 上传文件名，仅展示，不用于拼接路径 |
| media_type | TEXT | 否 | — | — | MIME 类型 |
| byte_size | INTEGER | 否 | — | — | 字节数 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### classes — 班级

关系模式：`classes(id, owner_id, code, name, school_year, grade_id, status, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| code | TEXT | 否 | — | — | 用户范围内班级业务代码 |
| name | TEXT | 否 | — | — | 班级显示名称 |
| school_year | TEXT | 否 | — | — | 学年，例如 2026-2027 |
| grade_id | TEXT | 否 | — | — | 复用项目年级字典；班级不固定为某一学科 |
| status | TEXT | 否 | 'active' | — | 启用或归档 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(owner_id,school_year,code)`

### students — 学生稳定身份

关系模式：`students(id, owner_id, student_no, name, status, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| student_no | TEXT | 是 | — | — | 学号按文本保存，保留前导零；无学号时教师明确建档 |
| name | TEXT | 否 | — | — | 姓名用于展示和人工核对，不作主键 |
| status | TEXT | 否 | 'active' | — | 学生归档状态 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(owner_id,student_no)`
- `CHECK(student_no IS NULL OR length(trim(student_no))>0)`

### class_memberships — 学生班级归属历史

关系模式：`class_memberships(id, class_id, student_id, joined_on, left_on)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| class_id | TEXT | 否 | — | FK → classes.id | 班级 |
| student_id | TEXT | 否 | — | FK → students.id | 学生 |
| joined_on | TEXT | 否 | — | — | 入班日期 YYYY-MM-DD |
| left_on | TEXT | 是 | — | — | 离班日期，可空；不删除旧归属 |

表级约束：

- `CHECK(left_on IS NULL OR left_on>=joined_on)`
- `UNIQUE(class_id,student_id,joined_on)`

### papers — 试卷稳定身份

关系模式：`papers(id, owner_id, subject_id, title, current_revision_id, status, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK；FK → paper_revisions.paper_id | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| subject_id | TEXT | 否 | — | EXT | EXT：知识库 subjects.id |
| title | TEXT | 否 | — | — | 试卷名称 |
| current_revision_id | TEXT | 是 | — | FK → paper_revisions.id | 当前已确认修订 |
| status | TEXT | 否 | 'active' | — | 试卷归档状态 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `FOREIGN KEY(current_revision_id,id) REFERENCES paper_revisions(id,paper_id) DEFERRABLE INITIALLY DEFERRED`

### paper_revisions — 原卷或练习转换的试卷修订

关系模式：`paper_revisions(id, paper_id, version, source_file_id, source_practice_revision_id, total_score_units, state, confirmed_at, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| paper_id | TEXT | 否 | — | FK → papers.id | 试卷身份 |
| version | INTEGER | 否 | — | — | 内容修订序号 |
| source_file_id | TEXT | 是 | — | FK → file_assets.id | 原始 DOCX 或其他原卷文件 |
| source_practice_revision_id | TEXT | 是 | — | FK → practice_revisions.id | 从已审核练习转换，可空 |
| total_score_units | INTEGER | 否 | — | — | 总分乘 100 后的整数，例如 100 分记 10000 |
| state | TEXT | 否 | 'draft' | — | 草稿可编辑；确认后不可变 |
| confirmed_at | TEXT | 是 | — | — | 确认时间 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(paper_id,version)`
- `UNIQUE(id,paper_id)`
- `CHECK((source_file_id IS NOT NULL)+(source_practice_revision_id IS NOT NULL)=1)`
- `CHECK((state='draft' AND confirmed_at IS NULL) OR (state='confirmed' AND confirmed_at IS NOT NULL))`

### paper_items — 试卷题干容器与独立计分小题

关系模式：`paper_items(id, paper_revision_id, parent_item_id, question_no, ordinal, is_scored, max_score_units, question_revision_id, content_json, source_locator_json)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| paper_revision_id | TEXT | 否 | — | FK → paper_items.paper_revision_id；FK → paper_revisions.id | 固定试卷修订 |
| parent_item_id | TEXT | 是 | — | FK → paper_items.id | 同份修订中的共享题干或大题容器 |
| question_no | TEXT | 否 | — | — | 完整题号，如 16(1)，不可只写 (1) |
| ordinal | INTEGER | 否 | — | — | 整卷展示顺序 |
| is_scored | INTEGER | 否 | — | — | 1 为成绩表对应小题；0 仅用于组织题干 |
| max_score_units | INTEGER | 是 | — | — | 计分小题满分乘 100；题干容器必须为空 |
| question_revision_id | TEXT | 是 | — | EXT | EXT：现有题库修订，可空；分析不强制先入题库 |
| content_json | TEXT | 否 | — | — | 题干、选项、公式、附件和共用材料快照 |
| source_locator_json | TEXT | 否 | '{}' | — | 原件块序号或预览定位 |

表级约束：

- `UNIQUE(paper_revision_id,question_no)`
- `UNIQUE(paper_revision_id,ordinal)`
- `UNIQUE(id,paper_revision_id)`
- `FOREIGN KEY(parent_item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id)`
- `CHECK(parent_item_id IS NULL OR parent_item_id<>id)`
- `CHECK((is_scored=1 AND max_score_units IS NOT NULL AND max_score_units>0) OR (is_scored=0 AND max_score_units IS NULL))`

### paper_item_knowledge — 本次试卷小题的已确认知识点

关系模式：`paper_item_knowledge(item_id, paper_revision_id, knowledge_point_id, knowledge_revision_id, knowledge_name_snapshot, role, source)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| item_id | TEXT | 否 | — | PK(1)；FK → paper_items.id | 本卷小题 |
| paper_revision_id | TEXT | 否 | — | FK → paper_items.paper_revision_id | 冗余范围键，用复合外键防跨卷关联 |
| knowledge_point_id | TEXT | 否 | — | PK(2) | EXT：独立知识点身份 |
| knowledge_revision_id | TEXT | 否 | — | EXT | EXT：知识点修订 |
| knowledge_name_snapshot | TEXT | 否 | — | — | 教师确认时名称 |
| role | TEXT | 否 | — | — | 分类角色；两者都参与失分关联，不设权重 |
| source | TEXT | 否 | — | — | 人工、确认后的 AI 或确认后的题库标注 |

表级约束：

- `PRIMARY KEY(item_id,knowledge_point_id)`
- `FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id)`

### assessments — 一次施测

关系模式：`assessments(id, owner_id, paper_revision_id, title, assessment_type, held_on, active_score_revision_id, state, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK；FK → score_revisions.assessment_id | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| paper_revision_id | TEXT | 否 | — | FK → paper_revisions.id | 使用已确认试卷 |
| title | TEXT | 否 | — | — | 月考、单元测验或课堂练习名称 |
| assessment_type | TEXT | 否 | — | — | 考试、测验、练习 |
| held_on | TEXT | 否 | — | — | 施测日期 |
| active_score_revision_id | TEXT | 是 | — | FK → score_revisions.id | 当前正式成绩修订 |
| state | TEXT | 否 | 'open' | — | 开放导入、结束或归档 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(id,paper_revision_id)`
- `FOREIGN KEY(active_score_revision_id,id) REFERENCES score_revisions(id,assessment_id) DEFERRABLE INITIALLY DEFERRED`

### assessment_classes — 施测适用班级

关系模式：`assessment_classes(assessment_id, class_id)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| assessment_id | TEXT | 否 | — | PK(1)；FK → assessments.id | 同一试卷可用于多个班 |
| class_id | TEXT | 否 | — | PK(2)；FK → classes.id | 参加班级 |

表级约束：

- `PRIMARY KEY(assessment_id,class_id)`

### assessment_participants — 学生本次参加与补考记录

关系模式：`assessment_participants(id, assessment_id, student_id, class_id, attempt_no, attendance, name_snapshot, student_no_snapshot)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| assessment_id | TEXT | 否 | — | FK → assessment_classes.assessment_id | 施测 |
| student_id | TEXT | 否 | — | FK → students.id | 学生稳定身份 |
| class_id | TEXT | 否 | — | FK → assessment_classes.class_id | 本次班级，转班后历史不变 |
| attempt_no | INTEGER | 否 | 1 | — | 本次施测内尝试序号，补考可新增 |
| attendance | TEXT | 否 | — | — | 参加、缺考或免考，不代替小题分数 |
| name_snapshot | TEXT | 否 | — | — | 本次学生名称快照 |
| student_no_snapshot | TEXT | 是 | — | — | 本次学号快照 |

表级约束：

- `FOREIGN KEY(assessment_id,class_id) REFERENCES assessment_classes(assessment_id,class_id)`
- `UNIQUE(assessment_id,student_id,attempt_no)`
- `UNIQUE(id,assessment_id)`

### score_imports — 成绩导入草稿

关系模式：`score_imports(id, assessment_id, file_id, base_score_revision_id, mapping_json, state, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| assessment_id | TEXT | 否 | — | FK → score_revisions.assessment_id；FK → assessments.id | 目标施测 |
| file_id | TEXT | 否 | — | FK → file_assets.id | 原始成绩 XLSX/CSV |
| base_score_revision_id | TEXT | 是 | — | FK → score_revisions.id | 上传时的正式成绩版本，提交前检查未变化 |
| mapping_json | TEXT | 否 | '{}' | — | 工作表、表头、学生列和题号列映射 |
| state | TEXT | 否 | — | — | 导入生命周期 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(id,assessment_id)`
- `FOREIGN KEY(base_score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id)`

### score_import_rows — 成绩表预览行与异常

关系模式：`score_import_rows(import_id, row_no, participant_id, raw_cells_json, issues_json)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| import_id | TEXT | 否 | — | PK(1)；FK → score_imports.id | 导入批次 |
| row_no | INTEGER | 否 | — | PK(2) | 原表行号 |
| participant_id | TEXT | 是 | — | FK → assessment_participants.id | 教师确认的学生参加记录，可空待匹配 |
| raw_cells_json | TEXT | 否 | — | — | 原始单元格值与题号；只在本地保存 |
| issues_json | TEXT | 否 | '[]' | — | 重名、越界、缺列等错误 |

表级约束：

- `PRIMARY KEY(import_id,row_no)`

### score_revisions — 全量成绩快照修订

关系模式：`score_revisions(id, assessment_id, version, source_import_id, base_revision_id, state, confirmed_at, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| assessment_id | TEXT | 否 | — | FK → score_revisions.assessment_id；FK → score_imports.assessment_id；FK → assessments.id | 所属施测 |
| version | INTEGER | 否 | — | — | 单次施测内修订序号 |
| source_import_id | TEXT | 是 | — | FK → score_imports.id | 来源成绩导入批次 |
| base_revision_id | TEXT | 是 | — | FK → score_revisions.id | 被修正的旧成绩版本 |
| state | TEXT | 否 | 'draft' | — | 完整确认后不可变 |
| confirmed_at | TEXT | 是 | — | — | 正式确认时间 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(assessment_id,version)`
- `UNIQUE(id,assessment_id)`
- `FOREIGN KEY(source_import_id,assessment_id) REFERENCES score_imports(id,assessment_id)`
- `FOREIGN KEY(base_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id)`
- `CHECK(base_revision_id IS NULL OR base_revision_id<>id)`
- `CHECK((state='draft' AND confirmed_at IS NULL) OR (state='confirmed' AND confirmed_at IS NOT NULL))`

### student_item_scores — 教师已提供的小题得分事实

关系模式：`student_item_scores(score_revision_id, assessment_id, paper_revision_id, participant_id, item_id, score_units, status)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| score_revision_id | TEXT | 否 | — | PK(1)；FK → score_revisions.id | 正式成绩快照；修正生成新版本 |
| assessment_id | TEXT | 否 | — | FK → assessments.id；FK → assessment_participants.assessment_id；FK → score_revisions.assessment_id | 所属施测，用于复合外键 |
| paper_revision_id | TEXT | 否 | — | FK → paper_items.paper_revision_id；FK → assessments.paper_revision_id | 本次原卷修订，用于复合外键 |
| participant_id | TEXT | 否 | — | PK(2)；FK → assessment_participants.id | 学生参加记录 |
| item_id | TEXT | 否 | — | PK(3)；FK → paper_items.id | 成绩表对应计分小题 |
| score_units | INTEGER | 是 | — | — | 实际分数乘 100；非 recorded 必须为空 |
| status | TEXT | 否 | — | — | 已录分、未录入、缺考、免考 |

表级约束：

- `PRIMARY KEY(score_revision_id,participant_id,item_id)`
- `FOREIGN KEY(score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id)`
- `FOREIGN KEY(participant_id,assessment_id) REFERENCES assessment_participants(id,assessment_id)`
- `FOREIGN KEY(assessment_id,paper_revision_id) REFERENCES assessments(id,paper_revision_id)`
- `FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id)`
- `CHECK((status='recorded' AND score_units IS NOT NULL AND score_units>=0) OR (status<>'recorded' AND score_units IS NULL))`

### analysis_runs — 失分关联学情报告快照

关系模式：`analysis_runs(id, assessment_id, score_revision_id, rule_code, selection_json, roster_snapshot_json, input_hash, state, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| assessment_id | TEXT | 否 | — | FK → score_revisions.assessment_id | 本次施测 |
| score_revision_id | TEXT | 否 | — | FK → score_revisions.id | 指定正式成绩版本 |
| rule_code | TEXT | 否 | 'any_loss_v1' | — | 任一相关小题失分即列需巩固；不预测掌握概率 |
| selection_json | TEXT | 否 | — | — | 分析班级和学生尝试选择；同学生不重复计入班级人数 |
| roster_snapshot_json | TEXT | 否 | — | — | 参测名单、班级与出勤冻结 |
| input_hash | TEXT | 否 | — | — | 成绩、试卷、映射、名单和规则的规范化输入指纹 |
| state | TEXT | 否 | — | — | 报告生成状态 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `FOREIGN KEY(score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id)`
- `UNIQUE(assessment_id,input_hash)`
- `UNIQUE(id,score_revision_id)`

### analysis_results — 每个学生每个知识点的本次表现

关系模式：`analysis_results(run_id, participant_id, knowledge_point_id, knowledge_name_snapshot, observation, expected_count, valid_count, loss_count, earned_units, available_units)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| run_id | TEXT | 否 | — | PK(1)；FK → analysis_runs.id | 分析快照 |
| participant_id | TEXT | 否 | — | PK(2)；FK → assessment_participants.id | 本次学生作答记录 |
| knowledge_point_id | TEXT | 否 | — | PK(3) | EXT：知识点身份，名称等由报告证据冻结 |
| knowledge_name_snapshot | TEXT | 否 | — | — | 报告显示名称 |
| observation | TEXT | 否 | — | — | 需巩固、相关题均满分、资料不全、无有效成绩 |
| expected_count | INTEGER | 否 | — | — | 已确认关联的计分小题数 |
| valid_count | INTEGER | 否 | — | — | 有 recorded 成绩的小题数 |
| loss_count | INTEGER | 否 | — | — | recorded 且实际分数低于满分的小题数 |
| earned_units | INTEGER | 否 | — | — | 相关有效小题实际分数合计，仅作为事实展示 |
| available_units | INTEGER | 否 | — | — | 相关有效小题满分合计，不含未录入等 |

表级约束：

- `PRIMARY KEY(run_id,participant_id,knowledge_point_id)`
- `CHECK((observation='needs_consolidation' AND loss_count>0) OR (observation='no_evidence' AND valid_count=0 AND loss_count=0) OR (observation='incomplete' AND valid_count>0 AND valid_count<expected_count AND loss_count=0) OR (observation='full_credit' AND expected_count>0 AND valid_count=expected_count AND loss_count=0))`

### analysis_evidence — 报告至小题成绩的证据链

关系模式：`analysis_evidence(run_id, participant_id, knowledge_point_id, item_id, score_revision_id, knowledge_revision_id, is_loss)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| run_id | TEXT | 否 | — | PK(1)；FK → analysis_runs.id；FK → analysis_results.run_id | 分析报告 |
| participant_id | TEXT | 否 | — | PK(2)；FK → student_item_scores.participant_id；FK → analysis_results.participant_id | 学生参加记录 |
| knowledge_point_id | TEXT | 否 | — | PK(3)；FK → paper_item_knowledge.knowledge_point_id；FK → analysis_results.knowledge_point_id | 本条结果的知识点 |
| item_id | TEXT | 否 | — | PK(4)；FK → paper_item_knowledge.item_id；FK → student_item_scores.item_id | 具体小题 |
| score_revision_id | TEXT | 否 | — | FK → student_item_scores.score_revision_id；FK → analysis_runs.score_revision_id | 报告所用成绩版本 |
| knowledge_revision_id | TEXT | 否 | — | EXT | EXT：该小题确认时的知识点修订 |
| is_loss | INTEGER | 否 | — | — | 是否有实际失分；非 recorded 为 0，但不算有效题 |

表级约束：

- `PRIMARY KEY(run_id,participant_id,knowledge_point_id,item_id)`
- `FOREIGN KEY(run_id,participant_id,knowledge_point_id) REFERENCES analysis_results(run_id,participant_id,knowledge_point_id)`
- `FOREIGN KEY(run_id,score_revision_id) REFERENCES analysis_runs(id,score_revision_id)`
- `FOREIGN KEY(score_revision_id,participant_id,item_id) REFERENCES student_item_scores(score_revision_id,participant_id,item_id)`
- `FOREIGN KEY(item_id,knowledge_point_id) REFERENCES paper_item_knowledge(item_id,knowledge_point_id)`

### analysis_teacher_notes — 教师对报告的说明

关系模式：`analysis_teacher_notes(id, run_id, participant_id, knowledge_point_id, note, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| run_id | TEXT | 否 | — | FK → analysis_runs.id | 对应分析报告 |
| participant_id | TEXT | 是 | — | FK → assessment_participants.id | 可空代表班级说明 |
| knowledge_point_id | TEXT | 是 | — | EXT | EXT：可空代表整体说明 |
| note | TEXT | 否 | — | — | 教师补充或修正解释，不覆盖原始失分事实 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### group_sets — 按本课目标建立的临时分组方案

关系模式：`group_sets(id, run_id, topic, criteria_json, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| run_id | TEXT | 否 | — | FK → analysis_runs.id | 分组依据报告 |
| topic | TEXT | 否 | — | — | 本课课题或教学目标 |
| criteria_json | TEXT | 否 | — | — | 教师确定的分组依据，不生成永久能力标签 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### learning_groups — 分组方案中的组

关系模式：`learning_groups(id, group_set_id, label, name, ordinal)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| group_set_id | TEXT | 否 | — | FK → group_sets.id | 本次分组方案 |
| label | TEXT | 否 | — | — | A/B/C 或教师自定义代码 |
| name | TEXT | 否 | — | — | 教师定义的分组名称 |
| ordinal | INTEGER | 否 | — | — | 显示顺序 |

表级约束：

- `UNIQUE(group_set_id,label)`
- `UNIQUE(id,group_set_id)`

### group_members — 临时分组成员

关系模式：`group_members(group_set_id, group_id, participant_id)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| group_set_id | TEXT | 否 | — | PK(1)；FK → learning_groups.group_set_id；FK → group_sets.id | 分组方案 |
| group_id | TEXT | 否 | — | FK → learning_groups.id | 方案内分组 |
| participant_id | TEXT | 否 | — | PK(2)；FK → assessment_participants.id | 报告内学生参加记录 |

表级约束：

- `PRIMARY KEY(group_set_id,participant_id)`
- `FOREIGN KEY(group_id,group_set_id) REFERENCES learning_groups(id,group_set_id)`

### lesson_plans — 教案身份

关系模式：`lesson_plans(id, owner_id, class_id, subject_id, title, current_revision_id, status, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK；FK → lesson_plan_revisions.lesson_plan_id | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| class_id | TEXT | 否 | — | FK → classes.id | 授课班级 |
| subject_id | TEXT | 否 | — | EXT | EXT：学科 |
| title | TEXT | 否 | — | — | 教案标题 |
| current_revision_id | TEXT | 是 | — | FK → lesson_plan_revisions.id | 当前修订 |
| status | TEXT | 否 | 'active' | — | 教案归档 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `FOREIGN KEY(current_revision_id,id) REFERENCES lesson_plan_revisions(id,lesson_plan_id) DEFERRABLE INITIALLY DEFERRED`

### lesson_plan_revisions — 结构化教案内容修订

关系模式：`lesson_plan_revisions(id, lesson_plan_id, version, analysis_run_id, group_set_id, schema_version, context_json, content_json, model_snapshot_json, source, state, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| lesson_plan_id | TEXT | 否 | — | FK → lesson_plans.id | 教案身份 |
| version | INTEGER | 否 | — | — | 内容修订序号 |
| analysis_run_id | TEXT | 是 | — | FK → analysis_runs.id | 学情报告依据；旧教案迁入或无学情备课可空 |
| group_set_id | TEXT | 是 | — | FK → group_sets.id | 本节分组方案，可空 |
| schema_version | INTEGER | 否 | 2 | — | 教案 JSON 契约版本 |
| context_json | TEXT | 否 | — | — | 课型、课时、时长、教材范围快照和教学约束 |
| content_json | TEXT | 否 | — | — | 目标、重难点、过程、检测、练习安排和反思模板 |
| model_snapshot_json | TEXT | 否 | '{}' | — | AI 模型身份与生成参数，无凭证 |
| source | TEXT | 否 | — | — | 手工、接受 AI 建议或旧草稿迁入 |
| state | TEXT | 否 | 'draft' | — | 草稿可改；审核版不可变 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(lesson_plan_id,version)`
- `UNIQUE(id,lesson_plan_id)`

### lesson_plan_evidence — 教案调整理由与来源

关系模式：`lesson_plan_evidence(id, lesson_revision_id, kind, target_path, source_ref_json, content_snapshot, sha256)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| lesson_revision_id | TEXT | 否 | — | FK → lesson_plan_revisions.id | 对应教案修订 |
| kind | TEXT | 否 | — | — | 学情、教材、题库或教师说明 |
| target_path | TEXT | 否 | — | — | 内容 JSON 路径，例如 process[1].design |
| source_ref_json | TEXT | 否 | — | — | 报告/原文区间/题目修订的精确引用 |
| content_snapshot | TEXT | 否 | — | — | 本次实际用于生成的证据文本或脱敏摘要 |
| sha256 | TEXT | 否 | — | — | 证据快照散列 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### practice_sets — 练习身份

关系模式：`practice_sets(id, owner_id, subject_id, title, current_revision_id, status, revision, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK；FK → practice_revisions.practice_set_id | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| subject_id | TEXT | 否 | — | EXT | EXT：学科 |
| title | TEXT | 否 | — | — | 练习名称 |
| current_revision_id | TEXT | 是 | — | FK → practice_revisions.id | 当前修订 |
| status | TEXT | 否 | 'active' | — | 启用或归档 |
| revision | INTEGER | 否 | 0 | — | 可变实体的乐观锁版本 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `FOREIGN KEY(current_revision_id,id) REFERENCES practice_revisions(id,practice_set_id) DEFERRABLE INITIALLY DEFERRED`

### practice_revisions — 固定练习内容与组卷约束

关系模式：`practice_revisions(id, practice_set_id, version, lesson_revision_id, group_id, constraints_json, state, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| practice_set_id | TEXT | 否 | — | FK → practice_sets.id | 练习身份 |
| version | INTEGER | 否 | — | — | 内容修订序号 |
| lesson_revision_id | TEXT | 是 | — | FK → lesson_plan_revisions.id | 关联教案修订，可空 |
| group_id | TEXT | 是 | — | FK → learning_groups.id | 目标分组，可空代表统一练习 |
| constraints_json | TEXT | 否 | — | — | 知识点、题量、时长、难度梯度、原题排除等教师约束 |
| state | TEXT | 否 | 'draft' | — | 审核后固定 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `UNIQUE(practice_set_id,version)`
- `UNIQUE(id,practice_set_id)`

### practice_items — 练习选题快照

关系模式：`practice_items(id, practice_revision_id, ordinal, question_revision_id, content_json, selection_reason, max_score_units, estimated_seconds)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| practice_revision_id | TEXT | 否 | — | FK → practice_revisions.id | 练习修订 |
| ordinal | INTEGER | 否 | — | — | 显示次序 |
| question_revision_id | TEXT | 否 | — | EXT | EXT：已确认题库修订；AI 草稿不能直接进入最终练习 |
| content_json | TEXT | 否 | — | — | 完整题干、共用材料、答案、配图快照 |
| selection_reason | TEXT | 否 | — | — | 选用理由，关联本节薄弱项 |
| max_score_units | INTEGER | 否 | — | — | 教师设置本次练习小题满分，便于回流 |
| estimated_seconds | INTEGER | 是 | — | — | 可空；教师估计完成时间 |

表级约束：

- `UNIQUE(practice_revision_id,ordinal)`

### practice_item_knowledge — 练习小题目标知识点

关系模式：`practice_item_knowledge(item_id, knowledge_point_id, knowledge_revision_id, knowledge_name_snapshot, role)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| item_id | TEXT | 否 | — | PK(1)；FK → practice_items.id | 练习小题 |
| knowledge_point_id | TEXT | 否 | — | PK(2) | EXT：知识点身份 |
| knowledge_revision_id | TEXT | 否 | — | EXT | EXT：知识点修订 |
| knowledge_name_snapshot | TEXT | 否 | — | — | 练习冻结时名称 |
| role | TEXT | 否 | — | — | 主要或关联知识点 |

表级约束：

- `PRIMARY KEY(item_id,knowledge_point_id)`

### workflow_jobs — 本地可恢复工作任务

关系模式：`workflow_jobs(id, owner_id, kind, input_json, model_snapshot_json, state, checkpoint_json, error_code, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| owner_id | TEXT | 否 | 'local' | — | 本地用户归属，预留授权范围 |
| kind | TEXT | 否 | — | — | 试卷知识点建议、教案生成或导出；题库复用既有 question_jobs |
| input_json | TEXT | 否 | — | — | 冻结输入及实体版本 |
| model_snapshot_json | TEXT | 否 | '{}' | — | 固定模型；导出任务可为空，无密钥 |
| state | TEXT | 否 | — | — | 重启遗留 running 转 interrupted，可重试 |
| checkpoint_json | TEXT | 否 | '{}' | — | 阶段进度，不假设上游流能重放 |
| error_code | TEXT | 是 | — | — | 脱敏错误代码 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### ai_proposals — 等待教师采用的 AI 建议

关系模式：`ai_proposals(id, job_id, target_kind, target_id, base_revision, payload_json, state, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| job_id | TEXT | 否 | — | FK → workflow_jobs.id | 建议来源任务 |
| target_kind | TEXT | 否 | — | — | 建议目标类型 |
| target_id | TEXT | 否 | — | — | 类型对应实体 ID，应用层校验 |
| base_revision | INTEGER | 否 | — | — | 请求时编辑版本；过期拒绝应用 |
| payload_json | TEXT | 否 | — | — | 有类型契约的建议内容 |
| state | TEXT | 否 | 'pending' | — | 待采用、采用、拒绝或过期 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### export_artifacts — 导出文件与输入版本

关系模式：`export_artifacts(id, job_id, file_id, entity_kind, entity_id, variant, format, input_hash, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| id | TEXT | 否 | — | PK | 稳定 UUID，由服务端生成 |
| job_id | TEXT | 否 | — | FK → workflow_jobs.id | 导出任务 |
| file_id | TEXT | 否 | — | FK → file_assets.id | 导出结果文件 |
| entity_kind | TEXT | 否 | — | — | 导出目标类型 |
| entity_id | TEXT | 否 | — | — | 对应固定版本，应用层校验 |
| variant | TEXT | 否 | — | — | 学生卷、教师卷、报告或成绩模板 |
| format | TEXT | 否 | — | — | 文件格式 |
| input_hash | TEXT | 否 | — | — | 输入快照指纹 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

### command_submissions — 关键写操作幂等记录

关系模式：`command_submissions(submission_id, operation, request_hash, result_json)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| submission_id | TEXT | 否 | — | PK | 客户端一次操作的稳定 ID |
| operation | TEXT | 否 | — | — | 确认试卷、导入成绩、采用建议等 |
| request_hash | TEXT | 否 | — | — | 相同 ID 不同请求必须报冲突 |
| result_json | TEXT | 否 | — | — | 与正式数据在同一库事务中写入的响应 |

表级约束：

- 主键、列级 CHECK 与外键见上表及 SQL。

## question_bank_extension

### question_knowledge_links — 题目修订与知识点的多对多关联

关系模式：`question_knowledge_links(question_revision_id, knowledge_point_id, knowledge_revision_id, subject_id_snapshot, knowledge_name_snapshot, role, created_at)`。

| 字段 | 类型 | 可空 | 默认值 | 键/引用 | 含义 |
|---|---|---|---|---|---|
| question_revision_id | TEXT | 否 | — | PK(1)；FK → question_revisions.id | 现有题库不可变题目修订；同题跨知识点不复制题干 |
| knowledge_point_id | TEXT | 否 | — | PK(2) | EXT：知识点身份 |
| knowledge_revision_id | TEXT | 否 | — | EXT | EXT：知识点内容修订 |
| subject_id_snapshot | TEXT | 否 | — | — | 关联时学科，跨库校验同学科 |
| knowledge_name_snapshot | TEXT | 否 | — | — | 关联时知识点名称，历史可读 |
| role | TEXT | 否 | — | — | 主要或关联知识点，仅分类、不分配分值 |
| created_at | TEXT | 否 | (strftime('%Y-%m-%dT%H:%M:%fZ','now')) | — | UTC 创建时间，界面转换为本地时间 |

表级约束：

- `PRIMARY KEY(question_revision_id,knowledge_point_id)`

## 索引与触发器

参考 SQL 包含知识树防环、同卷父子关系、失分值域、试卷总分、成绩矩阵完整、正式修订不可变等触发器；服务发布闸门还必须执行 02 中的 S 类规则。单凭建表成功不等于所有业务完整性已经实现。

### knowledge

```sql
CREATE INDEX IF NOT EXISTS ix_kp_parent ON knowledge_points(parent_id);
CREATE INDEX IF NOT EXISTS ix_alias_search ON knowledge_aliases(normalized_alias);
CREATE INDEX IF NOT EXISTS ix_textbook_doc ON textbook_knowledge_links(document_revision_id);
CREATE TRIGGER IF NOT EXISTS kp_cycle_update BEFORE UPDATE OF parent_id ON knowledge_points WHEN NEW.parent_id IS NOT NULL BEGIN
 SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_id) AS (SELECT id,parent_id FROM knowledge_points WHERE id=NEW.parent_id UNION SELECT p.id,p.parent_id FROM knowledge_points p JOIN ancestors a ON p.id=a.parent_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'KNOWLEDGE_CYCLE') END;
END;
CREATE TRIGGER IF NOT EXISTS kp_cycle_insert AFTER INSERT ON knowledge_points WHEN NEW.parent_id IS NOT NULL BEGIN
 SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_id) AS (SELECT id,parent_id FROM knowledge_points WHERE id=NEW.parent_id UNION SELECT p.id,p.parent_id FROM knowledge_points p JOIN ancestors a ON p.id=a.parent_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'KNOWLEDGE_CYCLE') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_knowledge_point_revisions_update BEFORE UPDATE ON knowledge_point_revisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_knowledge_point_revisions_delete BEFORE DELETE ON knowledge_point_revisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
```

### teaching

```sql
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_membership ON class_memberships(class_id,student_id) WHERE left_on IS NULL;
CREATE INDEX IF NOT EXISTS ix_membership_student ON class_memberships(student_id);
CREATE INDEX IF NOT EXISTS ix_paper_kp ON paper_item_knowledge(knowledge_point_id,item_id);
CREATE INDEX IF NOT EXISTS ix_participant_student ON assessment_participants(student_id,assessment_id);
CREATE INDEX IF NOT EXISTS ix_analysis_kp ON analysis_results(run_id,knowledge_point_id,observation);
CREATE INDEX IF NOT EXISTS ix_scores_participant ON student_item_scores(participant_id,score_revision_id);
CREATE INDEX IF NOT EXISTS ix_jobs_state ON workflow_jobs(state,created_at);
CREATE INDEX IF NOT EXISTS ix_practice_question ON practice_items(question_revision_id);
CREATE TRIGGER IF NOT EXISTS paper_cycle_update BEFORE UPDATE OF parent_item_id ON paper_items WHEN NEW.parent_item_id IS NOT NULL BEGIN
 SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_item_id) AS (SELECT id,parent_item_id FROM paper_items WHERE id=NEW.parent_item_id UNION SELECT p.id,p.parent_item_id FROM paper_items p JOIN ancestors a ON p.id=a.parent_item_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'ITEM_CYCLE') END;
END;
CREATE TRIGGER IF NOT EXISTS paper_cycle_insert AFTER INSERT ON paper_items WHEN NEW.parent_item_id IS NOT NULL BEGIN
 SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_item_id) AS (SELECT id,parent_item_id FROM paper_items WHERE id=NEW.parent_item_id UNION SELECT p.id,p.parent_item_id FROM paper_items p JOIN ancestors a ON p.id=a.parent_item_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'ITEM_CYCLE') END;
END;
CREATE TRIGGER IF NOT EXISTS assessment_confirmed_paper_insert BEFORE INSERT ON assessments BEGIN
 SELECT CASE WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)<>'confirmed' THEN RAISE(ABORT,'PAPER_NOT_CONFIRMED') END;
END;
CREATE TRIGGER IF NOT EXISTS assessment_paper_fixed BEFORE UPDATE OF paper_revision_id ON assessments WHEN NEW.paper_revision_id<>OLD.paper_revision_id BEGIN SELECT RAISE(ABORT,'ASSESSMENT_PAPER_FIXED'); END;
CREATE TRIGGER IF NOT EXISTS score_range_insert BEFORE INSERT ON student_item_scores BEGIN
 SELECT CASE WHEN (SELECT is_scored FROM paper_items WHERE id=NEW.item_id)<>1 THEN RAISE(ABORT,'NOT_SCORED_ITEM') END;
 SELECT CASE WHEN NEW.score_units>(SELECT max_score_units FROM paper_items WHERE id=NEW.item_id) THEN RAISE(ABORT,'SCORE_EXCEEDS_MAX') END;
END;
CREATE TRIGGER IF NOT EXISTS score_range_update BEFORE UPDATE ON student_item_scores BEGIN
 SELECT CASE WHEN (SELECT is_scored FROM paper_items WHERE id=NEW.item_id)<>1 THEN RAISE(ABORT,'NOT_SCORED_ITEM') END;
 SELECT CASE WHEN NEW.score_units>(SELECT max_score_units FROM paper_items WHERE id=NEW.item_id) THEN RAISE(ABORT,'SCORE_EXCEEDS_MAX') END;
END;
CREATE TRIGGER IF NOT EXISTS paper_confirm BEFORE UPDATE OF state ON paper_revisions WHEN NEW.state='confirmed' AND OLD.state='draft' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM paper_items WHERE paper_revision_id=NEW.id AND is_scored=1) THEN RAISE(ABORT,'NO_SCORED_ITEMS') END;
 SELECT CASE WHEN NEW.total_score_units<>(SELECT coalesce(sum(max_score_units),0) FROM paper_items WHERE paper_revision_id=NEW.id AND is_scored=1) THEN RAISE(ABORT,'PAPER_TOTAL_MISMATCH') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM paper_items i WHERE i.paper_revision_id=NEW.id AND i.is_scored=1 AND NOT EXISTS(SELECT 1 FROM paper_item_knowledge k WHERE k.item_id=i.id)) THEN RAISE(ABORT,'ITEM_KNOWLEDGE_MISSING') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM paper_items p JOIN paper_items c ON c.parent_item_id=p.id WHERE p.paper_revision_id=NEW.id AND p.is_scored=1) THEN RAISE(ABORT,'SCORED_ITEM_MUST_BE_LEAF') END;
 SELECT CASE WHEN NEW.source_practice_revision_id IS NOT NULL AND (SELECT state FROM practice_revisions WHERE id=NEW.source_practice_revision_id)<>'reviewed' THEN RAISE(ABORT,'PRACTICE_NOT_REVIEWED') END;
END;
CREATE TRIGGER IF NOT EXISTS score_confirm BEFORE UPDATE OF state ON score_revisions WHEN NEW.state='confirmed' AND OLD.state='draft' BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM assessment_participants p JOIN assessments a ON a.id=p.assessment_id JOIN paper_items i ON i.paper_revision_id=a.paper_revision_id AND i.is_scored=1 WHERE p.assessment_id=NEW.assessment_id AND NOT EXISTS(SELECT 1 FROM student_item_scores s WHERE s.score_revision_id=NEW.id AND s.participant_id=p.id AND s.item_id=i.id)) THEN RAISE(ABORT,'SCORE_MATRIX_INCOMPLETE') END;
END;
CREATE TRIGGER IF NOT EXISTS analysis_confirmed_score BEFORE INSERT ON analysis_runs BEGIN SELECT CASE WHEN (SELECT state FROM score_revisions WHERE id=NEW.score_revision_id)<>'confirmed' THEN RAISE(ABORT,'SCORE_NOT_CONFIRMED') END; END;
CREATE TRIGGER IF NOT EXISTS analysis_participant_insert BEFORE INSERT ON analysis_results BEGIN SELECT CASE WHEN (SELECT assessment_id FROM assessment_participants WHERE id=NEW.participant_id)<>(SELECT assessment_id FROM analysis_runs WHERE id=NEW.run_id) THEN RAISE(ABORT,'ANALYSIS_PARTICIPANT_MISMATCH') END; END;
CREATE TRIGGER IF NOT EXISTS evidence_loss_insert BEFORE INSERT ON analysis_evidence BEGIN
 SELECT CASE WHEN NEW.is_loss<>coalesce((SELECT CASE WHEN s.status='recorded' AND s.score_units<i.max_score_units THEN 1 ELSE 0 END FROM student_item_scores s JOIN paper_items i ON i.id=s.item_id WHERE s.score_revision_id=NEW.score_revision_id AND s.participant_id=NEW.participant_id AND s.item_id=NEW.item_id),0) THEN RAISE(ABORT,'LOSS_FACT_MISMATCH') END;
 SELECT CASE WHEN NEW.knowledge_revision_id<>(SELECT knowledge_revision_id FROM paper_item_knowledge WHERE item_id=NEW.item_id AND knowledge_point_id=NEW.knowledge_point_id) THEN RAISE(ABORT,'KNOWLEDGE_REVISION_MISMATCH') END;
END;

CREATE TRIGGER IF NOT EXISTS immutable_paper_revisions_update BEFORE UPDATE ON paper_revisions WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_paper_revisions_delete BEFORE DELETE ON paper_revisions WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS no_direct_sealed_paper_revisions BEFORE INSERT ON paper_revisions WHEN NEW.state='confirmed' BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_score_revisions_update BEFORE UPDATE ON score_revisions WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_score_revisions_delete BEFORE DELETE ON score_revisions WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS no_direct_sealed_score_revisions BEFORE INSERT ON score_revisions WHEN NEW.state='confirmed' BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_lesson_plan_revisions_update BEFORE UPDATE ON lesson_plan_revisions WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_lesson_plan_revisions_delete BEFORE DELETE ON lesson_plan_revisions WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS no_direct_sealed_lesson_plan_revisions BEFORE INSERT ON lesson_plan_revisions WHEN NEW.state='reviewed' BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_practice_revisions_update BEFORE UPDATE ON practice_revisions WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_practice_revisions_delete BEFORE DELETE ON practice_revisions WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS no_direct_sealed_practice_revisions BEFORE INSERT ON practice_revisions WHEN NEW.state='reviewed' BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_analysis_runs_update BEFORE UPDATE ON analysis_runs WHEN OLD.state='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_analysis_runs_delete BEFORE DELETE ON analysis_runs WHEN OLD.state='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS no_direct_sealed_analysis_runs BEFORE INSERT ON analysis_runs WHEN NEW.state='ready' BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_paper_items_insert BEFORE INSERT ON paper_items WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_paper_items_update BEFORE UPDATE ON paper_items WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' OR (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_paper_items_delete BEFORE DELETE ON paper_items WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_paper_item_knowledge_insert BEFORE INSERT ON paper_item_knowledge WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_paper_item_knowledge_update BEFORE UPDATE ON paper_item_knowledge WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' OR (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_paper_item_knowledge_delete BEFORE DELETE ON paper_item_knowledge WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_student_item_scores_insert BEFORE INSERT ON student_item_scores WHEN (SELECT state FROM score_revisions WHERE id=NEW.score_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_student_item_scores_update BEFORE UPDATE ON student_item_scores WHEN (SELECT state FROM score_revisions WHERE id=OLD.score_revision_id)='confirmed' OR (SELECT state FROM score_revisions WHERE id=NEW.score_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_student_item_scores_delete BEFORE DELETE ON student_item_scores WHEN (SELECT state FROM score_revisions WHERE id=OLD.score_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_lesson_plan_evidence_insert BEFORE INSERT ON lesson_plan_evidence WHEN (SELECT state FROM lesson_plan_revisions WHERE id=NEW.lesson_revision_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_lesson_plan_evidence_update BEFORE UPDATE ON lesson_plan_evidence WHEN (SELECT state FROM lesson_plan_revisions WHERE id=OLD.lesson_revision_id)='reviewed' OR (SELECT state FROM lesson_plan_revisions WHERE id=NEW.lesson_revision_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_lesson_plan_evidence_delete BEFORE DELETE ON lesson_plan_evidence WHEN (SELECT state FROM lesson_plan_revisions WHERE id=OLD.lesson_revision_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_practice_items_insert BEFORE INSERT ON practice_items WHEN (SELECT state FROM practice_revisions WHERE id=NEW.practice_revision_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_practice_items_update BEFORE UPDATE ON practice_items WHEN (SELECT state FROM practice_revisions WHERE id=OLD.practice_revision_id)='reviewed' OR (SELECT state FROM practice_revisions WHERE id=NEW.practice_revision_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_practice_items_delete BEFORE DELETE ON practice_items WHEN (SELECT state FROM practice_revisions WHERE id=OLD.practice_revision_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_analysis_results_insert BEFORE INSERT ON analysis_results WHEN (SELECT state FROM analysis_runs WHERE id=NEW.run_id)='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_analysis_results_update BEFORE UPDATE ON analysis_results WHEN (SELECT state FROM analysis_runs WHERE id=OLD.run_id)='ready' OR (SELECT state FROM analysis_runs WHERE id=NEW.run_id)='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_analysis_results_delete BEFORE DELETE ON analysis_results WHEN (SELECT state FROM analysis_runs WHERE id=OLD.run_id)='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_analysis_evidence_insert BEFORE INSERT ON analysis_evidence WHEN (SELECT state FROM analysis_runs WHERE id=NEW.run_id)='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_analysis_evidence_update BEFORE UPDATE ON analysis_evidence WHEN (SELECT state FROM analysis_runs WHERE id=OLD.run_id)='ready' OR (SELECT state FROM analysis_runs WHERE id=NEW.run_id)='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TRIGGER IF NOT EXISTS freeze_analysis_evidence_delete BEFORE DELETE ON analysis_evidence WHEN (SELECT state FROM analysis_runs WHERE id=OLD.run_id)='ready' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_practice_kp_insert BEFORE INSERT ON practice_item_knowledge WHEN (SELECT r.state FROM practice_revisions r JOIN practice_items i ON i.practice_revision_id=r.id WHERE i.id=NEW.item_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_practice_kp_update BEFORE UPDATE ON practice_item_knowledge WHEN (SELECT r.state FROM practice_revisions r JOIN practice_items i ON i.practice_revision_id=r.id WHERE i.id=OLD.item_id)='reviewed' OR (SELECT r.state FROM practice_revisions r JOIN practice_items i ON i.practice_revision_id=r.id WHERE i.id=NEW.item_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS freeze_practice_kp_delete BEFORE DELETE ON practice_item_knowledge WHEN (SELECT r.state FROM practice_revisions r JOIN practice_items i ON i.practice_revision_id=r.id WHERE i.id=OLD.item_id)='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
```

### question_bank_extension

```sql
CREATE INDEX IF NOT EXISTS ix_question_knowledge ON question_knowledge_links(knowledge_point_id,question_revision_id);

CREATE TRIGGER IF NOT EXISTS immutable_question_knowledge_links_update BEFORE UPDATE ON question_knowledge_links BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_question_knowledge_links_delete BEFORE DELETE ON question_knowledge_links BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
```

## 现有数据结构复用

题库保留 question_imports、question_source_blocks、question_drafts、question_suggestions、questions、question_revisions、question_sources、question_submissions、question_jobs。教材目录保留 catalog_state、embedding_profiles、index_generations、libraries、documents、library_documents、document_metadata_revisions、document_revisions、chunk_sets、chunks、generation_revisions、import_drafts、index_jobs、cleanup_queue、teaching_settings。它们的字段定义以仓库对应 schema.py 为准；快照附在 sql/existing-*.sql，均为只读设计基线。
