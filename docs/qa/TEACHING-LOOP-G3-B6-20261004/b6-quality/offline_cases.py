"""B6 quality preparation: real in-process API/Provider, HTTP transport only.

Runner establishes fresh TEMP/env=test/PYTHONUTF8 before this imports app.main.
All paper/score seeds use production repositories and confirmation guards.
Expected teacher-rule numbers are frozen in case-specs.json BEFORE execution.
No production aggregate or model output is used to construct an oracle.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
label=os.environ.get("B6_QUALITY_LABEL","")
assert label and os.environ.get("ZQKY_ENV")=="test" and os.environ.get("PYTHONUTF8")=="1"
data_root=Path(os.environ["ZQKY_DATA_DIR"]).resolve()
assert Path(os.environ["TEMP"]).resolve() in data_root.parents
assert data_root.parent.name.startswith("zqky-b5-b6-quality-") and not data_root.exists()
assert os.environ.get("ZQKY_KEEP_TEST_DATA")=="1"
run=OUT/"runs"/label
assert not run.exists(),"Never overwrite an earlier run"
run.mkdir(parents=True)
sys.path.insert(0,str(ROOT/"apps/api"))

from app.core.config import Settings
from app.core.secrets import SecretStore
from app.main import create_app
from app.repositories.teaching.papers import PaperRepository,ItemKnowledgeRecord
from app.repositories.teaching.scores import ScoreRepository
from app.contracts.scores import ScoreParticipantSnapshot,ScoreItemSnapshot
from app.services.lesson_generation.service import SYSTEM_PROMPT
from fastapi.testclient import TestClient

sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
def store(directory,name,value):
    q=directory/name
    assert not q.exists(),str(q)
    q.parent.mkdir(parents=True,exist_ok=True)
    q.write_bytes(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode("utf8")+b"\n")
    return sha(q.read_bytes())

seed_path=ROOT/"docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v3/browser/seed_runtime.py"
spec=importlib.util.spec_from_file_location("b6_quality_readonly_seed",seed_path)
seedmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(seedmod)
pack=json.loads((OUT/"case-specs.json").read_bytes())
pack_hash=sha((OUT/"case-specs.json").read_bytes())
settings=Settings(host="127.0.0.1",port=8001,allowed_origins=frozenset({"http://127.0.0.1:5174"}),env="test",data_dir=data_root,credentials_file=None,qdrant_url="http://127.0.0.1:16333",embedding_base_url="http://127.0.0.1:9",textbook_source_dir=Path(os.environ["ZQKY_TEXTBOOK_SOURCE_DIR"]))
assert settings.credentials_file is None
app=create_app(settings,bootstrap_textbooks=False,secret_store=SecretStore())
checks=[]; fixture=None

def request(client,method,path,expected=200,**kw):
    response=getattr(client,method)("/api/v1"+path,**kw)
    assert response.status_code==expected,(path,response.status_code,response.text)
    return response.json()

def ready(client,receipt):
    until=time.monotonic()+30
    while time.monotonic()<until:
        job=request(client,"get","/workflow-jobs/"+receipt["job"]["jobId"],params={"domain":"teaching"})
        if job["state"] in {"succeeded","failed","cancelled","interrupted"}:
            assert job["state"]=="succeeded",job
            return job
        time.sleep(.02)
    raise AssertionError("Bounded in-process job wait expired")

def paper_score_run(client,case,base,points):
    import uuid
    key=case["caseId"]
    with app.state.teaching.read_connection() as conn:
        paper_id=base["originalFixed"]["score"]["paperRevisionId"]
        original=conn.execute("SELECT source_file_id FROM paper_revisions WHERE id=?",(paper_id,)).fetchone()[0]
        rich=json.loads(conn.execute("SELECT content_json FROM paper_items WHERE paper_revision_id=? ORDER BY ordinal LIMIT 1",(paper_id,)).fetchone()[0])
    repository=PaperRepository(app.state.teaching)
    item_ids=[]
    with app.state.teaching.write_transaction() as conn:
        paper=repository.create_paper_in(conn,subject_id="math",title="匿名质量原卷"+key)
        revision=repository.create_revision_in(conn,paper_id=paper.paper_id,version=1,source_file_id=original,total_score_units=sum(x["maxScoreUnits"] for x in case["items"]),title_snapshot="匿名质量原卷"+key)
        for n,item in enumerate(case["items"]):
            iid=uuid.uuid4().hex; item_ids.append(iid)
            repository.insert_items_in(conn,paper_revision_id=revision.revision_id,items=[dict(item_id=iid,parent_item_id=None,question_no="Q"+str(n+1),ordinal=n+1,is_scored=True,max_score_units=item["maxScoreUnits"],content=rich,source_locator={"paragraphIndex":n+1})])
            repository.insert_item_knowledge_in(conn,item_id=iid,paper_revision_id=revision.revision_id,knowledge=[ItemKnowledgeRecord(points[k]["knowledgePointId"],points[k]["knowledgeRevisionId"],points[k]["name"],"primary","human") for k in item["knowledgeIndexes"]])
        repository.confirm_revision_in(conn,revision.revision_id)
        repository.set_current_revision_in(conn,paper.paper_id,revision.revision_id)
    class_count=max(x["classIndex"] for x in case["participants"])+1
    classes=[request(client,"post","/classes",201,json=dict(code="QA-"+key+"-"+str(n),name="当前匿名班"+key+"-"+str(n),schoolYear="2026",gradeId="g")) for n in range(class_count)]
    students={}
    for participant in case["participants"]:
        alias=participant["alias"]
        if alias not in students:
            students[alias]=request(client,"post","/students",201,json=dict(name="隔离样本"+key+"-"+alias,studentNo="QA-"+key+"-"+alias,classId=classes[participant["classIndex"]]["id"],joinedOn="2026-01-01"))
    participants=[dict(studentId=students[x["alias"]]["id"],classId=classes[x["classIndex"]]["id"],attendance=x["attendance"],attemptNo=x["attemptNo"]) for x in case["participants"]]
    assessment=request(client,"post","/assessments",201,json=dict(submissionId=key+"-assessment",paperRevisionId=revision.revision_id,title="匿名质量施测"+key,assessmentType="exam",heldOn="2026-10-04",classIds=[x["id"] for x in classes],participants=participants))
    ps=assessment["participants"]
    # Match explicit (student,class,attempt), never response order or highest score.
    actual=[]
    for requested in participants:
        actual.append(next(x for x in ps if x["studentId"]==requested["studentId"] and x["classId"]==requested["classId"] and x["attemptNo"]==requested["attemptNo"]))
    snapshots=[ScoreParticipantSnapshot.model_validate({k:x[k] for k in ["participantId","studentId","studentNo","name","classId","attemptNo","attendance"]}) for x in actual]
    score_repo=ScoreRepository(app.state.teaching)
    cells=[(actual[n]["participantId"],item_ids[m],state,units) for n,x in enumerate(case["participants"]) for m,(state,units) in enumerate(x["cells"])]
    with app.state.teaching.write_transaction() as conn:
        rid=score_repo.insert_revision_in(conn,assessment_id=assessment["assessment"]["assessmentId"],version=1,source_import_id=None,base_revision_id=None,participant_snapshot=snapshots,item_snapshot=[ScoreItemSnapshot(itemId=iid,itemPath="Q"+str(n+1),maxScoreUnits=case["items"][n]["maxScoreUnits"]) for n,iid in enumerate(item_ids)])
        score_repo.insert_matrix_in(conn,revision_id=rid,assessment_id=assessment["assessment"]["assessmentId"],paper_revision_id=revision.revision_id,cells=cells)
        score_repo.seal_revision_in(conn,rid)
        score_repo.set_active_revision_in(conn,assessment["assessment"]["assessmentId"],revision_id=rid,expected_revision=assessment["assessment"]["revision"])
    ids=[actual[n]["participantId"] for n in case["selectedParticipantIndexes"]]
    receipt=request(client,"post","/assessments/"+assessment["assessment"]["assessmentId"]+"/analysis-runs",202,json=dict(submissionId=key+"-analysis",scoreRevisionId=rid,selectedParticipantIds=ids,ruleCode="any_loss_v1"))
    ready(client,receipt)
    report=request(client,"get","/analysis-runs/"+receipt["runId"])
    rows=request(client,"get","/analysis-runs/"+receipt["runId"]+"/classes")["items"]
    klass=classes[case["selectedClassIndex"]]["id"]
    selected_points=[points[n] for n in case["selectedKnowledgeIndexes"]]
    for point,expected in zip(selected_points,case["expectedTargetCounts"]):
        row=next(x for x in rows if x["classId"]==klass and x["knowledgePoint"]["knowledgePointId"]==point["knowledgePointId"])
        assert {k:row[k] for k in expected}==expected,(key,"literal teacher oracle mismatch",row,expected)
        assert row["className"] is None and row["classNameNote"]=="该成绩未记录班名"
    return dict(assessment=assessment,score=request(client,"get","/score-revisions/"+rid),report=report,classes=rows,selectedClassId=klass,selectedPoints=selected_points,selectedParticipantIds=ids,matrix=[dict(participantId=pid,itemId=iid,status=state,scoreUnits=units) for pid,iid,state,units in cells],paperRevisionId=revision.revision_id)

def answer(case):
    ids=["new:N1","new:N2","new:N3","new:N4"]
    aliases=["K"+str(n+1) for n in range(len(case["selectedKnowledgeIndexes"]))]
    return dict(patch=dict(coreCompetencies="以依据解释有理数运算，保持审慎判断。",keyPoints="符号与绝对值判断；不从总失分臆造具体错因。",teachingDesign=case["interpretation"],exercises="待教师审核的课堂检测建议；不是自动发布的正式题库对象。",process=[dict(id=i,stage=s,design=case["interpretation"],secondary="教师可补充原题核对与课堂观察。") for i,s in zip(ids,["观察导入","探究依据","独立检测","归纳反馈"])]),budget=dict(durationMinutes=case["durationMinutes"],stages=[dict(processId=i,phase=phase,minutes=minutes,knowledgeAliases=aliases,activity="对照固定片段解释并核对步骤。",check="口头说明与出口检测，具体原因待核实。",evidenceAliases=["E1"]) for i,phase,minutes in zip(ids,["introduction","exploration","practice","conclusion"],case["stageMinutes"])]))

started=time.perf_counter()
try:
    with TestClient(app,base_url="http://127.0.0.1:8001") as client:
        base,fixture=seedmod.seed_for_browser(app,run/"seed.json",client=client,tag="b6-quality-seed")
        fixture.install()
        points=copy.deepcopy(base["originalFixed"]["report"]["knowledgePoints"])
        gap_point=request(client,"post","/knowledge-points",201,json=dict(subjectId="math",code="B6-QUALITY-GAP",name="无题有理数巩固"))
        points.append(dict(knowledgePointId=gap_point["id"],knowledgeRevisionId=gap_point["revisionId"],name=gap_point["name"],role="primary"))
        for case in pack["cases"]:
            directory=run/"quality-cases"/case["caseId"];directory.mkdir(parents=True)
            # Freeze literal expected and handwritten per-student source BEFORE APIs.
            expectedSHA=store(directory,"expected.json",dict(ruleCode="any_loss_v1",rationale=case["rationale"],expectedTargetCounts=case["expectedTargetCounts"],teacherPreservedFields=["title","totalLessons","currentLessonNo","lessonTypes","otherTypeText","reflection"],selectedFields=case["selectedFields"],historicalClassName=None,historicalClassNameNote="该成绩未记录班名",semanticClaimSupported=case["requestedClaimSupported"],humanReviewStatus="teacher_review_pending",notProducedBy="aggregate/model/candidate"))
            store(directory,"student-state-table.json",dict(items=case["items"],participants=case["participants"],selectedIndexes=case["selectedParticipantIndexes"],selectedClassIndex=case["selectedClassIndex"],selectedKnowledgeIndexes=case["selectedKnowledgeIndexes"]))
            t0=time.perf_counter();facts=paper_score_run(client,case,base,points)
            verified=copy.deepcopy(base["verifiedEvidence"])
            if case["materialCase"]=="boundary":
                text=base["textbook"]["normalizedText"]; start=text.index("有理数加法"); end=text.index("。",start)+1
                verified=request(client,"post","/lesson-plans/evidence/verify",json=dict(selection=base["textbook"]["selection"],slices=[dict(documentRevisionId=base["textbook"]["documentRevisionId"],charStart=start,charEnd=end)]))
            knowledge=[x["knowledgePointId"] for x in facts["selectedPoints"]]
            original=copy.deepcopy(base["originalLessonData"]);original["title"]="匿名质量"+case["caseId"]+"有理数加法"
            original["reflection"]="教师反思独立哨兵《保持》 & < > 中文"
            context=dict(analysisRunId=facts["report"]["runId"],selectedKnowledgePointIds=knowledge)
            lesson=request(client,"post","/lesson-plans",201,json=dict(submissionId=case["caseId"]+"-lesson",subjectId="math",classId=facts["selectedClassId"],data=original,context=context,source="manual"))
            question_ids=[base["questionRevisionId"]] if case["questionSource"]=="confirmed" else []
            gap=None
            if not question_ids:
                practice=request(client,"post","/practice-sets",201,json=dict(submissionId=case["caseId"]+"-gap-practice",analysisRunId=facts["report"]["runId"],title="匿名质量覆盖缺口",targetKnowledgePointIds=knowledge,constraints={"count":1}))
                gap=request(client,"post","/practice-sets/"+practice["practiceSetId"]+"/suggestions",json=dict(expectedRevision=0,constraints={"count":1}))
                assert gap["selectedCount"]==0 and gap["gaps"],gap
            generate=dict(submissionId=case["caseId"]+"-generate",baseRevisionId=lesson["currentRevisionId"],baseServerRevision=lesson["revision"],analysisRunId=facts["report"]["runId"],classId=facts["selectedClassId"],selectedKnowledgePointIds=knowledge,requirements=case["requirements"],durationMinutes=case["durationMinutes"],modelProfileId=base["modelProfiles"][0]["profileId"],scopeSnapshot=verified["scopeSnapshot"],evidenceRefs=verified["evidenceRefs"],questionRevisionIds=question_ids,practiceRevisionIds=[])
            raw=answer(case);rawSHA=store(directory,"raw-transport-response.json",raw);fixture.reply_override=raw
            wire_before=len(fixture.calls)
            receipt=request(client,"post","/lesson-plans/"+lesson["lessonPlanId"]+"/proposals",202,json=generate)
            job=ready(client,receipt);assert len(fixture.calls)==wire_before+1
            proposal_id=job["result"]["proposalId"]
            proposal=request(client,"get","/lesson-plans/"+lesson["lessonPlanId"]+"/proposals/"+proposal_id)
            with app.state.teaching.read_connection() as conn:
                frozen=json.loads(conn.execute("SELECT frozen_json FROM lesson_generation_inputs WHERE job_id=?",(job["jobId"],)).fetchone()[0])
            payload=frozen["modelPayload"]
            assert len(payload["classSummary"]["knowledgePoints"])==len(case["expectedTargetCounts"])
            for actual,wanted in zip(payload["classSummary"]["knowledgePoints"],case["expectedTargetCounts"]):
                assert actual["counts"]=={k:v for k,v in wanted.items() if k!="ratio"}
            wire=fixture.calls[-1]
            wire_text=json.dumps(wire,ensure_ascii=False)
            assert all(token not in wire_text for token in frozen["source"]["personalTokens"]),"Synthetic student identity escaped whitelist"
            assert frozen["contextSnapshot"]["analysis"]["className"] is None
            applied=request(client,"post","/lesson-plans/"+lesson["lessonPlanId"]+"/proposals/"+proposal_id+"/apply",json=dict(submissionId=case["caseId"]+"-apply",expectedRevision=lesson["revision"],baseRevisionId=lesson["currentRevisionId"],selectedFields=case["selectedFields"]))
            current=applied["currentRevision"];actual=current["data"]
            # Independent field-by-field preservation; never production merge oracle.
            for field in original:
                if field not in case["selectedFields"]:
                    assert actual[field]==original[field],(case["caseId"],"unselected/teacher field changed",field)
                else:
                    assert actual[field]==proposal["patch"][field],(case["caseId"],"selected whole field not applied",field)
            for field in ["coreCompetencies","keyPoints","teachingDesign","exercises"]:
                assert proposal["patch"][field]==raw["patch"][field]
            assert [x["minutes"] for x in proposal["budget"]["stages"]]==case["stageMinutes"]
            assert sum(x["minutes"] for x in proposal["budget"]["stages"])==case["durationMinutes"]
            assert current["reviewState"]=="unreviewed" and current["selectedFields"]==case["selectedFields"]
            fixed=request(client,"get","/lesson-plans/"+lesson["lessonPlanId"]+"/revisions/"+applied["currentRevisionId"])
            assert fixed==current
            assert request(client,"get","/score-revisions/"+facts["score"]["revisionId"])==facts["score"]
            assert request(client,"get","/analysis-runs/"+facts["report"]["runId"])==facts["report"]
            bound=dict(caseSpec=case,caseSpecPackSHA=pack_hash,ruleCode="any_loss_v1",runId=facts["report"]["runId"],scoreRevisionId=facts["score"]["revisionId"],paperRevisionId=facts["paperRevisionId"],selectedParticipantIds=facts["selectedParticipantIds"],classId=facts["selectedClassId"],knowledge=facts["selectedPoints"],scopeSnapshot=verified["scopeSnapshot"],evidenceRefs=verified["evidenceRefs"],materialCopyright="Self-authored owned synthetic B5/B6 rational-addition passage",questionRevisionIds=question_ids,practiceRevisionIds=[],sourceSnapshotHashes=dict(score=sha(canonical(facts["score"])),report=sha(canonical(facts["report"])),classes=sha(canonical(facts["classes"])),matrix=sha(canonical(facts["matrix"])),frozen=sha(canonical(frozen)),modelPayload=sha(canonical(payload))))
            files={"case.json":bound,"source-snapshots.json":facts,"input.json":generate,"input-frozen.json":frozen,"wire.json":wire,"original-lesson.json":original,"candidate.json":proposal,"selected-fields.json":case["selectedFields"],"applied-result.json":applied,"fixed-export-input.json":dict(data=actual,sourceLabel="后台固定修订 "+current["revisionId"],context=current["contextSnapshot"],revisionId=current["revisionId"],lessonPlanId=lesson["lessonPlanId"])}
            hashes={name:store(directory,name,value) for name,value in files.items()}
            result=dict(caseId=case["caseId"],expectedSHA=expectedSHA,caseHash=hashes["case.json"],hashes=hashes,rawSHA=rawSHA,modelFingerprint=proposal["modelFingerprint"],promptVersion="lesson_generation.SYSTEM_PROMPT@sha256:"+sha(SYSTEM_PROMPT.encode("utf8")),durationMs=round((time.perf_counter()-t0)*1000,3),usage=dict(inputTokens=None,outputTokens=None,reason="offline HTTP reply has no actual billable model usage"),failure=None,providerTransportCalls=1,technicalStructure="PASS",qualityVerdict="teacher_review_pending",liveStatus="live_run待输入",materialCase=case["materialCase"],requestedClaimSupported=case["requestedClaimSupported"],coverageGap=gap,shortcomings=["Transport reply is handwritten fixture, not real AI teaching-quality evidence","Human must judge facts interpretation, relevance, activities and feasibility","RAG-REL remains OPEN; selected-evidence structural verification is not search refusal quality"],docxStatus="pending_existing_exporter",humanScores=None)
            store(directory,"result.json",result);checks.append(result)
            print(json.dumps(dict(caseId=case["caseId"],technicalStructure="PASS",teacher_review_pending=True,durationMs=result["durationMs"]),ensure_ascii=False),flush=True)
        store(run,"SUMMARY.json",dict(task="B6-QUALITY-v1",pid=os.getpid(),durationMs=round((time.perf_counter()-started)*1000,3),caseCount=len(checks),technicalStructurePassed=len(checks),teacherReviewStatus="teacher_review_pending",liveStatus="live_run待输入",dataRoot=str(data_root),settingsCredentialsFile=None,tcpListenersStarted=0,providerHTTPTransportSubstitutedOnly=True,caseSpecsSHA=pack_hash,seedHelperSHA=sha(seed_path.read_bytes()),promptVersion="lesson_generation.SYSTEM_PROMPT@sha256:"+sha(SYSTEM_PROMPT.encode("utf8")),results=checks))
except BaseException as exc:
    store(run,"FIRST-FAILURE.json",dict(pid=os.getpid(),caseId=case.get("caseId") if "case" in globals() else None,errorType=type(exc).__name__,error=str(exc),durationMs=round((time.perf_counter()-started)*1000,3),completedCases=len(checks),dataRoot=str(data_root),retained=True))
    traceback.print_exc();raise
finally:
    if fixture is not None:fixture.restore()
