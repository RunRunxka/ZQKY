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
import { NewConnectionForm, type DraftConnectionForm } from './NewConnectionForm';
import { ConnectionDetail, type ConnectionDraft } from './ConnectionDetail';
import { ModelListPicker } from './ModelListPicker';
import { ProfileForm, type ProfileFormValue } from './ProfileForm';
import './styles/model-settings.css';
import './styles/model-detail.css';

type Overlay =
  | { kind: 'pick-provider' }
  | { kind: 'new-connection'; provider: ModelProviderView }
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

function connectionDirty(connection: ModelConnectionView, draft: ConnectionDraft): boolean {
  return (
    draft.displayName !== connection.displayName ||
    draft.baseUrl !== connection.baseUrl ||
    draft.apiFormat !== connection.apiFormat ||
    (draft.apiVersion || '') !== (connection.apiVersion ?? '') ||
    draft.apiKey.length > 0 ||
    draft.clearCredential ||
    draft.extraHeadersText.trim().length > 0
  );
}

export function ModelSettingsPanel() {
  const { catalog, error, loading, refresh } = useModelCatalog();
  const { directory, error: directoryError, refresh: refreshDirectory } = useProviderDirectory();
  const [query, setQuery] = useState('');
  const [section, setSection] = useState<'models' | 'connections' | 'defaults'>('models');
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [draft, setDraft] = useState<ConnectionDraft | null>(null);
  const [draftConnectionId, setDraftConnectionId] = useState<string | null>(null);
  const [newDraft, setNewDraft] = useState<DraftConnectionForm | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const lock = useRef(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ title: string; text: string; action: () => Promise<void> } | null>(null);
  const [discard, setDiscard] = useState<{ onDiscard: () => void } | null>(null);
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

  /** 执行一次动作；返回是否成功，供调用方决定是否清空选择/关闭弹窗（MR-13）。 */
  async function runAction(fn: () => Promise<unknown>, success = '已保存'): Promise<boolean> {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setActionError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(success);
      await refresh();
      notifyModelCatalogChanged();
      return true;
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '操作失败，请重试。');
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  const overlayConnection: ModelConnectionView | null =
    overlay && overlay.kind !== 'pick-provider' && overlay.kind !== 'new-connection' && 'connectionId' in overlay
      ? catalog?.connections.find((connection) => connection.id === overlay.connectionId) ?? null
      : null;

  // 详情草稿只在草稿所属连接与当前连接一致时使用，避免跨连接串值（MR-08）
  const activeDraft = overlayConnection && draftConnectionId === overlayConnection.id ? draft : null;
  const detailDirty = Boolean(overlayConnection && activeDraft && connectionDirty(overlayConnection, activeDraft));

  function openConnectionDetail(connection: ModelConnectionView) {
    setActionError(null);
    setImportError(null);
    setDraft(draftFrom(connection));
    setDraftConnectionId(connection.id);
    setOverlay({ kind: 'detail', connectionId: connection.id });
  }

  /** 统一的关闭入口：有未保存更改时先确认（MR-12）。 */
  function requestOverlayClose() {
    if (busy) return;
    if (overlay?.kind === 'detail' && detailDirty) {
      setDiscard({ onDiscard: () => setOverlay(null) });
      return;
    }
    setOverlay(null);
  }

  function beginAddProvider(provider: ModelProviderView) {
    setActionError(null);
    setNewDraft({
      displayName: provider.label,
      baseUrl: provider.defaultApiBase,
      apiKey: '',
      apiVersion: '',
    });
    setOverlay({ kind: 'new-connection', provider });
  }

  async function createNewConnection() {
    if (overlay?.kind !== 'new-connection' || !newDraft) return;
    const provider = overlay.provider;
    const ok = await runAction(async () => {
      const created = await createConnection({
        displayName: newDraft.displayName.trim(),
        providerId: provider.providerId,
        apiFormat: provider.defaultApiFormat,
        baseUrl: newDraft.baseUrl.trim(),
        ...(newDraft.apiVersion.trim() ? { apiVersion: newDraft.apiVersion.trim() } : {}),
        ...(newDraft.apiKey ? { apiKey: newDraft.apiKey } : {}),
      });
      setDraft(draftFrom(created));
      setDraftConnectionId(created.id);
      setOverlay({ kind: 'detail', connectionId: created.id });
      setNewDraft(null);
    }, '连接已创建');
    if (!ok) return; // 失败保留表单与错误（MR-16）
  }

  async function saveConnectionDetail() {
    if (!overlayConnection || !activeDraft) return;
    const targetId = overlayConnection.id;
    await runAction(async () => {
      const extraHeaders = parseHeaders(activeDraft.extraHeadersText);
      const updated = await updateConnection(targetId, {
        displayName: activeDraft.displayName.trim(),
        apiFormat: activeDraft.apiFormat,
        baseUrl: activeDraft.baseUrl.trim(),
        apiVersion: activeDraft.apiVersion.trim() || null,
        ...(activeDraft.apiKey && !activeDraft.clearCredential ? { apiKey: activeDraft.apiKey } : {}),
        ...(activeDraft.clearCredential ? { credentialAction: 'clear' as const } : {}),
        ...(Object.keys(extraHeaders).length > 0 ? { extraHeaders } : {}),
        expectedRevision: catalog?.revision,
      });
      // 用服务端返回的连接重建草稿与基线，避免下一次保存写回旧值（MR-07）
      setDraft(draftFrom(updated));
      setDraftConnectionId(updated.id);
    }, '连接已保存');
  }

  async function saveProfile(value: ProfileFormValue) {
    if (overlay?.kind !== 'profile') return;
    const existing = overlay.profile;
    const destination = value.connectionId;
    await runAction(async () => {
      if (existing) {
        await updateProfile(existing.id, { ...value, expectedRevision: catalog?.revision });
      } else {
        await createProfile(value);
      }
      // 模型可能被移动到另一个连接：草稿必须切到目标连接，否则会串值（MR-08）
      const connection = catalog?.connections.find((item) => item.id === destination) ?? null;
      if (connection) {
        setDraft(draftFrom(connection));
        setDraftConnectionId(connection.id);
      } else {
        setDraft(null);
        setDraftConnectionId(null);
      }
      setOverlay({ kind: 'detail', connectionId: destination });
    }, existing ? '模型已保存' : '模型已添加');
  }

  async function importModels(connectionId: string, ids: string[]): Promise<{ ok: boolean; error?: string }> {
    setImportError(null);
    setImporting(true);
    let failure: string | null = null;
    try {
      const ok = await runAction(async () => {
        const failures: string[] = [];
        for (const id of ids) {
          const exists = catalog?.profiles.some(
            (profile) => profile.connectionId === connectionId && profile.modelId === id,
          );
          if (exists) continue;
          try {
            await createProfile({
              connectionId,
              displayName: id.slice(0, 64),
              modelId: id,
              purpose: 'chat',
            });
          } catch (e) {
            failures.push(`${id}：${e instanceof Error ? e.message : '添加失败'}`);
          }
        }
        if (failures.length > 0) {
          failure = `部分模型未能添加：${failures.join('；')}`;
          throw new Error(failure);
        }
      }, '所选模型已添加');
      if (!ok) {
        const message = failure ?? '部分模型未能添加，请重试。';
        setImportError(message);
        return { ok: false, error: message };
      }
      return { ok: true };
    } finally {
      setImporting(false);
    }
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
              onChange={(id) => void runAction(() => setDefaultModel(id, catalog.revision), '默认模型已更新')}
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
                    onOpen={() => openConnectionDetail(connection)}
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
            onPick={beginAddProvider}
            onClose={() => setOverlay(null)}
          />
        </Modal>
      )}

      {overlay?.kind === 'new-connection' && newDraft && (
        <Modal title="添加连接" onClose={() => !busy && setOverlay(null)}>
          <NewConnectionForm
            providerLabel={overlay.provider.label}
            providerId={overlay.provider.providerId}
            defaultApiBase={overlay.provider.defaultApiBase}
            baseUrlRequired={!overlay.provider.defaultApiBase}
            busy={busy}
            error={actionError}
            draft={newDraft}
            onDraftChange={setNewDraft}
            onSubmit={() => void createNewConnection()}
            onCancel={() => !busy && setOverlay(null)}
          />
        </Modal>
      )}

      {overlay?.kind === 'detail' && overlayConnection && activeDraft && (
        <Modal
          title={`连接 · ${overlayConnection.displayName}`}
          onClose={requestOverlayClose}
        >
          {actionError && (
            <div className="settings-feedback error" role="alert">
              {actionError}
              <button
                onClick={async () => {
                  await refresh();
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
            draft={activeDraft}
            onDraftChange={setDraft}
            onSave={() => void saveConnectionDetail()}
            onClose={requestOverlayClose}
            onCreateModel={() =>
              setOverlay({ kind: 'profile', profile: null, connectionId: overlayConnection.id })
            }
            onDiscover={() => {
              setImportError(null);
              setOverlay({ kind: 'discover', connectionId: overlayConnection.id });
            }}
            onUseModel={(profile) =>
              void runAction(() => setDefaultModel(profile.id, catalog.revision), '已设为问答默认模型')
            }
            onTestModel={(profile, stream) => requestTest(profile, stream)}
            onAuthChanged={() => {
              void refresh();
              notifyModelCatalogChanged();
            }}
            tests={tests}
            onEditModel={(profile) => setOverlay({ kind: 'profile', profile, connectionId: overlayConnection.id })}
            onDeleteModel={(profile) =>
              setConfirm({
                title: '删除模型',
                text: `删除「${profile.displayName}」？历史回答会保留，使用此模型的会话需重新选择。`,
                action: async () => {
                  await runAction(() => deleteProfile(profile.id, catalog?.revision), '模型已删除');
                },
              })
            }
            onDeleteConnection={() =>
              setConfirm({
                title: '删除连接',
                text: `删除「${overlayConnection.displayName}」及服务端保存的凭证？该连接下的模型会阻止删除。`,
                action: async () => {
                  const ok = await runAction(async () => {
                    await deleteConnection(overlayConnection.id, catalog?.revision);
                  }, '连接已删除');
                  if (ok) setOverlay(null);
                },
              })
            }
            busy={busy}
            dirty={detailDirty}
          />
        </Modal>
      )}

      {overlay?.kind === 'discover' && overlayConnection && (
        <Modal title="从服务获取模型" onClose={() => !busy && setOverlay(null)}>
          <ModelListPicker
            connectionId={overlayConnection.id}
            connectionName={overlayConnection.displayName}
            providerId={overlayConnection.providerId}
            providerLabel={overlayConnection.providerLabel}
            existingIds={catalog.profiles
              .filter((profile) => profile.connectionId === overlayConnection.id)
              .map((profile) => profile.modelId)}
            error={importError}
            onAdd={async (ids) => {
              const result = await importModels(overlayConnection.id, ids);
              return result.ok;
            }}
            onManual={() => setOverlay({ kind: 'profile', profile: null, connectionId: overlayConnection.id })}
            onClose={() => !busy && setOverlay(null)}
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

      {discard && (
        <Modal
          title="放弃未保存的更改"
          onClose={() => setDiscard(null)}
        >
          <div role="alertdialog" aria-label="放弃未保存的更改">
            <p>该连接有未保存的更改，关闭将丢弃它们。</p>
            <footer>
              <button className="button subtle" onClick={() => setDiscard(null)}>
                继续编辑
              </button>
              <button
                className="button primary"
                onClick={() => {
                  const action = discard.onDiscard;
                  setDiscard(null);
                  action();
                }}
              >
                放弃更改
              </button>
            </footer>
          </div>
        </Modal>
      )}
    </main>
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
