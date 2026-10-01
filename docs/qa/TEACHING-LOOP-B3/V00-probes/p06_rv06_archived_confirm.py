"""V00 · RV06 探针：确认时复核已归档知识点（原卷 + 题库两条发布路径）。

缺陷回顾（B2-RV06）：草稿绑定时核 active，确认时不再复核；「绑定活跃 → 归档 → 确认」
仍成功发布新的已确认关联。

断言：
  A. 原卷：草稿绑定 → 归档 → 确认 409 KNOWLEDGE_ARCHIVED；零新增已确认修订；
     历史已确认修订的关联仍可读（名称快照不变）；
  B. 题库：草稿绑定 → 归档 → 确认 409 KNOWLEDGE_ARCHIVED；零新增题目；
     历史已确认题目的关联仍可读；
  C. 控制组：知识点保持 active 时两条路径都能确认成功（守卫不放行一切）。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p06_rv06_archived_confirm.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00_papers import PapersProbe, items_payload_from_view  # noqa: E402

from app.main import create_app  # noqa: E402
from app.services.question_bank.service import build_question_bank_service  # noqa: E402
from tests.papers_support import build_paper_docx  # noqa: E402

QB_DOC = """1. 下列说法正确的是（ ）
A. 甲
B. 乙
C. 丙
D. 丁
答案：A
解析：甲说法正确。
"""


def confirm_paper(probe: PapersProbe, paper_id: str, submission: str):
    revision = probe.client.get(f"/api/v1/papers/{paper_id}").json()["revision"]
    return probe.client.post(
        f"/api/v1/papers/{paper_id}/confirm",
        json={"expectedRevision": revision, "submissionId": submission},
    )


def prepare_bound_paper(probe: PapersProbe, point_id: str, *, title: str) -> tuple[str, str]:
    """导入 → 绑定知识点并解决阻断问题 → 返回 (paperId, revisionId)。"""
    docx = build_paper_docx(V.PROBE_TMP / f"{title}.docx", with_unknown_object=True)
    imported = probe.import_paper(Path(docx).read_bytes(), title=title)
    assert imported.status_code == 201, imported.text
    paper_id = imported.json()["paper"]["paperId"]
    revision = imported.json()["revision"]
    blocks = revision["blocks"]
    paragraph = next(b for b in blocks if b["kind"] == "paragraph")
    items = items_payload_from_view(revision["items"], content={})
    for entry in items:
        entry["knowledge"] = (
            [{"knowledgePointId": point_id, "role": "primary"}] if entry["isScored"] else []
        )
    issues = [
        {
            "issueId": issue["issueId"],
            "status": "resolved",
            "resolution": {
                "kind": "supplement_text",
                "targetBlockId": issue.get("blockId") or paragraph["blockId"],
                "text": "补录：教师补充的图形说明。",
            },
        }
        for issue in revision["issues"]
        if issue["status"] == "open"
    ]
    patched = probe.client.patch(
        f"/api/v1/papers/{paper_id}/draft",
        json={
            "expectedRevision": probe.client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
            "items": items,
            "issues": issues,
        },
    )
    assert patched.status_code == 200, patched.text
    return paper_id, revision["paperRevisionId"]


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    probe = PapersProbe(V.PROBE_TMP / "rv06_papers")
    settings = probe.settings
    app = probe.app
    qb = build_question_bank_service(
        app.state.question_bank,
        settings,
        model_resolver=probe.resolver,
        knowledge_catalog=app.state.knowledge,
        coordinator=app.state.publication_coordinator,
        job_engine=app.state.job_engine,
    )
    app.state.question_bank_service = qb
    client = probe.client  # papers 与 QB 路由在同一个 app / 同一个 TestClient 上
    try:
        active_point = probe.add_point(code="kp-active", name="一次函数")
        archive_candidate = probe.add_point(code="kp-archive", name="待归档知识点")

        def archive_point(point_id: str) -> dict[str, Any]:
            current = client.get(f"/api/v1/knowledge-points/{point_id}")
            assert current.status_code == 200, current.text
            response = client.post(
                f"/api/v1/knowledge-points/{point_id}/archive",
                json={"expectedRevision": current.json()["revision"]},
            )
            return {"status": response.status_code, "body": response.json() if response.status_code != 200 else None}

        # ---- C（原卷控制组）：active 时确认成功，且历史关联可读
        paper_ok, revision_ok = prepare_bound_paper(probe, active_point.point_id, title="rv06-ok")
        confirmed = confirm_paper(probe, paper_ok, "rv06-paper-ok")
        assert confirmed.status_code == 200, confirmed.text
        content_ok = client.get(
            f"/api/v1/papers/{paper_ok}/revisions/{revision_ok}/content"
        ).json()
        links_before_archive = [
            link
            for item in content_ok["items"]
            for link in item["knowledge"]
        ]
        archive_active = archive_point(active_point.point_id)
        content_after_archive = client.get(
            f"/api/v1/papers/{paper_ok}/revisions/{revision_ok}/content"
        ).json()
        links_after_archive = [
            {
                "knowledgePointId": link["knowledgePointId"],
                "knowledgeNameSnapshot": link["knowledgeNameSnapshot"],
                "source": link["source"],
            }
            for item in content_after_archive["items"]
            for link in item["knowledge"]
        ]
        results["papers_control_confirmed_then_archived"] = {
            "confirmStatus": confirmed.status_code,
            "linksBeforeArchive": len(links_before_archive),
            "archiveStatus": archive_active["status"],
            "linksAfterArchive": len(links_after_archive),
            "namesAfterArchive": sorted({row["knowledgeNameSnapshot"] for row in links_after_archive}),
        }
        if not (
            confirmed.status_code == 200
            and archive_active["status"] == 200
            and len(links_after_archive) == len(links_before_archive) > 0
        ):
            failures.append("A0: 历史已确认关联在归档后不可读")

        # ---- A（原卷缺陷场景）：绑定归档候选（active）→ 归档 → 确认
        paper_bad, revision_bad = prepare_bound_paper(
            probe, archive_candidate.point_id, title="rv06-archived"
        )
        confirmed_before = [
            row["id"]
            for row in probe.raw_rows(
                "SELECT id FROM paper_revisions WHERE paper_id = ? AND state = 'confirmed'",
                (paper_bad,),
            )
        ]
        archived = archive_point(archive_candidate.point_id)
        blocked = confirm_paper(probe, paper_bad, "rv06-paper-archived")
        confirmed_after = [
            row["id"]
            for row in probe.raw_rows(
                "SELECT id FROM paper_revisions WHERE paper_id = ? AND state = 'confirmed'",
                (paper_bad,),
            )
        ]
        results["papers_archived_confirm"] = {
            "archiveStatus": archived["status"],
            "confirmStatus": blocked.status_code,
            "confirmCode": blocked.json().get("code"),
            "issues": (blocked.json().get("details") or {}).get("issues"),
            "confirmedRevisionsBefore": len(confirmed_before),
            "confirmedRevisionsAfter": len(confirmed_after),
        }
        if not (
            archived["status"] == 200
            and blocked.status_code == 409
            and blocked.json().get("code") == "KNOWLEDGE_ARCHIVED"
            and len(confirmed_after) == 0
        ):
            failures.append("A: 原卷确认未复核已归档知识点或发生了发布")

        # ---- 题库控制组：active 时确认成功
        def upload_and_review(point_id: str | None, *, submission_ok: bool = True):
            response = client.post(
                "/api/v1/question-imports",
                files={"file": ("q.md", QB_DOC.encode("utf-8"), "text/markdown")},
                data={"subjectId": "math", "gradeId": "grade-7"},
            )
            assert response.status_code == 201, response.text
            import_id = response.json()["importId"]
            draft = client.get(f"/api/v1/question-imports/{import_id}").json()["drafts"][0]
            links = (
                [{"knowledgePointId": point_id, "role": "primary"}] if point_id else []
            )
            # ① 关联整表替换（内容/分类保持当前值）→ 强制回到 needs_review
            linked = client.patch(
                f"/api/v1/question-drafts/{draft['draftId']}",
                json={
                    "expectedRevision": draft["revision"],
                    "content": draft["content"],
                    "metadata": {**draft["metadata"], "subjectId": "math"},
                    "knowledgeLinks": links,
                },
            )
            assert linked.status_code == 200, linked.text
            # ② 单独标记已校对（内容/分类/关联都不再变化，review_state 才会生效）
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
            assert reviewed.json()["reviewState"] == "reviewed", reviewed.text
            return import_id, reviewed.json()

        qb_point = probe.add_point(code="kp-qb", name="题库知识点")
        import_ok, draft_ok = upload_and_review(qb_point.point_id)
        confirm_ok = client.post(
            f"/api/v1/question-imports/{import_ok}/confirm",
            json={
                "submissionId": "rv06-qb-ok",
                "importId": import_ok,
                "items": [
                    {"draftId": draft_ok["draftId"], "expectedDraftRevision": draft_ok["revision"]}
                ],
                "duplicateResolutions": [],
            },
        )
        question_ids = (confirm_ok.json().get("confirmedQuestionIds") or []) if confirm_ok.status_code == 200 else []
        archive_qb_point = archive_point(qb_point.point_id)
        question_after = (
            client.get(f"/api/v1/questions/{question_ids[0]}").json() if question_ids else None
        )
        results["qb_control_confirmed_then_archived"] = {
            "confirmStatus": confirm_ok.status_code,
            "confirmedCount": len(question_ids),
            "archiveStatus": archive_qb_point["status"],
            "linksAfterArchive": (question_after or {}).get("knowledgeLinks"),
        }
        if not (
            confirm_ok.status_code == 200
            and question_ids
            and archive_qb_point["status"] == 200
            and (question_after or {}).get("knowledgeLinks")
        ):
            failures.append("B0: 题库历史已确认关联在归档后不可读")

        # ---- B（题库缺陷场景）：绑定 active → 归档 → 确认
        qb_point2 = probe.add_point(code="kp-qb-2", name="待归档题库知识点")
        import_bad, draft_bad = upload_and_review(qb_point2.point_id)
        archived2 = archive_point(qb_point2.point_id)
        confirm_bad = client.post(
            f"/api/v1/question-imports/{import_bad}/confirm",
            json={
                "submissionId": "rv06-qb-archived",
                "importId": import_bad,
                "items": [
                    {"draftId": draft_bad["draftId"], "expectedDraftRevision": draft_bad["revision"]}
                ],
                "duplicateResolutions": [],
            },
        )
        questions_total = client.get("/api/v1/questions", params={"limit": 1}).json()["total"]
        results["qb_archived_confirm"] = {
            "archiveStatus": archived2["status"],
            "confirmStatus": confirm_bad.status_code,
            "confirmCode": confirm_bad.json().get("code"),
            "issues": (confirm_bad.json().get("details") or {}).get("issues"),
            "questionsTotal": questions_total,
        }
        if not (
            archived2["status"] == 200
            and confirm_bad.status_code == 409
            and confirm_bad.json().get("code") == "KNOWLEDGE_ARCHIVED"
            and questions_total == len(question_ids)
        ):
            failures.append("B: 题库确认未复核已归档知识点或发生了发布")
    finally:
        probe.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p06_rv06_archived_confirm", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in (
        "papers_control_confirmed_then_archived",
        "papers_archived_confirm",
        "qb_control_confirmed_then_archived",
        "qb_archived_confirm",
    ):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:400])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
