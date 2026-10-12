/**
 * 云端草稿同步与导出（R7-FE）。
 *
 * 语义（沿用归档 B5 的 CAS 口径，冻结端点见 `services/lesson-plans-api.ts`）：
 * - autosave：内容变更 900ms 防抖、**串行**发送 `PATCH /lesson-plans/{id}/draft`，
 *   携带 `expectedRevision`（服务器 CAS）与新的 `submissionId`（幂等重放）；
 * - 409 冲突：**不自动换新 CAS 覆盖**，暂停自动同步并停在冲突态，由教师选择
 *   「载入服务器版本」或「保持本地并暂停同步」；
 * - 读取失败/服务未就绪：如实进入错误态（含原因与重试），不伪造空目录、不静默降级；
 * - 导出：`POST /lesson-plans/{id}/export`（无 id 时先创建）→ 202 → 下载产物；
 *   失败如实报错，绝不宣称已导出。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useStore } from 'zustand';
import type { StoreApi } from 'zustand/vanilla';
import { ApiError } from '@/services/api-client';
import { lessonPlansApi, type LessonPlansApi, uploadLessonSource } from '@/services/lesson-plans-api';
import { newId, withLessonDefaults } from './lesson-data';
import { describeError } from '../services/errors';
import { modulesToWire } from './modules';
import type { LessonWorkbenchState } from './store';
import { ACTIVE_PLAN_KEY, clearActivePlanId, readActivePlanId, writeActivePlanId } from './draft-storage';
import { triggerBlobDownload } from '../services/download';
import type { LessonExportRequest, LessonSummaryPage } from '@/contracts/lesson-plans';

const SERVER_DEBOUNCE_MS = 900;

export type ServerStatus = 'local' | 'loading' | 'syncing' | 'synced' | 'error' | 'conflict';

export interface ServerState {
  planId: string | null;
  /** 服务器 CAS 修订号（与 store 的本地编辑 revision 不是一回事）。 */
  revision: number;
  status: ServerStatus;
  message?: string;
  conflictRevision?: number | null;
  lastSyncedAt?: string;
}

function storageOrNull(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function reasonOf(error: unknown): string {
  return describeError(error);
}

export interface ExportOutcome {
  fileName: string;
  downloaded: boolean;
}

export function useLessonServer({
  store,
  api = lessonPlansApi,
  uploadSource = uploadLessonSource,
}: {
  store: StoreApi<LessonWorkbenchState>;
  api?: LessonPlansApi;
  uploadSource?: typeof uploadLessonSource;
}) {
  const [storage] = useState<Storage | null>(storageOrNull);
  const [server, setServer] = useState<ServerState>({
    planId: null,
    revision: 0,
    status: 'local',
  });
  const serverRef = useRef(server);
  serverRef.current = server;
  const inFlight = useRef<Promise<void> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const paused = useRef(false);
  const revision = useStore(store, (state) => state.revision);

  const buildExportRequest = useCallback((): LessonExportRequest => {
    const state = store.getState();
    return { data: state.data, style: state.style, modules: modulesToWire(state.modules) };
  }, [store]);

  /* ---------------- 读取 / 创建 ---------------- */

  const openPlan = useCallback(
    async (planId: string) => {
      setServer((current) => ({ ...current, status: 'loading', message: undefined }));
      try {
        const view = await api.getLessonPlan(planId);
        store.setState({
          data: withLessonDefaults(view.currentRevision.data),
          revision: 0,
          past: [],
          future: [],
        });
        paused.current = false;
        if (storage) writeActivePlanId(storage, view.lessonPlanId);
        setServer({
          planId: view.lessonPlanId,
          revision: view.revision,
          status: 'synced',
          lastSyncedAt: new Date().toISOString(),
        });
        return view;
      } catch (error) {
        const notFound = error instanceof ApiError && error.status === 404;
        if (notFound && storage) clearActivePlanId(storage);
        setServer((current) => ({
          ...current,
          planId: notFound ? null : current.planId,
          status: 'error',
          message: `云端教案读取失败：${reasonOf(error)}`,
        }));
        throw error;
      }
    },
    [api, storage, store],
  );

  const createPlan = useCallback(async () => {
    setServer((current) => ({ ...current, status: 'loading', message: undefined }));
    try {
      const view = await api.createLessonPlan({
        submissionId: newId(),
        data: store.getState().data,
      });
      paused.current = false;
      if (storage) writeActivePlanId(storage, view.lessonPlanId);
      setServer({
        planId: view.lessonPlanId,
        revision: view.revision,
        status: 'synced',
        lastSyncedAt: new Date().toISOString(),
      });
      return view;
    } catch (error) {
      setServer((current) => ({
        ...current,
        status: 'error',
        message: `云端教案创建失败：${reasonOf(error)}`,
      }));
      throw error;
    }
  }, [api, storage, store]);

  const listPlans = useCallback((): Promise<LessonSummaryPage> => api.listLessonPlans(), [api]);

  /* ---------------- autosave（串行 + CAS） ---------------- */

  const flush = useCallback(async (): Promise<void> => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    if (inFlight.current) await inFlight.current.catch(() => undefined);
    const { planId, revision: serverRevision, status } = serverRef.current;
    if (!planId || paused.current || status === 'conflict') return;
    const data = store.getState().data;
    setServer((current) => ({ ...current, status: 'syncing', message: undefined }));
    const task = api
      .patchLessonPlanDraft(planId, {
        submissionId: newId(),
        expectedRevision: serverRevision,
        data,
        context: null,
        source: 'manual',
      })
      .then((view) => {
        setServer((current) => ({
          ...current,
          revision: view.revision,
          status: 'synced',
          lastSyncedAt: new Date().toISOString(),
        }));
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 409) {
          paused.current = true;
          setServer((current) => ({
            ...current,
            status: 'conflict',
            conflictRevision: error.details?.currentRevision ?? null,
            message: '云端已有更新版本，自动同步已暂停。请选择载入服务器版本，或保持本地内容并暂停同步。',
          }));
          return;
        }
        setServer((current) => ({
          ...current,
          status: 'error',
          message: `云端保存失败：${reasonOf(error)}`,
        }));
      })
      .finally(() => {
        inFlight.current = null;
      });
    inFlight.current = task;
    await task;
  }, [api, store]);

  useEffect(() => {
    const state = serverRef.current;
    if (!state.planId || paused.current || state.status === 'conflict') return;
    if (revision === 0) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      timer.current = null;
      void flush();
    }, SERVER_DEBOUNCE_MS);
    return () => {
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
    };
  }, [revision, flush]);

  /* 首屏：尝试恢复上次打开的云端教案；失败保留记忆并可重试（只执行一次）。 */
  const openedRef = useRef(false);
  useEffect(() => {
    if (openedRef.current) return;
    openedRef.current = true;
    const activeId = storage ? readActivePlanId(storage) : null;
    if (!activeId) return;
    void openPlan(activeId).catch(() => undefined);
  }, [openPlan, storage]);

  const retrySync = useCallback(async () => {
    paused.current = false;
    setServer((current) => ({ ...current, status: 'local', message: undefined }));
    await flush();
  }, [flush]);

  const reloadServerVersion = useCallback(async () => {
    const planId = serverRef.current.planId;
    if (!planId) return;
    await openPlan(planId);
  }, [openPlan]);

  const keepLocalOnly = useCallback(() => {
    paused.current = true;
    if (storage) clearActivePlanId(storage);
    setServer((current) => ({
      ...current,
      planId: null,
      status: 'local',
      message: '已暂停云端同步；本页内容仍保存在本机草稿。',
    }));
  }, [storage]);

  /** 导出：必要时先创建云端教案；成功返回文件名与是否已触发下载。 */
  const exportNow = useCallback(async (): Promise<ExportOutcome> => {
    const { planId } = serverRef.current;
    let targetId = planId;
    if (!targetId) {
      const created = await createPlan();
      targetId = created.lessonPlanId;
    }
    const receipt = await api.exportLessonPlan(targetId, buildExportRequest());
    const { blob, fileName } = await api.downloadLessonExport(receipt.artifact.artifactId);
    const suggested = receipt.artifact.fileName || fileName || '教案.docx';
    return { fileName: suggested, downloaded: triggerBlobDownload(blob, suggested) };
  }, [api, buildExportRequest, createPlan]);

  return {
    server,
    setServer,
    openPlan,
    createPlan,
    listPlans,
    flush,
    retrySync,
    reloadServerVersion,
    keepLocalOnly,
    exportNow,
    uploadSource,
    /** 云端教案 id 的本地记忆键（探针/测试断言用）。 */
    activePlanKey: ACTIVE_PLAN_KEY,
  };
}
