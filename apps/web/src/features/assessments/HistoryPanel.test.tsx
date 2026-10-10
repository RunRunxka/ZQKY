/**
 * F1：成绩版本的「彻底删除」入口（HistoryPanel）。
 *
 * 断言方向：
 * - 每条修订都有彻底删除按钮；二次确认取消时不发任何写请求；
 * - 成功 = 物理删除：role=status 提示 + 刷新修订列表 + 被删的正是当前展示版本时切到剩余第一个，
 *   且之后不再读取已删版本（避免矩阵/详情继续请求已删 id）；
 * - 被引用 409 → 组件内逐项列出中文原因（计数 0 不列、未知键原样保留）；非 409 原样 role=alert。
 */

import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ScoreRevisionView } from '@/contracts/scores';
import { HistoryPanel } from './HistoryPanel';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={typeof href === 'string' ? href : '#'} {...rest}>
      {children}
    </a>
  ),
}));

function response(status: number, body: unknown): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function revision(id: string, version: number): ScoreRevisionView {
  return {
    revisionId: id, assessmentId: 'as-1', paperRevisionId: 'pr-1', version, state: 'confirmed',
    sourceImportId: null, baseRevisionId: null, participantSnapshot: [], itemSnapshot: [],
    confirmedAt: '2026-10-02T00:00:00Z', createdAt: '2026-10-02T00:00:00Z',
  };
}

interface HistoryScene {
  revisions: ScoreRevisionView[];
  activeRevisionId: string | null;
  /** DELETE 的响应；成功（ok）时桩同步移除被删版本并清空生效字段（模拟真实读回）。 */
  deleteResponse: () => Response;
}

/** 历史面板的 fetch 桩：修订列表 / 施测详情 / 修订详情 / 矩阵 / DELETE。 */
function stubHistory(scene: HistoryScene) {
  const calls: { url: string; method: string }[] = [];
  const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    calls.push({ url, method });
    if (method === 'DELETE') {
      const revisionId = decodeURIComponent(url.split('/').pop() ?? '');
      const result = scene.deleteResponse();
      if (result.ok) {
        scene.revisions = scene.revisions.filter((item) => item.revisionId !== revisionId);
        if (scene.activeRevisionId === revisionId) scene.activeRevisionId = null;
      }
      return result;
    }
    const revisionPath = /\/score-revisions\/([^/?]+)/.exec(url);
    if (revisionPath) {
      const revisionId = decodeURIComponent(revisionPath[1]);
      const found = scene.revisions.find((item) => item.revisionId === revisionId) ?? null;
      if (url.includes('/matrix')) {
        return response(200, {
          revision: found ?? revision(revisionId, 0), items: [], rows: [], total: 0, offset: 0,
          limit: 50, missingCellCount: 0, missingParticipantIds: [], absentClassIds: [],
        });
      }
      return found
        ? response(200, found)
        : response(404, { code: 'SCORE_REVISION_NOT_FOUND', message: '成绩版本不存在' });
    }
    if (url.includes('/assessments/as-1/score-revisions')) {
      return response(200, { items: scene.revisions, total: scene.revisions.length });
    }
    if (url.includes('/assessments/as-1')) {
      return response(200, {
        assessment: {
          assessmentId: 'as-1', paperId: 'paper-1', paperRevisionId: 'pr-1',
          paperTitle: '一元一次方程原卷', subjectId: 'subject-1', title: '期中考试',
          assessmentType: 'exam', heldOn: '2026-10-01', activeScoreRevisionId: scene.activeRevisionId,
          state: 'open', revision: 4, classIds: ['class-1'], participantCount: 0,
          createdAt: '2026-10-01T00:00:00Z',
        },
        participants: [],
      });
    }
    return response(200, { items: [], total: 0, offset: 0, limit: 200 });
  });
  vi.stubGlobal('fetch', fetcher);
  return calls;
}

function ui() {
  return (
    <StrictMode>
      <HistoryPanel assessmentId="as-1" refreshToken={0} onChanged={() => {}} />
    </StrictMode>
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('成绩版本的彻底删除', () => {
  it('每条修订都有彻底删除按钮；二次确认取消时不发写请求', async () => {
    const confirmSpy = vi.fn(() => false);
    vi.stubGlobal('confirm', confirmSpy);
    const calls = stubHistory({
      revisions: [revision('rev-1', 1), revision('rev-2', 2)],
      activeRevisionId: 'rev-1',
      deleteResponse: () => response(200, { deleted: true, revisionId: 'rev-1', clearedActive: true, removedScores: 0, removedCorrections: 0 }),
    });
    render(ui());
    fireEvent.click(await screen.findByTestId('assessments-revision-delete-rev-1'));
    expect(screen.getByTestId('assessments-revision-delete-rev-2')).toBeInTheDocument();
    expect(confirmSpy).toHaveBeenCalledWith(
      '彻底删除成绩版本 v1？这是物理删除、不可恢复；若它是当前生效版本，删除后本施测将没有生效成绩。',
    );
    expect(calls.filter((call) => call.method === 'DELETE')).toHaveLength(0);
    expect(screen.queryByTestId('assessments-revision-delete-notice')).not.toBeInTheDocument();
  });

  it('成功删除：提示 + 刷新列表 + 展示版本切到剩余第一个且不再读取已删版本', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    const calls = stubHistory({
      revisions: [revision('rev-1', 1), revision('rev-2', 2)],
      activeRevisionId: 'rev-1',
      deleteResponse: () => response(200, { deleted: true, revisionId: 'rev-1', clearedActive: true, removedScores: 12, removedCorrections: 3 }),
    });
    render(ui());
    await waitFor(() =>
      expect(screen.getByTestId('assessments-revision-rev-1')).toHaveAttribute('aria-pressed', 'true'),
    );
    const listReads = () =>
      calls.filter((call) => call.method === 'GET' && call.url.includes('/assessments/as-1/score-revisions')).length;
    const before = listReads();
    fireEvent.click(screen.getByTestId('assessments-revision-delete-rev-1'));
    expect(await screen.findByTestId('assessments-revision-delete-notice')).toHaveTextContent(
      '已彻底删除成绩版本 v1：物理删除完成，不可恢复。',
    );
    await waitFor(() => expect(listReads()).toBeGreaterThan(before));
    expect(calls.filter((call) => call.method === 'DELETE')).toEqual([
      { url: '/api/v1/score-revisions/rev-1', method: 'DELETE' },
    ]);
    expect(screen.queryByTestId('assessments-revision-rev-1')).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId('assessments-revision-rev-2')).toHaveAttribute('aria-pressed', 'true'),
    );
    const deleteIndex = calls.findIndex((call) => call.method === 'DELETE');
    expect(
      calls.slice(deleteIndex + 1).filter(
        (call) => call.method === 'GET' && call.url.includes('/score-revisions/rev-1'),
      ),
    ).toHaveLength(0);
  });

  it('409 引用守卫逐项列中文原因（0 不列、未知键不隐藏），版本保留在列表', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    stubHistory({
      revisions: [revision('rev-1', 1), revision('rev-2', 2)],
      activeRevisionId: 'rev-2',
      deleteResponse: () => response(409, {
        code: 'SCORE_REVISION_IN_USE',
        message: '仍有下游数据引用该成绩版本',
        details: { counts: { analysisRuns: 2, dependentRevisions: 1, importBatches: 0, unexpectedRef: 3 } },
      }),
    });
    render(ui());
    fireEvent.click(await screen.findByTestId('assessments-revision-delete-rev-1'));
    const guard = await screen.findByTestId('assessments-revision-delete-guard');
    expect(guard).toHaveTextContent('不能彻底删除「v1」');
    expect(guard).toHaveTextContent('SCORE_REVISION_IN_USE');
    expect(guard).toHaveTextContent('仍有下游数据引用该成绩版本');
    expect(guard).toHaveTextContent('学情报告 2 条');
    expect(guard).toHaveTextContent('基于它的更新成绩版本 1 条');
    expect(guard).toHaveTextContent('unexpectedRef 3 条');
    expect(guard).not.toHaveTextContent('基于它的导入批次');
    expect(screen.getByTestId('assessments-revision-rev-1')).toBeInTheDocument();
    expect(screen.queryByTestId('assessments-revision-delete-notice')).not.toBeInTheDocument();
  });

  it('非 409 失败原样显示 code 与 message（不当作引用问题）', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    stubHistory({
      revisions: [revision('rev-1', 1)],
      activeRevisionId: 'rev-1',
      deleteResponse: () => response(404, { code: 'SCORE_REVISION_NOT_FOUND', message: '成绩版本不存在' }),
    });
    render(ui());
    fireEvent.click(await screen.findByTestId('assessments-revision-delete-rev-1'));
    expect(await screen.findByTestId('assessments-revision-delete-error')).toHaveTextContent(
      '彻底删除成绩版本失败（SCORE_REVISION_NOT_FOUND）：成绩版本不存在',
    );
    expect(screen.queryByTestId('assessments-revision-delete-guard')).not.toBeInTheDocument();
    expect(screen.getByTestId('assessments-revision-rev-1')).toBeInTheDocument();
  });
});
