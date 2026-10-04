"""B5 append-only teaching migration; existing 0001..0009 declarations unchanged."""
from app.core.migrations.base import Migration

TABLES = (
    "CREATE UNIQUE INDEX ux_classes_id_owner_b5 ON classes(id,owner_id)",
    """CREATE TABLE lesson_plans (
        id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL,
        subject_id TEXT NOT NULL, class_id TEXT NOT NULL,
        current_revision_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9007199254740991),
        archived_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(id,owner_id),
        FOREIGN KEY(class_id,owner_id) REFERENCES classes(id,owner_id),
        FOREIGN KEY(current_revision_id,id,owner_id,revision) REFERENCES lesson_plan_revisions(id,lesson_plan_id,owner_id,version) DEFERRABLE INITIALLY DEFERRED)""",
    """CREATE TABLE lesson_plan_revisions (
        id TEXT PRIMARY KEY NOT NULL, lesson_plan_id TEXT NOT NULL, owner_id TEXT NOT NULL,
        version INTEGER NOT NULL CHECK(version BETWEEN 1 AND 9007199254740991),
        data_json TEXT NOT NULL CHECK(json_valid(data_json)), content_hash TEXT NOT NULL,
        source TEXT NOT NULL CHECK(source IN('manual','rule','import_local','ai_applied')),
        context_snapshot_json TEXT NOT NULL CHECK(json_valid(context_snapshot_json)),
        analysis_run_id TEXT, accepted_proposal_id TEXT,
        import_envelope_json TEXT CHECK(import_envelope_json IS NULL OR json_valid(import_envelope_json)),
        source_metadata_json TEXT NOT NULL CHECK(json_valid(source_metadata_json)),
        selected_fields_json TEXT NOT NULL CHECK(json_valid(selected_fields_json) AND json_type(selected_fields_json)='array'),
        process_metadata_json TEXT NOT NULL CHECK(json_valid(process_metadata_json) AND json_type(process_metadata_json)='array'),
        created_at TEXT NOT NULL,
        UNIQUE(lesson_plan_id,version), UNIQUE(id,lesson_plan_id,owner_id), UNIQUE(id,lesson_plan_id,owner_id,version),
        UNIQUE(accepted_proposal_id),
        FOREIGN KEY(lesson_plan_id,owner_id) REFERENCES lesson_plans(id,owner_id),
        FOREIGN KEY(analysis_run_id,owner_id) REFERENCES analysis_runs(id,owner_id),
        FOREIGN KEY(accepted_proposal_id,lesson_plan_id,owner_id) REFERENCES lesson_ai_proposals(id,lesson_plan_id,owner_id) DEFERRABLE INITIALLY DEFERRED,
        CHECK((source='import_local')=(import_envelope_json IS NOT NULL)),
        CHECK((source='ai_applied')=(accepted_proposal_id IS NOT NULL)),
        CHECK(source='ai_applied' OR (json_array_length(selected_fields_json)=0 AND json_array_length(process_metadata_json)=0)))""",
    """CREATE TABLE lesson_revision_reviews (
        revision_id TEXT PRIMARY KEY NOT NULL, lesson_plan_id TEXT NOT NULL, owner_id TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'unreviewed' CHECK(state IN('unreviewed','reviewed')),
        reviewed_at TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(revision_id,lesson_plan_id,owner_id) REFERENCES lesson_plan_revisions(id,lesson_plan_id,owner_id),
        CHECK((state='unreviewed' AND reviewed_at IS NULL) OR(state='reviewed' AND reviewed_at IS NOT NULL)))""",
    """CREATE TABLE lesson_generation_inputs (
        id TEXT PRIMARY KEY NOT NULL, lesson_plan_id TEXT NOT NULL, owner_id TEXT NOT NULL,
        job_id TEXT NOT NULL UNIQUE, base_revision_id TEXT NOT NULL,
        base_server_revision INTEGER NOT NULL CHECK(base_server_revision BETWEEN 1 AND 9007199254740991),
        analysis_run_id TEXT NOT NULL, class_id TEXT NOT NULL,
        input_hash TEXT NOT NULL, model_profile_id TEXT NOT NULL, model_fingerprint TEXT NOT NULL,
        frozen_json TEXT NOT NULL CHECK(json_valid(frozen_json)), created_at TEXT NOT NULL,
        UNIQUE(id,lesson_plan_id,owner_id,job_id),
        FOREIGN KEY(lesson_plan_id,owner_id) REFERENCES lesson_plans(id,owner_id),
        FOREIGN KEY(base_revision_id,lesson_plan_id,owner_id,base_server_revision) REFERENCES lesson_plan_revisions(id,lesson_plan_id,owner_id,version),
        FOREIGN KEY(analysis_run_id,owner_id) REFERENCES analysis_runs(id,owner_id),
        FOREIGN KEY(class_id,owner_id) REFERENCES classes(id,owner_id),
        FOREIGN KEY(job_id,owner_id) REFERENCES workflow_jobs(id,owner_id))""",
    """CREATE TABLE lesson_ai_proposals (
        id TEXT PRIMARY KEY NOT NULL, lesson_plan_id TEXT NOT NULL, owner_id TEXT NOT NULL,
        generation_input_id TEXT NOT NULL, job_id TEXT NOT NULL UNIQUE,
        base_revision_id TEXT NOT NULL, base_server_revision INTEGER NOT NULL,
        analysis_run_id TEXT NOT NULL, input_hash TEXT NOT NULL, model_fingerprint TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), created_at TEXT NOT NULL,
        UNIQUE(id,lesson_plan_id,owner_id),
        FOREIGN KEY(generation_input_id,lesson_plan_id,owner_id,job_id) REFERENCES lesson_generation_inputs(id,lesson_plan_id,owner_id,job_id),
        FOREIGN KEY(base_revision_id,lesson_plan_id,owner_id,base_server_revision) REFERENCES lesson_plan_revisions(id,lesson_plan_id,owner_id,version),
        FOREIGN KEY(analysis_run_id,owner_id) REFERENCES analysis_runs(id,owner_id),
        FOREIGN KEY(job_id,owner_id) REFERENCES workflow_jobs(id,owner_id))""",
    """CREATE TABLE lesson_proposal_decisions (
        proposal_id TEXT PRIMARY KEY NOT NULL, lesson_plan_id TEXT NOT NULL, owner_id TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN('applied','rejected')),
        selected_fields_json TEXT NOT NULL CHECK(json_valid(selected_fields_json) AND json_type(selected_fields_json)='array'),
        accepted_revision_id TEXT, created_at TEXT NOT NULL,
        FOREIGN KEY(proposal_id,lesson_plan_id,owner_id) REFERENCES lesson_ai_proposals(id,lesson_plan_id,owner_id),
        FOREIGN KEY(accepted_revision_id,lesson_plan_id,owner_id) REFERENCES lesson_plan_revisions(id,lesson_plan_id,owner_id) DEFERRABLE INITIALLY DEFERRED,
        CHECK((state='applied' AND accepted_revision_id IS NOT NULL AND json_array_length(selected_fields_json)>0) OR
              (state='rejected' AND accepted_revision_id IS NULL AND json_array_length(selected_fields_json)=0)))""",
    "CREATE INDEX ix_lesson_owner_updated ON lesson_plans(owner_id,updated_at,id)",
    "CREATE INDEX ix_lesson_revisions_order ON lesson_plan_revisions(lesson_plan_id,version)",
)

IMMUTABLE_TABLES = ("lesson_plan_revisions", "lesson_generation_inputs", "lesson_ai_proposals", "lesson_proposal_decisions")
IMMUTABLE_TRIGGERS = tuple(
    f"CREATE TRIGGER {table}_immutable_{verb.lower()} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT,'LESSON_FIXED_CONTENT'); END"
    for table in IMMUTABLE_TABLES for verb in ("UPDATE", "DELETE")
)
TRIGGERS = IMMUTABLE_TRIGGERS + (
    """CREATE TRIGGER lesson_plan_identity_fixed BEFORE UPDATE ON lesson_plans BEGIN
        SELECT CASE WHEN NEW.id IS NOT OLD.id OR NEW.owner_id IS NOT OLD.owner_id OR
          NEW.subject_id IS NOT OLD.subject_id OR NEW.class_id IS NOT OLD.class_id OR NEW.created_at IS NOT OLD.created_at
          THEN RAISE(ABORT,'LESSON_IDENTITY_FIXED') END;
        SELECT CASE WHEN (NEW.current_revision_id IS NOT OLD.current_revision_id AND NEW.revision<>OLD.revision+1) OR
          (NEW.current_revision_id IS OLD.current_revision_id AND NEW.revision<>OLD.revision)
          THEN RAISE(ABORT,'LESSON_CAS_INVALID') END;
        SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM lesson_plan_revisions r WHERE r.id=NEW.current_revision_id
          AND r.lesson_plan_id=NEW.id AND r.owner_id=NEW.owner_id AND r.version=NEW.revision)
          THEN RAISE(ABORT,'LESSON_POINTER_VERSION_INVALID') END;
    END""",
    """CREATE TRIGGER lesson_revision_sequence BEFORE INSERT ON lesson_plan_revisions BEGIN
        SELECT CASE WHEN NEW.version<>(SELECT coalesce(max(version),0)+1 FROM lesson_plan_revisions WHERE lesson_plan_id=NEW.lesson_plan_id)
          THEN RAISE(ABORT,'LESSON_VERSION_SEQUENCE') END;
        SELECT CASE WHEN json_extract(NEW.context_snapshot_json,'$.subjectId') IS NOT
          (SELECT subject_id FROM lesson_plans WHERE id=NEW.lesson_plan_id AND owner_id=NEW.owner_id) OR
          json_extract(NEW.context_snapshot_json,'$.classId') IS NOT
          (SELECT class_id FROM lesson_plans WHERE id=NEW.lesson_plan_id AND owner_id=NEW.owner_id)
          THEN RAISE(ABORT,'LESSON_CONTEXT_IDENTITY_INVALID') END;
        SELECT CASE WHEN json_extract(NEW.context_snapshot_json,'$.analysis.analysisRunId') IS NOT NEW.analysis_run_id
          THEN RAISE(ABORT,'LESSON_ANALYSIS_CONTEXT_INVALID') END;
        SELECT CASE WHEN NEW.source='ai_applied' AND NOT EXISTS(SELECT 1 FROM lesson_ai_proposals p
          WHERE p.id=NEW.accepted_proposal_id AND p.lesson_plan_id=NEW.lesson_plan_id AND p.owner_id=NEW.owner_id
          AND p.analysis_run_id=NEW.analysis_run_id AND p.base_server_revision=NEW.version-1
          AND EXISTS(SELECT 1 FROM lesson_plans l WHERE l.id=NEW.lesson_plan_id AND l.owner_id=NEW.owner_id
            AND l.current_revision_id=p.base_revision_id AND l.revision=p.base_server_revision)
          AND NOT EXISTS(SELECT 1 FROM lesson_proposal_decisions d WHERE d.proposal_id=p.id))
          THEN RAISE(ABORT,'LESSON_PROPOSAL_NOT_PENDING') END;
    END""",
    """CREATE TRIGGER lesson_input_lineage BEFORE INSERT ON lesson_generation_inputs BEGIN
        SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM workflow_jobs j WHERE j.id=NEW.job_id AND j.owner_id=NEW.owner_id
          AND j.kind='lesson_generation' AND j.input_hash=NEW.input_hash
          AND json_extract(j.model_snapshot_json,'$.fingerprint')=NEW.model_fingerprint
          AND json_extract(j.model_snapshot_json,'$.profileId')=NEW.model_profile_id)
          THEN RAISE(ABORT,'LESSON_JOB_LINEAGE_INVALID') END;
        SELECT CASE WHEN json_extract(NEW.frozen_json,'$.lessonPlanId') IS NOT NEW.lesson_plan_id OR
          json_extract(NEW.frozen_json,'$.ownerId') IS NOT NEW.owner_id OR
          json_extract(NEW.frozen_json,'$.baseRevisionId') IS NOT NEW.base_revision_id OR
          json_extract(NEW.frozen_json,'$.baseServerRevision') IS NOT NEW.base_server_revision OR
          json_extract(NEW.frozen_json,'$.analysisRunId') IS NOT NEW.analysis_run_id OR
          json_extract(NEW.frozen_json,'$.classId') IS NOT NEW.class_id
          THEN RAISE(ABORT,'LESSON_INPUT_CONTEXT_INVALID') END;
    END""",
    """CREATE TRIGGER lesson_proposal_lineage BEFORE INSERT ON lesson_ai_proposals BEGIN
        SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM lesson_generation_inputs i WHERE i.id=NEW.generation_input_id
          AND i.lesson_plan_id=NEW.lesson_plan_id AND i.owner_id=NEW.owner_id AND i.job_id=NEW.job_id
          AND i.base_revision_id=NEW.base_revision_id AND i.base_server_revision=NEW.base_server_revision
          AND i.analysis_run_id=NEW.analysis_run_id AND i.input_hash=NEW.input_hash AND i.model_fingerprint=NEW.model_fingerprint)
          THEN RAISE(ABORT,'LESSON_PROPOSAL_LINEAGE_INVALID') END;
    END""",
    """CREATE TRIGGER lesson_decision_applied_identity BEFORE INSERT ON lesson_proposal_decisions WHEN NEW.state='applied' BEGIN
        SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM lesson_plan_revisions r WHERE r.id=NEW.accepted_revision_id
          AND r.lesson_plan_id=NEW.lesson_plan_id AND r.owner_id=NEW.owner_id AND r.accepted_proposal_id=NEW.proposal_id
          AND r.source='ai_applied' AND json(r.selected_fields_json)=json(NEW.selected_fields_json))
          THEN RAISE(ABORT,'LESSON_DECISION_REVISION_INVALID') END;
    END""",
    """CREATE TRIGGER lesson_decision_reject_without_revision BEFORE INSERT ON lesson_proposal_decisions WHEN NEW.state='rejected' BEGIN
        SELECT CASE WHEN EXISTS(SELECT 1 FROM lesson_plan_revisions r WHERE r.accepted_proposal_id=NEW.proposal_id)
          THEN RAISE(ABORT,'LESSON_PROPOSAL_ALREADY_APPLIED') END;
    END""",
    """CREATE TRIGGER lesson_review_identity_fixed BEFORE UPDATE ON lesson_revision_reviews BEGIN
        SELECT CASE WHEN NEW.revision_id IS NOT OLD.revision_id OR NEW.lesson_plan_id IS NOT OLD.lesson_plan_id OR
          NEW.owner_id IS NOT OLD.owner_id OR NEW.created_at IS NOT OLD.created_at OR OLD.state='reviewed' OR NEW.state<>'reviewed'
          THEN RAISE(ABORT,'LESSON_REVIEW_FIXED') END;
    END""",
    "CREATE TRIGGER lesson_review_no_delete BEFORE DELETE ON lesson_revision_reviews BEGIN SELECT RAISE(ABORT,'LESSON_REVIEW_FIXED'); END",
)

MIGRATION = Migration("0010", "B5 owned immutable lesson revisions, frozen AI inputs and terminal decisions", TABLES + TRIGGERS)
REQUIRED_TABLES = ("lesson_plans", "lesson_plan_revisions", "lesson_revision_reviews", "lesson_generation_inputs", "lesson_ai_proposals", "lesson_proposal_decisions")
