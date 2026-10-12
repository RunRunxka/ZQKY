"""New formal revisions cannot publish knowledge links outside the coordinator."""

from pathlib import Path
import threading
import time

import pytest

from tests.test_question_generation import GenerationHarness
from tests.test_question_subject_links import _confirmed_question, _patch_question


@pytest.mark.parametrize("explicit", [False, True])
def test_archive_waits_until_formal_revision_commit(tmp_path: Path, monkeypatch, explicit: bool) -> None:
    harness = GenerationHarness(tmp_path)
    release = threading.Event()
    threads: list[threading.Thread] = []
    try:
        point = harness.create_point()
        question_id, detail = _confirmed_question(harness, point)
        current_point = harness.client.get(f'/api/v1/knowledge-points/{point["pointId"]}').json()
        entered, archived = threading.Event(), threading.Event()
        original = harness.catalog.patch_question
        outcomes = {}

        def pause_before_domain_commit(*args, **kwargs):
            entered.set()
            assert release.wait(3)
            return original(*args, **kwargs)

        monkeypatch.setattr(harness.catalog, "patch_question", pause_before_domain_commit)

        def publish():
            overrides = {"knowledgeLinks": [{"knowledgePointId": point["pointId"]}]} if explicit else {}
            outcomes["patch"] = _patch_question(harness, question_id, detail, **overrides)

        def archive():
            outcomes["archive"] = harness.client.post(
                f'/api/v1/knowledge-points/{point["pointId"]}/archive',
                json={"expectedRevision": current_point["revision"]},
            )
            archived.set()

        threads = [threading.Thread(target=publish), threading.Thread(target=archive)]
        threads[0].start()
        assert entered.wait(3)
        threads[1].start()
        time.sleep(0.1)
        assert not archived.is_set()
        release.set()
        for thread in threads:
            thread.join(3)
            assert not thread.is_alive()
        assert outcomes["patch"].status_code == outcomes["archive"].status_code == 200
    finally:
        release.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(3)
        harness.close()


def test_archived_inherited_link_is_readable_but_cannot_enter_new_revision(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point()
        question_id, detail = _confirmed_question(harness, point)
        harness.archive_point(point["pointId"])
        rejected = _patch_question(harness, question_id, detail)
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["code"] == "KNOWLEDGE_ARCHIVED"
        assert harness.client.get(f"/api/v1/questions/{question_id}").json() == detail
        cleared = _patch_question(harness, question_id, detail, knowledgeLinks=[])
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["knowledgeLinks"] == []
    finally:
        harness.close()
