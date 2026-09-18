'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
// 复用 space 设计语言的样式；直达路由也需要加载（不能只依赖 SpaceMain 的引入）
import '@/features/space/styles/space.css';
// 知识库两页专属样式（B-R05-EXTEND-I1）：在 space.css 之后引入保证覆盖顺序
import '@/features/knowledge/styles/knowledge.css';
import {
  ChevronRight,
  Cloud,
  Database,
  Globe,
  HardDrive,
  Library,
  Plus,
  Search,
  Server,
  Sparkles,
  Star,
  type LucideIcon,
} from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  createKnowledge,
  kbPipelineSummary,
  loadDemoKnowledge,
  KnowledgeValidationError,
  readKnowledge,
  subscribeKnowledge,
  type KbPipelineSummary,
  type KnowledgeEntry,
} from '@/services/knowledge-catalog';

/** 文档计数（对照参考 kbDocCount） */
function docCount(kb: KnowledgeEntry): number {
  return kb.docs?.length ?? 0;
}

const PIPELINE_LABEL: Record<KbPipelineSummary['status'], string> = {
  empty: '空',
  registered: '待处理',
  processing: '处理中',
  ready: '已就绪',
  error: '有失败',
};

/** 复用现有 space-chip 变体（green 表就绪），tone 为空串时用默认样式 */
const PIPELINE_TONE: Record<KbPipelineSummary['status'], string> = {
  empty: '',
  registered: '',
  processing: 'blue',
  ready: 'green',
  error: 'amber',
};

function statusOf(kb: KnowledgeEntry): { label: string; tone: string; dot: string } {
  const summary = kbPipelineSummary(kb);
  return {
    label: PIPELINE_LABEL[summary.status],
    tone: PIPELINE_TONE[summary.status],
    // 状态圆点四态（对照参考 StatusDot）：处理中蓝+脉冲、已就绪绿、有失败红、空/待处理灰
    dot:
      summary.status === 'processing'
        ? 'processing'
        : summary.status === 'ready'
          ? 'ready'
          : summary.status === 'error'
            ? 'error'
            : '',
  };
}

/** 检索引擎分组（静态演示：目标项目无真实 RAG 服务部署） */
const ENGINE_GROUPS: {
  label: string;
  icon: LucideIcon;
  note: string;
  engines: { id: string; name: string; desc: string }[];
}[] = [
  {
    label: '本地引擎',
    icon: HardDrive,
    note: '在本设备上完成索引与检索。',
    engines: [{ id: 'builtin-local', name: '内置检索（未接入）', desc: '目标项目未部署向量检索服务，此处仅登记入口。' }],
  },
  {
    label: '服务端引擎',
    icon: Server,
    note: '连接自建或托管的服务端检索服务。',
    engines: [
      { id: 'demo-lightrag', name: 'LightRAG（演示）', desc: '参考产品支持的 RAG 引擎之一；需要服务端部署。' },
      { id: 'demo-weknora', name: 'WeKnora（演示）', desc: '参考产品支持的 RAG 引擎之一；需要服务端部署。' },
    ],
  },
  {
    label: '云端引擎',
    icon: Cloud,
    note: '以账号授权连接云端知识检索。',
    engines: [{ id: 'demo-ima', name: 'IMA 云检索（演示）', desc: '参考产品支持的云端知识检索；需要账号授权。' }],
  },
];

const EXTERNAL_SOURCES = [
  { id: 'ext-obsidian', name: 'Obsidian', desc: '本地库连接（参考支持）；目标项目未接入。' },
  { id: 'ext-marginnote', name: 'MarginNote 4', desc: '设备同步（参考支持）；目标项目未接入。' },
];

/** 引擎/来源总数（对照参考 providers.length + externalSources.length 口径） */
const ENGINE_TAB_COUNT =
  ENGINE_GROUPS.reduce((sum, group) => sum + group.engines.length, 0) + EXTERNAL_SOURCES.length;

export function KnowledgeBasesSection() {
  const [kbs, setKbs] = useState<KnowledgeEntry[]>([]);
  const [tab, setTab] = useState<'bases' | 'engines'>('bases');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const refresh = useCallback(() => {
    try {
      setKbs(readKnowledge());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '知识库目录无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeKnowledge(refresh);
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = kbs.filter((kb) => !q || kb.name.toLowerCase().includes(q));
    // 参考：subagent 类型库不在列表展示；本地目录无该类型，全部展示
    return list;
  }, [kbs, query]);

  return (
    <div className="space-page kb-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>教材资料库</h1>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                loadDemoKnowledge();
                setNotice('已载入演示知识库（重复载入不产生重复条目）。演示库无真实检索能力。');
              }}
            >
              <Sparkles size={14} />
              载入演示数据
            </button>
            <button className="space-button primary" onClick={() => setCreateOpen(true)}>
              <Plus size={14} />
              新建知识库
            </button>
          </div>
        </div>
        <p className="space-description">
          集中登记教学资料与检索引擎；聊天输入区「知识来源」选择与此共享同一份本地目录。
        </p>
      </header>
      <main className="space-content">
        <div className="space-tabs" role="tablist" aria-label="知识库视图">
          <button
            role="tab"
            aria-selected={tab === 'bases'}
            className={tab === 'bases' ? 'current' : ''}
            aria-controls="kb-bases-panel"
            id="kb-bases-tab"
            onClick={() => setTab('bases')}
          >
            <Database size={16} aria-hidden />
            知识库
            <span className="kb-tab-count" aria-hidden>
              {kbs.length}
            </span>
          </button>
          <button
            role="tab"
            aria-selected={tab === 'engines'}
            className={tab === 'engines' ? 'current' : ''}
            aria-controls="kb-engines-panel"
            id="kb-engines-tab"
            onClick={() => setTab('engines')}
          >
            <Server size={16} aria-hidden />
            检索引擎
            <span className="kb-tab-count" aria-hidden>
              {ENGINE_TAB_COUNT}
            </span>
          </button>
        </div>

        <div className="space-banner info" role="note">
          解析与索引为显式模拟：真实文件内容读取与向量检索服务未接入，模拟产物为本地结构化样例并全程标注；聊天中的知识来源是范围声明，不执行真实检索。
        </div>
        {notice && (
          <div className="space-banner info" role="status">
            {notice}
          </div>
        )}
        {error && (
          <div className="space-banner error" role="alert">
            {error}
            <div className="kb-banner-actions">
              <button
                className="space-button"
                onClick={() => {
                  setLoading(true);
                  refresh();
                }}
              >
                重试
              </button>
              <button className="space-button" onClick={() => setError(null)}>
                关闭
              </button>
            </div>
          </div>
        )}

        {tab === 'bases' ? (
          <div id="kb-bases-panel" role="tabpanel" aria-labelledby="kb-bases-tab">
            {loading ? (
              <div aria-hidden>
                {[0, 1].map((i) => (
                  <div className="space-skeleton" key={i} style={{ height: 76, marginBottom: 10 }} />
                ))}
              </div>
            ) : kbs.length === 0 ? (
              <div className="space-empty">
                <span className="kb-empty-icon" aria-hidden>
                  <Database size={20} />
                </span>
                <strong>还没有知识库</strong>
                <span>载入演示知识库快速体验，或新建一个库登记教学资料。</span>
                <button className="space-button primary" onClick={() => setCreateOpen(true)}>
                  <Plus size={14} />
                  新建知识库
                </button>
              </div>
            ) : (
              <>
                {kbs.length > 6 && (
                  <div className="space-toolbar">
                    <div className="kb-search-wrap">
                      <Search className="kb-search-icon" size={14} aria-hidden />
                      <input
                        className="space-search"
                        type="search"
                        placeholder="按名称搜索…"
                        aria-label="搜索知识库"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </div>
                  </div>
                )}
                <div className="space-card-grid">
                  {filtered.map((kb) => {
                    const status = statusOf(kb);
                    return (
                      <Link
                        className="space-persona-card"
                        key={kb.id}
                        href={`/knowledge-bases/${encodeURIComponent(kb.name)}`}
                      >
                        <ChevronRight className="kb-card-chevron" size={16} aria-hidden />
                        <div className="space-card-title">
                          <span className={`kb-status-dot ${status.dot}`} aria-hidden />
                          {kb.isDefault && (
                            <Star size={14} aria-label="默认库" fill="currentColor" color="#b7791f" />
                          )}
                          {kb.name}
                        </div>
                        <p className="space-card-body">{kb.description || '（无简介）'}</p>
                        <div className="space-meta-row">
                          <span className={`space-chip ${status.tone}`}>{status.label}</span>
                          <span className="space-chip">{docCount(kb)} 个文档</span>
                          <span className="space-chip">本地目录</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
                {kbs.length > 6 && filtered.length === 0 && (
                  <div className="kb-nomatch">没有匹配的知识库</div>
                )}
              </>
            )}
          </div>
        ) : (
          <div id="kb-engines-panel" role="tabpanel" aria-labelledby="kb-engines-tab">
            {ENGINE_GROUPS.map((group) => {
              const GroupIcon = group.icon;
              return (
                <section className="space-group" key={group.label}>
                  <div className="kb-group-head">
                    <GroupIcon size={16} aria-hidden />
                    <div>
                      <h2 className="kb-group-title">{group.label}</h2>
                      <p className="kb-group-desc">{group.note}</p>
                    </div>
                  </div>
                  <div className="space-card-grid">
                    {group.engines.map((engine) => {
                      const Icon =
                        group.label === '本地引擎' ? HardDrive : group.label === '服务端引擎' ? Server : Cloud;
                      return (
                        <article className="space-cli-card" key={engine.id}>
                          <ChevronRight className="kb-card-chevron" size={16} aria-hidden />
                          <div className="space-card-title">
                            <span className="kb-engine-icon" aria-hidden>
                              <Icon size={18} />
                            </span>
                            {engine.name}
                          </div>
                          <p className="space-card-body">{engine.desc}</p>
                          <div className="kb-engine-count">0 KB</div>
                        </article>
                      );
                    })}
                  </div>
                </section>
              );
            })}
            <section className="space-group">
              <div className="kb-group-head">
                <Library size={16} aria-hidden />
                <div>
                  <h2 className="kb-group-title">外部来源</h2>
                  <p className="kb-group-desc">连接本地笔记库或设备，不重建索引（参考支持）。</p>
                </div>
              </div>
              <div className="space-card-grid">
                {EXTERNAL_SOURCES.map((source) => (
                  <article className="space-cli-card" key={source.id}>
                    <ChevronRight className="kb-card-chevron" size={16} aria-hidden />
                    <div className="space-card-title">
                      <span className="kb-engine-icon" aria-hidden>
                        <Globe size={18} />
                      </span>
                      {source.name}
                    </div>
                    <p className="space-card-body">{source.desc}</p>
                    <div className="kb-engine-count">0 KB</div>
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}

        {createOpen && (
          <CreateKbForm
            onClose={() => setCreateOpen(false)}
            onCreated={(name) => {
              setCreateOpen(false);
              setNotice(`已创建知识库「${name}」（本地目录，未连接检索服务）。`);
            }}
          />
        )}
      </main>
    </div>
  );
}

function CreateKbForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (name: string) => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  return (
    <Modal title="新建知识库" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(e) => {
          e.preventDefault();
          try {
            const kb = createKnowledge(name, description);
            onCreated(kb.name);
          } catch (cause) {
            setError(
              cause instanceof KnowledgeValidationError
                ? cause.message
                : '创建失败，请检查输入后重试。',
            );
          }
        }}
      >
          <label>
            名称
            <input
              value={name}
              required
              maxLength={60}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：七年级数学资料"
            />
          </label>
          <label>
            简介
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="这个库用来登记什么资料？"
            />
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
