// Review probes assert the observed defect, not the desired acceptance behavior.
// Run from the repository root; all data exists only in jsdom storage.
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createBook, confirmProposal, confirmSpine, deleteBook, readBooks } from '../../../apps/web/src/services/books-store';
import { getRun, getLease, startRun, stopRun, regeneratePage } from '../../../apps/web/src/services/book-generation';

const ids: string[] = [];
const key = 'zhiqikeyuan:books';

function setup() {
  const draft = createBook('review-isolated', '');
  ids.push(draft.id);
  confirmProposal(draft.id);
  return confirmSpine(draft.id)!;
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.restoreAllMocks();
  for (const id of ids.splice(0)) stopRun(id, 'review-cleanup');
  vi.clearAllTimers();
  vi.useRealTimers();
});

it('reproduces: deleting a running book leaves a registered runner and renewing lease', async () => {
  const book = setup();
  startRun(book.id, { scenario: { stageDelayMs: 5, blockDelayMs: 5 } });
  deleteBook(book.id);
  await vi.advanceTimersByTimeAsync(10);
  const initial = getLease(book.id)!.heartbeatAt;
  await vi.advanceTimersByTimeAsync(1100);
  expect(readBooks()).toEqual([]);
  expect(getRun(book.id)?.status).toBe('running');
  expect(getLease(book.id)!.heartbeatAt).toBeGreaterThan(initial);
});

it('reproduces: transient storage read denial ends the loop but retains running state', async () => {
  const book = setup();
  startRun(book.id, { scenario: { stageDelayMs: 5, blockDelayMs: 5 } });
  const original = Storage.prototype.getItem;
  const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (this: Storage, name: string) {
    if (name === key) throw new Error('review read denied');
    return original.call(this, name);
  });
  await vi.advanceTimersByTimeAsync(10);
  spy.mockRestore();
  await vi.advanceTimersByTimeAsync(1100);
  expect(getRun(book.id)?.status).toBe('running');
  expect(readBooks()[0]!.pages.every(page => page.status === 'pending')).toBe(true);
  expect(getLease(book.id)?.live).toBe(true);
});

it('reproduces: repair returns void and an old task writes under a replacement run ID', async () => {
  const book = setup();
  const pageId = book.chapters[0]!.pageIds[0]!;
  const result = regeneratePage(book.id, pageId);
  expect(result).toBeUndefined();
  const stored = JSON.parse(localStorage.getItem(key)!) as typeof book[];
  stored[0]!.run!.runId = 'replacement-run';
  localStorage.setItem(key, JSON.stringify(stored));
  await vi.advanceTimersByTimeAsync(230);
  const current = readBooks()[0]!;
  expect(current.run!.runId).toBe('replacement-run');
  expect(current.pages.find(page => page.id === pageId)!.blocks.some(block => block.status === 'ready')).toBe(true);
});
