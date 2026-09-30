-- ZQKY 教学闭环 v1：参考 DDL；禁止对正式数据直接执行。
PRAGMA foreign_keys=ON;

-- 题目修订与知识点的多对多关联
CREATE TABLE IF NOT EXISTS question_knowledge_links (
    question_revision_id TEXT NOT NULL REFERENCES question_revisions(id),
    knowledge_point_id TEXT NOT NULL,
    knowledge_revision_id TEXT NOT NULL,
    subject_id_snapshot TEXT NOT NULL,
    knowledge_name_snapshot TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('primary','secondary')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY(question_revision_id,knowledge_point_id)
);
-- question_knowledge_links.question_revision_id: 现有题库不可变题目修订；同题跨知识点不复制题干
-- question_knowledge_links.knowledge_point_id: EXT：知识点身份
-- question_knowledge_links.knowledge_revision_id: EXT：知识点内容修订
-- question_knowledge_links.subject_id_snapshot: 关联时学科，跨库校验同学科
-- question_knowledge_links.knowledge_name_snapshot: 关联时知识点名称，历史可读
-- question_knowledge_links.role: 主要或关联知识点，仅分类、不分配分值
-- question_knowledge_links.created_at: UTC 创建时间，界面转换为本地时间

CREATE INDEX IF NOT EXISTS ix_question_knowledge ON question_knowledge_links(knowledge_point_id,question_revision_id);

CREATE TRIGGER IF NOT EXISTS immutable_question_knowledge_links_update BEFORE UPDATE ON question_knowledge_links BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

CREATE TRIGGER IF NOT EXISTS immutable_question_knowledge_links_delete BEFORE DELETE ON question_knowledge_links BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;

