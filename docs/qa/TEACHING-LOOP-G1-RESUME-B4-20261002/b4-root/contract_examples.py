"""Documentation examples only. Validating DTO shape is not business acceptance."""
import os
import tempfile
import json
from pathlib import Path
os.environ.update(ZQKY_DATA_DIR=tempfile.mkdtemp(prefix='zqky-b4-contract-'), ZQKY_ENV='test', PYTHONUTF8='1')
from app.contracts import b4

now = '2026-10-02T00:00:00Z'
sha = '1'*64
job = dict(jobId='job-analysis',domain='teaching',kind='analysis',attempt=0,state='queued',result=None,error=None)
kp = dict(knowledgePointId='kp-1',knowledgeRevisionId='kpr-1',name='固定知识点名称',role='primary')
participant = dict(participantId='participant-1',studentId='student-1',studentNo='0001',name='甲',classId='class-1',className=None,classNameNote='该成绩未记录班名',attemptNo=1,attendance='present')
states = dict(recorded=1,missing=0,absent=0,exempt=0)
rich = dict(version=2, sharedMaterials=[], stemBlocks=[dict(id='stem-1',kind='paragraph',text='示例固定题干')], optionBlocks={}, answerBlocks=[],explanationBlocks=[],assets=[],origin=dict(originalAssetId='source-1',originalSha256=sha,sourceLocator={'paragraph':1}))
constraints = dict(count=1,questionTypes=[],difficulties=[],includeUnknownDifficulty=False,excludeOriginal=True,deduplicate=True)
draft = dict(itemKey='selection-1',questionRevisionId='question-revision-1',ordinal=1,itemStructure=dict(nodes=[dict(nodeKey='leaf-1',parentNodeKey=None,questionNo='1',ordinal=1,isScored=True,maxScore='2',knowledgePointIds=['kp-1'],sourceBlockIds=['stem-1'])]),maxScore='2',selectedKnowledgePointIds=['kp-1'])
item = dict(practiceItemId='practice-item-1',selectionId='selection-1',itemKey='selection-1',nodeKey='leaf-1',parentItemId=None,questionNo='1',ordinal=1,isScored=True,maxScoreUnits=200,questionId='question-1',questionRevisionId='question-revision-1',content=rich,knowledgePoints=[kp],sourceLocator={'sourceBlockIds':['stem-1']},reason='覆盖明确目标知识点',answerState='missing')
revision = dict(practiceSetId='practice-1',practiceRevisionId='practice-revision-1',version=1,state='reviewed',title='针对练习',subjectId='math',analysisRunId='run-1',targetKnowledgePoints=[kp],constraints=constraints,inputHash=sha,totalScoreUnits=200,draftItems=[draft],items=[item],reviewedAt=now,createdAt=now)
run = dict(runId='run-1',assessmentId='assessment-1',subjectId='math',scoreRevisionId='score-1',paperRevisionId='paper-revision-1',paperTitle='固定测评',inputHash=sha,ruleCode='any_loss_v1',selectionSnapshot=dict(selectedParticipantIds=['participant-1'],uniqueStudentCount=1,participantCount=1,leafCount=1,stateCounts=states),participants=[participant],knowledgePoints=[kp],job=job,reportReady=False,createdAt=now)
class_row = dict(classId='class-1',className=None,classNameNote='该成绩未记录班名',knowledgePoint=kp,selectedCount=1,validCount=1,needsCount=1,incompleteCount=0,noEvidenceCount=0,fullCreditCount=0,numerator=1,denominator=1,ratio=1.0)
student_row = dict(participant=participant,knowledgePoint=kp,observation='needs_consolidation',informationIncomplete=False,expectedCount=1,validCount=1,stateCounts=states,totalScoreUnits=100,totalMaxScoreUnits=200)
evidence = dict(evidenceId='evidence-1',runId='run-1',scoreRevisionId='score-1',paperRevisionId='paper-revision-1',participant=participant,itemId='paper-item-1',itemPath='1',maxScoreUnits=200,scoreUnits=100,status='recorded',knowledgePoints=[kp],content={'richContent':rich},sharedMaterials=[],sourceLocator={'paragraph':1},assets=[],practiceRevisionId=None,practiceItemId=None,associationNote='综合题失分关联，具体错因待教师确认')
note = dict(noteId='note-1',runId='run-1',participantId='participant-1',knowledgePointId='kp-1',note='教师追加观察',createdAt=now,replayed=False)
artifact = dict(artifactId='artifact-1',exportId='export-1',practiceRevisionId='practice-revision-1',variant='student',assessmentId=None,fileAssetId='file-export-1',filename='针对练习-学生版.docx',mediaType='application/vnd.openxmlformats-officedocument.wordprocessingml.document',sha256=sha,byteSize=2048,downloadUrl='/api/v1/export-artifacts/artifact-1/download',createdAt=now)
data = {}
def sample(name, model, value):
    data[name] = model.model_validate(value).model_dump(mode='json',by_alias=True)
def page(name, model, value):
    sample(name,b4.Page[model],dict(items=[value],total=1,offset=0,limit=50))

sample('analysis.create.request',b4.AnalysisCreateRequest,dict(submissionId='submission-1',scoreRevisionId='score-1',selectedParticipantIds=['participant-1'],ruleCode='any_loss_v1'))
sample('analysis.create.202',b4.AnalysisReceipt,dict(runId='run-1',inputHash=sha,scoreRevisionId='score-1',paperRevisionId='paper-revision-1',job=job,replayed=False,reused=False))
sample('analysis.get.200',b4.AnalysisRunView,run)
page('analysis.list.200',b4.AnalysisRunView,run)
page('analysis.classes.200',b4.ClassReportRow,class_row)
page('analysis.students.200',b4.StudentReportRow,student_row)
page('analysis.evidence.200',b4.EvidenceRow,evidence)
sample('analysis.note.request',b4.NoteRequest,dict(submissionId='submission-note',participantId='participant-1',knowledgePointId='kp-1',note='教师追加观察'))
sample('analysis.note.201',b4.NoteView,note)
page('analysis.notes.200',b4.NoteView,note)
sample('practice.create.request',b4.PracticeCreateRequest,dict(submissionId='submission-practice',analysisRunId='run-1',title='针对练习',targetKnowledgePointIds=['kp-1'],constraints=constraints))
practice = dict(practiceSetId='practice-1',title='针对练习',subjectId='math',analysisRunId='run-1',revision=2,currentRevision=revision,revisions=[revision],replayed=False)
sample('practice.get.create.patch.review.newDraft.response',b4.PracticeSetView,practice)
page('practice.list.200',b4.PracticeSetView,practice)
sample('practice.revision.200',b4.PracticeRevisionView,revision)
sample('practice.draft.patch.request',b4.PracticeDraftPatch,dict(expectedRevision=1,items=[draft],constraints=constraints))
sample('practice.suggestions.request',b4.PracticeSuggestionsRequest,dict(expectedRevision=1,constraints=constraints))
sample('practice.suggestions.200',b4.PracticeSuggestions,dict(items=[dict(questionId='question-1',questionRevisionId='question-revision-1',content=rich,knowledgePoints=[kp],questionType='short_answer',difficulty=None,reason='覆盖明确目标知识点',answerState='missing')],requestedCount=1,selectedCount=1,coverage={'kp-1':1},gaps=[]))
sample('practice.review.request',b4.PracticeReviewRequest,dict(submissionId='submission-review',expectedRevision=1))
sample('practice.newDraft.request',b4.PracticeRevisionRequest,dict(submissionId='submission-draft',sourceRevisionId='practice-revision-1'))
for variant in ('student','teacher','score_template'):
    sample('export.'+variant+'.request',b4.ExportRequest,dict(submissionId='submission-export-'+variant,variant=variant,assessmentId='assessment-new' if variant=='score_template' else None))
sample('export.202',b4.ExportReceipt,dict(exportId='export-1',practiceRevisionId='practice-revision-1',inputHash=sha,job={**job,'kind':'export','jobId':'job-export'},replayed=False,reused=False))
sample('artifact.get.200',b4.ExportArtifact,artifact)
page('exports.list.200',b4.ExportArtifact,artifact)
sample('conversion.request',b4.PracticeConversionRequest,dict(submissionId='submission-convert',title='练习施测',heldOn='2026-10-02',classIds=['class-1'],participants=[dict(studentId='student-1',classId='class-1',attendance='present',attemptNo=1,classConfirmed=False,classConfirmationNote=None)]))
sample('conversion.201',b4.PracticeConversionReceipt,dict(conversionId='conversion-1',paperId='paper-new',paperRevisionId='paper-revision-new',assessmentId='assessment-new',practiceRevisionId='practice-revision-1',replayed=False))
data['errors'] = {
 '409':dict(code='REVISION_CONFLICT',message='草稿已更新，请核对后重试。',requestId='request-example',retryable=False,details=dict(currentRevision=3,fields=['expectedRevision'])),
 '422':dict(code='ANALYSIS_SELECTION_INVALID',message='同学生只能选择一个人次。',requestId='request-example',retryable=False,details=dict(issues=[dict(field='selectedParticipantIds[1]',row=1,code='DUPLICATE_STUDENT_ATTEMPT',message='同学生只能选择一个人次。')])),
 '409_not_ready':dict(code='REPORT_NOT_READY',message='报告尚未就绪。',requestId='request-example',retryable=False,details=dict(fields=['runId'])),
 '404':dict(code='EXPORT_ARTIFACT_NOT_FOUND',message='导出产物不存在。',requestId='request-example',retryable=False,details=None),
 '500':dict(code='ANALYSIS_SOURCE_CORRUPT',message='固定来源损坏，读取已停止。',requestId='request-example',retryable=False,details=None),
 '503':dict(code='SERVICE_UNAVAILABLE',message='学情服务未装配。',requestId='request-example',retryable=True,details=None),
}
path = Path('docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/contract-examples.json')
path.write_text(json.dumps(dict(documentationSamples=True,businessAcceptance=False,examples=data),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('validated',len(data)-1,'complete DTO documentation samples; not business tests')
