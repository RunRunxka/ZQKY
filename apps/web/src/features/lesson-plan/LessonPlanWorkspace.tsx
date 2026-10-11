'use client';
import { useEffect, useLayoutEffect, useState } from 'react';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { LoopConveyor } from '@/components/layout/LoopConveyor';
import { useLessonEditor } from './model/EditorContext';
import { DocumentGateway, type LessonWorkspaceProps } from './components/DocumentGateway';
import { LeaveProtection } from './components/LeaveProtection';
import { useLessonDocument } from './model/DocumentContext';
import { useNavigationGuard } from '@/services/navigation-guard';
import { OutlinePanel } from './components/OutlinePanel';
import { EditorPanel } from './components/EditorPanel';
import { ExportMenu } from './components/ExportMenu';
import { EditorOverlays } from './components/EditorOverlays';
import { MobileTabs } from './components/MobileTabs';
import { PreviewPane } from './components/PreviewPane';
import { ModuleNav } from './components/ModuleNav';
import { ModuleEditor } from './components/ModuleEditor';
import { TemplatePreview } from './components/TemplatePreview';
import { LessonStreamDialog } from './components/LessonStreamDialog';
import { DEFAULT_LESSON_STYLE, type LessonModuleId, type LessonStyleState } from './model/modules';
import './styles/lesson-v2.css';
import './styles/lesson-fonts.css';
import './styles/lesson-plan.css';
import './styles/lesson-visual.css';
import './styles/print.css';
import './styles/server-session.css';
import './styles/lesson-refined.css';
export function LessonPlanWorkspace(props: LessonWorkspaceProps) {
  return (
    <DocumentGateway {...props}>
      <LessonWorkspaceContent />
    </DocumentGateway>
  );
}
/** 服务端没有 viewport；在客户端提交后、浏览器绘制前读取，避免首次进入平板时闪出展开态 */
const useViewportLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;
/** 768–1279px 容不下「编辑区 + 教案配置 + 预览」三栏并排：默认收起教案配置，展开入口留在编辑区顶部 */
const COMPACT_LESSON_QUERY = '(max-width: 1279px)';
function LessonWorkspaceContent() {
  const doc = useLessonDocument(), navigation = useNavigationGuard();
  const {
    data,
    ready,
    set,
    collapsed,
    editingLocked,
    focusMode,
    mobileView,
    fontSize,
    setCollapsed,
    setFocusMode,
    setModal,
    printSnapshot,
    sourceLabel,
  } = useLessonEditor();
  useViewportLayoutEffect(() => {
    if (window.matchMedia(COMPACT_LESSON_QUERY).matches) setCollapsed(true);
  }, [setCollapsed]);
  // 模板工作台 v2（C3-2）：左模块导航/中模块编辑/右 A4 预览（第3页起）；
  // 经典三栏为默认（已验收行为零破坏），切换入口在编辑区顶栏。
  const [viewMode, setViewMode] = useState<'classic' | 'template'>('classic');
  const [selectedModule, setSelectedModule] = useState<LessonModuleId>('basic');
  const [lessonStyle, setLessonStyle] = useState<LessonStyleState>(DEFAULT_LESSON_STYLE);
  const [streamOpen, setStreamOpen] = useState(false);
  if (viewMode === 'template' && ready) {
    return (
      <WorkspaceShell
        pageTitle="教案工作台"
        className={`lesson-workspace lesson-page loop-conveyor-host`}
        beforeNavigate={navigation.hasProvider ? undefined : async () => { if (doc.leave.current && !(await doc.leave.current())) throw new Error('当前教案保持'); }}
        headerActions={
          <>
            <h1 className="lesson-page-title">教案工作台</h1>
            <button className="space-button" onClick={() => setStreamOpen(true)}>AI 生成</button>
            <button className="space-button" onClick={() => setViewMode('classic')}>经典视图</button>
            <ExportMenu />
          </>
        }
      >
        <LoopConveyor className="lesson-loop-conveyor" subjectId={doc.selection.subjectId || null} focusStation="lesson" />
        <div className="lesson-v2-grid">
          <ModuleNav
            data={data}
            selected={selectedModule}
            style={lessonStyle}
            onSelect={setSelectedModule}
            onToggleHidden={(id) => setLessonStyle((s) => ({
              ...s,
              hiddenModules: s.hiddenModules.includes(id)
                ? s.hiddenModules.filter((x) => x !== id)
                : [...s.hiddenModules, id],
            }))}
            onStyle={(patch) => setLessonStyle((s) => ({ ...s, ...patch }))}
          />
          <section className="lesson-mid" aria-label="教案编辑">
            <fieldset className="lesson-mid-fields" disabled={editingLocked}>
              <ModuleEditor
                data={data}
                selected={selectedModule}
                onSet={set}
                onAddProcess={() => set({ processV2: [...(data.processV2 ?? []), { id: crypto.randomUUID(), phase: 'exploration', phaseLabel: '', title: '', teacherActivity: '', studentActivity: '', intent: '' }] })}
                onUpdateProcess={(id, patch) => set({ processV2: (data.processV2 ?? []).map((p) => (p.id === id ? { ...p, ...patch } : p)) })}
                onRemoveProcess={(id) => set({ processV2: (data.processV2 ?? []).filter((p) => p.id !== id) })}
              />
            </fieldset>
          </section>
          <div className="lesson-tpl-wrap" aria-label="教案实时预览（正文，封面目录由导出自动补齐）">
            <TemplatePreview data={printSnapshot?.data ?? data} style={lessonStyle} onPrint={() => setModal('pdf')} />
          </div>
        </div>
        {streamOpen && (
          <LessonStreamDialog
            data={data}
            onClose={() => setStreamOpen(false)}
            onApply={set}
          />
        )}
        <EditorOverlays />
        <LeaveProtection />
      </WorkspaceShell>
    );
  }
  return (
    <WorkspaceShell
      pageTitle="教案工作台"
      className={`lesson-workspace lesson-page ${collapsed ? 'outline-hidden' : ''} ${focusMode ? 'focus-mode' : ''} mobile-${mobileView}${ready ? ' loop-conveyor-host' : ''}`}
      beforeNavigate={navigation.hasProvider ? undefined : async () => { if (doc.leave.current && !(await doc.leave.current())) throw new Error('当前教案保持'); }}
      headerActions={
        <>
          {/* UX-REGRESSION-FIX v1：教案标题进入公共顶栏，与导出菜单**同一行**；
              不再在顶栏下方多出一栏标题（壳内面包屑在教案页仍隐藏，其他页面不受影响）。
              字体/字号与协同写作、沉浸阅读同级（同一 --font-display 与排版值）。 */}
          <h1 className="lesson-page-title">教案工作台</h1>
          {ready ? <button className="space-button" onClick={() => setViewMode('template')}>模板视图</button> : null}
          {ready ? <ExportMenu /> : null}
        </>
      }
    >
      {ready ? (
        <>
          {/* 闭环传递带：教案调整之前的五站真实状态；占独立一行，不遮挡顶栏与三栏面板。
              本页工位＝教案调整（lesson）：它缺前置时主按钮改为「缺「X」：一句话」＋「去补齐」 */}
          <LoopConveyor className="lesson-loop-conveyor" subjectId={doc.selection.subjectId || null} focusStation="lesson" />
          {/* DOM 阅读顺序 = 视觉顺序：始终可见的编辑区 → 可折叠的教案配置 → 教案预览 */}
          <EditorPanel />
          <OutlinePanel />
          <PreviewPane
            data={printSnapshot?.data ?? data}
            sourceLabel={printSnapshot?.source ?? sourceLabel}
            fontSize={fontSize}
            focusMode={focusMode}
            onFocus={() => setFocusMode(!focusMode)}
            onPrint={() => setModal('pdf')}
          />
          <MobileTabs />
          <EditorOverlays />
          <LeaveProtection />
        </>
      ) : (
        <main className="status-page" role="status">
          正在恢复教案草稿…
        </main>
      )}
    </WorkspaceShell>
  );
}
