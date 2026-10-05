'use client';
import { useEffect, useRef, useState } from 'react';
import type { LessonCreateRequest, LessonImportRequest, LessonRevisionSummary, LessonSummary, LessonView } from '@/contracts/lesson-plans';
import { useLessonDocument, type DocumentOperationPublisher } from '../model/DocumentContext';
import { useLessonEditor } from '../model/EditorContext';
import { browserOperationRecovery, useLessonOperation } from '../model/useLessonOperation';
import { loadLegacyRaw, validateExactData } from '../model/server-cache';
import { emptyData } from '../model/defaults';
import { asApiError, stablePayloadKey } from '@/features/assessments/hooks';

type CreateContent = Omit<LessonCreateRequest, 'submissionId'>;
type ImportContent = Omit<LessonImportRequest, 'submissionId'>;
function frozenCopy<T>(value: T): T {
  const copy = structuredClone(value);
  const freeze = (entry: unknown) => { if (!entry || typeof entry !== 'object') return; Object.values(entry).forEach(freeze); Object.freeze(entry); };
  freeze(copy); return copy;
}
export function DocumentsPanel() {
  const doc = useLessonDocument(), editor = useLessonEditor();
  const current = useRef({ doc, editor }); current.current = { doc, editor };
  const copyOwner = useRef<symbol | null>(null);
  const [copyBusy, setCopyBusy] = useState(false);
  const bindPendingOperation = doc.bindPendingOperation;
  const publisherRef = useRef<DocumentOperationPublisher | null>(null);
  const create = useLessonOperation<CreateContent, LessonView>('lesson|new|create', browserOperationRecovery('zhiqikeyuan:lesson-plan:operation:v1:create', doc.services.recoveryStorage));
  const importing = useLessonOperation<ImportContent, LessonView>('lesson|new|import', browserOperationRecovery('zhiqikeyuan:lesson-plan:operation:v1:import', doc.services.recoveryStorage));
  const [lessons, setLessons] = useState<LessonSummary[]>([]), [history, setHistory] = useState<LessonRevisionSummary[]>([]);
  const [error, setError] = useState(''), [loading, setLoading] = useState(false), [total, setTotal] = useState(0);
  const [historyTotal, setHistoryTotal] = useState(0);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; const publisher = bindPendingOperation(); publisherRef.current = publisher; return () => { alive.current = false; copyOwner.current = null; if (publisherRef.current === publisher) publisherRef.current = null; publisher.release(); }; }, [bindPendingOperation]);
  const busy = create.busy || importing.busy;
  const unknown = create.state === 'unknown' || importing.state === 'unknown';
  const recoveryBlocked = create.recoveryBlocked || importing.recoveryBlocked;
  const resultUnknown = create.resultUnknown || importing.resultUnknown;
  useEffect(() => { publisherRef.current?.publish({ busy, unknown: resultUnknown, recoveryBlocked }); }, [busy, resultUnknown, recoveryBlocked]);
  async function load(more = false) {
    setLoading(true); setError('');
    try { const page = await doc.api.listLessons({ offset: more ? lessons.length : 0, limit: 50 }); if (alive.current) { setLessons((old) => more ? [...old, ...page.items] : page.items); setTotal(page.total); } }
    catch (cause) { if (alive.current) setError(asApiError(cause).message); }
    finally { if (alive.current) setLoading(false); }
  }
  async function start(kind: 'create' | 'import', useCurrent = false) {
    const publisher = publisherRef.current;
    if (!publisher?.isCurrent()) return;
    setError('');
    try {
      const operation = kind === 'create' ? create : importing;
      if (busy || recoveryBlocked || (unknown && operation.state !== 'unknown')) return;
      if (!operation.pending && (!doc.selection.subjectId || !doc.selection.classId)) throw new Error('请先在来源面板明确选择单一学科与班级');
      if (!operation.pending) await editor.flushDraft();
      let receipt;
      if (kind === 'create') {
        const data = structuredClone(useCurrent ? editor.data : emptyData); validateExactData(data);
        receipt = await create.run({ ...doc.selection, data, source: 'manual' }, (frozen) => doc.api.createLesson({ ...frozen.payload, submissionId: frozen.submissionId }), editor.revision);
      } else {
        const original = importing.pending?.payload ?? (() => { const old = loadLegacyRaw(doc.services.recoveryStorage ?? localStorage); if (!old) throw new Error('旧本地稿不存在；未发起导入'); return { ...doc.selection, draft: old.envelope }; })();
        receipt = await importing.run(original, (frozen) => doc.api.importLocalLesson({ ...frozen.payload, submissionId: frozen.submissionId }), editor.revision);
      }
      if (receipt?.current && alive.current && !operation.isRecoveryBlocked() && publisher.publish({ busy: false, unknown: false, recoveryBlocked: false })) await doc.openDocument(receipt.result.lessonPlanId);
    } catch (cause) { if (alive.current && publisher.isCurrent()) setError(asApiError(cause).message); }
  }
  async function retryOperationCache(kind: 'create' | 'import') {
    const operation = kind === 'create' ? create : importing, publisher = publisherRef.current;
    if (!publisher?.isCurrent() || busy) return;
    const outcome = operation.cleanupOutcome();
    const completed = outcome?.type === 'success' ? outcome.receipt.result : null;
    if (await operation.retryRecoveryWrite()) {
      if (!alive.current || !publisher.isCurrent()) return;
      editor.notice(outcome ? (completed ? '明确成功回执的缓存清理已完成；没有再次发送HTTP。' : '明确失败操作的缓存清理已完成；当前文档保持，没有再次发送HTTP。') : '原操作包已恢复到缓存；尚未发送HTTP，请显式重试原包。');
      if (completed && publisher.publish({ busy: false, unknown: false, recoveryBlocked: false })) await doc.openDocument(completed.lessonPlanId);
    }
  }
  async function loadHistory(more = false) {
    if (!doc.documentId) return;
    setError(''); try { const page = await doc.api.listLessonRevisions(doc.documentId, { offset: more ? history.length : 0, limit: 50 }); if (alive.current) { setHistory((old) => more ? [...old, ...page.items] : page.items); setHistoryTotal(page.total); } } catch (cause) { if (alive.current) setError(asApiError(cause).message); }
  }
  async function copyHistoryToCurrent() {
    const origin = current.current, server = origin.editor.server, intent = origin.doc.pendingCopy;
    if (!alive.current || copyOwner.current || !server?.ready || !server.cache || !intent || origin.editor.editingLocked || server.busy || server.unknown || server.syncState === 'conflict') return;
    const owner = Symbol('history copy');
    const fixed = frozenCopy(intent);
    const captured = Object.freeze({ documentId: origin.doc.documentId, store: origin.editor.store,
      loadGeneration: server.loadGeneration, writeEpoch: server.writeEpoch, editRevision: origin.editor.store.getState().revision,
      serverRevision: server.cache.serverRevision, serverRevisionId: server.cache.serverRevisionId,
      serverBaselineKey: stablePayloadKey(server.latest?.currentRevision),
      intent, intentKey: stablePayloadKey(fixed) });
    copyOwner.current = owner; setCopyBusy(true);
    const sameOwner = () => alive.current && copyOwner.current === owner;
    const sameSession = () => {
      const now = current.current;
      return sameOwner() && now.doc.mode === 'server' && now.doc.documentId === captured.documentId && now.editor.store === captured.store &&
        now.editor.server?.loadGeneration === captured.loadGeneration && now.editor.server.writeEpoch === captured.writeEpoch &&
        now.doc.pendingCopy === captured.intent && stablePayloadKey(now.doc.pendingCopy) === captured.intentKey;
    };
    try {
      const latest = await server.refreshLatest();
      if (!sameSession()) return;
      const now = current.current;
      if (now.editor.store.getState().revision !== captured.editRevision) { now.editor.notice('等待期间已有新编辑，请重新确认复制；当前输入和复制意图保持。'); return; }
      if (!latest) { now.editor.notice('后台版本读取未完成，当前输入与复制意图保持；可重试复制。'); return; }
      if (latest.lessonPlanId !== captured.documentId || fixed.lessonPlanId !== captured.documentId ||
          latest.revision !== captured.serverRevision || latest.currentRevisionId !== captured.serverRevisionId ||
          stablePayloadKey(latest.currentRevision) !== captured.serverBaselineKey ||
          now.editor.server!.cache?.serverRevision !== captured.serverRevision || now.editor.server!.cache?.serverRevisionId !== captured.serverRevisionId ||
          now.editor.server!.latest?.revision !== captured.serverRevision || now.editor.server!.latest?.currentRevisionId !== captured.serverRevisionId) {
        now.editor.notice('当前后台基线变化，请先对照版本；当前输入和复制意图保持。'); return;
      }
      if (now.editor.editingLocked || now.editor.server!.busy || now.editor.server!.unknown) { now.editor.notice('当前操作尚未完成，复制意图保持；请完成后重新确认。'); return; }
      now.editor.replace(structuredClone(fixed.data)); now.doc.finishCopy(); now.editor.notice('历史正文已成为当前编辑，可撤销；保存将创建新版本');
    } catch (cause) { if (sameSession()) current.current.editor.notice(`历史复制失败，当前输入和复制意图保持：${asApiError(cause).message}`); }
    finally { if (sameOwner()) { copyOwner.current = null; setCopyBusy(false); } }
  }
  return <details className="lesson-server-panel" onToggle={(event) => { if (event.currentTarget.open && !lessons.length && !loading) void load(); }}>
    <summary>后台文档与固定历史</summary>
    <div className="lesson-panel-body">
      {doc.initialRouteError && <p role="alert">{doc.initialRouteError}</p>}
      <div className="lesson-actions">
        <button className="button subtle" disabled={busy || unknown || recoveryBlocked} onClick={() => void start('create')}>创建空白后台教案</button>
        <button className="button subtle" disabled={busy || unknown || recoveryBlocked} onClick={() => void start('create', true)}>将当前正文创建为后台教案</button>
        <button className="button subtle" disabled={busy || unknown || recoveryBlocked} onClick={() => void start('import')}>导入完整旧本地稿到后台</button>
        {doc.mode !== 'local' && <button className="button subtle" onClick={() => void doc.openLocal()}>返回旧本地稿</button>}
      </div>
      <p className="lesson-help">旧本地稿保留原键和完整信封；导入成功后仅打开新后台文档。</p>
      {create.canRetryRecovery && <button className="button primary" disabled={busy} onClick={() => void retryOperationCache('create')}>重试创建操作恢复缓存</button>}
      {importing.canRetryRecovery && <button className="button primary" disabled={busy} onClick={() => void retryOperationCache('import')}>重试导入操作恢复缓存</button>}
      {create.state === 'unknown' && <button className="button primary" disabled={busy || recoveryBlocked} onClick={() => void start('create')}>重试原创建包</button>}
      {importing.state === 'unknown' && <button className="button primary" disabled={busy || recoveryBlocked} onClick={() => void start('import')}>重试原导入包</button>}
      {(error || create.error || importing.error || create.cacheError || importing.cacheError) && <p role="alert">{error || create.cacheError || importing.cacheError || create.error?.message || importing.error?.message}</p>}
      <ul className="lesson-document-list">{lessons.map((lesson) => <li key={lesson.lessonPlanId}><button className="lesson-document-item" onClick={() => void doc.openDocument(lesson.lessonPlanId)}>{lesson.title || '未命名教案'} <small>后台 v{lesson.revision} · {lesson.currentRevisionId}</small></button></li>)}</ul>
      <button className="button subtle" disabled={loading} onClick={() => void load()}>刷新后台列表</button>
      {lessons.length < total && <button className="button subtle" disabled={loading} onClick={() => void load(true)}>继续读取后台列表</button>}
      {doc.documentId && <><button className="button subtle" onClick={() => void loadHistory()}>读取固定历史</button><ul className="lesson-document-list">{history.map((revision) => <li key={revision.revisionId}><button className="lesson-document-item" onClick={() => void doc.openDocument(revision.lessonPlanId, revision.revisionId)}>只读 v{revision.version} · {revision.title || '未命名'}<small>{revision.revisionId} · {revision.source} · {revision.reviewState}</small></button></li>)}</ul>{history.length < historyTotal && <button className="button subtle" onClick={() => void loadHistory(true)}>继续读取固定历史</button>}</>}
      {editor.history && <button className="button primary" onClick={() => void doc.copyHistory(editor.history!)}>打开当前版本准备复制历史正文</button>}
      {doc.pendingCopy && editor.server && <button className="button primary" disabled={copyBusy || editor.editingLocked || editor.server.busy || editor.server.unknown || editor.server.syncState === 'conflict'} aria-busy={copyBusy} onClick={() => void copyHistoryToCurrent()}>明确复制历史正文到当前编辑</button>}
    </div>
  </details>;
}
