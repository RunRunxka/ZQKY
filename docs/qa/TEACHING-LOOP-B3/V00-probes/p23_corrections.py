"""V00 · B3-A4 修正：base=当前 active、新完整版本 + 审计、并发双修正只成功一个。

自建探针。覆盖：
  1. base 必须是当前 active；base 不存在 → 404 SCORE_REVISION_NOT_FOUND；
     active 被清空 → 409 SCORE_NO_BASE_REVISION；过期 base → 409 SCORE_BASE_REVISION_CONFLICT；
  2. 修正生成新完整版本（全矩阵 + **修正当时**参测快照）并落审计（原值/新值/理由/坐标）；
  3. 修正请求校验：重复条目/未变化值/缺 scoreText/多余 scoreText/未知人次/未知小题/超满分；
  4. 同 submissionId 重放不新增版本；并发双修正恰好一个成功、一个 409，只前进一个版本；
  5. 原修订不可变，新增参测人次后历史修订仍按自己的快照可读。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p23_corrections.py
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

LEAVES = (("Q1", 200), ("Q2", 300), ("Q3", 500))
HEADER = ("学号", "姓名", "Q1", "Q2", "Q3")
ROWS = (
    ("0001", "A", 2, 2, 5),
    ("0002", "B", 2, 3, None),
    ("0003", "C", None, None, None),
    ("0004", "D", 0, 3, 5),
)


def confirm_v1(harness: B.Harness, tag: str):
    scene = harness.sample_scene(
        tag=tag,
        leaves=LEAVES,
        students=(
            ("A", "0001", "present"),
            ("B", "0002", "present"),
            ("C", "0003", "absent"),
            ("D", "0004", "present"),
        ),
    )
    path = B.write_xlsx(Path(harness.settings.data_dir) / f"{tag}.xlsx", HEADER, ROWS)
    upload = harness.upload_scores(scene["assessment"]["assessmentId"], path)
    assert upload.status_code == 201, upload.text
    view = upload.json()
    body = {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": harness.assessment(scene["assessment"]["assessmentId"])["assessment"]["revision"],
        "baseScoreRevisionId": None,
        "previewVersion": view["previewVersion"],
        "submissionId": f"{tag}-v1",
        "absences": [{"classId": scene["class"]["id"], "participantIds": [scene["byName"]["C"]["participantId"]]}],
        "missing": {"participantIds": [scene["byName"]["B"]["participantId"]], "cellCount": 1},
    }
    confirm = harness.confirm_import(view["importId"], body)
    assert confirm.status_code == 200, confirm.text
    return scene, upload.json(), confirm.json()


def correction_body(harness, scene, *, base: str, submission_id: str, corrections: list, reason: str = "教师复核后更正") -> dict:
    assessment_id = scene["assessment"]["assessmentId"]
    revision = harness.assessment(assessment_id)["assessment"]["revision"]
    return {
        "baseScoreRevisionId": base,
        "expectedAssessmentRevision": revision,
        "submissionId": submission_id,
        "reason": reason,
        "corrections": corrections,
    }


def main() -> int:
    verdict = B.Verdict("p23_corrections")

    with B.Harness(tag="corr") as harness:
        scene, import_view, confirm1 = confirm_v1(harness, "corr")
        assessment_id = scene["assessment"]["assessmentId"]
        v1 = confirm1["revisionId"]
        b_pid = scene["byName"]["B"]["participantId"]
        q3 = scene["paper"]["itemIds"][2]

        # ---- 0. base 不存在 → 404
        missing_base = harness.correct_scores(
            assessment_id,
            correction_body(
                harness,
                scene,
                base="no-such-revision",
                submission_id="c-404",
                corrections=[
                    {"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "3"}
                ],
            ),
        )
        verdict.expect("base 不存在 404", missing_base.status_code, 404)
        verdict.expect("base 不存在错误码", missing_base.json().get("code"), "SCORE_REVISION_NOT_FOUND")

        # ---- 1. 修正 B 的 Q3：missing → recorded(3 分)
        response = harness.correct_scores(
            assessment_id,
            correction_body(
                harness,
                scene,
                base=v1,
                submission_id="c-1",
                corrections=[
                    {"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "3"}
                ],
            ),
        )
        verdict.expect("修正 200", response.status_code, 200)
        corrected = response.json()
        v2 = corrected["revisionId"]
        verdict.expect("新版本 version=2", corrected["version"], 2)
        verdict.expect("新版本 base=v1", corrected["baseRevisionId"], v1)
        verdict.expect("active 指向新版本", corrected["activeScoreRevisionId"], v2)
        verdict.expect("修正 replayed=false", corrected.get("replayed"), False)

        # 新版本矩阵与快照
        matrix2 = harness.score_matrix(v2, limit=200).json()
        verdict.expect("v2 total=4", matrix2["total"], 4)
        verdict.expect("v2 missingCellCount=0（B 已补齐）", matrix2["missingCellCount"], 0)
        table2 = B.matrix_map(matrix2)
        b_cells = table2["B"]["cells"]
        verdict.expect("v2 B 的 Q3 = recorded 300", (b_cells[q3]["status"], b_cells[q3]["scoreUnits"]), ("recorded", 300))
        verdict.expect("v2 B.totalUnits=800", table2["B"]["participant"]["totalUnits"], 800)
        verdict.expect("v2 A.totalUnits 不变 900", table2["A"]["participant"]["totalUnits"], 900)

        # 审计
        audit = harness.raw(
            "SELECT * FROM score_revision_corrections WHERE revision_id = ? ORDER BY seq", (v2,)
        )
        verdict.expect("审计 1 条", len(audit), 1)
        row = audit[0]
        verdict.expect(
            "审计原值/新值/理由/坐标",
            {
                "participant_id": row["participant_id"],
                "item_id": row["item_id"],
                "old_status": row["old_status"],
                "old_score_units": row["old_score_units"],
                "new_status": row["new_status"],
                "new_score_units": row["new_score_units"],
                "reason": row["reason"] == "教师复核后更正",
                "seq": row["seq"],
            },
            {
                "participant_id": b_pid,
                "item_id": q3,
                "old_status": "missing",
                "old_score_units": None,
                "new_status": "recorded",
                "new_score_units": 300,
                "reason": True,
                "seq": 1,
            },
        )

        # 原修订不可变：v1 仍是 missing，且 v1 快照仍是 4 人
        matrix1 = harness.score_matrix(v1, limit=200).json()
        verdict.expect("v1 仍是 4 人次快照", matrix1["total"], 4)
        verdict.expect("v1 missingCellCount=1（未被修正改写）", matrix1["missingCellCount"], 1)
        v1_b = B.matrix_map(matrix1)["B"]
        verdict.expect("v1 B 的 Q3 仍 missing", v1_b["cells"][q3]["status"], "missing")
        verdict.expect("v1 B.totalUnits 仍 null", v1_b["participant"]["totalUnits"], None)
        verdict.expect("v1 仍触发 active 为 v2", harness.assessment(assessment_id)["assessment"]["activeScoreRevisionId"], v2)

        # 审计表按 revision 不可改（无触发器但属服务私有；这里仅确认不可通过 API 改）
        # ---- 2. 过期 base → 409；active 清空 → 409 NO_BASE
        stale = harness.correct_scores(
            assessment_id,
            correction_body(
                harness,
                scene,
                base=v1,
                submission_id="c-stale",
                corrections=[
                    {"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "2"}
                ],
            ),
        )
        verdict.expect("过期 base 409", stale.status_code, 409)
        verdict.expect("过期 base 错误码", stale.json().get("code"), "SCORE_BASE_REVISION_CONFLICT")

        harness.raw_exec(
            "UPDATE assessments SET active_score_revision_id = NULL WHERE id = ?", (assessment_id,)
        )
        no_base = harness.correct_scores(
            assessment_id,
            correction_body(
                harness,
                scene,
                base=v2,
                submission_id="c-nobase",
                corrections=[
                    {"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "2"}
                ],
            ),
        )
        verdict.expect("active 清空 → 409", no_base.status_code, 409)
        verdict.expect("active 清空错误码", no_base.json().get("code"), "SCORE_NO_BASE_REVISION")
        harness.raw_exec(
            "UPDATE assessments SET active_score_revision_id = ? WHERE id = ?", (v2, assessment_id)
        )

        # ---- 3. 修正请求校验（各 422；绝不新增版本）
        def expect_422(label: str, corrections: list, code: str) -> None:
            before = harness.count("score_revisions")
            response = harness.correct_scores(
                assessment_id,
                correction_body(harness, scene, base=v2, submission_id=f"c-{label}", corrections=corrections),
            )
            verdict.expect(f"{label} → 422", response.status_code, 422)
            verdict.expect(f"{label} 错误码", response.json().get("code"), code)
            verdict.expect(f"{label} 不新增修订", harness.count("score_revisions"), before)

        expect_422(
            "重复条目",
            [
                {"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "4"},
                {"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "5"},
            ],
            "SCORE_CORRECTION_INVALID",
        )
        expect_422(
            "未变化值",
            [{"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "3"}],
            "SCORE_CORRECTION_INVALID",
        )
        expect_422(
            "未知人次",
            [{"participantId": "nobody", "itemId": q3, "status": "recorded", "scoreText": "4"}],
            "SCORE_PARTICIPANT_UNKNOWN",
        )
        expect_422(
            "未知小题",
            [{"participantId": b_pid, "itemId": "no-such-item", "status": "recorded", "scoreText": "4"}],
            "SCORE_ITEM_UNKNOWN",
        )
        expect_422(
            "超满分",
            [{"participantId": b_pid, "itemId": q3, "status": "recorded", "scoreText": "999"}],
            "SCORE_CELL_OVER_MAX",
        )
        # 契约校验（Pydantic）：recorded 缺 scoreText / 非 recorded 带 scoreText
        for label, payload in (
            ("recorded 缺 scoreText", {"participantId": b_pid, "itemId": q3, "status": "recorded"}),
            ("非 recorded 带 scoreText", {"participantId": b_pid, "itemId": q3, "status": "missing", "scoreText": "1"}),
        ):
            response = harness.correct_scores(
                assessment_id,
                correction_body(harness, scene, base=v2, submission_id=f"c-{label}", corrections=[payload]),
            )
            verdict.expect(f"{label} → 422", response.status_code, 422)
            verdict.expect(f"{label} 错误码 INVALID_REQUEST", response.json().get("code"), "INVALID_REQUEST")

        # ---- 4. 新增参测人次后修正：新版本快照含新人次（修正当时的快照）
        g = harness.create_student(name="G", student_no="0007", class_id=scene["class"]["id"], joined_on=B.days_before(30))
        added = harness.add_participants(
            assessment_id,
            expected_revision=harness.assessment(assessment_id)["assessment"]["revision"],
            submission_id="add-g",
            student_id=g["id"],
            class_id=scene["class"]["id"],
        )
        verdict.expect("补录 G 200", added.status_code, 200)
        g_pid = added.json()["participants"][-1]["participantId"]

        # A 的 Q1 2 → 1（recorded(1.5) 单位 150）→ v3
        a_pid = scene["byName"]["A"]["participantId"]
        q1 = scene["paper"]["itemIds"][0]
        c3_body = correction_body(
            harness,
            scene,
            base=v2,
            submission_id="c-3",
            corrections=[{"participantId": a_pid, "itemId": q1, "status": "recorded", "scoreText": "1.5"}],
        )
        response = harness.correct_scores(assessment_id, c3_body)
        verdict.expect("含新参测人次时修正 200", response.status_code, 200)
        v3 = response.json()["revisionId"]
        revision3 = harness.client.get(f"/api/v1/score-revisions/{v3}").json()
        verdict.expect("v3 快照 5 人次（含 G）", len(revision3["participantSnapshot"]), 5)
        verdict.expect(
            "v3 快照人次含 G",
            g_pid in [item["participantId"] for item in revision3["participantSnapshot"]],
            True,
        )
        matrix3 = harness.score_matrix(v3, limit=200).json()
        verdict.expect("v3 total=5", matrix3["total"], 5)
        table3 = B.matrix_map(matrix3)
        verdict.expect("v3 A 的 Q1=150", (table3["A"]["cells"][q1]["status"], table3["A"]["cells"][q1]["scoreUnits"]), ("recorded", 150))
        verdict.expect("v3 G 三叶 missing（present 无数据）", {table3["G"]["cells"][i]["status"] for i in scene["paper"]["itemIds"]}, {"missing"})
        verdict.expect("v3 G totalUnits=null", table3["G"]["participant"]["totalUnits"], None)

        # 历史修订仍按自己的快照可读（新增人次不影响历史）
        old_matrix = harness.score_matrix(v2, limit=200).json()
        verdict.expect("v2 仍 4 人次（不受新增 G 影响）", old_matrix["total"], 4)
        verdict.expect("v2 missingCellCount=0", old_matrix["missingCellCount"], 0)

        # ---- 5. 重放 + 并发双修正
        # 幂等重放必须是**字节级相同载荷**（request_hash 含 expectedAssessmentRevision）
        replay = harness.correct_scores(assessment_id, c3_body)
        verdict.expect("同 submissionId 同载荷重放 200", replay.status_code, 200)
        verdict.expect("重放返回 v3", replay.json().get("revisionId"), v3)
        verdict.expect("重放 replayed=true", replay.json().get("replayed"), True)
        verdict.expect("重放不新增版本", harness.count("score_revisions"), 3)

        # 同 submissionId 不同载荷 → 409 SUBMISSION_CONFLICT（幂等键不允许换内容）
        conflict = harness.correct_scores(
            assessment_id,
            correction_body(
                harness,
                scene,
                base=v3,
                submission_id="c-3",
                corrections=[{"participantId": a_pid, "itemId": q1, "status": "recorded", "scoreText": "2"}],
            ),
        )
        verdict.expect("同 submissionId 不同载荷 409", conflict.status_code, 409)
        verdict.expect("同 submissionId 不同载荷错误码", conflict.json().get("code"), "SUBMISSION_CONFLICT")

        # 并发双修正：同一 base=v3，不同 submissionId，各自改同一格的不同目标值
        results: list[tuple[int, str, str | None]] = []
        lock = threading.Lock()

        def worker(submission_id: str, text: str) -> None:
            response = harness.correct_scores(
                assessment_id,
                correction_body(
                    harness,
                    scene,
                    base=v3,
                    submission_id=submission_id,
                    corrections=[{"participantId": a_pid, "itemId": q1, "status": "recorded", "scoreText": text}],
                ),
            )
            payload = response.json()
            with lock:
                results.append(
                    (response.status_code, payload.get("code", "OK"), payload.get("revisionId"))
                )

        threads = [
            threading.Thread(target=worker, args=("c-conc-1", "1")),
            threading.Thread(target=worker, args=("c-conc-2", "0.5")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        statuses = sorted(status for status, _, _ in results)
        verdict.expect("并发双修正状态 ∈ {200,409}", statuses, [200, 409])
        verdict.expect("恰好一个成功", sum(1 for s, _, _ in results if s == 200), 1)
        verdict.check(
            "失败方 409 错误码 ∈ {SCORE_BASE_REVISION_CONFLICT, SCORE_ASSESSMENT_REVISION_CONFLICT}",
            [code for status, code, _ in results if status == 409]
            in (["SCORE_BASE_REVISION_CONFLICT"], ["SCORE_ASSESSMENT_REVISION_CONFLICT"]),
            [code for status, code, _ in results if status == 409],
        )
        verdict.expect("并发后恰好新增 1 个版本 → 共 4", harness.count("score_revisions"), 4)
        winner_revision = [revision for status, _, revision in results if status == 200][0]
        current_active = harness.assessment(assessment_id)["assessment"]["activeScoreRevisionId"]
        verdict.expect("active=并发胜者", current_active, winner_revision)
        # 胜者的矩阵与审计
        winner_matrix = harness.score_matrix(current_active, limit=200).json()
        winner_a = B.matrix_map(winner_matrix)["A"]["cells"][q1]
        verdict.check(
            "胜者写入的值 ∈ {100,50}（1 或 0.5）",
            winner_a["scoreUnits"] in (100, 50),
            winner_a,
        )
        verdict.expect(
            "并发修正审计 1 条",
            harness.count("score_revision_corrections", "revision_id = ?", (current_active,)),
            1,
        )
        verdict.note(f"并发结果={results}，active={current_active}")

    return verdict.finish(path=HERE / "p23_corrections.json")


if __name__ == "__main__":
    sys.exit(main())
