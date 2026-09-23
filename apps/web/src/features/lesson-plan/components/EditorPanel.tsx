'use client';
import { FilePenLine, Undo2, Redo2, PanelLeftClose, PanelLeftOpen, Sparkles } from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
import { FormPanel } from './FormPanel';
import { NlFillPanel } from './NlFillPanel';
export function EditorPanel() {
  const {
    undo,
    redo,
    past,
    future,
    editorTab,
    setEditorTab,
    collapsed,
    setCollapsed,
    completeCount,
  } = useLessonEditor();
  return (
    <>
      <main className="editor-panel">
        <div className="editor-heading">
          <div>
            <div className="eyebrow">LESSON PLANNER</div>
            <h1>把教学思路，写进课堂。</h1>
          </div>
          {/*
            教案配置的唯一折叠控件：位于始终可见的编辑区顶部，双向切换，
            按钮自身不随状态卸载，因此连续点击不会丢焦点。
          */}
          <button
            className="icon-button config-toggle"
            aria-label={collapsed ? '展开教案配置' : '收起教案配置'}
            aria-expanded={!collapsed}
            aria-controls="lesson-config-panel"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>
        <div className="editor-tabs">
          <button
            className={editorTab === 'form' ? 'active' : ''}
            onClick={() => setEditorTab('form')}
          >
            <FilePenLine size={16} />
            逐项填写
          </button>
          <button
            className={editorTab === 'fill' ? 'active' : ''}
            onClick={() => setEditorTab('fill')}
          >
            <Sparkles size={16} />
            要求填充<span>规则</span>
          </button>
          <div className="history-actions">
            <button
              className="icon-button"
              aria-label="撤销"
              disabled={!past.length}
              onClick={undo}
            >
              <Undo2 size={16} />
            </button>
            <button
              className="icon-button"
              aria-label="重做"
              disabled={!future.length}
              onClick={redo}
            >
              <Redo2 size={16} />
            </button>
          </div>
        </div>
        <div className="editor-scroll">
          {editorTab === 'form' ? <FormPanel /> : <NlFillPanel />}
        </div>
        <div className="editor-footer">
          <span>
            <span className="live-dot" />
            编辑后实时更新预览
          </span>
          <span>{completeCount} / 7 项已填写</span>
        </div>
      </main>
    </>
  );
}
