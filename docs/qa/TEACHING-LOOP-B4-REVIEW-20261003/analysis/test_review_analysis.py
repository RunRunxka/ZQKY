"""Read-only review probes. Real migrated isolated catalogs; no production edits."""
from __future__ import annotations

import asyncio
import itertools
import json
from pathlib import Path

import pytest

from app.contracts.b4 import NoteRequest
from app.core.exceptions import AppError
from app.services.analysis.aggregate import aggregate
from app.services.analysis.service import AnalysisService
from tests.analysis_support import AnalysisScene


def test_all_three_cell_state_combinations_against_literal_rules():
    # All states plus explicit zero/loss/full credit. Expectations are derived
    # here from the stated rule, never from a production helper or report.
    choices = [("recorded", 0), ("recorded", 50), ("recorded", 100),
               ("missing", None), ("absent", None), ("exempt", None)]
    kp = {"knowledgePointId": "kp", "knowledgeRevisionId": "kr", "name": "固定", "role": "primary"}
    for three in itertools.product(choices, repeat=3):
        facts = {"participants": [{"participantId": "p", "classId": "c"}],
                 "knowledgePoints": [kp],
                 "items": [{"itemId": str(i), "maxScoreUnits": 100, "knowledgePoints": [kp]} for i in range(3)],
                 "cells": [{"participantId": "p", "itemId": str(i), "status": s, "scoreUnits": n}
                           for i, (s, n) in enumerate(three)]}
        got = aggregate(facts)
        valid = sum(s == "recorded" for s, _ in three)
        loss = any(s == "recorded" and n < 100 for s, n in three)
        expected = "needs_consolidation" if loss else "no_evidence" if valid == 0 else "incomplete" if valid < 3 else "full_credit"
        student, classroom = got["students"][0], got["classes"][0]
        assert student["observation"] == expected, three
        assert student["informationIncomplete"] is (valid < 3), three
        assert student["totalScoreUnits"] == (sum(n for _, n in three) if valid == 3 else None), three
        assert student["totalMaxScoreUnits"] == 300
        assert classroom["denominator"] == int(valid > 0), three
        assert classroom["numerator"] == int(loss), three
        assert classroom["ratio"] == (int(loss) if valid else None), three


async def test_concurrent_same_facts_reuses_one_run_and_schedules_once(tmp_path):
    scene = AnalysisScene(tmp_path)
    a, b = await asyncio.gather(scene.accept(submission="one"),
                                scene.accept(submission="two", ids=list(reversed(scene.participant_ids))))
    assert a.run_id == b.run_id and a.input_hash == b.input_hash
    assert sum(r.reused for r in (a, b)) == 1
    assert len(scene.engine.accepted) == 1
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == 1
    assert scene.count("command_submissions") == 2
    replay = await scene.accept(submission="one", ids=list(reversed(scene.participant_ids)))
    assert replay.replayed and replay.run_id == a.run_id
    await scene.engine.run_job("teaching", a.job.job_id, scene.service.execute_job)
    assert scene.service.list_report_rows(a.run_id, "evidence").total == 12


async def test_owner_filter_covers_read_ready_filters_and_note_write(tmp_path):
    scene = AnalysisScene(tmp_path)
    own = await scene.ready()
    foreign = AnalysisService(scene.catalog, job_engine=scene.engine, asset_store=scene.assets, owner_id="different-owner")
    assert foreign.list_runs().total == 0
    for fn in (lambda: foreign.get_run(own.run_id),
               lambda: foreign.list_report_rows(own.run_id, "evidence"),
               lambda: foreign.list_notes(own.run_id),
               lambda: foreign.read_ready_report(own.run_id, owner_id="different-owner"),
               lambda: foreign.add_note(own.run_id, NoteRequest(submissionId="other", note="不能跨归属备注"))):
        with pytest.raises(AppError) as error:
            fn()
        assert error.value.code == "ANALYSIS_NOT_FOUND" and error.value.status_code == 404
    assert scene.count("analysis_teacher_notes") == 0 and scene.count("command_submissions") == 1
    with pytest.raises(AppError) as error:
        await foreign.create_run("assessment", scene.request("other-create"))
    assert error.value.code == "ASSESSMENT_NOT_FOUND"
    assert scene.count("analysis_runs") == 1 and scene.count("workflow_jobs") == 1


async def test_asgi_filter_pagination_and_failed_note_leave_ready_facts_unchanged(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    before = scene.service.read_ready_report(receipt.run_id)
    with scene.http_client() as client:
        url = f"/api/v1/analysis-runs/{receipt.run_id}"
        exact = client.get(url + "/evidence?participantId=p003&knowledgePointId=k1&limit=1")
        assert exact.status_code == 200 and exact.json()["total"] == 2
        assert exact.json()["items"][0]["participant"]["participantId"] == "p003"
        page2 = client.get(url + "/evidence?participantId=p003&knowledgePointId=k1&limit=1&offset=1")
        assert page2.status_code == 200 and page2.json()["items"][0]["evidenceId"] != exact.json()["items"][0]["evidenceId"]
        end = client.get(url + "/evidence?participantId=p003&knowledgePointId=k1&offset=100")
        assert end.status_code == 200 and end.json()["total"] == 2 and end.json()["items"] == []
        for body in ({"submissionId": "bad-target", "participantId": "not-selected", "note": "说明"},
                     {"submissionId": "bad-kp", "knowledgePointId": "not-fixed", "note": "说明"},
                     {"submissionId": "blank", "note": " \t\n"}):
            response = client.post(url + "/notes", json=body)
            assert response.status_code == 422 and response.json()["details"]["issues"]
        assert scene.count("command_submissions") == 1 and scene.count("analysis_teacher_notes") == 0
        note = {"submissionId": "literal-note", "participantId": "p003", "knowledgePointId": "k1", "note": "  教师原文\n第二行  "}
        accepted = client.post(url + "/notes", json=note)
        assert accepted.status_code == 201 and accepted.json()["note"] == note["note"]
        replay = client.post(url + "/notes", json=note)
        assert replay.status_code == 201 and replay.json()["replayed"]
        conflict = client.post(url + "/notes", json={**note, "note": "其他备注"})
        assert conflict.status_code == 409 and conflict.json()["code"] == "SUBMISSION_CONFLICT"
    assert scene.count("analysis_teacher_notes") == 1 and scene.count("command_submissions") == 2
    assert scene.service.read_ready_report(receipt.run_id) == before
