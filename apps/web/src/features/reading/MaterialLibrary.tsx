'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileText, Plus, Sparkles, Trash2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  ReadingValidationError,
  addMaterialToWorkspace,
  createMaterial,
  deleteMaterial,
  loadDemoReading,
  readMaterials,
  readWorkspaces,
  subscribeReading,
  type ReadingMaterial,
} from '@/services/reading-store';
import '@/features/space/styles/space.css';
import '@/features/reading/reading.css';

/** /reading/materials：材料库（对照参考 MaterialLibrary；解析未接入，仅文本材料） */
export function MaterialLibrary() {
  const router = useRouter();
  const [materials, setMaterials] = useState<ReadingMaterial[]>([]);
  const [filter, setFilter] = useState<'all' | 'unassigned'>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    try {
      setMaterials(readMaterials());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '材料库无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeReading(refresh);
  }, [refresh]);

  const filtered = useMemo(
    () => (filter === 'unassigned' ? materials.filter((item) => item.workspaceIds.length === 0) : materials),
    [materials, filter],
  );

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>阅读材料库</h1>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                loadDemoReading();
                setNotice('已载入演示阅读数据（重复载入不产生重复条目）。');
              }}
            >
              <Sparkles size={14} />
              载入演示数据
            </button>
            <button className="space-button primary" onClick={() => setCreating(true)}>
              <Plus size={14} />
              新建文本材料
            </button>
          </div>
        </div>
        <p className="space-description">
          材料解析（PDF/EPUB/DOCX/网页/音视频转录）依赖服务端，未接入；此处登记文本材料（粘贴或录入），可在阅读集合中打开。
        </p>
      </header>
      <main className="space-content">
        <div className="space-tabs" role="tablist" aria-label="材料筛选">
          <button role="tab" aria-selected={filter === 'all'} className={filter === 'all' ? 'current' : ''} onClick={() => setFilter('all')}>
            全部（{materials.length}）
          </button>
          <button
            role="tab"
            aria-selected={filter === 'unassigned'}
            className={filter === 'unassigned' ? 'current' : ''}
            onClick={() => setFilter('unassigned')}
          >
            未分配集合（{materials.filter((item) => item.workspaceIds.length === 0).length}）
          </button>
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
            <div className="space-skeleton" style={{ height: 76, marginBottom: 10 }} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="space-empty">
            <strong>{filter === 'all' ? '还没有材料' : '没有未分配的材料'}</strong>
            <span>新建文本材料或载入演示数据。</span>
          </div>
        ) : (
          <ul className="space-session-list">
            {filtered.map((material) => (
              <li className="space-session-card" key={material.id}>
                <div className="space-session-top">
                  <FileText size={14} aria-hidden />
                  <span className="space-session-title">{material.title}</span>
                  <span className="space-chip">{material.charCount} 字</span>
                  <span className="space-chip">{material.workspaceIds.length > 0 ? `已入 ${material.workspaceIds.length} 个集合` : '未分配'}</span>
                  <span className="space-session-actions">
                    {material.workspaceIds.length === 0 && <AssignButton material={material} onDone={(msg) => setNotice(msg)} />}
                    <button
                      className="icon-button"
                      aria-label={`删除材料 ${material.title}`}
                      onClick={() => {
                        if (window.confirm(`删除材料「${material.title}」？其批注与书签将一并删除。`)) {
                          deleteMaterial(material.id);
                        }
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </span>
                </div>
                <div className="space-meta-row">
                  <span>更新于 {new Date(material.updatedAt).toLocaleString('zh-CN')}</span>
                </div>
              </li>
            ))}
          </ul>
        )}

        {creating && (
          <CreateMaterialForm
            onClose={() => setCreating(false)}
            onCreated={(id) => {
              setCreating(false);
              router.push(`/reading/materials?focus=${id}`);
            }}
          />
        )}
      </main>
    </div>
  );
}

function AssignButton({ material, onDone }: { material: ReadingMaterial; onDone: (message: string) => void }) {
  const [open, setOpen] = useState(false);
  const workspaces = readWorkspaces();
  return (
    <>
      <button className="space-button" aria-label={`分配材料 ${material.title}`} onClick={() => setOpen(true)}>
        分配到集合
      </button>
      {open && (
        <Modal title={`分配「${material.title}」`} onClose={() => setOpen(false)}>
          {workspaces.length === 0 ? (
            <div className="space-empty">
              <strong>还没有阅读集合</strong>
              <span>先到「沉浸阅读」新建集合。</span>
            </div>
          ) : (
            <ul className="space-session-list">
              {workspaces.map((workspace) => (
                <li className="space-session-card" key={workspace.id}>
                  <div className="space-session-top">
                    <span className="space-session-title">{workspace.title}</span>
                    <button
                      className="space-button"
                      onClick={() => {
                        try {
                          addMaterialToWorkspace(workspace.id, material.id, false);
                          onDone(`已把「${material.title}」加入「${workspace.title}」。`);
                          setOpen(false);
                        } catch (cause) {
                          onDone(cause instanceof ReadingValidationError ? cause.message : '分配失败，请重试。');
                        }
                      }}
                    >
                      加入
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Modal>
      )}
    </>
  );
}

function CreateMaterialForm({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title="新建文本材料" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const material = createMaterial({ title, text });
            onCreated(material.id);
          } catch (cause) {
            setError(cause instanceof ReadingValidationError ? cause.message : '创建失败，请检查输入后重试。');
          }
        }}
      >
        <p className="space-footnote" style={{ marginTop: 0 }}>
          以“# 标题”开头的行会按标题层级渲染；仅支持文本材料（PDF/网页/媒体解析未接入）。
        </p>
        <label>
          标题
          <input value={title} required maxLength={80} onChange={(event) => setTitle(event.target.value)} placeholder="例如：课程纲要摘录" />
        </label>
        <label>
          正文
          <textarea value={text} style={{ minHeight: 140 }} onChange={(event) => setText(event.target.value)} placeholder={'# 第一章\n\n正文…'} />
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
