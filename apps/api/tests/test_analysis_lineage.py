"""True composite practice→paper mapping, including a later assessment of same fixed paper."""
import json
from app.contracts.b4 import AnalysisCreateRequest
from app.core.sqlite import now_iso
from tests.analysis_support import AnalysisScene


async def test_real_mappings_carry_fixed_practice_items_through_new_score(tmp_path):
    scene = AnalysisScene(tmp_path)
    source = await scene.ready()
    now = now_iso()
    content_json = json.dumps(scene.rich)
    with scene.catalog.write_transaction() as conn:
        conn.execute("INSERT INTO practice_sets(id,analysis_run_id,subject_id,title,created_at) VALUES('set',?,'math','针对练习',?)", (source.run_id, now))
        conn.execute("INSERT INTO practice_revisions(id,practice_set_id,version,input_hash,selection_snapshot_json,constraints_json,title_snapshot,created_at) VALUES('practice-r','set',1,?,'{}','{}','固定练习',?)", ("a" * 64, now))
        conn.execute("INSERT INTO practice_selections(id,practice_revision_id,item_key,ordinal,question_id,question_revision_id,question_content_hash,content_snapshot_json,metadata_snapshot_json,rich_assets_json,reason_json,source_snapshot_json,answer_state) VALUES('selection','practice-r','whole',1,'question','question-r',?,?, '{}','[]','{}','{}','provided')", ("b" * 64, content_json))
        for index, iid in enumerate(scene.item_ids):
            item = conn.execute("SELECT * FROM paper_items WHERE id=?", (iid,)).fetchone()
            conn.execute("INSERT INTO practice_items(id,practice_revision_id,selection_id,node_key,question_no,ordinal,is_scored,max_score_units,content_json,source_locator_json) VALUES(?,'practice-r','selection',?,?,?,1,?,?,?)",
                         (f"practice-{iid}", f"node-{iid}", item["question_no"], item["ordinal"], item["max_score_units"], content_json, json.dumps({"nodeKey": f"node-{iid}"})))
            for kp in conn.execute("SELECT * FROM paper_item_knowledge WHERE item_id=?", (iid,)):
                conn.execute("INSERT INTO practice_item_knowledge VALUES(?,'practice-r',?,?,?,'math','primary')",
                             (f"practice-{iid}", kp["knowledge_point_id"], kp["knowledge_revision_id"], kp["knowledge_name_snapshot"]))
        conn.execute("UPDATE practice_revisions SET state='reviewed',reviewed_at=?,total_score_units=1000 WHERE id='practice-r'", (now,))
        conn.execute("INSERT INTO papers(id,subject_id,title) VALUES('practice-paper','math','练习卷')")
        conn.execute("INSERT INTO paper_revisions(id,paper_id,version,source_practice_revision_id,total_score_units,title_snapshot,title_snapshot_source) VALUES('converted-paper-r','practice-paper',1,'practice-r',1000,'固定练习卷','human')")
        for index, iid in enumerate(scene.item_ids):
            conn.execute("INSERT INTO paper_items(id,paper_revision_id,question_no,ordinal,is_scored,max_score_units,content_json,source_locator_json,question_revision_id) SELECT ?,'converted-paper-r',i.question_no,i.ordinal,i.is_scored,i.max_score_units,i.content_json,?,s.question_revision_id FROM practice_items i JOIN practice_selections s ON s.id=i.selection_id AND s.practice_revision_id=i.practice_revision_id WHERE i.id=?",
                         (f"converted-{iid}", json.dumps({"practiceItemId": f"practice-{iid}", "practiceRevisionId": "practice-r"}), f"practice-{iid}"))
            conn.execute("INSERT INTO paper_item_knowledge(item_id,paper_revision_id,knowledge_point_id,knowledge_revision_id,knowledge_name_snapshot,role,source) SELECT ?,'converted-paper-r',knowledge_point_id,knowledge_revision_id,name_snapshot,role,'bank_confirmed' FROM practice_item_knowledge WHERE item_id=?",
                         (f"converted-{iid}", f"practice-{iid}"))
        conn.execute("UPDATE paper_revisions SET state='confirmed',confirmed_at=? WHERE id='converted-paper-r'", (now,))
        for aid in ("converted-assessment", "later-assessment"):
            conn.execute("INSERT INTO assessments(id,paper_revision_id,title,assessment_type,held_on) VALUES(?,'converted-paper-r','练习施测','practice','2026-10-02')", (aid,))
            conn.execute("INSERT INTO assessment_classes VALUES(?,'class')", (aid,))
        conn.execute("INSERT INTO practice_conversions(id,practice_revision_id,paper_revision_id,assessment_id,input_hash,participant_snapshot_json,created_at) VALUES('conversion','practice-r','converted-paper-r','converted-assessment',?,'[]',?)", ("c" * 64, now))
        for iid in scene.item_ids:
            conn.execute("INSERT INTO practice_paper_item_mappings VALUES('conversion','practice-r',?,?, 'converted-paper-r')", (f"practice-{iid}", f"converted-{iid}"))
        # A later explicitly created T30 assessment reuses this confirmed fixed paper.
        conn.execute("INSERT INTO assessment_participants(id,assessment_id,student_id,class_id,attendance,name_snapshot,student_no_snapshot) VALUES('later-p','later-assessment','s000','class','present','固定A','00000')")
        participant = {"participantId": "later-p", "studentId": "s000", "classId": "class", "studentNo": "00000", "name": "固定A", "attemptNo": 1, "attendance": "present"}
        items = [{"itemId": f"converted-{iid}", "itemPath": f"Q{n+1}", "maxScoreUnits": (200, 300, 500)[n]} for n, iid in enumerate(scene.item_ids)]
        conn.execute("INSERT INTO score_revisions(id,assessment_id,version,participant_snapshot_json,item_snapshot_json) VALUES('later-score','later-assessment',1,?,?)", (json.dumps([participant]), json.dumps(items)))
        conn.executemany("INSERT INTO student_item_scores VALUES('later-score','later-assessment','converted-paper-r','later-p',?,?,'recorded')", [(i["itemId"], i["maxScoreUnits"]) for i in items])
        conn.execute("UPDATE score_revisions SET state='confirmed',confirmed_at=? WHERE id='later-score'", (now,))
    receipt = await scene.service.create_run("later-assessment", AnalysisCreateRequest(submissionId="later", scoreRevisionId="later-score", selectedParticipantIds=["later-p"], ruleCode="any_loss_v1"))
    job = await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    assert job.state == "succeeded", job.error
    report = scene.service.read_ready_report(receipt.run_id)
    assert report["originalQuestionRevisionIds"] == ["question-r"]
    evidence = scene.service.list_report_rows(receipt.run_id, "evidence").items
    assert {(r.item_id, r.practice_revision_id, r.practice_item_id) for r in evidence} == {(f"converted-{iid}", "practice-r", f"practice-{iid}") for iid in scene.item_ids}
    assert scene.service.read_ready_report(source.run_id)["originalQuestionRevisionIds"] == []
