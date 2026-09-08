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
  Star,
  Trash2,
  TriangleAlert,
} from 'lucide-react';
import {
  addKbDocument,
  addKbSource,
  deleteKnowledge,
  KnowledgeValidationError,
  readKnowledge,
  removeKbDocument,
  removeKbSource,
  setDefaultKnowledge,
  subscribeKnowledge,
  updateKnowledge,
  type KnowledgeEntry,
} from '@/services/knowledge-catalog';

type DetailSection = 'files' | 'add' | 'sources' | 'versions' | 'settings';

const SECTIONS: { id: DetailSection; label: string }[] = [
  { id: 'files', label: '文档' },
  { id: 'add', label: '登记文档' },
  { id: 'sources', label: '外部来源' },
  { id: 'versions', label: '索引' },
  { id: 'settings', label: '设置' },
];

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
    return (
      <div className="space-page">
        <div className="space-banner" style={{ marginTop: 80 }}>
          正在读取知识库…
        </div>
      </div>
    );
  }

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
        </h1>
        <p className="space-description">{kb.description || '（无简介）'}</p>
      </header>
      <main className="space-content">
        <div className="space-banner info" role="note">
          <TriangleAlert size={13} aria-hidden style={{ display: 'inline', marginRight: 6 }} />
          解析与索引服务未接入：文档登记仅保存元信息，不解析内容、不建索引、不执行来源同步。
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
        {section === 'versions' && (
          <div className="space-empty">
            <strong>还没有索引版本</strong>
            <span>
              索引/重建依赖解析与向量检索服务，目标项目未接入；文档登记不会产生索引版本，聊天引用也不执行真实检索。
            </span>
          </div>
        )}
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
  return docs.length === 0 ? (
    <div className="space-empty">
      <strong>还没有登记文档</strong>
      <span>到「登记文档」选择文件登记（仅元信息），或载入演示数据。</span>
    </div>
  ) : (
    <ul className="space-session-list">
      {docs.map((doc) => (
        <li className="space-session-card" key={doc.id}>
          <div className="space-session-top">
            <span className="space-session-title">{doc.name}</span>
            <span className="space-chip">未解析 · 未索引</span>
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
          <div className="space-meta-row">
            <span>{formatSize(doc.size)}</span>
            <span>登记于 {new Date(doc.registeredAt).toLocaleString('zh-CN')}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

function RegisterDocs({ kb, onNotice }: { kb: KnowledgeEntry; onNotice: (value: string) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="space-category-manager">
      <p className="space-footnote" style={{ marginTop: 0 }}>
        选择文件后仅登记名称与大小（本机浏览器存储），不读取内容、不解析、不索引；聊天引用该库时只声明范围。
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
            let added = 0;
            for (const file of files) {
              if (addKbDocument(kb.id, { name: file.name, size: file.size })) added += 1;
            }
            onNotice(
              added > 0
                ? `已登记 ${added} 个文档（未解析，仅元信息）。`
                : '没有文档被登记（名称为空或已删除）。',
            );
            if (inputRef.current) inputRef.current.value = '';
          }}
        />
        <span className="space-chip">
          <FileUp size={12} />
          登记不解析
        </span>
      </div>
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
