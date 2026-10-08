'use client';
import { useEffect, useRef, useState } from 'react';
import type { LessonCreateRequest, LessonImportRequest, LessonRevisionSummary, LessonSummary, LessonView } from '@/contracts/lesson-plans';
import { ApiError } from '@/services/api-client';
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
  /** 列表归档视图：默认只看未归档；打开后传 `archived: true`（只看已归档，便于恢复）。 */
  const [archivedView, setArchivedView] = useState(false);
  /** 二次确认的归档/恢复目标；确认前不发任何写请求。 */
  const [archiveTarget, setArchiveTarget] = useState<{ lessonPlanId: string; revision: number; archived: boolean } | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState<ApiError | null>(null);
  const [archiveNotice, setArchiveNotice] = useState('');
  const archiveBusyRef = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; const publisher = bindPendingOperation(); publisherRef.current = publisher; return () => { alive.current = false; copyOwner.current = null; if (publisherRef.current === publisher) publisherRef.current = null; publisher.release(); }; }, [bindPendingOperation]);
  const busy = create.busy || importing.busy;
  const unknown = create.state === 'unknown' || importing.state === 'unknown';
  const recoveryBlocked = create.recoveryBlocked || importing.recoveryBlocked;
  const resultUnknown = create.resultUnknown || importing.resultUnknown;
  useEffect(() => { publisherRef.current?.publish({ busy, unknown: resultUnknown, recoveryBlocked }); }, [busy, resultUnknown, recoveryBlocked]);
  async function load(more = false, archived = archivedView) {
    setLoading(true); setError('');
    try { const page = await doc.api.listLessons({ offset: more ? lessons.length : 0, limit: 50, archived }); if (alive.current) { setLessons((old) => more ? [...old, ...page.items] : page.items); setTotal(page.total); } }
    catch (cause) { if (alive.current) setError(asApiError(cause).message); }
    finally { if (alive.current) setLoading(false); }
  }
  /** 切换归档视图即更换筛选：清空旧列表并显式读取一次，失败时只显示错误，不显示空目录。 */
  function changeArchivedView(next: boolean) {
    if (archiveBusy) return;
    setArchivedView(next);
    setArchiveTarget(null); setArchiveError(null); setArchiveNotice('');
    setLessons([]); setTotal(0);
    void load(false, next);
  }
  /**
   * 当前工作台已打开的教案不能归档：编辑器没有归档态，归档后继续写入会被后端拒绝（LESSON_INVALID）。
   * 恢复不受影响。
   */
  function archiveBlockReason(lessonPlanId: string) {
    if (doc.mode === 'local' || doc.documentId !== lessonPlanId) return '';
    return '该教案正在工作台打开：编辑器无法表示归档状态，归档后继续写入会被后端拒绝。请先返回旧本地稿或打开其他教案，再归档。';
  }
  /**
   * 归档/恢复一份后台教案：归档只写 archived_at，历史修订与 head 指针保留，revision 不递增。
   * 失败保留原目标与提示；结果未知时重按确认即重发同一请求（同一教案与 expectedRevision）。
   */
  async function changeArchivedLesson(target: { lessonPlanId: string; revision: number; archived: boolean }) {
    if (archiveBusyRef.current) return;
    archiveBusyRef.current = true;
    setArchiveBusy(true); setArchiveError(null); setArchiveNotice('');
    try {
      const body = { expectedRevision: target.revision };
      const view = target.archived ? await doc.api.archiveLessonPlan(target.lessonPlanId, body) : await doc.api.restoreLessonPlan(target.lessonPlanId, body);
      if (!alive.current) return;
      if (view.lessonPlanId !== target.lessonPlanId) throw new ApiError('LESSON_ARCHIVE_IDENTITY_MISMATCH', '归档回执与目标教案不一致，未刷新列表。', 500, false);
      setArchiveTarget(null);
      setArchiveNotice(target.archived ? `已归档教案 ${target.lessonPlanId}：不能写入，历史修订保留。` : `已恢复教案 ${target.lessonPlanId}：可继续编辑。`);
      void load(false);
    } catch (cause) {
      if (alive.current) setArchiveError(asApiError(cause));
    } finally { archiveBusyRef.current = false; if (alive.current) setArchiveBusy(false); }
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
      <label className="lesson-check"><input type="checkbox" aria-label="显示已归档" checked={archivedView} disabled={archiveBusy} onChange={(event) => changeArchivedView(event.target.checked)} />显示已归档</label>
      <p className="lesson-help">{archivedView ? '当前只看已归档教案，便于恢复；归档期间的修订历史保留。' : '当前只看未归档教案；已归档教案不出现在这里，可用上方开关查看。'}</p>
      {archiveNotice && <p role="status">{archiveNotice}</p>}
      {archiveError && <p role="alert">{archiveError.code}：{archiveError.message}</p>}
      {archiveError && <button className="button subtle" disabled={loading} onClick={() => void load(false)}>刷新后台列表对照服务器</button>}
      {loading && <p role="status">正在读取后台教案列表…</p>}
      <ul className="lesson-document-list">{lessons.map((lesson) => <li key={lesson.lessonPlanId}>
        <button className="lesson-document-item" onClick={() => void doc.openDocument(lesson.lessonPlanId)}>{lesson.title || '未命名教案'} <small>后台 v{lesson.revision} · {lesson.currentRevisionId}</small></button>
        <div className="lesson-sync-actions">
          <button className="button subtle" disabled={busy || unknown || recoveryBlocked || archiveBusy} onClick={() => setArchiveTarget({ lessonPlanId: lesson.lessonPlanId, revision: lesson.revision, archived: !archivedView })}>{archivedView ? '恢复' : '归档'}</button>
          {archivedView && <span className="small-badge">已归档</span>}
          {archiveTarget?.lessonPlanId === lesson.lessonPlanId && <>
            <span role="alert">{archiveTarget.archived ? '归档后不能写入，历史修订保留。' : '恢复后可继续编辑。'}{archiveTarget.archived && archiveBlockReason(lesson.lessonPlanId) ? ` ${archiveBlockReason(lesson.lessonPlanId)}` : ''}</span>
            <button className="button subtle" disabled={archiveBusy || (archiveTarget.archived && !!archiveBlockReason(lesson.lessonPlanId))} onClick={() => void changeArchivedLesson({ lessonPlanId: lesson.lessonPlanId, revision: lesson.revision, archived: archiveTarget.archived })}>{archiveBusy ? '正在提交…' : archiveTarget.archived ? '确认归档' : '确认恢复'}</button>
            <button className="button subtle" disabled={archiveBusy} onClick={() => setArchiveTarget(null)}>取消</button>
          </>}
        </div>
      </li>)}</ul>
      <button className="button subtle" disabled={loading} onClick={() => void load()}>刷新后台列表</button>
      {lessons.length < total && <button className="button subtle" disabled={loading} onClick={() => void load(true)}>继续读取后台列表</button>}
      {doc.documentId && <><button className="button subtle" onClick={() => void loadHistory()}>读取固定历史</button><ul className="lesson-document-list">{history.map((revision) => <li key={revision.revisionId}><button className="lesson-document-item" onClick={() => void doc.openDocument(revision.lessonPlanId, revision.revisionId)}>只读 v{revision.version} · {revision.title || '未命名'}<small>{revision.revisionId} · {revision.source} · {revision.reviewState}</small></button></li>)}</ul>{history.length < historyTotal && <button className="button subtle" onClick={() => void loadHistory(true)}>继续读取固定历史</button>}</>}
      {editor.history && <button className="button primary" onClick={() => void doc.copyHistory(editor.history!)}>打开当前版本准备复制历史正文</button>}
      {doc.pendingCopy && editor.server && <button className="button primary" disabled={copyBusy || editor.editingLocked || editor.server.busy || editor.server.unknown || editor.server.syncState === 'conflict'} aria-busy={copyBusy} onClick={() => void copyHistoryToCurrent()}>明确复制历史正文到当前编辑</button>}
    </div>
  </details>;
}
