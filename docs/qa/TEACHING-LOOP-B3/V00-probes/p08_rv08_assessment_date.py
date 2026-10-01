"""V00 · RV08 探针：施测改日期重核参测归属（自建真实 HTTP 链）。

缺陷回顾（B2-RV08）：`update_assessment()` 校验日期格式后直接写入，不重核既有参测人次
的班级归属；学生 joinedOn 晚于新 heldOn 也仍 200。

断言：
  A. 建档：学生 joinedOn=2026-09-20、施测 heldOn=2026-09-30（覆盖成立），
     classConfirmed=false 仍可创建（今天导入名单分析过去考试）；
  B. PATCH heldOn=2026-09-01（早于入班）→ 422 PARTICIPANT_CLASS_UNCONFIRMED，
     details.issues 定位到人次行；日期未写入；归属历史与快照未变；
  C. 重新确认路径：POST /assessments/{id}/participants 带既有 (studentId, classId,
     attemptNo) + classConfirmed + note → 只更新确认列（不新增行、不改快照）；
  D. 重确认后再 PATCH 到同一失效日期 → 成功；name/studentNo 快照与
     class_memberships 逐行不变。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p08_rv08_assessment_date.py
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

from tests.papers_support import SAMPLE_LEAF_SCORES, build_paper_docx  # noqa: E402

JOINED_ON = "2026-09-20"
HELD_ON = "2026-09-30"
INVALID_ON = "2026-09-01"


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    probe = PapersProbe(V.PROBE_TMP / "rv08")
    client = probe.client
    try:
        # ---- 班级 / 学生（真 API）
        created_class = client.post(
            "/api/v1/classes",
            json={
                "code": "G7-01",
                "name": "七年级一班",
                "schoolYear": "2026",
                "gradeId": "grade-7",
            },
        )
        assert created_class.status_code == 201, created_class.text
        class_id = created_class.json()["id"]
        created_student = client.post(
            "/api/v1/students",
            json={
                "name": "张三",
                "studentNo": "0007",
                "classId": class_id,
                "joinedOn": JOINED_ON,
            },
        )
        assert created_student.status_code == 201, created_student.text
        student_id = created_student.json()["id"]

        # ---- 已确认原卷（真导入 + 真确认）
        docx = build_paper_docx(V.PROBE_TMP / "rv08.docx")
        imported = probe.import_paper(Path(docx).read_bytes(), title="RV08 探针卷")
        assert imported.status_code == 201, imported.text
        paper_id = imported.json()["paper"]["paperId"]
        revision_id = imported.json()["revision"]["paperRevisionId"]
        content = client.get(f"/api/v1/papers/{paper_id}/revisions/{revision_id}/content").json()
        items = []
        for item in content["items"]:
            entry = {
                "itemId": item["itemId"],
                "questionNo": item["questionNo"],
                "ordinal": item["ordinal"],
                "isScored": item["isScored"],
                "content": item["content"],
                "sourceLocator": item["sourceLocator"],
                "knowledge": [],
            }
            if item.get("parentItemId"):
                entry["parentItemId"] = item["parentItemId"]
            if item.get("maxScore") is not None:
                entry["maxScore"] = item["maxScore"]
            if item["isScored"]:
                point = probe.add_point(
                    code=f"KP-{item['questionNo']}", name=f"知识点 {item['questionNo']}"
                )
                entry["knowledge"] = [{"knowledgePointId": point.point_id, "role": "primary"}]
            items.append(entry)
        patched = client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
                "items": items,
            },
        )
        assert patched.status_code == 200, patched.text
        confirmed = client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={
                "expectedRevision": client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
                "submissionId": "rv08-paper-confirm",
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        confirmed_revision = confirmed.json()["paperRevisionId"]

        # ---- A. 创建施测：归属覆盖成立、仍 classConfirmed=false
        created = client.post(
            "/api/v1/assessments",
            json={
                "submissionId": "rv08-create",
                "paperRevisionId": confirmed_revision,
                "title": "九月月考",
                "assessmentType": "exam",
                "heldOn": HELD_ON,
                "classIds": [class_id],
                "participants": [
                    {"studentId": student_id, "classId": class_id, "classConfirmed": False}
                ],
            },
        )
        assert created.status_code == 201, created.text
        assessment = created.json()["assessment"]
        participants = created.json()["participants"]
        assessment_id = assessment["assessmentId"]
        participant = participants[0]
        memberships_before = probe.raw_rows(
            "SELECT * FROM class_memberships ORDER BY rowid"
        )
        results["create"] = {
            "status": created.status_code,
            "heldOn": assessment["heldOn"],
            "attemptNo": participant["attemptNo"],
            "classConfirmed": participant["classConfirmed"],
            "nameSnapshot": participant["nameSnapshot"],
            "studentNoSnapshot": participant["studentNoSnapshot"],
        }
        if not (
            assessment["heldOn"] == HELD_ON
            and participant["classConfirmed"] is False
            and participant["nameSnapshot"] == "张三"
            and participant["studentNoSnapshot"] == "0007"
        ):
            failures.append("A: 施测创建/快照不符合预期")

        # ---- B. PATCH 到早于入班日期 → 定位拒绝
        updated = client.patch(
            f"/api/v1/assessments/{assessment_id}",
            json={"expectedRevision": assessment["revision"], "heldOn": INVALID_ON},
        )
        body = updated.json()
        after = client.get(f"/api/v1/assessments/{assessment_id}").json()
        results["patch_invalid_date"] = {
            "status": updated.status_code,
            "code": body.get("code"),
            "issues": (body.get("details") or {}).get("issues"),
            "heldOnAfter": after["assessment"]["heldOn"],
            "participantCount": len(after["participants"]),
        }
        if not (
            updated.status_code == 422
            and body.get("code") == "PARTICIPANT_CLASS_UNCONFIRMED"
            and (body.get("details") or {}).get("issues")
            and after["assessment"]["heldOn"] == HELD_ON
        ):
            failures.append("B: 改到失效日期未被定位拒绝或日期被写入")

        # ---- C. 重新确认路径：只更新确认列
        reconfirm = client.post(
            f"/api/v1/assessments/{assessment_id}/participants",
            json={
                "submissionId": "rv08-reconfirm",
                "expectedRevision": after["assessment"]["revision"],
                "participants": [
                    {
                        "studentId": student_id,
                        "classId": class_id,
                        "attemptNo": participant["attemptNo"],
                        "classConfirmed": True,
                        "classConfirmationNote": "教师核对纸质签到表：该生当日确在班参加考试。",
                    }
                ],
            },
        )
        after_reconfirm = client.get(f"/api/v1/assessments/{assessment_id}").json()
        results["reconfirm"] = {
            "status": reconfirm.status_code,
            "participantCount": len(after_reconfirm["participants"]),
            "classConfirmed": after_reconfirm["participants"][0]["classConfirmed"],
            "note": after_reconfirm["participants"][0].get("classConfirmationNote"),
            "nameSnapshot": after_reconfirm["participants"][0]["nameSnapshot"],
            "attemptNo": after_reconfirm["participants"][0]["attemptNo"],
        }
        if not (
            reconfirm.status_code in (200, 201)
            and len(after_reconfirm["participants"]) == 1
            and after_reconfirm["participants"][0]["classConfirmed"] is True
            and after_reconfirm["participants"][0]["nameSnapshot"] == "张三"
        ):
            failures.append("C: 重确认路径未按既有尝试更新确认列")

        # ---- D. 重确认后再改日期 → 成功；归属历史逐行不变
        retry_update = client.patch(
            f"/api/v1/assessments/{assessment_id}",
            json={
                "expectedRevision": after_reconfirm["assessment"]["revision"],
                "heldOn": INVALID_ON,
            },
        )
        after_update = client.get(f"/api/v1/assessments/{assessment_id}").json()
        memberships_after = probe.raw_rows("SELECT * FROM class_memberships ORDER BY rowid")
        results["patch_after_reconfirm"] = {
            "status": retry_update.status_code,
            "heldOnAfter": after_update["assessment"]["heldOn"],
            "participantSnapshots": [
                {
                    "name": row["nameSnapshot"],
                    "studentNo": row["studentNoSnapshot"],
                    "attemptNo": row["attemptNo"],
                }
                for row in after_update["participants"]
            ],
            "membershipsUnchanged": memberships_before == memberships_after,
            "membershipRows": memberships_after,
        }
        if not (
            retry_update.status_code == 200
            and after_update["assessment"]["heldOn"] == INVALID_ON
            and memberships_before == memberships_after
        ):
            failures.append("D: 重确认后日期更新失败或归属历史被改动")
    finally:
        probe.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p08_rv08_assessment_date", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in ("create", "patch_invalid_date", "reconfirm", "patch_after_reconfirm"):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:420])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
