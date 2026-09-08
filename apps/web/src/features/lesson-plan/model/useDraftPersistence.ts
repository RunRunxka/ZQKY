'use client';
import { useEffect, useRef, useState, useCallback } from 'react';
import type { StoreApi } from 'zustand/vanilla';
import type { LessonState } from './store';
import type { DraftEnvelope, DraftRepository } from './types';
import { makeEnvelope } from '../services/drafts';
import { createDraftWriter } from '../services/autosave';
export function useDraftPersistence(
  store: StoreApi<LessonState>,
  repository: DraftRepository,
  notice: (message: string) => void,
  onChange?: (draft: DraftEnvelope) => void,
) {
  const [ready, setReady] = useState(false),
    [saveStatus, setSaveStatus] = useState('正在恢复草稿…'),
    [storageBlocked, setStorageBlocked] = useState(false);
  const writerRef = useRef<ReturnType<typeof createDraftWriter> | null>(null);
  const blockedRef = useRef(false);
  useEffect(() => {
    let disposed = false;
    let unsubscribe: (() => void) | undefined;
    const writer = createDraftWriter(
      repository,
      (draft) => {
        if (!disposed && store.getState().revision === draft.revision)
          setSaveStatus('已保存到本机');
        try {
          onChange?.(draft);
        } catch {
          if (!disposed) notice('草稿已保存，但主项目同步失败');
        }
      },
      () => {
        if (!disposed) {
          setSaveStatus('保存失败');
          notice('保存失败，请导出 JSON 备份后重试。');
        }
      },
    );
    writerRef.current = writer;
    void (async () => {
      try {
        const draft = await repository.load();
        if (disposed) return;
        if (draft) store.getState().hydrate(draft.data, draft.revision);
        setSaveStatus(draft ? '草稿已恢复' : '本地示例');
      } catch (error) {
        if (disposed) return;
        blockedRef.current = true;
        setStorageBlocked(true);
        setSaveStatus('草稿读取失败');
        notice(`${(error as Error).message}。原草稿未覆盖。`);
      }
      if (disposed) return;
      setReady(true);
      unsubscribe = store.subscribe((next, previous) => {
        if (next.data === previous.data || blockedRef.current) return;
        setSaveStatus('保存中…');
        writer.enqueue(makeEnvelope(next.data, next.revision));
      });
    })();
    const leave = (e: BeforeUnloadEvent) => {
      void writer.flush().catch(() => {});
      if (writer.isPending()) {
        e.preventDefault();
      }
    };
    const hide = () => {
      void writer.flush().catch(() => {});
    };
    window.addEventListener('beforeunload', leave);
    window.addEventListener('pagehide', hide);
    return () => {
      disposed = true;
      unsubscribe?.();
      window.removeEventListener('beforeunload', leave);
      window.removeEventListener('pagehide', hide);
      void writer.flush().catch(() => {});
      if (writerRef.current === writer) writerRef.current = null;
    };
  }, [store, repository, notice, onChange]);
  const flushDraft = useCallback(() => writerRef.current?.flush() ?? Promise.resolve(), []);
  const resumeStorage = useCallback(() => {
    blockedRef.current = false;
    setStorageBlocked(false);
    const s = store.getState();
    setSaveStatus('保存中…');
    writerRef.current?.enqueue(makeEnvelope(s.data, s.revision));
  }, [store]);
  return { ready, saveStatus, storageBlocked, resumeStorage, flushDraft };
}
