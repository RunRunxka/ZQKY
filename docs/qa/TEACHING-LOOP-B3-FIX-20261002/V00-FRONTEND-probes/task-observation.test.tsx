import { StrictMode, useEffect } from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useKnowledgeJob } from '@/features/knowledge-points/hooks';
import { useQuestionJob } from '@/features/question-bank/jobs';
import { useObservedJob } from '@/services/use-workflow-job';
import type { JobView } from '@/contracts/teaching-loop';

// Independent fault scenarios: actual hooks, observer and clients; only HTTP fetch is replaced.
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
type Domain = 'knowledge' | 'question' | 'teaching';
type Task = ReturnType<typeof useKnowledgeJob> | ReturnType<typeof useQuestionJob> | ReturnType<typeof useObservedJob>;
let task: Task;
function snapshot(domain: Domain, jobId: string, state: JobView['state'], attempt: number): JobView {
  return { domain, kind: domain === 'question' ? 'generate' : 'suggest', jobId, state, attempt,
    result: state === 'succeeded' ? { importId: 'candidate-acceptance', candidateCount: 3 } : null,
    error: state === 'failed' ? { code: 'INDEPENDENT_PROVIDER_FAIL', message: '受控失败' } : null };
}
function TaskHarness({ domain, terminal }: { domain: Domain; terminal: (view: unknown) => void }) {
  const knowledge = useKnowledgeJob({ onTerminal: terminal, polling: { sleep: async () => undefined } });
  const question = useQuestionJob({ onTerminal: terminal, polling: { sleep: async () => undefined } });
  const teaching = useObservedJob('teaching', { onTerminal: terminal, polling: { sleep: async () => undefined } });
  const selected = domain === 'knowledge' ? knowledge : domain === 'question' ? question : teaching;
  useEffect(() => { task = selected; });
  return <output data-testid="observed-state">{selected.view ? `${selected.view.jobId}/${selected.view.state}/${selected.view.attempt}` : 'none'}|{selected.pending ?? 'idle'}|{selected.actionError?.code ?? 'clean'}|{selected.observationNotice ?? 'no-notice'}</output>;
}
function adopt(domain: Domain, jobId: string, state: JobView['state'], attempt: number) {
  const base = snapshot(domain, jobId, state, attempt);
  if (domain === 'question') (task as ReturnType<typeof useQuestionJob>).adopt({ jobId, state, attempt,
    importId: state === 'succeeded' ? 'candidate-acceptance' : null, candidateCount: state === 'succeeded' ? 3 : 0, errorCode: null });
  else (task as ReturnType<typeof useKnowledgeJob>).adopt(base);
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Independent StrictMode and stale explicit operations', () => {
  for (const domain of ['knowledge', 'question', 'teaching'] as const) {
    it(`${domain}: StrictMode synchronous terminal receipt is displayed and delivered exactly once`, async () => {
      const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
      const terminal = vi.fn();
      render(<StrictMode><TaskHarness domain={domain} terminal={terminal} /></StrictMode>);
      act(() => adopt(domain, 'strict-owned', 'succeeded', 4));
      await waitFor(() => expect(screen.getByTestId('observed-state')).toHaveTextContent('strict-owned/succeeded/4'));
      expect(terminal).toHaveBeenCalledTimes(1);
      expect(fetchMock).not.toHaveBeenCalled();
    });
    for (const action of ['retry', 'cancel'] as const) {
      for (const outcome of ['success', 'failure'] as const) {
        for (const invalidate of ['reset', 'switch', 'unmount'] as const) {
          it(`${domain}: ${action} late ${outcome} after ${invalidate} produces no old callback/state/error`, async () => {
            const request = deferred<Response>();
            const oldObservation = deferred<Response>();
            const terminal = vi.fn();
            const fetchMock = vi.fn((input: RequestInfo | URL) => String(input).includes(`/old-owned/${action}`)
              ? request.promise : oldObservation.promise);
            vi.stubGlobal('fetch', fetchMock);
            const ui = render(<StrictMode><TaskHarness domain={domain} terminal={terminal} /></StrictMode>);
            act(() => adopt(domain, 'old-owned', action === 'retry' ? 'failed' : 'running', 6));
            terminal.mockClear();
            act(() => { task[action](); task[action](); });
            expect(fetchMock.mock.calls.filter(([url]) => String(url).includes(`/${action}`))).toHaveLength(1);
            await waitFor(() => expect(screen.getByTestId('observed-state')).toHaveTextContent(`|${action}|`));
            if (invalidate === 'unmount') ui.unmount();
            else act(() => { task.reset(); if (invalidate === 'switch') adopt(domain, 'new-owned', 'queued', 9); });
            const stateBefore = task.view;
            const pendingBefore = task.pending;
            await act(async () => request.resolve(outcome === 'success'
              ? response(snapshot(domain, 'old-owned', action === 'retry' ? 'queued' : 'cancelled', 6))
              : response({ code: 'REVISION_CONFLICT', message: 'old failed', retryable: false }, 409)));
            expect(task.view).toBe(stateBefore);
            expect(task.pending).toBe(pendingBefore);
            expect(task.actionError).toBeNull();
            expect(terminal).not.toHaveBeenCalled();
            if (invalidate !== 'unmount') expect(screen.getByTestId('observed-state')).toHaveTextContent(invalidate === 'switch' ? 'new-owned/queued/9' : 'none');
          });
        }
      }
    }
  }
});

describe('Independent real protocol windows and commit barrier', () => {
  it('knowledge AI candidate initial queued(0) accepts first claimed terminal(1), matching common JobEngine protocol', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response(snapshot('knowledge', 'knowledge-first-owned', 'succeeded', 1)))));
    const terminal = vi.fn(); render(<TaskHarness domain="knowledge" terminal={terminal} />);
    act(() => adopt('knowledge', 'knowledge-first-owned', 'queued', 0));
    await waitFor(() => expect(screen.getByTestId('observed-state')).toHaveTextContent('knowledge-first-owned/succeeded/1'));
    expect(terminal).toHaveBeenCalledTimes(1); expect(task.observationNotice).toBeNull();
  });
  for (const domain of ['knowledge', 'question', 'teaching'] as const) {
    for (const state of ['succeeded', 'failed', 'cancelled', 'interrupted'] as const) {
      it(`${domain}: queued(0) accepts first terminal(${state},1), callback and committed UI agree`, async () => {
        let reads = 0;
        vi.stubGlobal('fetch', vi.fn(() => {
          reads += 1;
          return Promise.resolve(response(snapshot(domain, 'first-owned', reads === 1 ? 'running' : state, 1)));
        }));
        const terminal = vi.fn();
        render(<StrictMode><TaskHarness domain={domain} terminal={terminal} /></StrictMode>);
        act(() => adopt(domain, 'first-owned', 'queued', 0));
        // Callback can fire before React commit; rendered terminal is the independent commit barrier.
        await waitFor(() => expect(screen.getByTestId('observed-state')).toHaveTextContent(`first-owned/${state}/1`));
        expect(terminal).toHaveBeenCalledTimes(1);
        expect(task.view?.state).toBe(state); expect(task.view?.attempt).toBe(1);
        expect(task.observing).toBe(false); expect(task.observationNotice).toBeNull();
        expect(reads).toBe(2);
      });
    }
    it(`${domain}: first queued(0) refuses takeover terminal(2) and exposes no candidate`, async () => {
      vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(response(snapshot(domain, 'first-owned', 'succeeded', 2)))));
      const terminal = vi.fn();
      render(<TaskHarness domain={domain} terminal={terminal} />);
      act(() => adopt(domain, 'first-owned', 'queued', 0));
      await waitFor(() => expect(screen.getByTestId('observed-state')).toHaveTextContent('接管'));
      expect(task.view?.state).toBe('queued'); expect(task.view?.attempt).toBe(0);
      expect(task.observing).toBe(false); expect(terminal).not.toHaveBeenCalled();
    });
  }
});
