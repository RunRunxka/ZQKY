'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigationGuard } from '@/services/navigation-guard';
import { useLessonEditor } from '../model/EditorContext';
import { useLessonDocument } from '../model/DocumentContext';
export function LeaveProtection() {
  const editor = useLessonEditor(), doc = useLessonDocument(), { register } = useNavigationGuard();
  const leaveRef = doc.leave;
  const current = useRef({ editor, doc }); current.current = { editor, doc };
  const active = useRef(false), epoch = useRef(0), flushing = useRef(false);
  const resolver = useRef<((permitted: boolean) => void) | null>(null), promise = useRef<Promise<boolean> | null>(null), dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false), [error, setError] = useState(''), [saving, setSaving] = useState(false);
  const ask = useCallback(async (): Promise<boolean> => {
    if (!active.current) return false;
    const origin = current.current, token = epoch.current;
    let { editor: now, doc: document } = origin;
    if (now.printSnapshot) { now.notice('打印快照处理中，请完成打印后切换'); return false; }
    if (promise.current) return promise.current;
    if (flushing.current) return false;
    const isCurrent = () => active.current && epoch.current === token && current.current.editor.store === origin.editor.store && current.current.doc.mode === origin.doc.mode && current.current.doc.documentId === origin.doc.documentId;
    const canFlushLocal = () => document.mode === 'local' && !now.server && !now.history && !now.storageBlocked && !now.printSnapshot && !document.pendingOperation.current.busy && !document.pendingOperation.current.unknown;
    let failure = '';
    if (canFlushLocal() && now.localPending()) {
      flushing.current = true; setSaving(true);
      try {
        do {
          try { await now.flushDraft(); }
          catch (cause) { failure = `保存失败，当前教案保持：${(cause as Error).message}`; }
          if (!isCurrent()) return false;
          ({ editor: now, doc: document } = current.current);
        } while (!failure && canFlushLocal() && now.localPending());
      } finally { if (epoch.current === token) { flushing.current = false; if (active.current) setSaving(false); } }
      if (now.printSnapshot) { now.notice('打印快照处理中，请完成打印后切换'); return false; }
    }
    if (!failure && !(now.server?.dirty || now.server?.unknown || now.server?.busy || now.localPending() || now.storageBlocked || document.pendingOperation.current.busy || document.pendingOperation.current.unknown)) return true;
    setOpen(true); setError(failure); promise.current = new Promise<boolean>((resolve) => { resolver.current = resolve; }); return promise.current;
  }, []);
  function finish(permitted: boolean) { resolver.current?.(permitted); resolver.current = null; promise.current = null; setOpen(false); }
  useEffect(() => { active.current = true; leaveRef.current = ask; const unregister = register(`lesson-workspace|${doc.documentId ?? 'local'}`, ask); return () => { active.current = false; epoch.current += 1; flushing.current = false; if (leaveRef.current === ask) leaveRef.current = null; unregister(); resolver.current?.(false); resolver.current = null; promise.current = null; }; }, [ask, register, leaveRef, doc.documentId]);
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  const busy = editor.server?.busy || editor.localRunning() || doc.pendingOperation.current.busy || saving;
  const unknown = editor.server?.unknown || doc.pendingOperation.current.unknown;
  return <dialog className="modal lesson-leave-dialog" ref={dialog} aria-labelledby="lesson-leave-title" onCancel={(event) => { event.preventDefault(); finish(false); }}>
    <h2 id="lesson-leave-title">离开当前教案</h2><p>当前输入或原操作需要保留。请选择如何处理后再切换文档、历史或页面。</p>
    {unknown && <p role="status">原操作结果未知；请重试原包后再保存或放弃。</p>}{error && <p role="alert">{error}</p>}
    <div className="modal-actions">
      <button className="button subtle" onClick={() => finish(false)}>取消离开，继续编辑</button>
      <button className="button primary" disabled={!!busy || !!unknown || editor.storageBlocked} onClick={async () => { setSaving(true); try { await editor.flushDraft(); finish(true); } catch (cause) { setError(`保存失败，当前教案保持：${(cause as Error).message}`); } finally { setSaving(false); } }}>保存成功后离开</button>
      <button className="button subtle" disabled={!!busy || editor.storageBlocked} onClick={async () => { try { if (editor.server ? editor.server.keep() : (await editor.flushDraft(), true)) finish(true); else setError('恢复缓存未能写入，当前输入保持'); } catch (cause) { setError(`保留失败：${(cause as Error).message}`); } }}>保留恢复缓存后离开</button>
      <button className="button subtle" disabled={!!busy || !!unknown || editor.storageBlocked} onClick={() => { if (editor.server ? editor.server.discard() : editor.discardLocal()) finish(true); else setError('暂时无法放弃，在途操作与当前输入保持'); }}>明确放弃未保存编辑后离开</button>
    </div>
  </dialog>;
}
