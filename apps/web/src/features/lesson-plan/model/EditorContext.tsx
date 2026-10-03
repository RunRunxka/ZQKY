'use client';
import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useStore } from 'zustand';
import { createLessonStore } from './store';
import { useDraftPersistence } from './useDraftPersistence';
import type { FillProposal, TextField, LessonPlanServices, LessonPlanData } from './types';
import { useServerPersistence, type ServerBinding } from './useServerPersistence';
import type { LessonRevisionView } from '@/contracts/lesson-plans';
import { localDraftRepository, makeEnvelope } from '../services/drafts';
import { RuleBasedFillProvider } from '../services/fill';
import { download, exportDocx, safeName } from '../services/export';
import { sections } from './sections';
const fallbackProvider = new RuleBasedFillProvider();
const emptyServices: LessonPlanServices = {};
export interface EditorMode { server?: ServerBinding; history?: LessonRevisionView }
function useEditorController(services: LessonPlanServices, session: EditorMode) {
  const [store] = useState(() => createLessonStore(session.history?.data ?? session.server?.view.currentRevision.data));
  const repository = services.repository ?? localDraftRepository,
    provider = services.fillProvider ?? fallbackProvider;
  const { data, set, replace, undo, redo, past, future, revision } = useStore(store);
  const [active, setActive] = useState('basic'),
    [layoutTab, setLayoutTab] = useState<'outline' | 'style'>('outline'),
    [editorTab, setEditorTab] = useState<'form' | 'fill'>('form');
  const [collapsed, setCollapsed] = useState(false),
    [focusMode, setFocusMode] = useState(false),
    [mobileView, setMobileView] = useState<'edit' | 'preview'>('edit');
  const [fontSize, setFontSize] = useState(14),
    [toast, setToast] = useState(''),
    [busy, setBusy] = useState(false),
    [exportOpen, setExportOpen] = useState(false);
  const [input, setInput] = useState(''),
    [proposal, setProposal] = useState<FillProposal | null>(null),
    [mode, setMode] = useState<'overwrite' | 'append'>('overwrite');
  const [modal, setModal] = useState<'new' | 'pdf' | null>(null);
  const [printSnapshot, setPrintSnapshot] = useState<{ data: LessonPlanData; source: string } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null),
    fileInput = useRef<HTMLInputElement>(null);
  const notice = useCallback((message: string) => setToast(message), []);
  const local = useDraftPersistence(
    store,
    repository,
    notice,
    services.onChange,
    !session.server && !session.history,
  );
  const server = useServerPersistence(store, session.server);
  const ready = session.history ? true : session.server ? server.ready : local.ready;
  const saveStatus = session.history ? '固定历史只读' : session.server ? ({ idle: '后台稿有未保存编辑', saving: '正在保存后台稿', saved: '后台稿已保存', failed: '后台保存失败', conflict: '后台版本冲突', unknown: '后台操作结果未知', cache_error: '恢复缓存失败' }[server.syncState]) : local.saveStatus;
  const storageBlocked = session.server ? server.syncState === 'cache_error' : local.storageBlocked;
  const resumeStorage = local.resumeStorage;
  const flushDraft = session.server ? server.flush : local.flushDraft;
  const editingLocked = !!session.history || !!printSnapshot || (session.server && (server.exclusive || server.syncState === 'cache_error'));
  const sourceLabel = session.history ? `历史固定 v${session.history.version} · ${session.history.revisionId}` : session.server ?
    `${server.syncState === 'conflict' ? '冲突稿 · ' : ''}${server.dirty ? `未保存编辑 r${revision}，基于` : '后台固定'} v${server.cache?.serverRevision ?? session.server.view.revision} · ${server.cache?.serverRevisionId ?? session.server.view.currentRevisionId}` : `本地编辑 r${revision}`;
  const editedSet: typeof set = (patch) => { if (!editingLocked) set(patch); };
  const editedReplace = (next: LessonPlanData) => { if (!editingLocked) replace(next); };
  const editedUndo = () => { if (!editingLocked) undo(); };
  const editedRedo = () => { if (!editingLocked) redo(); };
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (modal) dialog.current?.showModal();
    else dialog.current?.close();
  }, [modal]);
  useEffect(() => { const after = () => setPrintSnapshot(null); window.addEventListener('afterprint', after); return () => window.removeEventListener('afterprint', after); }, []);
  const selectSection = (id: string) => {
    setActive(id);
    setEditorTab('form');
    setMobileView('edit');
    setTimeout(
      () =>
        document
          .getElementById(`field-${id}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      30,
    );
  };
  const completed = (id: string) => {
    const section = sections.find((s) => s.id === id)!;
    if (id === 'basic') return !!data.title.trim();
    if (id === 'process')
      return (
        data.process.length > 0 && data.process.every((p) => p.stage.trim() && p.design.trim())
      );
    return 'field' in section && !!data[section.field].trim();
  };
  const completeCount = sections.filter((s) => completed(s.id)).length;
  const updateText = (field: TextField, value: string) => editedSet({ [field]: value });
  const updateProcess = (id: string, patch: Record<string, string>) =>
    editedSet({ process: data.process.map((p) => (p.id === id ? { ...p, ...patch } : p)) });
  const reorder = (index: number, delta: number) => {
    const next = [...data.process];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    editedSet({ process: next });
  };
  const parse = async () => {
    setBusy(true);
    setProposal(null);
    try {
      const result = await provider.parse(input);
      setProposal(result);
      if (!Object.keys(result.patch).length) notice('暂未识别到可填充字段，请参照输入示例。');
    } catch (e) {
      notice(`解析失败：${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };
  const docx = async () => {
    setExportOpen(false);
    setBusy(true);
    try {
      await exportDocx(structuredClone(data), sourceLabel);
      notice('Word 文件已生成');
    } catch (e) {
      notice(`导出失败：${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };
  const backup = () => {
    download(
      new Blob([JSON.stringify(makeEnvelope(data, revision), null, 2)], {
        type: 'application/json',
      }),
      `教案-${safeName(data.title)}-${safeName(sourceLabel)}.json`,
    );
    setExportOpen(false);
    notice('草稿备份已生成');
  };
  return {
    data,
    set: editedSet,
    replace: editedReplace,
    undo: editedUndo,
    redo: editedRedo,
    store,
    server: session.server ? server : null,
    history: session.history ?? null,
    editingLocked: !!editingLocked,
    sourceLabel,
    printSnapshot,
    beginPrint: () => { const snapshot = { data: structuredClone(data), source: sourceLabel }; setPrintSnapshot(snapshot); return snapshot; },
    endPrint: () => setPrintSnapshot(null),
    localPending: local.isPending,
    localRunning: local.isRunning,
    discardLocal: local.discardPending,
    past,
    future,
    revision,
    active,
    setActive,
    layoutTab,
    setLayoutTab,
    editorTab,
    setEditorTab,
    collapsed,
    setCollapsed,
    focusMode,
    setFocusMode,
    mobileView,
    setMobileView,
    saveStatus,
    ready,
    fontSize,
    setFontSize,
    toast,
    setToast,
    busy,
    exportOpen,
    setExportOpen,
    input,
    setInput,
    proposal,
    setProposal,
    mode,
    setMode,
    modal,
    setModal,
    storageBlocked,
    resumeStorage,
    flushDraft,
    dialog,
    fileInput,
    notice,
    selectSection,
    completed,
    completeCount,
    updateText,
    updateProcess,
    reorder,
    parse,
    docx,
    backup,
  };
}
const EditorContext = createContext<ReturnType<typeof useEditorController> | null>(null);
export function LessonPlanProvider({
  children,
  services = emptyServices,
  session = {},
}: {
  children: ReactNode;
  services?: LessonPlanServices;
  session?: EditorMode;
}) {
  const editor = useEditorController(services, session);
  return <EditorContext.Provider value={editor}>{children}</EditorContext.Provider>;
}
export function useLessonEditor() {
  const editor = useContext(EditorContext);
  if (!editor) throw Error('LessonPlanProvider is required');
  return editor;
}
