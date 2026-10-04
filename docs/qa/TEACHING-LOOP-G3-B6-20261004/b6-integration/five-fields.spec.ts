import { test, expect, type Page, type Route } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const seedFile = process.env.B6_INTEGRATION_SEED;
if (!seedFile) throw new Error('ROOT-owned isolated B6 seed is required');
const seed = JSON.parse(readFileSync(seedFile, 'utf8'));
if (seed.label !== 'b6-shared-r1' || seed.apiOrigin !== 'http://127.0.0.1:8001') throw new Error('Wrong runtime');
const candidateFile = process.env.B6_CANDIDATE;
if (!candidateFile) throw new Error('ROOT-built candidate is required');
const candidate = JSON.parse(readFileSync(candidateFile, 'utf8'));
if (seed.buildId !== candidate.buildId || seed.candidateSHA !== createHash('sha256').update(readFileSync(candidateFile)).digest('hex')) throw new Error('Runtime seed and candidate identity mismatch');
const five = ['coreCompetencies', 'keyPoints', 'teachingDesign', 'process', 'exercises'];
const six = ['title', 'totalLessons', 'currentLessonNo', 'lessonTypes', 'otherTypeText', 'reflection'];
const teacher = { title: 'B6教师标题《有理数加法》', totalLessons: '3', currentLessonNo: '2',
  lessonTypes: ['review', 'other', 'review'], otherTypeText: 'B6教师指定课型',
  coreCompetencies: 'B6原素养：符号与依据。', keyPoints: 'B6原重点：保留原教师安排。',
  teachingDesign: 'B6原设计：先独立作答。',
  process: [{ id: 'b6-teacher-a', stage: '教师原环节', design: '教师原设计', secondary: '教师原二次备课' }],
  exercises: 'B6原练习：保留原教师作业。', reflection: 'B6教师反思：五字段应用不能修改。' };
// Literal expected text and minute oracle. No production merge/proposal.patch-derived expected.
const text = { coreCompetencies: '候选素养：基于固定班级计数开展解释。', keyPoints: '候选重点：有理数运算和复核。',
  teachingDesign: '候选设计：独立判断、同伴比较与出口检测。', exercises: '候选练习：使用固定正式题，说明运算依据。' };
async function panel(page: Page, summary: string) {
  const target = page.locator('details.lesson-server-panel').filter({ has: page.locator('summary', { hasText: summary }) }).first();
  if ((await target.getAttribute('open')) === null) await target.locator('summary').first().click();
  return target;
}

test('B6 single class and KP actual UI adopts all five fields and fixes new history with six teacher sentinels', async ({ page, context, request }, info) => {
  const kp = seed.selectedKnowledgePointIds[0];
  const point = seed.originalFixed.report.knowledgePoints.find((p: {knowledgePointId:string}) => p.knowledgePointId === kp);
  const isolatedDraft = JSON.stringify({schemaVersion:1,revision:31,updatedAt:'2026-10-04T14:00:00+08:00',data:teacher});
  await context.addInitScript(raw => {
    if (localStorage.getItem('zhiqikeyuan:lesson-plan:v1') === null) localStorage.setItem('zhiqikeyuan:lesson-plan:v1',raw);
  },isolatedDraft);
  const business: Array<{path:string;status:number;body:unknown}> = [];
  page.on('response', async response => {
    if (response.url().includes('/api/v1/lesson-plans') && response.request().method() !== 'GET') {
      business.push({path:response.url(),status:response.status(),body:response.request().postDataJSON()});
    }
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/assessments?assessmentId='+encodeURIComponent(seed.assessmentId)+'&step=history');
  await page.getByTestId('assessments-revision-'+seed.scoreRevisionId).click();
  await expect(page.getByRole('region', {name:'只读成绩矩阵',exact:true})).toBeVisible();
  await page.getByRole('link',{name:'分析这份固定成绩',exact:true}).click();
  await page.getByRole('region',{name:'固定报告历史',exact:true}).getByRole('button',{name:new RegExp(seed.analysisRunId)}).click();
  await expect(page.getByRole('region',{name:'所选固定报告',exact:true})).toContainText(seed.scoreRevisionId);
  await page.getByRole('link',{name:'以本次固定学情准备教案',exact:true}).click();
  await expect(page.getByLabel('课题',{exact:true})).toHaveValue(teacher.title);
  let source = await panel(page,'班级、固定学情与生成来源');
  await source.getByLabel('教案班级',{exact:true}).selectOption(seed.classId);
  await source.getByLabel('固定学情报告',{exact:true}).selectOption(seed.analysisRunId);
  const kps = source.getByRole('group',{name:'明确选择知识点（最多50项）',exact:true});
  await expect(kps.getByRole('checkbox')).toHaveCount(2);
  const checks = await kps.getByRole('checkbox').all();
  expect(checks).toHaveLength(2);
  for (const check of checks) await check.uncheck();
  await kps.locator('label').filter({hasText:point.name}).getByRole('checkbox').check();
  expect(await kps.getByRole('checkbox',{checked:true}).count()).toBe(1);
  await expect(source.getByLabel('教案生成模型',{exact:true}).locator('option[value="'+seed.modelProfiles[0].profileId+'"]')).toHaveCount(1);
  let releaseMetadata!: () => void, metadataHeld!: () => void;
  const metadataGate = new Promise<void>(resolve => { releaseMetadata = resolve; });
  const held = new Promise<void>(resolve => { metadataHeld = resolve; });
  const metadataWire: Array<{url:string;status:number;responseSHA:string;body:unknown}> = [];
  let delayMetadata = true;
  const delayActualMetadata = async (route: Route) => {
    if (!delayMetadata || route.request().method() !== 'GET' || new URL(route.request().url()).pathname !== '/api/v1/model-profiles') { await route.continue(); return; }
    const actual = await route.fetch();
    const body = await actual.body();
    metadataWire.push({url:route.request().url(),status:actual.status(),responseSHA:createHash('sha256').update(body).digest('hex'),body:JSON.parse(body.toString('utf8'))});
    metadataHeld();
    await metadataGate;
    await route.fulfill({response:actual,body});
  };
  await page.route('**/api/v1/model-profiles**',delayActualMetadata);
  const createPanel = await panel(page,'后台文档与固定历史');
  const createdPromise = page.waitForResponse(r => r.url().endsWith('/lesson-plans') && r.request().method()==='POST');
  await createPanel.getByRole('button',{name:'将当前正文创建为后台教案',exact:true}).click();
  const created = await createdPromise; expect(created.status()).toBe(201); const base = await created.json();
  expect(base.currentRevision.data).toEqual(teacher);
  expect(base.currentRevision.contextSnapshot.analysis.knowledgePoints).toEqual([point]);
  await expect(page.getByRole('button',{name:'保存后台稿',exact:true})).toBeVisible();
  source = await panel(page,'班级、固定学情与生成来源');
  await expect(source.getByLabel('教案班级',{exact:true})).toBeDisabled();
  await expect(source.getByLabel('教案班级',{exact:true})).toHaveValue(seed.classId);
  const delayedKps = source.getByRole('group',{name:'明确选择知识点（最多50项）',exact:true});
  try {
    await held;
    expect(metadataWire).toHaveLength(1);
    expect(metadataWire[0].status).toBe(200);
    await expect(source.getByRole('status')).toHaveText('正在读取真实来源…');
    await expect(source.getByLabel('教案生成模型',{exact:true}).locator('option[value="'+seed.modelProfiles[0].profileId+'"]')).toHaveCount(0);
    await source.getByLabel('固定学情报告',{exact:true}).selectOption(seed.analysisRunId);
    await expect(delayedKps.getByRole('checkbox')).toHaveCount(2);
    for (const check of await delayedKps.getByRole('checkbox').all()) await check.uncheck();
    await delayedKps.locator('label').filter({hasText:point.name}).getByRole('checkbox').check();
    await expect(delayedKps.getByRole('checkbox',{checked:true})).toHaveCount(1);
  } finally { delayMetadata = false; releaseMetadata(); }
  await expect(source.getByLabel('教案生成模型',{exact:true}).locator('option[value="'+seed.modelProfiles[0].profileId+'"]')).toHaveCount(1);
  await expect(source.getByLabel('教材年级',{exact:true}).locator('option[value="senior-1"]')).toHaveCount(1);
  await expect(source.getByLabel('教材版本',{exact:true}).locator('option[value="renjiao-a"]')).toHaveCount(1);
  await expect(source.getByRole('status')).toHaveCount(0);
  await expect(source.getByLabel('固定学情报告',{exact:true})).toHaveValue(seed.analysisRunId);
  await expect(delayedKps.getByRole('checkbox',{checked:true})).toHaveCount(1);
  await source.getByLabel('教案生成模型',{exact:true}).selectOption(seed.modelProfiles[0].profileId);
  await source.getByLabel('课堂时长',{exact:true}).fill('43');
  await source.getByLabel('教案生成要求',{exact:true}).fill('基于固定教材和班级计数安排有理数加法复习。');
  await source.getByLabel('教材年级',{exact:true}).selectOption('senior-1');
  await source.getByLabel('教材版本',{exact:true}).selectOption('renjiao-a');
  await source.getByRole('button',{name:'读取可选教材',exact:true}).click();
  await source.getByLabel('教材固定修订',{exact:true}).selectOption(seed.textbook.documentId);
  await source.getByLabel('切片起点',{exact:true}).fill(String(seed.textbook.slices[0].charStart));
  await source.getByLabel('切片终点',{exact:true}).fill(String(seed.textbook.slices[0].charEnd));
  await source.getByRole('button',{name:'读取并核验教材切片',exact:true}).click();
  const adoptedSlice = source.getByRole('group',{name:'真实教材切片',exact:true}).locator('details').filter({hasText:seed.textbook.documentRevisionId});
  await expect(adoptedSlice.locator('summary')).toHaveText(seed.verifiedEvidence.evidence[0].title+' · '+seed.textbook.documentRevisionId+' · ['+seed.textbook.slices[0].charStart+', '+seed.textbook.slices[0].charEnd+')');
  await expect(adoptedSlice.locator('pre')).toHaveText(seed.textbook.normalizedText.slice(seed.textbook.slices[0].charStart,seed.textbook.slices[0].charEnd));
  await source.getByRole('button',{name:'读取已确认固定题',exact:true}).click();
  await source.locator('label').filter({hasText:seed.questionRevisionId}).getByRole('checkbox').check();
  await source.locator('label').filter({hasText:seed.practiceRevisionId}).getByRole('checkbox').check();
  await panel(page,'学情驱动 AI 候选与逐字段差异');
  const generated = page.waitForResponse(r => r.url().endsWith('/lesson-plans/'+base.lessonPlanId+'/proposals') && r.request().method()==='POST');
  await page.getByRole('button',{name:'保存当前稿并生成 AI 候选',exact:true}).click();
  const response = await generated; expect(response.status()).toBe(202); const receipt = await response.json();
  const labels = ['核心素养','教学重点','教学设计','教学过程（整段）','针对练习'];
  for (const label of labels) await page.getByLabel('采用'+label,{exact:true}).check();
  await expect(page.getByText('预算 43 分钟；各环节合计 43 分钟',{exact:true})).toBeVisible();
  await info.attach('b6-five-selected.png',{body:await page.screenshot(),contentType:'image/png'});
  const appliedResponse = page.waitForResponse(r => r.url().endsWith('/apply') && r.request().method()==='POST');
  await page.getByRole('button',{name:'仅采用所选完整字段',exact:true}).click();
  const appliedHTTP = await appliedResponse; expect(appliedHTTP.status()).toBe(200); const applied = await appliedHTTP.json();
  const expectedProcess = ['情境导入','合作探究','独立练习','归纳检测'].map((stage,i)=>({
    id:'lp_'+createHash('sha256').update(receipt.inputHash+'\0new:N'+(i+1)).digest('hex').slice(0,32),
    stage,design:'候选活动'+(i+1),secondary:'候选二次'+(i+1)}));
  const expected = {...teacher,...text,process:expectedProcess};
  expect(applied.currentRevision.data).toEqual(expected);
  expect(applied.currentRevision.selectedFields).toEqual(five);
  expect(applied.currentRevision.contextSnapshot).toEqual(base.currentRevision.contextSnapshot);
  expect(applied.currentRevision.contextSnapshot.analysis.knowledgePoints).toEqual([point]);
  expect(applied.currentRevision.contextSnapshot.analysis.scoreRevisionId).toBe(seed.scoreRevisionId);
  expect(applied.currentRevision.contextSnapshot.analysis.analysisRunId).toBe(seed.analysisRunId);
  expect(applied.currentRevision.processMetadata.map((s:{minutes:number})=>s.minutes)).toEqual([11,11,11,10]);
  for (const field of six) expect(applied.currentRevision.data[field]).toEqual(teacher[field as keyof typeof teacher]);
  await expect(page.getByLabel('教学反思',{exact:true})).toHaveValue(teacher.reflection);
  const docs = await panel(page,'后台文档与固定历史');
  await docs.getByRole('button',{name:'读取固定历史',exact:true}).click();
  await docs.getByRole('button',{name:new RegExp('只读 v'+applied.currentRevision.version+'\\b')}).click();
  await expect(page.getByLabel('课题',{exact:true})).toBeDisabled();
  await expect(page.getByLabel('教学重、难点',{exact:true})).toHaveValue(text.keyPoints);
  const fixed = await request.get(seed.apiOrigin+'/api/v1/lesson-plans/'+base.lessonPlanId+'/revisions/'+applied.currentRevisionId);
  expect(fixed.status()).toBe(200); expect(await fixed.json()).toEqual(applied.currentRevision);
  const applyCall = business.find(v=>v.path.endsWith('/apply'))!;
  expect((applyCall.body as {selectedFields:string[]}).selectedFields).toEqual(five);
  await info.attach('b6-ui-five-chain.json',{body:JSON.stringify({seedFile,seedSHA:createHash('sha256').update(readFileSync(seedFile)).digest('hex'),
    buildId:seed.buildId,candidateFile,candidateSHA:seed.candidateSHA,base,receipt,applied,expected,teacherFields:six,business,metadataWire,
    productBusinessFetchMocked:false,actualMetadataResponseDelayedOnly:true,
    providerTransportOnly:true,teacherQuality:'teacher_review_pending'}),contentType:'application/json'});
  await info.attach('b6-current-fixed-history.png',{body:await page.screenshot(),contentType:'image/png'});
});
