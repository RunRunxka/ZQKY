"""V00 · RV07 探针：改题学科时的关联集合核验（自建）。

缺陷回顾（B2-RV07）：只显式提供 knowledgeLinks 时才核新学科；省略时无条件复制旧关联，
产生跨学科题。

断言：
  A. 改学科（math→chinese）且省略 knowledgeLinks → 422 KNOWLEDGE_REFERENCE_INVALID，
     details.issues 定位到冲突知识点，旧修订与关联未被改动；
  B. 同一次改学科 + 显式清空（knowledgeLinks=[]）→ 200，新修订无关联；
  C. 改学科 + 显式替换为同学科（chinese）知识点 → 200，新修订带新关联；
  D. 同学科（math）只改内容、省略关联 → 200，旧关联被复制保留。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p07_rv07_subject_links.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00_papers import PapersProbe  # noqa: E402

from app.services.question_bank.service import build_question_bank_service  # noqa: E402

QB_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：A
解析：甲说法正确。
"""


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    probe = PapersProbe(V.PROBE_TMP / "rv07")
    app = probe.app
    qb = build_question_bank_service(
        app.state.question_bank,
        probe.settings,
        model_resolver=probe.resolver,
        knowledge_catalog=app.state.knowledge,
        coordinator=app.state.publication_coordinator,
        job_engine=app.state.job_engine,
    )
    app.state.question_bank_service = qb
    client = probe.client
    try:
        math_point = probe.add_point(code="kp-math", name="一次函数", subject_id="math")
        chinese_point = probe.add_point(code="kp-chinese", name="修辞手法", subject_id="chinese")

        imported = client.post(
            "/api/v1/question-imports",
            files={"file": ("q.md", QB_DOC.encode("utf-8"), "text/markdown")},
            data={"subjectId": "math", "gradeId": "grade-7"},
        )
        assert imported.status_code == 201, imported.text
        import_id = imported.json()["importId"]
        draft = client.get(f"/api/v1/question-imports/{import_id}").json()["drafts"][0]
        linked = client.patch(
            f"/api/v1/question-drafts/{draft['draftId']}",
            json={
                "expectedRevision": draft["revision"],
                "content": draft["content"],
                "metadata": {**draft["metadata"], "subjectId": "math"},
                "knowledgeLinks": [{"knowledgePointId": math_point.point_id, "role": "primary"}],
            },
        )
        assert linked.status_code == 200, linked.text
        reviewed = client.patch(
            f"/api/v1/question-drafts/{draft['draftId']}",
            json={
                "expectedRevision": linked.json()["revision"],
                "content": linked.json()["content"],
                "metadata": linked.json()["metadata"],
                "reviewState": "reviewed",
            },
        )
        assert reviewed.status_code == 200, reviewed.text
        confirmed = client.post(
            f"/api/v1/question-imports/{import_id}/confirm",
            json={
                "submissionId": "rv07-confirm-1",
                "importId": import_id,
                "items": [
                    {"draftId": reviewed.json()["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}
                ],
                "duplicateResolutions": [],
            },
        )
        question_id = confirmed.json()["confirmedQuestionIds"][0]
        question = client.get(f"/api/v1/questions/{question_id}").json()
        results["baseline"] = {
            "subjectId": question["metadata"]["subjectId"],
            "revision": question["revision"],
            "knowledgeLinks": [
                {"knowledgePointId": link["knowledgePointId"], "role": link["role"]}
                for link in question["knowledgeLinks"]
            ],
        }

        def patch_question(payload: dict[str, Any]):
            return client.patch(f"/api/v1/questions/{question_id}", json=payload)

        # ---- A. 改学科、省略关联
        current = client.get(f"/api/v1/questions/{question_id}").json()
        payload_a = {
            "expectedRevision": current["revision"],
            "content": current["content"],
            "metadata": {**current["metadata"], "subjectId": "chinese"},
        }
        response_a = patch_question(payload_a)
        after_a = client.get(f"/api/v1/questions/{question_id}").json()
        body_a = response_a.json()
        results["subject_change_without_links"] = {
            "status": response_a.status_code,
            "code": body_a.get("code"),
            "issues": (body_a.get("details") or {}).get("issues"),
            "subjectAfter": after_a["metadata"]["subjectId"],
            "linksAfter": [link["knowledgePointId"] for link in after_a["knowledgeLinks"]],
            "revisionUnchanged": after_a["revision"] == current["revision"],
        }
        if not (
            response_a.status_code == 422
            and body_a.get("code") == "KNOWLEDGE_REFERENCE_INVALID"
            and body_a.get("details", {}).get("issues")
            and any(
                issue.get("field", "").startswith("knowledgeLinks")
                for issue in body_a["details"]["issues"]
            )
            and after_a["revision"] == current["revision"]
        ):
            failures.append("A: 改学科省略关联未被定位拒绝")

        # ---- B. 改学科 + 显式清空
        current = client.get(f"/api/v1/questions/{question_id}").json()
        response_b = patch_question(
            {
                "expectedRevision": current["revision"],
                "content": current["content"],
                "metadata": {**current["metadata"], "subjectId": "chinese"},
                "knowledgeLinks": [],
            }
        )
        after_b = client.get(f"/api/v1/questions/{question_id}").json()
        results["subject_change_explicit_clear"] = {
            "status": response_b.status_code,
            "subjectAfter": after_b["metadata"]["subjectId"],
            "linksAfter": [link["knowledgePointId"] for link in after_b["knowledgeLinks"]],
        }
        if not (
            response_b.status_code == 200
            and after_b["metadata"]["subjectId"] == "chinese"
            and after_b["knowledgeLinks"] == []
        ):
            failures.append("B: 改学科并显式清空未成功或被强制保留关联")

        # ---- C. 改回 math + 显式替换为同学科知识点（对 chinese 题改回 math 并给 math 关联）
        current = client.get(f"/api/v1/questions/{question_id}").json()
        response_c = patch_question(
            {
                "expectedRevision": current["revision"],
                "content": current["content"],
                "metadata": {**current["metadata"], "subjectId": "math"},
                "knowledgeLinks": [{"knowledgePointId": math_point.point_id, "role": "primary"}],
            }
        )
        after_c = client.get(f"/api/v1/questions/{question_id}").json()
        results["subject_change_explicit_replace"] = {
            "status": response_c.status_code,
            "subjectAfter": after_c["metadata"]["subjectId"],
            "linksAfter": [link["knowledgePointId"] for link in after_c["knowledgeLinks"]],
        }
        if not (
            response_c.status_code == 200
            and after_c["metadata"]["subjectId"] == "math"
            and [link["knowledgePointId"] for link in after_c["knowledgeLinks"]]
            == [math_point.point_id]
        ):
            failures.append("C: 改学科并显式替换未生效")

        # ---- C2. 替换为**异学科**知识点（chinese 点配 math 题）→ 422
        current = client.get(f"/api/v1/questions/{question_id}").json()
        response_c2 = patch_question(
            {
                "expectedRevision": current["revision"],
                "content": current["content"],
                "metadata": {**current["metadata"]},
                "knowledgeLinks": [{"knowledgePointId": chinese_point.point_id, "role": "primary"}],
            }
        )
        results["explicit_wrong_subject_link"] = {
            "status": response_c2.status_code,
            "code": response_c2.json().get("code"),
        }
        if response_c2.status_code != 422:
            failures.append("C2: 显式提交异学科关联未被拒")

        # ---- D. 同学科改内容、省略关联 → 复制旧关联
        current = client.get(f"/api/v1/questions/{question_id}").json()
        content = dict(current["content"])
        content["stemMarkdown"] = "下列说法正确的是（ ）（修改后的题干）"
        response_d = patch_question(
            {
                "expectedRevision": current["revision"],
                "content": content,
                "metadata": {**current["metadata"]},
            }
        )
        after_d = client.get(f"/api/v1/questions/{question_id}").json()
        results["same_subject_content_change"] = {
            "status": response_d.status_code,
            "stem": after_d["content"]["stemMarkdown"],
            "linksAfter": [link["knowledgePointId"] for link in after_d["knowledgeLinks"]],
            "revisionAdvanced": after_d["revision"] > current["revision"],
        }
        if not (
            response_d.status_code == 200
            and after_d["revision"] > current["revision"]
            and [link["knowledgePointId"] for link in after_d["knowledgeLinks"]]
            == [math_point.point_id]
            and "修改后的题干" in after_d["content"]["stemMarkdown"]
        ):
            failures.append("D: 同学科改内容未保留关联或未生效")
    finally:
        probe.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p07_rv07_subject_links", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in (
        "baseline",
        "subject_change_without_links",
        "subject_change_explicit_clear",
        "subject_change_explicit_replace",
        "explicit_wrong_subject_link",
        "same_subject_content_change",
    ):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:360])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
