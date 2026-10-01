"""V00 · B3-B6/B7 迁移 0006/0007 与"按修订自己的快照"闸门。

B6：自建 B2 旧库（仅应用 0001–0005 的登记前缀；含已确认卷 + 施测 + 参测人次，
    另有一条草稿修订与子行）→ 应用 0006/0007 → 逐行保留、FK/integrity、触发器在位、
    0001–0005 登记散列不漂移（对照 tests/test_b2_migrations.py::FROZEN_DIGESTS
    与正式库只读副本）。
B7：确认后新增参测人次 → 历史修订仍可读、不因此被判不全；新 draft 的闸门按**自己的**
    snapshot 核（含 G 的快照 + 少 G 的矩阵 = 拒绝；不含 G 的快照 + 对应矩阵 = 放行）。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p25_migrations.py
"""

from __future__ import annotations

import ast
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

from app.core import migrations as M  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.migrations import apply_migrations  # noqa: E402
from app.core.sqlite import connect  # noqa: E402

FROZEN_TEST = B.API_DIR / "tests" / "test_b2_migrations.py"
FORMAL_DB = B.REPO / ".local-data" / "teaching" / "teaching.sqlite3"


def load_frozen_digests() -> dict:
    tree = ast.parse(FROZEN_TEST.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "FROZEN_DIGESTS" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("未找到 FROZEN_DIGESTS")


def registry(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        row["id"]: row["sha256"]
        for row in connection.execute("SELECT id, sha256 FROM schema_migrations ORDER BY id")
    }


def dump_rows(connection: sqlite3.Connection) -> dict[str, list[list]]:
    tables = [
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name <> 'schema_migrations' ORDER BY name"
        )
    ]
    dumps: dict[str, list[list]] = {}
    for table in tables:
        rows = [list(row) for row in connection.execute(f"SELECT * FROM {table}")]
        rows.sort(key=lambda row: json.dumps(row, ensure_ascii=False, default=str))
        dumps[table] = rows
    return dumps


def seed_b2(connection: sqlite3.Connection) -> None:
    """写 B2 时代数据：已确认卷 + 一条草稿修订 + 班级/学生/归属 + 施测 + 参测人次。"""
    now = "2026-10-01T00:00:00.000Z"
    statements = [
        # 资产（原卷文件）
        (
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES "
            "('fa-b2','local','paper','blobs/aa','" + "aa" * 32 + "','b2.docx','application/octet-stream',1,?)",
            (now,),
        ),
        (
            "INSERT INTO papers (id, owner_id, subject_id, title, status, revision, created_at) "
            "VALUES ('pp-b2','local','math','B2 旧卷','active',1,?)",
            (now,),
        ),
        (
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, "
            "state, title_snapshot, title_snapshot_source, created_at) VALUES "
            "('pr-b2','pp-b2',1,'fa-b2',200,'draft','B2 旧卷','revision',?)",
            (now,),
        ),
        (
            "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, ordinal, "
            "is_scored, max_score_units, content_json, source_locator_json) VALUES "
            "('it-b2','pr-b2',NULL,'Q1',1,1,200,'{}','{}')",
            (),
        ),
        (
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) VALUES "
            "('it-b2','pr-b2','kp-b2','kpv-b2','B2 知识点','primary','human')",
            (),
        ),
        (
            "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='pr-b2'",
            (now,),
        ),
        ("UPDATE papers SET current_revision_id='pr-b2' WHERE id='pp-b2'", ()),
        # 第二修订（草稿）：多修订数据保留
        (
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, "
            "state, title_snapshot, title_snapshot_source, created_at) VALUES "
            "('pr-b2-draft','pp-b2',2,'fa-b2',0,'draft','B2 旧卷（新草稿）','revision',?)",
            (now,),
        ),
        ("INSERT INTO classes (id, owner_id, code, name, school_year, grade_id, status, revision, created_at) "
         "VALUES ('c-b2','local','C-B2','B2 班级','2026','grade-1','active',0,?)", (now,)),
        ("INSERT INTO students (id, owner_id, student_no, name, status, revision, created_at) "
         "VALUES ('s-b2-1','local','0001','甲','active',0,?)", (now,)),
        ("INSERT INTO students (id, owner_id, student_no, name, status, revision, created_at) "
         "VALUES ('s-b2-2','local','0002','乙','active',0,?)", (now,)),
        ("INSERT INTO class_memberships (id, class_id, student_id, joined_on) "
         "VALUES ('m-b2-1','c-b2','s-b2-1','2026-09-01')", ()),
        ("INSERT INTO class_memberships (id, class_id, student_id, joined_on) "
         "VALUES ('m-b2-2','c-b2','s-b2-2','2026-09-01')", ()),
        ("INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, held_on, "
         "active_score_revision_id, state, revision, created_at) "
         "VALUES ('a-b2','local','pr-b2','B2 旧施测','exam','2026-09-30',NULL,'open',0,?)", (now,)),
        ("INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('a-b2','c-b2')", ()),
        ("INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, attempt_no, "
         "attendance, name_snapshot, student_no_snapshot, class_confirmed, class_confirmation_note, "
         "class_confirmation_at) VALUES "
         "('ap-b2-1','a-b2','s-b2-1','c-b2',1,'present','甲','0001',0,NULL,NULL)", ()),
        ("INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, attempt_no, "
         "attendance, name_snapshot, student_no_snapshot, class_confirmed, class_confirmation_note, "
         "class_confirmation_at) VALUES "
         "('ap-b2-2','a-b2','s-b2-2','c-b2',1,'absent','乙','0002',0,NULL,NULL)", ()),
    ]
    for sql, params in statements:
        connection.execute(sql, list(params))


def main() -> int:
    verdict = B.Verdict("p25_migrations")
    data_dir = B.isolated_data_dir() / "mig"
    db_path = data_dir / "teaching" / "teaching.sqlite3"

    # ======================================================== B6：B2 旧库 → 0006/0007
    connection = connect(db_path)
    try:
        full = M.REGISTERED_MIGRATIONS["teaching"]
        prefix = tuple(m for m in full if m.id[:4] in ("0001", "0002", "0003", "0004", "0005"))
        verdict.expect("B2 前缀迁移条数=5", [m.id for m in prefix], [m.id for m in full[:5]])
        M.REGISTERED_MIGRATIONS = {**M.REGISTERED_MIGRATIONS, "teaching": prefix}
        applied = apply_migrations(connection, database="teaching")
        M.REGISTERED_MIGRATIONS = {**M.REGISTERED_MIGRATIONS, "teaching": full}
        verdict.expect("B2 旧库先应用 0001–0005", applied, [m.id for m in prefix])

        # B2 期 assessments 的 active 只能空（先种子再验证分期 CHECK）
        seed_b2(connection)
        try:
            connection.execute("UPDATE assessments SET active_score_revision_id='x' WHERE id='a-b2'")
            verdict.check("B2 CHECK 拒绝 active 非空", False, "不应写入")
        except sqlite3.IntegrityError as exc:
            verdict.check("B2 CHECK 拒绝 active 非空", "CHECK" in str(exc) or "constraint" in str(exc).lower(), str(exc))

        before = dump_rows(connection)
        before_registry = registry(connection)
        verdict.expect("种子后行数（participants/assessments/papers/revisions）", {
            "participants": len(before.get("assessment_participants", [])),
            "assessments": len(before.get("assessments", [])),
            "papers": len(before.get("papers", [])),
            "revisions": len(before.get("paper_revisions", [])),
        }, {"participants": 2, "assessments": 1, "papers": 1, "revisions": 2})
        verdict.expect(
            "B2 登记散列含 0001–0005",
            sorted(k[:4] for k in before_registry),
            ["0001", "0002", "0003", "0004", "0005"],
        )

        # 应用 0006/0007
        applied2 = apply_migrations(connection, database="teaching")
        verdict.expect(
            "升级只应用 0006/0007",
            applied2,
            ["0006_teaching_score_tables", "0007_teaching_assessment_active_score_fk"],
        )

        after = dump_rows(connection)
        preserved = {
            table: before[table] == after.get(table)
            for table in before
        }
        verdict.check("全部既有表逐行保留", all(preserved.values()), [k for k, v in preserved.items() if not v])
        verdict.expect("FK check 空", connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        verdict.expect("integrity_check=ok", [r[0] for r in connection.execute("PRAGMA integrity_check")], ["ok"])
        verdict.expect("foreign_keys 恢复为 1", connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

        triggers = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        expected_triggers = {
            "score_revision_confirm_gate",
            "immutable_score_revisions_update",
            "immutable_score_revisions_delete",
            "immutable_item_scores_insert",
            "immutable_item_scores_update",
            "immutable_item_scores_delete",
            "assessment_active_score_confirmed",
            "assessment_confirmed_paper_insert",
            "assessment_paper_fixed",
        }
        verdict.check(
            "成绩/施测触发器全部在位",
            expected_triggers <= triggers,
            sorted(expected_triggers - triggers),
        )
        verdict.expect(
            "0001–0005 登记散列逐字不变",
            {k: v for k, v in registry(connection).items() if k[:4] in ("0001", "0002", "0003", "0004", "0005")},
            before_registry,
        )
        fk_list = [dict(row) for row in connection.execute("PRAGMA foreign_key_list('assessments')")]
        verdict.check(
            "assessments 恢复 (active_score_revision_id,id)→score_revisions 复合外键",
            any(
                row["table"] == "score_revisions"
                and row["from"] == "active_score_revision_id"
                and row["to"] == "id"
                for row in fk_list
            ),
            fk_list,
        )
        assessments_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='assessments'"
        ).fetchone()[0]
        verdict.check(
            "分期 CHECK（active 仅空）已移除",
            "active_score_revision_id IS NULL" not in assessments_sql,
            assessments_sql[:200],
        )
        verdict.expect(
            "score_* 新表就位且为空",
            {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "score_imports",
                    "score_import_rows",
                    "score_revisions",
                    "student_item_scores",
                    "score_revision_corrections",
                )
            },
            {t: 0 for t in (
                "score_imports", "score_import_rows", "score_revisions",
                "student_item_scores", "score_revision_corrections",
            )},
        )

        # 散列对照：FROZEN_DIGESTS + 正式库只读副本
        frozen = load_frozen_digests()["teaching"]
        verdict.expect(
            "与 FROZEN_DIGESTS（0001/0002）一致",
            {k: before_registry[k] for k in frozen},
            frozen,
        )
        if FORMAL_DB.exists():
            read_only = sqlite3.connect(f"file:{FORMAL_DB.as_posix()}?mode=ro", uri=True)
            read_only.row_factory = sqlite3.Row
            try:
                formal = registry(read_only)
            finally:
                read_only.close()
            shared = sorted(set(formal) & {"0001_teaching_baseline", "0002_teaching_business_tables",
                                           "0003_teaching_paper_tables", "0004_teaching_assessment_tables",
                                           "0005_teaching_paper_revision_titles"})
            verdict.expect(
                "0001–0005 散列与正式库只读副本一致",
                {k: formal[k] for k in shared},
                {k: before_registry[k] for k in shared},
            )
            verdict.note(
                "正式库登记（只读）："
                + json.dumps(formal, ensure_ascii=False)
            )
        else:
            verdict.note("正式库不存在，跳过只读散列对照（not_run 原因见报告）")

        # 旧库数据仍能参与新链路：在升级后的库上真装配 + 成绩确认
        settings = Settings(
            host="127.0.0.1",
            port=8001,
            allowed_origins=frozenset({"http://127.0.0.1:5173"}),
            env="test",
            data_dir=data_dir,
        )
        from fastapi.testclient import TestClient

        from app.main import create_app

        app = create_app(settings)
        with TestClient(app, base_url="http://127.0.0.1:8001") as client:
            verdict.expect(
                "升级库可用（施测读取 200）",
                client.get("/api/v1/assessments/a-b2").status_code,
                200,
            )
            xlsx = B.write_xlsx(
                Path(data_dir) / "b2-upgrade.xlsx",
                ("学号", "姓名", "Q1"),
                (("0001", "甲", 2),),
            )
            upload = client.post(
                "/api/v1/assessments/a-b2/score-imports",
                files={"file": ("s.xlsx", xlsx.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            verdict.expect("升级库上传成绩 201", upload.status_code, 201)
            view = upload.json()
            verdict.expect("升级库自动映射 Q1", len((view["mapping"] or {}).get("itemColumns", [])), 1)
            assessment_rev = client.get("/api/v1/assessments/a-b2").json()["assessment"]["revision"]
            confirm = client.post(
                f"/api/v1/score-imports/{view['importId']}/confirm",
                json={
                    "expectedImportRevision": view["revision"],
                    "expectedAssessmentRevision": assessment_rev,
                    "baseScoreRevisionId": None,
                    "previewVersion": view["previewVersion"],
                    "submissionId": "b2-upgrade",
                    "absences": [{"classId": "c-b2", "participantIds": ["ap-b2-2"]}],
                },
            )
            # 甲有分（recorded）、乙缺考（absent 快照）→ 无 missing 承认
            if confirm.status_code == 200:
                verdict.check("升级库确认链 200", True, confirm.json())
            else:
                verdict.check(
                    "升级库确认链 200",
                    False,
                    {"status": confirm.status_code, "body": confirm.json()},
                )
    finally:
        connection.close()

    # ======================================================== B7：闸门按修订自己的快照
    with B.Harness(tag="snap") as harness:
        scene = harness.sample_scene(
            tag="snap",
            leaves=(("Q1", 200), ("Q2", 300)),
            students=(("A", "0001", "present"), ("B", "0002", "present")),
        )
        assessment_id = scene["assessment"]["assessmentId"]
        xlsx = B.write_xlsx(
            Path(harness.settings.data_dir) / "snap.xlsx",
            ("学号", "姓名", "Q1", "Q2"),
            (("0001", "A", 2, 3), ("0002", "B", 1, None)),
        )
        upload = harness.upload_scores(assessment_id, xlsx)
        assert upload.status_code == 201, upload.text
        view = upload.json()
        confirm = harness.confirm_import(
            view["importId"],
            {
                "expectedImportRevision": view["revision"],
                "expectedAssessmentRevision": scene["assessment"]["revision"],
                "baseScoreRevisionId": None,
                "previewVersion": view["previewVersion"],
                "submissionId": "snap-v1",
                "absences": [],
                "missing": {"participantIds": [scene["byName"]["B"]["participantId"]], "cellCount": 1},
            },
        )
        verdict.expect("B7 首版确认 200", confirm.status_code, 200)
        v1 = confirm.json()["revisionId"]
        v1_before = harness.score_matrix(v1, limit=200).json()

        # 确认后新增参测人次 G（真实 API）
        g = harness.create_student(name="G", student_no="0007", class_id=scene["class"]["id"], joined_on=B.days_before(30))
        added = harness.add_participants(
            assessment_id,
            expected_revision=harness.assessment(assessment_id)["assessment"]["revision"],
            submission_id="snap-g",
            student_id=g["id"],
            class_id=scene["class"]["id"],
        )
        verdict.expect("B7 新增人次 200", added.status_code, 200)
        g_pid = added.json()["participants"][-1]["participantId"]

        v1_after = harness.score_matrix(v1, limit=200).json()
        verdict.expect("历史修订仍 total=2（不受新增影响）", v1_after["total"], 2)
        verdict.expect(
            "历史修订 missing 口径不变",
            (v1_after["missingCellCount"], v1_after["missingParticipantIds"]),
            (v1_before["missingCellCount"], v1_before["missingParticipantIds"]),
        )
        verdict.expect("历史修订未被判不全（读得到）", v1_after["revision"]["state"], "confirmed")

        # 新 draft：**不含 G** 的快照 + 对应完整矩阵 → 闸门放行（证明按自己的快照）
        harness.raw_exec_many(
            [
                (
                    "INSERT INTO score_revisions (id, assessment_id, version, source_import_id, "
                    "base_revision_id, state, participant_snapshot_json, item_snapshot_json, "
                    "confirmed_at, created_at) "
                    "SELECT 'snap-own', assessment_id, 91, NULL, NULL, 'draft', "
                    "participant_snapshot_json, item_snapshot_json, NULL, created_at "
                    "FROM score_revisions WHERE id = ?",
                    (v1,),
                ),
                (
                    "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
                    "participant_id, item_id, score_units, status) "
                    "SELECT 'snap-own', assessment_id, paper_revision_id, participant_id, item_id, "
                    "score_units, status FROM student_item_scores WHERE score_revision_id = ?",
                    (v1,),
                ),
            ]
        )
        try:
            harness.raw_exec(
                "UPDATE score_revisions SET state='confirmed', confirmed_at='2026-10-01T00:00:00Z' "
                "WHERE id='snap-own'"
            )
            verdict.check("不含 G 的快照 + 对应矩阵 → 封存放行", True, None)
        except sqlite3.IntegrityError as exc:
            verdict.check("不含 G 的快照 + 对应矩阵 → 封存放行", False, str(exc))

        # 新 draft：**含 G** 的快照 + 少 G 的矩阵 → 闸门拒绝
        harness.raw_exec(
            "INSERT INTO score_revisions (id, assessment_id, version, source_import_id, base_revision_id, "
            "state, participant_snapshot_json, item_snapshot_json, confirmed_at, created_at) "
            "SELECT 'snap-with-g', assessment_id, 92, NULL, NULL, 'draft', "
            "json_insert(participant_snapshot_json, '$[#]', json_object("
            "'participantId', ?, 'studentId', ?, 'studentNo', '0007', 'name', 'G', "
            "'classId', ?, 'attemptNo', 1, 'attendance', 'present')), "
            "item_snapshot_json, NULL, created_at FROM score_revisions WHERE id = ?",
            (g_pid, g["id"], scene["class"]["id"], v1),
        )
        harness.raw_exec(
            "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
            "participant_id, item_id, score_units, status) "
            "SELECT 'snap-with-g', assessment_id, paper_revision_id, participant_id, item_id, "
            "score_units, status FROM student_item_scores WHERE score_revision_id = ?",
            (v1,),
        )
        try:
            harness.raw_exec(
                "UPDATE score_revisions SET state='confirmed', confirmed_at='2026-10-01T00:00:00Z' "
                "WHERE id='snap-with-g'"
            )
            verdict.check("含 G 的快照 + 少 G 的矩阵 → SCORE_MATRIX_INCOMPLETE", False, "不应成功")
        except sqlite3.IntegrityError as exc:
            verdict.check(
                "含 G 的快照 + 少 G 的矩阵 → SCORE_MATRIX_INCOMPLETE",
                "SCORE_MATRIX_INCOMPLETE" in str(exc),
                str(exc),
            )

    return verdict.finish(path=HERE / "p25_migrations.json")


if __name__ == "__main__":
    sys.exit(main())
