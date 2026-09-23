'use client';
import { useEffect, useLayoutEffect } from 'react';
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
import './styles/lesson-visual.css';
import './styles/print.css';
export function LessonPlanWorkspace({ services }: { services?: LessonPlanServices }) {
  return (
    <LessonPlanProvider services={services}>
      <LessonWorkspaceContent />
    </LessonPlanProvider>
  );
}
/** 服务端没有 viewport；在客户端提交后、浏览器绘制前读取，避免首次进入平板时闪出展开态 */
const useViewportLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;
/** 768–1279px 容不下「编辑区 + 教案配置 + 预览」三栏并排：默认收起教案配置，展开入口留在编辑区顶部 */
const COMPACT_LESSON_QUERY = '(max-width: 1279px)';
function LessonWorkspaceContent() {
  const {
    data,
    ready,
    collapsed,
    focusMode,
    mobileView,
    fontSize,
    setCollapsed,
    setFocusMode,
    setModal,
    flushDraft,
    notice,
  } = useLessonEditor();
  useViewportLayoutEffect(() => {
    if (window.matchMedia(COMPACT_LESSON_QUERY).matches) setCollapsed(true);
  }, [setCollapsed]);
  return (
    <WorkspaceShell
      pageTitle="教案工作台"
      className={`lesson-workspace lesson-page ${collapsed ? 'outline-hidden' : ''} ${focusMode ? 'focus-mode' : ''} mobile-${mobileView}`}
      beforeNavigate={flushDraft}
      onNavigationError={notice}
      headerActions={ready ? <ExportMenu /> : null}
    >
      {ready ? (
        <>
          {/* 页面标题行：壳内面包屑在教案页被隐藏（lesson-plan.css），此标题与协同写作/学习空间同级 */}
          <header className="lesson-page-head">
            <h1 className="lesson-page-title">教案工作台</h1>
          </header>
          {/* DOM 阅读顺序 = 视觉顺序：始终可见的编辑区 → 可折叠的教案配置 → 教案预览 */}
          <EditorPanel />
          <OutlinePanel />
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
