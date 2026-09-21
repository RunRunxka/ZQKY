'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileText, FolderPlus, Inbox, Plus, RefreshCw, Sparkles, Square, Trash2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { cancelMaterialIngest, simulateMaterialIngest } from '@/services/reading-ingest';
import {
  ReadingValidationError,
  addMaterialToWorkspace,
  createMaterial,
  deleteMaterial,
  loadDemoReading,
  readMaterials,
  readWorkspaces,
  subscribeReading,
  updateMaterialStatus,
  type ReadingMaterial,
  type ReadingSourceKind,
  type ReadingWorkspace,
} from '@/services/reading-store';
import '@/features/space/styles/space.css';
import '@/features/reading/reading.css';
import '@/features/reading/styles/reading-library.css';

const SIMULATED_KINDS: Array<{ value: Exclude<ReadingSourceKind, 'text'>; label: string }> = [
  { value: 'pdf', label: 'PDF（模拟解析）' },
  { value: 'epub', label: 'EPUB（模拟解析）' },
  { value: 'webpage', label: '网页（模拟抓取）' },
  { value: 'video', label: '视频（模拟转录）' },
  { value: 'audio', label: '音频（模拟转录）' },
];

/** /reading/materials：材料库（对照参考 MaterialLibrary；解析未接入，仅文本材料） */
export function MaterialLibrary() {
  const router = useRouter();
  const [materials, setMaterials] = useState<ReadingMaterial[]>([]);
  const [workspaces, setWorkspaces] = useState<ReadingWorkspace[]>([]);
  const [filter, setFilter] = useState<'all' | 'unassigned' | 'processing' | 'failed'>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    try {
      setMaterials(readMaterials());
      setWorkspaces(readWorkspaces());
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

  const filtered = useMemo(() => {
    if (filter === 'unassigned') return materials.filter((item) => item.workspaceIds.length === 0);
    if (filter === 'processing') {
      return materials.filter((item) => item.status === 'processing' || item.status === 'queued');
    }
    if (filter === 'failed') return materials.filter((item) => item.status === 'failed');
    return materials;
  }, [materials, filter]);

  // 筛选计数：与参考 tally 同口径，从真实材料数组推导（无服务端计数可兜底）
  const counts = useMemo(
    () => ({
      all: materials.length,
      unassigned: materials.filter((item) => item.workspaceIds.length === 0).length,
      processing: materials.filter((item) => item.status === 'processing' || item.status === 'queued').length,
      failed: materials.filter((item) => item.status === 'failed').length,
    }),
    [materials],
  );

  return (
    <div className="space-page reading-lib-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>阅读材料库</h1>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                try {
                  loadDemoReading();
                  setNotice('已载入演示阅读数据（重复载入不产生重复条目）。');
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
              新建材料
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
            全部
            <span className="reading-lib-count">（{counts.all}）</span>
          </button>
          <button
            role="tab"
            aria-selected={filter === 'unassigned'}
            className={filter === 'unassigned' ? 'current' : ''}
            onClick={() => setFilter('unassigned')}
          >
            未分配集合
            <span className="reading-lib-count">（{counts.unassigned}）</span>
          </button>
          <button
            role="tab"
            aria-selected={filter === 'processing'}
            className={filter === 'processing' ? 'current' : ''}
            onClick={() => setFilter('processing')}
          >
            解析中
            <span className="reading-lib-count">（{counts.processing}）</span>
          </button>
          <button
            role="tab"
            aria-selected={filter === 'failed'}
            className={filter === 'failed' ? 'current' : ''}
            onClick={() => setFilter('failed')}
          >
            解析失败
            <span className="reading-lib-count">（{counts.failed}）</span>
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
            <span className="reading-lib-empty-icon" aria-hidden>
              <Inbox size={18} />
            </span>
            <strong>
              {filter === 'all'
                ? '还没有材料'
                : filter === 'unassigned'
                  ? '没有未分配的材料'
                  : filter === 'processing'
                    ? '没有解析中的材料'
                    : '没有解析失败的材料'}
            </strong>
            <span>新建文本材料或载入演示数据。</span>
            <div className="reading-lib-empty-actions">
              {/* 空态主行动：aria-label 与页头「新建材料」区分，避免同名按钮歧义（对齐 I1 修复口径） */}
              <button
                className="space-button primary"
                aria-label="新建第一份材料"
                onClick={() => setCreating(true)}
              >
                <Plus size={14} />
                新建材料
              </button>
            </div>
          </div>
        ) : (
          <ul className="space-session-list">
            {filtered.map((material) => {
              const status = material.status ?? 'ready';
              return (
                <li className="space-session-card" key={material.id}>
                  <div className="space-session-top">
                    <span className="reading-lib-row-head">
                      <FileText size={14} aria-hidden />
                      <span className="space-session-title">{material.title}</span>
                    </span>
                    <span className="space-chip">{material.charCount} 字</span>
                    <span className="space-chip">{material.sourceKind === 'text' ? '文本' : `${material.sourceKind.toUpperCase()} · 模拟解析`}</span>
                    <span
                      className={`space-chip ${
                        status === 'failed'
                          ? 'reading-lib-status-failed'
                          : status === 'ready'
                            ? 'reading-lib-status-ready'
                            : 'reading-lib-status-busy'
                      }`}
                    >
                      <span
                        className={`reading-lib-dot ${
                          status === 'failed' ? 'is-failed' : status === 'ready' ? 'is-ready' : 'is-busy'
                        }`}
                        aria-hidden
                      />
                      {status === 'ready' && '就绪'}
                      {status === 'queued' && '排队中'}
                      {status === 'processing' && '解析中'}
                      {status === 'failed' && '解析失败'}
                    </span>
                    <span className="space-chip">{material.workspaceIds.length > 0 ? `已入 ${material.workspaceIds.length} 个集合` : '未分配'}</span>
                    <span className="space-session-actions">
                      {status === 'failed' && (
                        <button
                          className="space-button"
                          aria-label={`重试解析 ${material.title}`}
                          onClick={() => {
                            updateMaterialStatus(material.id, 'queued', null);
                            simulateMaterialIngest(material.id);
                          }}
                        >
                          <RefreshCw size={12} />
                          重试解析
                        </button>
                      )}
                      {(status === 'queued' || status === 'processing') && (
                        <button
                          className="space-button"
                          aria-label={`取消解析 ${material.title}`}
                          onClick={() => cancelMaterialIngest(material.id)}
                        >
                          <Square size={12} />
                          取消解析
                        </button>
                      )}
                      {status === 'ready' && material.workspaceIds.length === 0 && (
                        <AssignButton material={material} workspaces={workspaces} onDone={(msg) => setNotice(msg)} />
                      )}
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
                  {status === 'failed' && material.statusNote && (
                    <div className="space-meta-row">
                      <span role="status">{material.statusNote}</span>
                    </div>
                  )}
                  <div className="space-meta-row">
                    <span>更新于 {new Date(material.updatedAt).toLocaleString('zh-CN')}</span>
                  </div>
                </li>
              );
            })}
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

function AssignButton({
  material,
  workspaces,
  onDone,
}: {
  material: ReadingMaterial;
  workspaces: ReadingWorkspace[];
  onDone: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="space-button" aria-label={`分配材料 ${material.title}`} onClick={() => setOpen(true)}>
        <FolderPlus size={12} aria-hidden />
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
  const [kind, setKind] = useState<ReadingSourceKind>('text');
  const [filename, setFilename] = useState('');
  const [simulateFail, setSimulateFail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title="新建材料" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            if (kind === 'text') {
              const material = createMaterial({ title, text });
              onCreated(material.id);
              return;
            }
            // 非文本：真实解析未接入，走显式模拟解析流程（queued → ready/failed）
            const material = createMaterial({
              title,
              sourceKind: kind,
              filename,
              status: 'queued',
              extractor: `${kind}-simulated`,
            });
            onCreated(material.id);
            simulateMaterialIngest(material.id, { fail: simulateFail });
          } catch (cause) {
            setError(cause instanceof ReadingValidationError ? cause.message : '创建失败，请检查输入后重试。');
          }
        }}
      >
        <p className="space-footnote" style={{ marginTop: 0 }}>
          以“# 标题”开头的行按标题层级渲染。非文本类型为显式模拟：真实 PDF/网页/媒体解析未接入，解析产物为本地结构化样例并全程标注。
        </p>
        <label>
          材料类型
          <select value={kind} onChange={(event) => setKind(event.target.value as ReadingSourceKind)} aria-label="材料类型">
            <option value="text">文本（粘贴录入）</option>
            {SIMULATED_KINDS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          标题
          <input value={title} required maxLength={80} onChange={(event) => setTitle(event.target.value)} placeholder="例如：课程纲要摘录" />
        </label>
        {kind === 'text' ? (
          <label>
            正文
            <textarea value={text} style={{ minHeight: 140 }} onChange={(event) => setText(event.target.value)} placeholder={'# 第一章\n\n正文…'} />
          </label>
        ) : (
          <>
            <label>
              文件名（模拟导入，不读取真实文件）
              <input
                value={filename}
                required
                maxLength={120}
                onChange={(event) => setFilename(event.target.value)}
                placeholder={kind === 'webpage' ? 'https://example.com/article' : '示例文件.pdf'}
              />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" checked={simulateFail} onChange={(event) => setSimulateFail(event.target.checked)} />
              模拟一次解析失败（演示失败与重试路径）
            </label>
          </>
        )}
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
            {kind === 'text' ? '创建' : '导入并开始模拟解析'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
