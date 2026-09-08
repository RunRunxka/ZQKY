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
import type { FillProposal, TextField, LessonPlanServices } from './types';
import { localDraftRepository, makeEnvelope } from '../services/drafts';
import { RuleBasedFillProvider } from '../services/fill';
import { download, exportDocx, safeName } from '../services/export';
import { sections } from './sections';
const fallbackProvider = new RuleBasedFillProvider();
const emptyServices: LessonPlanServices = {};
function useEditorController(services: LessonPlanServices) {
  const [store] = useState(() => createLessonStore());
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
  const dialog = useRef<HTMLDialogElement>(null),
    fileInput = useRef<HTMLInputElement>(null);
  const notice = useCallback((message: string) => setToast(message), []);
  const { ready, saveStatus, storageBlocked, resumeStorage, flushDraft } = useDraftPersistence(
    store,
    repository,
    notice,
    services.onChange,
  );
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (modal) dialog.current?.showModal();
    else dialog.current?.close();
  }, [modal]);
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
  const updateText = (field: TextField, value: string) => set({ [field]: value });
  const updateProcess = (id: string, patch: Record<string, string>) =>
    set({ process: data.process.map((p) => (p.id === id ? { ...p, ...patch } : p)) });
  const reorder = (index: number, delta: number) => {
    const next = [...data.process];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    set({ process: next });
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
      await exportDocx(data);
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
      `教案-${safeName(data.title)}.json`,
    );
    setExportOpen(false);
    notice('草稿备份已生成');
  };
  return {
    data,
    set,
    replace,
    undo,
    redo,
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
}: {
  children: ReactNode;
  services?: LessonPlanServices;
}) {
  const editor = useEditorController(services);
  return <EditorContext.Provider value={editor}>{children}</EditorContext.Provider>;
}
export function useLessonEditor() {
  const editor = useContext(EditorContext);
  if (!editor) throw Error('LessonPlanProvider is required');
  return editor;
}
