'use client';

import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
import { GuardedLink, useNavigationGuard } from '@/services/navigation-guard';
import type { MutableRefObject } from 'react';
import type { PracticeEditingHandle } from './session';
import './styles.css';
import type { PracticeSetView, PracticeRevisionView, PracticeRevisionRequest, PracticeConversionReceipt } from '@/contracts/b4';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import { asApiError, useAsyncResource, useFrozenSubmission } from '@/features/assessments/hooks';
import { ErrorNotice, ReadNotice, SubmissionNotice, Pagination, RichReview, scoreText, nameOrShortId, shortId, stampText } from '@/features/learning-analysis/ui';
import { CreatePracticeForm } from './CreatePracticeForm';
import { PracticeEditor } from './PracticeEditor';
import { PracticeExports } from './PracticeExports';
import { PracticeConversion } from './PracticeConversion';
import '@/components/layout/space.css';
import '@/features/learning-analysis/styles.css';

export interface PracticesWorkspaceProps {
  initialPracticeSetId?: string | null;
  initialPracticeRevisionId?: string | null;
  initialAnalysisRunId?: string | null;
  services?: typeof b4Api;
}

/**
 * 练习来源报告的展示名（名称优先）：来源原卷标题 + 报告时间；
 * 标题缺失回落分析运行短号（不伪造名称），时间缺失只显示名称。
 */
function practiceSourceLabel(source: { sourcePaperTitle?: string | null; sourceCreatedAt?: string | null; analysisRunId: string }): string {
  const name = nameOrShortId(source.sourcePaperTitle, source.analysisRunId);
  const stamp = source.sourceCreatedAt ? stampText(source.sourceCreatedAt) : '';
  return stamp ? `${name} · ${stamp}` : name;
}

/** 受引用守卫 409 的一条计数：`键 → 标签 + 计数`。 */
interface PracticeReferenceCount { key: string; label: string; count: number }

/** `PRACTICE_IN_USE` 的逐项标签（键与后端一致；未知键用原始键名兜底，不隐藏引用）。 */
const PRACTICE_REFERENCE_LABELS: Record<string, string> = {
  reviewedRevisions: '已审核版本',
  exports: '导出记录',
  conversions: '施测转换',
};

/** 从 409 的 `details.counts` 解析逐项引用计数：只保留 >0 的键；形状不符返回空数组。 */
function practiceReferenceCounts(details: unknown): PracticeReferenceCount[] {
  if (!details || typeof details !== 'object') return [];
  const counts = (details as { counts?: unknown }).counts;
  if (!counts || typeof counts !== 'object') return [];
  return Object.entries(counts as Record<string, unknown>)
    .filter(([, value]) => typeof value === 'number' && value > 0)
    .map(([key, value]) => ({ key, label: PRACTICE_REFERENCE_LABELS[key] ?? key, count: value as number }));
}

export function PracticesWorkspace({ initialPracticeSetId = null, initialPracticeRevisionId = null, initialAnalysisRunId = null, services = b4Api }: PracticesWorkspaceProps) {
  const pageRef = useRef<HTMLDivElement>(null);
  useEntrance(pageRef, { preset: 'page' });
  const [setId, setSetId] = useState(initialPracticeSetId);
  const editing = useRef<PracticeEditingHandle | null>(null);
  const navigationGuard = useNavigationGuard();
  const pendingLeave = useRef<{ resolve: (allowed: boolean) => void } | null>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [leaveBusy, setLeaveBusy] = useState(false);
  const [leaveNotice, setLeaveNotice] = useState('');
  const leaveDialog = useRef<HTMLDialogElement>(null);
  const askLeave = useCallback((): Promise<boolean> => {
    const handle = editing.current;
    if (!handle || (!handle.dirty && !handle.busy && !handle.unknown)) return Promise.resolve(true);
    if (pendingLeave.current) return Promise.resolve(false);
    setLeaveNotice(handle.busy ? '操作仍在进行，请先取消离开并等待结果。' : handle.unknown ? '操作结果未知，请留在原练习并恢复原操作；不能直接放弃或当作已保存。' : '此练习有未保存输入，请明确处理后离开。');
    setLeaveOpen(true);
    return new Promise((resolve) => { pendingLeave.current = { resolve }; });
  }, []);
  const finishLeave = useCallback((allowed: boolean) => {
    pendingLeave.current?.resolve(allowed); pendingLeave.current = null;
    setLeaveOpen(false); setLeaveBusy(false);
    const dialog = leaveDialog.current;
    if (typeof dialog?.close === 'function') dialog.close();
    else dialog?.removeAttribute('open');
  }, []);
  useEffect(() => navigationGuard.register('practice-workspace', askLeave), [navigationGuard, askLeave]);
  useEffect(() => () => { pendingLeave.current?.resolve(false); pendingLeave.current = null; }, []);
  useEffect(() => {
    if (!leaveOpen) return;
    const dialog = leaveDialog.current;
    if (!dialog) return;
    if (typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
    else dialog.setAttribute('open', '');
    dialog.querySelector<HTMLButtonElement>('button')?.focus();
  }, [leaveOpen]);
  async function switchWithin(action: () => void) { if (await askLeave()) action(); }
  async function chooseLeave(choice: 'save' | 'keep' | 'discard') {
    const handle = editing.current;
    if (!handle) { finishLeave(true); return; }
    if (handle.busy || handle.unknown) { setLeaveNotice('请先取消离开并等待或重试原操作，当前内容保持。'); return; }
    setLeaveBusy(true);
    try {
      const allowed = choice === 'save' ? await handle.save() : choice === 'keep' ? handle.keep() : handle.discard();
      if (allowed) finishLeave(true);
      else { setLeaveNotice('操作未完成，输入和原练习保持。请取消离开，在工作区处理错误或未知结果。'); setLeaveBusy(false); }
    } catch { setLeaveNotice('处理失败，原练习与输入保持，请取消离开后重试。'); setLeaveBusy(false); }
  }

  const [fixedId, setFixedId] = useState(initialPracticeRevisionId);
  const [offset, setOffset] = useState(0);
  const [authoritative, setAuthoritative] = useState<PracticeSetView | null>(null);
  /** 练习列表状态筛选：默认只看 active；打开后不传 status（全部）。 */
  const [showArchived, setShowArchived] = useState(false);
  /** 二次确认的归档/恢复目标；确认前不发任何写请求。`title` 用于名称优先的回执提示。 */
  const [archiveTarget, setArchiveTarget] = useState<{ practiceSetId: string; revision: number; archived: boolean; title: string } | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState<ApiError | null>(null);
  const [archiveNotice, setArchiveNotice] = useState('');
  const archiveBusyRef = useRef(false);
  /** 二次确认的彻底删除目标；确认前不发任何写请求。 */
  const [deleteTarget, setDeleteTarget] = useState<{ practiceSetId: string; revision: number; title: string; archived: boolean } | null>(null);
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<ApiError | null>(null);
  const [deleteNotice, setDeleteNotice] = useState('');
  /** 被引用守卫拒绝的 409：逐项计数 + 「改为归档」快捷入口（乐观锁冲突/404 走既有错误区）。 */
  const [deleteGuard, setDeleteGuard] = useState<{ practiceSetId: string; error: ApiError; reasons: PracticeReferenceCount[] } | null>(null);
  const deleteBusyRef = useRef(false);
  /** 归档与彻底删除共用的存活标志：卸载后迟到的回执一律不写状态。 */
  const writeAlive = useRef(true);
  const [locks, setLocks] = useState({ create: false, workspace: false });
  const locked = Object.values(locks).some(Boolean);
  const createLock = useCallback((value: boolean) => setLocks((previous) => previous.create === value ? previous : { ...previous, create: value }), []);
  const workspaceLock = useCallback((value: boolean) => setLocks((previous) => previous.workspace === value ? previous : { ...previous, workspace: value }), []);
  const list = useAsyncResource((signal) => services.listPractices({ analysisRunId: initialAnalysisRunId ?? undefined, offset, limit: 20, ...(showArchived ? {} : { status: 'active' }) }, signal), `practices-list|${initialAnalysisRunId}|${offset}|${showArchived ? 'all' : 'active'}`);
  const source = useAsyncResource((signal) => initialAnalysisRunId && !setId ? services.getAnalysisRun(initialAnalysisRunId, signal) : Promise.resolve(null), `practices-create-source|${initialAnalysisRunId}|${setId}`);
  const current = useAsyncResource((signal) => setId ? services.getPractice(setId, signal) : Promise.resolve(null), `practices-current|${setId}`);
  const fixed = useAsyncResource((signal) => setId && fixedId ? services.getPracticeRevision(setId, fixedId, signal) : Promise.resolve(null), `practices-fixed|${setId}|${fixedId}`);
  const remote = current.lastData;
  const local = authoritative?.practiceSetId === setId ? authoritative : null;
  const view = local && (!remote || local.revision >= remote.revision) ? local : remote;
  const revision = fixedId ? fixed.lastData : view?.currentRevision;
  /** 归档练习只读：编辑/导出/转换入口按既有禁用模式置灰，后端也会 409。 */
  const archived = view?.practiceSetId === setId && view?.status === 'archived';
  function saved(next: PracticeSetView) {
    if (next.practiceSetId !== setId) return;
    setAuthoritative((previous) => previous?.practiceSetId === next.practiceSetId && (previous.revision > next.revision || (previous.revision === next.revision && previous.currentRevision.practiceRevisionId !== next.currentRevision.practiceRevisionId)) ? previous : next); list.reload();
  }
  useEffect(() => { writeAlive.current = true; return () => { writeAlive.current = false; }; }, []);
  /**
   * 归档/恢复练习集：带 expectedRevision 乐观锁；修订与既有产物原样保留。
   * 失败保留原目标与提示；结果未知时重按确认即重发同一请求（同一 setId 与 revision）。
   * 回执提示按名称优先用练习标题，不用 setId。
   */
  async function changeArchive(target: { practiceSetId: string; revision: number; archived: boolean; title: string }) {
    if (archiveBusyRef.current) return;
    archiveBusyRef.current = true;
    setArchiveBusy(true); setArchiveError(null); setArchiveNotice('');
    try {
      const body = { expectedRevision: target.revision };
      const result = target.archived ? await services.archivePracticeSet(target.practiceSetId, body) : await services.restorePracticeSet(target.practiceSetId, body);
      if (!writeAlive.current) return;
      if (result.practiceSetId !== target.practiceSetId) throw new ApiError('PRACTICE_ARCHIVE_IDENTITY_MISMATCH', '归档回执与目标练习不一致，未刷新列表。', 500, false);
      setArchiveTarget(null);
      setArchiveNotice(target.archived ? `已归档练习「${target.title}」：不能编辑/导出/转为施测，历史修订与既有产物保留。` : `已恢复练习「${target.title}」：可继续编辑、导出与转换为施测。`);
      list.reload();
      if (setId === target.practiceSetId) current.reload();
    } catch (cause) {
      if (writeAlive.current) setArchiveError(asApiError(cause));
    } finally { archiveBusyRef.current = false; if (writeAlive.current) setArchiveBusy(false); }
  }
  /**
   * 彻底删除练习（受引用守卫的物理删除，二次确认；已归档练习同样受同一守卫）：
   * 有已审核版本/导出/转换任一引用时 409 `PRACTICE_IN_USE`，逐项显示计数并给「改为归档」；
   * 乐观锁冲突 / 404 走既有错误区；成功刷新列表并清空当前选择。
   */
  async function deleteSet(target: { practiceSetId: string; revision: number; title: string }) {
    if (deleteBusyRef.current) return;
    deleteBusyRef.current = true;
    setDeleteBusyId(target.practiceSetId); setDeleteError(null); setDeleteNotice(''); setDeleteGuard(null);
    try {
      const receipt = await services.deletePracticeSet(target.practiceSetId, target.revision);
      if (!writeAlive.current) return;
      if (!receipt.deleted || receipt.practiceSetId !== target.practiceSetId) throw new ApiError('PRACTICE_DELETE_IDENTITY_MISMATCH', '删除回执与目标练习不一致，未刷新列表。', 500, false);
      setDeleteTarget(null);
      if (setId === target.practiceSetId) { setSetId(null); setFixedId(null); setAuthoritative(null); }
      setDeleteNotice(`已彻底删除练习「${target.title}」：物理删除完成，不可恢复。`);
      list.reload();
    } catch (cause) {
      if (!writeAlive.current) return;
      const error = asApiError(cause);
      if (error.status === 409 && error.code === 'PRACTICE_IN_USE') {
        setDeleteGuard({ practiceSetId: target.practiceSetId, error, reasons: practiceReferenceCounts(error.details) });
      } else setDeleteError(error);
    } finally { deleteBusyRef.current = false; if (writeAlive.current) setDeleteBusyId(null); }
  }
  /** 被引用不能物理删除时改走归档（不删除历史）：复用同一乐观锁守卫的归档通道。 */
  async function archiveFromGuard(target: { practiceSetId: string; revision: number; title: string }) {
    setDeleteGuard(null); setDeleteTarget(null);
    await changeArchive({ practiceSetId: target.practiceSetId, revision: target.revision, archived: true, title: target.title });
  }
  return <div ref={pageRef} className="space-page practices-page"><header className="space-header" data-motion-reveal><h1>针对练习</h1><p className="space-description">依据固定学情报告选正式题，复核计分结构并独立审核，导出后转换施测，再用新成绩回流。</p></header><main className="space-content">
    {!setId && initialPracticeRevisionId && <p className="space-banner error" role="alert">固定练习修订需要对应练习ID，入口不完整，不会猜测当前练习。</p>}
    {!setId && initialAnalysisRunId && <><ReadNotice resource={source} label="练习来源报告" />{source.lastData && <CreatePracticeForm run={source.lastData} services={services} onLocked={createLock} onCreated={(next) => { setAuthoritative(next); setSetId(next.practiceSetId); setFixedId(null); list.reload(); }} />}</>}
    <section className="b4-section" aria-label="练习列表" data-motion-reveal><h2>练习列表</h2><ReadNotice resource={list} label="练习列表" />
      <label><input type="checkbox" aria-label="显示已归档" checked={showArchived} disabled={locked} onChange={(event) => { setShowArchived(event.target.checked); setOffset(0); setArchiveTarget(null); setArchiveError(null); setArchiveNotice(''); setDeleteTarget(null); setDeleteGuard(null); setDeleteError(null); setDeleteNotice(''); }} />显示已归档</label>
      <p className="b4-hint">{showArchived ? '当前不筛选练习状态：同时列出进行中与已归档练习，便于核对与恢复。' : '当前只看进行中的练习；已归档练习不出现在这里，可用上方开关查看。'}</p>
      {archiveNotice && <p className="b4-hint" role="status">{archiveNotice}</p>}
      {deleteNotice && <p className="b4-hint" role="status" data-testid="practices-delete-notice">{deleteNotice}</p>}
      <ErrorNotice error={archiveError} />
      <ErrorNotice error={deleteError} />
      {(archiveError || deleteError) && <button className="space-button" onClick={list.reload}>刷新列表对照服务器</button>}
      {list.state.phase === 'ready' && list.lastData?.items.length === 0 && <p>还没有练习。请从已准备好的学情报告明确选择目标知识点。</p>}
      <div className="b4-list">{list.lastData?.items.map((item) => <Fragment key={item.practiceSetId}>
        <button className={`space-button${setId === item.practiceSetId ? ' primary' : ''}`} title={`练习 ${item.practiceSetId} · 当前修订 ${item.currentRevision.practiceRevisionId} · 来源报告 ${item.analysisRunId}`} disabled={locked} onClick={() => void switchWithin(() => { setSetId(item.practiceSetId); setFixedId(null); setAuthoritative(null); })}>
          {item.title}<span className="b4-meta">练习 {shortId(item.practiceSetId)} · {item.currentRevision.state === 'reviewed' ? '已审核' : '草稿'} · 来源报告 {practiceSourceLabel(item)}</span>
        </button>
        <div className="b4-actions">
          <button className="space-button" disabled={locked || archiveBusy || deleteBusyId !== null} onClick={() => setArchiveTarget({ practiceSetId: item.practiceSetId, revision: item.revision, archived: item.status !== 'archived', title: item.title })}>{item.status === 'archived' ? '恢复' : '归档'}</button>
          <button className="space-button danger" data-testid={`practices-delete-${item.practiceSetId}`} disabled={locked || archiveBusy || deleteBusyId !== null} onClick={() => { setDeleteTarget({ practiceSetId: item.practiceSetId, revision: item.revision, title: item.title, archived: item.status === 'archived' }); setDeleteNotice(''); setDeleteError(null); setDeleteGuard(null); }}>{deleteBusyId === item.practiceSetId ? '删除中…' : '彻底删除'}</button>
          {item.status === 'archived' && <span className="space-chip amber">已归档</span>}
          {archiveTarget?.practiceSetId === item.practiceSetId && <>
            <span className="b4-hint" role="alert">{archiveTarget.archived ? '归档后不能编辑/导出/转为施测，历史修订与既有产物保留；恢复后即可继续。' : '恢复后可继续编辑、导出与转换为施测，内容与修订保持原样。'}</span>
            <button className="space-button primary" disabled={archiveBusy} onClick={() => void changeArchive({ practiceSetId: item.practiceSetId, revision: item.revision, archived: archiveTarget.archived, title: archiveTarget.title })}>{archiveBusy ? '正在提交…' : archiveTarget.archived ? '确认归档' : '确认恢复'}</button>
            <button className="space-button" disabled={archiveBusy} onClick={() => setArchiveTarget(null)}>取消</button>
          </>}
          {deleteTarget?.practiceSetId === item.practiceSetId && <>
            <span className="b4-hint" role="alert">彻底删除「{deleteTarget.title}」是物理删除、不可恢复；已审核/已导出/已转换的练习会被拒绝并逐项列出原因{deleteTarget.archived ? '；已归档练习同样受该守卫，不会因归档而可删' : ''}。</span>
            <button className="space-button danger" disabled={deleteBusyId !== null} onClick={() => void deleteSet({ practiceSetId: deleteTarget.practiceSetId, revision: deleteTarget.revision, title: deleteTarget.title })}>{deleteBusyId === item.practiceSetId ? '删除中…' : '确认彻底删除'}</button>
            <button className="space-button" disabled={deleteBusyId !== null} onClick={() => setDeleteTarget(null)}>取消</button>
          </>}
          {deleteGuard?.practiceSetId === item.practiceSetId && <div className="space-banner error" role="alert" data-testid="practices-delete-guard">
            <p>不能彻底删除「{item.title}」（{deleteGuard.error.code}）：{deleteGuard.error.message}</p>
            {deleteGuard.reasons.length > 0
              ? <><p>还有 {deleteGuard.reasons.length} 类下游数据引用它：</p><ul className="practice-reference-list" aria-label="引用原因清单">{deleteGuard.reasons.map((reason) => <li key={reason.key}>{reason.label} {reason.count} 条</li>)}</ul></>
              : <p className="b4-hint">服务端未给出逐项引用计数；请先处理相关数据，或改为归档保证历史完整。</p>}
            {item.status !== 'archived' && <div className="b4-actions"><button className="space-button" disabled={archiveBusy} onClick={() => void archiveFromGuard({ practiceSetId: item.practiceSetId, revision: item.revision, title: item.title })}>{archiveBusy ? '归档中…' : '改为归档（不删除历史）'}</button></div>}
          </div>}
        </div>
      </Fragment>)}</div><Pagination page={list.lastData} offset={offset} onOffset={setOffset} disabled={locked} />
      <GuardedLink className="space-button" href="/learning-analysis">选择学情报告创建练习</GuardedLink>
    </section>
    {setId && <ReadNotice resource={current} label="所选练习" />}
    {setId && fixedId && <ReadNotice resource={fixed} label="固定练习修订" />}
    {view && view.practiceSetId === setId && <>
      <div className="b4-chain">
        <GuardedLink href={`/learning-analysis?runId=${encodeURIComponent(view.analysisRunId)}`}>来源报告 {practiceSourceLabel(view)}</GuardedLink>
        <span title={`练习 ${view.practiceSetId}`}>→ 练习 {view.title}</span>
        <span className="b4-meta" title={revision ? `练习修订 ${revision.practiceRevisionId}` : undefined}>{revision ? `${revision.state === 'reviewed' ? '审核' : '草稿'} v${revision.version} · ${shortId(revision.practiceRevisionId)}` : '读取修订中'}</span>
      </div>
      {archived && <p className="space-banner" role="status"><span className="space-chip amber">已归档</span> 该练习已归档：编辑、导出与转换为施测入口已禁用以保持归档内容不被改写；历史修订与既有产物保留。先在列表恢复后可继续。</p>}
      <section className="b4-section" aria-label="练习修订历史"><h2>固定修订历史</h2><div className="b4-actions"><button className="space-button" disabled={locked} onClick={() => void switchWithin(() => setFixedId(null))}>当前工作区</button><button className="space-button" disabled={locked} onClick={current.reload}>刷新服务器练习</button></div>
        <div className="b4-list">{view.revisions.map((item) => <button className="space-button" disabled={locked} key={item.practiceRevisionId} title={`练习修订 ${item.practiceRevisionId}`} onClick={() => void switchWithin(() => setFixedId(item.practiceRevisionId))}>v{item.version} · {item.state === 'reviewed' ? '已审核，只读' : '草稿'}<span className="b4-meta">{shortId(item.practiceRevisionId)} · {item.reviewedAt ?? item.createdAt}</span></button>)}</div>
      </section>
      {revision && revision.practiceSetId !== setId && <p className="space-banner error" role="alert">修订归属与当前练习不一致，未显示其他练习内容。</p>}
      {revision && revision.practiceSetId === setId && <PracticePane key={`${setId}|${fixedId ?? 'current'}`} view={view} revision={revision} services={services} onSaved={saved} onNewDraft={(next) => { saved(next); setFixedId(null); }} onLocked={workspaceLock} sessionHandle={editing} editable={!fixedId && revision.state === 'draft' && !archived} archived={archived} />}
    </>}
    {leaveOpen && <dialog ref={leaveDialog} className="practice-leave-dialog" aria-label="处理未保存练习" onCancel={(event) => { event.preventDefault(); if (!leaveBusy) finishLeave(false); }}>
      <h2>离开当前练习前</h2><p role="status">{leaveNotice}</p>
      <p>保留恢复稿后，返回此练习会恢复分值、选题、节点和约束；固定历史只读。明确放弃才删除此练习恢复稿。</p>
      <div className="b4-actions"><button className="space-button" disabled={leaveBusy} onClick={() => finishLeave(false)}>取消并继续编辑</button>
        <button className="space-button primary" disabled={leaveBusy || editing.current?.busy || editing.current?.unknown} onClick={() => void chooseLeave('save')}>保存成功后离开</button>
        <button className="space-button" disabled={leaveBusy || editing.current?.busy || editing.current?.unknown} onClick={() => void chooseLeave('keep')}>保留恢复稿并离开</button>
        <button className="space-button" disabled={leaveBusy || editing.current?.busy || editing.current?.unknown} onClick={() => void chooseLeave('discard')}>明确放弃修改并离开</button></div>
    </dialog>}
  </main></div>;
}

function PracticePane({ view, revision, services, onSaved, onNewDraft, onLocked, sessionHandle, editable, archived }: {
  view: PracticeSetView; revision: PracticeRevisionView; services: typeof b4Api;
  onSaved: (view: PracticeSetView) => void; onNewDraft: (view: PracticeSetView) => void; onLocked: (locked: boolean) => void; sessionHandle: MutableRefObject<PracticeEditingHandle | null>; editable: boolean; archived: boolean;
}) {
  const [converted, setConverted] = useState<PracticeConversionReceipt | null>(null);
  const [locks, setLocks] = useState({ editor: false, exports: false, conversion: false, copy: false });
  const editorLock = useCallback((value: boolean) => setLocks((previous) => previous.editor === value ? previous : { ...previous, editor: value }), []);
  const exportsLock = useCallback((value: boolean) => setLocks((previous) => previous.exports === value ? previous : { ...previous, exports: value }), []);
  const conversionLock = useCallback((value: boolean) => setLocks((previous) => previous.conversion === value ? previous : { ...previous, conversion: value }), []);
  const copy = useFrozenSubmission<PracticeRevisionRequest, PracticeSetView>();
  const anyLocked = Object.values(locks).some(Boolean) || copy.busy || copy.phase === 'unknown';
  useEffect(() => { onLocked(anyLocked); return () => onLocked(false); }, [anyLocked, onLocked]);
  async function newDraft() {
    const result = await copy.submit({ submissionId: '', sourceRevisionId: revision.practiceRevisionId }, (frozen) => services.createPracticeRevision(view.practiceSetId, { ...frozen.payload, submissionId: frozen.submissionId }));
    if (result) onNewDraft(result);
  }
  return <>
    <section className="b4-section" aria-label="固定练习概要"><h2>{revision.title}</h2><p>目标：{revision.targetKnowledgePoints.map((point) => point.name).join('、')}</p><p className="b4-meta" title={`分析运行 ${revision.analysisRunId} · 练习修订 ${revision.practiceRevisionId}`}>来源报告 {practiceSourceLabel(revision)} · 练习修订 {shortId(revision.practiceRevisionId)} · 后端总分 {scoreText(revision.totalScoreUnits)}分</p></section>
    {editable && <PracticeEditor view={view} services={services} onSaved={onSaved} onLocked={editorLock} sessionHandle={sessionHandle} />}
    <PracticeContents revision={revision} services={services} />
    {revision.state === 'reviewed' && <>
      <section className="b4-section" aria-label="从审核版建立草稿"><h2>审核版只读</h2><p className="b4-hint">修改需要从此固定版本建立新草稿，旧导出与施测继续使用旧内容。</p>{archived && <p className="space-banner" role="status">该练习已归档：建立新草稿的入口已禁用，恢复后可继续。</p>}<SubmissionNotice submission={copy} /><button className="space-button" disabled={archived || copy.busy || locks.exports || locks.conversion} onClick={() => void newDraft()}>{copy.phase === 'unknown' ? '重试原新草稿提交' : '从此审核版建立新草稿'}</button></section>
      <PracticeConversion key={`conversion|${revision.practiceRevisionId}`} revision={revision} services={services} onLocked={conversionLock} onConverted={setConverted} disabled={archived} />
      <PracticeExports key={`exports|${revision.practiceRevisionId}`} revision={revision} services={services} convertedAssessmentId={converted?.practiceRevisionId === revision.practiceRevisionId ? converted.assessmentId : null} onLocked={exportsLock} disabled={archived} />
    </>}
    {!editable && revision.state === 'draft' && (archived
      ? <p className="b4-hint">该练习已归档：编辑入口已禁用以保持归档内容不被改写，恢复后可继续编辑；历史修订保留。</p>
      : <p className="b4-hint">此处查看固定草稿。请点击“当前工作区”编辑当前草稿，不会改写历史修订。</p>)}
  </>;
}

function PracticeContents({ revision, services }: { revision: PracticeRevisionView; services: typeof b4Api }) {
  return <section className="b4-section" aria-label="服务端完整练习审阅"><h2>完整题目与计分叶审阅</h2>
    <p className="b4-hint">{revision.state === 'reviewed' ? '固定审核内容' : '服务端已保存内容'}；新编辑需保存后在这里复核。共同材料、父子题、答案解析与受管图片保持来源。</p>
    {revision.items.length === 0 && <p>尚无服务端题面快照。请先保存合法草稿，再审阅完整题面并独立审核。</p>}
    {revision.items.map((item) => <FixedItemContent key={item.practiceItemId} revision={revision} item={item} services={services} />)}
  </section>;
}

function FixedItemContent({ revision, item, services }: { revision: PracticeRevisionView; item: PracticeRevisionView['items'][number]; services: typeof b4Api }) {
  const loadAsset = useCallback(async (assetId: string, signal: AbortSignal) => {
    const declaration = item.content.assets.find((asset) => asset.assetId === assetId);
    if (!declaration) throw new Error('图片未在此固定修订中声明。');
    return (await services.getPracticeAsset(revision.practiceSetId, revision.practiceRevisionId, declaration.sha256, signal)).blob;
  }, [item.content.assets, revision.practiceSetId, revision.practiceRevisionId, services]);
  return <details><summary>{item.questionNo} · {item.isScored ? `计分叶，满分${scoreText(item.maxScoreUnits)}分` : '父题 / 材料，不计分'} · {item.knowledgePoints.map((point) => point.name).join('、')}</summary>
    <span className="b4-meta">题修订 {item.questionRevisionId} · 节点 {item.nodeKey} · 父题 {item.parentItemId ?? '无'} · 来源 {item.reason}</span><RichReview content={item.content} loadAsset={loadAsset} assetScope={`${revision.practiceRevisionId}|${item.practiceItemId}`} />
    <p className="b4-meta">固定知识点：{item.knowledgePoints.map((point) => `${point.name}（${point.knowledgeRevisionId}）`).join('、')}</p>
  </details>;
}

export default PracticesWorkspace;
