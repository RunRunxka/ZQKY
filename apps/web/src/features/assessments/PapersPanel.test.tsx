import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { PaperView } from '@/contracts/papers';
import { PapersPanel } from './PapersPanel';

function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function paper(overrides: Partial<PaperView> = {}): PaperView {
  return {
    paperId: 'paper-active',
    subjectId: 'subject-1',
    title: '期中卷',
    status: 'active',
    revision: 2,
    currentRevisionId: 'rev-active',
    currentState: 'confirmed',
    version: 1,
    totalScoreUnits: 10000,
    totalScore: '100',
    itemCount: 3,
    scoredLeafCount: 2,
    blockingIssueCount: 0,
    createdAt: '2026-10-01T00:00:00Z',
    ...overrides,
  };
}

const ARCHIVED_PAPER = paper({
  paperId: 'paper-old',
  title: '旧月考卷',
  status: 'archived',
  revision: 4,
  currentRevisionId: 'rev-old',
});

const TAXONOMY = { stages: [], grades: [], subjects: [], editions: [] };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('原卷归档、恢复与已归档筛选', () => {
  it('默认只取活跃原卷；开关显示已归档且不能选用，恢复用自己的 revision', async () => {
    const writes: { url: string; body: unknown }[] = [];
    const reads: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = String(input);
      const init = request ?? {};
      if (init.method === 'POST') {
        writes.push({ url, body: JSON.parse(String(init.body)) });
        if (url.endsWith('/papers/paper-active/archive')) {
          return response(200, paper({ status: 'archived', revision: 3 }));
        }
        return response(200, paper({ paperId: 'paper-old', status: 'active', revision: 5 }));
      }
      if (url.includes('/papers?')) {
        reads.push(url);
        const items = url.includes('status=active') ? [paper()] : [paper(), ARCHIVED_PAPER];
        return response(200, { items, total: items.length, offset: 0, limit: 100 });
      }
      if (url.endsWith('/textbook-taxonomy')) return response(200, TAXONOMY);
      return response(500, { code: 'UNEXPECTED_REQUEST', message: url });
    });
    vi.stubGlobal('fetch', fetchMock);
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    render(
      <StrictMode>
        <PapersPanel selected={null} onSelect={vi.fn()} refreshToken={0} />
      </StrictMode>,
    );
    await screen.findByTestId('assessments-paper-paper-active');
    expect(reads[0]).toContain('status=active');
    expect(screen.queryByTestId('assessments-paper-paper-old')).not.toBeInTheDocument();
    expect(screen.getByTestId('assessments-select-paper-paper-active')).toBeEnabled();

    const before = reads.length;
    fireEvent.click(screen.getByTestId('assessments-paper-archive-paper-active'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(writes[0]).toEqual({
      url: '/api/v1/papers/paper-active/archive',
      body: { expectedRevision: 2 },
    });
    await waitFor(() => expect(reads.length).toBeGreaterThan(before));
    expect(reads.at(-1)).toContain('status=active');

    fireEvent.click(screen.getByLabelText('显示已归档原卷'));
    await screen.findByTestId('assessments-paper-paper-old');
    expect(reads.at(-1)).not.toContain('status=active');
    expect(screen.getByTestId('assessments-paper-archived-paper-old')).toHaveTextContent('已归档');
    expect(screen.getByTestId('assessments-select-paper-paper-old')).toBeDisabled();

    fireEvent.click(screen.getByTestId('assessments-paper-restore-paper-old'));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]).toEqual({
      url: '/api/v1/papers/paper-old/restore',
      body: { expectedRevision: 4 },
    });
  });

  it('取消确认不发请求；归档失败在错误区显示服务端 message', async () => {
    const writes: string[] = [];
    const confirmSpy = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);
    vi.stubGlobal('confirm', confirmSpy);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = String(input);
      const init = request ?? {};
      if (init.method === 'POST') {
        writes.push(url);
        return response(409, { code: 'REVISION_CONFLICT', message: '原卷版本已变' });
      }
      if (url.includes('/papers?')) {
        return response(200, { items: [paper()], total: 1, offset: 0, limit: 100 });
      }
      if (url.endsWith('/textbook-taxonomy')) return response(200, TAXONOMY);
      return response(500, { code: 'UNEXPECTED_REQUEST', message: url });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<PapersPanel selected={null} onSelect={vi.fn()} refreshToken={0} />);
    await screen.findByTestId('assessments-paper-archive-paper-active');
    fireEvent.click(screen.getByTestId('assessments-paper-archive-paper-active'));
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByTestId('assessments-paper-archive-paper-active'));
    expect(await screen.findByTestId('assessments-paper-write-error')).toHaveTextContent(
      '原卷版本已变',
    );
    expect(writes).toHaveLength(1);
    expect(screen.getByTestId('assessments-paper-paper-active')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ 原卷彻底删除（受引用守卫） */

function selectedPaper() {
  return {
    paperId: 'paper-active',
    paperRevisionId: 'rev-active',
    title: '期中卷',
    version: 1,
    totalScoreUnits: 10000,
    scoredLeafCount: 2,
  };
}

describe('原卷彻底删除（受引用守卫的三态）', () => {
  it('删除成功：DELETE 带列表 revision，被删原卷消失并清空选用；修订号只留小字', async () => {
    const writes: { url: string; method: string }[] = [];
    let alive = true;
    vi.stubGlobal('confirm', vi.fn(() => true));
    const select = vi.fn();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = String(input);
      const init = request ?? {};
      if (init.method === 'DELETE' && url.includes('/papers/paper-active')) {
        writes.push({ url, method: 'DELETE' });
        alive = false;
        return response(200, { deleted: true, paperId: 'paper-active' });
      }
      if (url.includes('/papers?')) {
        return response(200, { items: alive ? [paper()] : [], total: alive ? 1 : 0, offset: 0, limit: 100 });
      }
      if (url.endsWith('/textbook-taxonomy')) return response(200, TAXONOMY);
      return response(500, { code: 'UNEXPECTED_REQUEST', message: url });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<PapersPanel selected={selectedPaper()} onSelect={select} refreshToken={0} />);
    await screen.findByTestId('assessments-paper-paper-active');
    // 列表项不再展示 revisionId 主文本，只留小字（完整值在 title）
    const revisionMeta = screen.getByTestId('assessments-paper-revision-paper-active');
    expect(revisionMeta).toHaveTextContent('修订号 rev-acti…');
    expect(revisionMeta).toHaveAttribute('title', 'rev-active');

    fireEvent.click(screen.getByTestId('assessments-paper-delete-paper-active'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].url).toBe('/api/v1/papers/paper-active?expectedRevision=2');
    expect(await screen.findByTestId('assessments-paper-delete-notice')).toHaveTextContent('已彻底删除原卷「期中卷」');
    expect(select).toHaveBeenCalledWith(null);
    await waitFor(() => expect(screen.queryByTestId('assessments-paper-paper-active')).not.toBeInTheDocument());
  });

  it('PAPER_IN_USE 409：逐项列出引用计数，「改为归档」走归档端点', async () => {
    const message = '该原卷已被施测引用，不能删除；归档原卷是安全的替代做法。';
    const writes: { url: string; body: unknown }[] = [];
    vi.stubGlobal('confirm', vi.fn(() => true));
    const fetchMock = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = String(input);
      const init = request ?? {};
      if (init.method === 'DELETE' && url.includes('/papers/paper-active')) {
        return response(409, {
          code: 'PAPER_IN_USE',
          message,
          details: { counts: { assessments: 3 } },
        });
      }
      if (init.method === 'POST' && url.endsWith('/papers/paper-active/archive')) {
        writes.push({ url, body: JSON.parse(String(init.body)) });
        return response(200, paper({ status: 'archived', revision: 3 }));
      }
      if (url.includes('/papers?')) {
        return response(200, { items: [paper()], total: 1, offset: 0, limit: 100 });
      }
      if (url.endsWith('/textbook-taxonomy')) return response(200, TAXONOMY);
      return response(500, { code: 'UNEXPECTED_REQUEST', message: url });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<PapersPanel selected={null} onSelect={vi.fn()} refreshToken={0} />);
    fireEvent.click(await screen.findByTestId('assessments-paper-delete-paper-active'));
    const guard = await screen.findByTestId('assessments-paper-delete-guard');
    expect(guard).toHaveTextContent(message);
    expect(guard).toHaveTextContent('引用施测 3 条');
    expect(screen.getByTestId('assessments-paper-paper-active')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('assessments-paper-delete-guard-archive'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toEqual({
      url: '/api/v1/papers/paper-active/archive',
      body: { expectedRevision: 2 },
    });
  });

  it('PAPER_HAS_CONFIRMED_REVISION 409：说明已确认修订只能归档', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    const fetchMock = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
      const url = String(input);
      const init = request ?? {};
      if (init.method === 'DELETE') {
        return response(409, {
          code: 'PAPER_HAS_CONFIRMED_REVISION',
          message: '该原卷存在已确认修订，不能删除（已确认原卷只能归档）。',
          details: { counts: { confirmedRevisions: 2 } },
        });
      }
      if (url.includes('/papers?')) {
        return response(200, { items: [paper()], total: 1, offset: 0, limit: 100 });
      }
      if (url.endsWith('/textbook-taxonomy')) return response(200, TAXONOMY);
      return response(500, { code: 'UNEXPECTED_REQUEST', message: url });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<PapersPanel selected={null} onSelect={vi.fn()} refreshToken={0} />);
    fireEvent.click(await screen.findByTestId('assessments-paper-delete-paper-active'));
    const guard = await screen.findByTestId('assessments-paper-delete-guard');
    expect(guard).toHaveTextContent('PAPER_HAS_CONFIRMED_REVISION');
    expect(guard).toHaveTextContent('已确认修订（已确认原卷只能归档） 2 条');
    expect(guard).toHaveTextContent('改为归档');
  });
});
