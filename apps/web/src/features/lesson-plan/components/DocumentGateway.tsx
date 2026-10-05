'use client';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import type { LessonRevisionView, LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { asApiError } from '@/features/assessments/hooks';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { LessonPlanProvider } from '../model/EditorContext';
import { defaultSourceApi, type LessonWorkspaceServices } from '../model/workspace-services';
import { LessonDocumentContext, type DocumentSelection, type DocumentOperationState, type DocumentOperationPublisher } from '../model/DocumentContext';

export interface LessonWorkspaceProps {
  services?: LessonWorkspaceServices;
  initialLessonPlanId?: string;
  initialRevisionId?: string;
  initialAnalysisRunId?: string;
  initialRouteError?: string;
}
const emptyServices: LessonWorkspaceServices = {};
export function DocumentGateway({ children, services = emptyServices, initialLessonPlanId, initialRevisionId, initialAnalysisRunId, initialRouteError }: LessonWorkspaceProps & { children: ReactNode }) {
  const router = useRouter();
  const api = services.lessonApi ?? lessonPlanApi;
  const sources = services.sourceApi ?? defaultSourceApi;
  const [documentId, setDocumentId] = useState(initialLessonPlanId);
  const [revisionId, setRevisionId] = useState(initialRevisionId);
  const [view, setView] = useState<LessonView | null>(null);
  const [fixed, setFixed] = useState<LessonRevisionView | null>(null);
  const [loading, setLoading] = useState(!!initialLessonPlanId && !initialRouteError);
  const [routeError, setRouteError] = useState(initialRouteError ?? '');
  const [error, setError] = useState(initialRouteError ?? '');
  const [selection, setSelection] = useState<DocumentSelection>({ subjectId: '', classId: '', context: null });
  const [pendingCopy, setPendingCopy] = useState<LessonRevisionView | null>(null);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const leave = useRef<(() => Promise<boolean>) | null>(null);
  const pendingOperation = useRef<DocumentOperationState>({ busy: false, unknown: false });
  const [pendingOperationState, setPendingOperationState] = useState<DocumentOperationState>({ busy: false, unknown: false });
  const pendingOwner = useRef<symbol | null>(null), pendingContext = useRef('');
  pendingContext.current = `${documentId ?? ''}|${revisionId ?? ''}|${routeError}`;
  const sequence = useRef(0);
  const alive = useRef(true);
  const publishOperation = useCallback((state: DocumentOperationState) => {
    if (pendingOperation.current.busy === state.busy && pendingOperation.current.unknown === state.unknown
      && !!pendingOperation.current.recoveryBlocked === !!state.recoveryBlocked) return;
    const next = { busy: state.busy, unknown: state.unknown, recoveryBlocked: !!state.recoveryBlocked };
    pendingOperation.current = next; setPendingOperationState(next);
  }, []);
  const bindPendingOperation = useCallback((): DocumentOperationPublisher => {
    const owner = Symbol('lesson document operation'), context = pendingContext.current;
    pendingOwner.current = owner; publishOperation({ busy: false, unknown: false });
    const isCurrent = () => alive.current && pendingOwner.current === owner && pendingContext.current === context;
    return {
      isCurrent,
      publish(state) { if (!isCurrent()) return false; publishOperation(state); return true; },
      release() { if (!isCurrent()) return; pendingOwner.current = null; publishOperation({ busy: false, unknown: false }); },
    };
  }, [publishOperation]);
  const routeIdentity = useRef(`${initialLessonPlanId ?? ''}|${initialRevisionId ?? ''}|${initialRouteError ?? ''}`);
  useEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current += 1; }; }, []);
  useEffect(() => { const identity = `${initialLessonPlanId ?? ''}|${initialRevisionId ?? ''}|${initialRouteError ?? ''}`; if (identity === routeIdentity.current) return; routeIdentity.current = identity; if (!initialRouteError && initialLessonPlanId === documentId && initialRevisionId === revisionId) return; sequence.current += 1; setDocumentId(initialLessonPlanId); setRevisionId(initialRevisionId); setView(null); setFixed(null); setPendingCopy(null); setLoading(!!initialLessonPlanId && !initialRouteError); setRouteError(initialRouteError ?? ''); setError(initialRouteError ?? ''); }, [initialLessonPlanId, initialRevisionId, initialRouteError, documentId, revisionId]);
  useEffect(() => {
    if (!documentId || routeError) return;
    const token = ++sequence.current;
    const abort = new AbortController(); setLoading(true); setError('');
    void Promise.all([api.getLesson(documentId, abort.signal), revisionId ? api.getLessonRevision(documentId, revisionId, abort.signal) : Promise.resolve(null)]).then(([next, history]) => {
      if (!alive.current || token !== sequence.current || abort.signal.aborted) return;
      if (next.lessonPlanId !== documentId || (history && (history.lessonPlanId !== documentId || history.revisionId !== revisionId))) throw new Error('教案固定身份不匹配，未显示其他内容');
      setView(next); setFixed(history); setSelection({ subjectId: next.subjectId, classId: next.classId, context: next.currentRevision.contextSnapshot.analysis ? {
        analysisRunId: next.currentRevision.contextSnapshot.analysis.analysisRunId,
        selectedKnowledgePointIds: next.currentRevision.contextSnapshot.analysis.knowledgePoints.map((point) => point.knowledgePointId),
      } : null }); setLoading(false);
    }).catch((cause) => { if (alive.current && token === sequence.current && !abort.signal.aborted) { setLoading(false); setError(asApiError(cause).message); } });
    return () => abort.abort();
  }, [documentId, revisionId, api, routeError]);
  const navigateDocument = useCallback(async (id: string, fixedId?: string, copy: LessonRevisionView | null = null) => {
    if (id === documentId && fixedId === revisionId) return;
    const origin = sequence.current;
    if (leave.current && !(await leave.current())) return;
    if (!alive.current || origin !== sequence.current) return;
    sequence.current += 1;
    const params = new URLSearchParams({ lessonPlanId: id }); if (fixedId) params.set('revisionId', fixedId);
    router.push(`/lesson-plans?${params.toString()}`);
    setLoading(true); setView(null); setFixed(null); setCandidateId(null); setPendingCopy(copy); setError(''); setDocumentId(id); setRevisionId(fixedId);
  }, [documentId, revisionId, router]);
  const openDocument = useCallback((id: string, fixedId?: string) => navigateDocument(id, fixedId), [navigateDocument]);
  const openLocal = useCallback(async () => {
    if (!documentId) return;
    const origin = sequence.current;
    if (leave.current && !(await leave.current())) return;
    if (!alive.current || origin !== sequence.current) return;
    router.push('/lesson-plans');
    sequence.current += 1; setDocumentId(undefined); setRevisionId(undefined); setView(null); setFixed(null); setLoading(false); setError(''); setPendingCopy(null);
  }, [documentId, router]);
  const onSaved = useCallback((next: LessonView) => setView((previous) => {
    if (!previous || previous.lessonPlanId !== next.lessonPlanId || next.revision < previous.revision || (next.revision === previous.revision && next.currentRevisionId !== previous.currentRevisionId)) return previous;
    return next;
  }), []);
  const mode = documentId ? revisionId ? 'history' : 'server' : 'local';
  const controller = { mode, documentId, initialAnalysisRunId, initialRouteError: routeError || undefined, view, api, sources, services, selection, setSelection,
    openDocument, openLocal, leave, pendingOperation, pendingOperationState, bindPendingOperation, onSaved, pendingCopy, finishCopy: () => setPendingCopy(null), candidateId, setCandidateId,
    async copyHistory(revision: LessonRevisionView) { if (revision.lessonPlanId !== documentId || revision.revisionId !== revisionId || !fixed || fixed.revisionId !== revision.revisionId) return; await navigateDocument(revision.lessonPlanId, undefined, structuredClone(revision)); },
  } as const;
  return <LessonDocumentContext.Provider value={controller}>
    {routeError || loading || (documentId && (!view || error)) ? <WorkspaceShell pageTitle="教案工作台" className="lesson-workspace lesson-page">
      <main className="status-page" aria-label="读取后台教案">{loading && !routeError ? <p role="status">正在读取后台教案…</p> : <><p role="alert">{routeError ? `教案地址无效：${routeError}` : `后台教案读取失败：${error}`}。未发起依赖编辑或覆盖恢复缓存。</p><button className="button subtle" onClick={() => { router.push('/lesson-plans'); setDocumentId(undefined); setRevisionId(undefined); setView(null); setFixed(null); setPendingCopy(null); setRouteError(''); setLoading(false); setError(''); }}>明确返回旧本地稿</button></>}</main>
    </WorkspaceShell> : <LessonPlanProvider key={`${mode}|${documentId ?? 'local'}|${revisionId ?? 'current'}`} services={services} session={mode === 'history' && fixed ? { history: fixed } : mode === 'server' && view ? { server: { view, api, storage: services.recoveryStorage, onSaved } } : {}}>{children}</LessonPlanProvider>}
  </LessonDocumentContext.Provider>;
}
