"""V00 · B3-A2 失败路径：承认 422 / 三版本 409 / 越界 422 / 重放幂等。

自建探针（真装配 + 真触发器）。覆盖：
  1. SCORE_ACKNOWLEDGEMENT_MISMATCH：cellCount / missing 人次 / absences / previewVersion 四类，带定位；
  2. expectedImportRevision 与 expectedAssessmentRevision 各自 409 + details.currentRevision；
     baseScoreRevisionId 不符 → 409 SCORE_BASE_REVISION_CONFLICT（带 issue 定位 baseScoreRevisionId；
     与 docs/API.md「带 currentRevision」的注记范围一致，见报告观察项）；
  3. 越界：SCORE_CELL_OVER_MAX / SCORE_CELL_INVALID 带原表 row/column，PATCH 失败不递增 revision；
  4. 同 submissionId 重放返回原修订、不新增版本；不同 submissionId 确认已确认批次 → 409。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p21_failure_paths.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

LEAVES = (("Q1", 200), ("Q2", 300), ("Q3", 500))
HEADER = ("学号", "姓名", "Q1", "Q2", "Q3")
ROWS = (("0001", "A", 2, 2, 5), ("0002", "B", 2, 3, None), ("0003", "C", None, None, None))


def setup_scene(harness: B.Harness, tag: str = "fail"):
    scene = harness.sample_scene(
        tag=tag,
        leaves=LEAVES,
        students=(("A", "0001", "present"), ("B", "0002", "present"), ("C", "0003", "absent")),
    )
    path = B.write_xlsx(Path(harness.settings.data_dir) / f"{tag}.xlsx", HEADER, ROWS)
    upload = harness.upload_scores(scene["assessment"]["assessmentId"], path)
    assert upload.status_code == 201, upload.text
    return scene, upload.json()


def base_confirm_body(view, scene, *, submission_id, base=..., missing=None, absences=None, preview_version=None, assessment_revision=None):
    assessment_id = view["assessmentId"]
    ack_absences = (
        absences
        if absences is not None
        else [{"classId": scene["class"]["id"], "participantIds": [scene["byName"]["C"]["participantId"]]}]
    )
    ack_missing = (
        missing
        if missing is not None
        else {"participantIds": [scene["byName"]["B"]["participantId"]], "cellCount": 1}
    )
    return {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": (
            assessment_revision if assessment_revision is not None else scene["assessment"]["revision"]
        ),
        "baseScoreRevisionId": (view.get("baseScoreRevisionId") if base is ... else base),
        "previewVersion": preview_version if preview_version is not None else view["previewVersion"],
        "submissionId": submission_id,
        "absences": ack_absences,
        "missing": ack_missing,
    }


def live_body(harness: B.Harness, view, scene, *, submission_id: str, **kw) -> dict:
    """按**当前**施测 revision 生成确认体（避免上一次确认推进版本导致的假冲突）。"""
    revision = harness.assessment(view["assessmentId"])["assessment"]["revision"]
    return base_confirm_body(view, scene, submission_id=submission_id, assessment_revision=revision, **kw)


def main() -> int:
    verdict = B.Verdict("p21_failure_paths")

    # ================================================================= H1 承认 422 与越界
    with B.Harness(tag="fail1") as harness:
        scene, view = setup_scene(harness, "fail1")
        import_id = view["importId"]
        verdict.expect("上传成功且 missing=1", view["missingCellCount"], 1)
        verdict.expect("上传后 score_revisions=0", harness.count("score_revisions"), 0)

        def expect_ack_fail(label: str, body: dict, *, field: str | None = None) -> None:
            response = harness.confirm_import(import_id, body)
            entry = {"label": label, "status": response.status_code}
            verdict.expect(f"{label} → 422", response.status_code, 422)
            payload = response.json()
            verdict.expect(f"{label} 错误码", payload.get("code"), "SCORE_ACKNOWLEDGEMENT_MISMATCH")
            issues = (payload.get("details") or {}).get("issues") or []
            verdict.check(f"{label} 带 issues 定位", bool(issues), issues[:2])
            if field is not None:
                verdict.check(
                    f"{label} 定位 field={field}",
                    any(issue.get("field") == field for issue in issues),
                    [i.get("field") for i in issues],
                )
            verdict.expect(f"{label} 确认后仍未写入修订", harness.count("score_revisions"), 0)

        # 1a. missing cellCount 不符
        body = live_body(harness, view, scene, submission_id="ack-1")
        body["missing"]["cellCount"] = 2
        expect_ack_fail("missing cellCount=2", body, field="cellCount")

        # 1b. missing 人次不符
        body = live_body(harness, view, scene, submission_id="ack-2")
        body["missing"]["participantIds"] = ["nobody"]
        expect_ack_fail("missing 人次不含 B", body, field="participantIds")

        # 1c. absences 未承认班级
        body = live_body(harness, view, scene, submission_id="ack-3", absences=[])
        expect_ack_fail("absences 为空", body, field="absences")

        # 1d. previewVersion 过期
        body = live_body(harness, view, scene, submission_id="ack-4", preview_version=view["previewVersion"] + 1)
        expect_ack_fail("previewVersion 过期", body, field="previewVersion")

        # 2. expectedImportRevision 409 + currentRevision
        body = live_body(harness, view, scene, submission_id="rev-1")
        body["expectedImportRevision"] = view["revision"] + 1
        response = harness.confirm_import(import_id, body)
        verdict.expect("import revision 409", response.status_code, 409)
        payload = response.json()
        verdict.expect("import revision 错误码", payload.get("code"), "SCORE_IMPORT_REVISION_CONFLICT")
        verdict.expect(
            "import revision details.currentRevision",
            (payload.get("details") or {}).get("currentRevision"),
            view["revision"],
        )

        # 3. 越界/非法单元格（PATCH）→ 422 + 物理坐标，revision 不递增
        rev_before = view["revision"]
        over = harness.patch_import(
            import_id,
            {"expectedRevision": rev_before, "rows": [{"rowNo": 2, "cells": [{"row": 2, "column": "C", "text": "999"}]}]},
        )
        verdict.expect("越界 PATCH 422", over.status_code, 422)
        over_payload = over.json()
        verdict.expect("越界错误码", over_payload.get("code"), "SCORE_CELL_OVER_MAX")
        over_issues = (over_payload.get("details") or {}).get("issues") or []
        verdict.check(
            "越界 issue 带原表 row=2/column=C",
            any(issue.get("row") == 2 and issue.get("column") == "C" for issue in over_issues),
            over_issues[:2],
        )
        current = harness.import_view(import_id).json()
        verdict.expect("越界 PATCH 后 revision 不递增", current["revision"], rev_before)

        neg = harness.patch_import(
            import_id,
            {"expectedRevision": rev_before, "rows": [{"rowNo": 3, "cells": [{"row": 3, "column": "C", "text": "-1"}]}]},
        )
        verdict.expect("负数 PATCH 422", neg.status_code, 422)
        verdict.expect("负数错误码", neg.json().get("code"), "SCORE_CELL_INVALID")
        verdict.check(
            "负数 issue 带原表 row=3/column=C",
            any(
                issue.get("row") == 3 and issue.get("column") == "C"
                for issue in (neg.json().get("details") or {}).get("issues") or []
            ),
            (neg.json().get("details") or {}).get("issues"),
        )

        # 4. 正常确认 → 重放
        body = live_body(harness, view, scene, submission_id="replay-1")
        confirm = harness.confirm_import(import_id, body)
        verdict.expect("首次确认 200", confirm.status_code, 200)
        first = confirm.json()
        verdict.expect("首次 replayed=false", first.get("replayed"), False)
        verdict.expect("一次确认后 score_revisions=1", harness.count("score_revisions"), 1)
        assessment_rev = harness.assessment(scene["assessment"]["assessmentId"])["assessment"]["revision"]

        replay = harness.confirm_import(import_id, body)
        verdict.expect("重放 200", replay.status_code, 200)
        second = replay.json()
        verdict.expect("重放 replayed=true", second.get("replayed"), True)
        verdict.expect("重放返回原修订", second.get("revisionId"), first.get("revisionId"))
        verdict.expect("重放不新增版本", harness.count("score_revisions"), 1)
        verdict.expect(
            "重放不改施测版本",
            harness.assessment(scene["assessment"]["assessmentId"])["assessment"]["revision"],
            assessment_rev,
        )

        # 4b. 换 submissionId 再确认已确认批次 → 409 NOT_EDITABLE
        other = live_body(harness, view, scene, submission_id="replay-2")
        other["expectedImportRevision"] = current["revision"]
        response = harness.confirm_import(import_id, other)
        verdict.expect("换 submissionId 409", response.status_code, 409)
        verdict.expect("换 submissionId 错误码", response.json().get("code"), "SCORE_IMPORT_NOT_EDITABLE")

    # ================================================================= H2 施测版本 409
    with B.Harness(tag="fail2") as harness:
        scene, view = setup_scene(harness, "fail2")
        import_id = view["importId"]
        assessment_id = scene["assessment"]["assessmentId"]
        old_revision = scene["assessment"]["revision"]
        # 新增一名学生参测（真实 participants 维护接口）→ 施测 revision+1
        g = harness.create_student(name="G", student_no="0007", class_id=scene["class"]["id"], joined_on=B.days_before(30))
        added = harness.add_participants(
            assessment_id,
            expected_revision=old_revision,
            submission_id="add-g",
            student_id=g["id"],
            class_id=scene["class"]["id"],
        )
        verdict.expect("补录人次 200", added.status_code, 200)
        new_revision = harness.assessment(assessment_id)["assessment"]["revision"]
        verdict.expect("施测 revision 递增", new_revision, old_revision + 1)

        body = base_confirm_body(view, scene, submission_id="assess-1", assessment_revision=old_revision)
        response = harness.confirm_import(import_id, body)
        verdict.expect("assessment revision 409", response.status_code, 409)
        payload = response.json()
        verdict.expect(
            "assessment revision 错误码", payload.get("code"), "SCORE_ASSESSMENT_REVISION_CONFLICT"
        )
        verdict.expect(
            "assessment revision details.currentRevision",
            (payload.get("details") or {}).get("currentRevision"),
            new_revision,
        )
        verdict.note(
            "assessment 冲突 details="
            + __import__("json").dumps(payload.get("details"), ensure_ascii=False)
        )
        verdict.expect("确认未写入", harness.count("score_revisions"), 0)

    # ================================================================= H3 base 版本 409
    with B.Harness(tag="fail3") as harness:
        scene, view = setup_scene(harness, "fail3")
        assessment_id = scene["assessment"]["assessmentId"]

        # 3a. 首版 base 非 null（bogus）→ 409 SCORE_BASE_REVISION_CONFLICT
        body = live_body(harness, view, scene, submission_id="base-1", base="bogus-revision")
        response = harness.confirm_import(view["importId"], body)
        verdict.expect("首版 base 不符 409", response.status_code, 409)
        payload = response.json()
        verdict.expect("首版 base 错误码", payload.get("code"), "SCORE_BASE_REVISION_CONFLICT")
        verdict.note(
            "首版 base 冲突 details="
            + __import__("json").dumps(payload.get("details"), ensure_ascii=False)
        )
        verdict.check(
            "base 冲突带 issue 定位 baseScoreRevisionId",
            any(
                issue.get("field") == "baseScoreRevisionId"
                for issue in (payload.get("details") or {}).get("issues") or []
            ),
            (payload.get("details") or {}).get("issues"),
        )

        # 3b. 确认 v1（正常）
        confirm1 = harness.confirm_import(
            view["importId"], live_body(harness, view, scene, submission_id="base-2")
        )
        verdict.expect("v1 确认 200", confirm1.status_code, 200)
        v1 = confirm1.json()["revisionId"]

        # 3c. 上传 I2（base 自动=v1）→ 确认 v2
        path = Path(harness.settings.data_dir) / "fail3b.xlsx"
        B.write_xlsx(path, HEADER, ROWS)
        upload2 = harness.upload_scores(assessment_id, path)
        verdict.expect("I2 上传 200", upload2.status_code, 201)
        view2 = upload2.json()
        verdict.expect("I2 base 自动=v1", view2["baseScoreRevisionId"], v1)
        confirm2 = harness.confirm_import(
            view2["importId"], live_body(harness, view2, scene, submission_id="base-3")
        )
        verdict.expect("v2 确认 200", confirm2.status_code, 200)
        v2 = confirm2.json()["revisionId"]
        verdict.expect("v2 与 v1 不同", v2 != v1, True)

        # 3d. 上传 I3：base 自动=v2；确认时故意给 v1 → 409（导入冻结点 v2 ≠ 请求 v1）
        upload3 = harness.upload_scores(assessment_id, path)
        verdict.expect("I3 上传 201", upload3.status_code, 201)
        view3 = upload3.json()
        verdict.expect("I3 base 自动=v2", view3["baseScoreRevisionId"], v2)
        stale = live_body(harness, view3, scene, submission_id="base-4", base=v1)
        response = harness.confirm_import(view3["importId"], stale)
        verdict.expect("确认 base 过期 409", response.status_code, 409)
        verdict.expect("确认 base 过期错误码", response.json().get("code"), "SCORE_BASE_REVISION_CONFLICT")
        verdict.expect("v3 未写入（仍 2 个修订）", harness.count("score_revisions"), 2)

        # 3e. 上传时显式给过期 base → 409（服务端拒绝，不落批次）
        upload_stale = harness.upload_scores(assessment_id, path, base_score_revision_id=v1)
        verdict.expect("上传过期 base 409", upload_stale.status_code, 409)
        verdict.expect("上传过期 base 错误码", upload_stale.json().get("code"), "SCORE_BASE_REVISION_CONFLICT")

    return verdict.finish(path=HERE / "p21_failure_paths.json")


if __name__ == "__main__":
    sys.exit(main())
