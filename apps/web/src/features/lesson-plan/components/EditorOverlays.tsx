'use client';
import { FilePenLine, PanelsTopLeft, Check, Download, X, Info, ExternalLink } from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
import { emptyData } from '../model/defaults';
import { exampleData } from '../model/defaults';
import { exportPdf } from '../services/export';
import { validateData } from '../services/drafts';
export function EditorOverlays() {
  const {
    data,
    replace,
    toast,
    setToast,
    modal,
    setModal,
    storageBlocked,
    resumeStorage,
    dialog,
    fileInput,
    notice,
    selectSection,
    backup,
  } = useLessonEditor();
  return (
    <>
      {' '}
      <input
        type="file"
        ref={fileInput}
        hidden
        accept=".json,application/json"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          try {
            if (file.size > 2 * 1024 * 1024) throw Error('草稿文件不能超过2 MB');
            const content = JSON.parse(await file.text());
            if (content.schemaVersion !== 1) throw Error('草稿版本不兼容');
            validateData(content.data);
            replace(content.data);
            notice('草稿已导入，可通过撤销恢复导入前内容');
          } catch (error) {
            notice(`导入失败：${(error as Error).message}`);
          } finally {
            e.target.value = '';
          }
        }}
      />
      <dialog
        className="modal"
        ref={dialog}
        onCancel={() => setModal(null)}
        onClick={(e) => {
          if (e.target === dialog.current) setModal(null);
        }}
      >
        <div className="modal-heading">
          <span className="section-icon">
            {modal === 'pdf' ? (
              <Download size={21} />
            ) : modal === 'new' ? (
              <FilePenLine size={21} />
            ) : (
              <PanelsTopLeft size={21} />
            )}
          </span>
          <button className="icon-button" aria-label="关闭弹窗" onClick={() => setModal(null)}>
            <X size={20} />
          </button>
        </div>
        {modal === 'new' ? (
          <>
            <h2>开始一份新教案</h2>
            <p>当前内容将被替换。你可以先备份草稿，或在新建后点击撤销恢复。</p>
            <div className="modal-actions">
              <button className="button subtle" onClick={backup}>
                备份当前草稿
              </button>
              <button
                className="button subtle"
                onClick={() => {
                  replace(exampleData);
                  setModal(null);
                  notice('示例教案已载入');
                }}
              >
                载入示例
              </button>
              <button
                className="button primary"
                onClick={() => {
                  replace(emptyData);
                  setModal(null);
                  selectSection('basic');
                  notice('空白教案已创建');
                }}
              >
                创建空白教案
              </button>
            </div>
          </>
        ) : modal === 'pdf' ? (
          <>
            <h2>导出一份可打印的教案</h2>
            <p>
              下一步打开浏览器打印窗口，将打印机或目标选择为<strong>“另存为 PDF”</strong>。
            </p>
            <div className="pdf-options">
              <div>
                <Check size={16} />
                <span>A4 纸张，使用当前预览字号</span>
              </div>
              <div>
                <Check size={16} />
                <span>建议关闭浏览器“页眉和页脚”</span>
              </div>
              <div>
                <Info size={16} />
                <span>PDF 与网页预览同源；Word 以原模板独立排版。</span>
              </div>
            </div>
            <div className="modal-actions">
              <button className="button subtle" onClick={() => setModal(null)}>
                继续编辑
              </button>
              <button
                className="button primary"
                onClick={() => {
                  setModal(null);
                  setTimeout(() => {
                    exportPdf(data.title).catch(() => notice('打印窗口未能打开，请重试'));
                  }, 100);
                }}
              >
                <ExternalLink size={16} />
                打开打印窗口
              </button>
            </div>
          </>
        ) : null}
      </dialog>
      {storageBlocked && (
        <div className="storage-alert">
          原草稿读取失败，自动保存已暂停。
          <button
            onClick={() => {
              backup();
              resumeStorage();
            }}
          >
            备份当前内容并替换旧草稿
          </button>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <Info size={17} />
          <span>{toast}</span>
          <button className="icon-button" aria-label="关闭提示" onClick={() => setToast('')}>
            <X size={14} />
          </button>
        </div>
      )}
    </>
  );
}
