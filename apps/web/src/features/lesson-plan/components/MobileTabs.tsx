'use client';
import { FilePenLine, FileText } from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
export function MobileTabs() {
  const { mobileView, setMobileView } = useLessonEditor();
  return (
    <>
      <div className="mobile-tabs">
        <button
          className={mobileView === 'edit' ? 'active' : ''}
          onClick={() => setMobileView('edit')}
        >
          <FilePenLine size={17} />
          编辑教案
        </button>
        <button
          className={mobileView === 'preview' ? 'active' : ''}
          onClick={() => setMobileView('preview')}
        >
          <FileText size={17} />
          预览教案
        </button>
      </div>
    </>
  );
}
