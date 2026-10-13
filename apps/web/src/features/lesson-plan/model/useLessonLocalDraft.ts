/**
 * 本地草稿持久化（R7-FE，沿用归档 autosave 语义：600ms 防抖、串行写入、失败保留待写版本）。
 *
 * - 键与 `schemaVersion` 兼容归档（`zhiqikeyuan:lesson-plan:v1`）；
 * - **坏草稿不覆盖**：读取失败时 `status.error` 置位并彻底停止自动写入，由界面给出处置入口；
 * - `flush()` 供路由离开、页面隐藏前调用；失败不抛给调用方（界面已有状态）。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from 'zustand';
import type { StoreApi } from 'zustand/vanilla';
import type { LessonWorkbenchState } from './store';
import {
  LOCAL_DRAFT_ERROR_MESSAGE,
  clearLocalDraft,
  readLocalDraft,
  writeLocalDraft,
  safeBrowserStorage,
} from './draft-storage';

const SAVE_DEBOUNCE_MS = 600;

export interface LocalDraftStatus {
  ready: boolean;
  /** 非空时表示本地草稿损坏/不可读：自动保存已暂停，界面必须显示该原因。 */
  error: string | null;
  savedAt: string | null;
  saving: boolean;
}

export function useLessonLocalDraft(store: StoreApi<LessonWorkbenchState>) {
  const [status, setStatus] = useState<LocalDraftStatus>({
    ready: false,
    error: null,
    savedAt: null,
    saving: false,
  });
  const storage = useMemo(safeBrowserStorage, []);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef(false);
  const blocked = useRef(false);

  const snapshot = useCallback(() => {
    const state = store.getState();
    return {
      data: state.data,
      modules: state.modules,
      removed: state.removed,
      style: state.style,
      revision: state.revision,
      updatedAt: new Date().toISOString(),
    };
  }, [store]);

  const writeNow = useCallback(
    (markSaving: boolean) => {
      if (!storage || blocked.current) return;
      if (markSaving) setStatus((current) => ({ ...current, saving: true }));
      try {
        const draft = snapshot();
        writeLocalDraft(storage, draft);
        pending.current = false;
        setStatus((current) => ({ ...current, saving: false, savedAt: draft.updatedAt }));
      } catch (error) {
        // 写入失败（配额/隐私模式）：保留待写状态，如实显示错误；不清空本地原稿。
        setStatus((current) => ({
          ...current,
          saving: false,
          error: error instanceof Error ? `本地草稿保存失败：${error.message}` : '本地草稿保存失败。',
        }));
      }
    },
    [snapshot, storage],
  );

  const flush = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    if (pending.current || !status.savedAt) writeNow(false);
  }, [status.savedAt, writeNow]);

  /* 首屏读取：为空则保持新建；损坏则暂停自动写入（不覆盖原稿）。 */
  useEffect(() => {
    if (!storage) {
      setStatus({ ready: true, error: '当前环境不支持本地草稿存储。', savedAt: null, saving: false });
      blocked.current = true;
      return;
    }
    const result = readLocalDraft(storage);
    if (result.status === 'error') {
      blocked.current = true;
      setStatus({ ready: true, error: result.message ?? LOCAL_DRAFT_ERROR_MESSAGE, savedAt: null, saving: false });
      return;
    }
    if (result.status === 'ok') {
      const { draft } = result;
      store.setState({
        data: draft.data,
        modules: draft.modules,
        removed: draft.removed,
        style: draft.style,
        activeModuleId: draft.modules[0]?.id ?? '',
        revision: 0,
        past: [],
        future: [],
      });
      setStatus({ ready: true, error: null, savedAt: draft.updatedAt, saving: false });
      return;
    }
    setStatus({ ready: true, error: null, savedAt: null, saving: false });
  }, [storage, store]);

  /* 变更即防抖入队：revision（正文/模块）与 style 都触发。 */
  const revision = useStore(store, (state) => state.revision);
  const style = useStore(store, (state) => state.style);
  useEffect(() => {
    if (!status.ready || status.error || !storage) return;
    pending.current = true;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      timer.current = null;
      writeNow(false);
    }, SAVE_DEBOUNCE_MS);
    return () => {
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
    };
  }, [revision, style, status.ready, status.error, storage, writeNow]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onHide = () => {
      if (pending.current) writeNow(false);
    };
    window.addEventListener('beforeunload', onHide);
    document.addEventListener('visibilitychange', onHide);
    return () => {
      window.removeEventListener('beforeunload', onHide);
      document.removeEventListener('visibilitychange', onHide);
    };
  }, [writeNow]);

  /** 教师显式放弃损坏草稿（唯一允许覆盖坏稿的入口）。 */
  const discardLocalDraft = useCallback(() => {
    if (!storage) return;
    clearLocalDraft(storage);
    blocked.current = false;
    setStatus({ ready: true, error: null, savedAt: null, saving: false });
  }, [storage]);

  return { status, flush, discardLocalDraft };
}
