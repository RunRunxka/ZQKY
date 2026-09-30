-- ZQKY 教学闭环 v1：参考 DDL；禁止对正式数据直接执行。
PRAGMA foreign_keys=ON;

-- 本模块文件登记
CREATE TABLE IF NOT EXISTS file_assets (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    kind TEXT NOT NULL CHECK(kind IN ('roster','score_sheet','paper','export','attachment')),
    blob_key TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    original_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK(byte_size>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- file_assets.id: 稳定 UUID，由服务端生成
-- file_assets.owner_id: 本地用户归属，预留授权范围
-- file_assets.kind: 名单、成绩、原卷、导出或配图
-- file_assets.blob_key: 受管相对文件键；禁止外部任意路径
-- file_assets.sha256: 原始字节 SHA-256
-- file_assets.original_name: 上传文件名，仅展示，不用于拼接路径
-- file_assets.media_type: MIME 类型
-- file_assets.byte_size: 字节数
-- file_assets.created_at: UTC 创建时间，界面转换为本地时间

-- 班级
CREATE TABLE IF NOT EXISTS classes (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    school_year TEXT NOT NULL,
    grade_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(owner_id,school_year,code)
);
-- classes.id: 稳定 UUID，由服务端生成
-- classes.owner_id: 本地用户归属，预留授权范围
-- classes.code: 用户范围内班级业务代码
-- classes.name: 班级显示名称
-- classes.school_year: 学年，例如 2026-2027
-- classes.grade_id: 复用项目年级字典；班级不固定为某一学科
-- classes.status: 启用或归档
-- classes.revision: 可变实体的乐观锁版本
-- classes.created_at: UTC 创建时间，界面转换为本地时间

-- 学生稳定身份
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    student_no TEXT,
    name TEXT NOT NULL CHECK(length(trim(name))>0),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(owner_id,student_no),
    CHECK(student_no IS NULL OR length(trim(student_no))>0)
);
-- students.id: 稳定 UUID，由服务端生成
-- students.owner_id: 本地用户归属，预留授权范围
-- students.student_no: 学号按文本保存，保留前导零；无学号时教师明确建档
-- students.name: 姓名用于展示和人工核对，不作主键
-- students.status: 学生归档状态
-- students.revision: 可变实体的乐观锁版本
-- students.created_at: UTC 创建时间，界面转换为本地时间

-- 学生班级归属历史
CREATE TABLE IF NOT EXISTS class_memberships (
    id TEXT PRIMARY KEY NOT NULL,
    class_id TEXT NOT NULL REFERENCES classes(id),
    student_id TEXT NOT NULL REFERENCES students(id),
    joined_on TEXT NOT NULL,
    left_on TEXT,
    CHECK(left_on IS NULL OR left_on>=joined_on),
    UNIQUE(class_id,student_id,joined_on)
);
-- class_memberships.id: 稳定 UUID，由服务端生成
-- class_memberships.class_id: 班级
-- class_memberships.student_id: 学生
-- class_memberships.joined_on: 入班日期 YYYY-MM-DD
-- class_memberships.left_on: 离班日期，可空；不删除旧归属

-- 试卷稳定身份
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    subject_id TEXT NOT NULL,
    title TEXT NOT NULL,
    current_revision_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(current_revision_id,id) REFERENCES paper_revisions(id,paper_id) DEFERRABLE INITIALLY DEFERRED
);
-- papers.id: 稳定 UUID，由服务端生成
-- papers.owner_id: 本地用户归属，预留授权范围
-- papers.subject_id: EXT：知识库 subjects.id
-- papers.title: 试卷名称
-- papers.current_revision_id: 当前已确认修订
-- papers.status: 试卷归档状态
-- papers.revision: 可变实体的乐观锁版本
-- papers.created_at: UTC 创建时间，界面转换为本地时间

-- 原卷或练习转换的试卷修订
CREATE TABLE IF NOT EXISTS paper_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    version INTEGER NOT NULL CHECK(version>0),
    source_file_id TEXT REFERENCES file_assets(id),
    source_practice_revision_id TEXT REFERENCES practice_revisions(id),
    total_score_units INTEGER NOT NULL CHECK(total_score_units>0),
    state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','confirmed')),
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(paper_id,version),
    UNIQUE(id,paper_id),
    CHECK((source_file_id IS NOT NULL)+(source_practice_revision_id IS NOT NULL)=1),
    CHECK((state='draft' AND confirmed_at IS NULL) OR (state='confirmed' AND confirmed_at IS NOT NULL))
);
-- paper_revisions.id: 稳定 UUID，由服务端生成
-- paper_revisions.paper_id: 试卷身份
-- paper_revisions.version: 内容修订序号
-- paper_revisions.source_file_id: 原始 DOCX 或其他原卷文件
-- paper_revisions.source_practice_revision_id: 从已审核练习转换，可空
-- paper_revisions.total_score_units: 总分乘 100 后的整数，例如 100 分记 10000
-- paper_revisions.state: 草稿可编辑；确认后不可变
-- paper_revisions.confirmed_at: 确认时间
-- paper_revisions.created_at: UTC 创建时间，界面转换为本地时间

-- 试卷题干容器与独立计分小题
CREATE TABLE IF NOT EXISTS paper_items (
    id TEXT PRIMARY KEY NOT NULL,
    paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
    parent_item_id TEXT,
    question_no TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK(ordinal>0),
    is_scored INTEGER NOT NULL CHECK(is_scored IN (0,1)),
    max_score_units INTEGER,
    question_revision_id TEXT,
    content_json TEXT NOT NULL CHECK(json_valid(content_json)),
    source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(source_locator_json)),
    UNIQUE(paper_revision_id,question_no),
    UNIQUE(paper_revision_id,ordinal),
    UNIQUE(id,paper_revision_id),
    FOREIGN KEY(parent_item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id),
    CHECK(parent_item_id IS NULL OR parent_item_id<>id),
    CHECK((is_scored=1 AND max_score_units IS NOT NULL AND max_score_units>0) OR (is_scored=0 AND max_score_units IS NULL))
);
-- paper_items.id: 稳定 UUID，由服务端生成
-- paper_items.paper_revision_id: 固定试卷修订
-- paper_items.parent_item_id: 同份修订中的共享题干或大题容器
-- paper_items.question_no: 完整题号，如 16(1)，不可只写 (1)
-- paper_items.ordinal: 整卷展示顺序
-- paper_items.is_scored: 1 为成绩表对应小题；0 仅用于组织题干
-- paper_items.max_score_units: 计分小题满分乘 100；题干容器必须为空
-- paper_items.question_revision_id: EXT：现有题库修订，可空；分析不强制先入题库
-- paper_items.content_json: 题干、选项、公式、附件和共用材料快照
-- paper_items.source_locator_json: 原件块序号或预览定位

-- 本次试卷小题的已确认知识点
CREATE TABLE IF NOT EXISTS paper_item_knowledge (
    item_id TEXT NOT NULL,
    paper_revision_id TEXT NOT NULL,
    knowledge_point_id TEXT NOT NULL,
    knowledge_revision_id TEXT NOT NULL,
    knowledge_name_snapshot TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('primary','secondary')),
    source TEXT NOT NULL CHECK(source IN ('human','ai_confirmed','bank_confirmed')),
    PRIMARY KEY(item_id,knowledge_point_id),
    FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id)
);
-- paper_item_knowledge.item_id: 本卷小题
-- paper_item_knowledge.paper_revision_id: 冗余范围键，用复合外键防跨卷关联
-- paper_item_knowledge.knowledge_point_id: EXT：独立知识点身份
-- paper_item_knowledge.knowledge_revision_id: EXT：知识点修订
-- paper_item_knowledge.knowledge_name_snapshot: 教师确认时名称
-- paper_item_knowledge.role: 分类角色；两者都参与失分关联，不设权重
-- paper_item_knowledge.source: 人工、确认后的 AI 或确认后的题库标注

-- 一次施测
CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
    title TEXT NOT NULL,
    assessment_type TEXT NOT NULL CHECK(assessment_type IN ('exam','quiz','practice')),
    held_on TEXT NOT NULL,
    active_score_revision_id TEXT,
    state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','closed','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(id,paper_revision_id),
    FOREIGN KEY(active_score_revision_id,id) REFERENCES score_revisions(id,assessment_id) DEFERRABLE INITIALLY DEFERRED
);
-- assessments.id: 稳定 UUID，由服务端生成
-- assessments.owner_id: 本地用户归属，预留授权范围
-- assessments.paper_revision_id: 使用已确认试卷
-- assessments.title: 月考、单元测验或课堂练习名称
-- assessments.assessment_type: 考试、测验、练习
-- assessments.held_on: 施测日期
-- assessments.active_score_revision_id: 当前正式成绩修订
-- assessments.state: 开放导入、结束或归档
-- assessments.revision: 可变实体的乐观锁版本
-- assessments.created_at: UTC 创建时间，界面转换为本地时间

-- 施测适用班级
CREATE TABLE IF NOT EXISTS assessment_classes (
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    class_id TEXT NOT NULL REFERENCES classes(id),
    PRIMARY KEY(assessment_id,class_id)
);
-- assessment_classes.assessment_id: 同一试卷可用于多个班
-- assessment_classes.class_id: 参加班级

-- 学生本次参加与补考记录
CREATE TABLE IF NOT EXISTS assessment_participants (
    id TEXT PRIMARY KEY NOT NULL,
    assessment_id TEXT NOT NULL,
    student_id TEXT NOT NULL REFERENCES students(id),
    class_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL DEFAULT 1 CHECK(attempt_no>0),
    attendance TEXT NOT NULL CHECK(attendance IN ('present','absent','exempt')),
    name_snapshot TEXT NOT NULL,
    student_no_snapshot TEXT,
    FOREIGN KEY(assessment_id,class_id) REFERENCES assessment_classes(assessment_id,class_id),
    UNIQUE(assessment_id,student_id,attempt_no),
    UNIQUE(id,assessment_id)
);
-- assessment_participants.id: 稳定 UUID，由服务端生成
-- assessment_participants.assessment_id: 施测
-- assessment_participants.student_id: 学生稳定身份
-- assessment_participants.class_id: 本次班级，转班后历史不变
-- assessment_participants.attempt_no: 本次施测内尝试序号，补考可新增
-- assessment_participants.attendance: 参加、缺考或免考，不代替小题分数
-- assessment_participants.name_snapshot: 本次学生名称快照
-- assessment_participants.student_no_snapshot: 本次学号快照

-- 成绩导入草稿
CREATE TABLE IF NOT EXISTS score_imports (
    id TEXT PRIMARY KEY NOT NULL,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    file_id TEXT NOT NULL REFERENCES file_assets(id),
    base_score_revision_id TEXT,
    mapping_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(mapping_json)),
    state TEXT NOT NULL CHECK(state IN ('uploaded','reviewing','confirmed','failed','cancelled')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(id,assessment_id),
    FOREIGN KEY(base_score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id)
);
-- score_imports.id: 稳定 UUID，由服务端生成
-- score_imports.assessment_id: 目标施测
-- score_imports.file_id: 原始成绩 XLSX/CSV
-- score_imports.base_score_revision_id: 上传时的正式成绩版本，提交前检查未变化
-- score_imports.mapping_json: 工作表、表头、学生列和题号列映射
-- score_imports.state: 导入生命周期
-- score_imports.revision: 可变实体的乐观锁版本
-- score_imports.created_at: UTC 创建时间，界面转换为本地时间

-- 成绩表预览行与异常
CREATE TABLE IF NOT EXISTS score_import_rows (
    import_id TEXT NOT NULL REFERENCES score_imports(id),
    row_no INTEGER NOT NULL CHECK(row_no>0),
    participant_id TEXT REFERENCES assessment_participants(id),
    raw_cells_json TEXT NOT NULL CHECK(json_valid(raw_cells_json)),
    issues_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(issues_json)),
    PRIMARY KEY(import_id,row_no)
);
-- score_import_rows.import_id: 导入批次
-- score_import_rows.row_no: 原表行号
-- score_import_rows.participant_id: 教师确认的学生参加记录，可空待匹配
-- score_import_rows.raw_cells_json: 原始单元格值与题号；只在本地保存
-- score_import_rows.issues_json: 重名、越界、缺列等错误

-- 全量成绩快照修订
CREATE TABLE IF NOT EXISTS score_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    version INTEGER NOT NULL CHECK(version>0),
    source_import_id TEXT,
    base_revision_id TEXT,
    state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','confirmed')),
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(assessment_id,version),
    UNIQUE(id,assessment_id),
    FOREIGN KEY(source_import_id,assessment_id) REFERENCES score_imports(id,assessment_id),
    FOREIGN KEY(base_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id),
    CHECK(base_revision_id IS NULL OR base_revision_id<>id),
    CHECK((state='draft' AND confirmed_at IS NULL) OR (state='confirmed' AND confirmed_at IS NOT NULL))
);
-- score_revisions.id: 稳定 UUID，由服务端生成
-- score_revisions.assessment_id: 所属施测
-- score_revisions.version: 单次施测内修订序号
-- score_revisions.source_import_id: 来源成绩导入批次
-- score_revisions.base_revision_id: 被修正的旧成绩版本
-- score_revisions.state: 完整确认后不可变
-- score_revisions.confirmed_at: 正式确认时间
-- score_revisions.created_at: UTC 创建时间，界面转换为本地时间

-- 教师已提供的小题得分事实
CREATE TABLE IF NOT EXISTS student_item_scores (
    score_revision_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    paper_revision_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    score_units INTEGER,
    status TEXT NOT NULL CHECK(status IN ('recorded','missing','absent','exempt')),
    PRIMARY KEY(score_revision_id,participant_id,item_id),
    FOREIGN KEY(score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id),
    FOREIGN KEY(participant_id,assessment_id) REFERENCES assessment_participants(id,assessment_id),
    FOREIGN KEY(assessment_id,paper_revision_id) REFERENCES assessments(id,paper_revision_id),
    FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id),
    CHECK((status='recorded' AND score_units IS NOT NULL AND score_units>=0) OR (status<>'recorded' AND score_units IS NULL))
);
-- student_item_scores.score_revision_id: 正式成绩快照；修正生成新版本
-- student_item_scores.assessment_id: 所属施测，用于复合外键
-- student_item_scores.paper_revision_id: 本次原卷修订，用于复合外键
-- student_item_scores.participant_id: 学生参加记录
-- student_item_scores.item_id: 成绩表对应计分小题
-- student_item_scores.score_units: 实际分数乘 100；非 recorded 必须为空
-- student_item_scores.status: 已录分、未录入、缺考、免考

-- 失分关联学情报告快照
CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY NOT NULL,
    assessment_id TEXT NOT NULL,
    score_revision_id TEXT NOT NULL,
    rule_code TEXT NOT NULL DEFAULT 'any_loss_v1' CHECK(rule_code='any_loss_v1'),
    selection_json TEXT NOT NULL CHECK(json_valid(selection_json)),
    roster_snapshot_json TEXT NOT NULL CHECK(json_valid(roster_snapshot_json)),
    input_hash TEXT NOT NULL CHECK(length(input_hash)=64),
    state TEXT NOT NULL CHECK(state IN ('running','ready','failed','cancelled')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id),
    UNIQUE(assessment_id,input_hash),
    UNIQUE(id,score_revision_id)
);
-- analysis_runs.id: 稳定 UUID，由服务端生成
-- analysis_runs.assessment_id: 本次施测
-- analysis_runs.score_revision_id: 指定正式成绩版本
-- analysis_runs.rule_code: 任一相关小题失分即列需巩固；不预测掌握概率
-- analysis_runs.selection_json: 分析班级和学生尝试选择；同学生不重复计入班级人数
-- analysis_runs.roster_snapshot_json: 参测名单、班级与出勤冻结
-- analysis_runs.input_hash: 成绩、试卷、映射、名单和规则的规范化输入指纹
-- analysis_runs.state: 报告生成状态
-- analysis_runs.created_at: UTC 创建时间，界面转换为本地时间

-- 每个学生每个知识点的本次表现
CREATE TABLE IF NOT EXISTS analysis_results (
    run_id TEXT NOT NULL REFERENCES analysis_runs(id),
    participant_id TEXT NOT NULL REFERENCES assessment_participants(id),
    knowledge_point_id TEXT NOT NULL,
    knowledge_name_snapshot TEXT NOT NULL,
    observation TEXT NOT NULL CHECK(observation IN ('needs_consolidation','full_credit','incomplete','no_evidence')),
    expected_count INTEGER NOT NULL CHECK(expected_count>=0),
    valid_count INTEGER NOT NULL CHECK(valid_count>=0 AND valid_count<=expected_count),
    loss_count INTEGER NOT NULL CHECK(loss_count>=0 AND loss_count<=valid_count),
    earned_units INTEGER NOT NULL CHECK(earned_units>=0),
    available_units INTEGER NOT NULL CHECK(available_units>=earned_units),
    PRIMARY KEY(run_id,participant_id,knowledge_point_id),
    CHECK((observation='needs_consolidation' AND loss_count>0) OR (observation='no_evidence' AND valid_count=0 AND loss_count=0) OR (observation='incomplete' AND valid_count>0 AND valid_count<expected_count AND loss_count=0) OR (observation='full_credit' AND expected_count>0 AND valid_count=expected_count AND loss_count=0))
);
-- analysis_results.run_id: 分析快照
-- analysis_results.participant_id: 本次学生作答记录
-- analysis_results.knowledge_point_id: EXT：知识点身份，名称等由报告证据冻结
-- analysis_results.knowledge_name_snapshot: 报告显示名称
-- analysis_results.observation: 需巩固、相关题均满分、资料不全、无有效成绩
-- analysis_results.expected_count: 已确认关联的计分小题数
-- analysis_results.valid_count: 有 recorded 成绩的小题数
-- analysis_results.loss_count: recorded 且实际分数低于满分的小题数
-- analysis_results.earned_units: 相关有效小题实际分数合计，仅作为事实展示
-- analysis_results.available_units: 相关有效小题满分合计，不含未录入等

-- 报告至小题成绩的证据链
CREATE TABLE IF NOT EXISTS analysis_evidence (
    run_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    knowledge_point_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    score_revision_id TEXT NOT NULL,
    knowledge_revision_id TEXT NOT NULL,
    is_loss INTEGER NOT NULL CHECK(is_loss IN (0,1)),
    PRIMARY KEY(run_id,participant_id,knowledge_point_id,item_id),
    FOREIGN KEY(run_id,participant_id,knowledge_point_id) REFERENCES analysis_results(run_id,participant_id,knowledge_point_id),
    FOREIGN KEY(run_id,score_revision_id) REFERENCES analysis_runs(id,score_revision_id),
    FOREIGN KEY(score_revision_id,participant_id,item_id) REFERENCES student_item_scores(score_revision_id,participant_id,item_id),
    FOREIGN KEY(item_id,knowledge_point_id) REFERENCES paper_item_knowledge(item_id,knowledge_point_id)
);
-- analysis_evidence.run_id: 分析报告
-- analysis_evidence.participant_id: 学生参加记录
-- analysis_evidence.knowledge_point_id: 本条结果的知识点
-- analysis_evidence.item_id: 具体小题
-- analysis_evidence.score_revision_id: 报告所用成绩版本
-- analysis_evidence.knowledge_revision_id: EXT：该小题确认时的知识点修订
-- analysis_evidence.is_loss: 是否有实际失分；非 recorded 为 0，但不算有效题

-- 教师对报告的说明
CREATE TABLE IF NOT EXISTS analysis_teacher_notes (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL REFERENCES analysis_runs(id),
    participant_id TEXT REFERENCES assessment_participants(id),
    knowledge_point_id TEXT,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- analysis_teacher_notes.id: 稳定 UUID，由服务端生成
-- analysis_teacher_notes.run_id: 对应分析报告
-- analysis_teacher_notes.participant_id: 可空代表班级说明
-- analysis_teacher_notes.knowledge_point_id: EXT：可空代表整体说明
-- analysis_teacher_notes.note: 教师补充或修正解释，不覆盖原始失分事实
-- analysis_teacher_notes.created_at: UTC 创建时间，界面转换为本地时间

-- 按本课目标建立的临时分组方案
CREATE TABLE IF NOT EXISTS group_sets (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL REFERENCES analysis_runs(id),
    topic TEXT NOT NULL,
    criteria_json TEXT NOT NULL CHECK(json_valid(criteria_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- group_sets.id: 稳定 UUID，由服务端生成
-- group_sets.run_id: 分组依据报告
-- group_sets.topic: 本课课题或教学目标
-- group_sets.criteria_json: 教师确定的分组依据，不生成永久能力标签
-- group_sets.created_at: UTC 创建时间，界面转换为本地时间

-- 分组方案中的组
CREATE TABLE IF NOT EXISTS learning_groups (
    id TEXT PRIMARY KEY NOT NULL,
    group_set_id TEXT NOT NULL REFERENCES group_sets(id),
    label TEXT NOT NULL,
    name TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK(ordinal>0),
    UNIQUE(group_set_id,label),
    UNIQUE(id,group_set_id)
);
-- learning_groups.id: 稳定 UUID，由服务端生成
-- learning_groups.group_set_id: 本次分组方案
-- learning_groups.label: A/B/C 或教师自定义代码
-- learning_groups.name: 教师定义的分组名称
-- learning_groups.ordinal: 显示顺序

-- 临时分组成员
CREATE TABLE IF NOT EXISTS group_members (
    group_set_id TEXT NOT NULL REFERENCES group_sets(id),
    group_id TEXT NOT NULL,
    participant_id TEXT NOT NULL REFERENCES assessment_participants(id),
    PRIMARY KEY(group_set_id,participant_id),
    FOREIGN KEY(group_id,group_set_id) REFERENCES learning_groups(id,group_set_id)
);
-- group_members.group_set_id: 分组方案
-- group_members.group_id: 方案内分组
-- group_members.participant_id: 报告内学生参加记录

-- 教案身份
CREATE TABLE IF NOT EXISTS lesson_plans (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    class_id TEXT NOT NULL REFERENCES classes(id),
    subject_id TEXT NOT NULL,
    title TEXT NOT NULL,
    current_revision_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(current_revision_id,id) REFERENCES lesson_plan_revisions(id,lesson_plan_id) DEFERRABLE INITIALLY DEFERRED
);
-- lesson_plans.id: 稳定 UUID，由服务端生成
-- lesson_plans.owner_id: 本地用户归属，预留授权范围
-- lesson_plans.class_id: 授课班级
-- lesson_plans.subject_id: EXT：学科
-- lesson_plans.title: 教案标题
-- lesson_plans.current_revision_id: 当前修订
-- lesson_plans.status: 教案归档
-- lesson_plans.revision: 可变实体的乐观锁版本
-- lesson_plans.created_at: UTC 创建时间，界面转换为本地时间

-- 结构化教案内容修订
CREATE TABLE IF NOT EXISTS lesson_plan_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    lesson_plan_id TEXT NOT NULL REFERENCES lesson_plans(id),
    version INTEGER NOT NULL CHECK(version>0),
    analysis_run_id TEXT REFERENCES analysis_runs(id),
    group_set_id TEXT REFERENCES group_sets(id),
    schema_version INTEGER NOT NULL DEFAULT 2 CHECK(schema_version=2),
    context_json TEXT NOT NULL CHECK(json_valid(context_json)),
    content_json TEXT NOT NULL CHECK(json_valid(content_json)),
    model_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(model_snapshot_json)),
    source TEXT NOT NULL CHECK(source IN ('human','ai_accepted','legacy_import')),
    state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','reviewed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(lesson_plan_id,version),
    UNIQUE(id,lesson_plan_id)
);
-- lesson_plan_revisions.id: 稳定 UUID，由服务端生成
-- lesson_plan_revisions.lesson_plan_id: 教案身份
-- lesson_plan_revisions.version: 内容修订序号
-- lesson_plan_revisions.analysis_run_id: 学情报告依据；旧教案迁入或无学情备课可空
-- lesson_plan_revisions.group_set_id: 本节分组方案，可空
-- lesson_plan_revisions.schema_version: 教案 JSON 契约版本
-- lesson_plan_revisions.context_json: 课型、课时、时长、教材范围快照和教学约束
-- lesson_plan_revisions.content_json: 目标、重难点、过程、检测、练习安排和反思模板
-- lesson_plan_revisions.model_snapshot_json: AI 模型身份与生成参数，无凭证
-- lesson_plan_revisions.source: 手工、接受 AI 建议或旧草稿迁入
-- lesson_plan_revisions.state: 草稿可改；审核版不可变
-- lesson_plan_revisions.created_at: UTC 创建时间，界面转换为本地时间

-- 教案调整理由与来源
CREATE TABLE IF NOT EXISTS lesson_plan_evidence (
    id TEXT PRIMARY KEY NOT NULL,
    lesson_revision_id TEXT NOT NULL REFERENCES lesson_plan_revisions(id),
    kind TEXT NOT NULL CHECK(kind IN ('analytics','textbook','question','teacher')),
    target_path TEXT NOT NULL,
    source_ref_json TEXT NOT NULL CHECK(json_valid(source_ref_json)),
    content_snapshot TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256)=64)
);
-- lesson_plan_evidence.id: 稳定 UUID，由服务端生成
-- lesson_plan_evidence.lesson_revision_id: 对应教案修订
-- lesson_plan_evidence.kind: 学情、教材、题库或教师说明
-- lesson_plan_evidence.target_path: 内容 JSON 路径，例如 process[1].design
-- lesson_plan_evidence.source_ref_json: 报告/原文区间/题目修订的精确引用
-- lesson_plan_evidence.content_snapshot: 本次实际用于生成的证据文本或脱敏摘要
-- lesson_plan_evidence.sha256: 证据快照散列

-- 练习身份
CREATE TABLE IF NOT EXISTS practice_sets (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    subject_id TEXT NOT NULL,
    title TEXT NOT NULL,
    current_revision_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(current_revision_id,id) REFERENCES practice_revisions(id,practice_set_id) DEFERRABLE INITIALLY DEFERRED
);
-- practice_sets.id: 稳定 UUID，由服务端生成
-- practice_sets.owner_id: 本地用户归属，预留授权范围
-- practice_sets.subject_id: EXT：学科
-- practice_sets.title: 练习名称
-- practice_sets.current_revision_id: 当前修订
-- practice_sets.status: 启用或归档
-- practice_sets.revision: 可变实体的乐观锁版本
-- practice_sets.created_at: UTC 创建时间，界面转换为本地时间

-- 固定练习内容与组卷约束
CREATE TABLE IF NOT EXISTS practice_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    practice_set_id TEXT NOT NULL REFERENCES practice_sets(id),
    version INTEGER NOT NULL CHECK(version>0),
    lesson_revision_id TEXT REFERENCES lesson_plan_revisions(id),
    group_id TEXT REFERENCES learning_groups(id),
    constraints_json TEXT NOT NULL CHECK(json_valid(constraints_json)),
    state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','reviewed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(practice_set_id,version),
    UNIQUE(id,practice_set_id)
);
-- practice_revisions.id: 稳定 UUID，由服务端生成
-- practice_revisions.practice_set_id: 练习身份
-- practice_revisions.version: 内容修订序号
-- practice_revisions.lesson_revision_id: 关联教案修订，可空
-- practice_revisions.group_id: 目标分组，可空代表统一练习
-- practice_revisions.constraints_json: 知识点、题量、时长、难度梯度、原题排除等教师约束
-- practice_revisions.state: 审核后固定
-- practice_revisions.created_at: UTC 创建时间，界面转换为本地时间

-- 练习选题快照
CREATE TABLE IF NOT EXISTS practice_items (
    id TEXT PRIMARY KEY NOT NULL,
    practice_revision_id TEXT NOT NULL REFERENCES practice_revisions(id),
    ordinal INTEGER NOT NULL CHECK(ordinal>0),
    question_revision_id TEXT NOT NULL,
    content_json TEXT NOT NULL CHECK(json_valid(content_json)),
    selection_reason TEXT NOT NULL,
    max_score_units INTEGER NOT NULL CHECK(max_score_units>0),
    estimated_seconds INTEGER CHECK(estimated_seconds>0),
    UNIQUE(practice_revision_id,ordinal)
);
-- practice_items.id: 稳定 UUID，由服务端生成
-- practice_items.practice_revision_id: 练习修订
-- practice_items.ordinal: 显示次序
-- practice_items.question_revision_id: EXT：已确认题库修订；AI 草稿不能直接进入最终练习
-- practice_items.content_json: 完整题干、共用材料、答案、配图快照
-- practice_items.selection_reason: 选用理由，关联本节薄弱项
-- practice_items.max_score_units: 教师设置本次练习小题满分，便于回流
-- practice_items.estimated_seconds: 可空；教师估计完成时间

-- 练习小题目标知识点
CREATE TABLE IF NOT EXISTS practice_item_knowledge (
    item_id TEXT NOT NULL REFERENCES practice_items(id),
    knowledge_point_id TEXT NOT NULL,
    knowledge_revision_id TEXT NOT NULL,
    knowledge_name_snapshot TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('primary','secondary')),
    PRIMARY KEY(item_id,knowledge_point_id)
);
-- practice_item_knowledge.item_id: 练习小题
-- practice_item_knowledge.knowledge_point_id: EXT：知识点身份
-- practice_item_knowledge.knowledge_revision_id: EXT：知识点修订
-- practice_item_knowledge.knowledge_name_snapshot: 练习冻结时名称
-- practice_item_knowledge.role: 主要或关联知识点

-- 本地可恢复工作任务
CREATE TABLE IF NOT EXISTS workflow_jobs (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    kind TEXT NOT NULL CHECK(kind IN ('paper_mapping','lesson_generation','export')),
    input_json TEXT NOT NULL CHECK(json_valid(input_json)),
    model_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(model_snapshot_json)),
    state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','failed','cancelled','interrupted')),
    checkpoint_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(checkpoint_json)),
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- workflow_jobs.id: 稳定 UUID，由服务端生成
-- workflow_jobs.owner_id: 本地用户归属，预留授权范围
-- workflow_jobs.kind: 试卷知识点建议、教案生成或导出；题库复用既有 question_jobs
-- workflow_jobs.input_json: 冻结输入及实体版本
-- workflow_jobs.model_snapshot_json: 固定模型；导出任务可为空，无密钥
-- workflow_jobs.state: 重启遗留 running 转 interrupted，可重试
-- workflow_jobs.checkpoint_json: 阶段进度，不假设上游流能重放
-- workflow_jobs.error_code: 脱敏错误代码
-- workflow_jobs.created_at: UTC 创建时间，界面转换为本地时间

-- 等待教师采用的 AI 建议
CREATE TABLE IF NOT EXISTS ai_proposals (
    id TEXT PRIMARY KEY NOT NULL,
    job_id TEXT NOT NULL REFERENCES workflow_jobs(id),
    target_kind TEXT NOT NULL CHECK(target_kind IN ('paper_revision','lesson_revision')),
    target_id TEXT NOT NULL,
    base_revision INTEGER NOT NULL CHECK(base_revision>=0),
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','applied','rejected','stale')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- ai_proposals.id: 稳定 UUID，由服务端生成
-- ai_proposals.job_id: 建议来源任务
-- ai_proposals.target_kind: 建议目标类型
-- ai_proposals.target_id: 类型对应实体 ID，应用层校验
-- ai_proposals.base_revision: 请求时编辑版本；过期拒绝应用
-- ai_proposals.payload_json: 有类型契约的建议内容
-- ai_proposals.state: 待采用、采用、拒绝或过期
-- ai_proposals.created_at: UTC 创建时间，界面转换为本地时间

-- 导出文件与输入版本
CREATE TABLE IF NOT EXISTS export_artifacts (
    id TEXT PRIMARY KEY NOT NULL,
    job_id TEXT NOT NULL REFERENCES workflow_jobs(id),
    file_id TEXT NOT NULL REFERENCES file_assets(id),
    entity_kind TEXT NOT NULL CHECK(entity_kind IN ('lesson_revision','practice_revision','analysis_run','score_template')),
    entity_id TEXT NOT NULL,
    variant TEXT NOT NULL CHECK(variant IN ('student','teacher','report','score_template')),
    format TEXT NOT NULL CHECK(format IN ('docx','pdf','xlsx','csv')),
    input_hash TEXT NOT NULL CHECK(length(input_hash)=64),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
-- export_artifacts.id: 稳定 UUID，由服务端生成
-- export_artifacts.job_id: 导出任务
-- export_artifacts.file_id: 导出结果文件
-- export_artifacts.entity_kind: 导出目标类型
-- export_artifacts.entity_id: 对应固定版本，应用层校验
-- export_artifacts.variant: 学生卷、教师卷、报告或成绩模板
-- export_artifacts.format: 文件格式
-- export_artifacts.input_hash: 输入快照指纹
-- export_artifacts.created_at: UTC 创建时间，界面转换为本地时间

-- 关键写操作幂等记录
CREATE TABLE IF NOT EXISTS command_submissions (
    submission_id TEXT PRIMARY KEY NOT NULL,
    operation TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
    result_json TEXT NOT NULL CHECK(json_valid(result_json))
);
-- command_submissions.submission_id: 客户端一次操作的稳定 ID
-- command_submissions.operation: 确认试卷、导入成绩、采用建议等
-- command_submissions.request_hash: 相同 ID 不同请求必须报冲突
-- command_submissions.result_json: 与正式数据在同一库事务中写入的响应

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

