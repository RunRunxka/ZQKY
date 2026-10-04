"""Independent read-only SQLite/managed-file oracle after the actual browser chain.

Own seed only. No production imports, migrations, aggregators or writes to DB.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile


def verify(seed_path,chain_path,output):
    seed_path=Path(seed_path).resolve()
    seed=json.loads(seed_path.read_text(encoding="utf-8"))
    data=Path(seed["dataDir"]).resolve();temporary=data.parent
    assert temporary.name.startswith("zqky-b4-v00-") and temporary.is_relative_to(Path(tempfile.gettempdir()).resolve())
    assert seed_path.parent==temporary
    chain=json.loads(Path(chain_path).read_text(encoding="utf-8"));assert chain["seed"]==seed
    checks={};teaching=None
    try:
        for name,raw in seed["catalogPaths"].items():
            path=Path(raw).resolve();assert path.is_relative_to(data)
            connection=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
            connection.row_factory=sqlite3.Row;connection.execute("PRAGMA query_only=ON")
            integrity=connection.execute("PRAGMA integrity_check").fetchall();foreign=connection.execute("PRAGMA foreign_key_check").fetchall()
            assert [r[0] for r in integrity]==["ok"] and foreign==[]
            checks[name]=dict(path=str(path),integrity="ok",foreignKeyViolations=0)
            if name=="teaching":teaching=connection
            else:connection.close()
        assert teaching is not None
        conversion=chain["conversion"];returned=chain["returnedAnalysis"];score=chain["returnedScore"]
        actual=teaching.execute("SELECT * FROM practice_conversions WHERE id=?",(conversion["conversionId"],)).fetchone()
        assert actual["assessment_id"]==conversion["assessmentId"] and actual["practice_revision_id"]==conversion["practiceRevisionId"] and actual["paper_revision_id"]==conversion["paperRevisionId"]
        mappings=teaching.execute("SELECT m.*,p.question_no AS practice_no,p.max_score_units AS practice_max,i.question_no AS paper_no,i.max_score_units AS paper_max,i.ordinal,i.content_json AS paper_content,p.content_json AS practice_content FROM practice_paper_item_mappings m JOIN practice_items p ON p.id=m.practice_item_id JOIN paper_items i ON i.id=m.paper_item_id WHERE m.conversion_id=? ORDER BY i.ordinal",(conversion["conversionId"],)).fetchall()
        assert len(mappings)==2
        assert [r["practice_no"] for r in mappings]==["16(1)","2"]
        assert [r["practice_max"] for r in mappings]==[250,200]
        for row in mappings:
            assert row["paper_no"]==row["practice_no"] and row["paper_max"]==row["practice_max"]
            assert json.loads(row["paper_content"])==json.loads(row["practice_content"])
        run=teaching.execute("SELECT * FROM analysis_runs WHERE id=?",(returned["runId"],)).fetchone()
        assert run["report_ready"]==1 and run["score_revision_id"]==score["revisionId"] and run["assessment_id"]==conversion["assessmentId"]
        snapshots={r["item_id"]:json.loads(r["snapshot_json"]) for r in teaching.execute("SELECT * FROM analysis_item_snapshots WHERE run_id=?",(returned["runId"],))}
        mapping_by_paper={r["paper_item_id"]:r for r in mappings}
        for item_id,snapshot in snapshots.items():
            mapping=mapping_by_paper[item_id]
            assert snapshot["practiceRevisionId"]==conversion["practiceRevisionId"] and snapshot["practiceItemId"]==mapping["practice_item_id"]
        # Handwritten facts, independent of production aggregation and API totals.
        expected={seed["students"][0]["id"]:[("recorded",0),("recorded",150)],seed["students"][1]["id"]:[("recorded",250),("missing",None)],seed["students"][2]["id"]:[("absent",None),("absent",None)],seed["students"][3]["id"]:[("recorded",250),("recorded",200)]}
        cells=teaching.execute("SELECT e.*,p.student_id FROM analysis_evidence e JOIN analysis_participants p ON p.run_id=e.run_id AND p.participant_id=e.participant_id WHERE e.run_id=?",(returned["runId"],)).fetchall()
        assert len(cells)==8
        api_by_id={r["evidenceId"]:r for r in chain["returnedEvidence"]["items"]}
        for cell in cells:
            ordinal=mapping_by_paper[cell["item_id"]]["ordinal"]
            assert (cell["status"],cell["score_units"])==expected[cell["student_id"]][ordinal-1]
            api=api_by_id[cell["id"]]
            assert api["itemId"]==cell["item_id"] and api["status"]==cell["status"] and api["scoreUnits"]==cell["score_units"]
            stored=teaching.execute("SELECT status,score_units FROM student_item_scores WHERE score_revision_id=? AND participant_id=? AND item_id=?",(score["revisionId"],cell["participant_id"],cell["item_id"])).fetchone()
            assert tuple(stored)==(cell["status"],cell["score_units"])
        exports=[]
        for variant,artifact in chain["metadata"].items():
            row=teaching.execute("SELECT a.*,f.blob_key,f.owner_id AS file_owner,e.variant,e.assessment_id,e.frozen_input_json,w.state,w.result_json FROM export_artifacts a JOIN file_assets f ON f.id=a.file_asset_id JOIN practice_exports e ON e.id=a.export_id JOIN workflow_jobs w ON w.id=e.job_id WHERE a.id=?",(artifact["artifactId"],)).fetchone()
            assert row["state"]=="succeeded" and row["owner_id"]==row["file_owner"]=="local"
            assert row["variant"]==variant and row["practice_revision_id"]==conversion["practiceRevisionId"]
            frozen=json.loads(row["frozen_input_json"])
            if variant=="score_template":
                assert row["assessment_id"]==conversion["assessmentId"] and len(frozen["participants"])==4 and len(frozen["leaves"])==2
            else:assert row["assessment_id"] is None
            blob=(data/"assets"/row["blob_key"]).resolve();assert blob.is_relative_to(data/"assets")
            payload=blob.read_bytes();assert len(payload)==row["byte_size"]==artifact["byteSize"] and hashlib.sha256(payload).hexdigest()==row["sha256"]==artifact["sha256"]
            exports.append(dict(artifactId=row["id"],variant=variant,sha256=row["sha256"],byteSize=len(payload)))
        old=teaching.execute("SELECT report_ready,selected_count,leaf_count FROM analysis_runs WHERE id=?",(chain["analysis"]["runId"],)).fetchone();assert tuple(old)==(1,4,3)
        assert teaching.execute("SELECT count(*) FROM analysis_evidence WHERE run_id=?",(chain["analysis"]["runId"],)).fetchone()[0]==12
        counts={t:teaching.execute("SELECT count(*) FROM "+t).fetchone()[0] for t in ("analysis_runs","analysis_participants","analysis_item_snapshots","analysis_student_results","analysis_class_results","analysis_evidence","analysis_teacher_notes","practice_sets","practice_revisions","practice_selections","practice_items","practice_item_knowledge","practice_conversions","practice_paper_item_mappings","practice_exports","export_artifacts")}
        assert all(value>0 for value in counts.values())
        result=dict(task="B4-V00-F v1 real browser fourDB check",databases=checks,conversion=dict(actual),mappings=[dict(r) for r in mappings],returnedEvidenceCount=8,oldEvidenceCount=12,exports=exports,b4TableCounts=counts,readonly=True)
        Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    finally:
        if teaching is not None:teaching.close()
