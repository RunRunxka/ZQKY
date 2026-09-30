-- ZQKY 教学闭环 v1：参考 DDL；禁止对正式数据直接执行。
PRAGMA foreign_keys=ON;

-- 学科字典
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY NOT NULL,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived'))
);
-- subjects.id: 复用现有项目学科键，不另造不兼容身份
-- subjects.code: 稳定学科代码，复用项目已有 subjectId
-- subjects.name: 学科名称
-- subjects.status: 启用或归档

-- 知识点身份与目录位置
CREATE TABLE IF NOT EXISTS knowledge_points (
    id TEXT PRIMARY KEY NOT NULL,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    code TEXT NOT NULL,
    parent_id TEXT,
    current_revision_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(subject_id,code),
    UNIQUE(id,subject_id),
    FOREIGN KEY(parent_id,subject_id) REFERENCES knowledge_points(id,subject_id),
    FOREIGN KEY(current_revision_id,id) REFERENCES knowledge_point_revisions(id,knowledge_point_id) DEFERRABLE INITIALLY DEFERRED,
    CHECK(parent_id IS NULL OR parent_id<>id)
);
-- knowledge_points.id: 稳定 UUID，由服务端生成
-- knowledge_points.subject_id: 所属学科
-- knowledge_points.code: 学科内稳定业务代码，不编码教材路径
-- knowledge_points.parent_id: 上位知识点，可空；不代表教材章节
-- knowledge_points.current_revision_id: 当前知识点内容修订
-- knowledge_points.sort_order: 同层显示顺序
-- knowledge_points.status: 归档后保留历史引用
-- knowledge_points.revision: 可变实体的乐观锁版本
-- knowledge_points.created_at: UTC 创建时间，界面转换为本地时间

-- 知识点不可变内容修订
CREATE TABLE IF NOT EXISTS knowledge_point_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    knowledge_point_id TEXT NOT NULL REFERENCES knowledge_points(id),
    version INTEGER NOT NULL CHECK(version>0),
    name TEXT NOT NULL CHECK(length(trim(name))>0),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(knowledge_point_id,version),
    UNIQUE(id,knowledge_point_id)
);
-- knowledge_point_revisions.id: 稳定 UUID，由服务端生成
-- knowledge_point_revisions.knowledge_point_id: 知识点身份
-- knowledge_point_revisions.version: 从 1 递增的内容版本
-- knowledge_point_revisions.name: 正式知识点名称
-- knowledge_point_revisions.description: 定义与范围说明，不记录学生掌握概率
-- knowledge_point_revisions.created_at: UTC 创建时间，界面转换为本地时间

-- 知识点检索别名
CREATE TABLE IF NOT EXISTS knowledge_aliases (
    id TEXT PRIMARY KEY NOT NULL,
    knowledge_point_id TEXT NOT NULL REFERENCES knowledge_points(id),
    alias TEXT NOT NULL CHECK(length(trim(alias))>0),
    normalized_alias TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(knowledge_point_id,normalized_alias)
);
-- knowledge_aliases.id: 稳定 UUID，由服务端生成
-- knowledge_aliases.knowledge_point_id: 正式知识点
-- knowledge_aliases.alias: 人工确认的同义名称
-- knowledge_aliases.normalized_alias: 服务端规范化后的检索词
-- knowledge_aliases.created_at: UTC 创建时间，界面转换为本地时间

-- 教材依据与知识点的可选关联
CREATE TABLE IF NOT EXISTS textbook_knowledge_links (
    id TEXT PRIMARY KEY NOT NULL,
    knowledge_point_id TEXT NOT NULL,
    knowledge_revision_id TEXT NOT NULL,
    document_revision_id TEXT NOT NULL,
    locator_json TEXT NOT NULL CHECK(json_valid(locator_json)),
    locator_hash TEXT NOT NULL,
    title_snapshot TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('human','ai_confirmed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(knowledge_revision_id,knowledge_point_id) REFERENCES knowledge_point_revisions(id,knowledge_point_id),
    UNIQUE(knowledge_revision_id,document_revision_id,locator_hash)
);
-- textbook_knowledge_links.id: 稳定 UUID，由服务端生成
-- textbook_knowledge_links.knowledge_point_id: 本库知识点身份
-- textbook_knowledge_links.knowledge_revision_id: 本库知识点修订
-- textbook_knowledge_links.document_revision_id: EXT：教材目录 document_revisions.id
-- textbook_knowledge_links.locator_json: 章节或原文区间定位，服务端核验范围
-- textbook_knowledge_links.locator_hash: 定位规范化 JSON 的 SHA-256
-- textbook_knowledge_links.title_snapshot: 关联时的教材标题
-- textbook_knowledge_links.source: 人工标注或确认后的 AI 建议
-- textbook_knowledge_links.created_at: UTC 创建时间，界面转换为本地时间

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

