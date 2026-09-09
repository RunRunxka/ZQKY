'use client';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Plus, Trash2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  WritingValidationError,
  createDocument,
  deleteDocument,
  listDocuments,
  subscribeWriting,
  type WritingDocument,
} from '@/services/writing-store';
import '@/features/space/styles/space.css';

/** /co-writer 列表（对照参考 CoWriterHomePage：新建空白/模板、删除；导入 DOCX 未接入为显式说明） */
export function WritingLibrary() {
  const router = useRouter();
  const [docs, setDocs] = useState<WritingDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    try {
      setDocs(listDocuments());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '写作文档无法读取，原数据未修改。');
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeWriting(refresh);
  }, [refresh]);

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>协同写作</h1>
          <div className="space-card-actions">
            <button className="space-button primary" onClick={() => setCreating(true)}>
              <Plus size={14} />
              新建文稿
            </button>
          </div>
        </div>
        <p className="space-description">
          文稿、版本与草稿本地保存；AI 改写/润色/扩写为显式模拟（统一事件模型流式输出，可取消/重试）。DOCX 导入未接入，不伪装上传成功。
        </p>
      </header>
      <main className="space-content">
        {error && (
          <div className="space-banner error" role="alert">
            {error}
          </div>
        )}
        {docs === null ? (
          <div aria-hidden>
            <div className="space-skeleton" style={{ height: 76, marginBottom: 10 }} />
          </div>
        ) : docs.length === 0 ? (
          <div className="space-empty">
            <strong>还没有文稿</strong>
            <span>新建空白文稿或使用教学设计模板开始写作。</span>
          </div>
        ) : (
          <ul className="space-session-list">
            {docs.map((doc) => (
              <li className="space-session-card" key={doc.docId}>
                <div className="space-session-top">
                  <FileText size={14} aria-hidden />
                  <Link className="space-session-title" href={`/co-writer/${doc.docId}`} aria-label={`打开文稿 ${doc.title}`}>
                    {doc.title}
                  </Link>
                  <span className="space-chip">{doc.content.length} 字</span>
                  <span className="space-chip">{doc.versions.length} 个版本</span>
                  <span className="space-session-actions">
                    <button
                      className="icon-button"
                      aria-label={`删除文稿 ${doc.title}`}
                      onClick={() => {
                        if (window.confirm(`删除文稿「${doc.title}」？其版本历史将一并删除。`)) {
                          deleteDocument(doc.docId);
                        }
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </span>
                </div>
                <div className="space-meta-row">
                  <span>更新于 {new Date(doc.updatedAt).toLocaleString('zh-CN')}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
        {creating && (
          <CreateDocForm
            onClose={() => setCreating(false)}
            onCreated={(id) => {
              setCreating(false);
              router.push(`/co-writer/${id}`);
            }}
          />
        )}
      </main>
    </div>
  );
}

function CreateDocForm({ onClose, onCreated }: { onClose: () => void; onCreated: (docId: string) => void }) {
  const [title, setTitle] = useState('');
  const [withTemplate, setWithTemplate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title="新建文稿" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const doc = createDocument({ title, withTemplate });
            onCreated(doc.docId);
          } catch (cause) {
            setError(cause instanceof WritingValidationError ? cause.message : '创建失败，请重试。');
          }
        }}
      >
        <label>
          标题
          <input value={title} maxLength={80} onChange={(event) => setTitle(event.target.value)} placeholder="未命名文稿" />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={withTemplate} onChange={(event) => setWithTemplate(event.target.checked)} />
          使用教学设计示例模板
        </label>
        {error && (
          <p className="space-form-error" role="alert">
            {error}
          </p>
        )}
        <div className="space-form-footer">
          <button type="button" className="space-button" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="space-button primary">
            创建
          </button>
        </div>
      </form>
    </Modal>
  );
}
