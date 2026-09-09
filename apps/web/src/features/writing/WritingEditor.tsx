'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, History, RotateCcw, Sparkles, Undo2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  getDocument,
  renameDocument,
  restoreVersion,
  saveDocumentContent,
  snapshotVersion,
  subscribeWriting,
  type WritingDocument,
} from '@/services/writing-store';
import { createWritingAiService, writingAiModeLabel, type WritingAiMode } from '@/features/writing/writing-ai';
import { AnswerMarkdown } from '@/features/chat/AnswerMarkdown';
import '@/features/space/styles/space.css';

interface AiPreview {
  mode: WritingAiMode;
  text: string;
  error: string | null;
  retryable: boolean;
  range: { start: number; end: number } | null;
}

/** /co-writer/[docId] 编辑器：自动保存、版本快照/恢复、撤销、选区 AI 修改与全文生成（显式模拟） */
export function WritingEditor({ docId }: { docId: string }) {
  const [doc, setDoc] = useState<WritingDocument | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'error'>('saved');
  const [undoStack, setUndoStack] = useState<string[]>([]);
  const [renaming, setRenaming] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [aiPanel, setAiPanel] = useState<{ mode: WritingAiMode; instruction: string } | null>(null);
  const [preview, setPreview] = useState<AiPreview | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const selectionRef = useRef<{ start: number; end: number } | null>(null);
  const serviceRef = useRef<ReturnType<typeof createWritingAiService> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const stateRef = useRef({ docId, content, dirty });
  stateRef.current = { docId, content, dirty };
  if (!serviceRef.current) serviceRef.current = createWritingAiService();

  const refresh = useCallback(() => {
    try {
      const current = getDocument(docId);
      if (!current) {
        setLoadError('文稿不存在或已被删除。');
        return;
      }
      setLoadError(null);
      setDoc(current);
      // 本地编辑未保存时以本地内容优先（刷新恢复由 autosave 保证已落盘）
      setContent((previous) => (dirty && previous ? previous : current.content));
    } catch (cause) {
      setLoadError(cause instanceof Error ? cause.message : '文稿无法读取，原数据未修改。');
    }
  }, [docId, dirty]);

  useEffect(() => {
    refresh();
    return subscribeWriting(refresh);
  }, [refresh]);

  // 自动保存：内容变更即同步落盘（本地存储即时写入，无需防抖悬挂状态）
  useEffect(() => {
    if (!dirty) return;
    setSaveState('saving');
    try {
      saveDocumentContent(stateRef.current.docId, stateRef.current.content);
      setDirty(false);
      setSaveState('saved');
    } catch {
      setSaveState('error');
    }
  }, [content, dirty]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  if (loadError) {
    return (
      <div className="space-page">
        <div className="space-empty" style={{ marginTop: 80 }}>
          <strong>无法打开文稿</strong>
          <span>{loadError}</span>
          <Link className="space-button" href="/co-writer">
            <ArrowLeft size={14} />
            返回协同写作
          </Link>
        </div>
      </div>
    );
  }
  if (!doc) {
    return (
      <div className="space-page">
        <div className="space-banner" style={{ marginTop: 80 }}>
          正在读取文稿…
        </div>
      </div>
    );
  }

  function updateContent(next: string) {
    setContent(next);
    setDirty(true);
  }

  function pushUndo(previous: string) {
    setUndoStack((stack) => [...stack.slice(-9), previous]);
  }

  function undo() {
    const stack = [...undoStack];
    const previous = stack.pop();
    if (previous === undefined) return;
    setUndoStack(stack);
    pushUndo(content);
    updateContent(previous);
  }

  function openSelectionAi(mode: WritingAiMode) {
    const el = textareaRef.current;
    const start = el?.selectionStart ?? 0;
    const end = el?.selectionEnd ?? 0;
    selectionRef.current = start < end ? { start, end } : null;
    setAiPanel({ mode, instruction: '' });
    setPreview(null);
  }

  function runAi() {
    if (!aiPanel || !doc) return;
    const isGenerate = aiPanel.mode === 'generate';
    const range = selectionRef.current;
    if (!isGenerate && !range) return;
    const sourceText = isGenerate ? `${doc.title}\n\n${content}` : content.slice(range!.start, range!.end);
    snapshotVersion(docId, `${writingAiModeLabel(aiPanel.mode)}前自动快照`);
    const controller = new AbortController();
    abortRef.current = controller;
    let text = '';
    setPreview({ mode: aiPanel.mode, text: '', error: null, retryable: false, range: isGenerate ? null : range });
    const turnId = `wturn-${Date.now().toString(36)}`;
    void serviceRef.current!.run(
      { docId, turnId, mode: aiPanel.mode, instruction: aiPanel.instruction, sourceText, signal: controller.signal },
      (event) => {
        if (event.type === 'text' && event.delta) {
          text += event.delta;
          setPreview((current) => (current ? { ...current, text } : current));
        } else if (event.type === 'error') {
          setPreview((current) => (current ? { ...current, error: event.message ?? 'AI 修改失败。', retryable: event.retryable ?? false } : current));
        } else if (event.type === 'end') {
          abortRef.current = null;
          setPreview((current) => (current ? { ...current, text } : current));
        }
      },
    ).catch((cause: unknown) => {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        setPreview((current) => (current && text ? { ...current, text } : null));
        return;
      }
      setPreview((current) => (current ? { ...current, error: cause instanceof Error ? cause.message : 'AI 修改失败。', retryable: true } : current));
    });
  }

  function applyPreview() {
    if (!preview || !preview.text) return;
    pushUndo(content);
    if (preview.range) {
      const next = content.slice(0, preview.range.start) + preview.text + content.slice(preview.range.end);
      updateContent(next);
    } else {
      updateContent(preview.text);
    }
    setPreview(null);
    setAiPanel(null);
  }

  function cancelPreview() {
    abortRef.current?.abort();
    abortRef.current = null;
    setPreview(null);
  }

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/co-writer">
            <ArrowLeft size={16} />
            返回协同写作
          </Link>
          <div className="space-card-actions">
            <button className="space-button" onClick={undo} disabled={undoStack.length === 0} aria-label="撤销修改">
              <Undo2 size={14} />
              撤销
            </button>
            <button className="space-button" onClick={() => setVersionsOpen(true)} aria-label="版本历史">
              <History size={14} />
              版本（{doc.versions.length}）
            </button>
            <button className="space-button" onClick={() => openSelectionAi('generate')} aria-label="AI 生成全文">
              <Sparkles size={14} />
              AI 生成
            </button>
          </div>
        </div>
        <h1>
          {doc.title}
          <button className="icon-button" aria-label="重命名文稿" style={{ marginLeft: 8, verticalAlign: 'middle' }} onClick={() => setRenaming(true)}>
            <RotateCcw size={12} style={{ transform: 'rotate(90deg)' }} />
          </button>
        </h1>
        <p className="space-description">
          <span className="space-chip" role="status">
            {saveState === 'saving' ? '保存中…' : saveState === 'error' ? '保存失败，将重试' : dirty ? '有未保存修改' : '已保存'}
          </span>
          <span className="space-chip">{content.length} 字</span>
          AI 修改为显式模拟：流式预览 → 应用/放弃，应用前自动保存版本。
        </p>
      </header>
      <main className="space-content">
        <textarea
          ref={textareaRef}
          aria-label="文稿正文编辑区"
          value={content}
          onChange={(event) => updateContent(event.target.value)}
          style={{ minHeight: 420, width: '100%', fontFamily: 'inherit', lineHeight: 1.7, resize: 'vertical' }}
          placeholder="开始写作…（支持 Markdown）"
        />
        <div className="space-card-actions" style={{ marginTop: 10 }}>
          <button className="space-button" onClick={() => openSelectionAi('rewrite')}>
            选区改写
          </button>
          <button className="space-button" onClick={() => openSelectionAi('polish')}>
            选区润色
          </button>
          <button className="space-button" onClick={() => openSelectionAi('expand')}>
            选区扩写
          </button>
          <button
            className="space-button"
            aria-label="保存版本"
            onClick={() => {
              snapshotVersion(docId, `手动版本（${new Date().toLocaleString('zh-CN')}）`);
            }}
          >
            保存版本
          </button>
        </div>
      </main>

      {aiPanel && !preview && (
        <Modal title={`AI ${writingAiModeLabel(aiPanel.mode)}`} onClose={() => setAiPanel(null)}>
          <form
            className="space-form"
            onSubmit={(event) => {
              event.preventDefault();
              runAi();
            }}
          >
            <p className="space-footnote" style={{ marginTop: 0 }}>
              {aiPanel.mode === 'generate'
                ? '将按标题与指令生成全文提纲（覆盖当前内容，应用前自动快照）。'
                : '已捕获正文选区；指令可选。'}
            </p>
            <label>
              指令（可选）
              <input
                value={aiPanel.instruction}
                onChange={(event) => setAiPanel({ ...aiPanel, instruction: event.target.value })}
                placeholder="例如：面向初中生，语言更口语化"
              />
            </label>
            <div className="space-form-footer">
              <button type="button" className="space-button" onClick={() => setAiPanel(null)}>
                取消
              </button>
              <button type="submit" className="space-button primary">
                开始生成
              </button>
            </div>
          </form>
        </Modal>
      )}

      {preview && (
        <Modal title={`AI ${writingAiModeLabel(preview.mode)}预览`} onClose={cancelPreview}>
          {preview.error ? (
            <div className="space-banner error" role="alert" style={{ marginBottom: 10 }}>
              {preview.error}
              {preview.retryable && (
                <button className="space-button" style={{ marginLeft: 8 }} onClick={runAi} aria-label="重试 AI 修改">
                  重试
                </button>
              )}
            </div>
          ) : (
            <div className="reading-msg assistant" style={{ maxWidth: '100%', marginBottom: 10 }} aria-label="AI 修改预览">
              <AnswerMarkdown text={preview.text} />
            </div>
          )}
          <div className="space-form-footer">
            <button className="space-button" onClick={cancelPreview}>
              放弃
            </button>
            <button className="space-button primary" onClick={applyPreview} disabled={!preview.text || Boolean(preview.error)}>
              应用
            </button>
          </div>
        </Modal>
      )}

      {renaming && (
        <RenameForm
          doc={doc}
          onClose={() => setRenaming(false)}
          onSaved={() => setRenaming(false)}
        />
      )}
      {versionsOpen && (
        <VersionsForm docId={docId} onClose={() => setVersionsOpen(false)} />
      )}
    </div>
  );
}

function RenameForm({ doc, onClose, onSaved }: { doc: WritingDocument; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState(doc.title);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title="重命名文稿" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            renameDocument(doc.docId, title);
            onSaved();
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : '保存失败，请重试。');
          }
        }}
      >
        <label>
          标题
          <input value={title} required maxLength={80} onChange={(event) => setTitle(event.target.value)} />
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
            保存
          </button>
        </div>
      </form>
    </Modal>
  );
}

function VersionsForm({ docId, onClose }: { docId: string; onClose: () => void }) {
  const [doc] = useState<WritingDocument | null>(() => getDocument(docId));
  return (
    <Modal title="版本历史" onClose={onClose}>
      {!doc || doc.versions.length === 0 ? (
        <p className="space-footnote">暂无版本。AI 应用与手动「保存版本」都会生成快照。</p>
      ) : (
        <ul className="space-session-list">
          {[...doc.versions].reverse().map((version) => (
            <li className="space-session-card" key={version.versionId}>
              <div className="space-session-top">
                <span className="space-session-title">{version.label}</span>
                <span className="space-chip">{version.content.length} 字</span>
                <button
                  className="space-button"
                  aria-label={`恢复版本 ${version.label}`}
                  onClick={() => {
                    restoreVersion(docId, version.versionId);
                    onClose();
                  }}
                >
                  恢复
                </button>
              </div>
              <div className="space-meta-row">
                <span>{new Date(version.savedAt).toLocaleString('zh-CN')}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
