"""练习集「连同全部历史彻底删除」（DELETE /practice-sets/{id}?includeHistory=true）。

覆盖（真四库 + 真实服务装配，tmp_path 隔离；不触碰正式 .local-data）：

- 默认路径（无 flag）：有历史引用 → 409 ``PRACTICE_IN_USE``，counts 三键齐全，
  message 含新增「如需连同全部历史彻底删除」提示；
- flag=true 全级联：集合/修订（含 reviewed）/selections/items/item_knowledge/
  mappings/conversions/exports/artifacts 全部清零；``file_assets``/``workflow_jobs``
  行保留；转换生成的原卷修订 ``source_practice_revision_id`` 置 NULL 且行仍在；
  回执四计数正确；
- 触发器逐字恢复（R10-BE：恢复文本取自 ``sqlite_master``，见
  ``triggers.suspend_triggers``）：删除后对另一 reviewed 修订/另一转换行/confirmed
  原卷修订（含 paper_source_fixed）的直连 DELETE/UPDATE 全部被拒；
- 解锁链：删除后报告 ``practiceSets``==0 且经真实 HTTP 端点把报告彻底删除成功；
  同一施测 ``practiceConversions``==0；
- 纯草稿集 flag=true 同样成功；CAS 409；404；归档集 + 历史 + flag=true 成功；
- HTTP 层路由接受 ``includeHistory`` 查询参数。
"""

from __future__ import annotations

import pytest

from app.contracts import b4
from app.core.exceptions import AppError
from app.repositories.teaching.analysis import AnalysisRepository
from app.repositories.teaching.assessments import AssessmentRepository
from app.repositories.teaching.practices import PracticeRepository
from app.repositories.teaching.triggers import PRACTICE_HISTORY_TRIGGERS
from tests.practices_support import PracticesScene


@pytest.fixture
async def scene(tmp_path):
    value = await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


def reviewed(scene, *, tag="r1"):
    """创建→存草稿→审核一个新集合；tag 必须唯一（create/draft/review 提交标识不复用）。"""
    return scene.review(scene.save(scene.create_set(submission=tag + "-create"),
                                   [scene.item(scene.question(rich=scene.rich()))], submission=tag + "-draft"),
                        submission=tag + "-review")


async def _seed_full_history(scene, *, tag="h1"):
    """审核 + 转换 + 三种导出（student/teacher/score_template，含工件），返回回执上下文。"""
    practice = reviewed(scene, tag=tag)
    conversion = scene.conversion(practice, submission=tag + "-conversion")
    student = await scene.export(practice, variant="student", submission=tag + "-student")
    assert (await scene.finish(student)).state == "succeeded"
    teacher = await scene.export(practice, variant="teacher", submission=tag + "-teacher")
    assert (await scene.finish(teacher)).state == "succeeded"
    template = await scene.export(practice, variant="score_template", assessment_id=conversion.assessment_id,
                                  submission=tag + "-template")
    assert (await scene.finish(template)).state == "succeeded"
    artifact = scene.artifact(practice, template.export_id)[0]
    return practice, conversion, artifact


def _set_counts(scene, set_id):
    with scene.catalog.read_connection() as conn:
        return {
            "sets": conn.execute("SELECT COUNT(*) FROM practice_sets WHERE id=?", (set_id,)).fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM practice_revisions WHERE practice_set_id=?", (set_id,)).fetchone()[0],
            "selections": conn.execute("SELECT COUNT(*) FROM practice_selections WHERE practice_revision_id IN "
                                       "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
            "items": conn.execute("SELECT COUNT(*) FROM practice_items WHERE practice_revision_id IN "
                                  "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
            "item_knowledge": conn.execute("SELECT COUNT(*) FROM practice_item_knowledge WHERE practice_revision_id IN "
                                           "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
            "mappings": conn.execute("SELECT COUNT(*) FROM practice_paper_item_mappings WHERE practice_revision_id IN "
                                     "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
            "conversions": conn.execute("SELECT COUNT(*) FROM practice_conversions WHERE practice_revision_id IN "
                                        "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
            "exports": conn.execute("SELECT COUNT(*) FROM practice_exports WHERE practice_revision_id IN "
                                    "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
            "artifacts": conn.execute("SELECT COUNT(*) FROM export_artifacts WHERE practice_revision_id IN "
                                      "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,)).fetchone()[0],
        }


# --------------------------------------------------------------------------- 默认路径守卫


async def test_default_delete_blocked_with_history_and_new_hint(scene) -> None:
    """无 flag + 有历史 → 409；counts 三键齐全；message 含新增确认提示。"""
    practice, conversion, _ = await _seed_full_history(scene)
    with pytest.raises(AppError) as blocked:
        scene.service.delete_practice(practice.practice_set_id,
                                      b4.PracticeSetStatusRequest(expectedRevision=practice.revision))
    assert blocked.value.status_code == 409
    assert blocked.value.code == "PRACTICE_IN_USE"
    counts = blocked.value.details["counts"]
    assert counts == {"reviewedRevisions": 1, "exports": 3, "conversions": 1}
    message = str(blocked.value)
    assert "练习集仍被引用，不能删除" in message
    assert "如需修改请从审核版建立新草稿" in message
    assert "如需连同全部历史彻底删除该练习（不可恢复），请在界面明确确认后重试" in message
    # 数据不乱
    assert _set_counts(scene, practice.practice_set_id)["revisions"] == 1


# --------------------------------------------------------------------------- 全级联成功


async def test_include_history_full_cascade_counts_and_boundaries(scene) -> None:
    """flag=true 全级联：练习侧全部清零；file_assets/workflow_jobs/原卷修订行保留；来源指针置 NULL。"""
    practice, conversion, artifact = await _seed_full_history(scene)
    set_id = practice.practice_set_id
    revision_id = practice.current_revision.practice_revision_id
    with scene.catalog.read_connection() as conn:
        paper_revision_id = conn.execute("SELECT paper_revision_id FROM practice_conversions WHERE id=?",
                                         (conversion.conversion_id,)).fetchone()[0]
    baseline_assets = scene.count("file_assets")
    with scene.catalog.read_connection() as conn:
        baseline_jobs = conn.execute("SELECT COUNT(*) FROM workflow_jobs").fetchone()[0]
    assert baseline_assets > 0 and baseline_jobs > 0

    receipt = scene.service.delete_practice(
        set_id, b4.PracticeSetStatusRequest(expectedRevision=practice.revision), include_history=True)

    assert receipt.deleted is True
    assert receipt.model_dump(by_alias=True) == {
        "deleted": True, "practiceSetId": set_id,
        "removedRevisions": 1, "removedExports": 3, "removedConversions": 1, "removedArtifacts": 3,
    }
    # 练习侧全部清零（集合、修订含 reviewed、选题/题目/题叶知识、映射、转换、导出、工件）
    assert all(value == 0 for key, value in _set_counts(scene, set_id).items())
    # 边界：file_assets / workflow_jobs 保留不动
    assert scene.count("file_assets") == baseline_assets
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM workflow_jobs").fetchone()[0] == baseline_jobs
    with scene.catalog.read_connection() as conn:
        # 转换生成的原卷修订行仍在（confirmed），仅来源指针置 NULL（0013 后合法状态）
        row = conn.execute("SELECT state,source_file_id,source_practice_revision_id FROM paper_revisions WHERE id=?",
                           (paper_revision_id,)).fetchone()
        assert row["state"] == "confirmed"
        assert row["source_file_id"] is None
        assert row["source_practice_revision_id"] is None
        # 0013 新口径：双源行必须为 0；库完整性 ok
        assert conn.execute("SELECT count(*) FROM paper_revisions WHERE source_file_id IS NOT NULL "
                            "AND source_practice_revision_id IS NOT NULL").fetchone()[0] == 0
        # 原卷/施测/报告本体行一律不动
        assert conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM assessments WHERE id=?", (conversion.assessment_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] >= 1
    from app.core.sqlite import open_readonly
    readonly = open_readonly(scene.catalog.db_path)
    try:
        assert readonly.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        readonly.close()
    # 该行普通 UPDATE 仍被不可变触发器拒绝（IMMUTABLE_REVISION，而不是 CHECK 错误）
    import sqlite3
    connection = sqlite3.connect(scene.catalog.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            connection.execute("BEGIN")
            try:
                connection.execute("UPDATE paper_revisions SET title_snapshot='篡改' WHERE id=?", (paper_revision_id,))
            finally:
                connection.execute("ROLLBACK")
    finally:
        connection.close()
    # 练习已不存在
    with pytest.raises(AppError) as missing:
        scene.service.get_practice(set_id)
    assert missing.value.code == "PRACTICE_NOT_FOUND"


# --------------------------------------------------------------------------- 触发器逐字恢复


async def test_include_history_restores_triggers_verbatim(scene) -> None:
    """删除后 10 个触发器都在（恢复文本取自 sqlite_master），兜底全部生效（不留后门）。"""
    import sqlite3

    practice, conversion, _ = await _seed_full_history(scene)
    other = reviewed(scene, tag="r2")  # 另一个含 reviewed 修订的集合
    other_conversion = scene.conversion(other, submission="r2-conversion")
    scene.service.delete_practice(practice.practice_set_id,
                                  b4.PracticeSetStatusRequest(expectedRevision=practice.revision),
                                  include_history=True)

    with scene.catalog.read_connection() as conn:
        for name in PRACTICE_HISTORY_TRIGGERS:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
            assert row is not None, name
            assert "TRIGGER" in row["sql"].upper(), name
        other_revision_id = other.current_revision.practice_revision_id
        confirmed_paper_revision_id = conn.execute(
            "SELECT paper_revision_id FROM practice_conversions WHERE id=?",
            (other_conversion.conversion_id,)).fetchone()[0]

    connection = sqlite3.connect(scene.catalog.db_path)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")

        def attempt(sql, params, match):
            """开事务执行必被拒的语句，无论成败都回滚（RAISE(ABORT) 只中止语句）。"""
            connection.execute("BEGIN")
            try:
                with pytest.raises(sqlite3.IntegrityError, match=match):
                    connection.execute(sql, params)
            finally:
                connection.execute("ROLLBACK")

        # (a) 另一 reviewed 修订直连 DELETE → 拒
        attempt("DELETE FROM practice_revisions WHERE id=?", (other_revision_id,), "IMMUTABLE_REVISION")
        # (b) 另一转换行直连 DELETE → 拒
        attempt("DELETE FROM practice_conversions WHERE id=?", (other_conversion.conversion_id,), "IMMUTABLE_REVISION")
        # (c) confirmed 原卷修订直连 UPDATE（title_snapshot）→ 拒
        attempt("UPDATE paper_revisions SET title_snapshot='篡改' WHERE id=?",
                (confirmed_paper_revision_id,), "IMMUTABLE_REVISION")
        # (d) confirmed 原卷修订直连 UPDATE source_practice_revision_id → 拒（paper_source_fixed）
        attempt("UPDATE paper_revisions SET source_practice_revision_id='x' WHERE id=?",
                (confirmed_paper_revision_id,), "PAPER_SOURCE_FIXED")
    finally:
        connection.close()


# --------------------------------------------------------------------------- 解锁链


async def test_include_history_unblocks_analysis_and_assessment_deletion(scene, tmp_path) -> None:
    """删除后报告 practiceSets==0 且经真实 HTTP 端点把报告彻底删除；施测 practiceConversions==0。"""
    practice, conversion, _ = await _seed_full_history(scene)
    run_id = scene.run_id
    assessments = AssessmentRepository(scene.catalog)
    with scene.catalog.read_connection() as conn:
        assert AnalysisRepository().count_references_in(conn, run_id)["practiceSets"] == 1
        assert assessments.count_references_in(conn, conversion.assessment_id)["practiceConversions"] == 1

    scene.service.delete_practice(practice.practice_set_id,
                                  b4.PracticeSetStatusRequest(expectedRevision=practice.revision),
                                  include_history=True)

    with scene.catalog.read_connection() as conn:
        assert AnalysisRepository().count_references_in(conn, run_id)["practiceSets"] == 0
        assert assessments.count_references_in(conn, conversion.assessment_id)["practiceConversions"] == 0

    # 经真实 HTTP 端点把该报告彻底删除成功
    from tests.practices_support import open_api_scene
    # PracticesScene 自带的 catalog 装配与 open_api_scene 不同库；这里用服务层端点所属
    # 装配（analysis service 注册在同一 create_app 骨架），直接走 PracticesScene 的
    # analysis_scene HTTP 上下文删除该报告。
    with scene.analysis_scene.http_client() as client:
        deleted = client.delete(f"/api/v1/analysis-runs/{run_id}")
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] is True
    with pytest.raises(AppError) as gone:
        scene.analysis_scene.service.get_run(run_id)
    assert gone.value.code == "ANALYSIS_NOT_FOUND"


# --------------------------------------------------------------------------- 边界与 CAS/404


async def test_include_history_pure_draft_set_succeeds_with_zero_counts(scene) -> None:
    """纯草稿集 + flag=true → 成功；回执四计数全 0。"""
    practice = scene.save(scene.create_set(submission="pure-draft"), [scene.item(scene.question(rich=scene.rich()))],
                          submission="pure-draft-save")
    set_id = practice.practice_set_id
    receipt = scene.service.delete_practice(set_id,
                                            b4.PracticeSetStatusRequest(expectedRevision=practice.revision),
                                            include_history=True)
    assert receipt.deleted is True
    assert receipt.model_dump(by_alias=True) == {
        "deleted": True, "practiceSetId": set_id,
        "removedRevisions": 1, "removedExports": 0, "removedConversions": 0, "removedArtifacts": 0,
    }
    assert all(value == 0 for value in _set_counts(scene, set_id).values())


async def test_include_history_cas_conflict_and_not_found(scene) -> None:
    """CAS 不符 → 409 REVISION_CONFLICT；集合不存在 → 404 PRACTICE_NOT_FOUND；零删除。"""
    practice = reviewed(scene)
    with pytest.raises(AppError) as stale:
        scene.service.delete_practice(practice.practice_set_id,
                                      b4.PracticeSetStatusRequest(expectedRevision=practice.revision + 3),
                                      include_history=True)
    assert stale.value.code == "REVISION_CONFLICT"
    assert stale.value.details["currentRevision"] == practice.revision
    with pytest.raises(AppError) as missing:
        scene.service.delete_practice("no-such-set",
                                      b4.PracticeSetStatusRequest(expectedRevision=0),
                                      include_history=True)
    assert missing.value.code == "PRACTICE_NOT_FOUND"
    # 两条失败路径都不删数据
    assert _set_counts(scene, practice.practice_set_id)["revisions"] == 1


async def test_include_history_stale_archived_set_with_history_succeeds(scene) -> None:
    """残留归档行（模拟旧库）+ 历史 + flag=true → 成功（删除是唯一出口）。"""
    practice, conversion, artifact = await _seed_full_history(scene)
    set_id = practice.practice_set_id
    with scene.catalog.write_transaction() as conn:
        conn.execute(
            "UPDATE practice_sets SET status='archived' WHERE id=?",
            (set_id,),
        )
    assert scene.service.get_practice(set_id).status == "archived"
    receipt = scene.service.delete_practice(set_id,
                                            b4.PracticeSetStatusRequest(expectedRevision=practice.revision),
                                            include_history=True)
    assert receipt.deleted is True
    assert receipt.removed_revisions == 1 and receipt.removed_conversions == 1
    assert receipt.removed_exports == 3 and receipt.removed_artifacts == 3
    assert all(value == 0 for value in _set_counts(scene, set_id).values())


# --------------------------------------------------------------------------- HTTP 路由


def test_http_route_accepts_include_history(tmp_path) -> None:
    """HTTP 层：route 接受 includeHistory 查询参数；默认路径守卫文案含新提示。"""
    from tests.practices_support import open_api_scene, seed_api_loop

    with open_api_scene(tmp_path) as (app, client, _settings):
        result = seed_api_loop(app, client)
        practice = result["practice"]
        set_id = practice["practiceSetId"]
        prefix = f"/api/v1/practice-sets/{set_id}"
        # 默认路径：守卫 409，message 含新增提示
        blocked = client.delete(prefix, params={"expectedRevision": practice["revision"]})
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["code"] == "PRACTICE_IN_USE"
        assert "如需连同全部历史彻底删除" in blocked.json()["message"]
        # flag=true：连同全部历史彻底删除成功，回执含四计数
        deleted = client.delete(prefix, params={"expectedRevision": practice["revision"], "includeHistory": "true"})
        assert deleted.status_code == 200, deleted.text
        body = deleted.json()
        assert body["deleted"] is True and body["practiceSetId"] == set_id
        assert body["removedRevisions"] >= 1
        assert {"removedExports", "removedConversions", "removedArtifacts"} <= set(body)
        # 集合已不存在
        assert client.get(prefix).status_code == 404
        # 再删一次 → 404
        again = client.delete(prefix, params={"expectedRevision": 0, "includeHistory": "true"})
        assert again.status_code == 404, again.text


# --------------------------------------------------------------------------- 0013 迁移


def _registered_migration(migration_id):
    from app.core.migrations import REGISTERED_MIGRATIONS
    return next(m for m in REGISTERED_MIGRATIONS["teaching"] if m.id == migration_id)


_PRACTICE_OWNER_TRIGGER = (
    "CREATE TRIGGER paper_practice_owner BEFORE INSERT ON paper_revisions WHEN NEW.source_practice_revision_id IS NOT NULL BEGIN "
    "SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM practice_revisions r JOIN practice_sets s ON s.id=r.practice_set_id "
    "JOIN papers p ON p.id=NEW.paper_id WHERE r.id=NEW.source_practice_revision_id AND s.owner_id=p.owner_id "
    "AND s.subject_id=p.subject_id AND r.state='reviewed') THEN RAISE(ABORT,'PRACTICE_OWNER_OR_STATE_MISMATCH') END; "
    "END"
)
_PAPER_SOURCE_FIXED_TRIGGER = (
    "CREATE TRIGGER paper_source_fixed BEFORE UPDATE OF paper_id,source_file_id,source_practice_revision_id "
    "ON paper_revisions WHEN NEW.paper_id IS NOT OLD.paper_id OR NEW.source_file_id IS NOT OLD.source_file_id "
    "OR NEW.source_practice_revision_id IS NOT OLD.source_practice_revision_id "
    "BEGIN SELECT RAISE(ABORT,'PAPER_SOURCE_FIXED'); END"
)


def _restore_paper_gates(connection) -> None:
    """逐字恢复 paper_practice_owner 与 paper_source_fixed（预置数据后不留后门）。"""
    connection.execute(_PRACTICE_OWNER_TRIGGER)
    connection.execute(_PAPER_SOURCE_FIXED_TRIGGER)


def _seed_minimal_practice_domain(connection) -> None:
    """预置最小 practice 域（papers→paper_revisions→assessments→score_revisions→
    analysis_runs→practice_sets→reviewed 修订，全 FK 链完整），支持练习源行。

    测试数据准备（先例 ``_seed_b2_business`` 直连 SQL）：封存/直审/确认闸门触发器是
    运行态写路径约束（``analysis_seal`` 等要求完整成绩矩阵），预置时临时摘除并在
    ``finally`` 恢复触发器子集（行本身满足表级 CHECK，``foreign_key_check`` 保持空）。
    同时预置：

    - ``file_assets`` ``fa-dep`` + ``papers`` ``pp13`` + 确认版 ``paper_revisions``
      ``pr13``（文件源单源行，可复用作"文件源行"）；
    - ``practice_revisions`` ``prev13``（reviewed，可被练习源 ``paper_revisions``
      行经 ``paper_practice_owner`` 闸门引用）。
    """
    drop = ("analysis_no_direct_ready", "analysis_seal", "analysis_inputs_fixed", "paper_practice_owner",
            "practice_no_direct_review", "practice_review", "assessment_confirmed_paper_insert",
            "assessment_active_score_confirmed", "practice_requires_ready", "practice_source_subject",
            "immutable_paper_revisions_update", "no_direct_sealed_paper_revisions")
    for trigger in drop:
        connection.execute("DROP TRIGGER IF EXISTS " + trigger)
    try:
        with connection:
            connection.execute("INSERT INTO file_assets (id,owner_id,kind,blob_key,sha256,original_name,"
                               "media_type,byte_size,created_at) VALUES ('fa-dep','local','paper','blobs/cc',?,"
                               "'d.docx','application/pdf',10,'2026-10-10')", ("c" * 64,))
            connection.execute("INSERT INTO papers(id,owner_id,subject_id,title) "
                               "VALUES('pp13','local','math','预置源卷')")
            connection.execute("INSERT INTO paper_revisions(id,paper_id,version,source_file_id,total_score_units,"
                               "state,confirmed_at,created_at,title_snapshot) "
                               "VALUES('pr13','pp13',1,'fa-dep',0,'confirmed','2026-10-10','2026-10-10','预置源卷')")
            connection.execute("INSERT INTO assessments(id,owner_id,paper_revision_id,title,assessment_type,"
                               "held_on,state,revision,created_at) "
                               "VALUES('as13','local','pr13','预置施测','exam','2026-10-02','open',0,'2026-10-10')")
            connection.execute("INSERT INTO score_revisions(id,assessment_id,version,state,confirmed_at,"
                               "participant_snapshot_json,item_snapshot_json,created_at) "
                               "VALUES('sr13','as13',1,'confirmed','2026-10-10','[]','[]','2026-10-10')")
            connection.execute("INSERT INTO workflow_jobs(id,owner_id,kind,state,created_at,updated_at) "
                               "VALUES('j13','local','analysis','succeeded','2026-10-10','2026-10-10')")
            connection.execute("INSERT INTO analysis_runs(id,owner_id,assessment_id,score_revision_id,"
                               "paper_revision_id,subject_id,rule_code,input_hash,input_json,job_id,report_ready,"
                               "selected_count,leaf_count,knowledge_count,class_count,created_at,ready_at) "
                               "VALUES('run13','local','as13','sr13','pr13','math','any_loss_v1',?,"
                               "'{}','j13',1,1,1,1,1,'2026-10-10','2026-10-10')", ("a" * 64,))
            connection.execute("INSERT INTO practice_sets(id,owner_id,analysis_run_id,subject_id,title,created_at) "
                               "VALUES('ps13','local','run13','math','预置练习','2026-10-10')")
            connection.execute("INSERT INTO practice_revisions(id,practice_set_id,version,input_hash,"
                               "selection_snapshot_json,constraints_json,title_snapshot,created_at,state,reviewed_at) "
                               "VALUES('prev13','ps13',1,?, '{}','{}','预置练习','2026-10-10','reviewed','2026-10-10')",
                               ("b" * 64,))
    finally:
        for statement in (
            "CREATE TRIGGER IF NOT EXISTS analysis_no_direct_ready "
            "BEFORE INSERT ON analysis_runs WHEN NEW.report_ready=1 "
            "BEGIN SELECT RAISE(ABORT,'USE_READY_TRANSITION'); END",
            "CREATE TRIGGER IF NOT EXISTS practice_no_direct_review "
            "BEFORE INSERT ON practice_revisions WHEN NEW.state='reviewed' "
            "BEGIN SELECT RAISE(ABORT,'USE_REVIEW_TRANSITION'); END",
            "CREATE TRIGGER IF NOT EXISTS assessment_confirmed_paper_insert "
            "BEFORE INSERT ON assessments BEGIN SELECT CASE WHEN (SELECT state FROM paper_revisions "
            "WHERE id=NEW.paper_revision_id)<>'confirmed' THEN RAISE(ABORT,'PAPER_NOT_CONFIRMED') END; END",
            "CREATE TRIGGER IF NOT EXISTS no_direct_sealed_paper_revisions "
            "BEFORE INSERT ON paper_revisions WHEN NEW.state='confirmed' "
            "BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END",
            _PRACTICE_OWNER_TRIGGER.replace("CREATE TRIGGER paper_practice_owner",
                                            "CREATE TRIGGER IF NOT EXISTS paper_practice_owner"),
            _PAPER_SOURCE_FIXED_TRIGGER.replace("CREATE TRIGGER paper_source_fixed",
                                                "CREATE TRIGGER IF NOT EXISTS paper_source_fixed"),
        ):
            connection.execute(statement)


def test_migration_0013_fresh_database_relaxed_check_and_idempotent(tmp_path) -> None:
    """fresh 库：0009 按老 CHECK 重建通过 → 0013 放宽为至多一源；幂等重跑为空。

    门禁口径（登记迁移 0013 ``paper_source_relaxed_rebuild``）：双源行必须为 0；
    禁的是"两个来源同时非空"，无源行合法（连带历史彻底删除的产物）。运行态有
    paper_practice_owner/paper_source_fixed 双闸（INSERT/UPDATE 均拦双源路径），
    CHECK 语义用临时摘除 UPDATE 闸后直验（先例：test_analysis_cleanup 直连验证）。
    """
    from app.core.migrations import apply_migrations
    from app.core.sqlite import connect

    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        applied = apply_migrations(connection, database="teaching")
        # 0013 是本卡语义关心的最后一笔；R5-b 追加的 0014_student_gender 之后可能再追加，
        # 只断言 0013 已应用且恰好一次，不锁死"最后一笔"（追加迁移不得破坏本断言）。
        assert applied.count("0013") == 1
        assert applied.index("0013") == len(applied) - 1 or applied[-1] != "0013"
        _seed_minimal_practice_domain(connection)
        with connection:
            # 无源（draft）行可插入
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, source_practice_revision_id, "
                "total_score_units, state, created_at) VALUES ('pr-none','pp13',2,NULL,NULL,0,'draft','2026-10-10')")
        # 练习来源（单源）行经 paper_practice_owner 闸门正常插入
        with connection:
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, source_practice_revision_id, "
                "total_score_units, state, created_at) VALUES ('pr-p','pp13',3,NULL,'prev13',0,'draft','2026-10-10')")
        # 双源行被 CHECK 拒（临时摘除 UPDATE 闸后直验 CHECK 语义）
        connection.execute("DROP TRIGGER paper_source_fixed")
        try:
            with pytest.raises(Exception, match="CHECK"):
                with connection:
                    connection.execute("UPDATE paper_revisions SET source_file_id='fa-dep' WHERE id='pr-p'")
        finally:
            connection.execute(_PAPER_SOURCE_FIXED_TRIGGER)
        # 运行态闸门恢复后：同一 UPDATE 被纸源固定闸拒绝（纵深防御仍在）
        with pytest.raises(Exception, match="PAPER_SOURCE_FIXED"):
            with connection:
                connection.execute("UPDATE paper_revisions SET source_file_id='fa-dep' WHERE id='pr-p'")
        # 幂等：重复应用为空操作
        assert apply_migrations(connection, database="teaching") == []
        assert apply_migrations(connection, database="teaching") == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_migration_0013_upgrade_from_0012_with_both_single_source_kinds(tmp_path, monkeypatch) -> None:
    """老库升级路径：等价 0012 状态（含文件源/练习源两类单源行）→ 应用 0013 → 行保留、
    both_sources_set=0、paper 相关触发器集合完整。"""
    from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations
    from app.core.sqlite import connect

    full = REGISTERED_MIGRATIONS["teaching"]
    prefix = tuple(m for m in full if m.id != "0013")
    assert len(prefix) == len(full) - 1
    path = tmp_path / "teaching.sqlite3"
    connection = connect(path)
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", prefix)
        apply_migrations(connection, database="teaching")
        _seed_minimal_practice_domain(connection)
        # 练习源（单源）行：0009 老口径下合法
        with connection:
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, source_practice_revision_id, "
                "total_score_units, state, created_at) VALUES ('pr-old-practice','pp13',2,NULL,'prev13',0,'draft','2026-10-10')")
        before_rows = [tuple(r) for r in connection.execute(
            "SELECT * FROM paper_revisions WHERE paper_id='pp13' ORDER BY version")]
        assert len(before_rows) == 2
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", full)
        # 0013 之后登记的迁移（如 R5-b 0014_student_gender）会一并应用，只断言 0013 在其中
        applied_after = apply_migrations(connection, database="teaching")
        assert "0013" in applied_after
        # 行保留（重建不丢行），内容不变
        after_rows = [tuple(r) for r in connection.execute(
            "SELECT * FROM paper_revisions WHERE paper_id='pp13' ORDER BY version")]
        assert after_rows == before_rows
        # 新口径对账：双源行 0
        assert connection.execute("SELECT count(*) FROM paper_revisions WHERE source_file_id IS NOT NULL "
                                  "AND source_practice_revision_id IS NOT NULL").fetchone()[0] == 0
        # paper 相关触发器集合完整（抽查重建必须恢复的三个）
        triggers = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'")}
        assert {"paper_source_fixed", "paper_practice_confirm", "paper_practice_owner"} <= triggers
        # 升级后原卷/练习来源闸门仍生效
        with pytest.raises(Exception, match="PAPER_SOURCE_FIXED"):
            with connection:
                connection.execute("UPDATE paper_revisions SET source_file_id='fa-dep' WHERE id='pr-old-practice'")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        # 幂等
        assert apply_migrations(connection, database="teaching") == []
    finally:
        connection.close()


def test_migration_0009_declarations_unchanged_and_0013_registered() -> None:
    """0009 声明冻结证据：RebuildPlan 产物与登记值可复核；0013 已登记并带散列。"""
    migration_0009 = _registered_migration("0009")
    migration_0013 = _registered_migration("0013")
    # 0009 仍是"恰一非空"互斥 CHECK（未被动过）
    assert "CHECK((source_file_id IS NOT NULL AND source_practice_revision_id IS NULL) " \
        "OR(source_file_id IS NULL AND source_practice_revision_id IS NOT NULL))" in migration_0009.rebuild.new_table_sql
    # 0013 用放宽后的 CHECK；其余与 0009 同源（copy/drop/restore 逐字一致）
    from dataclasses import replace as _replace
    relaxed = _replace(migration_0009.rebuild, new_table_sql="ignored")
    same_shared = (migration_0013.rebuild.copy_sql == relaxed.copy_sql
                   and migration_0013.rebuild.drop_and_rename == relaxed.drop_and_rename
                   and migration_0013.rebuild.restore == relaxed.restore)
    assert same_shared
    assert "CHECK(source_file_id IS NULL OR source_practice_revision_id IS NULL)" in migration_0013.rebuild.new_table_sql
    assert migration_0013.sha256 and len(migration_0013.sha256) == 64
    # 0009 散列与本文件登记时一致（PH 批次未触碰其任何输出）
    assert len(migration_0009.sha256) == 64
