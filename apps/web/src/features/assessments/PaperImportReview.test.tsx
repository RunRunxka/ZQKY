import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { PaperImportView } from '@/contracts/papers';
import { PaperImportReview } from './PaperImportReview';

function fixture(): PaperImportView {
  const paragraph = { id: 'paragraph-1', kind: 'paragraph', text: '计算 $1+1$' };
  const material = { id: 'material-1', kind: 'table', columnCount: 2,
    cells: [{ text: '共同材料', isHeader: true, rowSpan: 1, colSpan: 2 }] };
  const formula = { id: 'formula-1', kind: 'formula', latex: 'x^2' };
  return {
    paper: { paperId: 'paper-1', subjectId: 'math', title: '初始标题', status: 'active', revision: 1,
      currentRevisionId: 'pr-1', currentState: 'draft', version: 1, totalScoreUnits: 200,
      totalScore: '2', itemCount: 1, scoredLeafCount: 1, blockingIssueCount: 0, createdAt: '2026-10-02T00:00:00Z' },
    revision: { paperId: 'paper-1', paperRevisionId: 'pr-1', version: 1, state: 'draft', subjectId: 'math',
      title: '固定标题', totalScoreUnits: 200, totalScore: '2', confirmedAt: null, createdAt: '2026-10-02T00:00:00Z',
      items: [{ itemId: 'i-1', parentItemId: null, questionNo: '1', ordinal: 1, isScored: true,
        maxScoreUnits: 200, maxScore: '2', knowledge: [], sourceLocator: { paragraphIndex: 2 },
        content: { version: 2, sharedMaterials: [{ id: 'material-1', blocks: [material] }], stemBlocks: [paragraph, formula],
          optionBlocks: {}, answerBlocks: [], explanationBlocks: [], assets: [], origin: { originalAssetId: 'asset-1', originalSha256: 'abc', sourceLocator: { paragraphIndex: 2 } } } }],
      blocks: [{ blockId: 'b-1', ordinal: 1, kind: 'paragraph', locator: { paragraphIndex: 2 },
        disposition: 'item', itemId: 'i-1', excludeReason: null, content: paragraph },
      { blockId: 'b-2', ordinal: 2, kind: 'table', locator: { tableIndex: 1 }, disposition: 'shared_material',
        itemId: null, excludeReason: null, content: material }], issues: [] }, warnings: [],
  };
}
function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function setup(mutation: (url: string, init: RequestInit) => Promise<Response>, initial = fixture()) {
  let current = initial;
  const fetched = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === 'POST' || init?.method === 'PATCH') return mutation(url, init);
    if (url.includes('/knowledge-points')) return response(200, { items: [{ id: 'kp-1', code: 'M1', name: '整数运算' }], total: 1 });
    if (url.includes('/model-profiles')) return response(200, [{ id: 'model-1', displayName: '受控模型' }]);
    if (url.includes('/content')) return response(200, current.revision);
    return response(200, current.paper);
  });
  vi.stubGlobal('fetch', fetched);
  return { fetched, update: (next: PaperImportView) => { current = next; } };
}
function ui(initial = fixture(), selected = vi.fn(), changed = vi.fn()) {
  return <StrictMode><PaperImportReview initial={initial} onSelected={selected} onChanged={changed} /></StrictMode>;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('原卷完整源块校对与确认', () => {
  it('关联/满分保存不损失公式、合并表格、共同材料与来源；确认后选用固定修订标题', async () => {
    const initial = fixture();
    const bodies: Record<string, unknown>[] = [];
    const fixtureApi = setup(async (url, init) => {
      const body = JSON.parse(String(init.body)); bodies.push(body);
      const next: PaperImportView = { ...initial, paper: { ...initial.paper, revision: 2, title: '实体新标题' },
        revision: { ...initial.revision, state: url.endsWith('/confirm') ? 'confirmed' : 'draft' } };
      fixtureApi.update(next);
      return url.endsWith('/confirm') ? response(200, { paperId: 'paper-1', paperRevisionId: 'pr-1',
        state: 'confirmed', totalScoreUnits: 200, scoredLeafCount: 1, replayed: false }) : response(200, next.revision);
    });
    const selected = vi.fn();
    render(ui(initial, selected));
    await screen.findByRole('option', { name: 'M1 · 整数运算' });
    expect(screen.getAllByRole('columnheader', { name: '共同材料' }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('x', { exact: true }).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText('题 1 知识点'), { target: { value: 'kp-1' } });
    fireEvent.change(screen.getByLabelText('题 1 满分'), { target: { value: '2.00' } });
    expect(screen.getByTestId('paper-confirm')).toBeDisabled();
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    await waitFor(() => expect(screen.getByTestId('paper-confirm')).toBeEnabled());
    expect(bodies[0]).toMatchObject({ expectedRevision: 1, items: [{ maxScore: '2.00', knowledge: [{ knowledgePointId: 'kp-1' }] }] });
    expect((bodies[0].items as { content: unknown }[])[0].content).toEqual(initial.revision.items[0].content);
    fireEvent.click(screen.getByTestId('paper-confirm'));
    await screen.findByTestId('paper-confirm-result');
    await waitFor(() => expect(selected).toHaveBeenCalledExactlyOnceWith({ paperId: 'paper-1', paperRevisionId: 'pr-1', title: '固定标题', totalScoreUnits: 200, scoredLeafCount: 1 }));
    expect(bodies[1]).toMatchObject({ expectedRevision: 2 });
  });

  it('无题号原件可手建计分叶并把原文块真正加入题面和共同材料', async () => {
    const initial = fixture(); initial.revision.items = [];
    initial.revision.blocks = initial.revision.blocks.map((block) => ({ ...block, disposition: 'unassigned', itemId: null }));
    const bodies: Record<string, unknown>[] = [];
    setup(async (_url, init) => { bodies.push(JSON.parse(String(init.body))); return response(200, initial.revision); }, initial);
    render(ui(initial));
    fireEvent.click(screen.getByRole('button', { name: '新增题目' }));
    fireEvent.change(screen.getByLabelText('题 新题1 题号'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('题 1 满分'), { target: { value: '2' } });
    await screen.findByRole('option', { name: 'M1 · 整数运算' });
    fireEvent.change(screen.getByLabelText('题 1 知识点'), { target: { value: 'kp-1' } });
    fireEvent.change(screen.getByLabelText('原文块 1 加入题面'), { target: { value: '0' } });
    fireEvent.change(screen.getByLabelText('原文块 2 关联共同材料'), { target: { value: '0' } });
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ items: [{ questionNo: '1', content: {
      stemBlocks: [{ id: 'paragraph-1', text: '计算 $1+1$' }], sharedMaterials: [{ id: 'b-2', blocks: [{ kind: 'table' }] }],
    } }], blocks: [{ blockId: 'b-1', disposition: 'item' }, { blockId: 'b-2', disposition: 'shared_material' }] });
  });

  it('人工建立完整父子题号，容器显式不计分并保持同卷父题身份', async () => {
    const initial = fixture(); initial.revision.items = [];
    const bodies: Record<string, unknown>[] = [];
    setup(async (_url, init) => { bodies.push(JSON.parse(String(init.body))); return response(200, initial.revision); }, initial);
    render(ui(initial));
    fireEvent.click(screen.getByRole('button', { name: '新增题目' }));
    fireEvent.change(screen.getByLabelText('题 新题1 题号'), { target: { value: '10' } });
    fireEvent.click(screen.getByLabelText('题 10 计分叶'));
    fireEvent.click(screen.getByRole('button', { name: '新增题目' }));
    fireEvent.change(screen.getByLabelText('题 新题2 题号'), { target: { value: '10(1)' } });
    fireEvent.change(screen.getByLabelText('题 10(1) 满分'), { target: { value: '2' } });
    const parent = screen.getByLabelText('题 10(1) 父题') as HTMLSelectElement;
    const parentId = Array.from(parent.options).find((option) => option.textContent === '10')?.value;
    fireEvent.change(parent, { target: { value: parentId } });
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    await waitFor(() => expect(bodies).toHaveLength(1));
    const items = bodies[0].items as Record<string, unknown>[];
    expect(items[0]).toMatchObject({ questionNo: '10', isScored: false, maxScore: null });
    expect(items[1]).toMatchObject({ questionNo: '10(1)', isScored: true, maxScore: '2', parentItemId: items[0].itemId });
  });

  it('内容损失问题只允许实际补录，其他问题可带排除依据；422保留编辑与定位', async () => {
    const initial = fixture(); initial.revision.issues = [
      { issueId: 'loss', code: 'CONTENT_LOSS', severity: 'blocking', status: 'open', message: '文本缺失', blockId: 'b-1', locator: { paragraphIndex: 2 }, resolution: null },
      { issueId: 'heading', code: 'HEADING_UNASSIGNED', severity: 'warning', status: 'open', message: '标题待处理', blockId: 'b-2', locator: {}, resolution: null },
    ];
    const bodies: Record<string, unknown>[] = [];
    setup(async (_url, init) => { bodies.push(JSON.parse(String(init.body))); return response(422, { code: 'PAPER_ISSUE_RESOLUTION_INVALID', message: '补录不合法', details: { issues: [{ row: 0, field: 'resolution.text', code: 'PAPER_ISSUE_RESOLUTION_INVALID', message: '复核补录文本' }] } }); }, initial);
    render(ui(initial));
    expect(screen.getByLabelText('问题 loss 处置')).not.toHaveTextContent('有明确依据排除');
    fireEvent.change(screen.getByLabelText('问题 loss 处置'), { target: { value: 'supplement_text' } });
    fireEvent.change(screen.getByLabelText('问题 loss 补录目标块'), { target: { value: 'b-1' } });
    fireEvent.change(screen.getByLabelText('问题 loss 补录文本'), { target: { value: '实际补录题面' } });
    fireEvent.change(screen.getByLabelText('问题 heading 处置'), { target: { value: 'exclude' } });
    fireEvent.change(screen.getByLabelText('问题 heading 排除理由'), { target: { value: '仅有页眉，不属于题面' } });
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    expect(await screen.findByTestId('paper-review-error')).toHaveTextContent('resolution.text');
    expect(screen.getByLabelText('问题 loss 补录文本')).toHaveValue('实际补录题面');
    expect(bodies[0]).toMatchObject({ issues: [
      { issueId: 'loss', status: 'resolved', resolution: { kind: 'supplement_text', targetBlockId: 'b-1', text: '实际补录题面' } },
      { issueId: 'heading', status: 'excluded', resolution: { kind: 'exclude', reason: '仅有页眉，不属于题面' } },
    ] });
  });

  it('CAS409保留标题编辑；刷新对照不清除本地输入', async () => {
    setup(async () => response(409, { code: 'PAPER_REVISION_STALE', message: '已更新', details: { currentRevision: 9 } }));
    render(ui());
    fireEvent.change(screen.getByLabelText('原卷修订标题'), { target: { value: '保留标题' } });
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    expect(await screen.findByTestId('paper-review-error')).toHaveTextContent('当前版本 9');
    fireEvent.click(screen.getByRole('button', { name: '刷新原卷对照' }));
    await screen.findByText('已刷新服务端对照；本地编辑保留，请核对后保存。');
    expect(screen.getByLabelText('原卷修订标题')).toHaveValue('保留标题');
    expect(screen.getByTestId('paper-confirm')).toBeDisabled();
  });

  it('确认响应丢失后重放原标识和原版本', async () => {
    const bodies: unknown[] = [];
    setup(async (_url, init) => {
      bodies.push(JSON.parse(String(init.body)));
      if (bodies.length === 1) throw new TypeError('lost response');
      return response(200, { paperId: 'paper-1', paperRevisionId: 'pr-1', state: 'confirmed',
        totalScoreUnits: 200, scoredLeafCount: 1, replayed: true });
    });
    render(ui());
    fireEvent.click(screen.getByTestId('paper-confirm'));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('原卷修订标题')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试原卷确认' }));
    await screen.findByTestId('paper-confirm-result');
    expect(bodies).toHaveLength(2); expect(bodies[1]).toEqual(bodies[0]);
  });

  it.each(['success', 'failure'] as const)('卸载后迟到保存%s不改变父级或选择', async (outcome) => {
    let complete!: (value: Response) => void;
    const gate = new Promise<Response>((resolve) => { complete = resolve; });
    const { fetched } = setup(() => gate);
    const selected = vi.fn(); const changed = vi.fn();
    const rendered = render(ui(fixture(), selected, changed));
    fireEvent.change(screen.getByLabelText('原卷修订标题'), { target: { value: '旧编辑' } });
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    await waitFor(() => expect(fetched.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1));
    rendered.unmount();
    await act(async () => complete(outcome === 'success' ? response(200, fixture().revision)
      : response(422, { code: 'OLD_ERROR', message: '旧请求错误' })));
    expect(selected).not.toHaveBeenCalled(); expect(changed).not.toHaveBeenCalled();
  });

  it('历史修订保持自己的标题和富内容，只能选用固定版本', async () => {
    const initial = fixture(); initial.revision.state = 'confirmed'; initial.paper.title = '后来新标题';
    setup(async () => response(500, {}), initial);
    const selected = vi.fn(); render(ui(initial, selected));
    expect(screen.getByRole('heading', { name: '固定原卷修订：固定标题' })).toBeInTheDocument();
    expect(screen.getByLabelText('原卷修订标题')).toBeDisabled();
    expect(screen.queryByTestId('paper-save-draft')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '选用此固定修订' }));
    expect(selected).toHaveBeenCalledExactlyOnceWith({ paperId: 'paper-1', paperRevisionId: 'pr-1', title: '固定标题', totalScoreUnits: 200, scoredLeafCount: 1 });
  });

  it('确认成功但固定修订读取失败时显示真实失败并不改父级选择', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return response(200, { paperId: 'paper-1', paperRevisionId: 'pr-1', state: 'confirmed', totalScoreUnits: 200, scoredLeafCount: 1, replayed: false });
      if (String(input).endsWith('/papers/paper-1')) return response(200, fixture().paper);
      if (String(input).endsWith('/content')) return response(503, { code: 'SERVICE_UNAVAILABLE', message: '固定内容暂不可读' });
      return response(200, String(input).includes('model-profiles') ? [] : { items: [], total: 0 });
    }));
    const selected = vi.fn(); render(ui(fixture(), selected));
    fireEvent.click(screen.getByTestId('paper-confirm'));
    await screen.findByTestId('paper-confirm-result');
    expect(await screen.findByTestId('paper-review-error')).toHaveTextContent('固定内容暂不可读');
    expect(selected).not.toHaveBeenCalled();
  });

  it('AI queued@0→succeeded@1展示真实候选，教师选择后按当前版本应用', async () => {
    const requests: { url: string; body: Record<string, unknown> }[] = [];
    let applied = false;
    const initial = fixture();
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'POST') {
        requests.push({ url, body: JSON.parse(String(init.body)) });
        if (url.endsWith('/knowledge-proposals')) return response(202, { jobId: 'job-1', domain: 'teaching', kind: 'paper_mapping', state: 'queued', attempt: 0, result: null, error: null });
        if (url.endsWith('/apply')) { applied = true; return response(200, initial.revision); }
      }
      if (url.includes('/workflow-jobs/')) return response(200, { jobId: 'job-1', domain: 'teaching', kind: 'paper_mapping', state: 'succeeded', attempt: 1, result: { proposalId: 'proposal-1' }, error: null });
      if (url.includes('/paper-proposals/')) return response(200, { proposalId: 'proposal-1', jobId: 'job-1', state: applied ? 'applied' : 'pending', baseRevision: 1, stale: false,
        items: [{ itemId: 'i-1', questionNo: '1', knowledgePointId: 'kp-1', proposedName: '整数运算', proposedCode: 'M1', evidence: ['题面计算'], ambiguity: false }], issues: [] });
      if (url.includes('/knowledge-points')) return response(200, { items: [{ id: 'kp-1', code: 'M1', name: '整数运算' }], total: 1 });
      if (url.includes('/model-profiles')) return response(200, [{ id: 'model-1', displayName: '受控模型' }]);
      if (url.endsWith('/content')) return response(200, initial.revision);
      return response(200, { ...initial.paper, revision: applied ? 2 : 1 });
    }));
    render(ui(initial));
    await screen.findByRole('option', { name: '受控模型' });
    fireEvent.change(screen.getByLabelText('原卷建议模型'), { target: { value: 'model-1' } });
    fireEvent.click(screen.getByRole('button', { name: '生成关联建议' }));
    await screen.findByLabelText('题 1 建议确认知识点');
    expect(screen.getByRole('button', { name: '审核应用所选建议' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('题 1 建议确认知识点'), { target: { value: 'kp-1' } });
    fireEvent.click(screen.getByRole('button', { name: '审核应用所选建议' }));
    await screen.findByText('已审核应用知识点建议，仍需确认原卷。');
    expect(requests).toHaveLength(2);
    expect(requests[0].body).toEqual({ expectedRevision: 1, modelProfileId: 'model-1' });
    expect(requests[1].body).toEqual({ expectedRevision: 1, selections: [{ itemId: 'i-1', knowledgePointId: 'kp-1' }] });
    await screen.findByText('候选：applied');
  });
});
