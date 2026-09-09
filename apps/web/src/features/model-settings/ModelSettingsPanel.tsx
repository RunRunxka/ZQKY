'use client';
import { useRef, useState } from 'react';
import {
  Check,
  ChevronRight,
  CircleHelp,
  Download,
  Plus,
  Search,
  Settings2,
  Star,
  Trash2,
  Zap,
} from 'lucide-react';
import {
  CAPABILITY_EVIDENCE_LABELS,
  MODEL_PROTOCOL_LABELS,
  type ModelConnectionView,
  type ModelProfileView,
  type ModelTestResult,
} from '@/contracts/model-settings';
import {
  createConnection,
  createProfile,
  deleteConnection,
  deleteProfile,
  discoverModels,
  setDefaultModel,
  testProfile,
  updateConnection,
  updateProfile,
  notifyModelCatalogChanged,
} from '@/services/model-settings-api';
import { Modal } from '@/components/ui/Modal';
import { TestResult } from './TestResult';
import { ModelSelector } from './ModelSelector';
import { useModelCatalog } from './useModelCatalog';
import { ConnectionForm, type ConnectionFormValue } from './ConnectionForm';
import { ProfileForm, type ProfileFormValue } from './ProfileForm';
import './styles/model-settings.css';

type Editor =
  | { kind: 'connection'; value: ModelConnectionView | null; revision: number }
  | { kind: 'profile'; value: ModelProfileView | null; connectionId?: string; revision: number };
export function ModelSettingsPanel() {
  const { catalog, error, loading, refresh } = useModelCatalog();
  const [query, setQuery] = useState(''),
    [section, setSection] = useState('models');
  const [editor, setEditor] = useState<Editor | null>(null),
    [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [notice, setNotice] = useState<string | null>(null),
    [actionError, setActionError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{
    title: string;
    text: string;
    action: () => Promise<void>;
  } | null>(null);
  const [picker, setPicker] = useState<{
    connection: ModelConnectionView;
    ids: string[] | null;
    error?: string;
  } | null>(null);
  const [selected, setSelected] = useState<string[]>([]),
    [modelQuery, setModelQuery] = useState('');
  const [tests, setTests] = useState<
    Record<string, { running: boolean; result?: ModelTestResult; stream: boolean }>
  >({});
  const pickerEpoch = useRef(0);
  async function action(fn: () => Promise<unknown>, success = '已保存') {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setActionError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(success);
      await refresh();
      notifyModelCatalogChanged();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '操作失败，请重试。');
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function saveConnection(value: ConnectionFormValue) {
    if (editor?.kind !== 'connection') return;
    await action(async () => {
      if (editor.value)
        await updateConnection(editor.value.id, { ...value, expectedRevision: editor.revision });
      else await createConnection(value);
      setEditor(null);
    });
  }
  async function saveProfile(value: ProfileFormValue) {
    if (editor?.kind !== 'profile') return;
    await action(async () => {
      if (editor.value)
        await updateProfile(editor.value.id, { ...value, expectedRevision: editor.revision });
      else await createProfile(value);
      setEditor(null);
    });
  }
  async function openPicker(connection: ModelConnectionView) {
    const epoch = ++pickerEpoch.current;
    setSelected([]);
    setModelQuery('');
    setPicker({ connection, ids: null });
    setActionError(null);
    try {
      const { models } = await discoverModels(connection.id);
      if (epoch === pickerEpoch.current) setPicker({ connection, ids: models.map((m) => m.id) });
    } catch (e) {
      if (epoch === pickerEpoch.current)
        setPicker({
          connection,
          ids: [],
          error: e instanceof Error ? e.message : '获取失败，请手动添加。',
        });
    }
  }
  async function addSelected() {
    if (!picker || !catalog) return;
    await action(async () => {
      for (const id of selected) {
        if (
          !catalog.profiles.some((p) => p.connectionId === picker.connection.id && p.modelId === id)
        ) {
          await createProfile({
            connectionId: picker.connection.id,
            displayName: id.slice(0, 64),
            modelId: id,
            purpose: 'chat',
          });
          setSelected((prev) => prev.filter((value) => value !== id));
        }
      }
      setPicker(null);
    }, '所选模型已添加');
  }
  function requestTest(p: ModelProfileView, stream: boolean) {
    setConfirm({
      title: stream ? '测试流式输出' : '测试模型连接',
      text: '将发送一次少量文本的真实请求，可能产生少量费用。测试不会发送你的会话历史。',
      action: async () => {
        setTests((prev) => ({ ...prev, [p.id]: { running: true, stream } }));
        try {
          const result = await testProfile(p.id, { stream });
          setTests((prev) => ({ ...prev, [p.id]: { running: false, result, stream } }));
          await refresh();
          notifyModelCatalogChanged();
        } catch (e) {
          setTests((prev) => ({
            ...prev,
            [p.id]: {
              running: false,
              stream,
              result: {
                ok: false,
                error: {
                  code: 'REQUEST_FAILED',
                  message: e instanceof Error ? e.message : '测试失败。',
                },
              },
            },
          }));
        }
      },
    });
  }
  if (!catalog)
    return (
      <main className="model-settings settings-loading">
        <h1>模型管理</h1>
        {loading ? (
          <p role="status">正在读取模型设置…</p>
        ) : (
          <>
            <p role="alert">无法读取模型设置：{error}</p>
            <button className="button primary" onClick={() => void refresh()}>
              重试
            </button>
          </>
        )}
      </main>
    );
  const filtered = catalog.connections.filter((c) =>
    section === 'connections'
      ? `${c.displayName} ${c.baseUrl}`.toLowerCase().includes(query.toLowerCase())
      : !query ||
        catalog.profiles.some(
          (p) =>
            p.connectionId === c.id &&
            `${p.displayName} ${p.modelId} ${c.displayName}`
              .toLowerCase()
              .includes(query.toLowerCase()),
        ),
  );
  return (
    <main className="model-settings">
      <aside className="settings-navigation">
        <span className="settings-eyebrow">工作台设置</span>
        <h2>模型管理</h2>
        {[
          ['models', '问答模型'],
          ['connections', '连接管理'],
          ['defaults', '默认模型'],
        ].map(([id, label]) => (
          <button
            key={id}
            className={section === id ? 'current' : ''}
            onClick={() => setSection(id)}
          >
            <Settings2 size={16} />
            {label}
            <ChevronRight size={14} />
          </button>
        ))}
        <div className="settings-nav-note">
          <CircleHelp size={17} />
          <p>同一连接下的模型共用凭证。所有问答入口使用这里的模型目录。</p>
        </div>
      </aside>
      <div className="settings-scroll">
        <div className="settings-page-head">
          <div>
            <span className="settings-eyebrow">模型与连接</span>
            <h1>
              {section === 'models'
                ? '问答模型'
                : section === 'connections'
                  ? '连接管理'
                  : '默认模型'}
            </h1>
            <p>选择适合教学与学习的模型，在一个地方管理。</p>
          </div>
          <button
            className="button primary"
            onClick={() => {
              setActionError(null);
              setEditor({ kind: 'connection', value: null, revision: catalog.revision });
            }}
          >
            <Plus size={16} />
            添加连接
          </button>
        </div>
        <div className="settings-process-note">
          <span className="model-dot" />
          凭证保存到本机后端 apps/api/.env，重启后自动恢复；也可编辑文件后重启 API。
        </div>
        {(error || actionError) && !editor && !picker && (
          <p className="settings-feedback error" role="alert">
            {actionError ?? error}
            <button onClick={() => void refresh()}>刷新配置</button>
          </p>
        )}
        {notice && (
          <p className="settings-feedback success" role="status">
            <Check size={15} />
            {notice}
          </p>
        )}
        {section === 'defaults' ? (
          <section className="settings-default-card">
            <Star size={22} />
            <h2>全局默认问答模型</h2>
            <p>新会话默认使用此模型。已有会话的明确选择保持不变。</p>
            <ModelSelector
              catalog={{ ...catalog, defaultChatProfileId: null }}
              value={catalog.defaultChatProfileId}
              onChange={(id) =>
                void action(() => setDefaultModel(id, catalog.revision), '默认模型已更新')
              }
              disabled={busy}
            />
            <p className="settings-hint">教案生成、组卷等任务的模型分配仍在规划中。</p>
          </section>
        ) : (
          <>
            <div className="settings-list-toolbar">
              <div className="model-search">
                <Search size={16} />
                <input
                  aria-label="搜索连接或模型"
                  placeholder="搜索连接或模型…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <span>
                {catalog.connections.length} 个连接 · {catalog.profiles.length} 个模型
              </span>
            </div>
            {catalog.connections.length === 0 && (
              <div className="settings-empty-state">
                <Zap size={30} />
                <h2>添加第一个模型连接</h2>
                <p>填写服务地址和凭证，再获取模型列表或手动添加模型。</p>
              </div>
            )}
            {filtered.map((c) => (
              <details className="connection-group" key={c.id} open>
                <summary>
                  <span className="connection-avatar">{c.displayName.slice(0, 1)}</span>
                  <span>
                    <strong>{c.displayName}</strong>
                    <small>{MODEL_PROTOCOL_LABELS[c.protocol]}</small>
                  </span>
                  <span className={`small-badge ${c.hasCredential ? 'credential-ready' : ''}`}>
                    {c.hasCredential ? '凭证已配置' : '需填写凭证'}
                  </span>
                </summary>
                <div className="connection-tools">
                  <span title={c.baseUrl}>{c.baseUrl}</span>
                  <button
                    className="button subtle"
                    onClick={() => {
                      setActionError(null);
                      setEditor({ kind: 'connection', value: c, revision: catalog.revision });
                    }}
                  >
                    编辑连接
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`删除连接 ${c.displayName}`}
                    onClick={() => {
                      if (catalog.profiles.some((p) => p.connectionId === c.id)) {
                        setActionError('该连接仍被模型引用，请先删除相关模型。');
                        return;
                      }
                      setConfirm({
                        title: '删除连接',
                        text: `删除「${c.displayName}」及后端保存的凭证？`,
                        action: () =>
                          action(() => deleteConnection(c.id, catalog?.revision), '连接已删除'),
                      });
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                {section === 'models' && (
                  <div className="model-card-list">
                    {catalog.profiles
                      .filter(
                        (p) =>
                          p.connectionId === c.id &&
                          `${p.displayName} ${p.modelId} ${c.displayName}`
                            .toLowerCase()
                            .includes(query.toLowerCase()),
                      )
                      .map((p) => (
                        <article className="managed-model" key={p.id}>
                          <div className="managed-model-head">
                            <div>
                              <strong>{p.displayName}</strong>
                              <code>{p.modelId}</code>
                            </div>
                            {catalog.defaultChatProfileId === p.id && (
                              <span className="model-default">
                                <Star size={12} />
                                默认
                              </span>
                            )}
                            <button
                              className="icon-button"
                              aria-label={`编辑模型 ${p.displayName}`}
                              onClick={() => {
                                setActionError(null);
                                setEditor({
                                  kind: 'profile',
                                  value: p,
                                  revision: catalog.revision,
                                });
                              }}
                            >
                              <Settings2 size={16} />
                            </button>
                          </div>
                          <div className="model-facts">
                            <span>上下文 {p.contextTokens?.toLocaleString() ?? '未知'}</span>
                            <span>输出 {p.maxOutputTokens?.toLocaleString() ?? '默认'}</span>
                            <span>
                              对话 · {CAPABILITY_EVIDENCE_LABELS[p.capabilities.chat ?? 'unknown']}
                            </span>
                            <span>
                              流式 ·{' '}
                              {CAPABILITY_EVIDENCE_LABELS[p.capabilities.stream ?? 'unknown']}
                            </span>
                          </div>
                          <div className="managed-model-actions">
                            <button
                              disabled={!c.hasCredential || tests[p.id]?.running}
                              onClick={() => requestTest(p, false)}
                            >
                              连接测试
                            </button>
                            <button
                              disabled={!c.hasCredential || tests[p.id]?.running}
                              onClick={() => requestTest(p, true)}
                            >
                              流式测试
                            </button>
                            <button
                              disabled={busy || catalog.defaultChatProfileId === p.id}
                              onClick={() =>
                                void action(
                                  () => setDefaultModel(p.id, catalog.revision),
                                  '默认模型已更新',
                                )
                              }
                            >
                              设为默认
                            </button>
                            <button
                              aria-label={`删除模型 ${p.displayName}`}
                              onClick={() =>
                                setConfirm({
                                  title: '删除模型',
                                  text: `删除「${p.displayName}」？历史回答会保留，使用此模型的会话需重新选择。`,
                                  action: () =>
                                    action(
                                      () => deleteProfile(p.id, catalog?.revision),
                                      '模型已删除',
                                    ),
                                })
                              }
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                          {tests[p.id] && <TestResult test={tests[p.id]} />}
                        </article>
                      ))}
                  </div>
                )}
                <div className="connection-add">
                  <button
                    className="button subtle"
                    disabled={!c.hasCredential}
                    onClick={() => void openPicker(c)}
                  >
                    <Download size={14} />
                    从服务获取模型
                  </button>
                  <button
                    className="button subtle"
                    onClick={() => {
                      setActionError(null);
                      setEditor({
                        kind: 'profile',
                        value: null,
                        connectionId: c.id,
                        revision: catalog.revision,
                      });
                    }}
                  >
                    <Plus size={14} />
                    手动添加
                  </button>
                </div>
              </details>
            ))}
            {filtered.length === 0 && catalog.connections.length > 0 && (
              <p className="settings-empty">没有匹配的连接或模型。</p>
            )}
          </>
        )}
      </div>
      {editor && (
        <Modal
          title={
            editor.kind === 'connection'
              ? editor.value
                ? '编辑连接'
                : '添加连接'
              : editor.value
                ? '编辑模型'
                : '添加模型'
          }
          onClose={() => {
            if (!busy) setEditor(null);
          }}
        >
          {actionError && (
            <div className="settings-feedback error" role="alert">
              {actionError}
              <button
                onClick={async () => {
                  const next = await refresh();
                  if (next)
                    setEditor((prev) => (prev ? { ...prev, revision: next.revision } : null));
                }}
              >
                重新读取版本（保留表单）
              </button>
            </div>
          )}
          {editor.kind === 'connection' ? (
            <ConnectionForm
              connection={editor.value}
              busy={busy}
              onCancel={() => {
                if (!busy) setEditor(null);
              }}
              onSave={(value) => void saveConnection(value)}
            />
          ) : (
            <ProfileForm
              profile={editor.value}
              connections={catalog.connections}
              initialConnectionId={editor.connectionId}
              busy={busy}
              onCancel={() => {
                if (!busy) setEditor(null);
              }}
              onSave={(value) => void saveProfile(value)}
            />
          )}
        </Modal>
      )}
      {picker && (
        <Modal
          title={`添加模型 · ${picker.connection.displayName}`}
          onClose={() => {
            if (!busy) {
              pickerEpoch.current++;
              setPicker(null);
            }
          }}
        >
          <p className="settings-hint">勾选要添加的模型。已有配置会保留，不会被服务列表覆盖。</p>
          {picker.ids === null ? (
            <p role="status">正在获取模型列表…</p>
          ) : picker.error ? (
            <p role="alert">{picker.error}</p>
          ) : (
            <>
              <input
                aria-label="筛选发现的模型"
                placeholder="搜索模型 ID"
                value={modelQuery}
                onChange={(e) => setModelQuery(e.target.value)}
              />
              <div className="discovery-list">
                {picker.ids
                  .filter((id) => id.toLowerCase().includes(modelQuery.toLowerCase()))
                  .map((id) => {
                    const exists = catalog.profiles.some(
                      (p) => p.connectionId === picker.connection.id && p.modelId === id,
                    );
                    return (
                      <label key={id}>
                        <input
                          type="checkbox"
                          disabled={exists || busy}
                          checked={exists || selected.includes(id)}
                          onChange={() =>
                            setSelected(
                              selected.includes(id)
                                ? selected.filter((x) => x !== id)
                                : [...selected, id],
                            )
                          }
                        />
                        <span>{id}</span>
                        {exists && <small>已添加</small>}
                      </label>
                    );
                  })}
              </div>
              {picker.ids.length === 0 && <p>服务返回了空列表，你仍可手动添加模型。</p>}
            </>
          )}
          {actionError && <p role="alert">{actionError}</p>}
          <footer>
            <button
              className="button subtle"
              disabled={busy}
              onClick={() => {
                setEditor({
                  kind: 'profile',
                  value: null,
                  connectionId: picker.connection.id,
                  revision: catalog.revision,
                });
                pickerEpoch.current++;
                setPicker(null);
              }}
            >
              手动添加
            </button>
            <button
              className="button primary"
              disabled={busy || selected.length === 0}
              onClick={() => void addSelected()}
            >
              {busy ? '添加中…' : `添加所选 ${selected.length} 个模型`}
            </button>
          </footer>
        </Modal>
      )}
      {confirm && (
        <Modal title={confirm.title} onClose={() => setConfirm(null)}>
          <p>{confirm.text}</p>
          <footer>
            <button className="button subtle" onClick={() => setConfirm(null)}>
              取消
            </button>
            <button
              className="button primary"
              onClick={() => {
                const task = confirm.action;
                setConfirm(null);
                void task();
              }}
            >
              确认
            </button>
          </footer>
        </Modal>
      )}
    </main>
  );
}
