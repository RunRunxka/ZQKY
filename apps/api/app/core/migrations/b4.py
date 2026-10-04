"""Append-only B4 declarations. No B5 tables or cross-database foreign keys."""
from app.core.migrations.base import Migration, RebuildPlan

TABLES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_job_owner ON workflow_jobs(id,owner_id)",
    """CREATE TABLE analysis_runs (
        id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL DEFAULT 'local',
        assessment_id TEXT NOT NULL, score_revision_id TEXT NOT NULL, paper_revision_id TEXT NOT NULL,
        subject_id TEXT NOT NULL, rule_code TEXT NOT NULL CHECK(rule_code='any_loss_v1'),
        input_hash TEXT NOT NULL CHECK(length(input_hash)=64), input_json TEXT NOT NULL CHECK(json_valid(input_json)),
        job_id TEXT NOT NULL, report_ready INTEGER NOT NULL DEFAULT 0 CHECK(report_ready IN(0,1)),
        selected_count INTEGER NOT NULL CHECK(selected_count>0), leaf_count INTEGER NOT NULL CHECK(leaf_count>0),
        knowledge_count INTEGER NOT NULL CHECK(knowledge_count>=0), class_count INTEGER NOT NULL CHECK(class_count>0),
        created_at TEXT NOT NULL, ready_at TEXT,
        UNIQUE(owner_id,input_hash), UNIQUE(id,owner_id), UNIQUE(id,paper_revision_id),
        FOREIGN KEY(score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id),
        FOREIGN KEY(assessment_id,paper_revision_id) REFERENCES assessments(id,paper_revision_id),
        FOREIGN KEY(job_id,owner_id) REFERENCES workflow_jobs(id,owner_id),
        CHECK((report_ready=0 AND ready_at IS NULL) OR(report_ready=1 AND ready_at IS NOT NULL)))""",
    """CREATE TABLE analysis_participants (
        run_id TEXT NOT NULL REFERENCES analysis_runs(id), participant_id TEXT NOT NULL,
        student_id TEXT NOT NULL, class_id TEXT NOT NULL, snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),
        PRIMARY KEY(run_id,participant_id), UNIQUE(run_id,student_id))""",
    """CREATE TABLE analysis_item_snapshots (
        run_id TEXT NOT NULL, item_id TEXT NOT NULL, paper_revision_id TEXT NOT NULL,
        snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)), PRIMARY KEY(run_id,item_id),
        FOREIGN KEY(run_id,paper_revision_id) REFERENCES analysis_runs(id,paper_revision_id),
        FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id))""",
    """CREATE TABLE analysis_student_results (
        run_id TEXT NOT NULL, participant_id TEXT NOT NULL, knowledge_point_id TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
        PRIMARY KEY(run_id,participant_id,knowledge_point_id),
        FOREIGN KEY(run_id,participant_id) REFERENCES analysis_participants(run_id,participant_id))""",
    """CREATE TABLE analysis_class_results (
        run_id TEXT NOT NULL REFERENCES analysis_runs(id), class_id TEXT NOT NULL, knowledge_point_id TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), PRIMARY KEY(run_id,class_id,knowledge_point_id))""",
    """CREATE TABLE analysis_evidence (
        id TEXT PRIMARY KEY NOT NULL, run_id TEXT NOT NULL, participant_id TEXT NOT NULL, item_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN('recorded','missing','absent','exempt')), score_units INTEGER,
        UNIQUE(run_id,participant_id,item_id),
        FOREIGN KEY(run_id,participant_id) REFERENCES analysis_participants(run_id,participant_id),
        FOREIGN KEY(run_id,item_id) REFERENCES analysis_item_snapshots(run_id,item_id),
        CHECK((status='recorded' AND typeof(score_units)='integer' AND score_units>=0) OR(status<>'recorded' AND score_units IS NULL)))""",
    "CREATE INDEX ix_analysis_evidence_run ON analysis_evidence(run_id,participant_id,item_id)",
    """CREATE TABLE analysis_teacher_notes (
        id TEXT PRIMARY KEY NOT NULL, run_id TEXT NOT NULL REFERENCES analysis_runs(id),
        participant_id TEXT, knowledge_point_id TEXT, note TEXT NOT NULL CHECK(length(trim(note)) BETWEEN 1 AND 2000),
        created_at TEXT NOT NULL, FOREIGN KEY(run_id,participant_id) REFERENCES analysis_participants(run_id,participant_id))""",
    """CREATE TABLE practice_sets (
        id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL DEFAULT 'local', analysis_run_id TEXT NOT NULL,
        subject_id TEXT NOT NULL, title TEXT NOT NULL, current_revision_id TEXT,
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0), status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('active','archived')),
        created_at TEXT NOT NULL, UNIQUE(id,owner_id),
        FOREIGN KEY(analysis_run_id,owner_id) REFERENCES analysis_runs(id,owner_id),
        FOREIGN KEY(current_revision_id,id) REFERENCES practice_revisions(id,practice_set_id) DEFERRABLE INITIALLY DEFERRED)""",
    """CREATE TABLE practice_revisions (
        id TEXT PRIMARY KEY NOT NULL, practice_set_id TEXT NOT NULL REFERENCES practice_sets(id), version INTEGER NOT NULL CHECK(version>0),
        state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN('draft','reviewed')),
        input_hash TEXT NOT NULL, selection_snapshot_json TEXT NOT NULL CHECK(json_valid(selection_snapshot_json)),
        constraints_json TEXT NOT NULL CHECK(json_valid(constraints_json)), draft_items_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(draft_items_json)),
        total_score_units INTEGER NOT NULL DEFAULT 0 CHECK(total_score_units>=0), reviewed_at TEXT,
        title_snapshot TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(practice_set_id,version), UNIQUE(id,practice_set_id),
        CHECK((state='draft' AND reviewed_at IS NULL) OR(state='reviewed' AND reviewed_at IS NOT NULL)))""",
    """CREATE TABLE practice_selections (
        id TEXT PRIMARY KEY NOT NULL, practice_revision_id TEXT NOT NULL REFERENCES practice_revisions(id),
        item_key TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>0), question_id TEXT NOT NULL, question_revision_id TEXT NOT NULL,
        question_content_hash TEXT NOT NULL CHECK(length(question_content_hash)=64),
        content_snapshot_json TEXT NOT NULL CHECK(json_valid(content_snapshot_json)), metadata_snapshot_json TEXT NOT NULL CHECK(json_valid(metadata_snapshot_json)),
        rich_assets_json TEXT NOT NULL CHECK(json_valid(rich_assets_json)), reason_json TEXT NOT NULL CHECK(json_valid(reason_json)),
        source_snapshot_json TEXT NOT NULL CHECK(json_valid(source_snapshot_json)), answer_state TEXT NOT NULL,
        UNIQUE(id,practice_revision_id), UNIQUE(practice_revision_id,item_key), UNIQUE(practice_revision_id,ordinal))""",
    """CREATE TABLE practice_items (
        id TEXT PRIMARY KEY NOT NULL, practice_revision_id TEXT NOT NULL REFERENCES practice_revisions(id), selection_id TEXT NOT NULL,
        node_key TEXT NOT NULL, parent_item_id TEXT, question_no TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>0),
        is_scored INTEGER NOT NULL CHECK(is_scored IN(0,1)), max_score_units INTEGER,
        content_json TEXT NOT NULL CHECK(json_valid(content_json)), source_locator_json TEXT NOT NULL CHECK(json_valid(source_locator_json)),
        UNIQUE(id,practice_revision_id), UNIQUE(practice_revision_id,ordinal), UNIQUE(practice_revision_id,question_no),
        UNIQUE(selection_id,node_key),
        FOREIGN KEY(selection_id,practice_revision_id) REFERENCES practice_selections(id,practice_revision_id),
        FOREIGN KEY(parent_item_id,practice_revision_id) REFERENCES practice_items(id,practice_revision_id),
        CHECK(parent_item_id IS NULL OR parent_item_id<>id),
        CHECK((is_scored=1 AND typeof(max_score_units)='integer' AND max_score_units>0) OR(is_scored=0 AND max_score_units IS NULL)))""",
    """CREATE TABLE practice_item_knowledge (
        item_id TEXT NOT NULL, practice_revision_id TEXT NOT NULL, knowledge_point_id TEXT NOT NULL,
        knowledge_revision_id TEXT NOT NULL, name_snapshot TEXT NOT NULL, subject_snapshot TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN('primary','secondary')), PRIMARY KEY(item_id,knowledge_point_id),
        FOREIGN KEY(item_id,practice_revision_id) REFERENCES practice_items(id,practice_revision_id))""",
    """CREATE TABLE practice_conversions (
        id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL DEFAULT 'local', practice_revision_id TEXT NOT NULL REFERENCES practice_revisions(id),
        paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id), assessment_id TEXT NOT NULL,
        input_hash TEXT NOT NULL CHECK(length(input_hash)=64), participant_snapshot_json TEXT NOT NULL CHECK(json_valid(participant_snapshot_json)),
        created_at TEXT NOT NULL, UNIQUE(id,practice_revision_id,paper_revision_id), UNIQUE(assessment_id),
        FOREIGN KEY(assessment_id,paper_revision_id) REFERENCES assessments(id,paper_revision_id))""",
    """CREATE TABLE practice_paper_item_mappings (
        conversion_id TEXT NOT NULL, practice_revision_id TEXT NOT NULL, practice_item_id TEXT NOT NULL,
        paper_item_id TEXT NOT NULL, paper_revision_id TEXT NOT NULL,
        PRIMARY KEY(conversion_id,practice_item_id), UNIQUE(paper_revision_id,paper_item_id),
        FOREIGN KEY(conversion_id,practice_revision_id,paper_revision_id) REFERENCES practice_conversions(id,practice_revision_id,paper_revision_id),
        FOREIGN KEY(practice_item_id,practice_revision_id) REFERENCES practice_items(id,practice_revision_id),
        FOREIGN KEY(paper_item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id))""",
    """CREATE TABLE practice_exports (
        id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL DEFAULT 'local', practice_revision_id TEXT NOT NULL REFERENCES practice_revisions(id),
        variant TEXT NOT NULL CHECK(variant IN('student','teacher','score_template')), assessment_id TEXT REFERENCES assessments(id),
        input_hash TEXT NOT NULL CHECK(length(input_hash)=64), frozen_input_json TEXT NOT NULL CHECK(json_valid(frozen_input_json)),
        job_id TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(owner_id,input_hash), UNIQUE(id,owner_id),
        FOREIGN KEY(job_id,owner_id) REFERENCES workflow_jobs(id,owner_id),
        CHECK((variant='score_template' AND assessment_id IS NOT NULL) OR(variant<>'score_template' AND assessment_id IS NULL)))""",
    """CREATE TABLE export_artifacts (
        id TEXT PRIMARY KEY NOT NULL, export_id TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL DEFAULT 'local',
        practice_revision_id TEXT NOT NULL REFERENCES practice_revisions(id), file_asset_id TEXT NOT NULL UNIQUE REFERENCES file_assets(id),
        filename TEXT NOT NULL, media_type TEXT NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64), byte_size INTEGER NOT NULL CHECK(byte_size>0),
        created_at TEXT NOT NULL, FOREIGN KEY(export_id,owner_id) REFERENCES practice_exports(id,owner_id))""",
)


def _sealed_children(table: str, parent: str, fk: str, state: str, sealed: str) -> tuple[str, ...]:
    return tuple(
        f"CREATE TRIGGER freeze_{table}_{op.lower()} BEFORE {op} ON {table} "
        f"WHEN " + " OR ".join(f"(SELECT {state} FROM {parent} WHERE id={prefix}.{fk})={sealed}" for prefix in prefixes) +
        " BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"
        for op, prefixes in (("INSERT", ("NEW",)), ("UPDATE", ("OLD", "NEW")), ("DELETE", ("OLD",)))
    )


TRIGGERS = (
    """CREATE TRIGGER practice_identity_fixed BEFORE UPDATE ON practice_sets WHEN
      NEW.id IS NOT OLD.id OR NEW.owner_id IS NOT OLD.owner_id OR
      NEW.analysis_run_id IS NOT OLD.analysis_run_id OR NEW.subject_id IS NOT OLD.subject_id OR
      NEW.created_at IS NOT OLD.created_at
      BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END""",
    """CREATE TRIGGER practice_source_subject BEFORE INSERT ON practice_sets WHEN
      NOT EXISTS(SELECT 1 FROM analysis_runs a WHERE a.id=NEW.analysis_run_id AND a.owner_id=NEW.owner_id AND a.subject_id=NEW.subject_id)
      BEGIN SELECT RAISE(ABORT,'PRACTICE_SOURCE_MISMATCH'); END""",
    """CREATE TRIGGER conversion_source BEFORE INSERT ON practice_conversions BEGIN
      SELECT CASE WHEN NOT EXISTS(
        SELECT 1 FROM practice_revisions r JOIN practice_sets s ON s.id=r.practice_set_id
        JOIN paper_revisions pr ON pr.id=NEW.paper_revision_id
        JOIN papers p ON p.id=pr.paper_id
        JOIN assessments a ON a.id=NEW.assessment_id AND a.paper_revision_id=pr.id
        WHERE r.id=NEW.practice_revision_id AND r.state='reviewed' AND s.owner_id=NEW.owner_id
          AND pr.state='confirmed' AND pr.source_practice_revision_id=r.id
          AND p.owner_id=NEW.owner_id AND p.subject_id=s.subject_id AND a.owner_id=NEW.owner_id
      ) THEN RAISE(ABORT,'PRACTICE_CONVERSION_SOURCE_MISMATCH') END;
    END""",
    """CREATE TRIGGER practice_cycle_update BEFORE UPDATE OF parent_item_id ON practice_items WHEN NEW.parent_item_id IS NOT NULL BEGIN
      SELECT CASE WHEN EXISTS(WITH RECURSIVE a(id,parent_item_id) AS (SELECT id,parent_item_id FROM practice_items WHERE id=NEW.parent_item_id UNION SELECT p.id,p.parent_item_id FROM practice_items p JOIN a ON p.id=a.parent_item_id) SELECT 1 FROM a WHERE id=NEW.id) THEN RAISE(ABORT,'ITEM_CYCLE') END;
    END""",
    """CREATE TRIGGER practice_cycle_insert AFTER INSERT ON practice_items WHEN NEW.parent_item_id IS NOT NULL BEGIN
      SELECT CASE WHEN EXISTS(WITH RECURSIVE a(id,parent_item_id) AS (SELECT id,parent_item_id FROM practice_items WHERE id=NEW.parent_item_id UNION SELECT p.id,p.parent_item_id FROM practice_items p JOIN a ON p.id=a.parent_item_id) SELECT 1 FROM a WHERE id=NEW.id) THEN RAISE(ABORT,'ITEM_CYCLE') END;
    END""",
    """CREATE TRIGGER note_knowledge_target BEFORE INSERT ON analysis_teacher_notes WHEN NEW.knowledge_point_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM analysis_student_results WHERE run_id=NEW.run_id AND knowledge_point_id=NEW.knowledge_point_id) BEGIN SELECT RAISE(ABORT,'NOTE_TARGET_INVALID'); END""",
    "CREATE TRIGGER analysis_no_direct_ready BEFORE INSERT ON analysis_runs WHEN NEW.report_ready=1 BEGIN SELECT RAISE(ABORT,'USE_READY_TRANSITION'); END",
    """CREATE TRIGGER analysis_seal BEFORE UPDATE OF report_ready ON analysis_runs WHEN NEW.report_ready=1 AND OLD.report_ready=0 BEGIN
      SELECT CASE WHEN (SELECT state FROM score_revisions WHERE id=NEW.score_revision_id)<>'confirmed' THEN RAISE(ABORT,'SCORE_NOT_CONFIRMED') END;
      SELECT CASE WHEN (SELECT count(*) FROM analysis_participants WHERE run_id=NEW.id)<>NEW.selected_count THEN RAISE(ABORT,'ANALYSIS_PARTICIPANTS_INCOMPLETE') END;
      SELECT CASE WHEN (SELECT count(*) FROM analysis_item_snapshots WHERE run_id=NEW.id)<>NEW.leaf_count THEN RAISE(ABORT,'ANALYSIS_ITEMS_INCOMPLETE') END;
      SELECT CASE WHEN (SELECT count(*) FROM analysis_evidence WHERE run_id=NEW.id)<>NEW.selected_count*NEW.leaf_count THEN RAISE(ABORT,'ANALYSIS_EVIDENCE_INCOMPLETE') END;
      SELECT CASE WHEN (SELECT count(*) FROM analysis_student_results WHERE run_id=NEW.id)<>NEW.selected_count*NEW.knowledge_count THEN RAISE(ABORT,'ANALYSIS_STUDENTS_INCOMPLETE') END;
      SELECT CASE WHEN (SELECT count(*) FROM analysis_class_results WHERE run_id=NEW.id)<>NEW.class_count*NEW.knowledge_count THEN RAISE(ABORT,'ANALYSIS_CLASSES_INCOMPLETE') END;
    END""",
    """CREATE TRIGGER analysis_inputs_fixed BEFORE UPDATE ON analysis_runs WHEN
      NEW.id IS NOT OLD.id OR NEW.owner_id IS NOT OLD.owner_id OR NEW.assessment_id IS NOT OLD.assessment_id OR
      NEW.score_revision_id IS NOT OLD.score_revision_id OR NEW.paper_revision_id IS NOT OLD.paper_revision_id OR NEW.subject_id IS NOT OLD.subject_id OR
      NEW.rule_code IS NOT OLD.rule_code OR NEW.input_hash IS NOT OLD.input_hash OR NEW.input_json IS NOT OLD.input_json OR NEW.job_id IS NOT OLD.job_id OR
      NEW.selected_count IS NOT OLD.selected_count OR NEW.leaf_count IS NOT OLD.leaf_count OR NEW.knowledge_count IS NOT OLD.knowledge_count OR NEW.class_count IS NOT OLD.class_count OR
      NEW.created_at IS NOT OLD.created_at OR OLD.report_ready=1
      BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END""",
    "CREATE TRIGGER analysis_no_delete BEFORE DELETE ON analysis_runs BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END",
    "CREATE TRIGGER practice_requires_ready BEFORE INSERT ON practice_sets WHEN coalesce((SELECT report_ready FROM analysis_runs WHERE id=NEW.analysis_run_id),0)<>1 BEGIN SELECT RAISE(ABORT,'REPORT_NOT_READY'); END",
    "CREATE TRIGGER practice_no_direct_review BEFORE INSERT ON practice_revisions WHEN NEW.state='reviewed' BEGIN SELECT RAISE(ABORT,'USE_REVIEW_TRANSITION'); END",
    """CREATE TRIGGER practice_review BEFORE UPDATE OF state ON practice_revisions WHEN NEW.state='reviewed' AND OLD.state='draft' BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM practice_items WHERE practice_revision_id=NEW.id AND is_scored=1) THEN RAISE(ABORT,'NO_SCORED_ITEMS') END;
      SELECT CASE WHEN NEW.total_score_units<>(SELECT coalesce(sum(max_score_units),0) FROM practice_items WHERE practice_revision_id=NEW.id AND is_scored=1) THEN RAISE(ABORT,'PRACTICE_TOTAL_MISMATCH') END;
      SELECT CASE WHEN EXISTS(SELECT 1 FROM practice_items p JOIN practice_items c ON c.parent_item_id=p.id WHERE p.practice_revision_id=NEW.id AND p.is_scored=1) THEN RAISE(ABORT,'SCORED_ITEM_MUST_BE_LEAF') END;
      SELECT CASE WHEN EXISTS(SELECT 1 FROM practice_items p WHERE p.practice_revision_id=NEW.id AND p.is_scored=1 AND NOT EXISTS(SELECT 1 FROM practice_item_knowledge k WHERE k.item_id=p.id)) THEN RAISE(ABORT,'ITEM_KNOWLEDGE_MISSING') END;
    END""",
    "CREATE TRIGGER practice_revision_update BEFORE UPDATE ON practice_revisions WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END",
    "CREATE TRIGGER practice_revision_delete BEFORE DELETE ON practice_revisions WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END",
    """CREATE TRIGGER practice_mapping_source BEFORE INSERT ON practice_paper_item_mappings BEGIN
      SELECT CASE WHEN (SELECT source_practice_revision_id FROM paper_revisions WHERE id=NEW.paper_revision_id) IS NOT NEW.practice_revision_id THEN RAISE(ABORT,'PRACTICE_SOURCE_MISMATCH') END;
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM paper_items p WHERE p.id=NEW.paper_item_id AND p.paper_revision_id=NEW.paper_revision_id
        AND json_extract(p.source_locator_json,'$.practiceItemId')=NEW.practice_item_id
        AND json_extract(p.source_locator_json,'$.practiceRevisionId')=NEW.practice_revision_id)
      THEN RAISE(ABORT,'PRACTICE_ITEM_MAPPING_MISMATCH') END;
    END""",
    """CREATE TRIGGER export_source BEFORE INSERT ON practice_exports BEGIN
      SELECT CASE WHEN (SELECT state FROM practice_revisions WHERE id=NEW.practice_revision_id)<>'reviewed' THEN RAISE(ABORT,'PRACTICE_NOT_REVIEWED') END;
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM practice_revisions r JOIN practice_sets s ON s.id=r.practice_set_id WHERE r.id=NEW.practice_revision_id AND s.owner_id=NEW.owner_id) THEN RAISE(ABORT,'PRACTICE_OWNER_MISMATCH') END;
      SELECT CASE WHEN NEW.variant='score_template' AND NOT EXISTS(SELECT 1 FROM practice_conversions WHERE assessment_id=NEW.assessment_id AND practice_revision_id=NEW.practice_revision_id AND owner_id=NEW.owner_id) THEN RAISE(ABORT,'PRACTICE_ASSESSMENT_MISMATCH') END;
    END""",
    """CREATE TRIGGER artifact_source BEFORE INSERT ON export_artifacts BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM practice_exports e JOIN file_assets a ON a.id=NEW.file_asset_id WHERE e.id=NEW.export_id AND e.owner_id=NEW.owner_id AND e.practice_revision_id=NEW.practice_revision_id AND a.owner_id=NEW.owner_id AND a.kind='export' AND a.sha256=NEW.sha256 AND a.byte_size=NEW.byte_size AND a.media_type=NEW.media_type) THEN RAISE(ABORT,'EXPORT_ASSET_MISMATCH') END;
    END""",
) + sum((_sealed_children(t, 'analysis_runs', 'run_id', 'report_ready', '1') for t in
         ('analysis_participants', 'analysis_item_snapshots', 'analysis_student_results', 'analysis_class_results', 'analysis_evidence')), ()) + sum(
    (_sealed_children(t, 'practice_revisions', 'practice_revision_id', 'state', "'reviewed'") for t in
     ('practice_selections', 'practice_items', 'practice_item_knowledge')), ()) + tuple(
    f"CREATE TRIGGER immutable_{t}_{op.lower()} BEFORE {op} ON {t} BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"
    for t in ('analysis_teacher_notes', 'practice_conversions', 'practice_paper_item_mappings', 'practice_exports', 'export_artifacts')
    for op in ('UPDATE', 'DELETE')
) + ("CREATE TRIGGER notes_ready BEFORE INSERT ON analysis_teacher_notes WHEN coalesce((SELECT report_ready FROM analysis_runs WHERE id=NEW.run_id),0)<>1 BEGIN SELECT RAISE(ABORT,'REPORT_NOT_READY'); END",)


def paper_rebuild(original: tuple[str, ...], related: tuple[str, ...]) -> RebuildPlan:
    """Restore every original index/trigger; extend only the source confirmation gate."""
    restore = tuple(s for s in original if 'CREATE INDEX' in s or 'CREATE TRIGGER' in s)
    dependent = tuple(s for s in related + TRIGGERS if 'CREATE TRIGGER' in s and 'paper_revisions' in s)
    restore += dependent
    restore = tuple(s.replace("NEW.state='confirmed' AND OLD.state='draft' BEGIN", "NEW.state='confirmed' AND OLD.state='draft' BEGIN\n SELECT CASE WHEN NEW.source_practice_revision_id IS NOT NULL AND (SELECT state FROM practice_revisions WHERE id=NEW.source_practice_revision_id)<>'reviewed' THEN RAISE(ABORT,'PRACTICE_NOT_REVIEWED') END;") if 'CREATE TRIGGER IF NOT EXISTS paper_confirm ' in s else s for s in restore)
    restore += (
        """CREATE TRIGGER paper_practice_confirm BEFORE UPDATE OF state ON paper_revisions WHEN NEW.state='confirmed' AND OLD.state='draft' AND NEW.source_practice_revision_id IS NOT NULL BEGIN
          SELECT CASE WHEN (SELECT count(*) FROM paper_items WHERE paper_revision_id=NEW.id)<>(SELECT count(*) FROM practice_items WHERE practice_revision_id=NEW.source_practice_revision_id) THEN RAISE(ABORT,'PRACTICE_ITEM_MAPPING_INCOMPLETE') END;
          SELECT CASE WHEN (SELECT count(DISTINCT json_extract(source_locator_json,'$.practiceItemId')) FROM paper_items WHERE paper_revision_id=NEW.id)<>(SELECT count(*) FROM practice_items WHERE practice_revision_id=NEW.source_practice_revision_id) THEN RAISE(ABORT,'PRACTICE_ITEM_MAPPING_INCOMPLETE') END;
          SELECT CASE WHEN EXISTS(SELECT 1 FROM paper_items i LEFT JOIN practice_items p ON p.id=json_extract(i.source_locator_json,'$.practiceItemId') AND p.practice_revision_id=NEW.source_practice_revision_id LEFT JOIN practice_selections s ON s.id=p.selection_id WHERE i.paper_revision_id=NEW.id AND (p.id IS NULL OR i.question_no<>p.question_no OR i.ordinal<>p.ordinal OR i.question_revision_id IS NOT s.question_revision_id OR i.is_scored<>p.is_scored OR i.max_score_units IS NOT p.max_score_units OR json(i.content_json) IS NOT json(p.content_json) OR (SELECT json_extract(parent.source_locator_json,'$.practiceItemId') FROM paper_items parent WHERE parent.id=i.parent_item_id) IS NOT p.parent_item_id)) THEN RAISE(ABORT,'PRACTICE_ITEM_SNAPSHOT_MISMATCH') END;
          SELECT CASE WHEN EXISTS(SELECT 1 FROM paper_items i JOIN practice_items p ON p.id=json_extract(i.source_locator_json,'$.practiceItemId') WHERE i.paper_revision_id=NEW.id AND ((SELECT count(*) FROM paper_item_knowledge WHERE item_id=i.id)<>(SELECT count(*) FROM practice_item_knowledge WHERE item_id=p.id) OR EXISTS(SELECT 1 FROM paper_item_knowledge k WHERE k.item_id=i.id AND NOT EXISTS(SELECT 1 FROM practice_item_knowledge pk WHERE pk.item_id=p.id AND pk.knowledge_point_id=k.knowledge_point_id AND pk.knowledge_revision_id=k.knowledge_revision_id AND pk.name_snapshot=k.knowledge_name_snapshot AND pk.role=k.role)))) THEN RAISE(ABORT,'PRACTICE_KNOWLEDGE_SNAPSHOT_MISMATCH') END;
        END""",
        """CREATE TRIGGER paper_practice_owner BEFORE INSERT ON paper_revisions WHEN NEW.source_practice_revision_id IS NOT NULL BEGIN
          SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM practice_revisions r JOIN practice_sets s ON s.id=r.practice_set_id JOIN papers p ON p.id=NEW.paper_id WHERE r.id=NEW.source_practice_revision_id AND s.owner_id=p.owner_id AND s.subject_id=p.subject_id AND r.state='reviewed') THEN RAISE(ABORT,'PRACTICE_OWNER_OR_STATE_MISMATCH') END;
        END""",
        """CREATE TRIGGER paper_source_fixed BEFORE UPDATE OF paper_id,source_file_id,source_practice_revision_id ON paper_revisions WHEN NEW.paper_id IS NOT OLD.paper_id OR NEW.source_file_id IS NOT OLD.source_file_id OR NEW.source_practice_revision_id IS NOT OLD.source_practice_revision_id BEGIN SELECT RAISE(ABORT,'PAPER_SOURCE_FIXED'); END""",
    )
    columns = 'id,paper_id,version,source_file_id,source_practice_revision_id,total_score_units,state,confirmed_at,created_at,title_snapshot,title_snapshot_source'
    return RebuildPlan(table='paper_revisions', new_table_sql="""CREATE TABLE paper_revisions_rebuilt (
        id TEXT PRIMARY KEY NOT NULL, paper_id TEXT NOT NULL REFERENCES papers(id), version INTEGER NOT NULL CHECK(version>0),
        source_file_id TEXT REFERENCES file_assets(id), source_practice_revision_id TEXT REFERENCES practice_revisions(id),
        total_score_units INTEGER NOT NULL CHECK(total_score_units>=0), state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN('draft','confirmed')),
        confirmed_at TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        title_snapshot TEXT NOT NULL DEFAULT '', title_snapshot_source TEXT,
        UNIQUE(paper_id,version), UNIQUE(id,paper_id),
        CHECK((source_file_id IS NOT NULL AND source_practice_revision_id IS NULL) OR(source_file_id IS NULL AND source_practice_revision_id IS NOT NULL)),
        CHECK((state='draft' AND confirmed_at IS NULL) OR(state='confirmed' AND confirmed_at IS NOT NULL)))""",
        copy_sql=f'INSERT INTO paper_revisions_rebuilt ({columns}) SELECT {columns} FROM paper_revisions',
        drop_and_rename=tuple('DROP TRIGGER IF EXISTS '+s.split('TRIGGER', 1)[1].strip().removeprefix('IF NOT EXISTS ').split()[0] for s in restore if 'CREATE TRIGGER' in s) + ('DROP TABLE paper_revisions', 'ALTER TABLE paper_revisions_rebuilt RENAME TO paper_revisions'),
        restore=restore, verifications=(('exclusive_source', 'SELECT count(*) FROM paper_revisions WHERE (source_file_id IS NULL)=(source_practice_revision_id IS NULL)'),
            ('required_trigger', "SELECT CASE WHEN EXISTS(SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='paper_confirm') THEN 0 ELSE 1 END")))


def migrations(original: tuple[str, ...], related: tuple[str, ...]) -> tuple[Migration, ...]:
    return (
        Migration('0008', 'B4 analysis, reviewed practices and managed export metadata', TABLES + TRIGGERS),
        Migration('0009', 'B4 exclusive file/practice paper source via checked rebuild', rebuild=paper_rebuild(original, related)),
    )
