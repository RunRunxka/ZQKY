import { readFileSync } from 'node:fs';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { deriveMissingAcknowledgement, groupAbsencesByClass } from '@/features/assessments/labels';
import { ScoreImportReview } from '@/features/assessments/ScoreImportReview';

const fixture = JSON.parse(readFileSync(
  'docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_absence_fixture.json', 'utf8',
));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('real API file absence + blank remaining leaves yields a phantom missing acknowledgement', () => {
  expect(fixture.view.missingCellCount).toBe(0);
  const absences = groupAbsencesByClass(fixture.participants, fixture.rows);
  expect(absences).toHaveLength(1);
  const missing = deriveMissingAcknowledgement(fixture.participants, fixture.rows, 3, 0);
  expect(missing).toEqual({ participantIds: absences[0].participantIds, cellCount: 2 });
  expect(fixture.rejected.status).toBe(422);
  expect(fixture.rejected.body.code).toBe('SCORE_ACKNOWLEDGEMENT_MISMATCH');
  expect(fixture.accepted.status).toBe(200);
});

it('real component can only submit the phantom range; unchecking it disables confirmation', async () => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  const bodies: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const body = url.includes('/confirm')
      ? (bodies.push(JSON.parse(String(init?.body))), fixture.rejected.body)
      : { items: fixture.rows, total: fixture.rows.length, offset: 0, limit: 200 };
    return { ok: !url.includes('/confirm'), status: url.includes('/confirm') ? 422 : 200,
             json: async () => body } as Response;
  }));
  render(<ScoreImportReview view={fixture.view} reloadToken={0} leaves={fixture.leaves}
    participants={fixture.participants} assessmentRevision={fixture.assessmentRevision}
    onReload={() => {}} onReloadAssessment={() => {}} onChanged={() => {}}
    onOpenHistory={() => {}} />);
  fireEvent.click(screen.getByTestId('score-goto-acknowledge'));
  const phantomCheckbox = await screen.findByLabelText('承认空白 2 个单元覆盖 1 人次');
  fireEvent.click(screen.getByLabelText(/承认 .* 缺考 1 人次/));
  expect(screen.getByTestId('score-open-confirm')).toBeDisabled();
  fireEvent.click(phantomCheckbox);
  fireEvent.click(screen.getByTestId('score-open-confirm'));
  fireEvent.click(screen.getByTestId('score-confirm-submit'));
  await waitFor(() => expect(bodies).toHaveLength(1));
  expect(bodies[0]).toMatchObject({ missing: { cellCount: 2 } });
  await screen.findByTestId('score-ack-mismatch');
});
