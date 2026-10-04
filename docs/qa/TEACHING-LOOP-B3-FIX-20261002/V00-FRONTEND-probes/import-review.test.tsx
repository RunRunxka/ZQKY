import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RosterImportPanel } from '@/features/assessments/RosterImportPanel';
import { PaperImportReview } from '@/features/assessments/PaperImportReview';
import type { PaperImportView } from '@/contracts/papers';
import type { RosterImportView } from '@/contracts/roster';
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const now = '2026-10-02T00:00:00Z';
const point = { id: 'point-manual', name: '独立正式点', code: 'K-1', subjectId: 'math', revisionId: 'point-r1' };
function rosterView(): RosterImportView { return { importId: 'roster-independent', classId: 'class-1', className: '独立班', state: 'reviewing', revision: 3, fileAsset: { originalName: '原名单.csv' } as never, headers: ['姓名', '学号'], mapping: { name: '姓名', studentNo: '学号' }, warnings: [], issues: [], rows: [{ rowNo: 1, name: '同名甲', studentNo: '00019', suggestion: 'conflict', decision: null, matchedStudentId: null, matchedStudentName: null, issues: [] }, { rowNo: 2, name: '新生乙', studentNo: '00020', suggestion: 'create', decision: null, matchedStudentId: null, matchedStudentName: null, issues: [] }, { rowNo: 3, name: '空白行', studentNo: null, suggestion: 'no_student_no', decision: null, matchedStudentId: null, matchedStudentName: null, issues: [] }], createdAt: now, updatedAt: now }; }
function paperView(): PaperImportView {
  const material = { id: 'material-required', blocks: [{ id: 'material-text', kind: 'paragraph', text: '必要背景不可丢失' }] };
  const content = { version: 2, sharedMaterials: [material], stemBlocks: [{ id: 'stem-one', kind: 'paragraph', text: '现有题干' }], optionBlocks: {}, answerBlocks: [], explanationBlocks: [], assets: [], origin: { originalAssetId: 'paper-origin', originalSha256: '2'.repeat(64), sourceLocator: {} } };
  return { paper: { paperId: 'paper-independent', subjectId: 'math', title: '旧实体标题', status: 'active', revision: 9, currentRevisionId: 'fixed-owned', currentState: 'draft', version: 1, totalScoreUnits: 200, totalScore: '2', itemCount: 1, scoredLeafCount: 1, blockingIssueCount: 1, createdAt: now }, revision: { paperId: 'paper-independent', paperRevisionId: 'fixed-owned', version: 1, state: 'draft', subjectId: 'math', title: '独立固定修订标题', totalScoreUnits: 200, totalScore: '2', confirmedAt: null, createdAt: now, items: [{ itemId: 'leaf-one', parentItemId: null, questionNo: '1', ordinal: 1, isScored: true, maxScoreUnits: 200, maxScore: '2', content, sourceLocator: { block: 1 }, knowledge: [{ knowledgePointId: point.id, knowledgeRevisionId: point.revisionId, knowledgeNameSnapshot: point.name, role: 'primary', source: 'human' }] }], blocks: Array.from({ length: 21 }, (_, index) => ({ blockId: `source-${index + 1}`, ordinal: index + 1, kind: 'paragraph' as const, locator: { paragraph: index + 1 }, disposition: 'unassigned' as const, itemId: null, excludeReason: null, content: { id: `source-${index + 1}`, kind: 'paragraph', text: `完整原文${index + 1}` } })), issues: [{ issueId: 'content-loss', code: 'CONTENT_LOSS', severity: 'blocking', message: '必须实际补录', blockId: 'source-1', locator: { paragraph: 1 }, status: 'open', resolution: null }] }, warnings: [] };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Independent roster import ownership and frozen decisions', () => {
  for (const suffix of ['csv', 'xlsx']) it(`${suffix}: raw multipart sheet/mapping, explicit create/link/ignore and unknown replay`, async () => {
    const confirms: Record<string, unknown>[] = []; let upload: FormData | null = null;
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'POST' && url.includes('/confirm')) { confirms.push(JSON.parse(String(init.body))); return confirms.length === 1 ? Promise.reject(new TypeError('confirmation committed; lost response')) : Promise.resolve(response({ importId: 'roster-independent', state: 'confirmed', applied: [], ignored: [3], replayed: true })); }
      if (init?.method === 'POST') { upload = init.body as FormData; return Promise.resolve(response(rosterView())); }
      if (url.includes('/students')) return Promise.resolve(response({ items: [{ id: 'same-name-explicit', name: '同名甲', studentNo: '00019' }], total: 1, offset: 0, limit: 100 }));
      return Promise.resolve(response({ items: [], total: 0, offset: 0, limit: 100 }));
    }));
    const changed = vi.fn(); render(<StrictMode><RosterImportPanel classId="class-1" onChanged={changed} /></StrictMode>);
    fireEvent.change(screen.getByLabelText('名单文件'), { target: { files: [new File(['test-bytes-only'], `名单.${suffix}`)] } });
    fireEvent.change(screen.getByLabelText('名单工作表名'), { target: { value: '隔离工作表' } }); fireEvent.change(screen.getByLabelText('上传时姓名表头'), { target: { value: '姓名' } }); fireEvent.change(screen.getByLabelText('上传时学号表头'), { target: { value: '学号' } });
    fireEvent.click(screen.getByRole('button', { name: '上传名单' })); await screen.findByTestId('roster-row-1');
    expect(upload!.get('sheetName')).toBe('隔离工作表'); expect(JSON.parse(String(upload!.get('mappingJson')))).toEqual({ name: '姓名', studentNo: '学号' });
    expect(screen.getByRole('button', { name: '确认名单' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('第 1 行处理'), { target: { value: 'link' } });
    fireEvent.change(screen.getByLabelText('第 1 行关联学生'), { target: { value: 'same-name-explicit' } });
    fireEvent.change(screen.getByLabelText('第 2 行处理'), { target: { value: 'create' } }); fireEvent.change(screen.getByLabelText('第 3 行处理'), { target: { value: 'ignore' } });
    fireEvent.click(screen.getByRole('button', { name: '确认名单' })); await screen.findByText(/确认结果未知/);
    expect(screen.getByLabelText('第 1 行处理')).toBeDisabled(); expect(screen.getByLabelText('名单工作表名')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '确认名单' })); await screen.findByTestId('roster-import-result');
    expect(confirms).toHaveLength(2); expect(confirms[1]).toEqual(confirms[0]); expect(confirms[0]).toMatchObject({ expectedRevision: 3, identityMatches: [{ rowNo: 1, action: 'link', studentId: 'same-name-explicit' }, { rowNo: 2, action: 'create', studentId: null }, { rowNo: 3, action: 'ignore', studentId: null }] }); expect(changed).toHaveBeenCalledTimes(1);
  });
  for (const status of [200, 422]) it(`upload ${status} after class switch cannot show old import or signal parent`, async () => {
    const gate = deferred<Response>();
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => init?.method === 'POST' ? gate.promise : Promise.resolve(response({ items: [], total: 0 }))));
    const changed = vi.fn(); const ui = render(<RosterImportPanel classId="class-1" onChanged={changed} />);
    fireEvent.change(screen.getByLabelText('名单文件'), { target: { files: [new File(['old'], 'old.csv')] } }); fireEvent.click(screen.getByRole('button', { name: '上传名单' }));
    ui.rerender(<RosterImportPanel classId="class-2" onChanged={changed} />);
    await act(async () => gate.resolve(response(status === 200 ? rosterView() : { code: 'VALIDATION_ERROR', message: 'old malformed' }, status)));
    expect(screen.queryByTestId('roster-row-1')).not.toBeInTheDocument(); expect(screen.queryByText(/old malformed/)).not.toBeInTheDocument(); expect(changed).not.toHaveBeenCalled();
  });
});

describe('Independent full paper authoring and own fixed revision', () => {
  function setup(initial: PaperImportView, handler: (url: string, init?: RequestInit) => Promise<Response> | null) {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input); const handled = handler(url, init); if (handled) return handled;
      if (url.includes('/knowledge-points')) return Promise.resolve(response({ items: [point], total: 1 }));
      if (url.includes('/model-profiles')) return Promise.resolve(response([]));
      if (url.includes('/content')) return Promise.resolve(response(initial.revision));
      if (url.includes('/papers/')) return Promise.resolve(response(initial.paper));
      return Promise.resolve(response({ items: [], total: 0 }));
    }));
  }
  it('21 source blocks paginate; actual structured supplement + shared material + manual container/leaf remain in PATCH', async () => {
    const initial = paperView(); let patch: Record<string, unknown> | null = null;
    setup(initial, (_url, init) => { if (init?.method === 'PATCH') { patch = JSON.parse(String(init.body)); return Promise.resolve(response(initial.revision)); } return null; });
    render(<PaperImportReview initial={initial} onSelected={vi.fn()} onChanged={vi.fn()} />);
    expect(screen.queryByTestId('paper-source-source-21')).not.toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: '下一页原文' })); expect(screen.getByTestId('paper-source-source-21')).toHaveTextContent('完整原文21'); fireEvent.click(screen.getByRole('button', { name: '上一页原文' }));
    const issue = screen.getByLabelText('问题 content-loss 处置'); expect(within(issue).queryByRole('option', { name: '有明确依据排除' })).not.toBeInTheDocument();
    fireEvent.change(issue, { target: { value: 'supplement_text' } }); fireEvent.change(screen.getByLabelText('问题 content-loss 补录目标块'), { target: { value: 'source-1' } }); fireEvent.change(screen.getByLabelText('问题 content-loss 补录文本'), { target: { value: '真实补录内容' } });
    fireEvent.change(screen.getByLabelText('原文块 2 关联共同材料'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: '新增题目' })); fireEvent.change(screen.getByLabelText('题 新题2 题号'), { target: { value: '2' } }); fireEvent.click(screen.getByLabelText('题 2 计分叶'));
    fireEvent.click(screen.getByRole('button', { name: '新增题目' })); fireEvent.change(screen.getByLabelText('题 新题3 题号'), { target: { value: '2(1)' } });
    const parentId = (screen.getByLabelText('题 2(1) 父题') as HTMLSelectElement).options[2].value;
    fireEvent.change(screen.getByLabelText('题 2(1) 父题'), { target: { value: parentId } }); fireEvent.change(screen.getByLabelText('题 2(1) 满分'), { target: { value: '1.25' } });
    fireEvent.change(screen.getByLabelText('原文块 3 加入题面'), { target: { value: '2' } });
    await waitFor(() => expect(within(screen.getByLabelText('题 2(1) 知识点')).getByRole('option', { name: 'K-1 · 独立正式点' })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('题 2(1) 知识点'), { target: { value: point.id } });
    fireEvent.click(screen.getByRole('button', { name: '保存原卷草稿' })); await waitFor(() => expect(patch).not.toBeNull());
    expect(patch).toMatchObject({ expectedRevision: 9, issues: [{ issueId: 'content-loss', status: 'resolved', resolution: { kind: 'supplement_text', targetBlockId: 'source-1', text: '真实补录内容' } }] });
    const items = patch!.items as { parentItemId: string | null; isScored: boolean; maxScore: string | null; content: { sharedMaterials: { id: string }[]; stemBlocks: { text: string }[] } }[];
    expect(items[0].content.sharedMaterials.map((material) => material.id)).toEqual(['material-required', 'source-2']);
    expect(items[1].isScored).toBe(false); expect(items[1].maxScore).toBeNull(); expect(items[2].parentItemId).toBe(parentId); expect(items[2].maxScore).toBe('1.25'); expect(items[2].content.stemBlocks[0].text).toBe('完整原文3');
  });
  for (const readStatus of [200, 503]) it(`confirmed receipt reads its fixed revision despite newer entity head; read ${readStatus} ${readStatus === 200 ? 'selects own title' : 'never changes selection'}`, async () => {
    const initial = paperView(); const reads: string[] = [];
    setup(initial, (url, init) => {
      if (init?.method === 'POST') return Promise.resolve(response({ paperId: initial.paper.paperId, paperRevisionId: 'confirmed-owned', state: 'confirmed', totalScoreUnits: 200, scoredLeafCount: 1, replayed: false }));
      if (url.includes('/papers/') && !url.includes('/content')) return Promise.resolve(response({ ...initial.paper, currentRevisionId: 'newer-unrelated', title: '后来实体标题' }));
      if (url.includes('/content')) { reads.push(url); return Promise.resolve(response(readStatus === 200 ? { ...initial.revision, paperRevisionId: 'confirmed-owned', title: '自己的固定标题', state: 'confirmed' } : { code: 'REVISION_READ_UNAVAILABLE', message: 'fixed revision could not be read' }, readStatus)); }
      return null;
    });
    const selected = vi.fn(); render(<PaperImportReview initial={initial} onSelected={selected} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: '确认原卷入库' })); await waitFor(() => expect(reads).toHaveLength(1));
    expect(reads[0]).toContain('/revisions/confirmed-owned/content'); expect(reads[0]).not.toContain('newer-unrelated');
    if (readStatus === 200) { await waitFor(() => expect(selected).toHaveBeenCalledTimes(1)); expect(selected.mock.calls[0][0]).toMatchObject({ paperRevisionId: 'confirmed-owned', title: '自己的固定标题' }); }
    else { await screen.findByTestId('paper-review-error'); expect(selected).not.toHaveBeenCalled(); }
  });
  it('unknown paper receipt locks editing and retry sends identical request + submissionId', async () => {
    const initial = paperView(); const bodies: unknown[] = [];
    setup(initial, (_url, init) => { if (init?.method === 'POST') { bodies.push(JSON.parse(String(init.body))); return bodies.length === 1 ? Promise.reject(new TypeError('receipt lost')) : Promise.resolve(response({ paperId: initial.paper.paperId, paperRevisionId: 'fixed-owned', state: 'confirmed', totalScoreUnits: 200, scoredLeafCount: 1, replayed: true })); } return null; });
    render(<PaperImportReview initial={initial} onSelected={vi.fn()} onChanged={vi.fn()} />); fireEvent.click(screen.getByRole('button', { name: '确认原卷入库' }));
    await screen.findByRole('button', { name: '重试原卷确认' }); expect(screen.getByLabelText('原卷修订标题')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原卷确认' })); await waitFor(() => expect(bodies).toHaveLength(2)); expect(bodies[1]).toEqual(bodies[0]);
  });
  it('successful paper confirmation after unmount cannot select old fixed revision or notify parent', async () => {
    const initial = paperView(); const gate = deferred<Response>(); setup(initial, (_url, init) => init?.method === 'POST' ? gate.promise : null);
    const selected = vi.fn(); const changed = vi.fn(); const ui = render(<PaperImportReview initial={initial} onSelected={selected} onChanged={changed} />); fireEvent.click(screen.getByRole('button', { name: '确认原卷入库' })); ui.unmount();
    await act(async () => gate.resolve(response({ paperId: initial.paper.paperId, paperRevisionId: 'fixed-owned', state: 'confirmed', totalScoreUnits: 200, scoredLeafCount: 1, replayed: false })));
    expect(selected).not.toHaveBeenCalled(); expect(changed).not.toHaveBeenCalled();
  });
});
