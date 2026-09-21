'use client';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { BookOpen, FileText, Library, MessagesSquare, Plus, Sparkles, Trash2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  ReadingValidationError,
  createWorkspace,
  deleteWorkspace,
  loadDemoReading,
  readMaterials,
  readSessions,
  readWorkspaces,
  subscribeReading,
  type ReadingMaterial,
  type ReadingSession,
  type ReadingWorkspace,
} from '@/services/reading-store';
import '@/features/space/styles/space.css';
import '@/features/reading/reading.css';
import '@/features/reading/styles/reading-library.css';

/** /reading 入口：阅读集合列表（对照参考 ReadingLibrary；材料解析/转录为本地模拟） */
export function ReadingLibrary() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<ReadingWorkspace[]>([]);
  const [materials, setMaterials] = useState<ReadingMaterial[]>([]);
  const [sessions, setSessions] = useState<ReadingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    try {
      setWorkspaces(readWorkspaces());
      setMaterials(readMaterials());
      setSessions(readSessions());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '阅读数据无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeReading(refresh);
  }, [refresh]);

  return (
    <div className="space-page reading-lib-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>沉浸阅读</h1>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                try {
                  loadDemoReading();
                  setNotice('已载入演示阅读数据（重复载入不产生重复条目）。材料解析与伴生回复为本地模拟。');
                } catch (cause) {
                  setNotice(cause instanceof Error ? cause.message : '演示数据载入失败，原数据未修改。');
                }
              }}
            >
              <Sparkles size={14} />
              载入演示数据
            </button>
            <button className="space-button primary" onClick={() => setCreating(true)}>
              <Plus size={14} />
              新建阅读集合
            </button>
          </div>
        </div>
        <p className="space-description">
          以集合组织阅读材料与伴生会话；材料解析（PDF/EPUB/媒体/网页）未接入，仅登记文本材料；批注、书签与阅读位置本地保存。
        </p>
      </header>
      <main className="space-content">
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
        ) : workspaces.length === 0 ? (
          <div className="space-empty">
            <span className="reading-lib-empty-icon" aria-hidden>
              <Library size={18} />
            </span>
            <strong>还没有阅读集合</strong>
            <span>新建集合并加入文本材料开始阅读，或载入演示数据。</span>
            <div className="reading-lib-empty-actions">
              {/* 空态主行动：aria-label 与页头「新建阅读集合」区分，避免同名按钮歧义（对齐 I1 修复口径） */}
              <button
                className="space-button primary"
                aria-label="新建第一篇阅读集合"
                onClick={() => setCreating(true)}
              >
                <Plus size={14} />
                新建阅读集合
              </button>
            </div>
          </div>
        ) : (
          <div className="space-card-grid">
            {workspaces.map((workspace) => {
              const materialsOf = materials.filter((item) => item.workspaceIds.includes(workspace.id));
              const sessionsOf = sessions.filter((item) => item.workspaceId === workspace.id);
              return (
                <article className="space-persona-card" key={workspace.id}>
                  <Link
                    className="space-card-link"
                    href={`/reading/${workspace.id}`}
                    aria-label={`打开阅读集合 ${workspace.title}`}
                  >
                    <div className="space-card-title">
                      <BookOpen size={15} aria-hidden />
                      {workspace.title}
                    </div>
                    <p className="space-card-body">{workspace.description || '（无简介）'}</p>
                    <div className="space-meta-row">
                      <span className="space-chip">
                        <FileText size={12} className="reading-lib-chip-icon" aria-hidden />
                        材料 {materialsOf.length}
                      </span>
                      <span className="space-chip">
                        <MessagesSquare size={12} className="reading-lib-chip-icon" aria-hidden />
                        会话 {sessionsOf.length}
                      </span>
                      <span className="space-chip">本地目录</span>
                    </div>
                  </Link>
                  <div className="space-card-actions" style={{ marginTop: 8 }}>
                    <button className="space-button" onClick={() => router.push(`/reading/${workspace.id}`)}>
                      进入阅读
                    </button>
                    <button
                      className="space-button danger"
                      aria-label={`删除集合 ${workspace.title}`}
                      onClick={() => {
                        if (window.confirm(`删除阅读集合「${workspace.title}」？材料保留在库中，伴生会话将一并删除。`)) {
                          deleteWorkspace(workspace.id);
                        }
                      }}
                    >
                      <Trash2 size={14} />
                      删除
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {creating && (
          <CreateWorkspaceForm
            onClose={() => setCreating(false)}
            onCreated={(id) => {
              setCreating(false);
              router.push(`/reading/${id}`);
            }}
          />
        )}
      </main>
    </div>
  );
}

function CreateWorkspaceForm({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title="新建阅读集合" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const workspace = createWorkspace(title, description);
            onCreated(workspace.id);
          } catch (cause) {
            setError(cause instanceof ReadingValidationError ? cause.message : '创建失败，请检查输入后重试。');
          }
        }}
      >
        <label>
          名称
          <input value={title} required maxLength={60} onChange={(event) => setTitle(event.target.value)} placeholder="例如：分数专题阅读" />
        </label>
        <label>
          简介
          <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="这个集合用来读什么？" />
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
