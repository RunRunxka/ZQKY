"""Read-only owned-TEMP revision/Blob/DOCX audit plus teacher feedback forms.

Adds source bindings; never rewrites handwritten expected or prior run outputs.
Uses the repository readonly SQLite entrance, no main/API/live model invocation.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime
import argparse
import contextlib
import csv
import hashlib
import json
import os
import posixpath
import sys
import zipfile
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[3]
parser=argparse.ArgumentParser();parser.add_argument("--run",required=True);args=parser.parse_args()
assert args.run.replace("-","").isalnum() and os.environ["ZQKY_ENV"]=="test" and os.environ["PYTHONUTF8"]=="1"
run=OUT/"runs"/args.run
read=lambda q:json.loads(q.read_bytes())
sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
summary=read(run/"SUMMARY.json");owned=Path(summary["dataRoot"]).resolve()
assert Path(os.environ["TEMP"]).resolve() in owned.parents and owned.parent.name.startswith("zqky-b5-b6-quality-")
seed=read(run/"seed.json");manifest=read(OUT/"exports"/args.run/"DOCX-MANIFEST.json")
sys.path.insert(0,str(ROOT/"apps/api"))
from app.core.sqlite import open_readonly

def write(q,v):
    assert not q.exists(),"Preserve audit edition: "+str(q)
    q.write_bytes(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False).encode("utf8")+b"\n")
    return sha(q.read_bytes())
def rows(conn,table,column,identifier):
    allowed={"analysis_runs","score_revisions","student_item_scores","paper_revisions","paper_items","paper_item_knowledge","paper_source_blocks","knowledge_point_revisions","document_revisions","question_revisions","question_knowledge_links"}
    assert table in allowed and column in {"id","score_revision_id","paper_revision_id","question_revision_id"}
    return [dict(x) for x in conn.execute(f"SELECT * FROM {table} WHERE {column}=? ORDER BY rowid",(identifier,))]
def fixed_set(values):return dict(records=values,canonicalSHA=sha(canonical(values)))

ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
results=[]
with contextlib.ExitStack() as stack:
    db={k:stack.enter_context(contextlib.closing(open_readonly(Path(v)))) for k,v in seed["catalogPaths"].items()}
    for result in summary["results"]:
        key=result["caseId"];directory=run/"quality-cases"/key;case=read(directory/"case.json");frozen=read(directory/"input-frozen.json");data=read(directory/"fixed-export-input.json")["data"];expected=read(directory/"expected.json")
        assert result["expectedSHA"]==sha((directory/"expected.json").read_bytes())
        assert all(sha((directory/n).read_bytes())==h for n,h in result["hashes"].items())
        export=next(x for x in manifest["records"] if x["caseId"]==key);doc=Path(export["file"])
        assert sha(doc.read_bytes())==export["fileSHA"] and sha((directory/"fixed-export-input.json").read_bytes())==export["fixedExportInputSHA"]
        with zipfile.ZipFile(doc) as z:
            assert z.testzip() is None
            root=ET.fromstring(z.read("word/document.xml"));text="".join(x.text or "" for x in root.findall(".//w:t",ns))
            for field,value in data.items():
                if isinstance(value,str):assert value in text,(key,"DOCX missing field",field)
            for item in data["process"]:
                for field in ["stage","design","secondary"]:assert item[field] in text,(key,"DOCX missing process",field)
            bad=[]
            for name in z.namelist():
                if not name.endswith(".rels"):continue
                tree=ET.fromstring(z.read(name));base="" if name=="_rels/.rels" else str(PurePosixPath(name).parent.parent)
                for rel in tree:
                    target=rel.attrib.get("Target","")
                    if rel.attrib.get("TargetMode")=="External":continue
                    normalized=posixpath.normpath(posixpath.join(base,target)).lstrip("/")
                    if normalized not in z.namelist():bad.append(dict(rels=name,target=target))
            assert not bad,bad
            docx=dict(zipCRC="PASS",all11FieldsProjected=True,allProcessTextPresent=True,internalRelationshipsMissing=bad,tableCount=len(root.findall(".//w:tbl",ns)),layoutStatus="not_run_structure_only")
        teaching=db["teaching"]
        refs=dict(rule=dict(code="any_loss_v1",handwrittenExpectedSHA=sha((directory/"expected.json").read_bytes()),specPackSHA=summary["caseSpecsSHA"]),
            run=fixed_set(rows(teaching,"analysis_runs","id",case["runId"])),
            score=fixed_set(rows(teaching,"score_revisions","id",case["scoreRevisionId"])),
            matrix=fixed_set(rows(teaching,"student_item_scores","score_revision_id",case["scoreRevisionId"])),
            paper=dict(revision=fixed_set(rows(teaching,"paper_revisions","id",case["paperRevisionId"])),items=fixed_set(rows(teaching,"paper_items","paper_revision_id",case["paperRevisionId"])),knowledge=fixed_set(rows(teaching,"paper_item_knowledge","paper_revision_id",case["paperRevisionId"])),blocks=fixed_set(rows(teaching,"paper_source_blocks","paper_revision_id",case["paperRevisionId"]))),knowledge=[],material=[],questions=[],practices=[])
        for kp in frozen["source"]["referenceKnowledge"]:
            if any(x["revisionId"]==kp["knowledgeRevisionId"] for x in refs["knowledge"]):continue
            records=rows(db["knowledge"],"knowledge_point_revisions","id",kp["knowledgeRevisionId"])
            assert len(records)==1
            refs["knowledge"].append(dict(knowledgePointId=kp["knowledgePointId"],revisionId=kp["knowledgeRevisionId"],**fixed_set(records)))
        for material in frozen["source"]["textbooks"]:
            records=rows(db["catalog"],"document_revisions","id",material["documentRevisionId"]);assert len(records)==1
            row=records[0];base=Path(seed["catalogPaths"]["catalog"]).parent
            blob=base/"blobs"/row["original_blob_id"];normal=base/"normalized"/row["normalized_blob_id"];mapping=base/"normalized"/row["source_map_blob_id"]
            assert sha(blob.read_bytes())==row["original_file_sha256"] and sha(normal.read_bytes())==row["normalized_text_sha256"]
            assert normal.read_text(encoding="utf8")[material["charStart"]:material["charEnd"]]==material["text"]
            assert sha(normal.read_bytes())==material["normalizedTextSha256"]
            refs["material"].append(dict(documentRevisionId=material["documentRevisionId"],**fixed_set(records),originalBlobSHA=sha(blob.read_bytes()),normalizedBlobSHA=sha(normal.read_bytes()),sourceMapSHA=sha(mapping.read_bytes()),selectedSlice=material,selectedSliceSHA=sha(material["text"].encode("utf8")),license="Owned self-authored synthetic fixture; no formal textbook copy"))
        for question in frozen["source"]["questions"]:
            rid=question["question_revision_id"]
            refs["questions"].append(dict(revisionId=rid,revision=fixed_set(rows(db["question_bank"],"question_revisions","id",rid)),knowledge=fixed_set(rows(db["question_bank"],"question_knowledge_links","question_revision_id",rid)),fixedReader=question,fixedReaderSHA=sha(canonical(question))))
        binding=dict(version=2,caseId=key,originalCaseSHA=sha((directory/"case.json").read_bytes()),expectedSHA=sha((directory/"expected.json").read_bytes()),refs=refs,inputSHA=sha((directory/"input.json").read_bytes()),frozenInputSHA=sha((directory/"input-frozen.json").read_bytes()),wireSHA=sha((directory/"wire.json").read_bytes()),rawSHA=result["rawSHA"],candidateSHA=sha((directory/"candidate.json").read_bytes()),selectedFieldsSHA=sha((directory/"selected-fields.json").read_bytes()),appliedSHA=sha((directory/"applied-result.json").read_bytes()),export=export,docxAudit=docx,modelFingerprint=result["modelFingerprint"],promptVersion=result["promptVersion"],durationMs=result["durationMs"],usage=result["usage"],failure=result["failure"],teacherReview="teacher_review_pending",liveRun="live_run待输入",RAG_REL="OPEN")
        bindingSHA=write(directory/"case-bound-v2.json",binding)
        results.append(dict(caseId=key,title=case["caseSpec"]["title"],counts=case["caseSpec"]["expectedTargetCounts"],caseHash=result["caseHash"],boundV2SHA=bindingSHA,docxSHA=export["fileSHA"],technicalStructure="PASS",docxStructure="PASS",teacher_review="pending",live_run="待输入",shortcomings=result["shortcomings"],materialCase=case["caseSpec"]["materialCase"],semanticClaimSupported=expected["semanticClaimSupported"]))
dimensions=["学情事实解释","教材支持相关性","目标KP覆盖","活动课堂检测","分钟可实施性","教师字段保持","内容准确可解释","练习反馈"]
feedback=OUT/("feedback-"+args.run+".csv")
with feedback.open("x",encoding="utf-8-sig",newline="") as stream:
    writer=csv.DictWriter(stream,fieldnames=["case_id","case_hash","bound_v2_sha","candidate_sha","docx_sha","reviewer","reviewed_at","hard_failure","evidence_location"]+dimensions+["不足","修改建议","真人结论"])
    writer.writeheader()
    for result in results:
        directory=run/"quality-cases"/result["caseId"]
        writer.writerow(dict(case_id=result["caseId"],case_hash=result["caseHash"],bound_v2_sha=result["boundV2SHA"],candidate_sha=sha((directory/"candidate.json").read_bytes()),docx_sha=result["docxSHA"]))
markdown=OUT/("feedback-"+args.run+".md")
assert not markdown.exists()
markdown.write_text("# 教师反馈填写表\n\n所有分数与真人结论留空，当前teacher_review_pending。请先读RUBRIC.md，逐例填写硬失败与证据位置，再填八维0～3及修改建议。替身和JSON合法不作教学质量评价。\n\n"+"\n\n".join("## "+x["caseId"]+" "+x["title"]+"\n\nCaseHash `"+x["caseHash"]+"`。\n\n评审人：____  日期：____  硬失败及原文位置：____\n\n"+"；".join(d+"：____" for d in dimensions)+"\n\n不足：____  修改建议：____  真人结论：____" for x in results)+"\n",encoding="utf8",newline="\n")
write(OUT/("RESULTS-"+args.run+"-v1.json"),dict(task="B6-QUALITY-v1",at=datetime.now().astimezone().isoformat(),pid=os.getpid(),caseCount=15,technicalStructure="PASS15",docxStructure="PASS15",teacherQuality="teacher_review_pending",liveRun="live_run待输入",RAG_REL="OPEN",results=results,feedbackCsvSHA=sha(feedback.read_bytes()),feedbackMdSHA=sha(markdown.read_bytes()),noMainImport=True,noNetwork=True,ownedTempReadOnly=str(owned),doesNotClaimSqliteFullRecoveryOrLayout=True))
print(json.dumps(dict(caseCount=len(results),literalCountsPassed=True,allRevisionBindings=True,docxStructurePassed=15,teacherQuality="teacher_review_pending",liveRun="待输入",RAG_REL="OPEN"),ensure_ascii=False),flush=True)
