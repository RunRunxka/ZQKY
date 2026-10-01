"""V00 · B3-A1 正常链：XLSX 上传 → 自动映射 → PATCH 修正 → 预览承认 → 确认 → 修订/矩阵。

自建探针（真 `create_app` + TestClient + 真 ScoreService/真 SQLite 触发器；无实现者测试夹具）。

样本（授权样例三叶 Q1=2/Q2=3/Q3=5 分，×100 单位）：
  A 全部 recorded、D 显式记录 0、B 空白 missing、C 缺考 absent、E 免考 exempt、
  另有一行"学号 9999/姓名 冯"未匹配 → PATCH 指定为 F 的人次并做一处单元格校正。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p20_normal_chain.py
退出码 0 = 全部断言通过；1 = 存在失败（failures 数组给出首败）。
"""

from __future__ import annotations

import sys
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
    ("0005", "E", None, None, None),
    ("9999", "冯", 1, 2, 3),  # 未匹配 → 教师 PATCH 指定为 F
)


def main() -> int:
    verdict = B.Verdict("p20_normal_chain")
    with B.Harness(tag="normal") as harness:
        scene = harness.sample_scene(
            tag="normal",
            leaves=LEAVES,
            students=(
                ("A", "0001", "present"),
                ("B", "0002", "present"),
                ("C", "0003", "absent"),
                ("D", "0004", "present"),
                ("E", "0005", "exempt"),
                ("F", "0006", "present"),
            ),
        )
        assessment_id = scene["assessment"]["assessmentId"]
        class_id = scene["class"]["id"]
        path = B.write_xlsx(Path(harness.settings.data_dir) / "scores.xlsx", HEADER, ROWS)

        # ---- 1. 上传 + 自动映射
        upload = harness.upload_scores(assessment_id, path)
        verdict.expect("上传 201", upload.status_code, 201)
        view = upload.json() if upload.status_code == 201 else {}
        verdict.expect("上传后 state=reviewing", view.get("state"), "reviewing")
        verdict.expect("rowCount=6", view.get("rowCount"), 6)
        mapping = view.get("mapping") or {}
        verdict.expect("自动识别学号列=A", mapping.get("studentNoColumn"), "A")
        verdict.expect("自动识别姓名列=B", mapping.get("nameColumn"), "B")
        verdict.expect(
            "自动映射计分列",
            [(c["itemId"], c["column"]) for c in mapping.get("itemColumns", [])],
            [
                (scene["paper"]["itemIds"][0], "C"),
                (scene["paper"]["itemIds"][1], "D"),
                (scene["paper"]["itemIds"][2], "E"),
            ],
        )
        verdict.expect("resolvedRowCount=5（第 7 行未匹配）", view.get("resolvedRowCount"), 5)
        # 上传时 missing = B 的 Q3 空白 1 格 + 未匹配的第 7 行 3 叶 = 4；PATCH 指定人次后应回到 1
        verdict.expect("上传时 missingCellCount=4", view.get("missingCellCount"), 4)
        verdict.check(
            "未匹配行是阻断问题且带 rowNo",
            any(
                issue.get("code") == "SCORE_ROW_UNRESOLVED" and issue.get("row") == 7
                for issue in view.get("issues", [])
            ),
            view.get("issues"),
        )

        # ---- 2. PATCH 修正：未匹配行指定为 F 的人次 + 一处单元格校正
        f_pid = scene["byName"]["F"]["participantId"]
        patch1 = harness.patch_import(
            view["importId"],
            {"expectedRevision": view["revision"], "rows": [{"rowNo": 7, "participantId": f_pid}]},
        )
        verdict.expect("PATCH 指定人次 200", patch1.status_code, 200)
        view = patch1.json()
        verdict.expect("PATCH 后 revision=1", view.get("revision"), 1)
        verdict.expect("PATCH 后 previewVersion=1", view.get("previewVersion"), 1)
        verdict.expect("PATCH 后 resolvedRowCount=6", view.get("resolvedRowCount"), 6)
        verdict.expect("PATCH 后 missingCellCount 仍=1", view.get("missingCellCount"), 1)
        verdict.expect("PATCH 后 issues 空", view.get("issues"), [])

        patch2 = harness.patch_import(
            view["importId"],
            {
                "expectedRevision": view["revision"],
                "rows": [
                    {"rowNo": 7, "cells": [{"row": 7, "column": "C", "text": "1.5"}]},
                ],
            },
        )
        verdict.expect("PATCH 单元格校正 200", patch2.status_code, 200)
        view = patch2.json()
        verdict.expect("校正后 revision=2", view.get("revision"), 2)
        verdict.expect("校正后 previewVersion=2", view.get("previewVersion"), 2)
        verdict.expect("校正后 missingCellCount 仍=1", view.get("missingCellCount"), 1)

        # 行视图：F 行 Q1 文本 = 1.5
        rows_view = harness.import_rows(view["importId"]).json()
        row7 = next(row for row in rows_view["items"] if row["rowNo"] == 7)
        cell_c = next(cell for cell in row7["cells"] if cell["column"] == "C")
        verdict.expect("行视图 F 的 Q1 文本", cell_c.get("text"), "1.5")

        # ---- 3. 确认（承认范围 = 本地推导的 absent 名单 + missing 统计）
        assessment_revision = harness.assessment(assessment_id)["assessment"]["revision"]
        c_pid = scene["byName"]["C"]["participantId"]
        b_pid = scene["byName"]["B"]["participantId"]
        body = {
            "expectedImportRevision": view["revision"],
            "expectedAssessmentRevision": assessment_revision,
            "baseScoreRevisionId": None,
            "previewVersion": view["previewVersion"],
            "submissionId": "confirm-normal-1",
            "absences": [{"classId": class_id, "participantIds": [c_pid]}],
            "missing": {"participantIds": [b_pid], "cellCount": 1},
        }
        confirm = harness.confirm_import(view["importId"], body)
        verdict.expect("确认 200", confirm.status_code, 200)
        result = confirm.json() if confirm.status_code == 200 else {}
        verdict.expect("确认 state=confirmed", result.get("state"), "confirmed")
        verdict.expect("首个版本 revisionId 非空", bool(result.get("revisionId")), True)
        verdict.expect("activeScoreRevisionId=revisionId", result.get("activeScoreRevisionId"), result.get("revisionId"))
        verdict.expect("assessmentRevision+1", result.get("assessmentRevision"), assessment_revision + 1)
        verdict.expect("replayed=false", result.get("replayed"), False)

        # ---- 4. 读修订
        revisions = harness.score_revisions(assessment_id).json()
        verdict.expect("修订历史 1 条", revisions["total"], 1)
        revision = revisions["items"][0]
        verdict.expect("修订 state=confirmed", revision["state"], "confirmed")
        verdict.expect("修订 version=1", revision["version"], 1)
        verdict.expect("修订来源批次", revision["sourceImportId"], view["importId"])
        verdict.expect("baseRevisionId=null（首个版本）", revision["baseRevisionId"], None)
        verdict.expect("participantSnapshot 6 人次", len(revision["participantSnapshot"]), 6)
        verdict.expect("itemSnapshot 3 叶", len(revision["itemSnapshot"]), 3)
        verdict.expect(
            "itemSnapshot 满分与顺序",
            [(item["itemPath"], item["maxScoreUnits"]) for item in revision["itemSnapshot"]],
            [("Q1", 200), ("Q2", 300), ("Q3", 500)],
        )

        # ---- 5. 读矩阵（全量 + 分页）
        matrix = harness.score_matrix(result["revisionId"], limit=200)
        verdict.expect("矩阵 200", matrix.status_code, 200)
        page = matrix.json()
        verdict.expect("矩阵 total=6", page["total"], 6)
        verdict.expect("矩阵 items=3", len(page["items"]), 3)
        verdict.expect("矩阵 missingCellCount=1", page["missingCellCount"], 1)
        verdict.expect("矩阵 missingParticipantIds=[B]", page["missingParticipantIds"], [b_pid])
        verdict.expect("矩阵 absentClassIds=[班级]", page["absentClassIds"], [class_id])

        table = B.matrix_map(page)
        for name in ("A", "B", "C", "D", "E", "F"):
            verdict.check(f"矩阵含人次 {name}", name in table, list(table))

        a = table["A"]["participant"]
        verdict.expect("A.totalUnits=900（2+2+5）", a["totalUnits"], 900)
        verdict.expect("A.totalMaxUnits=1000", a["totalMaxUnits"], 1000)

        b = table["B"]["participant"]
        verdict.expect("B.totalUnits=null（有 missing）", b["totalUnits"], None)
        b_cells = table["B"]["cells"]
        verdict.expect(
            "B 三态 recorded/recorded/missing",
            [b_cells[i]["status"] for i in scene["paper"]["itemIds"]],
            ["recorded", "recorded", "missing"],
        )

        c = table["C"]["participant"]
        verdict.expect("C.attendance=absent", c["attendance"], "absent")
        verdict.expect("C.totalUnits=null", c["totalUnits"], None)
        verdict.expect(
            "C 三叶全 absent",
            {table["C"]["cells"][i]["status"] for i in scene["paper"]["itemIds"]},
            {"absent"},
        )

        d = table["D"]["participant"]
        d_cells = table["D"]["cells"]
        verdict.expect("D 的 Q1 = recorded(0)", d_cells[scene["paper"]["itemIds"][0]]["status"], "recorded")
        verdict.expect("D 的 Q1 scoreUnits=0", d_cells[scene["paper"]["itemIds"][0]]["scoreUnits"], 0)
        verdict.expect("D.totalUnits=800（0+3+5）", d["totalUnits"], 800)

        e = table["E"]["participant"]
        verdict.expect("E.attendance=exempt", e["attendance"], "exempt")
        verdict.expect("E.totalUnits=null", e["totalUnits"], None)
        verdict.expect(
            "E 三叶全 exempt",
            {table["E"]["cells"][i]["status"] for i in scene["paper"]["itemIds"]},
            {"exempt"},
        )

        f = table["F"]["participant"]
        verdict.expect("F.totalUnits=650（1.5+2+3）", f["totalUnits"], 650)

        # 分页
        page0 = harness.score_matrix(result["revisionId"], offset=0, limit=2).json()
        page2 = harness.score_matrix(result["revisionId"], offset=2, limit=2).json()
        page4 = harness.score_matrix(result["revisionId"], offset=4, limit=2).json()
        verdict.expect(
            "分页 rows/total/offset/limit",
            [
                (len(page0["rows"]), page0["total"], page0["offset"], page0["limit"]),
                (len(page2["rows"]), page2["total"], page2["offset"], page2["limit"]),
                (len(page4["rows"]), page4["total"], page4["offset"], page4["limit"]),
            ],
            [(2, 6, 0, 2), (2, 6, 2, 2), (2, 6, 4, 2)],
        )
        all_names = [
            row["participant"]["name"]
            for pagex in (page0, page2, page4)
            for row in pagex["rows"]
        ]
        verdict.expect("分页无重复覆盖全部 6 人", sorted(all_names), ["A", "B", "C", "D", "E", "F"])

        # ---- 6. 确认后批次冻结读取 + 数据库落点
        frozen = harness.import_view(view["importId"]).json()
        verdict.expect("确认后批次 state=confirmed", frozen["state"], "confirmed")
        verdict.expect("确认后批次 missingCellCount=1", frozen["missingCellCount"], 1)
        verdict.expect("确认后批次 resolvedRowCount=6", frozen["resolvedRowCount"], 6)

        verdict.expect("student_item_scores 行数=6×3", harness.count("student_item_scores"), 18)
        verdict.expect(
            "四态计数 recorded=11/missing=1/absent=3/exempt=3",
            {
                row["status"]: row["n"]
                for row in harness.raw(
                    "SELECT status, COUNT(*) AS n FROM student_item_scores GROUP BY status"
                )
            },
            {"recorded": 11, "missing": 1, "absent": 3, "exempt": 3},
        )
        summary = harness.raw(
            "SELECT summary_json FROM score_imports WHERE id = ?", (view["importId"],)
        )[0]["summary_json"]
        ack = __import__("json").loads(summary)["acknowledged"]
        verdict.expect("确认摘要承认 cellCount=1", ack["missing"]["cellCount"], 1)
        verdict.expect(
            "确认摘要承认缺考人次",
            [item["participantIds"] for item in ack["absences"]],
            [[c_pid]],
        )
        verdict.expect(
            "D 的 Q1 在库中 score_units=0 且 status=recorded",
            harness.raw(
                "SELECT status, score_units FROM student_item_scores "
                "WHERE participant_id=? AND item_id=?",
                (d["participantId"], scene["paper"]["itemIds"][0]),
            ),
            [{"status": "recorded", "score_units": 0}],
        )

    return verdict.finish(path=HERE / "p20_normal_chain.json")


if __name__ == "__main__":
    sys.exit(main())
