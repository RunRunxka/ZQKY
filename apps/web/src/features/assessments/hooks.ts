'use client';

/**
 * `/assessments` 工作区的数据获取原语与逻辑确认状态机（TEACHING-LOOP B3 · F20-I）。
 *
 * 与知识点/题库模块的 hooks 同构但**独立维护**（模块级依赖隔离；三份都只是薄薄的 React
 * 适配，语义由 `@/services/api-client` 与冻结契约锁定）。要点：
 *
 * - 三态显式（loading / ready / failed）：读取失败必须能显示 `ApiError` 的 code/message
 *   与重试入口，调用方不得把失败当空列表；`lastData` 让刷新失败时继续显示上一次成功数据；
 * - **StrictMode 安全**：每次 effect setup 都恢复挂载标志（B2-RV09 的教训）；
 * - **操作身份 + 观察代次**（B2-RV10 的教训）：切施测/换批次/卸载都让代次前进，
 *   迟到的成功与失败一律不写状态；
 * - **逻辑确认冻结**（F20-I）：点确认即冻结 `submissionId` + 当时原样 payload，
 *   结果未知（拿不到响应）时重试必须复用同一 `submissionId` 与同一载荷；
 *   结果未知时锁定原包；只有已有明确结果后，载荷变化才可开启新的逻辑确认。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '@/services/api-client';
import type { ErrorIssue } from '@/contracts/api';
import type { ScoreImportView, ScoreImportRowView } from '@/contracts/scores';
import {
  listScoreImportRows,
  patchScoreImport,
  type ScoreImportPatchRequest,
} from '@/services/assessments-api';

export type AsyncState<T> =
  | { phase: 'loading' }
  | { phase: 'ready'; data: T }
  | { phase: 'failed'; error: ApiError };

/** 把任意异常归一为 ApiError，保证界面能显示 code 与是否可重试。 */
export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError(
    'UNEXPECTED_ERROR',
    error instanceof Error ? error.message : '请求失败，请重试。',
    0,
    true,
  );
}

export interface AsyncResource<T> {
  state: AsyncState<T>;
  reload: () => void;
  /** 最近一次**成功**读取的数据（读取失败或重新加载期间保持可用）。 */
  lastData: T | null;
}

/** 带 abort 与重试的三态资源；`key` 变化即重新加载并取消上一次请求。 */
export function useAsyncResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: string,
): AsyncResource<T> {
  const [state, setState] = useState<AsyncState<T>>({ phase: 'loading' });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  /**
   * 最近一次**成功**读取（连同它的 key）：同一 key 刷新失败时继续可用；
   * key 变化（切换实体）即视为没有数据，避免把上一个施测/批次的视图当成本次的数据。
   */
  const lastRef = useRef<{ key: string; data: T } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setState({ phase: 'loading' });
    loadRef.current(controller.signal).then(
      (data) => {
        if (!active) return;
        lastRef.current = { key, data };
        setState({ phase: 'ready', data });
      },
      (error: unknown) => {
        if (active) setState({ phase: 'failed', error: asApiError(error) });
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [tick, key]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  const lastData = lastRef.current && lastRef.current.key === key ? lastRef.current.data : null;
  return { state, reload, lastData };
}

/* ------------------------------------------------------------------ 五步成绩流 */

/**
 * 成绩导入的五个步骤（`upload → 映射 → 校对 → 承认 → 确认`）。
 * 映射/校对/承认由导入批次视图与用户所处的校对阶段推导；确认后不可回退。
 */
export type ScoreFlowStep = 'upload' | 'mapping' | 'review' | 'acknowledge' | 'confirmed';

export const SCORE_FLOW_STEPS: readonly { id: ScoreFlowStep; label: string }[] = [
  { id: 'upload', label: '上传成绩表' },
  { id: 'mapping', label: '列映射' },
  { id: 'review', label: '行校对' },
  { id: 'acknowledge', label: '预览承认' },
  { id: 'confirmed', label: '确认入库' },
];

/** 映射是否已足以进入校对：工作表 + 至少一个身份列 + 至少一个计分叶列。 */
export function hasUsableMapping(view: ScoreImportView | null): boolean {
  if (!view || !view.mapping) return false;
  const { studentNoColumn, nameColumn, itemColumns, workSheet } = view.mapping;
  return (
    Boolean(workSheet) &&
    (Boolean(studentNoColumn) || Boolean(nameColumn)) &&
    (itemColumns?.length ?? 0) > 0
  );
}

/** 由批次视图 + 用户请求推导当前步骤（纯函数，便于单测与按钮守卫）。 */
export function scoreFlowStep(
  view: ScoreImportView | null,
  options: { acknowledgeRequested?: boolean } = {},
): ScoreFlowStep {
  if (!view) return 'upload';
  if (view.state === 'confirmed') return 'confirmed';
  if (view.state === 'failed' || view.state === 'cancelled') return 'upload';
  if (!hasUsableMapping(view)) return 'mapping';
  return options.acknowledgeRequested ? 'acknowledge' : 'review';
}

/* ------------------------------------------------------------------ 逻辑确认冻结 */

export type SubmissionPhase = 'idle' | 'in-flight' | 'succeeded' | 'failed' | 'unknown';

export interface SubmissionMetadata {
  contextKey: string;
  originalEditGeneration: number;
  loadGeneration: string;
}

export interface FrozenSubmission<T> {
  operationId: string;
  submissionId: string;
  payloadKey: string;
  /** 冻结时的原样载荷：重试必须原样重发，不得被后来的编辑偷换。 */
  payload: T;
  metadata?: SubmissionMetadata;
}

export interface SubmissionReceipt<T, R> {
  result: R;
  operation: FrozenSubmission<T>;
  /** Only the hook's mounted observation; consumers also check document/load identities. */
  current: boolean;
}

function immutableSubmission<T>(value: FrozenSubmission<T>): FrozenSubmission<T> {
  const copy = structuredClone(value);
  const seen = new WeakSet<object>();
  const freeze = (entry: unknown) => {
    if (!entry || typeof entry !== 'object' || seen.has(entry)) return;
    seen.add(entry);
    Object.values(entry).forEach(freeze);
    Object.freeze(entry);
  };
  freeze(copy);
  return copy;
}

/** 稳定序列化：键排序后 JSON 化，保证「同载荷」判定与字段顺序无关。 */
export function stablePayloadKey(value: unknown): string {
  const seen = new WeakSet<object>();
  const canonical = (input: unknown): unknown => {
    if (Array.isArray(input)) return input.map(canonical);
    if (input && typeof input === 'object') {
      if (seen.has(input as object)) return '[循环]';
      seen.add(input as object);
      const entries = Object.entries(input as Record<string, unknown>)
        .filter(([, entry]) => entry !== undefined)
        .sort(([a], [b]) => a.localeCompare(b));
      return Object.fromEntries(entries.map(([key, entry]) => [key, canonical(entry)]));
    }
    return input;
  };
  return JSON.stringify(canonical(value));
}

export interface SubmissionController<T, R> {
  /** 当前逻辑确认（含失败后仍复用同一标识）；成功后自动释放。 */
  frozen: FrozenSubmission<T> | null;
  phase: SubmissionPhase;
  /** 在途（按钮 busy）；同一时刻只有一个请求。 */
  busy: boolean;
  result: R | null;
  /** 服务端明确失败（4xx/5xx 信封）。 */
  error: ApiError | null;
  /** 结果未知（没有拿到响应）：必须重试同一标识，不得换标识重做。 */
  unknownNotice: string | null;
  /** 发起（或重试）当前逻辑确认；返回值：成功时的结果，否则 null。 */
  submit: (payload: T, run: (submission: FrozenSubmission<T>) => Promise<R>) => Promise<R | null>;
  submitWithReceipt: (
    payload: T,
    run: (submission: FrozenSubmission<T>) => Promise<R>,
    metadata: SubmissionMetadata,
  ) => Promise<SubmissionReceipt<T, R> | null>;
  /** Restore a validated recovery operation as unknown; never sends automatically. */
  recoverFrozen: (operation: FrozenSubmission<T>) => boolean;
  /** 释放冻结（用户明确要形成新的逻辑确认时调用）。 */
  release: () => void;
}

/**
 * 逻辑确认：冻结 `submissionId` + 原样 payload。
 *
 * - 同一载荷重复点击 → **不产生第二个请求**（在途去重）；
 * - 结果未知（status 0）后重试 → 复用同一 `submissionId` 与同一冻结载荷；
 * - 载荷变化（例如承认勾选变化）→ 新的逻辑确认 → 新标识；
 * - 明确结果（成功 2xx / 明确失败信封）后解除按钮锁定；成功后自动释放冻结；
 * - 卸载或 `release` 后，迟到响应不写状态。
 */
export function useFrozenSubmission<T, R>(): SubmissionController<T, R> {
  const [frozen, setFrozen] = useState<FrozenSubmission<T> | null>(null);
  const [phase, setPhase] = useState<SubmissionPhase>('idle');
  const [result, setResult] = useState<R | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [unknownNotice, setUnknownNotice] = useState<string | null>(null);
  const mounted = useRef(true);
  const epoch = useRef(0);
  const busyRef = useRef(false);
  const frozenRef = useRef<FrozenSubmission<T> | null>(null);
  const unknownRef = useRef(false);

  useEffect(() => {
    // 每次 setup 恢复挂载标志：StrictMode 的 setup→cleanup→setup 不能永久失效（B2-RV09）
    mounted.current = true;
    return () => {
      mounted.current = false;
      epoch.current += 1;
    };
  }, []);

  const setFrozenSubmission = useCallback((next: FrozenSubmission<T> | null) => {
    frozenRef.current = next;
    setFrozen(next);
  }, []);

  const release = useCallback(() => {
    epoch.current += 1; // 在途响应失效
    busyRef.current = false;
    unknownRef.current = false;
    setFrozenSubmission(null);
    setPhase('idle');
    setUnknownNotice(null);
    setError(null);
  }, [setFrozenSubmission]);

  const send = useCallback(
    async (
      payload: T,
      run: (submission: FrozenSubmission<T>) => Promise<R>,
      metadata?: SubmissionMetadata,
    ): Promise<SubmissionReceipt<T, R> | null> => {
      if (busyRef.current) return null; // 在途重复点击：不再发第二个请求
      const payloadKey = stablePayloadKey(payload);
      const existing = frozenRef.current;
      if (existing?.metadata && metadata && existing.metadata.contextKey !== metadata.contextKey) {
        setError(new ApiError('SUBMISSION_CONTEXT_MISMATCH', '原操作属于另一个编辑上下文，请先恢复原操作。', 409, false));
        return null;
      }
      const createSubmission = () => {
        const id = crypto.randomUUID();
        return immutableSubmission({ operationId: id, submissionId: id, payloadKey, payload, ...(metadata ? { metadata } : {}) });
      };
      const submission: FrozenSubmission<T> =
        existing && (unknownRef.current || existing.payloadKey === payloadKey)
          ? existing // 同一逻辑确认：复用冻结载荷与标识（结果未知后的重试）
          : createSubmission();
      if (submission !== existing) {
        setFrozenSubmission(submission);
      }
      const token = epoch.current;
      busyRef.current = true;
      setPhase('in-flight');
      setError(null);
      setUnknownNotice(null);
      try {
        const payloadResult = await run(submission);
        const current = mounted.current && token === epoch.current;
        const receipt = { result: payloadResult, operation: submission, current };
        if (!current) return receipt; // receipt-only: no state write into another mounted context
        setResult(payloadResult);
        setPhase('succeeded');
        unknownRef.current = false;
        // 明确成功：解锁并释放冻结（同一逻辑确认已经完成）
        epoch.current += 1;
        busyRef.current = false;
        setFrozenSubmission(null);
        setUnknownNotice(null);
        return receipt;
      } catch (cause) {
        if (!mounted.current || token !== epoch.current) return null; // 迟到失败同样不写
        busyRef.current = false;
        const apiError = asApiError(cause);
        if (apiError.status === 0) {
          // 拿不到响应：服务端可能已写入也可能没有；不换标识，原样重试即幂等
          setPhase('unknown');
          unknownRef.current = true;
          setUnknownNotice(
            `确认结果未知（${apiError.code}）：${apiError.message} 可能已写入也可能未写入；` +
              '请直接重试——同一个提交标识与原样载荷会按幂等处理，不会重复写入。',
          );
          return null;
        }
        setError(apiError);
        unknownRef.current = false;
        setPhase('failed');
        setUnknownNotice(null);
        return null;
      }
    },
    [setFrozenSubmission],
  );

  const submit = useCallback(async (payload: T, run: (operation: FrozenSubmission<T>) => Promise<R>) => {
    const receipt = await send(payload, run);
    return receipt?.current ? receipt.result : null;
  }, [send]);

  const submitWithReceipt = useCallback((payload: T, run: (operation: FrozenSubmission<T>) => Promise<R>, metadata: SubmissionMetadata) =>
    send(payload, run, metadata), [send]);

  const recoverFrozen = useCallback((operation: FrozenSubmission<T>): boolean => {
    if (busyRef.current) return false;
    const metadata = operation?.metadata;
    if (!operation || typeof operation.submissionId !== 'string' || !operation.submissionId ||
        operation.operationId !== operation.submissionId || operation.payloadKey !== stablePayloadKey(operation.payload) ||
        !metadata || typeof metadata.contextKey !== 'string' || !metadata.contextKey ||
        !Number.isSafeInteger(metadata.originalEditGeneration) || metadata.originalEditGeneration < 0 ||
        typeof metadata.loadGeneration !== 'string' || !metadata.loadGeneration) return false;
    const previous = frozenRef.current;
    if (previous && (previous.submissionId !== operation.submissionId || previous.payloadKey !== operation.payloadKey ||
        previous.operationId !== operation.operationId || previous.metadata?.contextKey !== metadata.contextKey ||
        previous.metadata?.originalEditGeneration !== metadata.originalEditGeneration ||
        previous.metadata?.loadGeneration !== metadata.loadGeneration)) return false;
    setFrozenSubmission(previous ?? immutableSubmission(operation));
    unknownRef.current = true;
    setPhase('unknown');
    setUnknownNotice('已恢复原操作，结果仍未知。请显式重试同一提交标识与原包。');
    setError(null);
    return true;
  }, [setFrozenSubmission]);

  return { frozen, phase, busy: phase === 'in-flight', result, error, unknownNotice, submit, submitWithReceipt, recoverFrozen, release };
}

/* ------------------------------------------------------------------ 校对草稿 */

export interface ScoreDraftEdits {
  /** 行号 → 人工指定的人次（消歧/未匹配行定位）。 */
  participants: Record<number, string>;
  /** `行:列` → 校正后的分数文本（原表物理坐标）。 */
  cells: Record<string, string>;
}

export const EMPTY_SCORE_DRAFTS: ScoreDraftEdits = { participants: {}, cells: {} };

export function draftCellKey(row: number, column: string): string {
  return `${row}:${column}`;
}

export interface ScoreDraftsController {
  edits: ScoreDraftEdits;
  dirty: boolean;
  saving: boolean;
  /** 409：保留编辑，按服务端 `currentRevision` 提示刷新对照。 */
  conflict: { currentRevision: number | null; message: string } | null;
  /** 422：保留校对状态并逐条定位到行/列。 */
  issues: ErrorIssue[];
  error: ApiError | null;
  notice: string | null;
  setParticipant: (rowNo: number, participantId: string) => void;
  setCell: (row: number, column: string, text: string) => void;
  clearCell: (row: number, column: string) => void;
  /** 保存（`expectedRevision` 乐观锁，T60 CAS）；返回服务端重算后的批次视图。 */
  save: () => Promise<ScoreImportView | null>;
  /** 放弃本地草稿（切施测/换批次/明确取消时）。 */
  reset: () => void;
}

/**
 * 校对草稿：行定位（participantId）与单元格校正（原表坐标）的本地编辑 + 保存。
 *
 * - 409：**保留编辑**，把 `currentRevision` 与提示交回调用方显式刷新对照；
 * - 422：保留校对状态，把 `details.issues` 原样暴露（调用方定位到该行该列）；
 * - 切施测/换批次/卸载后代次前进，迟到的保存响应不写状态（B2-RV10 同源要求）。
 */
export function useScoreDrafts(view: ScoreImportView | null): ScoreDraftsController {
  const [edits, setEdits] = useState<ScoreDraftEdits>(EMPTY_SCORE_DRAFTS);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState<{ currentRevision: number | null; message: string } | null>(
    null,
  );
  const [issues, setIssues] = useState<ErrorIssue[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const mounted = useRef(true);
  const epoch = useRef(0);
  const viewRef = useRef(view);
  viewRef.current = view;
  const editsRef = useRef(edits);
  editsRef.current = edits;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      epoch.current += 1;
    };
  }, []);

  // 批次身份变化（切施测/换批次）即清空草稿：编辑不能跨批次偷渡
  const viewKey = view ? `${view.importId}#${view.assessmentId}` : 'none';
  useEffect(() => {
    setEdits(EMPTY_SCORE_DRAFTS);
    setConflict(null);
    setIssues([]);
    setError(null);
    setNotice(null);
    setSaving(false);
  }, [viewKey]);

  const dirty = useMemo(
    () => Object.keys(edits.participants).length + Object.keys(edits.cells).length > 0,
    [edits],
  );

  const setParticipant = useCallback((rowNo: number, participantId: string) => {
    setEdits((prev) => {
      const participants = { ...prev.participants };
      if (participantId) participants[rowNo] = participantId;
      else delete participants[rowNo];
      return { ...prev, participants };
    });
  }, []);

  const setCell = useCallback((row: number, column: string, text: string) => {
    setEdits((prev) => ({ ...prev, cells: { ...prev.cells, [draftCellKey(row, column)]: text } }));
  }, []);

  const clearCell = useCallback((row: number, column: string) => {
    setEdits((prev) => {
      const cells = { ...prev.cells };
      delete cells[draftCellKey(row, column)];
      return { ...prev, cells };
    });
  }, []);

  const reset = useCallback(() => {
    epoch.current += 1;
    setEdits(EMPTY_SCORE_DRAFTS);
    setConflict(null);
    setIssues([]);
    setError(null);
    setNotice(null);
    setSaving(false);
  }, []);

  const save = useCallback(async (): Promise<ScoreImportView | null> => {
    const current = viewRef.current;
    if (!current) return null;
    const draft = editsRef.current;
    const rows: ScoreImportPatchRequest['rows'] = [];
    for (const [rowNoText, participantId] of Object.entries(draft.participants)) {
      rows.push({ rowNo: Number(rowNoText), participantId });
    }
    for (const [key, text] of Object.entries(draft.cells)) {
      const [rowText, column] = key.split(':');
      rows.push({ rowNo: Number(rowText), cells: [{ row: Number(rowText), column, text }] });
    }
    const token = epoch.current;
    setSaving(true);
    setConflict(null);
    setIssues([]);
    setError(null);
    setNotice(null);
    try {
      const next = await patchScoreImport(current.importId, {
        expectedRevision: current.revision,
        rows,
      });
      if (!mounted.current || token !== epoch.current) return null;
      setEdits(EMPTY_SCORE_DRAFTS);
      setNotice(`已保存校对（批次 r${next.revision}，预览 v${next.previewVersion}）。`);
      return next;
    } catch (cause) {
      if (!mounted.current || token !== epoch.current) return null; // 迟到响应不写状态
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        setConflict({
          currentRevision: apiError.details?.currentRevision ?? null,
          message: apiError.message,
        });
      } else if (apiError.status === 422) {
        setIssues(apiError.details?.issues ?? []);
        setError(apiError);
      } else {
        setError(apiError);
      }
      return null;
    } finally {
      if (mounted.current && token === epoch.current) setSaving(false);
    }
  }, []);

  return {
    edits,
    dirty,
    saving,
    conflict,
    issues,
    error,
    notice,
    setParticipant,
    setCell,
    clearCell,
    save,
    reset,
  };
}

/* ------------------------------------------------------------------ 原表行读取 */

/** 读取全部原表行（承认范围推导用）：按 200/页上限循环取到 total，最多 20 页。 */
export async function loadAllImportRows(
  importId: string,
  signal?: AbortSignal,
  pageSize = 200,
): Promise<ScoreImportRowView[]> {
  const rows: ScoreImportRowView[] = [];
  for (let page = 0; page < 20; page += 1) {
    const chunk = await listScoreImportRows(
      importId,
      { offset: page * pageSize, limit: pageSize },
      signal,
    );
    rows.push(...chunk.items);
    if (rows.length >= chunk.total || chunk.items.length === 0) break;
  }
  return rows;
}
