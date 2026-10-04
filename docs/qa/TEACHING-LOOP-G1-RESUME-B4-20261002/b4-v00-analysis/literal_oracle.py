"""Independent literal expectations. No application imports or aggregation code."""
from copy import deepcopy

NOTE = "该成绩未记录班名"
ASSOCIATION = "综合题失分关联，具体错因待教师确认"
PEOPLE = {
    "p000": {"studentId": "s000", "studentNo": "00000", "name": "A", "attendance": "present"},
    "p001": {"studentId": "s001", "studentNo": "00001", "name": "B", "attendance": "present"},
    "p002": {"studentId": "s002", "studentNo": "00002", "name": "C", "attendance": "absent"},
    "p003": {"studentId": "s003", "studentNo": "00003", "name": "D", "attendance": "present"},
}
# observation, incomplete, valid, recorded/missing/absent/exempt, entire-test total.
STUDENTS = {
    ("p000", "k1"): ("needs_consolidation", False, 2, (2, 0, 0, 0), 900),
    ("p000", "k2"): ("needs_consolidation", False, 2, (2, 0, 0, 0), 900),
    ("p001", "k1"): ("full_credit", False, 2, (2, 0, 0, 0), None),
    ("p001", "k2"): ("incomplete", True, 1, (1, 1, 0, 0), None),
    ("p002", "k1"): ("no_evidence", True, 0, (0, 0, 2, 0), None),
    ("p002", "k2"): ("no_evidence", True, 0, (0, 0, 2, 0), None),
    ("p003", "k1"): ("needs_consolidation", False, 2, (2, 0, 0, 0), 800),
    ("p003", "k2"): ("full_credit", False, 2, (2, 0, 0, 0), 800),
}
# selected, valid, needs, incomplete, no-evidence, full-credit, numerator, denominator, ratio.
CLASSES = {
    ("class", "k1"): (4, 3, 2, 1, 1, 1, 2, 3, 2 / 3),
    ("class", "k2"): (4, 3, 1, 2, 1, 1, 1, 3, 1 / 3),
}
# All twelve participant × leaf cells are explicitly written, including full credit.
EVIDENCE = {
    ("p000", "i000"): ("recorded", 200),
    ("p000", "i001"): ("recorded", 200),
    ("p000", "i002"): ("recorded", 500),
    ("p001", "i000"): ("recorded", 200),
    ("p001", "i001"): ("recorded", 300),
    ("p001", "i002"): ("missing", None),
    ("p002", "i000"): ("absent", None),
    ("p002", "i001"): ("absent", None),
    ("p002", "i002"): ("absent", None),
    ("p003", "i000"): ("recorded", 0),
    ("p003", "i001"): ("recorded", 300),
    ("p003", "i002"): ("recorded", 500),
}
ITEMS = {
    "i000": ("Q1", 200, ["k1"], {"paragraphIndex": 0, "nodeKey": "node-0"}),
    "i001": ("Q2", 300, ["k1", "k2"], {"paragraphIndex": 1, "nodeKey": "node-1"}),
    "i002": ("Q3", 500, ["k2"], {"paragraphIndex": 2, "nodeKey": "node-2"}),
}
STATES = ("recorded", "missing", "absent", "exempt")
CLASS_FIELDS = ("selectedCount", "validCount", "needsCount", "incompleteCount", "noEvidenceCount",
                "fullCreditCount", "numerator", "denominator", "ratio")


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}; actual {actual!r}")


def fixed_kp(kp, kid):
    equal(kp, {"knowledgePointId": kid, "knowledgeRevisionId": kid + "-r",
               "name": "固定" + kid, "role": "primary"}, "fixed knowledge")


def participant(person, pid):
    equal(person, {"participantId": pid, **PEOPLE[pid], "classId": "class", "className": None,
                   "classNameNote": NOTE, "attemptNo": 1}, "frozen participant " + pid)


def student_rows(rows, expected=STUDENTS, *, expected_count=2, total_max=1000, check_people=True):
    keys = [(r["participant"]["participantId"], r["knowledgePoint"]["knowledgePointId"]) for r in rows]
    equal(len(keys), len(set(keys)), "unique student/KP rows")
    equal(set(keys), set(expected), "student/KP coverage")
    for row, key in zip(rows, keys):
        observation, incomplete, valid, counts, total = expected[key]
        if check_people:
            participant(row["participant"], key[0])
        fixed_kp(row["knowledgePoint"], key[1])
        for field, value in (("observation", observation), ("informationIncomplete", incomplete),
                             ("expectedCount", expected_count), ("validCount", valid),
                             ("stateCounts", dict(zip(STATES, counts))), ("totalScoreUnits", total),
                             ("totalMaxScoreUnits", total_max)):
            equal(row[field], value, f"{key}.{field}")


def class_rows(rows, expected=CLASSES):
    keys = [(r["classId"], r["knowledgePoint"]["knowledgePointId"]) for r in rows]
    equal(len(keys), len(set(keys)), "unique class/KP rows")
    equal(set(keys), set(expected), "class/KP coverage")
    for row, key in zip(rows, keys):
        equal(row["className"], None, "historical className")
        equal(row["classNameNote"], NOTE, "historical classNameNote")
        fixed_kp(row["knowledgePoint"], key[1])
        for field, value in zip(CLASS_FIELDS, expected[key]):
            equal(row[field], value, f"{key}.{field}")


def evidence_rows(rows, rich, run_id, *, score_revision="score-r", expected=EVIDENCE, check_people=True):
    keys = [(r["participant"]["participantId"], r["itemId"]) for r in rows]
    equal(len(keys), len(set(keys)), "unique participant/leaf evidence")
    equal(set(keys), set(expected), "complete evidence coverage")
    equal(len({r["evidenceId"] for r in rows}), len(expected), "unique evidence ids")
    source_blocks = [{"blockId": "shared", "ordinal": 1, "block": rich["sharedMaterials"][0]["blocks"][0],
                      "sourceLocator": {"paragraphIndex": 1}, "disposition": "shared_material",
                      "itemId": None, "excludeReason": None}]
    for row, key in zip(rows, keys):
        path, maximum, kids, locator = ITEMS[key[1]]
        if check_people:
            participant(row["participant"], key[0])
        for field, value in (("runId", run_id), ("scoreRevisionId", score_revision),
                             ("paperRevisionId", "paper-r"), ("itemPath", path), ("maxScoreUnits", maximum),
                             ("status", expected[key][0]), ("scoreUnits", expected[key][1]),
                             ("sourceLocator", locator), ("content", {**rich, "sourceBlocks": source_blocks}),
                             ("sharedMaterials", rich["sharedMaterials"]), ("assets", rich["assets"]),
                             ("practiceRevisionId", None), ("practiceItemId", None), ("associationNote", ASSOCIATION)):
            equal(row[field], value, f"{key}.{field}")
        equal([k["knowledgePointId"] for k in row["knowledgePoints"]], kids, "leaf knowledge links")
        for kp in row["knowledgePoints"]:
            fixed_kp(kp, kp["knowledgePointId"])


def base_packet(packet, rich):
    run = packet["run"]
    equal(run["paperTitle"], "固定标题", "fixed title")
    equal(run["scoreRevisionId"], "score-r", "fixed score revision")
    equal(run["paperRevisionId"], "paper-r", "fixed paper revision")
    equal(run["selectionSnapshot"], {"selectedParticipantIds": ["p000", "p001", "p002", "p003"],
          "uniqueStudentCount": 4, "participantCount": 4, "leafCount": 3,
          "stateCounts": {"recorded": 8, "missing": 1, "absent": 3, "exempt": 0}}, "selection snapshot")
    equal(run["reportReady"], True, "ready")
    equal(run["job"]["state"], "succeeded", "job state")
    equal({p["participantId"] for p in run["participants"]}, set(PEOPLE), "participants coverage")
    for p in run["participants"]:
        participant(p, p["participantId"])
    equal(len(run["knowledgePoints"]), 2, "fixed KP count")
    for k in run["knowledgePoints"]:
        fixed_kp(k, k["knowledgePointId"])
    student_rows(packet["students"])
    class_rows(packet["classes"])
    evidence_rows(packet["evidence"], rich, run["runId"])


def reject_wrong_outputs(packet, rich):
    """Only mutate copies of response JSON; never mutate the product or live database."""
    variants = []
    def variant(name, change):
        wrong = deepcopy(packet)
        change(wrong)
        variants.append((name, wrong))
    variant("recorded-zero-as-missing", lambda p: p["evidence"][9].update(status="missing", scoreUnits=None))
    variant("missing-as-zero", lambda p: p["evidence"][5].update(status="recorded", scoreUnits=0))
    variant("loss-only-evidence", lambda p: p["evidence"].pop(0))
    variant("multi-KP-evidence-duplicated", lambda p: p["evidence"].append(deepcopy(p["evidence"][1])))
    variant("selected-count-denominator", lambda p: p["classes"][0].update(denominator=4, ratio=0.5))
    variant("KP-double-count-total", lambda p: p["students"][0].update(totalScoreUnits=1100))
    variant("missing-student-total-filled", lambda p: p["students"][2].update(totalScoreUnits=500))
    variant("absence-as-full-credit", lambda p: p["students"][4].update(observation="full_credit"))
    variant("old-observation-literal", lambda p: p["students"][0].update(observation="needs_practice"))
    variant("live-class-name-in-history", lambda p: p["classes"][0].update(className="现班名"))
    variant("incomplete-erased", lambda p: p["students"][3].update(informationIncomplete=False))
    variant("material-truncated", lambda p: p["evidence"][0].update(sharedMaterials=[]))
    variant("source-blocks-missing", lambda p: p["evidence"][0]["content"].pop("sourceBlocks"))
    variant("assets-missing", lambda p: p["evidence"][0].update(assets=[]))
    rejected = []
    for name, wrong in variants:
        try:
            base_packet(wrong, rich)
        except AssertionError as error:
            rejected.append({"variant": name, "rejected": True, "reason": str(error)})
        else:
            raise AssertionError("independent oracle accepted wrong output: " + name)
    return rejected
