'use client';
import { useMemo, useRef, useState } from 'react';
import { Check, ChevronRight, CircleHelp, Plus, Search, Settings2, Star, Zap } from 'lucide-react';
import {
  type ModelConnectionView,
  type ModelProfileView,
  type ModelProviderView,
  type ModelTestResult,
} from '@/contracts/model-settings';
import {
  createConnection,
  createProfile,
  deleteConnection,
  deleteProfile,
  notifyModelCatalogChanged,
  setDefaultModel,
  testProfile,
  updateConnection,
  updateProfile,
} from '@/services/model-settings-api';
import { Modal } from '@/components/ui/Modal';
import { ModelSelector } from './ModelSelector';
import { useModelCatalog } from './useModelCatalog';
import { useProviderDirectory } from './useProviderDirectory';
import { ProviderCard } from './ProviderCard';
import { ProviderPicker } from './ProviderPicker';
import { ConnectionDetail, type ConnectionDraft } from './ConnectionDetail';
import { ModelListPicker } from './ModelListPicker';
import { ProfileForm, type ProfileFormValue } from './ProfileForm';
import './styles/model-settings.css';
import './styles/model-detail.css';

type Overlay =
  | { kind: 'pick-provider' }
  | { kind: 'detail'; connectionId: string }
  | { kind: 'discover'; connectionId: string }
  | { kind: 'profile'; profile: ModelProfileView | null; connectionId?: string };

function draftFrom(connection: ModelConnectionView): ConnectionDraft {
  return {
    displayName: connection.displayName,
    baseUrl: connection.baseUrl,
    apiFormat: connection.apiFormat,
    apiVersion: connection.apiVersion ?? '',
    extraHeadersText: '',
    apiKey: '',
    clearCredential: false,
  };
}

export function ModelSettingsPanel() {
  const { catalog, error, loading, refresh } = useModelCatalog();
  const { directory, error: directoryError, refresh: refreshDirectory } = useProviderDirectory();
  const [query, setQuery] = useState('');
  const [section, setSection] = useState<'models' | 'connections' | 'defaults'>('models');
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [draft, setDraft] = useState<ConnectionDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const lock = useRef(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ title: string; text: string; action: () => Promise<void> } | null>(null);
  const [tests, setTests] = useState<Record<string, { running: boolean; result?: ModelTestResult; stream: boolean }>>({});

  const providersById = useMemo(() => {
    const map = new Map<string, ModelProviderView>();
    if (directory) {
      for (const provider of [...directory.providers, ...directory.legacy]) {
        map.set(provider.providerId, provider);
      }
    }
    return map;
  }, [directory]);

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

  const overlayConnection: ModelConnectionView | null =
    overlay && overlay.kind !== 'pick-provider' && 'connectionId' in overlay
      ? catalog?.connections.find((connection) => connection.id === overlay.connectionId) ?? null
      : null;

  async function addProvider(provider: ModelProviderView) {
    const needsBase = !provider.defaultApiBase;
    setOverlay({
      kind: 'detail',
      connectionId: '',
    });
    // 新建走同一个详情形态：先创建连接，再进入详情
    await action(async () => {
      const created = await createConnection({
        displayName: provider.label,
        providerId: provider.providerId,
        apiFormat: provider.defaultApiFormat,
        baseUrl: provider.defaultApiBase,
      });
      setDraft(draftFrom(created));
      setOverlay({ kind: 'detail', connectionId: created.id });
      if (needsBase) setNotice('请在详情中填写 Base URL。');
    }, '连接已创建');
  }

  async function saveConnectionDetail() {
    if (!overlayConnection || !draft) return;
    await action(async () => {
      const extraHeaders = parseHeaders(draft.extraHeadersText);
      await updateConnection(overlayConnection.id, {
        displayName: draft.displayName.trim(),
        apiFormat: draft.apiFormat,
        baseUrl: draft.baseUrl.trim(),
        apiVersion: draft.apiVersion.trim() || null,
        ...(draft.apiKey && !draft.clearCredential ? { apiKey: draft.apiKey } : {}),
        ...(draft.clearCredential ? { credentialAction: 'clear' as const } : {}),
        ...(Object.keys(extraHeaders).length > 0 ? { extraHeaders } : {}),
        expectedRevision: catalog?.revision,
      });
      const updated = catalog?.connections.find((connection) => connection.id === overlayConnection.id);
      setDraft(updated ? draftFrom(updated) : null);
    }, '连接已保存');
  }

  async function saveProfile(value: ProfileFormValue) {
    if (overlay?.kind !== 'profile') return;
    const existing = overlay.profile;
    await action(async () => {
      if (existing) await updateProfile(existing.id, { ...value, expectedRevision: catalog?.revision });
      else await createProfile(value);
      setOverlay({ kind: 'detail', connectionId: value.connectionId });
    }, existing ? '模型已保存' : '模型已添加');
  }

  function requestTest(profile: ModelProfileView, stream: boolean) {
    setConfirm({
      title: stream ? '测试流式输出' : '测试模型连接',
      text: '将发送一次少量文本的真实请求，可能产生少量费用。测试不会发送你的会话历史。',
      action: async () => {
        setTests((prev) => ({ ...prev, [profile.id]: { running: true, stream } }));
        try {
          const result = await testProfile(profile.id, { stream });
          setTests((prev) => ({ ...prev, [profile.id]: { running: false, result, stream } }));
          await refresh();
          notifyModelCatalogChanged();
        } catch (e) {
          setTests((prev) => ({
            ...prev,
            [profile.id]: {
              running: false,
              stream,
              result: { ok: false, error: { code: 'REQUEST_FAILED', message: e instanceof Error ? e.message : '测试失败。' } },
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

  const filteredConnections = catalog.connections.filter((connection) => {
    const modelMatch =
      section === 'models' &&
      catalog.profiles.some(
        (profile) =>
          profile.connectionId === connection.id &&
          `${profile.displayName} ${profile.modelId} ${connection.displayName}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      );
    const connectionMatch = `${connection.displayName} ${connection.providerLabel ?? ''} ${connection.baseUrl}`
      .toLowerCase()
      .includes(query.toLowerCase());
    return !query || connectionMatch || modelMatch;
  });

  return (
    <main className="model-settings">
      <aside className="settings-navigation">
        <span className="settings-eyebrow">工作台设置</span>
        <h2>模型管理</h2>
        {(
          [
            ['models', '问答模型'],
            ['connections', '连接管理'],
            ['defaults', '默认模型'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} className={section === id ? 'current' : ''} onClick={() => setSection(id)}>
            <Settings2 size={16} />
            {label}
            <ChevronRight size={14} />
          </button>
        ))}
        <div className="settings-nav-note">
          <CircleHelp size={17} />
          <p>一个连接的一套凭证可被多个模型复用。所有问答入口使用这里的模型目录。</p>
        </div>
      </aside>

      <div className="settings-scroll">
        <div className="settings-page-head">
          <div>
            <span className="settings-eyebrow">模型与连接</span>
            <h1>{section === 'models' ? '问答模型' : section === 'connections' ? '连接管理' : '默认模型'}</h1>
            <p>选择适合教学与学习的模型，在一个地方管理。</p>
          </div>
          <button className="button primary" onClick={() => setOverlay({ kind: 'pick-provider' })}>
            <Plus size={16} />
            添加连接
          </button>
        </div>

        <div className="settings-process-note">
          <span className="model-dot" />
          凭证保存在服务端（正式服务为忽略的 apps/api/.env），响应不回显明文；重启后自动恢复。
        </div>

        {(actionError || error || directoryError) && overlay === null && (
          <p className="settings-feedback error" role="alert">
            {actionError ?? error ?? directoryError}
            <button
              onClick={() => {
                void refresh();
                void refreshDirectory();
              }}
            >
              刷新配置
            </button>
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
              onChange={(id) => void action(() => setDefaultModel(id, catalog.revision), '默认模型已更新')}
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
                <p>从供应商目录选择服务，填写凭证，再获取或手动添加模型。</p>
                <button className="button primary" onClick={() => setOverlay({ kind: 'pick-provider' })}>
                  <Plus size={16} />
                  选择供应商
                </button>
              </div>
            )}

            <div className="provider-grid">
              {filteredConnections.map((connection) => {
                const provider = connection.providerId ? providersById.get(connection.providerId) ?? null : null;
                const profiles = catalog.profiles.filter((profile) => profile.connectionId === connection.id);
                const defaultProfile = profiles.find((profile) => profile.id === catalog.defaultChatProfileId);
                return (
                  <ProviderCard
                    key={connection.id}
                    connection={connection}
                    modelCount={profiles.length}
                    inUseModelName={defaultProfile?.displayName ?? null}
                    credentialKnown={provider ? provider.requiresKey : true}
                    onOpen={() => {
                      setActionError(null);
                      setDraft(draftFrom(connection));
                      setOverlay({ kind: 'detail', connectionId: connection.id });
                    }}
                  />
                );
              })}
              {catalog.connections.length > 0 && (
                <button
                  type="button"
                  className="provider-card add-card"
                  onClick={() => setOverlay({ kind: 'pick-provider' })}
                >
                  <Plus size={18} />
                  添加连接
                </button>
              )}
            </div>
            {filteredConnections.length === 0 && catalog.connections.length > 0 && (
              <p className="settings-empty">没有匹配的连接或模型。</p>
            )}
          </>
        )}
      </div>

      {overlay?.kind === 'pick-provider' && directory && (
        <Modal title="选择供应商" onClose={() => setOverlay(null)}>
          <ProviderPicker
            directory={directory.providers}
            onPick={(provider) => void addProvider(provider)}
            onClose={() => setOverlay(null)}
          />
        </Modal>
      )}

      {overlay?.kind === 'detail' && overlayConnection && draft && (
        <Modal
          title={`连接 · ${overlayConnection.displayName}`}
          onClose={() => {
            if (!busy) setOverlay(null);
          }}
        >
          {actionError && (
            <div className="settings-feedback error" role="alert">
              {actionError}
              <button
                onClick={async () => {
                  const next = await refresh();
                  if (next) void next;
                }}
              >
                重新读取版本（保留表单）
              </button>
            </div>
          )}
          <ConnectionDetail
            connection={overlayConnection}
            provider={overlayConnection.providerId ? providersById.get(overlayConnection.providerId) ?? null : null}
            profiles={catalog.profiles.filter((profile) => profile.connectionId === overlayConnection.id)}
            defaultChatProfileId={catalog.defaultChatProfileId}
            importing={importing}
            draft={draft}
            onDraftChange={setDraft}
            onSave={() => void saveConnectionDetail()}
            onClose={() => setOverlay(null)}
            onCreateModel={() =>
              setOverlay({ kind: 'profile', profile: null, connectionId: overlayConnection.id })
            }
            onDiscover={() => setOverlay({ kind: 'discover', connectionId: overlayConnection.id })}
            onUseModel={(profile) =>
              void action(() => setDefaultModel(profile.id, catalog.revision), '已设为问答默认模型')
            }
            onTestModel={(profile, stream) => requestTest(profile, stream)}
            tests={tests}
            onEditModel={(profile) => setOverlay({ kind: 'profile', profile, connectionId: overlayConnection.id })}
            onDeleteModel={(profile) =>
              setConfirm({
                title: '删除模型',
                text: `删除「${profile.displayName}」？历史回答会保留，使用此模型的会话需重新选择。`,
                action: () => action(() => deleteProfile(profile.id, catalog?.revision), '模型已删除'),
              })
            }
            onDeleteConnection={() =>
              setConfirm({
                title: '删除连接',
                text: `删除「${overlayConnection.displayName}」及服务端保存的凭证？该连接下的模型会阻止删除。`,
                action: () =>
                  action(async () => {
                    await deleteConnection(overlayConnection.id, catalog?.revision);
                    setOverlay(null);
                  }, '连接已删除'),
              })
            }
            busy={busy}
            dirty={overlayConnection ? connectionDirty(overlayConnection, draft) : false}
          />
        </Modal>
      )}

      {overlay?.kind === 'discover' && overlayConnection && (
        <Modal title="从服务获取模型" onClose={() => setOverlay(null)}>
          <ModelListPicker
            connectionId={overlayConnection.id}
            connectionName={overlayConnection.displayName}
            providerId={overlayConnection.providerId}
            providerLabel={overlayConnection.providerLabel}
            existingIds={catalog.profiles
              .filter((profile) => profile.connectionId === overlayConnection.id)
              .map((profile) => profile.modelId)}
            onAdd={async (ids) => {
              setImporting(true);
              try {
                await action(async () => {
                  for (const id of ids) {
                    const exists = catalog.profiles.some(
                      (profile) => profile.connectionId === overlayConnection.id && profile.modelId === id,
                    );
                    if (!exists) {
                      await createProfile({
                        connectionId: overlayConnection.id,
                        displayName: id.slice(0, 64),
                        modelId: id,
                        purpose: 'chat',
                      });
                    }
                  }
                }, '所选模型已添加');
              } finally {
                setImporting(false);
              }
            }}
            onManual={() => setOverlay({ kind: 'profile', profile: null, connectionId: overlayConnection.id })}
            onClose={() => setOverlay(null)}
          />
        </Modal>
      )}

      {overlay?.kind === 'profile' && (
        <Modal
          title={overlay.profile ? '编辑模型' : '添加模型'}
          onClose={() => {
            if (!busy) setOverlay({ kind: 'detail', connectionId: overlay.connectionId ?? '' });
          }}
        >
          {actionError && (
            <div className="settings-feedback error" role="alert">
              {actionError}
            </div>
          )}
          <ProfileForm
            profile={overlay.profile}
            connections={catalog.connections}
            initialConnectionId={overlay.connectionId}
            busy={busy}
            onCancel={() => setOverlay({ kind: 'detail', connectionId: overlay.connectionId ?? '' })}
            onSave={(value) => void saveProfile(value)}
          />
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

function connectionDirty(connection: ModelConnectionView, draft: ConnectionDraft): boolean {
  return (
    draft.displayName !== connection.displayName ||
    draft.baseUrl !== connection.baseUrl ||
    draft.apiFormat !== connection.apiFormat ||
    (draft.apiVersion || '') !== (connection.apiVersion ?? '') ||
    draft.apiKey.length > 0 ||
    draft.clearCredential
  );
}

function parseHeaders(text: string): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const index = trimmed.indexOf(':');
    if (index <= 0) continue;
    headers[trimmed.slice(0, index).trim()] = trimmed.slice(index + 1).trim();
  }
  return headers;
}
