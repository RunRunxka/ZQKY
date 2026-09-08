import type { DraftEnvelope, DraftRepository } from '../model/types';
/** Serializes asynchronous saves. A failed write remains pending for retry. */
export function createDraftWriter(
  repository: DraftRepository,
  onSaved: (draft: DraftEnvelope) => void,
  onError: (error: unknown) => void,
) {
  let pending: DraftEnvelope | undefined;
  let running: Promise<void> | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  function enqueue(draft: DraftEnvelope) {
    pending = draft;
    clearTimeout(timer);
    timer = setTimeout(() => {
      void flush().catch(() => {});
    }, 600);
  }
  function flush(): Promise<void> {
    clearTimeout(timer);
    if (running) return running.then(() => flush());
    if (!pending) return Promise.resolve();
    const current = pending;
    pending = undefined;
    let result: void | Promise<void>;
    try {
      result = repository.save(current);
    } catch (error) {
      pending ??= current;
      onError(error);
      return Promise.reject(error);
    }
    if (!result) {
      onSaved(current);
      return pending ? flush() : Promise.resolve();
    }
    running = Promise.resolve(result)
      .then(
        () => {
          onSaved(current);
        },
        (error) => {
          pending ??= current;
          onError(error);
          throw error;
        },
      )
      .finally(() => {
        running = undefined;
      });
    return running.then(() => flush());
  }
  return { enqueue, flush, isPending: () => !!pending || !!running };
}
