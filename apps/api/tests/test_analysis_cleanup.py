"""B-AN：学情报告彻底删除（受引用守卫 + 触发器逐字恢复）的真实装配测试。

覆盖：

- 404（不存在/非本人）与未封存报告同样可删；
- 成功：已封存报告删除后 7 张相关表（run + 6 子表）全部无该 run 行、
  ``workflow_jobs`` 任务行保留、回执 ``{"deleted": true, "runId": ...}``；
- 触发器恢复断言：删除后 7 个 DELETE 触发器与 ``b4`` 登记声明**逐字一致**，
  且对另一个已封存 run 的子表行/报告行直连 DELETE 被拒（兜底仍生效）；
- 守卫：``practice_sets`` 引用 → 409 ``practiceSets``；教案修订引用 →
  ``lessonReferences`` 计数正确；``details.counts`` 恒含两键；
- 归档报告同样可删；HTTP 层路由（TestClient）。

R6 适配：归档把 ``practice_sets`` 引用守卫走完整 ``PracticesScene``（练习域，R7+ 批次）；
本批练习域未回归，守卫语义不变——``practice_sets`` 引用行按同一外键形状直接播种
（与 HTTP 守卫用例同一模式），练习域回归后由其自己的任务卡补全链路用例。

测试全部走隔离 ``tmp_path`` 场景（``AnalysisScene``），不触碰正式 .local-data。
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from app.contracts.b4 import AnalysisCreateRequest, NoteRequest
from app.core.exceptions import AppError
from app.core.migrations import b4 as b4_migrations
from app.core.sqlite import now_iso
from app.services.analysis.service import ANALYSIS_RUN_IN_USE
from tests.analysis_support import AnalysisScene

#: 删除涉及的 7 张表（run + 6 子表）与 7 个 DELETE 触发器
_RUN_TABLES = ("analysis_runs", "analysis_participants", "analysis_item_snapshots",
               "analysis_student_results", "analysis_class_results", "analysis_evidence",
               "analysis_teacher_notes")
_DELETE_TRIGGERS = {"analysis_no_delete", "immutable_analysis_teacher_notes_delete"} | {
    f"freeze_{table}_delete" for table in
    ("analysis_participants", "analysis_item_snapshots", "analysis_student_results",
     "analysis_class_results", "analysis_evidence")}


def _registered_trigger_sql() -> dict[str, str]:
    """从 b4 登记声明提取 ``CREATE TRIGGER <name> ...`` 逐字文本（迁移实际执行的来源）。"""
    return {statement.split()[2]: statement for statement in b4_migrations.TRIGGERS
            if statement.startswith("CREATE TRIGGER")}


def _rows_for_run(scene, table, run_id):
    column = "id" if table == "analysis_runs" else "run_id"
    with scene.catalog.read_connection() as conn:
        return conn.execute(f"SELECT count(*) FROM {table} WHERE {column}=?", (run_id,)).fetchone()[0]


# --------------------------------------------------------------------------- 404 / 未封存


async def test_delete_missing_run_is_404_and_unsealed_deletable(tmp_path):
    scene = AnalysisScene(tmp_path)
    with pytest.raises(AppError) as missing:
        scene.service.delete_run("no-such-run")
    assert missing.value.status_code == 404 and missing.value.code == "ANALYSIS_NOT_FOUND"
    # 未封存（report_ready=0，无子表行）的报告同样可删
    receipt = await scene.accept()
    result = scene.service.delete_run(receipt.run_id)
    assert result.deleted is True
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT count(*) FROM analysis_runs").fetchone()[0] == 0


# --------------------------------------------------------------------------- 成功删除


async def test_delete_sealed_run_clears_seven_tables_and_keeps_job(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    run_id = receipt.run_id
    scene.service.add_note(run_id, NoteRequest(submissionId="note-1", note="教师备注"))
    # 前置：6 张子表确有该 run 的行（evidence=12/participants=4/item_snapshots=3/…）
    assert all(_rows_for_run(scene, table, run_id) > 0 for table in _RUN_TABLES[1:])

    result = scene.service.delete_run(run_id)
    assert result.deleted is True
    assert result.model_dump(by_alias=True) == {"deleted": True, "runId": run_id}
    assert all(_rows_for_run(scene, table, run_id) == 0 for table in _RUN_TABLES)
    # 任务行保留不动（任务历史不属于报告内容）
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT count(*) FROM workflow_jobs").fetchone()[0] == 1
    # 重复删除 → 404，不静默成功
    with pytest.raises(AppError) as missing:
        scene.service.delete_run(run_id)
    assert missing.value.status_code == 404 and missing.value.code == "ANALYSIS_NOT_FOUND"


# --------------------------------------------------------------------------- 触发器恢复


async def test_delete_restores_delete_triggers_verbatim(tmp_path):
    """彻底删除后，7 个 DELETE 触发器必须与登记声明逐字一致且兜底生效（不留后门）。"""
    scene = AnalysisScene(tmp_path)
    first = await scene.ready()
    scene.service.add_note(first.run_id, NoteRequest(submissionId="note-a", note="备注A"))
    # 第二个已封存报告：新成绩修订（facts 含 scoreRevisionId → input_hash 不同 → 新 run）
    scene.new_score()
    second = await scene.service.create_run("assessment", AnalysisCreateRequest(
        submissionId="s2", scoreRevisionId="score-r2",
        selectedParticipantIds=scene.participant_ids, ruleCode="any_loss_v1"))
    job = await scene.engine.run_job("teaching", second.job.job_id, scene.service.execute_job)
    assert job.state == "succeeded", job.error
    other = second.run_id
    assert other != first.run_id
    # 另一报告也放一条备注（无行的表不会触发 BEFORE DELETE，断言才有效）
    scene.service.add_note(other, NoteRequest(submissionId="note-b", note="备注B"))

    scene.service.delete_run(first.run_id)

    registered = _registered_trigger_sql()
    assert _DELETE_TRIGGERS <= set(registered)
    with scene.catalog.read_connection() as conn:
        for name in sorted(_DELETE_TRIGGERS):
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
            assert row is not None, name
            assert row["sql"] == registered[name], name
    # 兜底仍生效：对另一个已封存 run 的直连 DELETE 全部被拒
    for sql in (f"DELETE FROM analysis_participants WHERE run_id='{other}'",
                f"DELETE FROM analysis_item_snapshots WHERE run_id='{other}'",
                f"DELETE FROM analysis_evidence WHERE run_id='{other}'",
                f"DELETE FROM analysis_teacher_notes WHERE run_id='{other}'",
                f"DELETE FROM analysis_runs WHERE id='{other}'"):
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            with scene.catalog.write_transaction() as conn:
                conn.execute(sql)
    assert scene.service.get_run(other).report_ready


# --------------------------------------------------------------------------- 守卫


async def test_delete_guarded_by_practice_set(tmp_path):
    """``practice_sets`` 引用该 run → 409 practiceSets=1，counts 恒含两键，数据不乱。

    R6 适配：练习域（R7+）未回归，按 ``practice_sets`` 的外键形状直接播种引用行
    （``analysis_runs(id,owner_id)`` 复合外键），守卫只数行数，语义与完整链路一致。
    """
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    with scene.catalog.write_transaction() as conn:
        conn.execute("INSERT INTO practice_sets(id,owner_id,analysis_run_id,subject_id,title,created_at) "
                     "VALUES('ps-guard','local',?,'math','针对练习',?)", (receipt.run_id, now_iso()))
    with pytest.raises(AppError) as err:
        scene.service.delete_run(receipt.run_id)
    assert err.value.status_code == 409 and err.value.code == ANALYSIS_RUN_IN_USE
    counts = err.value.details["counts"]
    assert set(counts) == {"practiceSets", "lessonReferences"}
    assert counts["practiceSets"] == 1 and counts["lessonReferences"] == 0
    assert "学情报告仍被引用" in str(err.value) and "针对练习 1 条" in str(err.value)
    # 数据不乱：报告仍在且可读
    assert scene.service.get_run(receipt.run_id).report_ready


async def test_delete_guarded_by_lesson_revision_reference(tmp_path):
    """教案修订引用（lesson_plan_revisions.analysis_run_id）→ 409 lessonReferences 计数正确。"""
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    run_id = receipt.run_id
    now = now_iso()
    base_context = {"subjectId": "math", "classId": "class"}
    with scene.catalog.write_transaction() as conn:
        conn.execute("INSERT INTO lesson_plans(id,owner_id,subject_id,class_id,current_revision_id,revision,"
                     "archived_at,created_at,updated_at) VALUES('lesson','local','math','class','lesson-r1',1,NULL,?,?)",
                     (now, now))
        conn.execute("INSERT INTO lesson_plan_revisions(id,lesson_plan_id,owner_id,version,data_json,content_hash,"
                     "source,context_snapshot_json,analysis_run_id,accepted_proposal_id,import_envelope_json,"
                     "source_metadata_json,selected_fields_json,process_metadata_json,created_at) "
                     "VALUES('lesson-r1','lesson','local',1,?,'seed','manual',?,NULL,NULL,NULL,'{}','[]','[]',?)",
                     (json.dumps({"title": "种子版本"}, ensure_ascii=False), json.dumps(base_context), now))
        referenced_context = {**base_context, "analysis": {"analysisRunId": run_id}}
        conn.execute("INSERT INTO lesson_plan_revisions(id,lesson_plan_id,owner_id,version,data_json,content_hash,"
                     "source,context_snapshot_json,analysis_run_id,accepted_proposal_id,import_envelope_json,"
                     "source_metadata_json,selected_fields_json,process_metadata_json,created_at) "
                     "VALUES('lesson-r2','lesson','local',2,?,'seed','manual',?,?,NULL,NULL,'{}','[]','[]',?)",
                     (json.dumps({"title": "引用报告版本"}, ensure_ascii=False), json.dumps(referenced_context), run_id, now))
    with pytest.raises(AppError) as err:
        scene.service.delete_run(run_id)
    assert err.value.status_code == 409 and err.value.code == ANALYSIS_RUN_IN_USE
    counts = err.value.details["counts"]
    assert counts["lessonReferences"] == 1 and counts["practiceSets"] == 0
    assert "教案引用" in str(err.value)
    assert scene.service.get_run(run_id).report_ready


# --------------------------------------------------------------------------- 归档可删


async def test_delete_archived_run(tmp_path):
    """已归档（archived_at 非空）的报告同样可彻底删除。"""
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    scene.service.set_archived(receipt.run_id, None, archived=True)
    assert scene.service.get_run(receipt.run_id).archived_at is not None
    result = scene.service.delete_run(receipt.run_id)
    assert result.deleted is True
    assert scene.service.list_runs().total == 0
    assert all(_rows_for_run(scene, table, receipt.run_id) == 0 for table in _RUN_TABLES)


# --------------------------------------------------------------------------- HTTP 路由


async def test_http_delete_route_receipt_404_and_guard(tmp_path):
    scene = AnalysisScene(tmp_path)
    with scene.http_client() as client:
        receipt = await scene.ready()
        url = f"/api/v1/analysis-runs/{receipt.run_id}"
        missing = client.delete("/api/v1/analysis-runs/unknown")
        assert missing.status_code == 404 and missing.json()["code"] == "ANALYSIS_NOT_FOUND"
        # 守卫：播种一条 practice_sets 引用 → 409 列出计数
        with scene.catalog.write_transaction() as conn:
            conn.execute("INSERT INTO practice_sets(id,owner_id,analysis_run_id,subject_id,title,created_at) "
                         "VALUES('ps-guard','local',?,'math','针对练习',?)", (receipt.run_id, now_iso()))
        blocked = client.delete(url)
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["code"] == ANALYSIS_RUN_IN_USE
        assert blocked.json()["details"]["counts"] == {"practiceSets": 1, "lessonReferences": 0}
        assert "学情报告仍被引用" in blocked.json()["message"]
        with scene.catalog.write_transaction() as conn:
            conn.execute("DELETE FROM practice_sets WHERE id='ps-guard'")
        deleted = client.delete(url)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json() == {"deleted": True, "runId": receipt.run_id}
        assert client.get(url).status_code == 404
