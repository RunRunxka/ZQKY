"""Pure integer-unit any_loss_v1 rules; no current catalog reads or IO."""
from collections import defaultdict

STATES = ("recorded", "missing", "absent", "exempt")


def aggregate(facts: dict) -> dict:
    items = {item["itemId"]: item for item in facts["items"]}
    cells = {(cell["participantId"], cell["itemId"]): cell for cell in facts["cells"]}
    kp_items = defaultdict(list)
    for item in items.values():
        for kp in item["knowledgePoints"]:
            kp_items[kp["knowledgePointId"]].append(item)
    students, classes = [], []
    by_class = defaultdict(list)
    for participant in facts["participants"]:
        pid = participant["participantId"]
        all_cells = [cells[(pid, iid)] for iid in items]
        total = (sum(cell["scoreUnits"] for cell in all_cells)
                 if all(cell["status"] == "recorded" for cell in all_cells) else None)
        for kp in facts["knowledgePoints"]:
            linked = kp_items[kp["knowledgePointId"]]
            counts = dict.fromkeys(STATES, 0)
            has_loss = False
            for item in linked:
                cell = cells[(pid, item["itemId"])]
                counts[cell["status"]] += 1
                if cell["status"] == "recorded" and cell["scoreUnits"] < item["maxScoreUnits"]:
                    has_loss = True
            valid, expected = counts["recorded"], len(linked)
            incomplete = valid < expected
            observation = ("needs_consolidation" if has_loss else "no_evidence" if valid == 0
                           else "incomplete" if incomplete else "full_credit")
            row = {"participant": participant, "knowledgePoint": kp, "observation": observation,
                   "informationIncomplete": incomplete, "expectedCount": expected,
                   "validCount": valid, "stateCounts": counts, "totalScoreUnits": total,
                   "totalMaxScoreUnits": sum(item["maxScoreUnits"] for item in items.values())}
            students.append(row)
            by_class[(participant["classId"], kp["knowledgePointId"])].append(row)
    for (class_id, _), rows in sorted(by_class.items()):
        needs = sum(row["observation"] == "needs_consolidation" for row in rows)
        valid = sum(row["validCount"] > 0 for row in rows)
        # 纯计算无法 JOIN：className 落 None 占位，展示名由读路径按同 owner 实时
        # 补 classes.name（名称优先）；classNameNote 保留兼容旧前端。
        classes.append({"classId": class_id, "className": None, "classNameNote": "该成绩未记录班名",
                        "knowledgePoint": rows[0]["knowledgePoint"], "selectedCount": len(rows),
                        "validCount": valid, "needsCount": needs,
                        "incompleteCount": sum(row["informationIncomplete"] for row in rows),
                        "noEvidenceCount": sum(row["observation"] == "no_evidence" for row in rows),
                        "fullCreditCount": sum(row["observation"] == "full_credit" for row in rows),
                        "numerator": needs, "denominator": valid,
                        "ratio": needs / valid if valid else None})
    return {"students": students, "classes": classes}
