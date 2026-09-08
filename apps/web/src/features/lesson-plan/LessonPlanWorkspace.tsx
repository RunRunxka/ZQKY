'use client';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { LessonPlanProvider, useLessonEditor } from './model/EditorContext';
import type { LessonPlanServices } from './model/types';
import { OutlinePanel } from './components/OutlinePanel';
import { EditorPanel } from './components/EditorPanel';
import { ExportMenu } from './components/ExportMenu';
import { EditorOverlays } from './components/EditorOverlays';
import { MobileTabs } from './components/MobileTabs';
import { PreviewPane } from './components/PreviewPane';
import './styles/lesson-plan.css';
import './styles/print.css';
export function LessonPlanWorkspace({ services }: { services?: LessonPlanServices }) {
  return (
    <LessonPlanProvider services={services}>
      <LessonWorkspaceContent />
    </LessonPlanProvider>
  );
}
function LessonWorkspaceContent() {
  const {
    data,
    ready,
    collapsed,
    focusMode,
    mobileView,
    fontSize,
    setFocusMode,
    setModal,
    flushDraft,
    notice,
  } = useLessonEditor();
  return (
    <WorkspaceShell
      pageTitle="教案工作台"
      className={`lesson-workspace ${collapsed ? 'outline-hidden' : ''} ${focusMode ? 'focus-mode' : ''} mobile-${mobileView}`}
      beforeNavigate={flushDraft}
      onNavigationError={notice}
      headerActions={ready ? <ExportMenu /> : null}
    >
      {ready ? (
        <>
          <OutlinePanel />
          <EditorPanel />
          <PreviewPane
            data={data}
            fontSize={fontSize}
            focusMode={focusMode}
            onFocus={() => setFocusMode(!focusMode)}
            onPrint={() => setModal('pdf')}
          />
          <MobileTabs />
          <EditorOverlays />
        </>
      ) : (
        <main className="status-page" role="status">
          正在恢复教案草稿…
        </main>
      )}
    </WorkspaceShell>
  );
}
