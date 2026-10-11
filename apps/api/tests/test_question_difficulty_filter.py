"""题库难度过滤（C4-2）：GET /questions 的 difficulty 查询参数。

用普通 markdown 导入链（upload → reviewed → confirm）建两道不同题干的 confirmed 题，
SQL 直改 metadata.difficulty 后断言过滤与非法取值 422。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_question_bank import open_harness
from tests.test_question_bank_confirm import upload_and_review, confirm

ONE_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：A
解析：甲说法正确。
"""

OTHER_DOC = """1. 计算 3+4 的结果是（ ）
A. 6
B. 7
C. 8
D. 9
答案：B
解析：基本加法。
"""


@pytest.fixture()
def harness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def _confirm_one(h, doc: str, key: str) -> str:
    import_id, draft = upload_and_review(h, doc, subjectId="math")
    response = confirm(h, import_id, [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
                       submission_id=key)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["failures"] == [], result
    return result["confirmedQuestionIds"][0]


def _set_difficulty(h, question_id: str, difficulty: str) -> None:
    with h.catalog.write_transaction() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM question_revisions WHERE id = (SELECT current_revision_id FROM questions WHERE id=?)",
            (question_id,),
        ).fetchone()
        metadata = json.loads(row["metadata_json"])
        metadata["difficulty"] = difficulty
        conn.execute(
            "UPDATE question_revisions SET metadata_json=? WHERE id=(SELECT current_revision_id FROM questions WHERE id=?)",
            (json.dumps(metadata, ensure_ascii=False), question_id),
        )


def test_difficulty_filter(harness) -> None:
    q1 = _confirm_one(harness, ONE_DOC, "sub-diff-1")
    q2 = _confirm_one(harness, OTHER_DOC, "sub-diff-2")
    _set_difficulty(harness, q1, "easy")
    _set_difficulty(harness, q2, "hard")

    easy = harness.client.get("/api/v1/questions", params={"difficulty": "easy"}).json()
    assert easy["total"] == 1 and easy["questions"][0]["questionId"] == q1
    hard = harness.client.get("/api/v1/questions", params={"difficulty": "hard"}).json()
    assert hard["total"] == 1 and hard["questions"][0]["questionId"] == q2
    assert harness.client.get("/api/v1/questions").json()["total"] == 2

    bad = harness.client.get("/api/v1/questions", params={"difficulty": "super"})
    assert bad.status_code == 422
