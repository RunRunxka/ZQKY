'use client';
import {
  FilePenLine,
  ChevronDown,
  Plus,
  Download,
  FileText,
  LoaderCircle,
  Braces,
} from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
export function ExportMenu() {
  const { saveStatus, busy, exportOpen, setExportOpen, setModal, docx, backup } = useLessonEditor();
  return (
    <>
      <div className="header-actions">
        <span className={`save-status ${saveStatus.includes('失败') ? 'error-text' : ''}`}>
          <span className="status-dot" />
          {saveStatus}
        </span>
        <button className="button subtle new-button" onClick={() => setModal('new')}>
          <Plus size={16} />
          新建教案
        </button>
        <div className="export-container">
          <button
            className="button primary"
            aria-expanded={exportOpen}
            onClick={() => setExportOpen(!exportOpen)}
            disabled={busy}
          >
            {busy ? <LoaderCircle size={16} className="spin" /> : <Download size={16} />}导出教案
            <ChevronDown size={14} />
          </button>
          {exportOpen && (
            <>
              <button
                className="menu-backdrop"
                aria-label="关闭导出菜单"
                onClick={() => setExportOpen(false)}
              />
              <div className="export-menu">
                <button
                  onClick={() => {
                    setExportOpen(false);
                    setModal('pdf');
                  }}
                >
                  <FileText size={17} />
                  <span>
                    导出 PDF<small>通过浏览器另存为 PDF</small>
                  </span>
                </button>
                <button onClick={docx}>
                  <FilePenLine size={17} />
                  <span>
                    导出 Word<small>保留原始模板格式 · .docx</small>
                  </span>
                </button>
                <hr />
                <button onClick={backup}>
                  <Braces size={17} />
                  <span>
                    备份草稿<small>可再次导入编辑 · .json</small>
                  </span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
