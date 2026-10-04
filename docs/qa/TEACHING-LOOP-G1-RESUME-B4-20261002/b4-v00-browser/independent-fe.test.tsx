// Independent literal display/async-contract probes. All service doubles below
// are component evidence ONLY. They never count as real API/four-DB/browser pass.
import React,{StrictMode} from 'react';
import '@testing-library/jest-dom/vitest';
import {render,screen,fireEvent,act,waitFor,cleanup} from '@testing-library/react';
import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {PracticeEditor} from '@/features/practices/PracticeEditor';
import {PracticeExports} from '@/features/practices/PracticeExports';
import {PracticeConversion} from '@/features/practices/PracticeConversion';
import {CreatePracticeForm} from '@/features/practices/CreatePracticeForm';
import {LearningAnalysisWorkspace} from '@/features/learning-analysis/LearningAnalysisWorkspace';
import {b4Api} from '@/services/teaching-loop-b4-api';
import {ApiError} from '@/services/api-client';
import type {PracticeSetView,PracticeSuggestions,AnalysisRunView,ExportArtifact} from '@/contracts/b4';
import type {JobView,RichContentV2} from '@/contracts/teaching-loop';
import * as assessments from '@/services/assessments-api';

vi.mock('next/link',()=>({default:({href,children,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>)=><a href={href} {...props}>{children}</a>}));
vi.mock('@/services/assessments-api',()=>({listClasses:vi.fn(),listClassStudents:vi.fn(),listAssessments:vi.fn(),listScoreRevisions:vi.fn(),getScoreRevision:vi.fn(),getAssessment:vi.fn(),getPaperAsset:vi.fn()}));
vi.mock('@/services/workflow-jobs-api',()=>({observeJob:vi.fn(),retryObservationWindow:(view:JobView)=>({minAttempt:view.attempt,maxAttempt:view.attempt+1}),retryJob:vi.fn(),cancelJob:vi.fn()}));

const point={knowledgePointId:'literal-k',knowledgeRevisionId:'literal-kr',name:'固定知识点',role:'primary' as const};
const rich:RichContentV2={version:2,stemBlocks:[{id:'stem',kind:'paragraph',text:'独立完整题面'},{id:'formula',kind:'formula',latex:'x+1'},{id:'table',kind:'table',columnCount:1,cells:[{text:'单元格',isHeader:false,rowSpan:1,colSpan:1}]}],sharedMaterials:[{id:'m',blocks:[{id:'mb',kind:'paragraph',text:'共同材料'}]}],optionBlocks:{A:[{id:'option-a',kind:'paragraph',text:'选项甲'}]},answerBlocks:[{id:'answer',kind:'paragraph',text:'独立答案'}],explanationBlocks:[{id:'explain',kind:'paragraph',text:'独立解析'}],assets:[],origin:{originalAssetId:'test-source',originalSha256:'ab'.repeat(32),sourceLocator:{paragraphIndex:1}}};
function view(id='set-a',revision=0):PracticeSetView{
  const draft={itemKey:'item',questionRevisionId:'literal-qr',ordinal:1,maxScore:'1.25',selectedKnowledgePointIds:['literal-k'],itemStructure:{nodes:[{nodeKey:'leaf',parentNodeKey:null,questionNo:'16(1)',ordinal:1,isScored:true,maxScore:'1.25',knowledgePointIds:['literal-k'],sourceBlockIds:['stem','formula','table','option-a']}]}};
  const fixed={practiceSetId:id,practiceRevisionId:id+'-r1',version:1,state:'draft' as const,title:'独立练习',subjectId:'math',analysisRunId:'run-a',targetKnowledgePoints:[point],constraints:{count:1},inputHash:'cd'.repeat(32),totalScoreUnits:125,draftItems:[draft],items:[{practiceItemId:'pi',selectionId:'sel',itemKey:'item',nodeKey:'leaf',parentItemId:null,questionNo:'16(1)',ordinal:1,isScored:true,maxScoreUnits:125,questionId:'literal-q',questionRevisionId:'literal-qr',content:rich,knowledgePoints:[point],sourceLocator:{},reason:'正式题',answerState:'provided'}],reviewedAt:null,createdAt:'2026-10-02T00:00:00Z'};
  return {practiceSetId:id,title:'独立练习',subjectId:'math',analysisRunId:'run-a',revision,currentRevision:fixed,revisions:[fixed],replayed:false};
}
function run(id='run-a',ready=true):AnalysisRunView{return {runId:id,assessmentId:'assessment-a',subjectId:'math',scoreRevisionId:'score-a',paperRevisionId:'paper-a',paperTitle:'固定原卷',inputHash:'ef'.repeat(32),ruleCode:'any_loss_v1',selectionSnapshot:{selectedParticipantIds:[],uniqueStudentCount:1,participantCount:1,leafCount:1,stateCounts:{recorded:1,missing:0,absent:0,exempt:0}},participants:[],knowledgePoints:[point],job:{jobId:'analysis-job',domain:'teaching',kind:'analysis',attempt:ready?1:0,state:ready?'succeeded':'queued',result:null,error:null},reportReady:ready,createdAt:'2026-10-02T00:00:00Z'};}
function deferred<T>(){let resolve!:(v:T)=>void,reject!:(reason:unknown)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
// Testing Library's string accessible-name matcher is already exact. Its role
// API has no Playwright-style `exact` option; label-text exact stays explicit.
const button=(name:string)=>screen.getByRole('button',{name});
const field=(name:string)=>screen.getByLabelText(name,{exact:true});
function edit(name:string,value:string){fireEvent.change(field(name),{target:{value}});}
function services(overrides:Partial<typeof b4Api>={}){return {...b4Api,...overrides};}
function editor(api:typeof b4Api,current=view(),saved=vi.fn(),strict=false){const ui=<PracticeEditor view={current} services={api} onSaved={saved} onLocked={vi.fn()}/>;return {...render(strict?<StrictMode>{ui}</StrictMode>:ui),saved};}
const suggestions:PracticeSuggestions={requestedCount:2,selectedCount:1,coverage:{'literal-k':1},gaps:['独立事实：请求2题，只有1题'],items:[{questionId:'literal-q2',questionRevisionId:'literal-qr2',content:rich,knowledgePoints:[point],questionType:'short_answer',difficulty:'easy',reason:'正式固定来源',answerState:'provided'}]};

beforeEach(()=>{vi.clearAllMocks();vi.mocked(assessments.listClasses).mockResolvedValue({items:[],total:0,offset:0,limit:50});});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

describe('independent FE async and frozen identity',()=>{
  it('late successful save retains later edit and next CAS uses returned revision; StrictMode',async()=>{
    const wait=deferred<PracticeSetView>();const patch=vi.fn().mockImplementationOnce(()=>wait.promise).mockResolvedValueOnce(view('set-a',2));const saved=vi.fn();editor(services({patchPracticeDraft:patch}),view(),saved,true);
    edit('第1题整题满分','2');fireEvent.click(button('保存草稿'));expect(patch).toHaveBeenCalledTimes(1);expect(patch.mock.calls[0][1].items[0].maxScore).toBe('2');
    edit('第1题整题满分','2.50');edit('第1题节点1满分','2.50');expect(button('独立审核此草稿')).toBeDisabled();
    await act(async()=>wait.resolve(view('set-a',1)));expect(field('第1题整题满分')).toHaveValue('2.50');expect(screen.getByText(/之后的编辑仍保留/)).toBeVisible();
    fireEvent.click(button('保存草稿'));await waitFor(()=>expect(patch).toHaveBeenCalledTimes(2));expect(patch.mock.calls[1][1]).toMatchObject({expectedRevision:1,items:[{maxScore:'2.50',itemStructure:{nodes:[{questionNo:'16(1)',maxScore:'2.50'}]}}]});
  });
  it.each([409,422])('explicit %s retains local draft and issue details instead of empty replacement',async status=>{
    const patch=vi.fn().mockRejectedValue(new ApiError(status===409?'REVISION_CONFLICT':'INVALID_REQUEST','独立拒绝事实',status,false,undefined,{currentRevision:3,issues:[{field:'items',code:'DUPLICATE_QUESTION_NO',message:'题号重复'}]}));editor(services({patchPracticeDraft:patch}));edit('第1题节点1题号','自定义16(1)');fireEvent.click(button('保存草稿'));
    await screen.findByText('独立拒绝事实',{exact:false});expect(field('第1题节点1题号')).toHaveValue('自定义16(1)');expect(button('保存草稿')).toBeEnabled();expect(button('独立审核此草稿')).toBeDisabled();expect(screen.getByText(/题号重复/)).toBeVisible();
  });
  it('remote revision refresh retains dirty input until explicit CAS adoption',()=>{
    const api=services();const saved=vi.fn();const locked=vi.fn();const current=view();const rendered=render(<PracticeEditor view={current} services={api} onSaved={saved} onLocked={locked}/>);edit('第1题整题满分','3.75');
    rendered.rerender(<PracticeEditor view={view('set-a',4)} services={api} onSaved={saved} onLocked={locked}/>);expect(field('第1题整题满分')).toHaveValue('3.75');expect(button('独立审核此草稿')).toBeDisabled();fireEvent.click(button('保留输入并采用最新版本'));expect(field('第1题整题满分')).toHaveValue('3.75');expect(screen.getByText(/已采用最新CAS版本/)).toBeVisible();
  });
  it('old suggestion after constraint edit is discarded, and count gap never silently adds items',async()=>{
    const wait=deferred<PracticeSuggestions>();const suggest=vi.fn().mockReturnValue(wait.promise);editor(services({suggestPractice:suggest}));fireEvent.click(button('获取正式题建议'));edit('练习题量','2');await act(async()=>wait.resolve(suggestions));expect(screen.getByText(/旧请求的建议未采用/)).toBeVisible();expect(screen.queryByText(/正式题 literal-q2/)).not.toBeInTheDocument();expect(screen.getAllByRole('article')).toHaveLength(1);
  });
  it.each(['success','error'])('unmount rejects late save %s without callback or leaking into next set',async outcome=>{
    const wait=deferred<PracticeSetView>();const saved=vi.fn();const mounted=editor(services({patchPracticeDraft:vi.fn().mockReturnValue(wait.promise)}),view(),saved,true);fireEvent.click(button('保存草稿'));mounted.unmount();editor(services(),view('set-b'));
    await act(async()=>{if(outcome==='success')wait.resolve(view('set-a',1));else wait.reject(new ApiError('OLD_ERROR','old failure',422,false));});expect(saved).not.toHaveBeenCalled();expect(screen.queryByText('old failure')).not.toBeInTheDocument();expect(field('第1题整题满分')).toHaveValue('1.25');
  });
  it('review unknown freezes original CAS and submission ID across retry',async()=>{
    const reviewed=view('set-a',1);reviewed.currentRevision.state='reviewed';const review=vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST','真实提交可能已完成',0,true)).mockResolvedValueOnce(reviewed);const saved=vi.fn();editor(services({reviewPractice:review}),view(),saved,true);
    fireEvent.click(button('独立审核此草稿'));await screen.findByText(/确认结果未知/);expect(field('第1题节点1题号')).toBeDisabled();expect(button('保存草稿')).toBeDisabled();fireEvent.click(button('重试原审核提交'));await waitFor(()=>expect(saved).toHaveBeenCalledWith(reviewed));expect(review.mock.calls[1]).toEqual(review.mock.calls[0]);expect(review.mock.calls[0][1].expectedRevision).toBe(0);expect(review.mock.calls[0][1].submissionId).toMatch(/^[0-9a-f-]{36}$/);
  });
  it('non-ready report cannot create practice; unknown create freezes title/target/run and unlocks only on result',async()=>{
    const created=view();const create=vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST','未知',0,true)).mockResolvedValueOnce(created);const api=services({createPractice:create});const onCreated=vi.fn();const ui=render(<CreatePracticeForm run={run('run-a',false)} services={api} onCreated={onCreated}/>);expect(button('创建针对练习')).toBeDisabled();expect(field('练习标题')).toBeDisabled();ui.rerender(<CreatePracticeForm run={run()} services={api} onCreated={onCreated}/>);
    edit('练习标题','固定标题');fireEvent.click(field('练习目标 固定知识点'));fireEvent.click(button('创建针对练习'));await screen.findByText(/确认结果未知/);expect(field('练习标题')).toBeDisabled();fireEvent.click(button('重试原创建练习提交'));await waitFor(()=>expect(onCreated).toHaveBeenCalledWith(created));expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);expect(create.mock.calls[0][0]).toMatchObject({analysisRunId:'run-a',title:'固定标题',targetKnowledgePointIds:['literal-k']});
  });
  it('analysis fixed source starts with no selection and same-student attempt selection is explicit',async()=>{
    const participants=[{participantId:'a1',studentId:'a',name:'合成甲',attemptNo:1,attendance:'present',classId:'class',studentNo:'00001'},{participantId:'a2',studentId:'a',name:'合成甲',attemptNo:2,attendance:'present',classId:'class',studentNo:'00001'},{participantId:'b1',studentId:'b',name:'合成乙',attemptNo:1,attendance:'present',classId:'class',studentNo:'00002'}];
    vi.mocked(assessments.listAssessments).mockResolvedValue({items:[],total:0,offset:0,limit:50});vi.mocked(assessments.listScoreRevisions).mockResolvedValue({items:[],total:0});vi.mocked(assessments.getScoreRevision).mockResolvedValue({revisionId:'score-a',assessmentId:'assessment-a',paperRevisionId:'paper-a',state:'confirmed',version:1,participantSnapshot:participants,itemSnapshot:[],sourceImportId:null,baseRevisionId:null,reason:null,createdAt:'2026-10-02T00:00:00Z',confirmedAt:'2026-10-02T00:00:00Z'} as Awaited<ReturnType<typeof assessments.getScoreRevision>>);
    const create=vi.fn().mockRejectedValue(new ApiError('KNOWN','定向停止前置',422,false));const api=services({listAnalysisRuns:vi.fn().mockResolvedValue({items:[],total:0,offset:0,limit:20}),createAnalysisRun:create});render(<StrictMode><LearningAnalysisWorkspace initialAssessmentId="assessment-a" initialScoreRevisionId="score-a" services={api}/></StrictMode>);
    await screen.findByLabelText('分析人次 合成甲 1');expect(button('创建本次报告')).toBeDisabled();fireEvent.click(field('分析人次 合成甲 1'));fireEvent.click(field('分析人次 合成甲 2'));expect(field('分析人次 合成甲 1')).not.toBeChecked();expect(field('分析人次 合成甲 2')).toBeChecked();fireEvent.click(field('分析人次 合成乙 1'));fireEvent.click(button('创建本次报告'));await waitFor(()=>expect(create).toHaveBeenCalledTimes(1));expect(create.mock.calls[0][1]).toMatchObject({scoreRevisionId:'score-a',selectedParticipantIds:['a2','b1'],ruleCode:'any_loss_v1'});
  });
  it('conversion unknown freezes dates, full participants and fixed revision',async()=>{
    // Named fixtures keep original ancillary updatedAt while supplying every
    // ClassView/StudentView field; no unsafe assertion erases DTO requirements.
    const klass={id:'class',code:'c',name:'合成班',schoolYear:'2026',gradeId:'g',status:'active' as const,revision:0,studentCount:1,createdAt:'now',updatedAt:'now'};
    const student={id:'student',name:'合成甲',studentNo:'00001',status:'active' as const,revision:0,memberships:[{membershipId:'membership',classId:'class',className:'合成班',joinedOn:'2026-01-01',leftOn:null}],createdAt:'now',updatedAt:'now'};
    vi.mocked(assessments.listClasses).mockResolvedValue({items:[klass],total:1,offset:0,limit:50});
    vi.mocked(assessments.listClassStudents).mockResolvedValue({items:[student],total:1,offset:0,limit:50});
    const receipt={conversionId:'cv',paperId:'paper',paperRevisionId:'paper-r',assessmentId:'assessment',practiceRevisionId:'set-a-r1',replayed:true};const convert=vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST','未知',0,true)).mockResolvedValueOnce(receipt);const onConverted=vi.fn();render(<PracticeConversion revision={view().currentRevision} services={services({convertPractice:convert})} onConverted={onConverted} onLocked={vi.fn()}/>);
    await waitFor(()=>expect(field('练习施测班级').querySelectorAll('option')).toHaveLength(2));edit('练习施测班级','class');await screen.findByLabelText('练习参测 合成甲');fireEvent.click(field('练习参测 合成甲'));edit('练习施测日期','2026-10-02');edit('合成甲 练习人次','3');edit('合成甲 练习出勤','exempt');fireEvent.click(button('转换固定练习为施测'));await screen.findByText(/确认结果未知/);expect(field('练习施测日期')).toBeDisabled();fireEvent.click(button('重试原转换提交'));await waitFor(()=>expect(onConverted).toHaveBeenCalledWith(receipt));expect(convert.mock.calls[1]).toEqual(convert.mock.calls[0]);expect(convert.mock.calls[0].slice(0,2)).toEqual(['set-a','set-a-r1']);expect(convert.mock.calls[0][2].participants[0]).toMatchObject({studentId:'student',classId:'class',attemptNo:3,attendance:'exempt'});
  });
  it.each(['late-edit','unknown'])('teacher note %s preserves independent new input or original retry packet',async mode=>{
    const ready=run();const wait=deferred<{noteId:string;runId:string;participantId:null;knowledgePointId:null;note:string;createdAt:string;replayed:boolean}>();
    const written={noteId:'note',runId:'run-a',participantId:null,knowledgePointId:null,note:'首次教师备注',createdAt:'now',replayed:false};
    const append=mode==='late-edit'?vi.fn().mockReturnValue(wait.promise):vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST','未知备注',0,true)).mockResolvedValueOnce({...written,replayed:true});
    vi.mocked(assessments.listAssessments).mockResolvedValue({items:[],total:0,offset:0,limit:50});vi.mocked(assessments.getAssessment).mockResolvedValue({assessment:{assessmentId:'assessment-a',paperRevisionId:'paper-a',paperId:'paper',paperTitle:'固定原卷',subjectId:'math',title:'独立施测',assessmentType:'exam',heldOn:'2026-10-02',activeScoreRevisionId:'score-a',state:'open',revision:0,classIds:['class'],participantCount:0,createdAt:'2026-10-02T00:00:00Z'},participants:[]});
    const page=()=>Promise.resolve({items:[],total:0,offset:0,limit:50});
    const api=services({listAnalysisRuns:vi.fn().mockImplementation(page),getAnalysisRun:vi.fn().mockResolvedValue(ready),listAnalysisClasses:vi.fn().mockImplementation(page),listAnalysisStudents:vi.fn().mockImplementation(page),listAnalysisEvidence:vi.fn().mockImplementation(page),listAnalysisNotes:vi.fn().mockImplementation(page),createAnalysisNote:append});
    render(<StrictMode><LearningAnalysisWorkspace initialRunId="run-a" services={api}/></StrictMode>);await screen.findByRole('tab',{name:'教师备注'});fireEvent.click(screen.getByRole('tab',{name:'教师备注'}));await screen.findByLabelText('教师备注内容');edit('教师备注内容','首次教师备注');fireEvent.click(button('追加教师备注'));
    if(mode==='late-edit'){
      expect(field('教师备注内容')).toBeEnabled();edit('教师备注内容','之后的新教师输入');await act(async()=>wait.resolve(written));expect(field('教师备注内容')).toHaveValue('之后的新教师输入');expect(append.mock.calls[0][1].note).toBe('首次教师备注');
    }else{
      await screen.findByText(/确认结果未知/);expect(field('教师备注内容')).toBeDisabled();fireEvent.click(button('重试原备注提交'));await waitFor(()=>expect(append).toHaveBeenCalledTimes(2));expect(append.mock.calls[1]).toEqual(append.mock.calls[0]);await waitFor(()=>expect(field('教师备注内容')).toHaveValue(''));
    }
  });
});

const artifact:ExportArtifact={artifactId:'artifact',exportId:'export',practiceRevisionId:'set-a-r1',variant:'student',assessmentId:null,fileAssetId:'file',filename:'student.docx',mediaType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',sha256:'ab'.repeat(32),byteSize:4,downloadUrl:'/api/v1/export-artifacts/artifact/download',createdAt:'now'};
const exportJob:JobView={jobId:'job',domain:'teaching',kind:'export',attempt:1,state:'succeeded',result:{artifactId:'artifact',exportId:'export',practiceRevisionId:'set-a-r1',variant:'student',assessmentId:null},error:null};
function exportsUI(api:typeof b4Api){return render(<StrictMode><PracticeExports revision={view().currentRevision} services={api} convertedAssessmentId="assessment-a" onLocked={vi.fn()}/></StrictMode>);}
describe('independent export display identity, no fake four-DB claim',()=>{
  it.each(['receipt','job','artifact'])('rejects wrong %s fixed identity before enabling download',async stage=>{
    const list=vi.fn().mockResolvedValue({items:[],total:0,offset:0,limit:50});const job={...exportJob,result:{...exportJob.result,...(stage==='job'?{practiceRevisionId:'WRONG'}:{})}};
    const metadata={...artifact,...(stage==='artifact'?{assessmentId:'WRONG'}:{})};const get=vi.fn().mockResolvedValue(metadata);
    const create=vi.fn().mockResolvedValue({exportId:'export',practiceRevisionId:stage==='receipt'?'WRONG':'set-a-r1',inputHash:'00'.repeat(32),job,replayed:false,reused:false});exportsUI(services({listPracticeExports:list,createPracticeExport:create,getExportArtifact:get}));fireEvent.click(button('生成学生 DOCX'));await screen.findByText('EXPORT_IDENTITY_MISMATCH');expect(screen.queryByRole('button',{name:'下载学生 DOCX'})).not.toBeInTheDocument();if(stage!=='artifact')expect(get).not.toHaveBeenCalled();
  });
  it('unknown template retry uses original variant/assessment/submission while other variants locked',async()=>{
    const job={...exportJob,result:{...exportJob.result,variant:'score_template',assessmentId:'assessment-a'}};const metadata={...artifact,variant:'score_template' as const,assessmentId:'assessment-a'};
    const create=vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST','未知',0,true)).mockResolvedValueOnce({exportId:'export',practiceRevisionId:'set-a-r1',inputHash:'00'.repeat(32),job,replayed:true,reused:false});const list=vi.fn().mockResolvedValue({items:[],total:0,offset:0,limit:50});exportsUI(services({listPracticeExports:list,createPracticeExport:create,getExportArtifact:vi.fn().mockResolvedValue(metadata)}));
    fireEvent.click(button('生成成绩模板 XLSX'));await screen.findByText(/确认结果未知/);expect(button('生成学生 DOCX')).toBeDisabled();expect(field('模板施测ID')).toBeDisabled();fireEvent.click(button('重试原导出提交'));await waitFor(()=>expect(create).toHaveBeenCalledTimes(2));expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);expect(create.mock.calls[0][2]).toMatchObject({variant:'score_template',assessmentId:'assessment-a'});await waitFor(()=>expect(list.mock.calls.length).toBeGreaterThan(2));
  });
  it('old revision history artifact is filtered and incomplete bytes do not create download URL',async()=>{
    const createURL=vi.fn();vi.stubGlobal('URL',class extends URL{static createObjectURL=createURL;static revokeObjectURL=vi.fn();});const list=vi.fn().mockResolvedValue({items:[artifact,{...artifact,artifactId:'old',practiceRevisionId:'old-revision',variant:'teacher'}],total:2,offset:0,limit:50});const download=vi.fn().mockResolvedValue({blob:new Blob(['x']),fileName:'student.docx'});exportsUI(services({listPracticeExports:list,downloadExportArtifact:download}));await screen.findByRole('button',{name:'下载学生 DOCX'});expect(screen.queryByRole('button',{name:'下载教师 DOCX'})).not.toBeInTheDocument();fireEvent.click(button('下载学生 DOCX'));await screen.findByText('EXPORT_DOWNLOAD_INCOMPLETE');expect(createURL).not.toHaveBeenCalled();
  });
});
