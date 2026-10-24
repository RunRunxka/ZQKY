'use client';
/**
 * 教案工作台（R12，magic-resume 形态的三栏沉浸式编辑器）。
 *
 * 形态：64px 顶栏（课题名 + 保存状态 + 撤销/重做/本地教案/导出）+ 三栏（模块轨与排版 /
 * 当前模块表单与 AI 生成 / A4 校样台）+ 右侧悬浮 dock；列宽可拖拽、可折叠、各自滚动。
 *
 * 数据：正文/排版/模块全部进本地草稿（浏览器）+ 本机后端（数据目录 `.local-data`，不联网）；
 * 保存走可选 `PATCH /draft` CAS 同步；AI 只产候选，教师「采用」才进草稿；导出由后端组装，
 * 前端只触发 + 下载，并把预览算出的正文页码随请求发给后端，保证目录页码一致。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from 'zustand';
import { motion, useReducedMotion } from 'framer-motion';
import { Cloud, Download, LoaderCircle, NotebookPen, PanelLeft, PenLine, Redo2, ScanEye, Undo2 } from 'lucide-react';
import { lessonPlansApi, uploadLessonSource, type LessonPlansApi } from '@/services/lesson-plans-api';
import { ApiError } from '@/services/api-client';
import { useNavigationGuard } from '@/services/navigation-guard';
import { createLessonWorkbenchStore } from './model/store';
import { emptyLessonData } from './model/lesson-data';
import { DEFAULT_LESSON_STYLE, defaultModuleLayout, modulesToWire } from './model/modules';
import { useLessonLocalDraft } from './model/useLessonLocalDraft';
import {
  readOwnership,
  safeBrowserStorage,
  writeOwnership,
  type LessonOwnership,
} from './model/draft-storage';
import { reasonOf, useLessonServer } from './model/useLessonServer';
import { mergeCandidateData, parseModuleText } from './services/fill-parsers';
import { ColumnSplitter } from './components/ColumnSplitter';
import { LayoutPanel, StylePanel } from './components/LeftPanels';
import { ModuleEditor } from './components/ModuleEditor';
import { GeneratePanel, type GeneratePanelServices } from './components/GeneratePanel';
import { PaperPreview } from './components/PaperPreview';
import { LessonsDialog } from './components/LessonsDialog';
import { PreviewDock } from './components/PreviewDock';
import { TooltipProvider } from './components/Tooltip';
import { WorkbenchHelp } from './components/WorkbenchHelp';
import { WorkbenchNotices, type WorkbenchNotice } from './components/WorkbenchNotices';
import './styles/lesson-fonts.css';
import './styles/lesson-workbench.css';
import { SlidingGroup } from '@/components/ui/SlidingGroup';

type MobilePane = 'layout' | 'edit' | 'preview';
type PanelKey = 'layout' | 'editor' | 'preview';

const COLUMN_LIMITS = {
  left: { min: 15, max: 34, initial: 20 },
  mid: { min: 24, max: 44, initial: 32 },
  /** 左 + 中 的上限（右栏至少 36%）。 */
  combinedMax: 64,
} as const;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function LessonWorkbench({
  api = lessonPlansApi,
  uploadSource = uploadLessonSource,
  generateServices,
}: {
  api?: LessonPlansApi;
  uploadSource?: typeof uploadLessonSource;
  generateServices?: GeneratePanelServices;
}) {
  const [store] = useState(() => createLessonWorkbenchStore());
  const data = useStore(store, (state) => state.data);
  const modules = useStore(store, (state) => state.modules);
  const removed = useStore(store, (state) => state.removed);
  const style = useStore(store, (state) => state.style);
  const activeModuleId = useStore(store, (state) => state.activeModuleId);
  const candidate = useStore(store, (state) => state.candidate);
  const canUndo = useStore(store, (state) => state.past.length > 0);
  const canRedo = useStore(store, (state) => state.future.length > 0);

  const local = useLessonLocalDraft(store);
  const serverSync = useLessonServer({ store, api, uploadSource });
  const reduceMotion = useReducedMotion();
  const [columns, setColumns] = useState<{ left: number; mid: number }>({
    left: COLUMN_LIMITS.left.initial,
    mid: COLUMN_LIMITS.mid.initial,
  });
  const [panels, setPanels] = useState<Record<PanelKey, boolean>>({ layout: true, editor: true, preview: true });
  const [mobilePane, setMobilePane] = useState<MobilePane>('edit');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [dismissed, setDismissed] = useState<string[]>([]);
  /** 教案删除回执（R10-FE）：对话框内删除成功后，关掉对话框仍能看到结果 */
  const [lessonDeletedNotice, setLessonDeletedNotice] = useState<string | null>(null);
  const [exportState, setExportState] = useState<{
    status: 'idle' | 'busy' | 'ok' | 'error';
    message?: string;
  }>({ status: 'idle' });
  const generateRef = useRef<HTMLDivElement>(null);

  const navigation = useNavigationGuard();

  /**
   * 教案归属（学科 + 班级）：教案必须属于某班某科（后端创建契约要求），
   * 存在本机以便新建/导出复用上次选择；「本地教案」对话框里可改。
   */
  const ownershipStorage = useMemo(() => safeBrowserStorage(), []);
  const [ownership, setOwnership] = useState<LessonOwnership>(() =>
    ownershipStorage ? readOwnership(ownershipStorage) : { subjectId: '', classId: '' },
  );
  const changeOwnership = useCallback(
    (next: LessonOwnership) => {
      setOwnership(next);
      if (ownershipStorage) writeOwnership(ownershipStorage, next);
    },
    [ownershipStorage],
  );

  /* 离开页面前先落本地草稿（服务器同步是尽力而为，不阻塞导航）。 */
  const flushAll = useCallback(async () => {
    local.flush();
    await serverSync.flush().catch(() => undefined);
  }, [local, serverSync]);

  /**
   * 守卫**只注册一次**：`flushAll` 的身份每次渲染都会变（`useLessonLocalDraft` /
   * `useLessonServer` 每次返回新对象），而导航守卫会把"守卫集合在决策期间发生增删"
   * 当作不安全而拒绝该次导航——若跟着 `flushAll` 重新注册，就会出现
   * 「点导航栏没反应、被锁在教案工作台」。这里用 ref 取最新实现，注册只依赖 provider。
   */
  const flushRef = useRef(flushAll);
  useEffect(() => {
    flushRef.current = flushAll;
  }, [flushAll]);
  useEffect(() => {
    if (!navigation.hasProvider) return;
    return navigation.register('lesson-plan:draft', async () => {
      await flushRef.current();
      return true;
    });
  }, [navigation]);

  /* 快捷键：撤销/重做/保存/打印；在输入框内不劫持（保留原生撤销）。 */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const meta = event.ctrlKey || event.metaKey;
      if (!meta) return;
      const target = event.target as HTMLElement | null;
      const typing =
        !!target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);
      const key = event.key.toLowerCase();
      if (key === 'z' && !typing) {
        event.preventDefault();
        if (event.shiftKey) store.getState().redo();
        else store.getState().undo();
        return;
      }
      if (key === 'y' && !typing) {
        event.preventDefault();
        store.getState().redo();
        return;
      }
      if (key === 's') {
        event.preventDefault();
        void flushRef.current();
        return;
      }
      if (key === 'p') {
        event.preventDefault();
        if (typeof window !== 'undefined') window.print();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [store]);

  const activeModule = modules.find((module) => module.id === activeModuleId) ?? modules[0];

  const candidateResults = useMemo(() => {
    if (!candidate) return [];
    return candidate.order
      .map((key) => parseModuleText(key, candidate.modules[key]?.text ?? ''))
      .filter((result) => result.fields.length > 0 || result.processRows.length > 0);
  }, [candidate]);

  const mergedPreview = useMemo(
    () =>
      candidateResults.length > 0
        ? mergeCandidateData(data, candidateResults)
        : { data, filledFields: new Set<string>() },
    [candidateResults, data],
  );

  const parsePreview = useCallback(
    (key: string) => {
      const text = candidate?.modules[key]?.text ?? '';
      if (!text.trim()) return { labels: [], unparsed: 0 };
      const result = parseModuleText(key, text);
      return { labels: result.fields.map((field) => field.label), unparsed: result.unparsed.length };
    },
    [candidate],
  );

  const adjustColumn = useCallback((which: 'left' | 'mid', delta: number) => {
    setColumns((current) => {
      const next = { ...current };
      if (which === 'left') {
        next.left = clamp(current.left + delta, COLUMN_LIMITS.left.min, COLUMN_LIMITS.left.max);
      } else {
        next.mid = clamp(current.mid + delta, COLUMN_LIMITS.mid.min, COLUMN_LIMITS.mid.max);
      }
      const overflow = next.left + next.mid - COLUMN_LIMITS.combinedMax;
      if (overflow > 0) {
        if (which === 'left') next.mid = clamp(next.mid - overflow, COLUMN_LIMITS.mid.min, COLUMN_LIMITS.mid.max);
        else next.left = clamp(next.left - overflow, COLUMN_LIMITS.left.min, COLUMN_LIMITS.left.max);
      }
      if (Math.abs(next.left - current.left) < 0.01 && Math.abs(next.mid - current.mid) < 0.01) {
        return current;
      }
      return next;
    });
  }, []);

  const togglePanel = useCallback((key: PanelKey) => {
    setPanels((current) => ({ ...current, [key]: !current[key] }));
  }, []);

  const onExport = useCallback(async () => {
    // 教案必须属于某班某科：还没选归属时先让教师去「本地教案」里选，不静默猜班级
    if (!ownership.subjectId || !ownership.classId) {
      setDialogOpen(true);
      setExportState({
        status: 'error',
        message: '导出前请先在「本地教案」里选择学科与班级（教案必须属于某班某科）。',
      });
      return;
    }
    setExportState({ status: 'busy' });
    try {
      const outcome = await serverSync.exportNow(ownership);
      setExportState({
        status: 'ok',
        message: outcome.downloaded
          ? `已生成并开始下载 ${outcome.fileName}`
          : `已生成 ${outcome.fileName}，但当前浏览器未触发下载，请在下载列表中确认。`,
      });
    } catch (error) {
      if (error instanceof ApiError && error.code === 'CLASS_NOT_FOUND') {
        // 班级被删除后本机记忆里的 classId 已失效：清空并让教师重选，不静默换班。
        changeOwnership({ ...ownership, classId: '' });
        setDialogOpen(true);
        setExportState({
          status: 'error',
          message: '原选择的班级已不存在，请在「本地教案」里重新选择班级后重试。',
        });
        return;
      }
      setExportState({ status: 'error', message: `导出失败：${reasonOf(error)}` });
    }
  }, [changeOwnership, ownership, serverSync]);

  const focusGenerate = useCallback(() => {
    setGenerateOpen(true);
    generateRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  }, [reduceMotion]);

  const notices = useMemo<WorkbenchNotice[]>(() => {
    const list: WorkbenchNotice[] = [];
    if (local.status.error) {
      list.push({
        id: 'local-draft',
        tone: 'warn',
        title: '本地草稿不可用，自动保存已暂停',
        message: local.status.error,
        actions: [
          {
            label: '放弃损坏草稿并新建',
            testId: 'lw-local-draft-discard',
            onClick: () => {
              local.discardLocalDraft();
              store.setState({
                data: emptyLessonData(),
                modules: defaultModuleLayout(),
                removed: [],
                activeModuleId: 'basic',
                revision: 0,
                past: [],
                future: [],
              });
            },
          },
        ],
        dismissible: false,
      });
    }
    if (serverSync.server.status === 'conflict') {
      list.push({
        id: 'server-conflict',
        tone: 'error',
        title: '教案版本冲突（本机后端）',
        message: `${serverSync.server.message ?? ''}${
          serverSync.server.conflictRevision != null
            ? `（服务器当前修订 ${serverSync.server.conflictRevision}）`
            : ''
        }`,
        actions: [
          {
            label: '载入服务器版本',
            testId: 'lw-conflict-reload',
            onClick: () => void serverSync.reloadServerVersion().catch(() => undefined),
          },
          {
            label: '保持本地并暂停同步',
            testId: 'lw-conflict-keep-local',
            onClick: () => serverSync.keepLocalOnly(),
          },
        ],
        dismissible: false,
      });
    } else if (serverSync.server.status === 'error') {
      list.push({
        id: 'server-error',
        tone: 'warn',
        title: '教案同步失败（本机后端）',
        message: serverSync.server.message,
        actions: [
          { label: '重试', testId: 'lw-server-retry', onClick: () => void serverSync.retrySync() },
          { label: '改用本地草稿', testId: 'lw-server-local-only', onClick: () => serverSync.keepLocalOnly() },
        ],
      });
    } else if (serverSync.server.status === 'local' && serverSync.server.message) {
      list.push({
        id: 'server-local',
        tone: 'info',
        title: '当前使用本地草稿',
        message: serverSync.server.message,
      });
    }
    if (lessonDeletedNotice) {
      list.push({
        id: 'lesson-deleted',
        tone: 'success',
        title: '教案已彻底删除',
        message: lessonDeletedNotice,
      });
    }
    if (exportState.status === 'ok' || exportState.status === 'error') {
      list.push({
        id: 'export',
        tone: exportState.status === 'ok' ? 'success' : 'error',
        title: exportState.status === 'ok' ? '导出已触发' : '导出失败',
        message: exportState.message,
      });
    }
    return list.filter((notice) => !dismissed.includes(notice.id));
  }, [
    dismissed,
    exportState.message,
    exportState.status,
    lessonDeletedNotice,
    local,
    serverSync,
    store,
  ]);

  const syncLabel = (() => {
    switch (serverSync.server.status) {
      case 'loading':
        return '读取教案中…';
      case 'syncing':
        return '正在同步…';
      case 'synced':
        return serverSync.server.lastSyncedAt
          ? `已同步 ${serverSync.server.lastSyncedAt.slice(11, 16)}`
          : '已同步';
      case 'conflict':
        return '版本冲突';
      case 'error':
        return '同步失败';
      default:
        return local.status.savedAt ? `本地草稿 ${local.status.savedAt.slice(11, 16)}` : '本地草稿';
    }
  })();

  const gridTracks = useMemo(() => {
    const visible: Array<{ key: PanelKey; track: string }> = [];
    if (panels.layout) visible.push({ key: 'layout', track: `${columns.left}%` });
    if (panels.editor) visible.push({ key: 'editor', track: `${columns.mid}%` });
    if (panels.preview) visible.push({ key: 'preview', track: 'minmax(0,1fr)' });
    if (visible.length === 0) return '0px';
    const tracks: string[] = [];
    visible.forEach((panel, index) => {
      if (index > 0) tracks.push('8px');
      // 最后一个可见栏占满剩余宽度；前面的栏保留用户拖出来的比例。
      // 这样折叠预览/编辑/布局时不会留下无人占用的空白轨道。
      tracks.push(index === visible.length - 1 ? 'minmax(0,1fr)' : panel.track);
    });
    return tracks.join(' ');
  }, [columns.left, columns.mid, panels]);

  return (
    <TooltipProvider>
      <div className="lesson-workbench" data-testid="lesson-workbench">
        <motion.header
          className="lw-topbar"
          initial={reduceMotion ? false : { y: -14, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="lw-topbar-left">
            <span className="lw-eyebrow">
              <NotebookPen size={14} aria-hidden />
              教案工作台
            </span>
            <label className="lw-name">
              <span className="lw-visually-hidden">教案名称</span>
              <input
                data-testid="lw-name-input"
                value={data.title}
                placeholder="教案名称（课题）"
                onChange={(event) => store.getState().setData({ title: event.target.value })}
              />
            </label>
            <span
              className={`lw-sync-chip ${serverSync.server.status}`}
              data-testid="lw-sync-state"
              role="status"
              aria-label={`保存状态：${syncLabel}`}
              title="草稿自动保存在本机浏览器；「本地教案」把教案保存到本机后端（.local-data，不外发）"
            >
              <Cloud size={13} aria-hidden />
              <span className="lw-sync-label">{syncLabel}</span>
            </span>
          </div>
          <div className="lw-topbar-actions">
            <button
              type="button"
              className="lw-icon-button"
              aria-label="撤销"
              title="撤销（Ctrl/⌘ + Z）"
              data-testid="lw-undo"
              disabled={!canUndo}
              onClick={() => store.getState().undo()}
            >
              <Undo2 size={15} />
            </button>
            <button
              type="button"
              className="lw-icon-button"
              aria-label="重做"
              title="重做（Ctrl/⌘ + Shift + Z）"
              data-testid="lw-redo"
              disabled={!canRedo}
              onClick={() => store.getState().redo()}
            >
              <Redo2 size={15} />
            </button>
            <button
              type="button"
              className="lw-button"
              aria-label="本地教案"
              data-testid="lw-library-button"
              onClick={() => setDialogOpen(true)}
            >
              <Cloud size={15} aria-hidden />
              <span className="lw-button-label">本地教案</span>
            </button>
            <button
              type="button"
              className="lw-button primary"
              aria-label="导出"
              data-testid="lw-export-button"
              disabled={exportState.status === 'busy'}
              onClick={() => void onExport()}
            >
              {exportState.status === 'busy' ? (
                <LoaderCircle size={15} className="lw-spin" aria-hidden />
              ) : (
                <Download size={15} aria-hidden />
              )}
              <span className="lw-button-label">导出</span>
            </button>
          </div>
        </motion.header>

        <WorkbenchNotices notices={notices} onDismiss={(id) => setDismissed((current) => [...current, id])} />

        <SlidingGroup activeKey={mobilePane} className="lw-pane-tabs" role="tablist" aria-label="工作台分栏">
          {(
            [
              ['layout', '布局与排版', PanelLeft],
              ['edit', '内容编辑', PenLine],
              ['preview', '预览', ScanEye],
            ] as Array<[MobilePane, string, typeof PanelLeft]>
          ).map(([pane, label, Icon]) => (
            <button
              key={pane}
              type="button"
              role="tab"
              aria-selected={mobilePane === pane}
              className={mobilePane === pane ? 'selected' : ''}
              data-testid={`lw-pane-${pane}`}
              onClick={() => setMobilePane(pane)}
            >
              <Icon size={15} aria-hidden />
              {label}
            </button>
          ))}
        </SlidingGroup>

        <div
          className={`lw-columns pane-${mobilePane} ${panels.layout ? '' : 'layout-collapsed'} ${
            panels.editor ? '' : 'editor-collapsed'
          } ${panels.preview ? '' : 'preview-collapsed'}`}
          data-testid="lw-columns"
          style={
            {
              '--lw-left': `${columns.left}%`,
              '--lw-mid': `${columns.mid}%`,
              gridTemplateColumns: gridTracks,
            } as React.CSSProperties
          }
        >
          <aside className="lw-col lw-col-left" aria-label="布局与排版" data-testid="lw-col-left">
            <div className="lw-col-scroll">
              <LayoutPanel
                modules={modules}
                removed={removed}
                data={data}
                activeModuleId={activeModule?.id ?? ''}
                onSelect={(id) => {
                  store.getState().setActiveModule(id);
                  // 手机/平板单栏模式：在「布局」里点模块即跳到编辑，少一次切页签。
                  if (mobilePane === 'layout') setMobilePane('edit');
                }}
                onMove={(id, delta) => store.getState().moveModule(id, delta)}
                onReorder={(from, to) => store.getState().reorderModule(from, to)}
                onToggleHidden={(id) => store.getState().toggleHidden(id)}
                onRemove={(id) => store.getState().removeModule(id)}
                onRestore={(id) => store.getState().restoreModule(id)}
                onAddCustom={(label) => {
                  store.getState().addCustomModule(label);
                  setMobilePane('edit');
                }}
              />
              <StylePanel
                style={style}
                onChange={(patch) => store.getState().setStyle(patch)}
                onReset={() => store.getState().setStyle({ ...DEFAULT_LESSON_STYLE })}
              />
            </div>
          </aside>

          <ColumnSplitter
            className="lw-splitter-left"
            label="调整布局栏宽度"
            testId="lw-splitter-left"
            onResize={(delta) => adjustColumn('left', delta)}
          />

          <section className="lw-col lw-col-mid" aria-label="教案编辑" data-testid="lw-col-mid">
            <div className="lw-col-scroll">
              {activeModule && (
                <ModuleEditor
                  entry={activeModule}
                  data={data}
                  setData={(patch) => store.getState().setData(patch)}
                  updateData={(updater) => store.getState().updateData(updater)}
                  renameCustomModule={(id, label) => store.getState().renameCustomModule(id, label)}
                  setCustomBody={(id, body) => store.getState().setCustomBody(id, body)}
                />
              )}
              <div className="lw-generate-anchor" ref={generateRef}>
                <GeneratePanel
                  data={data}
                  candidate={candidate}
                  open={generateOpen}
                  onOpenChange={setGenerateOpen}
                  onStartCandidate={(requestId, list) => store.getState().startCandidate(requestId, list)}
                  onDelta={(key, delta) => store.getState().appendCandidateDelta(key, delta)}
                  onModuleState={(key, state, message) => store.getState().markCandidateModule(key, state, message)}
                  onFinishCandidate={(status, message) => store.getState().finishCandidate(status, message)}
                  onClearCandidate={() => store.getState().clearCandidate()}
                  onAdopt={(keys) => store.getState().adoptCandidate(keys)}
                  parsePreview={parsePreview}
                  services={generateServices}
                />
              </div>
            </div>
          </section>

          <ColumnSplitter
            className="lw-splitter-mid"
            label="调整编辑栏宽度"
            testId="lw-splitter-mid"
            onResize={(delta) => adjustColumn('mid', delta)}
          />

          <div className="lw-col lw-col-right" data-testid="lw-col-right">
            <PaperPreview
              data={mergedPreview.data}
              modules={modulesToWire(modules)}
              style={style}
              filledFields={mergedPreview.filledFields}
              title={data.title}
              onSelectModule={(id) => {
                store.getState().setActiveModule(id);
                if (mobilePane === 'preview') setMobilePane('edit');
              }}
            />
          </div>
        </div>

        <PreviewDock
          onGenerate={focusGenerate}
          onExport={() => void onExport()}
          exportBusy={exportState.status === 'busy'}
          onLibrary={() => setDialogOpen(true)}
          onPrint={() => {
            if (typeof window !== 'undefined') window.print();
          }}
          onHelp={() => setHelpOpen(true)}
          onToggleLayout={() => togglePanel('layout')}
          onToggleEditor={() => togglePanel('editor')}
          onTogglePreview={() => togglePanel('preview')}
          layoutVisible={panels.layout}
          editorVisible={panels.editor}
          previewVisible={panels.preview}
        />

        {dialogOpen && (
          <LessonsDialog
            api={api}
            currentPlanId={serverSync.server.planId}
            ownership={ownership}
            onOwnershipChange={changeOwnership}
            onOpen={(id) => serverSync.openPlan(id)}
            onCreate={() => serverSync.createPlan(ownership).then(() => undefined)}
            onDeleted={(result) => {
              // 删掉的正是当前打开的教案：退回到"只用本地草稿"，不让同步指向已删教案
              if (serverSync.server.planId === result.lessonPlanId) serverSync.keepLocalOnly();
              setLessonDeletedNotice(
                `已彻底删除教案「${result.title}」：连同 ${result.removedRevisions} 个修订一并物理删除，不可恢复。`,
              );
            }}
            onClose={() => setDialogOpen(false)}
          />
        )}

        {helpOpen && <WorkbenchHelp onClose={() => setHelpOpen(false)} />}
      </div>
    </TooltipProvider>
  );
}
