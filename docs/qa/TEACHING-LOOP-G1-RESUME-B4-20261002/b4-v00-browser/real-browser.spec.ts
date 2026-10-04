import { test, expect, type Page, type APIRequestContext, type TestInfo } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const folder=path.dirname(fileURLToPath(import.meta.url));
const api='http://127.0.0.1:8001';
type Json=Record<string,any>;
const hash=(bytes:Buffer)=>crypto.createHash('sha256').update(bytes).digest('hex');
function gate(){let release!:()=>void;const promise=new Promise<void>(resolve=>{release=resolve;});return {promise,release};}
async function get(request:APIRequestContext,route:string){const r=await request.get(api+route);expect(r.status(),route).toBe(200);return r.json();}
async function postResult(page:Page,pathEnd:string,status:number,click:()=>Promise<void>){
  const pending=page.waitForResponse(r=>r.url().endsWith(pathEnd)&&r.request().method()==='POST');
  await click();const response=await pending;expect(response.status(),pathEnd).toBe(status);return response.json();
}
function offlinePython(testInfo:TestInfo,args:string[]){
  const executable=process.env.ZQKY_B4_V00_PYTHON;
  if(!executable)throw new Error('Explicit existing Python runtime is required');
  const started=Date.now();const out=spawnSync(executable,[path.join(folder,'artifacts.py'),...args],{cwd:folder,encoding:'utf8',windowsHide:true});
  const identity=`python-${args[0]}-${started}`;
  fs.writeFileSync(testInfo.outputPath(`${identity}-stdout.log`),out.stdout??'');
  fs.writeFileSync(testInfo.outputPath(`${identity}-stderr.log`),out.stderr??'');
  fs.writeFileSync(testInfo.outputPath(`${identity}.json`),JSON.stringify({executable,args:[path.join(folder,'artifacts.py'),...args],cwd:folder,started,ended:Date.now(),elapsedMs:Date.now()-started,exit:out.status,signal:out.signal,error:out.error?.message},null,2));
  expect(out.error).toBeUndefined();expect(out.status,out.stderr).toBe(0);
}

async function layout(page:Page,testInfo:TestInfo,stage:string){
  const states=[];
  for(const size of [{width:1440,height:900},{width:1920,height:1080},{width:390,height:844}]){
    await page.setViewportSize(size);
    const metrics=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
      overflowing:[...document.querySelectorAll<HTMLElement>('main input,main button,main select,main summary')].filter(e=>{const r=e.getBoundingClientRect();return !e.closest('.b4-table-wrap,.space-tabs')&&r.width>0&&(r.left<-.5||r.right>innerWidth+.5);}).map(e=>({tag:e.tagName,label:e.getAttribute('aria-label')??e.textContent?.slice(0,80)})),
      scrollRegions:[...document.querySelectorAll<HTMLElement>('.b4-table-wrap,.space-tabs')].map(e=>({label:e.getAttribute('aria-label'),clientWidth:e.clientWidth,scrollWidth:e.scrollWidth,overflowX:getComputedStyle(e).overflowX}))}));
    expect(metrics.scroll,`${stage} ${size.width} document overflow`).toBeLessThanOrEqual(size.width);
    expect(metrics.body,`${stage} ${size.width} body overflow`).toBeLessThanOrEqual(size.width);
    // Wide fixed-fact tables may scroll inside an explicitly labelled wrapper.
    // Interactive controls themselves must remain within the viewport.
    expect(metrics.overflowing,`${stage} ${size.width}`).toEqual([]);
    await page.screenshot({path:testInfo.outputPath(`${stage}-${size.width}.png`),fullPage:true});states.push(metrics);
  }
  fs.writeFileSync(testInfo.outputPath(`${stage}-layout.json`),JSON.stringify(states,null,2));
  await page.setViewportSize({width:1440,height:900});
}

async function keyboardAndMotion(page:Page,testInfo:TestInfo){
  const first=page.getByRole('tab',{name:'班级依据',exact:true});
  const keyboardTarget=page.getByRole('tab',{name:'学生依据',exact:true});
  await first.focus();await page.keyboard.press('Tab');await expect(keyboardTarget).toBeFocused();
  const focus=await keyboardTarget.evaluate(e=>({visible:e.matches(':focus-visible'),style:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth}));
  expect(focus.visible).toBe(true);expect(focus.style).not.toBe('none');expect(parseFloat(focus.width)).toBeGreaterThanOrEqual(2);
  await page.screenshot({path:testInfo.outputPath('keyboard-visible-focus.png'),fullPage:true});
  await keyboardTarget.evaluate(e=>(e as HTMLElement).blur());await page.mouse.move(1,1);
  // This real primary button has a background hover transition; the report tabs
  // have no hover color change. No QA-injected CSS or invented animation.
  const target=page.getByRole('button',{name:'创建本次报告',exact:true});
  await page.emulateMedia({reducedMotion:'no-preference'});
  const before=await target.evaluate(e=>getComputedStyle(e).backgroundColor);
  const animation=target.evaluate(e=>new Promise(resolve=>{
    e.addEventListener('pointerenter',()=>requestAnimationFrame(()=>resolve({color:getComputedStyle(e).backgroundColor,duration:getComputedStyle(e).transitionDuration,animations:e.getAnimations().map(a=>({state:a.playState,duration:a.effect?.getTiming().duration}))})),{once:true});
  }));
  await target.screenshot({path:testInfo.outputPath('motion-normal-before.png')});
  await target.hover();const normal=await animation as Json;
  expect(normal.duration.split(',').some((v:string)=>parseFloat(v)>0.00002)).toBe(true);
  expect(normal.animations.some((a:Json)=>a.state==='running')).toBe(true);
  await page.waitForTimeout(200);await target.screenshot({path:testInfo.outputPath('motion-normal-final.png')});
  await page.mouse.move(1,1);await page.waitForTimeout(200);await page.emulateMedia({reducedMotion:'reduce'});
  await target.screenshot({path:testInfo.outputPath('motion-reduced-before.png')});
  const reducedBefore=await target.evaluate(e=>getComputedStyle(e).backgroundColor);
  const reducedSample=target.evaluate(e=>new Promise(resolve=>{
    e.addEventListener('pointerenter',()=>requestAnimationFrame(()=>{const color=getComputedStyle(e).backgroundColor;requestAnimationFrame(()=>resolve({color,next:getComputedStyle(e).backgroundColor,duration:getComputedStyle(e).transitionDuration,animations:e.getAnimations().map(a=>a.playState)}));}),{once:true});
  }));
  await target.hover();const reduced=await reducedSample as Json;
  expect(reduced.duration.split(',').every((v:string)=>parseFloat(v)<=0.00002)).toBe(true);
  expect(reduced.color).not.toBe(reducedBefore);expect(reduced.color).toBe(reduced.next);expect(reduced.animations).not.toContain('running');
  await target.screenshot({path:testInfo.outputPath('motion-reduced-final.png')});
  offlinePython(testInfo,['pixels',testInfo.outputPath('motion-normal-before.png'),testInfo.outputPath('motion-normal-final.png'),testInfo.outputPath('motion-reduced-before.png'),testInfo.outputPath('motion-reduced-final.png'),testInfo.outputPath('motion-pixels.json')]);
  fs.writeFileSync(testInfo.outputPath('actual-motion-focus.json'),JSON.stringify({before,normal,reducedBefore,reduced,focus},null,2));
  await page.emulateMedia({reducedMotion:'no-preference'});
}

test('真实 history→明确人次→报告/备注→缺口手动补题→练习审核/三下载→转换→T60→新T70；晚响应/未知原包/三视口',async({page,request},testInfo)=>{
  expect(process.version).toBe('v24.19.0');
  const seedPath=process.env.ZQKY_B4_V00_SEED;
  if(!seedPath||process.env.ZQKY_B4_V00_OWNED_API!=='http://127.0.0.1:8001')throw new Error('CTRL must authorize exact owned backend and its seed before execution');
  const seed=JSON.parse(fs.readFileSync(seedPath,'utf8'));
  const server=await get(request,'/__test/b4');expect(server.seed).toEqual(seed);
  expect(Object.values(seed.emptyB4Counts)).toEqual([0,0,0,0,0]);expect(server.calls).toEqual([]);
  const apiLog:Json[]=[];page.on('response',response=>{if(response.url().includes('/api/v1/'))apiLog.push({url:response.url(),status:response.status(),method:response.request().method()});});
  const originalMatrix=await get(request,`/api/v1/score-revisions/${seed.scoreRevisionId}/matrix?offset=0&limit=50`);
  const originalScore=await get(request,`/api/v1/score-revisions/${seed.scoreRevisionId}`);
  const evidenceExpectedTotals=[900,null,null,800];
  for(let index=0;index<4;index++)expect(originalMatrix.rows.find((r:Json)=>r.participant.studentId===seed.students[index].id&&r.participant.attemptNo===1).participant.totalUnits).toBe(evidenceExpectedTotals[index]);

  await page.goto(`/assessments?assessmentId=${seed.assessmentId}&step=history`);
  await page.getByRole('tab',{name:'5 历史',exact:true}).click();
  await page.getByTestId(`assessments-revision-${seed.scoreRevisionId}`).click();
  await page.getByRole('link',{name:'分析这份固定成绩',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(`/learning-analysis\\?assessmentId=${seed.assessmentId}&scoreRevisionId=${seed.scoreRevisionId}`));
  await expect(page.getByLabel('分析成绩修订',{exact:true})).toHaveValue(seed.scoreRevisionId);
  await expect(page.getByRole('button',{name:'创建本次报告',exact:true})).toBeDisabled();
  const nameA=seed.students[0].name;
  await page.getByLabel(`分析人次 ${nameA} 1`,{exact:true}).check();
  await page.getByLabel(`分析人次 ${nameA} 2`,{exact:true}).check();
  await expect(page.getByLabel(`分析人次 ${nameA} 1`,{exact:true})).not.toBeChecked();
  await page.getByLabel(`分析人次 ${nameA} 1`,{exact:true}).check();
  await expect(page.getByLabel(`分析人次 ${nameA} 2`,{exact:true})).not.toBeChecked();
  for(const student of seed.students.slice(1))await page.getByLabel(`分析人次 ${student.name} 1`,{exact:true}).check();
  const analysis=await postResult(page,`/assessments/${seed.assessmentId}/analysis-runs`,202,()=>page.getByRole('button',{name:'创建本次报告',exact:true}).click());
  const facts=page.getByRole('region',{name:'报告事实与证据',exact:true});
  await expect(facts).toBeVisible();
  await expect(page.getByRole('region',{name:'固定报告历史',exact:true}).locator('button.primary .b4-meta')).toHaveText(`报告 ${analysis.runId} · 已准备`);
  const initialRun=await get(request,`/api/v1/analysis-runs/${analysis.runId}`);
  expect(initialRun.reportReady).toBe(true);expect(initialRun.selectionSnapshot).toMatchObject({uniqueStudentCount:4,participantCount:4,leafCount:3});
  const classes=await get(request,`/api/v1/analysis-runs/${analysis.runId}/classes`);
  expect(classes.items.find((r:Json)=>r.knowledgePoint.knowledgePointId===seed.points[0].id)).toMatchObject({numerator:2,denominator:3});
  expect(classes.items.find((r:Json)=>r.knowledgePoint.knowledgePointId===seed.points[1].id)).toMatchObject({numerator:1,denominator:3});
  const k1Row=facts.locator('tbody tr').filter({hasText:seed.points[0].revisionId});await expect(k1Row).toContainText('2 / 3');
  await keyboardAndMotion(page,testInfo);
  await page.getByRole('tab',{name:'学生依据',exact:true}).click();await expect(facts.locator('tbody tr')).toHaveCount(8);
  await page.getByRole('tab',{name:'全部题证据',exact:true}).click();
  const evidence=facts.locator(':scope > [role="tabpanel"] > details');await expect(evidence).toHaveCount(12);
  for(let n=0;n<12;n++)await evidence.nth(n).locator(':scope > summary').click();
  const images=facts.locator('img');await expect(images).toHaveCount(12);
  await expect.poll(()=>images.evaluateAll(all=>all.every(e=>(e as HTMLImageElement).complete&&(e as HTMLImageElement).naturalWidth>0))).toBe(true);
  await expect(facts.locator('.katex')).toHaveCount(12);
  await expect(facts.locator('table')).toHaveCount(12);
  await layout(page,testInfo,'initial-rich-report');
  const initialEvidence=await get(request,`/api/v1/analysis-runs/${analysis.runId}/evidence?limit=200`);
  expect(initialEvidence.total).toBe(12);expect(initialEvidence.items.every((r:Json)=>r.practiceRevisionId===null&&r.practiceItemId===null)).toBe(true);
  await page.getByRole('tab',{name:'教师备注',exact:true}).click();
  await page.getByLabel('备注人次',{exact:true}).selectOption(initialRun.participants.find((p:Json)=>p.studentId===seed.students[0].id).participantId);
  await page.getByLabel('备注知识点',{exact:true}).selectOption(seed.points[0].id);
  await page.getByLabel('教师备注内容',{exact:true}).fill('本次运算失分关联，具体错因需教师确认。');
  const note=await postResult(page,`/analysis-runs/${analysis.runId}/notes`,201,()=>page.getByRole('button',{name:'追加教师备注',exact:true}).click());
  await expect(facts).toContainText(note.note);
  await page.getByLabel('练习标题',{exact:true}).fill('B4浏览器闭环练习');
  await page.getByLabel(`练习目标 ${seed.points[0].name}`,{exact:true}).check();
  await page.getByLabel('练习题量',{exact:true}).fill('2');
  // Manual generated questions have unspecified difficulty. This is an explicit
  // teacher-selected constraint, never a silent widening after the gap.
  await page.getByLabel('允许未标注难度',{exact:true}).check();
  const created=await postResult(page,'/api/v1/practice-sets',201,()=>page.getByRole('button',{name:'创建针对练习',exact:true}).click());
  await page.getByRole('link',{name:'打开新练习：B4浏览器闭环练习',exact:true}).click();
  const editor=page.getByRole('region',{name:'练习草稿编辑',exact:true});
  await editor.getByRole('button',{name:'获取正式题建议',exact:true}).click();
  await expect(editor.getByRole('region',{name:'正式题建议与缺口',exact:true})).toContainText('正式题建议：1 / 2');
  await expect(editor).toContainText('仍有缺口');
  expect((await get(request,'/__test/b4')).calls).toHaveLength(0);
  await editor.getByRole('link',{name:'缺题时手动补题并校对',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(`returnPracticeSetId=${created.practiceSetId}#generation$`));
  const panel=page.getByTestId('qb-generation-panel');
  if(!await panel.isVisible())await page.getByTestId('qb-generation-open').click();
  await panel.getByRole('combobox',{name:'学科',exact:true}).selectOption('math');
  await panel.getByLabel('有理数（F10-RATIONAL）',{exact:true}).check();
  await panel.getByLabel('题数（1–10）',{exact:true}).fill('1');
  const generation=await postResult(page,'/api/v1/question-generation-jobs',202,()=>page.getByTestId('qb-generation-submit').click());
  expect(generation).toMatchObject({state:'queued',attempt:0,candidateCount:0});
  await expect.poll(async()=>(await get(request,'/__test/b4')).calls.length).toBe(1);
  const actualRequest=(await get(request,'/__test/b4')).calls[0].request;
  const serialized=JSON.stringify(actualRequest);
  expect(serialized).toContain(seed.points[0].id);expect(serialized).toContain('F10-RATIONAL');
  for(const student of seed.students){expect(serialized).not.toContain(student.name);expect(serialized).not.toContain(student.studentNo);expect(serialized).not.toContain(student.id);}
  for(const p of seed.participants)expect(serialized).not.toContain(p.participantId);
  expect((await request.post(api+'/__test/b4/release')).status()).toBe(200);
  await expect(page.getByTestId('qb-generation-succeeded')).toContainText('生成 1 道待校对候选草稿');
  await page.getByTestId('qb-generation-import').click();
  await expect(page).toHaveURL(new RegExp(`^http://127\\.0\\.0\\.1:5174/question-bank/imports/[^/?#]+\\?returnPracticeSetId=${created.practiceSetId}$`));
  const importMatch=page.url().match(/\/question-bank\/imports\/([^/?#]+)/);expect(importMatch).not.toBeNull();
  const importId=importMatch![1];
  await page.getByRole('textbox',{name:'题干',exact:true}).fill('人工校对补题：计算 (-2)+5，并说明运算方向。');
  const manualSavePending=page.waitForResponse(r=>r.url().includes('/question-drafts/')&&r.request().method()==='PATCH');
  await page.getByRole('button',{name:'保存修改',exact:true}).click();expect((await manualSavePending).status()).toBe(200);
  await expect(page.getByRole('button',{name:'标记已校对',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'标记已校对',exact:true}).click();await expect(page.getByTestId('qb-review-state')).toHaveText('已校对');
  const confirmed=await postResult(page,`/question-imports/${importId}/confirm`,200,()=>page.getByRole('button',{name:'确认入库（1 道）',exact:true}).click());
  expect(confirmed.failures).toEqual([]);expect(confirmed.confirmedQuestionIds).toHaveLength(1);
  const manualQuestion=await get(request,`/api/v1/questions/${confirmed.confirmedQuestionIds[0]}`);expect(manualQuestion.knowledgeLinks[0].knowledgePointId).toBe(seed.points[0].id);
  // Actual preserved return link through the existing confirmation/library UI.
  await page.getByRole('button',{name:'查看已入库题目',exact:true}).click();
  await page.getByRole('link',{name:'返回练习并重新选正式题',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(`/practices\\?practiceSetId=${created.practiceSetId}$`));
  await editor.getByRole('button',{name:'获取正式题建议',exact:true}).click();
  await expect(editor.getByRole('region',{name:'正式题建议与缺口',exact:true})).toContainText('正式题建议：2 / 2');
  const suggestions=editor.getByRole('region',{name:'正式题建议与缺口',exact:true});
  for(const question of [seed.questionId,confirmed.confirmedQuestionIds[0]]){
    const detail=suggestions.locator('details').filter({has:page.locator('summary',{hasText:`正式题 ${question} ·`})});
    await detail.locator(':scope > summary').click();await detail.getByRole('button',{name:'作为一计分叶加入，随后复核结构',exact:true}).click();
  }
  await editor.getByLabel('第1题节点1题号',{exact:true}).fill('16(1)');
  await editor.getByLabel('第1题整题满分',{exact:true}).fill('2');await editor.getByLabel('第1题节点1满分',{exact:true}).fill('2');
  await editor.getByLabel('第2题整题满分',{exact:true}).fill('2');await editor.getByLabel('第2题节点1满分',{exact:true}).fill('2');
  const patchGate=gate(),patchSeen=gate();let delayed:Json|null=null;let patchOnce=true;
  await page.route('**/practice-sets/*/draft',async route=>{
    if(route.request().method()!=='PATCH'||!patchOnce){await route.continue();return;}
    patchOnce=false;const response=await route.fetch();expect(response.status()).toBe(200);delayed=await response.json();patchSeen.release();await patchGate.promise;await route.fulfill({response});
  });
  await editor.getByRole('button',{name:'保存草稿',exact:true}).click();await patchSeen.promise;
  await editor.getByLabel('第1题整题满分',{exact:true}).fill('2.50');await editor.getByLabel('第1题节点1满分',{exact:true}).fill('2.50');
  await expect(editor.getByRole('button',{name:'独立审核此草稿',exact:true})).toBeDisabled();
  patchGate.release();await expect(editor).toContainText('之后的编辑仍保留，尚未保存');
  await expect(editor.getByLabel('第1题节点1满分',{exact:true})).toHaveValue('2.50');
  const savePending=page.waitForResponse(r=>r.url().endsWith(`/practice-sets/${created.practiceSetId}/draft`)&&r.request().method()==='PATCH');
  await editor.getByRole('button',{name:'保存草稿',exact:true}).click();const savedResponse=await savePending;expect(savedResponse.status()).toBe(200);const saved=await savedResponse.json();
  expect(saved.revision).toBe((delayed as unknown as Json).revision+1);expect(saved.currentRevision.items[0]).toMatchObject({questionNo:'16(1)',maxScoreUnits:250});
  await expect(editor).toContainText('审核需要另行确认');
  await layout(page,testInfo,'saved-practice');
  const originalReviewBodies:string[]=[];let dropReview=true;let reviewed:Json|null=null;
  await page.route('**/practice-sets/*/review',async route=>{
    originalReviewBodies.push(route.request().postData()!);const response=await route.fetch();expect(response.status()).toBe(200);reviewed=await response.json();
    if(dropReview){dropReview=false;await route.abort('failed');}else await route.fulfill({response});
  });
  await editor.getByRole('button',{name:'独立审核此草稿',exact:true}).click();
  await expect(editor).toContainText('确认结果未知');await expect(editor.getByLabel('第1题节点1题号',{exact:true})).toBeDisabled();
  await editor.getByRole('button',{name:'重试原审核提交',exact:true}).click();
  await expect(page.getByRole('region',{name:'固定练习导出',exact:true})).toBeVisible();expect(originalReviewBodies).toHaveLength(2);expect(originalReviewBodies[1]).toBe(originalReviewBodies[0]);
  const fixed=(reviewed as unknown as Json).currentRevision.practiceRevisionId;
  const immutablePractice=await get(request,`/api/v1/practice-sets/${created.practiceSetId}/revisions/${fixed}`);
  const exportPanel=page.getByRole('region',{name:'固定练习导出',exact:true});
  const exportBodies:string[]=[],exportReceipts:Json[]=[];let dropExport=true;
  await page.route('**/practice-sets/*/revisions/*/exports',async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    exportBodies.push(route.request().postData()!);const response=await route.fetch();expect(response.status()).toBe(202);exportReceipts.push(await response.json());
    if(dropExport){dropExport=false;await route.abort('failed');}else await route.fulfill({response});
  });
  await exportPanel.getByRole('button',{name:'生成学生 DOCX',exact:true}).click();await expect(exportPanel).toContainText('确认结果未知');
  await expect(exportPanel.getByRole('button',{name:'生成教师 DOCX',exact:true})).toBeDisabled();
  await exportPanel.getByRole('button',{name:'重试原导出提交',exact:true}).click();
  await expect(exportPanel.getByRole('button',{name:'下载学生 DOCX',exact:true})).toBeEnabled();expect(exportBodies[1]).toBe(exportBodies[0]);
  const files:Record<string,string>={},metadata:Record<string,Json>={};
  async function download(variant:string,label:string){
    const exportHistory=await get(request,`/api/v1/practice-sets/${created.practiceSetId}/revisions/${fixed}/exports`);
    const record=exportHistory.items.find((x:Json)=>x.variant===variant);expect(record.practiceRevisionId).toBe(fixed);
    const artifact=await get(request,'/api/v1/export-artifacts/'+record.artifactId);expect(artifact.practiceRevisionId).toBe(fixed);expect(artifact.exportId).toBe(record.exportId);expect(artifact.variant).toBe(variant);
    const accepted=exportReceipts.find(receipt=>receipt.exportId===record.exportId);expect(accepted).toBeDefined();
    const job=await get(request,`/api/v1/workflow-jobs/${accepted!.job.jobId}?domain=teaching`);expect(job).toMatchObject({state:'succeeded',kind:'export'});expect(job.result).toMatchObject({artifactId:record.artifactId,exportId:record.exportId,practiceRevisionId:fixed,variant,assessmentId:artifact.assessmentId});
    const promise=page.waitForEvent('download');await exportPanel.getByRole('button',{name:label,exact:true}).click();const payload=await promise;
    expect(await payload.failure()).toBeNull();const target=testInfo.outputPath(variant+(variant==='score_template'?'.xlsx':'.docx'));await payload.saveAs(target);
    const bytes=fs.readFileSync(target);expect(hash(bytes)).toBe(artifact.sha256);expect(bytes.length).toBe(artifact.byteSize);files[variant]=target;metadata[variant]=artifact;
  }
  await download('student','下载学生 DOCX');
  await exportPanel.getByRole('button',{name:'生成教师 DOCX',exact:true}).click();await expect(exportPanel.getByRole('button',{name:'下载教师 DOCX',exact:true})).toBeEnabled();await download('teacher','下载教师 DOCX');
  const conversionPanel=page.getByRole('region',{name:'练习转换施测',exact:true});
  await conversionPanel.getByLabel('练习施测日期',{exact:true}).fill('2026-10-02');await conversionPanel.getByLabel('练习施测班级',{exact:true}).selectOption(seed.classId);
  for(const student of seed.students)await conversionPanel.getByLabel(`练习参测 ${student.name}`,{exact:true}).check();
  await conversionPanel.getByLabel(`${seed.students[2].name} 练习出勤`,{exact:true}).selectOption('absent');
  const conversion=await postResult(page,`/practice-sets/${created.practiceSetId}/revisions/${fixed}/assessments`,201,()=>conversionPanel.getByRole('button',{name:'转换固定练习为施测',exact:true}).click());
  await expect(exportPanel.getByLabel('模板施测ID',{exact:true})).toHaveValue(conversion.assessmentId);
  await exportPanel.getByRole('button',{name:'生成成绩模板 XLSX',exact:true}).click();await expect(exportPanel.getByRole('button',{name:'下载成绩模板 XLSX',exact:true})).toBeEnabled();await download('score_template','下载成绩模板 XLSX');
  expect(metadata.score_template.assessmentId).toBe(conversion.assessmentId);
  const artifactManifest=testInfo.outputPath('downloads.json');fs.writeFileSync(artifactManifest,JSON.stringify({files,metadata},null,2));offlinePython(testInfo,['verify',artifactManifest,testInfo.outputPath('download-all-entry-verification.json')]);
  const entered=testInfo.outputPath('returned-scores.xlsx');offlinePython(testInfo,['fill',files.score_template,entered]);
  await layout(page,testInfo,'fixed-conversion-exports');
  await conversionPanel.getByRole('link',{name:'进入现有成绩工作区',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(`assessmentId=${conversion.assessmentId}&step=score`));
  await page.getByLabel('成绩表格文件',{exact:true}).setInputFiles(entered);await page.getByLabel('工作表名',{exact:true}).fill('成绩');
  await page.getByRole('button',{name:'上传并创建待校对批次',exact:true}).click();
  await expect(page.getByLabel('映射工作表名',{exact:true})).toHaveValue('成绩');
  await page.getByLabel('学号列',{exact:true}).fill('A');await page.getByLabel('姓名列',{exact:true}).fill('B');await page.getByLabel('出勤列',{exact:true}).fill('C');
  await page.getByLabel('16(1) 列字母',{exact:true}).fill('E');await page.getByLabel('2 列字母',{exact:true}).fill('F');
  await page.getByRole('button',{name:'保存映射并重算',exact:true}).click();
  await expect(page.getByTestId('assessments-mapping-notice')).toContainText('已保存映射');
  await page.getByTestId('score-goto-acknowledge').click();await page.getByLabel(/承认 .* 缺考 1 人次/).check();await page.getByLabel(/承认空白 1 个单元覆盖 1 人次/).check();
  await page.getByTestId('score-open-confirm').click();const dialog=page.getByRole('dialog',{name:'确认成绩入库',exact:true});
  const returnConfirmPending=page.waitForResponse(r=>r.url().includes('/score-imports/')&&r.url().endsWith('/confirm')&&r.request().method()==='POST');
  await dialog.getByTestId('score-confirm-submit').click();const returnConfirmResponse=await returnConfirmPending;expect(returnConfirmResponse.status()).toBe(200);const returnedScore=await returnConfirmResponse.json();
  await expect(page.getByTestId('score-confirm-result')).toContainText('已确认入库');
  await page.getByRole('tab',{name:'5 历史',exact:true}).click();await page.getByRole('link',{name:'分析这份固定成绩',exact:true}).click();
  await expect(page.getByLabel('分析成绩修订',{exact:true})).toHaveValue(returnedScore.revisionId);
  for(const student of seed.students)await page.getByLabel(`分析人次 ${student.name} 1`,{exact:true}).check();
  const returnedAnalysis=await postResult(page,`/assessments/${conversion.assessmentId}/analysis-runs`,202,()=>page.getByRole('button',{name:'创建本次报告',exact:true}).click());
  await expect(facts).toBeVisible();
  await expect(page.getByRole('region',{name:'固定报告历史',exact:true}).locator('button.primary .b4-meta')).toHaveText(`报告 ${returnedAnalysis.runId} · 已准备`);
  await page.getByRole('tab',{name:'全部题证据',exact:true}).click();
  const returnedEvidence=await get(request,`/api/v1/analysis-runs/${returnedAnalysis.runId}/evidence?limit=200`);
  expect(returnedEvidence.total).toBe(8);
  expect(returnedEvidence.items.every((r:Json)=>r.practiceRevisionId===fixed&&!!r.practiceItemId)).toBe(true);
  const converted=await get(request,`/api/v1/assessments/${conversion.assessmentId}`);
  expect(converted.assessment.paperRevisionId).toBe(conversion.paperRevisionId);
  for(const row of returnedEvidence.items){const old=immutablePractice.items.find((i:Json)=>i.practiceItemId===row.practiceItemId);expect(old).toBeDefined();expect(row.itemPath).toBe(old.questionNo);expect(row.maxScoreUnits).toBe(old.maxScoreUnits);}
  const returnedDetails=facts.locator(':scope > [role="tabpanel"] > details');await expect(returnedDetails).toHaveCount(8);
  await returnedDetails.first().locator(':scope > summary').click();await returnedDetails.first().getByText('原始来源与回流映射',{exact:true}).click();await expect(returnedDetails.first()).toContainText(`练习修订 ${fixed}`);
  await layout(page,testInfo,'returned-report');
  expect(await get(request,`/api/v1/score-revisions/${seed.scoreRevisionId}`)).toEqual(originalScore);
  expect(await get(request,`/api/v1/score-revisions/${seed.scoreRevisionId}/matrix?offset=0&limit=50`)).toEqual(originalMatrix);
  expect(await get(request,`/api/v1/analysis-runs/${analysis.runId}/evidence?limit=200`)).toEqual(initialEvidence);
  expect(await get(request,`/api/v1/practice-sets/${created.practiceSetId}/revisions/${fixed}`)).toEqual(immutablePractice);
  const chainPath=testInfo.outputPath('chain.json');
  fs.writeFileSync(chainPath,JSON.stringify({runtime:{version:process.version,execPath:process.execPath,executableSHA256:hash(fs.readFileSync(process.execPath))},seed,analysis,initialRun,classes,note,created,generation,actualRequest,confirmed,saved,reviewed,originalReviewBodies,exportBodies,conversion,metadata,returnedScore,returnedAnalysis,returnedEvidence,apiLog},null,2));
  offlinePython(testInfo,['db',seedPath,chainPath,testInfo.outputPath('four-db-lineage-verification.json')]);
});
