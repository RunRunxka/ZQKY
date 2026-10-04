import type { Page } from '@playwright/test';

export interface BookRecoveryOptions {
  bookId: string;
  pageId: string;
  expectedNote: string;
  /** Absolute Date.now() deadline shared with the existing completion wait. */
  deadline: number;
}

interface Observation {
  kind: 'waiting' | 'interrupted' | 'ready' | 'failed' | 'stopped';
  bookId: string;
  bookStatus: string | null;
  note: string | null;
  continueAttempts: number;
  continueClicks: number;
  atMs: number;
  reason: string | null;
}

export interface BookRecoveryResult {
  bookId: string;
  bookStatus: string | null;
  note: string | null;
  branch: 'normal' | 'recovered';
  continueAttempts: number;
  continueClicks: number;
  completedAtMs: number;
}

export interface BookRecoveryCleanup {
  bookId: string;
  continueAttempts: number;
  /** null if the page/context closed before the last browser counter could be read. */
  continueClicks: number | null;
  contextClosed: boolean;
  resourcesReleased: boolean;
  observerDisconnected: boolean;
  timerCleared: boolean;
  listenersRemoved: boolean;
  resultStatus: 'ready' | 'failed';
  failure: string | null;
  cleanupErrors: string[];
}

export interface BookRecoveryHandle {
  /** Rejects on invalid state, failed recovery, second interruption or deadline. */
  result: Promise<BookRecoveryResult>;
  /** Idempotent: stops observation, awaits the UI action/result and disposes its handle. */
  cleanup(): Promise<BookRecoveryCleanup>;
}

/** Observe alongside the original count-zero expectations; never changes stored data. */
export function startBookInterruptedRecovery(
  page: Page,
  options: BookRecoveryOptions,
): BookRecoveryHandle {
  const installed = page.evaluateHandle((target) => {
    if (!Number.isFinite(target.deadline)) throw new Error('invalid shared completion deadline');
    const key = 'zhiqikeyuan:books';
    const interruptedText = '生成已中断（无执行器在跑）';
    let attempts = 0;
    let clicks = 0;
    let offered = false;
    let armed = false;
    let resumed = false;
    let terminal: Observation | null = null;
    let request: Observation | null = null;
    let waiting: ((value: Observation) => void) | null = null;
    let observerDisconnected = false;
    let timerCleared = false;
    let listenersRemoved = false;
    const snapshot = (kind: Observation['kind'], reason: string | null = null): Observation => ({
      kind, reason, bookId: target.bookId, bookStatus: null, note: null,
      continueAttempts: attempts, continueClicks: clicks, atMs: Date.now(),
    });
    const isRecord = (value: unknown): value is Record<string, unknown> =>
      typeof value === 'object' && value !== null && !Array.isArray(value);
    const visible = (element: HTMLElement) => {
      const style = getComputedStyle(element);
      return style.visibility !== 'hidden' && style.display !== 'none' &&
        element.getClientRects().length > 0;
    };
    const inspect = (): Observation => {
      const state = snapshot('waiting');
      try {
        const raw = localStorage.getItem(key);
        if (raw === null) throw new Error('books collection missing');
        const list: unknown = JSON.parse(raw);
        if (!Array.isArray(list)) throw new Error('books collection is not an array');
        const books = list.filter((value) => isRecord(value) && value.id === target.bookId);
        if (books.length !== 1 || !isRecord(books[0])) throw new Error('target book missing or duplicated');
        const book = books[0];
        state.bookStatus = typeof book.status === 'string' ? book.status : null;
        if (!Array.isArray(book.pages)) throw new Error('target pages malformed');
        const pages = book.pages.filter((value) => isRecord(value) && value.id === target.pageId);
        if (pages.length !== 1 || !isRecord(pages[0]) || !Array.isArray(pages[0].blocks)) {
          throw new Error('target note page missing or malformed');
        }
        const notes = pages[0].blocks.filter((value) => isRecord(value) && value.type === 'user_note');
        if (notes.length !== 1 || !isRecord(notes[0]) || typeof notes[0].content !== 'string') {
          throw new Error('target note missing or malformed');
        }
        state.note = notes[0].content;
        if (state.note !== target.expectedNote) throw new Error('saved note changed');
        if (location.pathname !== `/books/${target.bookId}/pages/${target.pageId}`) {
          throw new Error('page navigated away from target book/page');
        }
        if (state.bookStatus !== 'compiling' && state.bookStatus !== 'ready') {
          throw new Error(`unacceptable book status: ${state.bookStatus}`);
        }
        const rejected = [...document.querySelectorAll('.space-banner, .book-reader-storage-error')]
          .find((element) => /无法继续生成：|恢复未保存：/.test(element.textContent ?? '') ||
            element.classList.contains('book-reader-storage-error'));
        if (rejected) throw new Error(`recovery/storage failure: ${rejected.textContent?.trim()}`);
        const strips = document.querySelectorAll<HTMLElement>('.book-pipeline-strip');
        if (strips.length > 1) throw new Error('multiple generation strips');
        if (state.bookStatus === 'ready') {
          if (strips.length === 0) state.kind = 'ready';
          return state;
        }
        if (strips.length === 0) return state; // Storage/React commit boundary, not completion.
        const strip = strips[0]!;
        const stages = strip.querySelectorAll('.book-pipeline-strip-stage');
        if (stages.length !== 1) throw new Error('generation stage missing or duplicated');
        const stage = stages[0]!.textContent?.trim();
        if (stage === '准备（大纲已就绪·模拟）…' || stage === '正在逐章编译（本地模拟，不调用模型）…') {
          if (clicks === 1) resumed = true;
          return state;
        }
        if (stage !== interruptedText) throw new Error(`unacceptable generation stage: ${stage}`);
        const buttons = [...strip.querySelectorAll<HTMLButtonElement>('button')];
        const continuing = buttons.filter((button) => button.textContent?.trim() === '继续生成');
        if (continuing.length === 1 && visible(continuing[0]!) && !continuing[0]!.disabled) {
          if (clicks === 1 && resumed) throw new Error('interrupted again after one Continue');
          state.kind = 'interrupted';
        }
        return state;
      } catch (cause) {
        state.kind = 'failed';
        state.reason = cause instanceof Error ? cause.message : String(cause);
        return state; // Delivered as a rejected result, never converted to ready.
      }
    };
    const release = () => {
      observer.disconnect();
      observerDisconnected = true;
      clearTimeout(timer);
      timerCleared = true;
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('zqky:books', check);
      document.removeEventListener('click', onClick, true);
      listenersRemoved = true;
    };
    const finish = (state: Observation) => {
      if (terminal) return terminal;
      terminal = state;
      request = null;
      release();
      waiting?.(state);
      waiting = null;
      return state;
    };
    function check() {
      if (terminal) return terminal;
      const state = inspect();
      if (state.kind === 'failed') return finish(state);
      if (Date.now() >= target.deadline) return finish({ ...state, kind: 'failed', reason: 'shared completion deadline exceeded' });
      if (state.kind === 'ready') return finish(state);
      if (state.kind === 'interrupted' && !offered && !armed) {
        offered = true;
        if (waiting) { waiting(state); waiting = null; } else request = state;
      }
      return state;
    }
    function onStorage(event: StorageEvent) {
      if (event.key === key || event.key === null) check();
    }
    function onClick(event: Event) {
      const button = event.target instanceof Element ? event.target.closest('button') : null;
      if (!button?.closest('.book-pipeline-strip') || button.textContent?.trim() !== '继续生成') return;
      clicks += 1;
      if (!armed || clicks !== 1) finish(snapshot('failed', 'unexpected or repeated UI Continue click'));
      else check();
    }
    const observer = new MutationObserver(check);
    const timer = window.setTimeout(() => {
      const state = inspect();
      finish(state.kind === 'failed' ? state : { ...state, kind: 'failed', reason: 'shared completion deadline exceeded' });
    }, Math.max(0, target.deadline - Date.now()));
    observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, characterData: true });
    window.addEventListener('storage', onStorage);
    window.addEventListener('zqky:books', check);
    document.addEventListener('click', onClick, true);
    check();
    return {
      next(): Promise<Observation> {
        if (terminal) return Promise.resolve(terminal);
        if (request) { const state = request; request = null; return Promise.resolve(state); }
        return new Promise((resolve) => { waiting = resolve; });
      },
      arm(): Observation {
        const state = check();
        if (state.kind === 'interrupted' && !armed) {
          armed = true;
          attempts += 1;
          return { ...state, continueAttempts: attempts };
        }
        if (state.kind === 'waiting') offered = false;
        return state;
      },
      stop() {
        if (!terminal) finish(snapshot('stopped', 'observation cancelled by cleanup'));
        return { continueAttempts: attempts, continueClicks: clicks, observerDisconnected, timerCleared, listenersRemoved };
      },
    };
  }, options);

  let lastObservation: Observation | null = null;
  const result = (async (): Promise<BookRecoveryResult> => {
    const observer = await installed;
    for (;;) {
      let state = await observer.evaluate((controller) => controller.next());
      lastObservation = state;
      if (state.kind === 'interrupted') {
        state = await observer.evaluate((controller) => controller.arm());
        lastObservation = state;
        if (state.kind === 'interrupted') {
          const remaining = options.deadline - Date.now();
          if (remaining <= 0) throw new Error(`book recovery deadline exceeded: ${options.bookId}`);
          await page.locator('.book-pipeline-strip')
            .getByRole('button', { name: '继续生成', exact: true })
            .click({ timeout: Math.min(remaining, 5000) });
          continue;
        }
      }
      if (state.kind === 'failed' || state.kind === 'stopped') {
        throw new Error(`book recovery failed: ${JSON.stringify(state)}`);
      }
      if (state.kind === 'ready') {
        return {
          bookId: state.bookId, bookStatus: state.bookStatus, note: state.note,
          branch: state.continueClicks === 0 ? 'normal' : 'recovered',
          continueAttempts: state.continueAttempts, continueClicks: state.continueClicks,
          completedAtMs: state.atMs,
        };
      }
    }
  })();
  let cleaning: Promise<BookRecoveryCleanup> | null = null;
  return {
    result,
    cleanup() {
      if (cleaning) return cleaning;
      cleaning = (async () => {
        const cleanupErrors: string[] = [];
        const [setup] = await Promise.allSettled([installed]);
        const contextClosed = page.isClosed();
        let released: {
          continueAttempts: number; continueClicks: number | null;
          observerDisconnected: boolean; timerCleared: boolean; listenersRemoved: boolean;
        } = {
          continueAttempts: lastObservation?.continueAttempts ?? 0,
          continueClicks: contextClosed ? null : lastObservation?.continueClicks ?? 0,
          observerDisconnected: false, timerCleared: false, listenersRemoved: false,
        };
        if (setup.status === 'fulfilled') {
          if (!contextClosed) {
            const [stopped] = await Promise.allSettled([setup.value.evaluate((controller) => controller.stop())]);
            if (stopped.status === 'fulfilled') released = stopped.value;
            else cleanupErrors.push(String(stopped.reason));
          }
        } else cleanupErrors.push(String(setup.reason));
        const [settled] = await Promise.allSettled([result]);
        if (setup.status === 'fulfilled') {
          const [disposed] = await Promise.allSettled([setup.value.dispose()]);
          if (disposed.status === 'rejected') cleanupErrors.push(String(disposed.reason));
        }
        return {
          bookId: options.bookId, ...released, contextClosed,
          resourcesReleased: (contextClosed || (released.observerDisconnected && released.timerCleared && released.listenersRemoved)) && cleanupErrors.length === 0,
          resultStatus: settled.status === 'fulfilled' ? 'ready' : 'failed',
          failure: settled.status === 'rejected' ? String(settled.reason) : null,
          cleanupErrors,
        };
      })();
      return cleaning;
    },
  };
}
