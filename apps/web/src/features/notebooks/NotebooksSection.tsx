'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
// 复用 space 设计语言的样式；直达路由也需要加载（不能只依赖 SpaceMain 的引入）
import '@/features/space/styles/space.css';
import {
  ArrowLeft,
  ChevronRight,
  Copy,
  Download,
  FolderInput,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  TriangleAlert,
} from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  createNotebook,
  deleteNotebook,
  exportNotebookMarkdown,
  listNotebooks,
  listRecords,
  NOTEBOOK_COLORS,
  relocateRecord,
  removeNotebookRecord,
  subscribeNotebooks,
  updateNotebook,
  updateNotebookRecord,
  type Notebook,
  type NotebookColor,
  type NotebookRecord,
} from '@/services/notebook-store';

const COLOR_DOT: Record<NotebookColor, string> = {
  blue: '#2563eb',
  green: '#33876b',
  amber: '#b7791f',
  purple: '#7c5cd6',
  gray: '#8a8a8a',
};

const TYPE_LABEL: Record<string, string> = {
  research_report: '研究报告',
  chat: '对话',
  co_writer: '协同写作',
  video_learning: '视频学习',
};

export function NotebooksSection() {
  const params = useParams<{ notebookId?: string }>();
  const routeNotebookId = params?.notebookId;
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(routeNotebookId ?? null);
  const [records, setRecords] = useState<NotebookRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [notebookQuery, setNotebookQuery] = useState('');
  const [recordQuery, setRecordQuery] = useState('');
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [editingNotebook, setEditingNotebook] = useState<Notebook | null>(null);
  const [editingRecord, setEditingRecord] = useState<NotebookRecord | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [movingRecord, setMovingRecord] = useState<NotebookRecord | null>(null);

  const refresh = useCallback(() => {
    try {
      const notebooksNow = listNotebooks();
      setNotebooks(notebooksNow);
      setRecords(listRecords());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '笔记本数据无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeNotebooks(refresh);
  }, [refresh]);

  // URL 驱动选中（/notebooks/[notebookId] 深链）
  useEffect(() => {
    if (routeNotebookId) setSelectedId(routeNotebookId);
  }, [routeNotebookId]);

  // 深链指向不存在的笔记本：明确提示
  const selected = useMemo(
    () => notebooks.find((n) => n.id === selectedId) ?? null,
    [notebooks, selectedId],
  );
  useEffect(() => {
    if (!loading && routeNotebookId && !selected)
      setError('链接指向的笔记本不存在，可能已被删除。');
  }, [loading, routeNotebookId, selected]);

  const filteredNotebooks = useMemo(() => {
    const q = notebookQuery.trim().toLowerCase();
    return q ? notebooks.filter((n) => n.name.toLowerCase().includes(q)) : notebooks;
  }, [notebooks, notebookQuery]);

  const selectedRecords = useMemo(
    () => (selected ? records.filter((record) => record.notebookId === selected.id) : []),
    [selected, records],
  );

  const filteredRecords = useMemo(() => {
    const q = recordQuery.trim().toLowerCase();
    return q
      ? selectedRecords.filter(
          (record) =>
            record.title.toLowerCase().includes(q) || record.content.toLowerCase().includes(q),
        )
      : selectedRecords;
  }, [selectedRecords, recordQuery]);

  function selectNotebook(id: string) {
    setSelectedId(id);
    setError(null);
    const target = `/notebooks/${id}`;
    if (window.location.pathname !== target) {
      window.history.pushState(null, '', target);
    }
  }

  async function handleExport() {
    if (!selected) return;
    const result = exportNotebookMarkdown(selected.id);
    if (!result) {
      setError('导出失败：笔记本不存在。');
      return;
    }
    const blob = new Blob([result.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = result.name;
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`已导出「${result.name}」（共 ${selectedRecords.length} 条记录的实际内容）。`);
  }

  function handleDeleteNotebook(notebook: Notebook) {
    if (
      window.confirm(
        `删除笔记本「${notebook.name}」？其中的记录会回到默认笔记本「学习笔记」，不会丢失。`,
      )
    ) {
      if (!deleteNotebook(notebook.id)) {
        setError('删除失败：默认笔记本不能删除。');
        return;
      }
      if (selectedId === notebook.id) setSelectedId(null);
      setNotice(`已删除「${notebook.name}」，其中记录已移回默认笔记本。`);
    }
  }

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/space">
            <ArrowLeft size={16} />
            返回学习空间
          </Link>
          <button
            className="space-button"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw size={14} />
            刷新
          </button>
        </div>
        <h1>笔记本</h1>
        <p className="space-description">
          聊天与研究产物集中存放；记录支持查看、编辑、移动/复制与导出。
        </p>
      </header>
      <main className="space-content">
        <div className="space-bank-layout">
          <nav className="space-scope-rail" aria-label="笔记本列表">
            <button
              className="space-scope-item"
              onClick={() => {
                setCreating(true);
                setNewName('');
                setNewDesc('');
              }}
            >
              <Plus size={14} />
              <span>新建笔记本</span>
            </button>
            {notebooks.length > 6 && (
              <input
                className="space-search"
                type="search"
                placeholder="搜索笔记本…"
                aria-label="搜索笔记本"
                value={notebookQuery}
                onChange={(e) => setNotebookQuery(e.target.value)}
              />
            )}
            {filteredNotebooks.map((notebook) => (
              <button
                key={notebook.id}
                className={`space-scope-item ${selectedId === notebook.id ? 'current' : ''}`}
                aria-pressed={selectedId === notebook.id}
                onClick={() => selectNotebook(notebook.id)}
              >
                <span
                  aria-hidden
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: COLOR_DOT[notebook.color],
                    flexShrink: 0,
                  }}
                />
                <span style={{ flex: 1, textAlign: 'left' }}>{notebook.name}</span>
                <span className="count">{listRecords().filter((r) => r.notebookId === notebook.id).length}</span>
              </button>
            ))}
          </nav>

          <div className="space-bank-main">
            <div className="space-banner info" role="note">
              参考产品中记录由聊天/研究/写作功能产生，此处不提供「新建记录」；在聊天中使用「保存到笔记」即可沉淀记录。
            </div>
            {notice && (
              <div className="space-banner info" role="status">
                {notice}
              </div>
            )}
            {error && (
              <div className="space-banner error" role="alert">
                {error}
              </div>
            )}

            {loading ? (
              <div aria-hidden>
                <div className="space-skeleton" style={{ height: 120 }} />
              </div>
            ) : !selected ? (
              <div className="space-empty">
                <strong>选择一个笔记本</strong>
                <span>左侧选择笔记本查看其中的记录；新建后即可开始整理。</span>
              </div>
            ) : (
              <>
                <div className="space-session-top" style={{ marginBottom: 12 }}>
                  <span
                    aria-hidden
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 999,
                      background: COLOR_DOT[selected.color],
                    }}
                  />
                  <span className="space-session-title" style={{ fontSize: 17 }}>
                    {selected.name}
                  </span>
                  <span className="space-chip">{selectedRecords.length} 条记录</span>
                  <span className="space-session-actions">
                    <button
                      className="space-button"
                      onClick={() => setEditingNotebook(selected)}
                    >
                      <Pencil size={13} />
                      编辑
                    </button>
                    <button className="space-button" onClick={() => void handleExport()}>
                      <Download size={13} />
                      导出 Markdown
                    </button>
                    {selected.id !== 'notebook-main' && (
                      <button
                        className="space-button danger"
                        onClick={() => handleDeleteNotebook(selected)}
                      >
                        <Trash2 size={13} />
                        删除
                      </button>
                    )}
                  </span>
                </div>
                {selected.description && (
                  <p className="space-description" style={{ marginBottom: 10 }}>
                    {selected.description}
                  </p>
                )}
                {selectedRecords.length > 8 && (
                  <div className="space-toolbar">
                    <input
                      className="space-search"
                      type="search"
                      placeholder="搜索记录标题或内容…"
                      aria-label="搜索记录"
                      value={recordQuery}
                      onChange={(e) => setRecordQuery(e.target.value)}
                    />
                  </div>
                )}

                {selectedRecords.length === 0 ? (
                  <div className="space-empty">
                    <strong>这个笔记本还是空的</strong>
                    <span>在聊天里生成研究报告后点「保存到笔记」，记录会出现在这里。</span>
                  </div>
                ) : filteredRecords.length === 0 ? (
                  <div className="space-empty">
                    <strong>没有匹配的记录</strong>
                    <span>换个搜索词再试。</span>
                  </div>
                ) : (
                  <ul className="space-session-list">
                    {filteredRecords.map((record) => (
                      <RecordRow
                        key={record.id}
                        record={record}
                        expanded={expandedId === record.id}
                        onToggle={() =>
                          setExpandedId((current) => (current === record.id ? null : record.id))
                        }
                        onEdit={() => setEditingRecord(record)}
                        onDelete={() => {
                          if (window.confirm(`删除记录「${record.title}」？删除后无法恢复。`)) {
                            removeNotebookRecord(record.id);
                            setNotice(`已删除记录「${record.title}」。`);
                          }
                        }}
                        onMove={() => setMovingRecord(record)}
                      />
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      {creating && (
        <Modal title="新建笔记本" onClose={() => setCreating(false)}>
          <form
            className="space-form"
            onSubmit={(e) => {
              e.preventDefault();
              const notebook = createNotebook(newName, newDesc);
              if (!notebook) {
                setError('名称为空或已存在同名笔记本。');
                return;
              }
              setError(null);
              setCreating(false);
              setNotice(`已创建笔记本「${notebook.name}」。`);
              selectNotebook(notebook.id);
            }}
          >
            <label>
              名称
              <input
                value={newName}
                required
                maxLength={60}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="例如：月度整理"
              />
            </label>
            <label>
              简介
              <input
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="这个笔记本用来收集什么？"
              />
            </label>
            <div className="space-form-footer">
              <button type="button" className="space-button" onClick={() => setCreating(false)}>
                取消
              </button>
              <button type="submit" className="space-button primary">
                创建
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editingNotebook && (
        <NotebookEditForm
          notebook={editingNotebook}
          onClose={() => setEditingNotebook(null)}
          onSaved={(name) => {
            setEditingNotebook(null);
            setNotice(`已保存笔记本「${name}」。`);
          }}
        />
      )}

      {editingRecord && (
        <RecordEditForm
          record={editingRecord}
          onClose={() => setEditingRecord(null)}
          onSaved={(title) => {
            setEditingRecord(null);
            setNotice(`已保存记录「${title}」。`);
          }}
        />
      )}

      {movingRecord && (
        <MoveRecordForm
          record={movingRecord}
          notebooks={notebooks.filter((n) => n.id !== movingRecord.notebookId)}
          onClose={() => setMovingRecord(null)}
          onDone={(message) => {
            setMovingRecord(null);
            setNotice(message);
          }}
        />
      )}
    </div>
  );
}

function RecordRow({
  record,
  expanded,
  onToggle,
  onEdit,
  onDelete,
  onMove,
}: {
  record: NotebookRecord;
  expanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onMove: () => void;
}) {
  const sessionId = record.metadata?.sessionId;
  return (
    <li className="space-session-card">
      <div className="space-session-top">
        <button
          className="icon-button"
          aria-label={expanded ? `收起记录 ${record.title}` : `展开记录 ${record.title}`}
          aria-expanded={expanded}
          onClick={onToggle}
        >
          <ChevronRight
            size={14}
            style={{
              transform: expanded ? 'rotate(90deg)' : 'none',
              transition: 'transform 0.15s',
            }}
          />
        </button>
        <span className="space-session-title">{record.title}</span>
        <span className="space-chip blue">{TYPE_LABEL[record.type] ?? record.type}</span>
        <span className="space-session-actions">
          <button className="icon-button" aria-label={`编辑记录 ${record.title}`} onClick={onEdit}>
            <Pencil size={14} />
          </button>
          <button className="icon-button" aria-label={`移动或复制记录 ${record.title}`} onClick={onMove}>
            <FolderInput size={14} />
          </button>
          <button className="icon-button" aria-label={`删除记录 ${record.title}`} onClick={onDelete}>
            <Trash2 size={14} />
          </button>
        </span>
      </div>
      <div className="space-meta-row">
        <span>更新于 {new Date(record.updatedAt).toLocaleString('zh-CN')}</span>
      </div>
      {expanded && (
        <div className="space-explanation" style={{ whiteSpace: 'pre-wrap' }}>
          {record.summary && (
            <p>
              <strong>摘要：</strong>
              {record.summary}
            </p>
          )}
          {record.userQuery && (
            <p>
              <strong>提问：</strong>
              {record.userQuery}
            </p>
          )}
          {record.content || '（无正文）'}
          {sessionId && (
            <p style={{ marginTop: 10 }}>
              <Link className="space-button" href={`/chat/${sessionId}?mode=mock`}>
                打开原会话
              </Link>
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function NotebookEditForm({
  notebook,
  onClose,
  onSaved,
}: {
  notebook: Notebook;
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  const [name, setName] = useState(notebook.name);
  const [description, setDescription] = useState(notebook.description);
  const [color, setColor] = useState<NotebookColor>(notebook.color);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title={`编辑笔记本 · ${notebook.name}`} onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(e) => {
          e.preventDefault();
          const updated = updateNotebook(notebook.id, { name, description, color });
          if (!updated) {
            setError('名称为空或已存在同名笔记本。');
            return;
          }
          onSaved(updated.name);
        }}
      >
        <label>
          名称
          <input value={name} required maxLength={60} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          简介
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <fieldset
          style={{ border: 0, padding: 0, margin: 0 }}
        >
          <legend className="space-footnote" style={{ padding: 0 }}>
            颜色标记
          </legend>
          <div className="space-card-actions">
            {NOTEBOOK_COLORS.map((value) => (
              <button
                type="button"
                key={value}
                aria-label={`颜色 ${value}`}
                aria-pressed={color === value}
                onClick={() => setColor(value)}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 999,
                  background: COLOR_DOT[value],
                  outline: color === value ? '2px solid var(--ink)' : 'none',
                  outlineOffset: 2,
                }}
              />
            ))}
          </div>
        </fieldset>
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

function RecordEditForm({
  record,
  onClose,
  onSaved,
}: {
  record: NotebookRecord;
  onClose: () => void;
  onSaved: (title: string) => void;
}) {
  const [title, setTitle] = useState(record.title);
  const [summary, setSummary] = useState(record.summary ?? '');
  const [content, setContent] = useState(record.content);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title={`编辑记录 · ${record.title}`} onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(e) => {
          e.preventDefault();
          const updated = updateNotebookRecord(record.id, {
            title,
            summary,
            content,
          });
          if (!updated) {
            setError('保存失败：记录不存在或已被删除。');
            return;
          }
          onSaved(updated.title);
        }}
      >
        <label>
          标题
          <input value={title} required onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          摘要（可选）
          <input value={summary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <label>
          正文
          <textarea value={content} onChange={(e) => setContent(e.target.value)} />
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

function MoveRecordForm({
  record,
  notebooks,
  onClose,
  onDone,
}: {
  record: NotebookRecord;
  notebooks: Notebook[];
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [target, setTarget] = useState(notebooks[0]?.id ?? '');
  return (
    <Modal title={`移动或复制 · ${record.title}`} onClose={onClose}>
      {notebooks.length === 0 ? (
        <div className="space-empty">
          <strong>没有其他笔记本</strong>
          <span>先新建一个笔记本，再移动或复制记录。</span>
          <div className="space-form-footer" style={{ width: '100%' }}>
            <button className="space-button" onClick={onClose}>
              关闭
            </button>
          </div>
        </div>
      ) : (
        <form
          className="space-form"
          onSubmit={(e) => {
            e.preventDefault();
            const mode = (new FormData(e.currentTarget).get('mode') as string) === 'copy' ? 'copy' : 'move';
            const done = relocateRecord(record.id, target, mode);
            if (!done) {
              onDone('操作失败：记录或目标笔记本不存在。');
              return;
            }
            onDone(
              mode === 'move'
                ? `已把「${record.title}」移动到目标笔记本。`
                : `已把「${record.title}」复制到目标笔记本（生成副本）。`,
            );
          }}
        >
          <label>
            目标笔记本
            <select
              className="space-select"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              {notebooks.map((notebook) => (
                <option key={notebook.id} value={notebook.id}>
                  {notebook.name}
                </option>
              ))}
            </select>
          </label>
          <div className="space-card-actions" role="radiogroup" aria-label="操作方式">
            <label className="space-toggle">
              <input type="radio" name="mode" value="move" defaultChecked />
              移动（从当前笔记本移出）
            </label>
            <label className="space-toggle">
              <input type="radio" name="mode" value="copy" />
              <Copy size={12} />
              复制（保留原记录，生成副本）
            </label>
          </div>
          <p className="space-footnote" style={{ margin: 0 }}>
            <TriangleAlert size={12} aria-hidden /> 移动后当前列表将不再显示该记录。
          </p>
          <div className="space-form-footer">
            <button type="button" className="space-button" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="space-button primary">
              执行
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
