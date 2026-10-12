import json
import sqlite3
import pytest
from app.contracts.b4 import NoteRequest
from app.core.exceptions import AppError
from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations
from app.core.sqlite import connect
from app.services.analysis.service import AnalysisService
from tests.analysis_support import AnalysisScene


async def test_literal_full_report_and_rich_evidence(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    report = scene.service.read_ready_report(receipt.run_id)
    rows = {(r["participant"]["name"], r["knowledgePoint"]["knowledgePointId"]): r for r in report["students"]}
    expected = {("A", "k1"): ("needs_consolidation", False, 900), ("A", "k2"): ("needs_consolidation", False, 900),
                ("B", "k1"): ("full_credit", False, None), ("B", "k2"): ("incomplete", True, None),
                ("C", "k1"): ("no_evidence", True, None), ("C", "k2"): ("no_evidence", True, None),
                ("D", "k1"): ("needs_consolidation", False, 800), ("D", "k2"): ("full_credit", False, 800)}
    assert {k: (v["observation"], v["informationIncomplete"], v["totalScoreUnits"]) for k, v in rows.items()} == expected
    classes = {r["knowledgePoint"]["knowledgePointId"]: r for r in report["classes"]}
    assert (classes["k1"]["numerator"], classes["k1"]["denominator"], classes["k1"]["ratio"]) == (2, 3, 2 / 3)
    assert (classes["k2"]["numerator"], classes["k2"]["denominator"], classes["k2"]["ratio"]) == (1, 3, 1 / 3)
    assert classes["k1"]["incompleteCount"] == 1 and classes["k2"]["incompleteCount"] == 2
    # 契约升级（名称优先）：读路径按同 owner JOIN classes.name 补展示名；classNameNote 兼容保留
    assert all(p["className"] == "现班名" and p["classNameNote"] == "该成绩未记录班名" for p in report["participants"])
    evidence = scene.service.list_report_rows(receipt.run_id, "evidence", limit=200)
    assert evidence.total == len(evidence.items) == 12
    zero = [e for e in evidence.items if e.score_units == 0]
    assert len(zero) == 1 and zero[0].status == "recorded"
    assert len([e for e in evidence.items if e.status == "absent"]) == 3
    assert all(e.content["stemBlocks"] == scene.rich["stemBlocks"] and e.shared_materials == scene.rich["sharedMaterials"] and e.assets == scene.rich["assets"] and e.content["sourceBlocks"][0]["blockId"] == "shared" for e in evidence.items)
    assert all(e.practice_revision_id is None and e.practice_item_id is None for e in evidence.items)
    assert len(report["originalQuestionContents"]) == 3 and report["originalQuestionRevisionIds"] == []
    assert all("type" not in c for c in report["originalQuestionContents"])
    assert "participantId" not in str(report["originalQuestionContents"])
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE classes SET name='后来班名' WHERE id='class'")
        conn.execute("UPDATE students SET name='后来名字' WHERE id='s000'")
        conn.execute("UPDATE papers SET title='后来卷名',status='archived' WHERE id='paper'")
        conn.execute("UPDATE assessments SET active_score_revision_id=NULL WHERE id='assessment'")
    # 固定事实不被改名影响；className 例外：名称优先读路径跟随当前班名（本卡预期变更）。
    renamed = scene.service.read_ready_report(receipt.run_id)
    for before, after in zip(report["participants"], renamed["participants"]):
        after.pop("className"), before.pop("className")
    assert renamed == report
    assert all(p["className"] == "后来班名" for p in scene.service.read_ready_report(receipt.run_id)["participants"])
    # A separately fixed paper that actually recorded its type retains it. Only
    # unknown source types are omitted; no other placeholder or inference.
    known_scene = AnalysisScene(tmp_path / "known-source", known_type="short_answer")
    known = await known_scene.ready()
    assert all(c["type"] == "short_answer" for c in known_scene.service.read_ready_report(known.run_id)["originalQuestionContents"])


@pytest.mark.parametrize("ids,code", [(["p000", "p000"], "DUPLICATE_PARTICIPANT"), (["missing"], "PARTICIPANT_NOT_IN_REVISION")])
async def test_invalid_selection_has_position_and_no_half_accept(tmp_path, ids, code):
    scene = AnalysisScene(tmp_path)
    with pytest.raises(AppError) as failure:
        await scene.accept(ids=ids)
    assert failure.value.status_code == 422 and failure.value.details["issues"][0]["code"] == code
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == scene.count("command_submissions") == 0


async def test_replay_precedes_asset_io_and_same_input_reuses_failed_job(tmp_path, monkeypatch):
    scene = AnalysisScene(tmp_path)
    first = await scene.accept()
    monkeypatch.setattr(scene.service, "_verify_assets", lambda _: (_ for _ in ()).throw(AssertionError("must replay first")))
    replay = await scene.accept(ids=list(reversed(scene.participant_ids)))
    assert replay.replayed and replay.run_id == first.run_id and replay.job == first.job
    with pytest.raises(AppError) as failure:
        await scene.accept(ids=scene.participant_ids[:1])
    assert failure.value.code == "SUBMISSION_CONFLICT"
    monkeypatch.undo()
    lease = scene.store.claim(first.job.job_id)
    scene.store.fail_if_current_lease(first.job.job_id, lease, code="TEST_FAIL", message="故障")
    reused = await scene.accept(submission="s2")
    assert reused.reused and not reused.replayed and reused.run_id == first.run_id and reused.job.state == "failed"
    assert len(scene.engine.accepted) == 1
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == 1


async def test_accept_fault_rolls_back_run_job_and_submission(tmp_path, monkeypatch):
    scene = AnalysisScene(tmp_path)
    original = scene.service.repo.create_in
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected accept failure")
    monkeypatch.setattr(scene.service.repo, "create_in", fail)
    with pytest.raises(RuntimeError):
        await scene.accept()
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == scene.count("command_submissions") == 0


async def test_notes_ready_append_replay_and_foreign_filters(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError, match="尚未完成"):
        scene.service.list_report_rows(receipt.run_id, "evidence")
    with pytest.raises(AppError) as notready:
        scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n0", note="先备注"))
    assert notready.value.code == "REPORT_NOT_READY"
    await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    one = scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n1", participantId="p000", knowledgePointId="k1", note="待教师判断具体错因"))
    assert scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n1", participantId="p000", knowledgePointId="k1", note="待教师判断具体错因")).replayed
    scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n2", note="追加记录"))
    assert scene.service.list_notes(receipt.run_id).total == 2
    for kwargs in ({"class_id": "other"}, {"participant_id": "other"}, {"knowledge_point_id": "other"}):
        with pytest.raises(AppError) as failed:
            scene.service.list_report_rows(receipt.run_id, "students", **kwargs)
        assert failed.value.code == "ANALYSIS_FILTER_INVALID"
    with pytest.raises(AppError) as blank:
        scene.service.add_note(receipt.run_id, NoteRequest(submissionId="blank", note="  "))
    assert blank.value.status_code == 422
    with pytest.raises(AppError) as owner:
        scene.service.read_ready_report(receipt.run_id, owner_id="other")
    assert owner.value.status_code == 404
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
        with scene.catalog.write_transaction() as conn:
            conn.execute("UPDATE analysis_teacher_notes SET note='rewrite' WHERE id=?", (one.note_id,))


# --------------------------------------------------------------------------- 名称优先（读路径补班名）


async def test_class_name_prefers_real_name_and_null_when_missing(tmp_path):
    """契约升级：详情/四个报告视图的班名走“名称优先”——同 owner JOIN classes.name 实时补名，
    班名缺失才 null；冻结事实（input_json/payload_json）不被改写，班名改名后读取即时生效。"""
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    # 详情视图：班名来自 JOIN（种子班名为「现班名」）
    view = scene.service.get_run(receipt.run_id)
    assert all(p.class_name == "现班名" for p in view.participants)
    # 报告视图：classes 行补名，students/evidence 行内 participant 补名
    classes = scene.service.list_report_rows(receipt.run_id, "classes").items
    assert all(row.class_name == "现班名" for row in classes)
    students = scene.service.list_report_rows(receipt.run_id, "students").items
    assert all(row.participant.class_name == "现班名" for row in students)
    evidence = scene.service.list_report_rows(receipt.run_id, "evidence").items
    assert all(row.participant.class_name == "现班名" for row in evidence)
    # 改名后读取即时生效（不回写快照）；归档班仍可读
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE classes SET name='新班名',status='archived' WHERE id='class'")
    assert all(p.class_name == "新班名" for p in scene.service.get_run(receipt.run_id).participants)
    # 班级行被物理删除（旧库/异常数据）：读路径得 null，不伪造名称、不抛错
    raw = connect(scene.catalog.db_path)
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("DELETE FROM classes WHERE id='class'")
    finally:
        raw.close()
    view = scene.service.get_run(receipt.run_id)
    assert all(p.class_name is None for p in view.participants)
    classes = scene.service.list_report_rows(receipt.run_id, "classes").items
    assert all(row.class_name is None and row.class_name_note == "该成绩未记录班名" for row in classes)
    # 冻结事实未被改写：input_json 里的 participant 仍无 className 值（只读补名不落库）
    with scene.catalog.read_connection() as conn:
        frozen = conn.execute("SELECT input_json FROM analysis_runs WHERE id=?", (receipt.run_id,)).fetchone()
    assert all(p["className"] is None for p in json.loads(frozen["input_json"])["participants"])


async def test_database_seal_rejects_all_result_dml(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    for sql in ("UPDATE analysis_runs SET input_json='{}'", "UPDATE analysis_runs SET report_ready=0,ready_at=NULL", "DELETE FROM analysis_runs"):
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            with scene.catalog.write_transaction() as conn:
                conn.execute(sql)
    for table in ("analysis_participants", "analysis_item_snapshots", "analysis_student_results", "analysis_class_results", "analysis_evidence"):
        for sql in (f"UPDATE {table} SET run_id=run_id", f"DELETE FROM {table}", f"INSERT INTO {table} SELECT * FROM {table}"):
            with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
                with scene.catalog.write_transaction() as conn:
                    conn.execute(sql)
    assert scene.service.get_run(receipt.run_id).report_ready


# --------------------------------------------------------------------------- 0011 软归档


def test_migration_0011_upgrade_and_idempotent_on_existing_database(tmp_path, monkeypatch):
    """既有库（已迁移 0001..0010）再跑 0011 只新增一列并升级触发器，重复应用为空操作。"""
    full = REGISTERED_MIGRATIONS["teaching"]
    prefix = tuple(m for m in full if m.id != "0011_analysis_runs_archived_at")
    assert len(prefix) == len(full) - 1
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", prefix)
        apply_migrations(connection, database="teaching")
        assert "archived_at" not in {r[1] for r in connection.execute("PRAGMA table_info(analysis_runs)")}
        original_trigger = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='analysis_inputs_fixed'").fetchone()[0]

        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", full)
        assert apply_migrations(connection, database="teaching") == ["0011_analysis_runs_archived_at"]
        columns = [r[1] for r in connection.execute("PRAGMA table_info(analysis_runs)")]
        assert "archived_at" in columns
        # 只加一列，且加在既有列之后（追加式 ALTER 不重排列序）
        assert columns[-1] == "archived_at" and len(columns) == 18
        # 触发器已升级：老句尾 OR OLD.report_ready=1 已被替换
        upgraded = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='analysis_inputs_fixed'").fetchone()[0]
        assert "OR OLD.report_ready=1" not in " ".join(upgraded.split())
        assert "OLD.report_ready=1 AND" in " ".join(upgraded.split())
        assert connection.execute("SELECT count(*) FROM schema_migrations WHERE id='0011_analysis_runs_archived_at'").fetchone()[0] == 1
        # 幂等：重复应用不执行任何迁移、触发器不再被改写
        assert apply_migrations(connection, database="teaching") == []
        assert connection.execute("SELECT sql FROM sqlite_master WHERE name='analysis_inputs_fixed'").fetchone()[0] == upgraded
        assert "OR OLD.report_ready=1" in " ".join(original_trigger.split())
    finally:
        connection.close()


async def test_archive_restore_roundtrip_keeps_report_readable(tmp_path):
    """归档/恢复只写 archived_at；报告内容、子表与读取路径全部不变。"""
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    before = scene.service.get_run(receipt.run_id)
    assert before.archived_at is None and before.report_ready
    snapshot = dict(scene.service.read_ready_report(receipt.run_id), archivedAt=None)

    archived = scene.service.set_archived(receipt.run_id, None, archived=True)
    assert archived.archived_at is not None
    # 幂等：重复归档返回当前视图不报错，时间戳不刷新
    again = scene.service.set_archived(receipt.run_id, None, archived=True)
    assert again == archived
    # 归档后仍可读：详情、四个报告视图、教师备注（archivedAt 是预期内的归档字段变化）
    assert scene.service.get_run(receipt.run_id).archived_at == archived.archived_at
    assert dict(scene.service.read_ready_report(receipt.run_id), archivedAt=None) == snapshot
    assert scene.service.list_report_rows(receipt.run_id, "classes").total == 2
    assert scene.service.list_report_rows(receipt.run_id, "students").total == 8
    assert scene.service.list_report_rows(receipt.run_id, "evidence").total == 12
    scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n-arch", note="归档后仍可备注"))
    assert scene.service.list_notes(receipt.run_id).total == 1
    # 列表过滤：缺省全部、True 只看已归档、False 只看未归档
    assert scene.service.list_runs().total == 1
    assert scene.service.list_runs(archived=True).total == 1
    assert scene.service.list_runs(archived=False).total == 0

    restored = scene.service.set_archived(receipt.run_id, None, archived=False)
    assert restored.archived_at is None
    assert scene.service.set_archived(receipt.run_id, None, archived=False) == restored
    assert scene.service.list_runs(archived=False).total == 1
    assert scene.service.list_runs(archived=True).total == 0
    assert scene.service.read_ready_report(receipt.run_id) == snapshot
    assert scene.service.get_run(receipt.run_id).model_dump(exclude={"job"}) == before.model_dump(exclude={"job"})


async def test_archive_missing_run_is_404_and_unsealed_row_untouched(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()  # 未封存（report_ready=0）
    with pytest.raises(AppError) as missing:
        scene.service.set_archived("no-such-run", None, archived=True)
    assert missing.value.status_code == 404 and missing.value.code == "ANALYSIS_NOT_FOUND"
    # 未封存报告同样允许归档（列表清理不等任务结束）
    archived = scene.service.set_archived(receipt.run_id, None, archived=True)
    assert archived.archived_at is not None and not archived.report_ready
    # 不可变闸门仍然生效：归档列之外的一切写入照旧拒绝
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
        with scene.catalog.write_transaction() as conn:
            conn.execute("UPDATE analysis_runs SET input_json='{}' WHERE id=?", (receipt.run_id,))
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
        with scene.catalog.write_transaction() as conn:
            conn.execute("DELETE FROM analysis_runs WHERE id=?", (receipt.run_id,))
    # 已归档时间戳不得改写（NULL↔时间戳的归档/恢复转换之外一律拒绝）
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
        with scene.catalog.write_transaction() as conn:
            conn.execute("UPDATE analysis_runs SET archived_at='2020-01-01T00:00:00Z' WHERE id=?", (receipt.run_id,))
