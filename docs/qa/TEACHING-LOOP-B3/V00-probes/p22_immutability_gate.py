"""V00 · B3-A3 不可变与闸门（含变异实验）。

覆盖：
  1. 直连 sqlite：已确认修订的 UPDATE/DELETE、已确认修订矩阵行的 INSERT/UPDATE/DELETE
     一律 `SCORE_REVISION_IMMUTABLE`，且失败后数据逐行不变；
  2. 确认矩阵不全 → `SCORE_MATRIX_INCOMPLETE`（DB 闸门 `score_revision_confirm_gate` 按该修订自己的快照核）；
  3. **变异 1（DB 副本）**：在临时库副本上 DROP 闸门 → 同一"不全确认"UPDATE 改为成功（证明闸门是真正的拦截面）；
  4. **变异 2（服务层）**：在临时库上 DROP 闸门 + 让服务写入少一格的矩阵 → 观察服务是否独立拦截
     （结论如实记录；这是对"断言非空洞"的反证）；
  5. active 只能指向已确认修订：`SCORE_REVISION_NOT_CONFIRMED`。

所有变异只发生在探针自建的临时数据目录/副本上。运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p22_immutability_gate.py
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

LEAVES = (("Q1", 200), ("Q2", 300), ("Q3", 500))
HEADER = ("学号", "姓名", "Q1", "Q2", "Q3")
ROWS = (("0001", "A", 2, 2, 5), ("0002", "B", 2, 3, None), ("0003", "C", None, None, None))


def confirm_scene(harness: B.Harness, tag: str):
    scene = harness.sample_scene(
        tag=tag,
        leaves=LEAVES,
        students=(("A", "0001", "present"), ("B", "0002", "present"), ("C", "0003", "absent")),
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
        "submissionId": f"{tag}-confirm",
        "absences": [{"classId": scene["class"]["id"], "participantIds": [scene["byName"]["C"]["participantId"]]}],
        "missing": {"participantIds": [scene["byName"]["B"]["participantId"]], "cellCount": 1},
    }
    confirm = harness.confirm_import(view["importId"], body)
    assert confirm.status_code == 200, confirm.text
    return scene, confirm.json()["revisionId"]


def attempt(harness: B.Harness, sql: str, params: tuple = ()) -> str | None:
    """执行直连写；返回错误消息（成功返回 None）。"""
    try:
        harness.raw_exec(sql, params)
        return None
    except sqlite3.IntegrityError as exc:
        return str(exc)


def insert_incomplete_draft(harness: B.Harness, confirmed_id: str, draft_id: str) -> None:
    harness.raw_exec_many(
        [
            (
                "INSERT INTO score_revisions (id, assessment_id, version, source_import_id, "
                "base_revision_id, state, participant_snapshot_json, item_snapshot_json, "
                "confirmed_at, created_at) "
                "SELECT ?, assessment_id, 99, NULL, NULL, 'draft', participant_snapshot_json, "
                "item_snapshot_json, NULL, created_at FROM score_revisions WHERE id = ?",
                (draft_id, confirmed_id),
            ),
            (
                "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
                "participant_id, item_id, score_units, status) "
                "SELECT ?, assessment_id, paper_revision_id, participant_id, item_id, score_units, status "
                "FROM student_item_scores WHERE score_revision_id = ?",
                (draft_id, confirmed_id),
            ),
            (
                "DELETE FROM student_item_scores WHERE rowid IN ("
                "SELECT rowid FROM student_item_scores WHERE score_revision_id = ? LIMIT 1)",
                (draft_id,),
            ),
        ]
    )


def main() -> int:
    verdict = B.Verdict("p22_immutability_gate")
    copy_db: Path | None = None

    # ======================================================== 1/2/5：未变异的真库
    with B.Harness(tag="immut") as harness:
        scene, revision_id = confirm_scene(harness, "immut")
        assessment_id = scene["assessment"]["assessmentId"]

        matrix_rows = harness.count("student_item_scores", "score_revision_id = ?", (revision_id,))
        verdict.expect("确认后矩阵行数=3×3", matrix_rows, 9)

        attempts = {
            "UPDATE 已确认修订 version": attempt(
                harness,
                "UPDATE score_revisions SET version = 99 WHERE id = ?",
                (revision_id,),
            ),
            "DELETE 已确认修订": attempt(
                harness, "DELETE FROM score_revisions WHERE id = ?", (revision_id,)
            ),
            "UPDATE 已确认矩阵行": attempt(
                harness,
                "UPDATE student_item_scores SET score_units = 100 WHERE score_revision_id = ?",
                (revision_id,),
            ),
            "DELETE 已确认矩阵行": attempt(
                harness,
                "DELETE FROM student_item_scores WHERE score_revision_id = ?",
                (revision_id,),
            ),
            "INSERT 已确认矩阵行": attempt(
                harness,
                "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
                "participant_id, item_id, score_units, status) "
                "SELECT ?, assessment_id, paper_revision_id, participant_id, item_id, 0, 'recorded' "
                "FROM student_item_scores WHERE score_revision_id = ? LIMIT 1",
                (revision_id, revision_id),
            ),
        }
        for label, error in attempts.items():
            verdict.check(
                f"{label} → SCORE_REVISION_IMMUTABLE",
                error is not None and "SCORE_REVISION_IMMUTABLE" in error,
                error,
            )
        verdict.expect(
            "不可变尝试后修订仍在且 version 未变",
            harness.raw("SELECT version, state FROM score_revisions WHERE id = ?", (revision_id,)),
            [{"version": 1, "state": "confirmed"}],
        )
        verdict.expect(
            "不可变尝试后矩阵行数不变",
            harness.count("student_item_scores", "score_revision_id = ?", (revision_id,)),
            9,
        )

        # ---- 矩阵不全 → SCORE_MATRIX_INCOMPLETE（闸门按该修订自己的快照）
        insert_incomplete_draft(harness, revision_id, "draft-incomplete")
        verdict.expect(
            "构造的不全草稿：快照 3 人次×3 叶、矩阵 8 行",
            {
                "snapshot": len(
                    json.loads(
                        harness.raw(
                            "SELECT participant_snapshot_json AS j FROM score_revisions WHERE id=?",
                            ("draft-incomplete",),
                        )[0]["j"]
                    )
                ),
                "items": len(
                    json.loads(
                        harness.raw(
                            "SELECT item_snapshot_json AS j FROM score_revisions WHERE id=?",
                            ("draft-incomplete",),
                        )[0]["j"]
                    )
                ),
                "cells": harness.count(
                    "student_item_scores", "score_revision_id = ?", ("draft-incomplete",)
                ),
            },
            {"snapshot": 3, "items": 3, "cells": 8},
        )
        gate_error = attempt(
            harness,
            "UPDATE score_revisions SET state='confirmed', confirmed_at='2026-10-01T00:00:00Z' "
            "WHERE id = 'draft-incomplete'",
        )
        verdict.check(
            "不全矩阵确认 → SCORE_MATRIX_INCOMPLETE",
            gate_error is not None and "SCORE_MATRIX_INCOMPLETE" in gate_error,
            gate_error,
        )
        verdict.expect(
            "闸门拒绝后草稿仍未确认",
            harness.raw("SELECT state FROM score_revisions WHERE id='draft-incomplete'")[0]["state"],
            "draft",
        )

        # ---- 完整草稿 → active 只允许已确认
        harness.raw_exec_many(
            [
                (
                    "INSERT INTO score_revisions (id, assessment_id, version, source_import_id, "
                    "base_revision_id, state, participant_snapshot_json, item_snapshot_json, "
                    "confirmed_at, created_at) "
                    "SELECT 'draft-complete', assessment_id, 98, NULL, NULL, 'draft', "
                    "participant_snapshot_json, item_snapshot_json, NULL, created_at "
                    "FROM score_revisions WHERE id = ?",
                    (revision_id,),
                ),
                (
                    "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
                    "participant_id, item_id, score_units, status) "
                    "SELECT 'draft-complete', assessment_id, paper_revision_id, participant_id, item_id, "
                    "score_units, status FROM student_item_scores WHERE score_revision_id = ?",
                    (revision_id,),
                ),
            ]
        )
        active_error = attempt(
            harness,
            "UPDATE assessments SET active_score_revision_id = 'draft-complete' WHERE id = ?",
            (assessment_id,),
        )
        verdict.check(
            "active 指向 draft → SCORE_REVISION_NOT_CONFIRMED",
            active_error is not None and "SCORE_REVISION_NOT_CONFIRMED" in active_error,
            active_error,
        )

        # 保留正式库字节供副本变异（关闭 app 后复制）
        original_db = harness.db_path
    copy_db = Path(tempfile.mkdtemp(prefix="b3v00-mut-")) / "teaching.sqlite3"
    shutil.copy2(original_db, copy_db)

    # ======================================================== 3：DB 副本上 DROP 闸门
    connection = sqlite3.connect(str(copy_db))
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        before = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name='score_revision_confirm_gate'"
        ).fetchone()[0]
        verdict.expect("副本上闸门存在", before, 1)
        connection.execute("DROP TRIGGER score_revision_confirm_gate")
        connection.commit()
        after = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name='score_revision_confirm_gate'"
        ).fetchone()[0]
        verdict.expect("副本上闸门已 DROP", after, 0)
        try:
            connection.execute(
                "UPDATE score_revisions SET state='confirmed', confirmed_at='2026-10-01T00:00:00Z' "
                "WHERE id = 'draft-incomplete'"
            )
            connection.commit()
            verdict.check("DROP 闸门后同一条不全确认 UPDATE 成功（反证闸门是拦截面）", True, None)
        except sqlite3.IntegrityError as exc:
            verdict.check(
                "DROP 闸门后同一条不全确认 UPDATE 成功（反证闸门是拦截面）",
                False,
                f"仍被拒绝：{exc}",
            )
        state = connection.execute(
            "SELECT state FROM score_revisions WHERE id='draft-incomplete'"
        ).fetchone()[0]
        verdict.expect("副本上不全修订已变 confirmed", state, "confirmed")
    finally:
        connection.close()
    # 原库仍完好（副本变异不外溢）
    check = sqlite3.connect(str(original_db))
    try:
        original_state = check.execute(
            "SELECT state FROM score_revisions WHERE id='draft-incomplete'"
        ).fetchone()[0]
        original_trigger = check.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name='score_revision_confirm_gate'"
        ).fetchone()[0]
    finally:
        check.close()
    verdict.expect("原库的不全修订仍是 draft（变异不外溢）", original_state, "draft")
    verdict.expect("原库闸门仍在", original_trigger, 1)
    verdict.note(f"DB 副本变异位置：{copy_db}")

    # ======================================================== 4：服务层变异（临时库）
    with B.Harness(tag="mutsvc") as harness:
        scene = harness.sample_scene(
            tag="mutsvc",
            leaves=LEAVES,
            students=(("A", "0001", "present"), ("B", "0002", "present")),
        )
        path = B.write_xlsx(Path(harness.settings.data_dir) / "mutsvc.xlsx", HEADER, ROWS[:2])
        upload = harness.upload_scores(scene["assessment"]["assessmentId"], path)
        assert upload.status_code == 201, upload.text
        view = upload.json()
        harness.raw_exec("DROP TRIGGER score_revision_confirm_gate")
        verdict.expect(
            "服务层变异：闸门已删除",
            harness.raw(
                "SELECT count(*) AS n FROM sqlite_master WHERE type='trigger' "
                "AND name='score_revision_confirm_gate'"
            )[0]["n"],
            0,
        )

        service = harness.app.state.score_service
        repository = service._scores
        original_insert = repository.insert_matrix_in
        dropped: dict[str, object] = {}

        def patched(conn, *, revision_id, assessment_id, paper_revision_id, cells):
            cells = list(cells)
            dropped["cell"] = cells.pop() if cells else None
            return original_insert(
                conn,
                revision_id=revision_id,
                assessment_id=assessment_id,
                paper_revision_id=paper_revision_id,
                cells=cells,
            )

        repository.insert_matrix_in = patched  # type: ignore[method-assign]
        body = {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": harness.assessment(scene["assessment"]["assessmentId"])["assessment"]["revision"],
            "baseScoreRevisionId": None,
            "previewVersion": view["previewVersion"],
            "submissionId": "mutsvc-confirm",
            "absences": [],
            "missing": {
                "participantIds": [scene["byName"]["B"]["participantId"]],
                "cellCount": 1,
            },
        }
        # A 全 recorded、B 缺 Q3（missing 1 格）→ 承认后进入写矩阵路径
        response = harness.confirm_import(view["importId"], body)
        repository.insert_matrix_in = original_insert  # type: ignore[method-assign]
        verdict.note(
            "服务层变异结果："
            + json.dumps(
                {
                    "status": response.status_code,
                    "droppedCell": dropped.get("cell"),
                    "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:200],
                },
                ensure_ascii=False,
            )
        )
        if response.status_code == 200:
            revision_id = response.json()["revisionId"]
            rows = harness.count(
                "student_item_scores", "score_revision_id = ?", (revision_id,)
            )
            verdict.note(
                "服务层不独立复核矩阵完整性：删掉闸门 + 仓储少写一格时确认仍成功"
                f"（该修订 {rows} 行，期望 6 行）；残余风险：任何绕过 build_preview 的"
                "未来写入路径只能靠 DB 闸门兜底（本批生产路径均从冻结快照生成完整矩阵）。"
            )
            verdict.expect("变异确认写入了 5 行（少 1）", rows, 5)
        else:
            verdict.note("服务层自行拦截了不完整写入（未观察到预期外行为）。")

    return verdict.finish(path=HERE / "p22_immutability_gate.json")


if __name__ == "__main__":
    sys.exit(main())
