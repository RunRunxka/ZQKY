import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DraftEditor } from '@/features/question-bank/DraftEditor';
import { QuestionDetailPanel } from '@/features/question-bank/QuestionDetailPanel';
import { ReviewWorkspace } from '@/features/question-bank/ReviewWorkspace';
import { ConfirmPanel } from '@/features/question-bank/ConfirmPanel';
import { buildTaxonomyIndex } from '@/features/question-bank/taxonomy';
import { ApiError } from '@/services/api-client';
import type { DraftView } from '@/contracts/question-bank';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const content = { type: 'short_answer' as const, stemMarkdown: '独立旧题干', options: [], answer: { choiceKeys: [], accepted: null, textMarkdown: '独立答案' }, explanationMarkdown: '独立解析', assetIds: [] };
const metadata = { stageId: 'junior', gradeId: 'grade-1', subjectId: 'math', editionId: 'rj', knowledgeTags: ['历史文字标签'], difficulty: 'easy' as const };
function draft(id = 'draft-independent', revision = 4): DraftView { return { draftId: id, importId: 'import-independent', revision, content, metadata, sourceSpans: [], extractionMethod: 'ai', reviewState: 'reviewed', missingAnswerAcknowledged: false, warnings: [], duplicateOfQuestionId: null, knowledgeLinks: [{ knowledgePointId: 'point-independent', knowledgeRevisionId: 'point-r2', knowledgeNameSnapshot: '正式有理数', subjectIdSnapshot: 'math', role: 'primary', source: 'human' }] }; }
function detail(id: string, revision = 4) { return { questionId: id, revision, status: 'confirmed', content: { ...content, stemMarkdown: id === 'new-question' ? '独立新题干' : content.stemMarkdown }, metadata, answerState: 'provided', sources: [], sourceImportId: null, confirmedAt: '2026-10-02T00:00:00Z', knowledgeLinks: draft().knowledgeLinks }; }
function imported(revision = 4) { return { importId: 'import-independent', ownerId: 'local', state: 'needs_review', revision, uploadedFileName: '独立.md', uploadedBytes: 24, draftCount: 1, reviewedCount: 1, unassignedCount: 0, warnings: [], createdAt: '2026-10-02T00:00:00Z', drafts: [draft(undefined, revision)], unassignedBlocks: [] }; }
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Independent draft/detail late writes and formal knowledge display', () => {
  for (const status of [200, 409, 422]) {
    it(`draft write ${status} after object switch leaves new editor and parent untouched`, async () => {
      const gate = deferred<Response>();
      vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => init?.method === 'PATCH' ? gate.promise : Promise.resolve(response({ items: [], total: 0 }))));
      const updated = vi.fn(); const replaced = vi.fn(); const reload = vi.fn();
      const p = { importId: 'import-independent', draft: draft(), taxonomy: buildTaxonomyIndex(null), onDraftUpdated: updated, onDetailReplaced: replaced, onReloadDraft: reload };
      const ui = render(<StrictMode><DraftEditor {...p} /></StrictMode>);
      expect(screen.getByTestId('qb-knowledge-link-0')).toHaveTextContent('正式有理数'); expect(screen.getByTestId('qb-legacy-tags')).toHaveTextContent('历史文字标签');
      fireEvent.change(screen.getByLabelText('题干'), { target: { value: '旧编辑请求' } }); fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
      ui.rerender(<StrictMode><DraftEditor {...p} draft={{ ...draft('new-draft'), content: { ...content, stemMarkdown: '独立新草稿' } }} /></StrictMode>);
      await act(async () => gate.resolve(response(status === 200 ? { ...draft(), revision: 5 } : { code: status === 409 ? 'REVISION_CONFLICT' : 'VALIDATION_ERROR', message: 'late draft failure', details: { currentRevision: 5 } }, status)));
      expect(screen.getByLabelText('题干')).toHaveValue('独立新草稿'); expect(updated).not.toHaveBeenCalled(); expect(replaced).not.toHaveBeenCalled(); expect(reload).not.toHaveBeenCalled();
    });
    it(`formal question save ${status} after switch produces zero onChanged/onClose and preserves new preview`, async () => {
      const gate = deferred<Response>();
      const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === 'PATCH') return gate.promise;
        if (String(input).includes('/questions/')) return Promise.resolve(response(detail(String(input).includes('new-question') ? 'new-question' : 'old-question')));
        return Promise.resolve(response({ items: [], total: 0 }));
      }); vi.stubGlobal('fetch', fetchMock);
      const changed = vi.fn(); const closed = vi.fn(); const p = { questionId: 'old-question', taxonomy: buildTaxonomyIndex(null), onChanged: changed, onClose: closed };
      const ui = render(<StrictMode><QuestionDetailPanel {...p} /></StrictMode>);
      await screen.findByRole('button', { name: '编辑题目' }); fireEvent.click(screen.getByRole('button', { name: '编辑题目' }));
      fireEvent.change(screen.getByLabelText('题干'), { target: { value: 'old-write-edited' } }); fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
      ui.rerender(<StrictMode><QuestionDetailPanel {...p} questionId="new-question" /></StrictMode>);
      await screen.findByText('独立新题干');
      const oldReadsBefore = fetchMock.mock.calls.filter(([url, init]) => String(url).includes('/questions/old-question') && (!init?.method || init.method === 'GET')).length;
      await act(async () => gate.resolve(response(status === 200 ? detail('old-question', 5) : { code: status === 409 ? 'REVISION_CONFLICT' : 'VALIDATION_ERROR', message: 'late formal failure', details: { currentRevision: 5 } }, status)));
      expect(screen.getByText('独立新题干')).toBeInTheDocument(); expect(changed).not.toHaveBeenCalled(); expect(closed).not.toHaveBeenCalled();
      expect(fetchMock.mock.calls.filter(([url, init]) => String(url).includes('/questions/old-question') && (!init?.method || init.method === 'GET'))).toHaveLength(oldReadsBefore);
    });
  }
});

describe('Independent whole-batch question confirmation semantics', () => {
  const callbacks = { onResolutionChange: vi.fn(), onConfirm: vi.fn(), onOpenLibrary: vi.fn(), onReload: vi.fn() };
  it('HTTP200 + failures explicitly remains whole batch unconfirmed and contains no success count', () => {
    render(<ConfirmPanel drafts={[draft()]} submissionId="acceptance-id" busy={false} resolutions={{}} state={{ phase: 'done', result: { confirmedQuestionIds: [], linkedQuestionIds: [], skippedDraftIds: [], failures: [{ draftId: 'draft-independent', code: 'KNOWLEDGE_ARCHIVED', message: '正式知识点已归档' }] } }} {...callbacks} />);
    expect(screen.getByTestId('qb-confirm-unconfirmed')).toHaveTextContent('整批未确认'); expect(screen.queryByText(/本次已入库/)).not.toBeInTheDocument(); expect(screen.getByTestId('qb-confirm-ai-count')).toHaveTextContent('需人工确认');
  });
  it('network-lost confirmation displays outcome unknown, never claims no question was committed', () => {
    render(<ConfirmPanel drafts={[draft()]} submissionId="acceptance-id" busy={false} resolutions={{}} state={{ phase: 'failed', error: new ApiError('NETWORK_ERROR', 'commit receipt lost', 0, true) }} {...callbacks} />);
    expect(screen.getByRole('alert')).not.toHaveTextContent('没有任何题目被入库');
    expect(screen.getByRole('alert')).toHaveTextContent('结果未知');
  });
  it('UNKNOWN review confirmation replays original draft revisions and duplicate decisions instead of rebuilding changed body', async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/confirm')) { bodies.push(JSON.parse(String(init?.body))); return bodies.length === 1 ? Promise.reject(new TypeError('commit receipt lost')) : Promise.resolve(response({ confirmedQuestionIds: ['question-created'], linkedQuestionIds: [], skippedDraftIds: [], failures: [] })); }
      if (init?.method === 'PATCH') return Promise.resolve(response(draft(undefined, 5)));
      if (url.includes('/question-imports/')) return Promise.resolve(response(imported()));
      if (url.includes('/textbook-taxonomy')) return Promise.resolve(response({ stages: [], grades: [], subjects: [], editions: [] }));
      if (url.includes('/model-catalog')) return Promise.resolve(response({ profiles: [], connections: [], defaultChatProfileId: null }));
      return Promise.resolve(response({ items: [], total: 0 }));
    }));
    render(<ReviewWorkspace importId="import-independent" />);
    await screen.findByRole('button', { name: '确认入库（1 道）' }); fireEvent.click(screen.getByRole('button', { name: '确认入库（1 道）' }));
    await screen.findByText(/确认请求失败/);
    fireEvent.click(screen.getByRole('button', { name: '标记已校对' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '标记已校对' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: '确认入库（1 道）' }));
    await waitFor(() => expect(bodies).toHaveLength(2)); expect(bodies[1]).toEqual(bodies[0]);
  });
});
