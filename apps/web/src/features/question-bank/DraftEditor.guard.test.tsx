import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type { DraftView, QuestionImportDetail } from '@/contracts/question-bank';
import { DraftEditor } from './DraftEditor';
import { buildTaxonomyIndex } from './taxonomy';

const taxonomy = buildTaxonomyIndex({ stages: [], grades: [], subjects: [], editions: [] });
function draft(draftId = 'd-1'): DraftView {
  return {
    draftId,
    importId: 'imp-1',
    revision: 1,
    content: {
      type: 'short_answer',
      stemMarkdown: draftId,
      options: [],
      answer: { choiceKeys: [], accepted: null, textMarkdown: '3' },
      explanationMarkdown: null,
      assetIds: [],
    },
    metadata: {
      stageId: '',
      gradeId: '',
      subjectId: 'math',
      editionId: '',
      difficulty: 'easy',
      knowledgeTags: [],
    },
    sourceSpans: [],
    extractionMethod: 'rule',
    reviewState: 'needs_review',
    missingAnswerAcknowledged: false,
    warnings: [],
    duplicateOfQuestionId: null,
  };
}
function json(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function stubWrite(handler: (url: string, init: RequestInit) => Promise<Response>) {
  return vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init: RequestInit = {}) =>
      url.includes('/knowledge-points')
        ? Promise.resolve(json(200, { items: [], total: 0, offset: 0, limit: 200 }))
        : handler(url, init),
    ),
  );
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('草稿写入的对象与卸载守卫', () => {
  for (const operation of ['save', 'split'] as const) {
    for (const status of [200, 409]) {
      for (const boundary of ['switch', 'unmount'] as const) {
        it(`${operation} ${status} 迟到响应在 ${boundary} 后没有父级副作用`, async () => {
          const pending = deferred<Response>();
          stubWrite(() => pending.promise);
          const onDraftUpdated = vi.fn();
          const onDetailReplaced = vi.fn();
          const onReloadDraft = vi.fn(async () => draft());
          const props = {
            importId: 'imp-1',
            draft: draft(),
            taxonomy,
            onDraftUpdated,
            onDetailReplaced,
            onReloadDraft,
          };
          const view = render(<DraftEditor {...props} />);
          if (operation === 'split') {
            fireEvent.change(screen.getByLabelText('拆分位置（字符偏移）'), {
              target: { value: '12' },
            });
            fireEvent.click(screen.getByRole('button', { name: '拆分' }));
          } else fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
          if (boundary === 'switch') {
            view.rerender(<DraftEditor {...props} draft={draft('d-2')} />);
            fireEvent.change(screen.getByLabelText('题干'), { target: { value: '新草稿编辑' } });
          } else view.unmount();
          await act(async () =>
            pending.resolve(
              status === 409
                ? json(409, { code: 'REVISION_CONFLICT', message: '旧响应', retryable: false })
                : json(
                    200,
                    operation === 'save'
                      ? { ...draft(), revision: 2 }
                      : { importId: 'imp-1', drafts: [] },
                  ),
            ),
          );
          expect(onDraftUpdated).not.toHaveBeenCalled();
          expect(onDetailReplaced).not.toHaveBeenCalled();
          expect(onReloadDraft).not.toHaveBeenCalled();
          if (boundary === 'switch') {
            expect(screen.getByLabelText('题干')).toHaveValue('新草稿编辑');
            expect(screen.queryByText(/旧响应/)).not.toBeInTheDocument();
            expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled();
          }
        });
      }
    }
    it(`${operation} 的冲突读回也随草稿切换失效`, async () => {
      stubWrite(async () =>
        json(409, { code: 'REVISION_CONFLICT', message: '冲突', retryable: false }),
      );
      const readback = deferred<DraftView | null>();
      let isCurrent: (() => boolean) | undefined;
      const onReloadDraft = vi.fn((_id: string, guard?: () => boolean) => {
        isCurrent = guard;
        return readback.promise;
      });
      const props = {
        importId: 'imp-1',
        draft: draft(),
        taxonomy,
        onDraftUpdated: vi.fn(),
        onDetailReplaced: vi.fn(),
        onReloadDraft,
      };
      const view = render(<DraftEditor {...props} />);
      if (operation === 'split') {
        fireEvent.change(screen.getByLabelText('拆分位置（字符偏移）'), {
          target: { value: '12' },
        });
        fireEvent.click(screen.getByRole('button', { name: '拆分' }));
      } else fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
      await waitFor(() => expect(onReloadDraft).toHaveBeenCalledOnce());
      expect(isCurrent?.()).toBe(true);
      view.rerender(<DraftEditor {...props} draft={draft('d-2')} />);
      expect(isCurrent?.()).toBe(false);
      await act(async () => readback.resolve({ ...draft(), revision: 9 }));
      expect(screen.queryByText('修订 r9')).not.toBeInTheDocument();
      expect(screen.getByLabelText('题干')).toHaveValue('d-2');
    });
  }
  it('当前对象保存和拆分成功仍回调权威响应', async () => {
    const updated = { ...draft(), revision: 2 };
    const detail = { importId: 'imp-1', drafts: [draft('new-draft')] } as QuestionImportDetail;
    stubWrite(async (_url: string, init: RequestInit) =>
      json(200, init.method === 'PATCH' ? updated : detail),
    );
    const onDraftUpdated = vi.fn();
    const onDetailReplaced = vi.fn();
    render(
      <DraftEditor
        importId="imp-1"
        draft={draft()}
        taxonomy={taxonomy}
        onDraftUpdated={onDraftUpdated}
        onDetailReplaced={onDetailReplaced}
        onReloadDraft={async () => null}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    await waitFor(() => expect(onDraftUpdated).toHaveBeenCalledWith(updated));
    fireEvent.change(screen.getByLabelText('拆分位置（字符偏移）'), { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: '拆分' }));
    await waitFor(() => expect(onDetailReplaced).toHaveBeenCalledWith(detail));
  });
  it('富题面通过单一预览读取草稿资产，修订变化重新读取并撤销旧 URL', async () => {
    const source = draft();
    source.content.richContent = {
      version: 2,
      sharedMaterials: [],
      stemBlocks: [
        { id: 'p', kind: 'paragraph', text: '富题面权威文本' },
        { id: 'image', kind: 'image', assetId: 'asset-1', width: 0, height: 0 },
      ],
      optionBlocks: {},
      answerBlocks: [],
      explanationBlocks: [],
      assets: [],
      origin: { originalAssetId: 'original', originalSha256: 'a'.repeat(64), sourceLocator: {} },
    };
    const createObjectURL = vi
      .fn()
      .mockReturnValueOnce('blob:first')
      .mockReturnValueOnce('blob:second');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL, revokeObjectURL }));
    const fetch = vi.fn(async (url: RequestInfo | URL) =>
      String(url).includes('/knowledge-points')
        ? json(200, { items: [], total: 0, offset: 0, limit: 200 })
        : ({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'image/png' }),
            blob: async () => new Blob(['bytes'], { type: 'image/png' }),
          } as Response),
    );
    vi.stubGlobal('fetch', fetch);
    const props = {
      importId: 'imp-1',
      draft: source,
      taxonomy,
      onDraftUpdated: vi.fn(),
      onDetailReplaced: vi.fn(),
      onReloadDraft: async () => null,
    };
    const view = render(<DraftEditor {...props} />);
    const preview = screen.getByRole('region', { name: '草稿内容预览' });
    expect(within(preview).getByText('富题面权威文本')).toBeInTheDocument();
    await waitFor(() =>
      expect(within(preview).getByRole('img')).toHaveAttribute('src', 'blob:first'),
    );
    expect(
      fetch.mock.calls.some(
        ([url]) => url === '/api/v1/question-drafts/d-1/assets/asset-1/content',
      ),
    ).toBe(true);
    view.rerender(<DraftEditor {...props} draft={{ ...source, revision: 2 }} />);
    await waitFor(() =>
      expect(within(preview).getByRole('img')).toHaveAttribute('src', 'blob:second'),
    );
    expect(fetch.mock.calls.filter(([url]) => String(url).includes('/assets/'))).toHaveLength(2);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:first');
  });
});
