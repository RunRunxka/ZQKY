"""G2 draft commands: original receipts, real HTTP, and atomic teaching writes."""
import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contracts import b4
from app.core.exceptions import AppError
from tests.practices_support import PracticesScene, open_api_scene, seed_api_loop


@pytest.fixture
async def scene(tmp_path):
    value = await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


def command(scene, practice, *, submission="draft-first", score="1.00", question=None):
    question = question or scene.question()
    return b4.PracticeDraftPatch(
        submissionId=submission, expectedRevision=practice.revision,
        items=[scene.item(question, score=score)], constraints=practice.current_revision.constraints,
    )


def receipts(scene, set_id):
    with scene.catalog.read_connection() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM command_submissions WHERE owner_id=? AND operation=? ORDER BY created_at,submission_id",
            (scene.service.owner_id, "practice.draft:" + set_id),
        )]


async def test_replay_returns_original_receipt_after_later_save_and_review(scene):
    practice = scene.create_set()
    first_command = command(scene, practice)
    first = scene.service.save_draft(practice.practice_set_id, first_command)
    original_receipt = receipts(scene, practice.practice_set_id)
    second_command = command(scene, first, submission="draft-second", score="3.00",
                             question=scene.questions.get_question(first.current_revision.items[0].question_id))
    second = scene.service.save_draft(practice.practice_set_id, second_command)
    reviewed = scene.review(second)
    replay = scene.service.save_draft(practice.practice_set_id, first_command)
    assert replay.model_dump() == first.model_copy(update={"replayed": True}).model_dump()
    assert replay.revision == 1 and replay.current_revision.total_score_units == 100
    assert scene.service.get_practice(practice.practice_set_id).model_dump() == reviewed.model_dump()
    assert reviewed.revision == 3 and reviewed.current_revision.total_score_units == 300
    assert len(receipts(scene, practice.practice_set_id)) == 2
    assert receipts(scene, practice.practice_set_id)[0] == original_receipt[0]


async def test_same_identity_different_body_conflicts_before_stale_cas(scene):
    practice = scene.create_set()
    body = command(scene, practice)
    first = scene.service.save_draft(practice.practice_set_id, body)
    changed = body.model_dump(by_alias=True)
    changed["items"][0]["maxScore"] = "2.00"
    changed["items"][0]["itemStructure"]["nodes"][0]["maxScore"] = "2.00"
    with pytest.raises(AppError) as error:
        scene.service.save_draft(practice.practice_set_id, b4.PracticeDraftPatch.model_validate(changed))
    assert error.value.status_code == 409 and error.value.code == "SUBMISSION_CONFLICT"
    with pytest.raises(AppError) as error:
        scene.service.save_draft(practice.practice_set_id, body.model_copy(update={"submission_id": "genuine-new"}))
    assert error.value.code == "REVISION_CONFLICT" and error.value.details == {"currentRevision": 1, "fields": ["expectedRevision"]}
    assert scene.service.get_practice(practice.practice_set_id).model_dump() == first.model_dump()
    assert len(receipts(scene, practice.practice_set_id)) == 1


async def test_same_submission_is_scoped_to_practice_and_owner(scene):
    question = scene.question()
    first_set = scene.create_set(submission="set-one")
    second_set = scene.create_set(submission="set-two")
    body = command(scene, first_set, question=question)
    first = scene.service.save_draft(first_set.practice_set_id, body)
    second = scene.service.save_draft(second_set.practice_set_id, body)
    assert first.practice_set_id != second.practice_set_id and first.revision == second.revision == 1
    assert len(receipts(scene, first.practice_set_id)) == len(receipts(scene, second.practice_set_id)) == 1
    scene.service.owner_id = "foreign"
    with pytest.raises(AppError) as error:
        scene.service.save_draft(first.practice_set_id, body)
    assert error.value.status_code == 404 and error.value.code == "PRACTICE_NOT_FOUND"
    assert receipts(scene, first.practice_set_id) == []
    scene.service.owner_id = "local"


async def test_successful_replay_ignores_later_reference_and_asset_failure(scene, monkeypatch):
    question = scene.question(rich=scene.rich())
    practice = scene.create_set()
    body = command(scene, practice, question=question)
    first = scene.service.save_draft(practice.practice_set_id, body)
    scene.questions.archive_question(question.question_id)
    monkeypatch.setattr(scene.service, "read_question_asset", lambda _: (_ for _ in ()).throw(AssertionError("replay asset IO")))
    monkeypatch.setattr(scene.service, "_prepared", lambda *_: (_ for _ in ()).throw(AssertionError("replay preflight")))
    monkeypatch.setattr(scene.service, "_active_refs", lambda *_: (_ for _ in ()).throw(AssertionError("replay refs")))
    replay = scene.service.save_draft(practice.practice_set_id, body)
    assert replay.model_dump() == first.model_copy(update={"replayed": True}).model_dump()
    assert len(receipts(scene, practice.practice_set_id)) == 1


async def test_concurrent_identical_commands_store_once(scene, monkeypatch):
    practice = scene.create_set()
    body = command(scene, practice)
    barrier = threading.Barrier(2)
    prepare = scene.service._prepared
    store = scene.service._store_items
    writes = []
    def both_prepare(*args):
        prepared = prepare(*args)
        barrier.wait(timeout=10)
        return prepared
    def counted_store(*args):
        writes.append(1)
        return store(*args)
    monkeypatch.setattr(scene.service, "_prepared", both_prepare)
    monkeypatch.setattr(scene.service, "_store_items", counted_store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(scene.service.save_draft, practice.practice_set_id, body) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].model_copy(update={"replayed": False}).model_dump() == results[1].model_copy(update={"replayed": False}).model_dump()
    assert writes == [1] and len(receipts(scene, practice.practice_set_id)) == 1
    assert scene.service.get_practice(practice.practice_set_id).revision == 1
    assert scene.coordinator.busy is False


async def test_receipt_insert_failure_rolls_back_business_then_same_command_retries(scene):
    practice = scene.create_set()
    body = command(scene, practice)
    with scene.catalog.write_transaction() as conn:
        conn.execute("CREATE TRIGGER fail_draft_receipt BEFORE INSERT ON command_submissions "
                     "WHEN NEW.operation LIKE 'practice.draft:%' BEGIN SELECT RAISE(ABORT,'receipt failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="receipt failure"):
        scene.service.save_draft(practice.practice_set_id, body)
    assert scene.service.get_practice(practice.practice_set_id).model_dump() == practice.model_dump()
    assert receipts(scene, practice.practice_set_id) == []
    assert scene.coordinator.busy is False
    with scene.catalog.write_transaction() as conn:
        conn.execute("DROP TRIGGER fail_draft_receipt")
    saved = scene.service.save_draft(practice.practice_set_id, body)
    assert saved.revision == 1 and saved.current_revision.total_score_units == 100
    assert len(receipts(scene, practice.practice_set_id)) == 1


async def test_archive_between_preparation_and_publication_rejects_zero_partial(scene, monkeypatch):
    question = scene.question()
    practice = scene.create_set()
    body = command(scene, practice, question=question)
    prepare = scene.service._prepared
    def archive_after_prepare(*args):
        prepared = prepare(*args)
        scene.questions.archive_question(question.question_id)
        return prepared
    monkeypatch.setattr(scene.service, "_prepared", archive_after_prepare)
    with pytest.raises(AppError) as error:
        scene.service.save_draft(practice.practice_set_id, body)
    assert error.value.code == "PRACTICE_REFERENCE_CHANGED"
    assert scene.service.get_practice(practice.practice_set_id).model_dump() == practice.model_dump()
    assert receipts(scene, practice.practice_set_id) == []


def test_actual_api_lost_changed_save_response_replays_original_before_new_state(tmp_path):
    with open_api_scene(tmp_path) as (app, client, settings):
        seed = seed_api_loop(app, client, tag="g2-replay")
        practice = seed["practice"]
        prefix = "/api/v1/practice-sets/" + practice["practiceSetId"]
        copied = client.post(prefix + "/revisions", json={"submissionId": "g2-copy", "sourceRevisionId": practice["currentRevision"]["practiceRevisionId"]})
        assert copied.status_code == 201, copied.text
        draft = copied.json()
        body = {"submissionId": "g2-save", "expectedRevision": draft["revision"],
                "items": copy.deepcopy(draft["currentRevision"]["draftItems"]), "constraints": draft["currentRevision"]["constraints"]}
        body["items"][0]["maxScore"] = "1.00"
        body["items"][0]["itemStructure"]["nodes"][0]["maxScore"] = "1.00"
        frozen_wire = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        first = client.patch(prefix + "/draft", content=frozen_wire, headers={"content-type": "application/json"})
        assert first.status_code == 200, first.text
        original = first.json()
        assert original["revision"] == draft["revision"] + 1 and original["currentRevision"]["totalScoreUnits"] == 100
        replay = client.patch(prefix + "/draft", content=frozen_wire, headers={"content-type": "application/json"})
        assert replay.status_code == 200, replay.text
        assert replay.json() == dict(original, replayed=True)
        newer = copy.deepcopy(body)
        newer.update(submissionId="g2-later-save", expectedRevision=original["revision"])
        newer["items"][0]["maxScore"] = "3.00"
        newer["items"][0]["itemStructure"]["nodes"][0]["maxScore"] = "3.00"
        later = client.patch(prefix + "/draft", json=newer)
        assert later.status_code == 200, later.text
        replay = client.patch(prefix + "/draft", content=frozen_wire, headers={"content-type": "application/json"})
        assert replay.status_code == 200 and replay.json() == dict(original, replayed=True)
        assert client.get(prefix).json() == later.json()
        conflict = client.patch(prefix + "/draft", json=dict(newer, submissionId="g2-save"))
        assert conflict.status_code == 409 and conflict.json()["code"] == "SUBMISSION_CONFLICT"
        stale = client.patch(prefix + "/draft", json=dict(body, submissionId="g2-new-stale"))
        assert stale.status_code == 409 and stale.json()["code"] == "REVISION_CONFLICT"
        assert stale.json()["details"]["currentRevision"] == later.json()["revision"]
        assert client.patch(prefix + "/draft", json={k: v for k, v in body.items() if k != "submissionId"}).status_code == 422
        with app.state.teaching.read_connection() as conn:
            rows = conn.execute("SELECT submission_id,result_json FROM command_submissions WHERE operation=? ORDER BY submission_id",
                                ("practice.draft:" + practice["practiceSetId"],)).fetchall()
        assert len(rows) == 3  # The initial seed, first save, and later save.
        stored = json.loads(next(row["result_json"] for row in rows if row["submission_id"] == "g2-save"))
        assert stored == original
        app.state.practice_service.owner_id = "foreign"
        foreign = client.patch(prefix + "/draft", content=frozen_wire, headers={"content-type": "application/json"})
        assert foreign.status_code == 404 and foreign.json()["code"] == "PRACTICE_NOT_FOUND"
        assert "currentRevision" not in foreign.json().get("details", {})
        app.state.practice_service.owner_id = "local"
        assert settings.credentials_file is None


@pytest.mark.parametrize("review_after_commit", [False, True])
async def test_early_receipt_miss_then_identical_commit_replays_before_new_cas_and_state(scene, monkeypatch, review_after_commit):
    practice = scene.create_set()
    body = command(scene, practice, submission="early-miss")
    local = threading.local()
    missed, committed = threading.Event(), threading.Event()
    replay = scene.service._replay
    def pause_first_miss(value):
        result = replay(value)
        if getattr(local, "lag", False) and not getattr(local, "paused", False):
            local.paused = True
            assert result is None
            missed.set()
            assert committed.wait(timeout=10)
        return result
    monkeypatch.setattr(scene.service, "_replay", pause_first_miss)
    def lag():
        local.lag = True
        return scene.service.save_draft(practice.practice_set_id, body.model_copy(deep=True))
    def leader():
        assert missed.wait(timeout=10)
        try:
            saved = scene.service.save_draft(practice.practice_set_id, body.model_copy(deep=True))
            if review_after_commit:
                scene.review(saved, submission="review-after-early-miss")
            return saved
        finally:
            committed.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        lag_future, leader_future = pool.submit(lag), pool.submit(leader)
        first, duplicate = leader_future.result(timeout=15), lag_future.result(timeout=15)
    assert duplicate.model_dump() == first.model_copy(update={"replayed": True}).model_dump()
    current = scene.service.get_practice(practice.practice_set_id)
    assert current.revision == (2 if review_after_commit else 1)
    assert current.current_revision.state == ("reviewed" if review_after_commit else "draft")
    assert len(receipts(scene, practice.practice_set_id)) == 1
    assert scene.coordinator.busy is False


async def test_preflight_receipt_and_cas_share_snapshot_while_identical_save_commits(scene, monkeypatch):
    practice = scene.create_set()
    body = command(scene, practice, submission="snapshot-miss")
    local = threading.local()
    pinned, committed = threading.Event(), threading.Event()
    replay_in, set_view = scene.service._replay_in, scene.service._set_view
    observed = []
    def pause_pinned_miss(conn, value):
        result = replay_in(conn, value)
        if getattr(local, "lag", False):
            local.calls = getattr(local, "calls", 0) + 1
            if local.calls == 2:
                assert result is None and conn.in_transaction
                pinned.set()
                assert committed.wait(timeout=10)
        return result
    def observe_snapshot(conn, set_id):
        result = set_view(conn, set_id)
        if getattr(local, "lag", False) and pinned.is_set():
            observed.append((result.revision, result.current_revision.state))
        return result
    monkeypatch.setattr(scene.service, "_replay_in", pause_pinned_miss)
    monkeypatch.setattr(scene.service, "_set_view", observe_snapshot)
    def lag():
        local.lag = True
        return scene.service.save_draft(practice.practice_set_id, body.model_copy(deep=True))
    def leader():
        assert pinned.wait(timeout=10)
        try:
            saved = scene.service.save_draft(practice.practice_set_id, body.model_copy(deep=True))
            scene.review(saved, submission="review-after-snapshot-miss")
            return saved
        finally:
            committed.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        lag_future, leader_future = pool.submit(lag), pool.submit(leader)
        first, duplicate = leader_future.result(timeout=15), lag_future.result(timeout=15)
    assert observed == [(practice.revision, "draft")]
    assert duplicate.model_dump() == first.model_copy(update={"replayed": True}).model_dump()
    assert scene.service.get_practice(practice.practice_set_id).revision == 2
    assert len(receipts(scene, practice.practice_set_id)) == 1
    assert scene.coordinator.busy is False


@pytest.mark.parametrize("error_kind", ["asset-io", "asset-validation"])
async def test_asset_preparation_error_after_identical_commit_returns_original_receipt(scene, monkeypatch, error_kind):
    question = scene.question(rich=scene.rich())
    practice = scene.create_set()
    body = command(scene, practice, submission="prepare-error", question=question)
    local = threading.local()
    preparing, committed = threading.Event(), threading.Event()
    read_asset = scene.service.read_question_asset
    failure = OSError("source image disappeared") if error_kind == "asset-io" else AppError(
        "source image validation failed", code="PRACTICE_ASSET_INVALID", status_code=422)
    def fail_lag_asset(asset_id):
        if getattr(local, "lag", False):
            assert not scene.coordinator.busy
            preparing.set()
            assert committed.wait(timeout=10)
            raise failure
        return read_asset(asset_id)
    monkeypatch.setattr(scene.service, "read_question_asset", fail_lag_asset)
    def lag():
        local.lag = True
        return scene.service.save_draft(practice.practice_set_id, body.model_copy(deep=True))
    def leader():
        assert preparing.wait(timeout=10)
        try:
            return scene.service.save_draft(practice.practice_set_id, body.model_copy(deep=True))
        finally:
            committed.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        lag_future, leader_future = pool.submit(lag), pool.submit(leader)
        first, duplicate = leader_future.result(timeout=15), lag_future.result(timeout=15)
    assert duplicate.model_dump() == first.model_copy(update={"replayed": True}).model_dump()
    assert scene.service.get_practice(practice.practice_set_id).revision == 1
    assert len(receipts(scene, practice.practice_set_id)) == 1
    assert scene.coordinator.busy is False


async def test_preparation_error_without_successful_receipt_retains_original_failure(scene, monkeypatch):
    question = scene.question(rich=scene.rich())
    practice = scene.create_set()
    body = command(scene, practice, submission="prepare-no-receipt", question=question)
    failure = OSError("original isolated asset failure")
    def fail_asset(_):
        assert not scene.coordinator.busy
        raise failure
    monkeypatch.setattr(scene.service, "read_question_asset", fail_asset)
    with pytest.raises(OSError) as error:
        scene.service.save_draft(practice.practice_set_id, body)
    assert error.value is failure
    assert scene.service.get_practice(practice.practice_set_id).model_dump() == practice.model_dump()
    assert receipts(scene, practice.practice_set_id) == []
    assert scene.coordinator.busy is False


def test_actual_http_identical_deepcopy_concurrency_after_early_miss_writes_once(tmp_path, monkeypatch):
    with open_api_scene(tmp_path) as (app, client, settings):
        seed = seed_api_loop(app, client, tag="g2-v2-http-concurrent")
        practice = seed["practice"]
        prefix = "/api/v1/practice-sets/" + practice["practiceSetId"]
        copied = client.post(prefix + "/revisions", json={"submissionId": "g2-v2-copy",
            "sourceRevisionId": practice["currentRevision"]["practiceRevisionId"]})
        assert copied.status_code == 201, copied.text
        draft = copied.json()
        body = {"submissionId": "g2-v2-http-same", "expectedRevision": draft["revision"],
                "items": copy.deepcopy(draft["currentRevision"]["draftItems"]),
                "constraints": copy.deepcopy(draft["currentRevision"]["constraints"])}
        body["items"][0]["maxScore"] = "1.00"
        body["items"][0]["itemStructure"]["nodes"][0]["maxScore"] = "1.00"
        service = app.state.practice_service
        replay, store = service._replay, service._store_items
        committed, missed = threading.Event(), threading.Event()
        gate = threading.Lock()
        first_call, writes = [], []
        def pause_one_early_miss(value):
            result = replay(value)
            if value.submission_id == body["submissionId"]:
                with gate:
                    pause = not first_call
                    first_call.append(1)
                if pause:
                    assert result is None
                    missed.set()
                    assert committed.wait(timeout=10)
            return result
        def counted_store(*args):
            writes.append(1)
            return store(*args)
        monkeypatch.setattr(service, "_replay", pause_one_early_miss)
        monkeypatch.setattr(service, "_store_items", counted_store)
        barrier = threading.Barrier(2)
        def patch_identical():
            barrier.wait(timeout=5)
            response = client.patch(prefix + "/draft", json=copy.deepcopy(body))
            if response.status_code == 200:
                committed.set()
            return response
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(patch_identical) for _ in range(2)]
            responses = [future.result(timeout=15) for future in futures]
        assert missed.is_set()
        assert [response.status_code for response in responses] == [200, 200], [response.text for response in responses]
        results = [response.json() for response in responses]
        assert sorted(result["replayed"] for result in results) == [False, True]
        assert dict(results[0], replayed=False) == dict(results[1], replayed=False)
        assert results[0]["revision"] == draft["revision"] + 1
        assert results[0]["currentRevision"]["totalScoreUnits"] == 100
        assert writes == [1]
        assert client.get(prefix).json() == dict(results[0], replayed=False)
        with app.state.teaching.read_connection() as conn:
            rows = conn.execute("SELECT result_json FROM command_submissions WHERE owner_id=? AND operation=? AND submission_id=?",
                ("local", "practice.draft:" + practice["practiceSetId"], body["submissionId"])).fetchall()
        assert len(rows) == 1 and json.loads(rows[0]["result_json"]) == dict(results[0], replayed=False)
        assert settings.credentials_file is None and not app.state.publication_coordinator.busy
