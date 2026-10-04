"""Static B5 wire contract: no app.main, routes, model calls or formal data."""
from pathlib import Path
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SAMPLE = Path(tempfile.mkdtemp(prefix="zqky-b5-contract-"))
(SAMPLE / "empty-textbooks").mkdir()
os.environ.update(ZQKY_DATA_DIR=str(SAMPLE / "data"), ZQKY_ENV="test", PYTHONUTF8="1",
    ZQKY_QDRANT_URL="http://127.0.0.1:16333", ZQKY_EMBEDDING_BASE_URL="http://127.0.0.1:9",
    ZQKY_TEXTBOOK_SOURCE_DIR=str(SAMPLE / "empty-textbooks"))
sys.path.insert(0, str(ROOT / "apps/api"))
from pydantic import ValidationError
from app.contracts import lesson_plans as dto
from app.contracts.b4 import Page
from app.contracts.teaching_loop import ApiErrorEnvelope
from app.core.migrations.teaching import MIGRATIONS
from app.core.migrations.lesson_plans import MIGRATION

targets = [OUT / "B5-OLD-MIGRATIONS-v1.json", OUT / "B5-WIRE-EXAMPLES-v1.json",
           OUT.parent / "B5-OPENAPI-v1.json", OUT / "B5-CONTRACT-PROBE-v1.json"]
if any(p.exists() for p in targets):
    raise FileExistsError("new immutable output label required")
assert len(MIGRATIONS) == 9, "capture the nine original declarations before registering 0010"
old = [{"id": m.id, "sha256": m.sha256, "description": m.description,
        "statements": list(m.statements), "rebuild": m.rebuild.fingerprint_text() if m.rebuild else None}
       for m in MIGRATIONS]
data = dict(title="一次函数复习", totalLessons="1", currentLessonNo="1", lessonTypes=["review"],
    otherTypeText="", coreCompetencies="用函数解释变量关系", keyPoints="一次函数斜率", teachingDesign="先观察再验证",
    process=[dict(id="teacher-stage-1", stage="复习", design="比较两条直线", secondary="保留教师批注")],
    exercises="解释 y=2x+1 的意义", reflection="教师课后填写")
draft = dict(schemaVersion=1, revision=7, updatedAt="2026-10-03T12:00:00+08:00", data=data)
point = dict(knowledgePointId="kp-demo", knowledgeRevisionId="kr-demo", name="一次函数", role="primary")
analysis = dict(analysisRunId="run-demo", inputHash="1"*64, scoreRevisionId="score-demo", paperRevisionId="paper-demo",
    className=None, classNameNote="当时未记录", knowledgePoints=[point])
context = dict(analysisRunId="run-demo", selectedKnowledgePointIds=["kp-demo"])
snapshot = dict(subjectId="math", classId="class-demo", classNameAtSave="示例班", analysis=analysis)
revision = dict(protocolVersion=2, lessonPlanId="lesson-demo", revisionId="revision-demo", version=1,
    data=data, contentHash="2"*64, source="manual", contextSnapshot=snapshot, analysisRunId="run-demo",
    acceptedProposalId=None, importEnvelope=None, selectedFields=[], processMetadata=[], reviewState="unreviewed",
    createdAt="2026-10-03T04:00:00Z")
view = dict(protocolVersion=2, lessonPlanId="lesson-demo", subjectId="math", classId="class-demo", revision=1,
    currentRevisionId="revision-demo", currentRevision=revision, replayed=False)
summary = {k:view[k] for k in ("lessonPlanId","subjectId","classId","revision","currentRevisionId")}
summary.update(title=data["title"], source="manual", analysisRunId="run-demo", updatedAt=revision["createdAt"])
rs = {k:revision[k] for k in ("lessonPlanId","revisionId","version","contentHash","source","analysisRunId",
                              "acceptedProposalId","selectedFields","reviewState","createdAt")}
rs["title"] = data["title"]
selection = dict(gradeId="grade-8", subjectId="math", editionId="edition-demo", documentIds=["textbook-demo"])
scope = dict(schemaVersion=2, selection=selection, documents=[dict(documentId="textbook-demo",
    documentRevisionId="textbook-revision-demo", metadataRevisionId="metadata-demo")], embeddingGenerationId="embedding-demo", scopeHash="3"*64)
ref = dict(evidenceId="evidence-demo", documentRevisionId="textbook-revision-demo", normalizedTextSha256="4"*64, charStart=0, charEnd=8)
evidence = dict(ref, documentId="textbook-demo", title="示例教材", editionLabel="示例版本", subjectLabel="数学",
    chapterPath=["一次函数"], text="一次函数示例原文", originalFileSha256="5"*64,
    locator=dict(kind="markdown", lineStart=1, lineEnd=2), isSuperseded=False, readable=None)
ev = dict(scopeSnapshot=scope, evidenceRefs=[ref], evidence=[evidence])
generate = dict(submissionId="generate-demo", baseRevisionId="revision-demo", baseServerRevision=1,
    analysisRunId="run-demo", classId="class-demo", selectedKnowledgePointIds=["kp-demo"], requirements="增加比较与解释活动",
    durationMinutes=40, modelProfileId="profile-demo", scopeSnapshot=scope, evidenceRefs=[ref],
    questionRevisionIds=[], practiceRevisionIds=[])
job = dict(jobId="job-demo", domain="teaching", kind="lesson_generation", attempt=0, state="queued", result=None, error=None)
receipt = dict(lessonPlanId="lesson-demo", inputHash="6"*64, job=job, replayed=False)
phases = ["introduction", "exploration", "practice", "conclusion"]
process = [dict(id=f"stable-{i}", stage=label, design="观察、讨论并说明依据", secondary="")
           for i,label in enumerate(["导入","探究","练习","总结"],1)]
stages = [dict(processId=item["id"], phase=phases[i], minutes=10, knowledgeAliases=["K1"],
    activity="比较并解释", check="写出关系与理由", evidenceAliases=["E1"]) for i,item in enumerate(process)]
proposal = dict(protocolVersion=2, lessonPlanId="lesson-demo", proposalId="proposal-demo", jobId="job-demo",
    baseRevisionId="revision-demo", baseServerRevision=1, inputHash="6"*64, modelFingerprint="7"*64, state="pending",
    patch=dict(coreCompetencies=None, keyPoints="比较函数关系", teachingDesign=None, process=process, exercises=None),
    budget=dict(durationMinutes=40, stages=stages), evidence=[dict(alias="E1",kind="textbook",referenceId="evidence-demo",
      title="示例教材",sha256="4"*64,locator=dict(charStart=0,charEnd=8),text="一次函数示例原文")],
    generationSource=dict(analysis=analysis,classId="class-demo",selectedKnowledgePoints=[point],modelProfileId="profile-demo",
      scopeSnapshot=scope,evidenceRefs=[ref],requirements=generate["requirements"]),
    selectedFields=[],acceptedRevisionId=None,createdAt="2026-10-03T04:01:00Z",decidedAt=None,replayed=False)
applied = copy.deepcopy(view)
applied.update(revision=2,currentRevisionId="revision-applied-demo")
applied["currentRevision"].update(revisionId="revision-applied-demo",version=2,source="ai_applied",
    acceptedProposalId="proposal-demo",selectedFields=["process"],processMetadata=stages,contentHash="8"*64)
applied["currentRevision"]["data"]["process"] = process
rejected = dict(proposal,state="rejected",decidedAt="2026-10-03T04:02:00Z")
endpoints = [
 ("get","/lesson-plans",None,Page[dto.LessonSummary],200,None,dict(items=[summary],total=1,offset=0,limit=50)),
 ("post","/lesson-plans",dto.LessonCreateRequest,dto.LessonView,201,dict(submissionId="create-demo",subjectId="math",classId="class-demo",data=data,context=context,source="manual"),view),
 ("post","/lesson-plans/import-local",dto.LessonImportRequest,dto.LessonView,201,dict(submissionId="import-demo",subjectId="math",classId="class-demo",draft=draft,context=context),dict(view,currentRevision=dict(revision,source="import_local",importEnvelope=draft))),
 ("get","/lesson-plans/{id}",None,dto.LessonView,200,None,view),
 ("patch","/lesson-plans/{id}/draft",dto.LessonSaveRequest,dto.LessonView,200,dict(submissionId="save-demo",expectedRevision=1,data=data,context=context,source="rule"),view),
 ("get","/lesson-plans/{id}/revisions",None,Page[dto.LessonRevisionSummary],200,None,dict(items=[rs],total=1,offset=0,limit=50)),
 ("get","/lesson-plans/{id}/revisions/{revisionId}",None,dto.LessonRevisionView,200,None,revision),
 ("post","/lesson-plans/evidence/verify",dto.LessonEvidenceRequest,dto.LessonEvidenceView,200,dict(selection=selection,slices=[dict(documentRevisionId="textbook-revision-demo",charStart=0,charEnd=8)]),ev),
 ("post","/lesson-plans/{id}/proposals",dto.LessonGenerateRequest,dto.LessonGenerationReceipt,202,generate,receipt),
 ("get","/lesson-plans/{id}/proposals/{proposalId}",None,dto.LessonProposalView,200,None,proposal),
 ("post","/lesson-plans/{id}/proposals/{proposalId}/apply",dto.LessonApplyRequest,dto.LessonView,200,dict(submissionId="apply-demo",expectedRevision=1,baseRevisionId="revision-demo",selectedFields=["process"]),applied),
 ("post","/lesson-plans/{id}/proposals/{proposalId}/reject",dto.LessonRejectRequest,dto.LessonProposalView,200,dict(submissionId="reject-demo"),rejected),
]
errors = {
 "404":dict(code="NOT_FOUND",message="所选资源不可用",requestId="request-demo",retryable=False),
 "409":dict(code="REVISION_CONFLICT",message="后台教案已有新版本",requestId="request-demo",retryable=False,details=dict(currentRevision=2,fields=["expectedRevision"])),
 "413":dict(code="LESSON_REQUEST_TOO_LARGE",message="请求超过2 MiB，请保留原稿",requestId="request-demo",retryable=False),
 "422":dict(code="LESSON_PROPOSAL_INVALID",message="候选分钟合计不等于课时",requestId="request-demo",retryable=False,details=dict(issues=[dict(field="budget.stages",code="DURATION_MISMATCH",message="请核对课时预算")])),
 "503":dict(code="SERVICE_UNAVAILABLE",message="教案服务未装配",requestId="request-demo",retryable=True),
}
for sample in errors.values(): ApiErrorEnvelope.model_validate(sample)
components = {}
def schema(model):
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", model.__name__)
    raw = model.model_json_schema(by_alias=True)
    defs = raw.pop("$defs",{})
    def rewrite(value):
        if isinstance(value,dict): return {k:rewrite(v) for k,v in value.items()}
        if isinstance(value,list): return [rewrite(v) for v in value]
        if isinstance(value,str): return value.replace("#/$defs/","#/components/schemas/")
        return value
    for key,value in defs.items():
        converted = rewrite(value)
        if key in components: assert components[key] == converted, key
        components[key] = converted
    components[name] = rewrite(raw)
    return {"$ref":"#/components/schemas/"+name}
error_schema = schema(ApiErrorEnvelope)
paths, examples = {}, []
validated = 0
for method,path,req,resp,status,request,response in endpoints:
    response = resp.model_validate(response).model_dump(by_alias=True, mode="json")
    validated += 1
    if req:
        request = req.model_validate(request).model_dump(by_alias=True,mode="json")
        validated += 1
    operation = dict(operationId="lesson_"+method+"_"+re.sub(r"[^a-zA-Z0-9]","_",path).strip("_"),
        summary="B5 static contract; implementation pending",responses={str(status):dict(description="Accepted job" if status==202 else "Success",content={"application/json":dict(schema=schema(resp),example=response)})})
    operation["responses"].update({code:dict(description=value["code"],content={"application/json":dict(schema=error_schema,example=value)}) for code,value in errors.items()})
    params = [dict(name=name,**{"in":"path"},required=True,schema=dict(type="string",minLength=1)) for name in re.findall(r"\{(.*?)\}",path)]
    if method=="get" and path.endswith(("/lesson-plans","/revisions")):
        params.extend([dict(name="offset",**{"in":"query"},schema=dict(type="integer",minimum=0,default=0)),dict(name="limit",**{"in":"query"},schema=dict(type="integer",minimum=1,maximum=200,default=50))])
        if path=="/lesson-plans": params.extend([dict(name=name,**{"in":"query"},schema=dict(type="string")) for name in ("subjectId","classId")])
    if params: operation["parameters"]=params
    if req: operation["requestBody"]=dict(required=True,content={"application/json":dict(schema=schema(req),example=request)})
    paths.setdefault("/api/v1"+path,{})[method]=operation
    examples.append(dict(method=method.upper(),path="/api/v1"+path,status=status,request=request,response=response,errors=errors))
negative = [
 (dto.DraftEnvelope,dict(draft,schemaVersion=True)),
 (dto.DraftEnvelope,dict(draft,revision=True)),
 (dto.DraftEnvelope,dict(draft,updatedAt="2026-10-03T04:00:00")),
 (dto.LessonCreateRequest,dict(endpoints[1][5],ownerId="other")),
 (dto.LessonSaveRequest,dict(endpoints[4][5],expectedRevision=True)),
 (dto.LessonApplyRequest,dict(endpoints[10][5],selectedFields=["process","process"])),
 (dto.LessonApplyRequest,dict(endpoints[10][5],selectedFields=["reflection"])),
 (dto.LessonGenerateRequest,dict(generate,durationMinutes=True)),
 (dto.LessonGenerateRequest,dict(generate,evidenceRefs=[dict(ref,charStart=True)])),
 (dto.LessonGenerateRequest,dict(generate,selectedKnowledgePointIds=["kp-demo","kp-demo"])),
 (dto.LessonPlanData,dict(data,title="😀"*41)),
 (dto.LessonPlanData,dict(data,process=data["process"]*2)),
]
for model,sample in negative:
    try: model.model_validate(sample)
    except ValidationError: pass
    else: raise AssertionError(f"Expected strict rejection: {model.__name__}")
openapi = dict(openapi="3.1.0",info=dict(title="B5 lesson plans static wire contract",version="1.0.0",description="Schemas and fabricated examples, not an implemented API or acceptance result."),paths=paths,components=dict(schemas=components))
values = [dict(capturedAt=datetime.now(timezone.utc).isoformat(),migrations=old,newMigration=dict(id=MIGRATION.id,sha256=MIGRATION.sha256)),dict(staticExamples=True,endpoints=examples),openapi,
    dict(status="STATIC_CONTRACT_VALIDATED",sampleRoot=str(SAMPLE),sampleRetained=True,appMainImported=False,positiveDTOs=validated,errorDTOs=len(errors),negativeDTOs=len(negative),endpoints=len(endpoints),oldMigrations=len(old),newMigrationSHA=MIGRATION.sha256)]
for path,value in zip(targets,values):
    with path.open("x",encoding="utf-8",newline="\n") as stream: stream.write(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(values[-1],ensure_ascii=False))
