"""V00 · B3 附加：并发双确认只前进一批 + 损坏读取显式失败（不静默空）。

覆盖：
  1. 两个线程同 submissionId 并发确认 → 恰好一条修订、两响应都成功且 revisionId 相同
     （一个真执行、一个重放）；
  2. 两个线程不同 submissionId 并发确认同一批次 → 恰好一个成功（另一个 409），只前进一批；
  3. 损坏读取：
     - `score_imports.mapping_json` 被人为改坏 → GET 批次 500 `SCORE_ROW_CORRUPT`（不返回空视图）；
     - 上传损坏的 XLSX 字节 → 422 `TABLE_PARSE_FAILED`（不落批次）；
     - `score_revisions.participant_snapshot_json` 改坏 → GET 修订/矩阵明确报错（不静默丢失人次）。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p30_concurrency_corruption.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

LEAVES = (("Q1", 200), ("Q2", 300))
HEADER = ("学号", "姓名", "Q1", "Q2")
ROWS = (("0001", "A", 2, 3), ("0002", "B", 1, None))


def setup(harness: B.Harness, tag: str):
    scene = harness.sample_scene(
        tag=tag,
        leaves=LEAVES,
        students=(("A", "0001", "present"), ("B", "0002", "present")),
    )
    path = B.write_xlsx(Path(harness.settings.data_dir) / f"{tag}.xlsx", HEADER, ROWS)
    upload = harness.upload_scores(scene["assessment"]["assessmentId"], path)
    assert upload.status_code == 201, upload.text
    return scene, upload.json()


def confirm_body(harness: B.Harness, scene, view, submission_id: str) -> dict:
    return {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": harness.assessment(scene["assessment"]["assessmentId"])["assessment"]["revision"],
        "baseScoreRevisionId": None,
        "previewVersion": view["previewVersion"],
        "submissionId": submission_id,
        "absences": [],
        "missing": {"participantIds": [scene["byName"]["B"]["participantId"]], "cellCount": 1},
    }


def main() -> int:
    verdict = B.Verdict("p30_concurrency_corruption")

    # ---------------- 1. 同 submissionId 并发确认（应只执行一次，另一个重放）
    with B.Harness(tag="conc-same") as harness:
        scene, view = setup(harness, "conc-same")
        body = confirm_body(harness, scene, view, "conc-same")
        results: list[tuple[int, dict]] = []
        lock = threading.Lock()

        def worker() -> None:
            response = harness.confirm_import(view["importId"], body)
            with lock:
                results.append((response.status_code, response.json()))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        verdict.expect("同 submissionId 并发：两响应都 200", [s for s, _ in results], [200, 200])
        revisions = {payload.get("revisionId") for _s, payload in results}
        verdict.expect("同 submissionId 并发：返回同一修订", len(revisions), 1)
        verdict.expect("同 submissionId 并发：只落 1 个修订", harness.count("score_revisions"), 1)
        replays = sorted(payload.get("replayed") for _s, payload in results)
        verdict.expect("同 submissionId 并发：恰好一个真执行 + 一个重放", replays, [False, True])

    # ---------------- 2. 不同 submissionId 并发确认（只前进一批）
    with B.Harness(tag="conc-diff") as harness:
        scene, view = setup(harness, "conc-diff")
        bodies = [
            confirm_body(harness, scene, view, "conc-a"),
            confirm_body(harness, scene, view, "conc-b"),
        ]
        results2: list[tuple[int, str]] = []
        lock2 = threading.Lock()

        def worker2(body: dict) -> None:
            response = harness.confirm_import(view["importId"], body)
            with lock2:
                results2.append((response.status_code, response.json().get("code", "OK")))

        threads2 = [threading.Thread(target=worker2, args=(body,)) for body in bodies]
        for thread in threads2:
            thread.start()
        for thread in threads2:
            thread.join()
        verdict.expect("不同 submissionId 并发：状态 ∈ {200,409}", sorted(s for s, _ in results2), [200, 409])
        verdict.expect("不同 submissionId 并发：恰好一个成功", sum(1 for s, _ in results2 if s == 200), 1)
        verdict.expect("不同 submissionId 并发：只落 1 个修订", harness.count("score_revisions"), 1)
        verdict.note(f"不同 submissionId 并发结果={results2}")

    # ---------------- 3. 损坏读取
    with B.Harness(tag="corrupt") as harness:
        scene, view = setup(harness, "corrupt")
        assessment_id = scene["assessment"]["assessmentId"]

        def corrupt(sql: str, params: tuple) -> None:
            """绕过 json_valid CHECK 写入损坏值（PRAGMA ignore_check_constraints，仅本临时库）。"""
            harness.raw_exec_many(
                [
                    ("PRAGMA ignore_check_constraints = ON", ()),
                    (sql, params),
                    ("PRAGMA ignore_check_constraints = OFF", ()),
                ]
            )

        # 3a. 损坏 mapping_json → GET 批次明确 500，不返回空
        corrupt("UPDATE score_imports SET mapping_json = '{broken' WHERE id = ?", (view["importId"],))
        verdict.expect(
            "损坏值确已落库（绕过 CHECK）",
            harness.raw("SELECT mapping_json FROM score_imports WHERE id = ?", (view["importId"],))[0]["mapping_json"],
            "{broken",
        )
        broken = harness.import_view(view["importId"])
        verdict.expect("损坏 mapping_json → 500", broken.status_code, 500)
        verdict.expect("损坏 mapping_json 错误码", broken.json().get("code"), "SCORE_ROW_CORRUPT")

        # 3b. 损坏 XLSX 字节 → 422 TABLE_PARSE_FAILED，且不落批次
        before = harness.count("score_imports")
        bad_path = Path(harness.settings.data_dir) / "bad.xlsx"
        bad_path.write_bytes(b"PK\x03\x04" + b"\x00" * 64)  # ZIP 魔数但内容损坏
        bad = harness.upload_scores(assessment_id, bad_path, file_name="bad.xlsx")
        verdict.expect("损坏 XLSX 上传 422", bad.status_code, 422)
        verdict.expect("损坏 XLSX 错误码", bad.json().get("code"), "TABLE_PARSE_FAILED")
        verdict.expect("损坏 XLSX 不落批次", harness.count("score_imports"), before)

        # 3c. 恢复 mapping 后正常确认，再损坏 participant_snapshot_json → 读修订明确报错
        harness.raw_exec(
            "UPDATE score_imports SET mapping_json = ? WHERE id = ?",
            (json.dumps(
                {
                    "workSheet": "成绩",
                    "headerRow": 1,
                    "studentNoColumn": "A",
                    "nameColumn": "B",
                    "itemColumns": [
                        {"itemId": scene["paper"]["itemIds"][0], "column": "C"},
                        {"itemId": scene["paper"]["itemIds"][1], "column": "D"},
                    ],
                },
                ensure_ascii=False,
            ), view["importId"]),
        )
        confirm = harness.confirm_import(view["importId"], confirm_body(harness, scene, view, "corrupt-confirm"))
        verdict.expect("恢复正常后确认 200", confirm.status_code, 200)
        revision_id = confirm.json()["revisionId"]
        verdict.expect(
            "确认修订读取正常（快照 2 人次）",
            harness.score_matrix(revision_id).json()["total"],
            2,
        )
        # 新建一个草稿修订并损坏其快照（已确认修订受不可变触发器保护，不在此测试范围）
        harness.raw_exec(
            "INSERT INTO score_revisions (id, assessment_id, version, source_import_id, base_revision_id, "
            "state, participant_snapshot_json, item_snapshot_json, confirmed_at, created_at) "
            "SELECT 'corrupt-draft', assessment_id, 77, NULL, NULL, 'draft', participant_snapshot_json, "
            "item_snapshot_json, NULL, created_at FROM score_revisions WHERE id = ?",
            (revision_id,),
        )
        corrupt(
            "UPDATE score_revisions SET participant_snapshot_json = 'not-json' WHERE id = 'corrupt-draft'",
            (),
        )
        verdict.expect(
            "损坏快照确已落库（绕过 CHECK）",
            harness.raw(
                "SELECT participant_snapshot_json AS j FROM score_revisions WHERE id = 'corrupt-draft'"
            )[0]["j"],
            "not-json",
        )
        broken_revision = harness.client.get("/api/v1/score-revisions/corrupt-draft")
        verdict.expect("损坏快照 → 500", broken_revision.status_code, 500)
        verdict.note(
            "损坏快照响应="
            + json.dumps(broken_revision.json(), ensure_ascii=False)[:200]
        )

    return verdict.finish(path=HERE / "p30_concurrency_corruption.json")


if __name__ == "__main__":
    sys.exit(main())
