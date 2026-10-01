import { useEffect } from 'react';
import { readFileSync } from 'node:fs';
import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, render, waitFor } from '@testing-library/react';
import { useQuestionJob, type QuestionJobController } from '@/features/question-bank/jobs';

const fixture = JSON.parse(readFileSync(
  'docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_generation_fixture.json', 'utf8',
));
let latest: QuestionJobController | null = null;

function Harness({ terminal }: { terminal: (view: unknown) => void }) {
  const job = useQuestionJob({ onTerminal: terminal, polling: { sleep: async () => {} } });
  useEffect(() => { latest = job; });
  return null;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); latest = null; });

it('actual create queued(0) -> succeeded(1) is discarded as another attempt', async () => {
  const onTerminal = vi.fn();
  const fetch = vi.fn(async () => ({ ok: true, status: 200,
                                    json: async () => fixture.terminal }) as Response);
  vi.stubGlobal('fetch', fetch);
  render(<Harness terminal={onTerminal} />);
  act(() => latest!.adopt(fixture.receipt));
  await waitFor(() => expect(latest!.observationNotice).not.toBeNull());
  expect(latest!.view?.state).toBe('queued');
  expect(latest!.view?.attempt).toBe(0);
  expect(latest!.view?.importId).toBeNull();
  expect(latest!.observing).toBe(false);
  expect(onTerminal).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fixture.terminal.result.importId).toBeTruthy();
});
