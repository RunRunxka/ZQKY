'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
// 复用 space 设计语言的样式；直达路由也需要加载（不能只依赖 SpaceMain 的引入）
import '@/features/space/styles/space.css';
import {
  ArrowLeft,
  FileUp,
  Github,
  Globe,
  RefreshCw,
  Square,
  Star,
  Trash2,
  TriangleAlert,
} from 'lucide-react';
import {
  addKbDocument,
  addKbSource,
  deleteKnowledge,
  kbPipelineSummary,
  KnowledgeValidationError,
  readKnowledge,
  removeKbDocument,
  removeKbSource,
  setDefaultKnowledge,
  subscribeKnowledge,
  updateKbDocument,
  updateKnowledge,
  type KbDocStatus,
  type KbPipelineSummary,
  type KnowledgeEntry,
} from '@/services/knowledge-catalog';
import {
  cancelKbDocIngest,
  resumeKbIngests,
  simulateKbDocIngest,
  simulateKbIngestAll,
} from '@/services/knowledge-ingest';

type DetailSection = 'files' | 'add' | 'sources' | 'versions' | 'settings';

const SECTIONS: { id: DetailSection; label: string }[] = [
  { id: 'files', label: '文档' },
  { id: 'add', label: '登记文档' },
  { id: 'sources', label: '外部来源' },
  { id: 'versions', label: '索引' },
  { id: 'settings', label: '设置' },
];

const KB_PIPELINE_LABEL: Record<KbPipelineSummary['status'], string> = {
  empty: '空',
  registered: '待处理',
  processing: '处理中',
  ready: '已就绪',
  error: '有失败',
};

/** 复用现有 space-chip 变体（green 表就绪） */
const KB_PIPELINE_TONE: Record<KbPipelineSummary['status'], string> = {
  empty: '',
  registered: '',
  processing: 'blue',
  ready: 'green',
  error: 'amber',
};

const DOC_STATUS_LABEL: Record<KbDocStatus, string> = {
  registered: '未解析 · 未索引',
  parsing: '解析中',
  indexing: '索引中',
  ready: '已解析 · 已索引',
  error: '处理失败',
};

const DOC_STATUS_TONE: Record<KbDocStatus, string> = {
  registered: '',
  parsing: 'blue',
  indexing: 'blue',
  ready: 'green',
  error: 'amber',
};

function formatSize(size: number | undefined): string {
  if (!size) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function KnowledgeBaseDetailSection() {
  const params = useParams<{ kbName: string }>();
  const kbName = decodeURIComponent(params.kbName);
  const [kbs, setKbs] = useState<KnowledgeEntry[] | null>(null);
  const [section, setSection] = useState<DetailSection>('files');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    try {
      setKbs(readKnowledge());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '知识库目录无法读取，原数据未修改。');
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeKnowledge(refresh);
  }, [refresh]);

  const kb = useMemo(() => kbs?.find((entry) => entry.name === kbName) ?? null, [kbs, kbName]);
  const kbId = kb?.id ?? null;

  // 刷新恢复：挂载后对处于 parsing/indexing 的文档重新挂载模拟推进。
  // 仅在对应 KB 的 id 变化时执行，避免与 subscribeKnowledge 的每次刷新重复启动。
  useEffect(() => {
    if (kbId) resumeKbIngests(kbId);
  }, [kbId]);

  if (kbs !== null && !kb) {
    return (
      <div className="space-page">
        <div className="space-empty" style={{ marginTop: 80 }}>
          <strong>知识库「{kbName}」不存在</strong>
          <span>它可能已被删除，或链接有误。</span>
          <Link className="space-button" href="/knowledge-bases">
            <ArrowLeft size={14} />
            返回资料库列表
          </Link>
        </div>
      </div>
    );
  }

  if (!kb) {
    // kbs 仍为 null 时可能是读取中，也可能是读取失败：失败必须如实提示，不能停在“读取中”
    return (
      <div className="space-page">
        {error ? (
          <div className="space-banner error" role="alert" style={{ marginTop: 80 }}>
            {error}
          </div>
        ) : (
          <div className="space-banner" style={{ marginTop: 80 }}>
            正在读取知识库…
          </div>
        )}
      </div>
    );
  }

  const summary = kbPipelineSummary(kb);

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/knowledge-bases">
            <ArrowLeft size={16} />
            返回资料库
          </Link>
          <div className="space-card-actions">
            {!kb.isDefault && (
              <button
                className="space-button"
                onClick={() => {
                  setDefaultKnowledge(kb.id);
                  setNotice(`已将「${kb.name}」设为默认库。聊天知识来源选择不受影响（仍为范围声明）。`);
                }}
              >
                <Star size={14} />
                设为默认库
              </button>
            )}
          </div>
        </div>
        <h1>
          {kb.name}
          {kb.isDefault && <span className="space-chip amber" style={{ marginLeft: 10 }}>默认库</span>}
          <span className={`space-chip ${KB_PIPELINE_TONE[summary.status]}`} style={{ marginLeft: 8 }}>
            知识库状态：{KB_PIPELINE_LABEL[summary.status]}
          </span>
        </h1>
        <p className="space-description">{kb.description || '（无简介）'}</p>
      </header>
      <main className="space-content">
        <div className="space-banner info" role="note">
          <TriangleAlert size={13} aria-hidden style={{ display: 'inline', marginRight: 6 }} />
          解析与索引为显式模拟：真实文件内容读取与向量检索服务未接入，模拟产物为本地结构化样例并全程标注，不代表真实服务结果。
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

        <nav className="space-segment" aria-label="知识库分区" style={{ marginBottom: 16 }}>
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              className={section === item.id ? 'current' : ''}
              aria-pressed={section === item.id}
              onClick={() => setSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {section === 'files' && <DocList kb={kb} onNotice={setNotice} onError={setError} />}
        {section === 'add' && <RegisterDocs kb={kb} onNotice={setNotice} />}
        {section === 'sources' && <SourceList kb={kb} onNotice={setNotice} onError={setError} />}
        {section === 'versions' && <IndexVersions kb={kb} onNotice={setNotice} />}
        {section === 'settings' && (
          <SettingsTab kb={kb} onNotice={setNotice} onError={setError} />
        )}
      </main>
    </div>
  );
}

function DocList({
  kb,
  onNotice,
  onError,
}: {
  kb: KnowledgeEntry;
  onNotice: (value: string) => void;
  onError: (value: string) => void;
}) {
  const docs = kb.docs ?? [];
  const summary = kbPipelineSummary(kb);
  const errorDocs = docs.filter((doc) => (doc.status ?? 'registered') === 'error');

  if (docs.length === 0) {
    return (
      <div className="space-empty">
        <strong>还没有登记文档</strong>
        <span>到「登记文档」选择文件登记（仅元信息），或载入演示数据。</span>
      </div>
    );
  }

  return (
    <div className="space-category-manager">
      <div className="space-toolbar">
        <span className="space-footnote" style={{ marginTop: 0, flex: '1 1 200px' }}>
          共 {summary.total} 个文档 · 就绪 {summary.ready} · 处理中 {summary.active} · 失败 {summary.error}（解析/索引为显式模拟）
        </span>
        <button
          className="space-button"
          onClick={() => {
            simulateKbIngestAll(kb.id);
            onNotice('已启动全部文档的模拟解析（本地结构化样例，非真实解析）。');
          }}
        >
          <RefreshCw size={12} />
          全部解析并索引
        </button>
        {summary.error > 0 && (
          <button
            className="space-button"
            onClick={() => {
              for (const doc of errorDocs) simulateKbDocIngest(kb.id, doc.id);
              onNotice(`已重试 ${errorDocs.length} 个失败文档的模拟解析。`);
            }}
          >
            <RefreshCw size={12} />
            重试失败项
          </button>
        )}
      </div>
      <ul className="space-session-list">
        {docs.map((doc) => {
          const status = doc.status ?? 'registered';
          const active = status === 'parsing' || status === 'indexing';
          const percent = doc.progress?.percent ?? 0;
          return (
            <li className="space-session-card" key={doc.id}>
              <div className="space-session-top">
                <span className="space-session-title">{doc.name}</span>
                <span className={`space-chip ${DOC_STATUS_TONE[status]}`}>
                  {DOC_STATUS_LABEL[status]}
                </span>
                {status === 'ready' && doc.chunks != null && (
                  <span className="space-chip">{doc.chunks} 块（模拟）</span>
                )}
                {active && (
                  <button
                    className="space-button"
                    aria-label={`取消解析 ${doc.name}`}
                    onClick={() => {
                      cancelKbDocIngest(kb.id, doc.id);
                      onNotice(`已取消「${doc.name}」的模拟解析（可重试）。`);
                    }}
                  >
                    <Square size={12} />
                    取消解析
                  </button>
                )}
                {status === 'error' && (
                  <button
                    className="space-button"
                    aria-label={`重试解析 ${doc.name}`}
                    onClick={() => {
                      simulateKbDocIngest(kb.id, doc.id);
                      onNotice(`已重新启动「${doc.name}」的模拟解析。`);
                    }}
                  >
                    <RefreshCw size={12} />
                    重试解析
                  </button>
                )}
                <button
                  className="icon-button"
                  aria-label={`移除文档 ${doc.name}`}
                  onClick={() => {
                    if (removeKbDocument(kb.id, doc.id)) onNotice(`已移除登记：${doc.name}。`);
                    else onError('移除失败：文档不存在或已被删除。');
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
              {active && (
                <div className="space-meta-row">
                  <span className="space-chip blue">
                    {doc.progress?.stage ?? DOC_STATUS_LABEL[status]} {percent}%
                  </span>
                  <div
                    role="progressbar"
                    aria-label={`${doc.name} 模拟处理进度`}
                    aria-valuenow={percent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    style={{ flex: 1, height: 6, borderRadius: 999, background: '#dbeafe', overflow: 'hidden' }}
                  >
                    <div
                      className="transition-all duration-300"
                      style={{
                        height: '100%',
                        width: `${Math.max(percent, 4)}%`,
                        borderRadius: 999,
                        background: '#2563eb',
                      }}
                    />
                  </div>
                </div>
              )}
              {status === 'error' && doc.statusNote && (
                <div className="space-meta-row">
                  <span role="status">{doc.statusNote}</span>
                </div>
              )}
              <div className="space-meta-row">
                <span>{formatSize(doc.size)}</span>
                <span>登记于 {new Date(doc.registeredAt).toLocaleString('zh-CN')}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function IndexVersions({
  kb,
  onNotice,
}: {
  kb: KnowledgeEntry;
  onNotice: (value: string) => void;
}) {
  const versions = [...(kb.indexVersions ?? [])].sort((a, b) => b.version - a.version);
  const docs = kb.docs ?? [];
  return (
    <div className="space-category-manager">
      <div className="space-toolbar">
        <span className="space-footnote" style={{ marginTop: 0, flex: '1 1 200px' }}>
          索引为显式模拟：版本记录为本地结构化样例，真实向量检索未接入。
        </span>
        <button
          className="space-button"
          disabled={docs.length === 0}
          onClick={() => {
            for (const doc of docs) {
              updateKbDocument(kb.id, doc.id, { status: 'registered', statusNote: null, progress: null });
            }
            simulateKbIngestAll(kb.id);
            onNotice('已重跑全部文档的模拟索引流水线（本地样例，非真实索引）。');
          }}
        >
          <RefreshCw size={12} />
          重建索引
        </button>
      </div>
      {versions.length === 0 ? (
        <div className="space-empty">
          <strong>还没有索引版本</strong>
          <span>
            解析与索引为显式模拟：登记文档并处理完成后会生成标注为模拟的本地索引版本；真实向量检索服务未接入。
          </span>
        </div>
      ) : (
        <ul className="space-session-list">
          {versions.map((version) => (
            <li className="space-session-card" key={version.id}>
              <div className="space-session-top">
                <span className="space-session-title">版本 {version.version}</span>
                <span className={`space-chip ${version.ready ? 'green' : ''}`}>
                  {version.ready ? '就绪' : '未就绪'}
                </span>
                <span className="space-chip">{version.docCount} 文档</span>
                <span className="space-chip">{version.chunkCount} 块</span>
              </div>
              <div className="space-meta-row">
                <span>{version.provider}</span>
                <span>{new Date(version.createdAt).toLocaleString('zh-CN')}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RegisterDocs({ kb, onNotice }: { kb: KnowledgeEntry; onNotice: (value: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [simulateFail, setSimulateFail] = useState(false);
  return (
    <div className="space-category-manager">
      <p className="space-footnote" style={{ marginTop: 0 }}>
        选择文件后登记名称与大小（本机浏览器存储），并自动启动显式模拟解析：不读取真实文件内容，产物为本地结构化样例并全程标注。
      </p>
      <div className="space-category-row">
        <input
          ref={inputRef}
          type="file"
          multiple
          aria-label="选择要登记的文件"
          onChange={(event) => {
            const files = [...(event.target.files ?? [])];
            if (files.length === 0) return;
            const added: string[] = [];
            for (const file of files) {
              const doc = addKbDocument(kb.id, { name: file.name, size: file.size });
              if (doc) added.push(doc.id);
            }
            if (added.length > 0) {
              for (const docId of added) simulateKbDocIngest(kb.id, docId, { fail: simulateFail });
              onNotice(`已登记 ${added.length} 个文档，正在模拟解析（本地结构化样例，非真实解析）。`);
            } else {
              onNotice('没有文档被登记（名称为空或已删除）。');
            }
            if (inputRef.current) inputRef.current.value = '';
          }}
        />
        <span className="space-chip">
          <FileUp size={12} />
          登记后模拟解析
        </span>
      </div>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, marginTop: 10 }}>
        <input
          type="checkbox"
          checked={simulateFail}
          aria-label="模拟一次解析失败（演示失败与重试路径）"
          onChange={(event) => setSimulateFail(event.target.checked)}
        />
        模拟一次解析失败（演示失败与重试路径）
      </label>
    </div>
  );
}

function SourceList({
  kb,
  onNotice,
  onError,
}: {
  kb: KnowledgeEntry;
  onNotice: (value: string) => void;
  onError: (value: string) => void;
}) {
  const [kind, setKind] = useState<'web' | 'github'>('web');
  const [ref, setRef] = useState('');
  const sources = kb.sources ?? [];
  return (
    <div className="space-category-manager">
      <p className="space-footnote" style={{ marginTop: 0 }}>
        外部来源登记后不会同步抓取（抓取与解析依赖后端服务，未接入）；仅作为来源清单保存。
      </p>
      <div className="space-category-row">
        <select
          className="space-select"
          aria-label="来源类型"
          value={kind}
          onChange={(e) => setKind(e.target.value === 'github' ? 'github' : 'web')}
        >
          <option value="web">网页</option>
          <option value="github">GitHub 仓库</option>
        </select>
        <input
          value={ref}
          aria-label="来源地址"
          placeholder={kind === 'web' ? 'https://…' : 'https://github.com/owner/repo'}
          onChange={(e) => setRef(e.target.value)}
        />
        <button
          className="space-button primary"
          onClick={() => {
            if (addKbSource(kb.id, kind, ref)) {
              setRef('');
              onNotice('已登记来源（不同步抓取）。');
            } else {
              onError('来源地址不能为空。');
            }
          }}
        >
          登记来源
        </button>
      </div>
      {sources.length === 0 ? (
        <p className="space-footnote">还没有登记来源。</p>
      ) : (
        <ul className="space-session-list">
          {sources.map((source) => (
            <li className="space-session-card" key={source.id}>
              <div className="space-session-top">
                <span className="space-chip">
                  {source.kind === 'github' ? <Github size={12} /> : <Globe size={12} />}
                  {source.kind === 'github' ? 'GitHub' : '网页'}
                </span>
                <span className="space-session-title">{source.ref}</span>
                <button
                  className="icon-button"
                  aria-label={`移除来源 ${source.ref}`}
                  onClick={() => {
                    if (removeKbSource(kb.id, source.id)) onNotice('已移除来源登记。');
                    else onError('移除失败：来源不存在或已被删除。');
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SettingsTab({
  kb,
  onNotice,
  onError,
}: {
  kb: KnowledgeEntry;
  onNotice: (value: string) => void;
  onError: (value: string) => void;
}) {
  const router = useRouter();
  const [name, setName] = useState(kb.name);
  const [description, setDescription] = useState(kb.description);
  return (
    <div className="space-category-manager">
      <div className="space-category-row">
        <input
          value={name}
          aria-label="知识库名称"
          maxLength={60}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          value={description}
          aria-label="知识库简介"
          placeholder="简介"
          onChange={(e) => setDescription(e.target.value)}
        />
        <button
          className="space-button primary"
          onClick={() => {
            try {
              const updated = updateKnowledge(kb.id, { name, description });
              onNotice(`已保存「${updated.name}」。`);
              // 改名后旧 URL 按名称会查不到，同步替换地址
              if (updated.name !== kb.name) {
                router.replace(`/knowledge-bases/${encodeURIComponent(updated.name)}`);
              }
            } catch (cause) {
              onError(
                cause instanceof KnowledgeValidationError
                  ? cause.message
                  : '保存失败，请检查输入后重试。',
              );
            }
          }}
        >
          保存修改
        </button>
      </div>
      <div className="space-category-row">
        <span className="space-footnote" style={{ marginTop: 0 }}>
          删除知识库只移除本地目录登记（文档元信息与来源清单），不影响聊天已保存内容。
        </span>
        <button
          className="space-button danger"
          onClick={() => {
            if (window.confirm(`删除知识库「${kb.name}」？登记的文档与来源清单将一并移除。`)) {
              if (deleteKnowledge(kb.id)) {
                router.push('/knowledge-bases');
              } else {
                onError('删除失败：知识库不存在或已被删除。');
              }
            }
          }}
        >
          <Trash2 size={14} />
          删除知识库
        </button>
      </div>
    </div>
  );
}
