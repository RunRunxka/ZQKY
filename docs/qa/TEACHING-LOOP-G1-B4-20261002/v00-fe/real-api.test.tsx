import { StrictMode } from 'react';
import fs from 'node:fs';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AssessmentsWorkspace } from '@/features/assessments/AssessmentsWorkspace';
import { ScorePanel } from '@/features/assessments/ScorePanel';

// Native network call captured before installing a relative-path adapter. No business data is mocked.
const networkFetch = globalThis.fetch;
const origin = 'http://127.0.0.1:8001';
const qa = 'docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe';
const seed = JSON.parse(fs.readFileSync('docs/qa/TEACHING-LOOP-G1-B4-20261002/root/browser-seed.json', 'utf8').replace(/^\ufeff/, ''));
const log: unknown[] = [];

async function forward(input: RequestInfo | URL, init: RequestInit = {}) {
  const path = String(input); let body = init.body; const headers = new Headers(init.headers);
  // jsdom File/FormData are converted into real multipart bytes without inventing any API response.
  if (body instanceof FormData) {
    const boundary = `v00-${crypto.randomUUID()}`; const parts: Buffer[] = [];
    for (const [name, value] of body.entries()) {
      parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="${name}"`));
      if (value instanceof File) {
        parts.push(Buffer.from(`; filename="${value.name}"\r\nContent-Type: ${value.type || 'application/octet-stream'}\r\n\r\n`));
        const bytes = await new Promise<ArrayBuffer>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.onerror = reject; reader.readAsArrayBuffer(value); });
        parts.push(Buffer.from(bytes));
      } else parts.push(Buffer.from(`\r\n\r\n${value}`));
      parts.push(Buffer.from('\r\n'));
    }
    parts.push(Buffer.from(`--${boundary}--\r\n`)); body = Buffer.concat(parts);
    headers.set('content-type', `multipart/form-data; boundary=${boundary}`);
  }
  // jsdom AbortSignal is not a Node/Undici signal. Component observation epochs remain exercised;
  // this adapter intentionally does not test physical transport cancellation.
  const { signal: _jsdomSignal, ...transportInit } = init;
  let result: Response;
  try { result = await networkFetch(path.startsWith('/') ? `${origin}${path}` : path, { ...transportInit, headers, body }); }
  catch (error) { log.push({ path, transportError: String(error) }); throw error; }
  const cloned = result.clone();
  let receipt: unknown;
  try { receipt = await cloned.json(); } catch { receipt = { contentType: cloned.headers.get('content-type') }; }
  log.push({ path, method: init.method ?? 'GET', status: result.status, body: receipt });
  return result;
}
async function api(path: string, method = 'GET', body?: unknown) {
  const result = await forward(`/api/v1${path}`, { method, headers: { 'content-type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await result.json(); expect(result.ok, JSON.stringify(value)).toBe(true); return value;
}
beforeEach(() => Object.defineProperties(HTMLDialogElement.prototype, {
  showModal: { configurable: true, value: function(this: HTMLDialogElement) { this.setAttribute('open',''); } },
  close: { configurable: true, value: function(this: HTMLDialogElement) { this.removeAttribute('open'); } },
}));
afterEach(() => { cleanup(); vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLDialogElement.prototype,'showModal'); Reflect.deleteProperty(HTMLDialogElement.prototype,'close');
  fs.writeFileSync(`${qa}/real-api-receipts.json`, JSON.stringify(log,null,2));
});

it('actual FastAPI/four databases: mounted roster create/import/transfer preserves drafts; saved new score confirms and unknown original package replays', async () => {
  const tag = `V00-COMP-${Date.now()}`;
  const cls = await api('/classes','POST',{code:tag,name:`${tag}班`,schoolYear:'2026',gradeId:'grade-1'});
  const to = await api('/classes','POST',{code:`${tag}-to`,name:`${tag}转入`,schoolYear:'2026',gradeId:'grade-1'});
  const a = await api('/students','POST',{name:`${tag}甲`,studentNo:`${tag}-001`,classId:cls.id});
  const b = await api('/students','POST',{name:`${tag}乙`,studentNo:`${tag}-002`,classId:cls.id});
  vi.stubGlobal('fetch',forward);
  render(<StrictMode><AssessmentsWorkspace/></StrictMode>);
  fireEvent.click(await screen.findByTestId(`assessments-class-${cls.id}`)); fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
  fireEvent.click(await screen.findByLabelText(`参测 ${a.name}`));
  fireEvent.change(screen.getByLabelText(`${a.name} 出勤`),{target:{value:'exempt'}});
  fireEvent.change(screen.getByLabelText(`${a.name} 人次序号`),{target:{value:'3'}});
  fireEvent.click(screen.getByTestId('assessments-tab-roster'));
  fireEvent.change(screen.getByLabelText('学生姓名'),{target:{value:`${tag}丙`}});
  fireEvent.change(screen.getByLabelText('学生学号'),{target:{value:`${tag}-003`}});
  fireEvent.submit(screen.getByRole('form',{name:'添加学生'}));
  await waitFor(() => expect(screen.getByLabelText('学生姓名')).toHaveValue(''));
  fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
  await screen.findByLabelText(`参测 ${tag}丙`);
  expect(screen.getByLabelText(`参测 ${a.name}`)).not.toBeChecked();
  expect(screen.getByLabelText(`${a.name} 出勤`)).toHaveValue('exempt'); expect(screen.getByLabelText(`${a.name} 人次序号`)).toHaveValue(3);
  fireEvent.click(screen.getByTestId('assessments-tab-roster'));
  fireEvent.change(screen.getByLabelText('名单文件'),{target:{files:[new File([`\ufeff学号,姓名\n${tag}-004,${tag}丁\n`],'真名单.csv',{type:'text/csv'})]}});
  fireEvent.click(screen.getByRole('button',{name:'上传名单',exact:true}));
  fireEvent.change(await screen.findByLabelText('第 1 行处理'),{target:{value:'create'}});
  fireEvent.click(screen.getByRole('button',{name:'保存映射与行决策',exact:true}));
  await screen.findByText(/已保存映射与行决策/);
  fireEvent.click(screen.getByRole('button',{name:'确认名单',exact:true})); await screen.findByTestId('roster-import-result');
  fireEvent.click(screen.getByTestId('assessments-tab-assessment')); await screen.findByLabelText(`参测 ${tag}丁`);
  expect(screen.getByLabelText(`参测 ${a.name}`)).not.toBeChecked(); expect(screen.getByLabelText(`${a.name} 人次序号`)).toHaveValue(3);
  fireEvent.click(screen.getByTestId('assessments-tab-roster'));
  await waitFor(() => expect(screen.getByLabelText('转班学生')).toContainHTML(b.id));
  fireEvent.change(screen.getByLabelText('转班学生'),{target:{value:b.id}});
  fireEvent.change(screen.getByLabelText('转入班级'),{target:{value:to.id}});
  fireEvent.click(screen.getByRole('button',{name:'确认转班',exact:true})); await screen.findByTestId('roster-transfer-result');
  fireEvent.click(screen.getByTestId('assessments-tab-assessment'));
  await waitFor(() => expect(screen.queryByLabelText(`参测 ${b.name}`)).toBeNull());
  expect(await screen.findByTestId('assessments-roster-notice')).toHaveTextContent('已撤销其参测选择及人次草稿');
  expect(screen.getByLabelText(`参测 ${a.name}`)).not.toBeChecked(); expect(screen.getByLabelText(`${a.name} 出勤`)).toHaveValue('exempt'); expect(screen.getByLabelText(`${a.name} 人次序号`)).toHaveValue(3);
  const roster = await api(`/classes/${cls.id}/students`);
  expect(roster.items.map((x: {name:string}) => x.name).sort()).toEqual([`${tag}甲`,`${tag}丙`,`${tag}丁`].sort());
  cleanup();

  const now = new Date(); const heldOn = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
  const created = await api('/assessments','POST',{paperRevisionId:seed.paperRevisionId,title:`${tag}施测`,assessmentType:'exam',heldOn,classIds:[cls.id],submissionId:crypto.randomUUID(),
    participants:roster.items.map((x: {id:string}) => ({studentId:x.id,classId:cls.id,attendance:'present',attemptNo:1}))});
  const assessmentId = created.assessment.assessmentId;
  const file = new FormData(); file.append('file',new File([`\ufeff学号,姓名,Q1,Q2,Q3\n${tag}-001,${tag}甲,2,2,5\n${tag}-003,${tag}丙,2,3,5\n${tag}-004,${tag}丁,0,3,5\n`],'真成绩.csv',{type:'text/csv'}));
  const uploadedResponse = await forward(`/api/v1/assessments/${assessmentId}/score-imports`,{method:'POST',body:file});
  expect(uploadedResponse.status).toBe(201); const uploaded = await uploadedResponse.json();
  const paper = await api(`/papers/${seed.paperId}/revisions/${seed.paperRevisionId}/content`);
  await api(`/score-imports/${uploaded.importId}`,'PATCH',{expectedRevision:uploaded.revision,mapping:{workSheet:'CSV',headerRow:1,studentNoColumn:'A',nameColumn:'B',itemColumns:paper.items.filter((x:{isScored:boolean})=>x.isScored).map((x:{itemId:string},i:number)=>({itemId:x.itemId,column:['C','D','E'][i]}))}});
  const confirms: unknown[] = []; let lost = false;
  vi.stubGlobal('fetch',async (url:RequestInfo|URL,init?:RequestInit)=>{
    if(String(url).endsWith('/confirm')&&String(url).includes('/score-imports/')) {
      confirms.push(JSON.parse(String(init?.body))); const result = await forward(url,init);
      expect(result.status).toBe(200); if(!lost){lost=true;throw new TypeError('actual server committed; response lost');} return result;
    }
    return forward(url,init);
  });
  render(<StrictMode><ScorePanel assessmentId={assessmentId} onOpenHistory={()=>{}} refreshToken={0} onChanged={()=>{}}/></StrictMode>);
  await screen.findByLabelText('第 2 行 列 C 校正'); fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
  fireEvent.change(screen.getByLabelText('第 2 行 列 C 校正'),{target:{value:'1'}});
  expect(screen.queryByTestId('score-open-confirm')).toBeNull(); expect(screen.getByTestId('score-goto-acknowledge')).toBeDisabled(); expect(confirms).toEqual([]);
  fireEvent.click(screen.getByTestId('score-save-drafts')); await screen.findByTestId('score-draft-notice');
  await waitFor(()=>expect(screen.getByTestId('score-goto-acknowledge')).toBeEnabled());
  const saved = await api(`/score-imports/${uploaded.importId}`);
  fireEvent.click(screen.getByTestId('score-goto-acknowledge')); fireEvent.click(screen.getByTestId('score-open-confirm')); fireEvent.click(screen.getByTestId('score-confirm-submit'));
  await screen.findByTestId('score-confirm-unknown'); expect(screen.getByLabelText('第 2 行 列 C 校正')).toBeDisabled();
  fireEvent.click(screen.getByTestId('score-confirm-submit')); await screen.findByTestId('score-confirm-result');
  expect(confirms).toHaveLength(2); expect(confirms[1]).toEqual(confirms[0]);
  expect(confirms[0]).toMatchObject({expectedImportRevision:saved.revision,previewVersion:saved.previewVersion});
  const revisions = await api(`/assessments/${assessmentId}/score-revisions`); expect(revisions.items).toHaveLength(1);
  const matrix = await api(`/score-revisions/${revisions.items[0].revisionId}/matrix?offset=0&limit=50`);
  expect(matrix.total).toBe(3); const row = matrix.rows.find((x:{participant:{name:string}})=>x.participant.name===a.name);
  expect(row.cells.map((x:{scoreUnits:number})=>x.scoreUnits)).toEqual([100,200,500]); expect(row.participant.totalUnits).toBe(800);
  log.push({case:'actual-summary',assessmentId,importId:uploaded.importId,scoreRevisionId:revisions.items[0].revisionId,confirms,finalRow:row});
},30_000);
