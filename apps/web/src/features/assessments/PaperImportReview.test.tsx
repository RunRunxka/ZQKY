/**
 * 原卷导入校对面板（沿用归档 `PaperImportReview`，R5-FE）关键红线单测：
 *
 * - 确认是逻辑确认：结果未知时重试复用同一 `submissionId` 与原样载荷（不重复入库）；
 * - 有未保存校对时不能确认（必须先保存草稿），保存走 `expectedRevision` 乐观锁；
 * - 只呈现拆题结构：题号/分值/知识点可改，**试卷正文不渲染**（正文只随保存原样回传）；
 * - AI 知识点建议只进候选：教师显式选模型才生成，应用前不会改动原卷。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { PaperImportView } from '@/contracts/papers';
import { PaperImportReview } from './PaperImportReview';

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof stubApi>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return (
      String(url).includes(fragment) &&
      (method === undefined || (request?.method ?? 'GET').toUpperCase() === method)
    );
  });
}

const SECRET_TEXT = '这是不该渲染的题面正文';

const IMPORT: PaperImportView = {
  paper: {
    paperId: 'paper-1',
    subjectId: 'math',
    title: '七年级数学期中试卷',
    status: 'active',
    revision: 4,
    currentRevisionId: 'rev-2',
    currentState: 'draft',
    version: 2,
    totalScoreUnits: 1000,
    totalScore: '10',
    itemCount: 1,
    scoredLeafCount: 1,
    blockingIssueCount: 0,
    createdAt: '2026-10-01T00:00:00Z',
  },
  revision: {
    paperId: 'paper-1',
    paperRevisionId: 'rev-2',
    version: 2,
    state: 'draft',
    subjectId: 'math',
    title: '七年级数学期中试卷',
    totalScoreUnits: 1000,
    totalScore: '10',
    confirmedAt: null,
    createdAt: '2026-10-01T00:00:00Z',
    items: [
      {
        itemId: 'item-1',
        parentItemId: null,
        questionNo: '1',
        ordinal: 1,
        isScored: true,
        maxScoreUnits: 1000,
        maxScore: '10',
        content: {
          version: 2,
          stemBlocks: [{ id: 'b1', kind: 'paragraph', text: SECRET_TEXT }],
          optionBlocks: {},
          answerBlocks: [],
          explanationBlocks: [],
          sharedMaterials: [],
          assets: [],
        },
        sourceLocator: { paragraph: 3 },
        knowledge: [],
      },
    ],
    blocks: [
      {
        blockId: 'blk-1',
        ordinal: 1,
        kind: 'paragraph',
        locator: { paragraph: 3 },
        disposition: 'item',
        itemId: 'item-1',
        excludeReason: null,
        content: { id: 'b1', kind: 'paragraph', text: SECRET_TEXT },
      },
    ],
    issues: [],
  },
  warnings: ['扫描页 2 已是文本层。'],
};

function baseHandler(onContentPatch?: Handler): Handler {
  return (url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    if (url.includes('/model-profiles')) return jsonResponse(true, 200, []);
    if (url.includes('/knowledge-points')) {
      return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 200 });
    }
    if (url.includes('/papers/paper-1/draft') && method === 'PATCH') {
      return onContentPatch ? onContentPatch(url, init) : jsonResponse(true, 200, IMPORT.revision);
    }
    if (url.includes('/revisions/rev-2/content')) return jsonResponse(true, 200, IMPORT.revision);
    if (url.includes('/papers/paper-1')) return jsonResponse(true, 200, IMPORT.paper);
    return jsonResponse(false, 404, { code: 'NOT_FOUND', message: `未 mock：${url}` });
  };
}

function renderReview(overrides: Partial<PaperImportView> = {}) {
  return render(
    <PaperImportReview
      initial={{ ...IMPORT, ...overrides }}
      onChanged={vi.fn()}
      onClose={vi.fn()}
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('原卷校对：只给结构，不给正文', () => {
  it('渲染题号/分值/知识点字段与原文块处置，但不渲染题面正文', async () => {
    stubApi(baseHandler());
    renderReview();
    expect(screen.getByTestId('paper-import-review')).toBeInTheDocument();
    expect(screen.getByLabelText('题 1 题号')).toHaveValue('1');
    expect(screen.getByLabelText('题 1 满分')).toHaveValue('10');
    expect(screen.getByLabelText('题 1 知识点')).toBeInTheDocument();
    expect(screen.getByLabelText('原文块 1 处置')).toBeInTheDocument();
    expect(screen.getByText('结构：题面 1 块 · 选项 0 组 · 答案 0 块 · 解析 0 块（正文不在此渲染）')).toBeInTheDocument();
    expect(screen.queryByText(SECRET_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText(new RegExp(SECRET_TEXT))).not.toBeInTheDocument();
  });

  it('有未保存校对时不能确认；保存发送原样 content 与 expectedRevision', async () => {
    const fetchMock = stubApi(baseHandler());
    renderReview();
    // 无未保存改动时可以确认（草稿读回自服务端）
    expect(screen.getByTestId('paper-confirm')).not.toBeDisabled();
    expect(screen.getByTestId('paper-save-draft')).toBeDisabled();

    fireEvent.change(screen.getByLabelText('题 1 题号'), { target: { value: '1(1)' } });
    expect(screen.getByTestId('paper-save-draft')).not.toBeDisabled();
    expect(screen.getByTestId('paper-confirm')).toBeDisabled();

    fireEvent.click(screen.getByTestId('paper-save-draft'));
    await waitFor(() => expect(calls(fetchMock, '/papers/paper-1/draft', 'PATCH')).toHaveLength(1));
    const body: {
      expectedRevision: number;
      items: Array<{ questionNo: string; content: { stemBlocks: Array<{ text: string }> } }>;
    } = JSON.parse(
      String(calls(fetchMock, '/papers/paper-1/draft', 'PATCH')[0]?.[1]?.body),
    );
    expect(body.expectedRevision).toBe(4);
    expect(body.items[0].questionNo).toBe('1(1)');
    // content 原样回传（前端不改写服务端持久化内容）
    expect(body.items[0].content.stemBlocks[0].text).toBe(SECRET_TEXT);
  });

  it('保存 409：显示服务端 currentRevision 并保留本地编辑', async () => {
    stubApi((url, init) => {
      if (url.includes('/draft')) {
        return jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '版本已变化。',
          details: { currentRevision: 9 },
        });
      }
      return baseHandler()(url, init);
    });
    renderReview();
    fireEvent.change(screen.getByLabelText('题 1 题号'), { target: { value: '2' } });
    fireEvent.click(screen.getByTestId('paper-save-draft'));
    const error = await screen.findByTestId('paper-review-error');
    expect(error).toHaveTextContent('REVISION_CONFLICT');
    expect(error).toHaveTextContent('当前版本 9');
    expect(error).toHaveTextContent('编辑已保留');
    // 编辑保留在本地（题号已改为 2，标签随之变化）
    expect(screen.getByLabelText('题 2 题号')).toHaveValue('2');
  });
});

describe('原卷确认：逻辑确认冻结', () => {
  it('确认携带 submissionId；结果未知后重试复用同一 submissionId', async () => {
    let attempt = 0;
    const seen: string[] = [];
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/papers/paper-1/confirm')) {
        attempt += 1;
        seen.push(JSON.parse(String(init.body)).submissionId);
        if (attempt === 1) throw new Error('network down');
        return jsonResponse(true, 200, {
          paperId: 'paper-1',
          paperRevisionId: 'rev-2',
          state: 'confirmed',
          totalScoreUnits: 1000,
          scoredLeafCount: 1,
          replayed: false,
        });
      }
      return baseHandler()(url, init);
    });
    renderReview();
    const confirmButton = screen.getByTestId('paper-confirm');
    expect(confirmButton).not.toBeDisabled();

    fireEvent.click(confirmButton);
    await waitFor(() =>
      expect(screen.getByText(/可能已写入也可能未写入/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByTestId('paper-confirm'));
    await waitFor(() => expect(calls(fetchMock, '/confirm', 'POST')).toHaveLength(2));
    expect(seen[1]).toBe(seen[0]);
    await waitFor(() =>
      expect(screen.getByTestId('paper-confirm-result')).toHaveTextContent('已确认原卷'),
    );
  });

  it('已确认修订只读：不再提供保存/确认', () => {
    stubApi(baseHandler());
    renderReview({
      paper: { ...IMPORT.paper, currentState: 'confirmed', revision: 5 },
      revision: { ...IMPORT.revision, state: 'confirmed', confirmedAt: '2026-10-02T00:00:00Z' },
    });
    expect(screen.queryByTestId('paper-save-draft')).not.toBeInTheDocument();
    expect(screen.queryByTestId('paper-confirm')).not.toBeInTheDocument();
    expect(screen.getByText('已确认（只读）')).toBeInTheDocument();
  });

  it('AI 建议只进候选：没有显式模型时「生成关联建议」不可用', async () => {
    stubApi(baseHandler());
    renderReview();
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'AI 知识点关联建议（教师审核后应用）' })).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: '生成关联建议' })).toBeDisabled();
    expect(screen.getByLabelText('原卷建议模型')).toHaveValue('');
  });
});
