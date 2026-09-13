'use client';

import { useMemo, useState } from 'react';
import { Loader2, Plus, Settings2, Star, Trash2, Wand2, Waves, Zap } from 'lucide-react';
import {
  API_FORMAT_LABELS,
  CAPABILITY_EVIDENCE_LABELS,
  AUTH_MODE_LABELS,
  PROVIDER_MODE_LABELS,
  type ApiFormat,
  type ModelConnectionView,
  type ModelProfileView,
  type ModelProviderView,
  type ModelTestResult,
} from '@/contracts/model-settings';
import { ProviderMark } from './ProviderMark';
import { AuthPanel } from './AuthPanel';
import { TestResult } from './TestResult';

export interface ConnectionDraft {
  displayName: string;
  baseUrl: string;
  apiFormat: ApiFormat;
  apiVersion: string;
  extraHeadersText: string;
  apiKey: string;
  clearCredential: boolean;
}

/**
 * 连接详情：供应商与地址、认证、模型列表。
 *
 * 表单草稿与已保存态分开——只有"保存修改"提交，成功响应前不显示已保存。
 * 打开本弹窗不会切换问答默认模型；切换只能由模型行上的"用于问答"触发。
 */
export function ConnectionDetail({
  connection,
  provider,
  profiles,
  defaultChatProfileId,
  importing,
  draft,
  onDraftChange,
  onSave,
  onClose,
  onCreateModel,
  onDiscover,
  onUseModel,
  onDeleteModel,
  onDeleteConnection,
  onEditModel,
  onTestModel,
  onAuthChanged,
  tests,
  busy,
  dirty,
}: {
  connection: ModelConnectionView;
  provider: ModelProviderView | null;
  profiles: ModelProfileView[];
  defaultChatProfileId: string | null;
  importing: boolean;
  draft: ConnectionDraft;
  onDraftChange: (next: ConnectionDraft) => void;
  onSave: () => void;
  onClose: () => void;
  onCreateModel: () => void;
  onDiscover: () => void;
  onUseModel: (profile: ModelProfileView) => void;
  onDeleteModel: (profile: ModelProfileView) => void;
  onDeleteConnection: () => void;
  onEditModel: (profile: ModelProfileView) => void;
  onTestModel: (profile: ModelProfileView, stream: boolean) => void;
  /** 受管认证状态变化（授权完成/退出）后通知父层刷新目录与可调用性 */
  onAuthChanged: () => void;
  tests: Record<string, { running: boolean; result?: ModelTestResult; stream: boolean }>;
  busy: boolean;
  dirty: boolean;
}) {
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const formatChoices: ApiFormat[] = useMemo(() => {
    if (!provider) return ['auto', 'openai_chat', 'openai_responses', 'anthropic'];
    return provider.apiFormats.length > 0 ? provider.apiFormats : [provider.defaultApiFormat];
  }, [provider]);
  const formatLocked = formatChoices.length === 1;
  const label = connection.providerLabel ?? '自定义连接';

  function attemptClose() {
    if (dirty) {
      setConfirmDiscard(true);
      return;
    }
    onClose();
  }

  return (
    <div className="connection-detail">
      <div className="detail-head">
        <ProviderMark providerId={connection.providerId} label={label} size={34} />
        <div>
          <h3>{connection.displayName}</h3>
          <p className="detail-subtitle">
            {label}
            {provider && ` · ${PROVIDER_MODE_LABELS[provider.mode]}`}
            {provider && ` · ${AUTH_MODE_LABELS[provider.authMode]}`}
          </p>
        </div>
      </div>

      <section className="detail-section" aria-label="供应商与地址">
        <h3>连接</h3>
        <div className="settings-field-row">
          <label>
            显示名称
            <input
              maxLength={64}
              value={draft.displayName}
              onChange={(e) => onDraftChange({ ...draft, displayName: e.target.value })}
            />
          </label>
          <label>
            API 格式
            <select
              value={draft.apiFormat}
              disabled={formatLocked}
              onChange={(e) => onDraftChange({ ...draft, apiFormat: e.target.value as ApiFormat })}
            >
              {formatChoices.map((format) => (
                <option key={format} value={format}>
                  {API_FORMAT_LABELS[format]}
                </option>
              ))}
            </select>
            {formatLocked && <small className="settings-hint">该供应商的 API 格式固定。</small>}
          </label>
        </div>
        <label>
          Base URL
          <input
            value={draft.baseUrl}
            onChange={(e) => onDraftChange({ ...draft, baseUrl: e.target.value })}
            placeholder={provider?.defaultApiBase || 'https://api.example.com/v1'}
          />
          <small className="settings-hint">
            留空使用供应商默认地址
            {provider?.defaultApiBase ? `（${provider.defaultApiBase}）` : ''}；已填写的内容不会被自动改写。
          </small>
        </label>
        {provider?.baseUrlsByFormat?.anthropic && (
          <small className="settings-hint">
            选择 Anthropic 格式时，默认地址为 {provider.baseUrlsByFormat.anthropic}。
          </small>
        )}
        {connection.providerId === 'azure_openai' && (
          <label>
            API 版本（Azure）
            <input
              value={draft.apiVersion}
              onChange={(e) => onDraftChange({ ...draft, apiVersion: e.target.value })}
              placeholder="仅填 preview 会实际转发"
            />
            <small className="settings-hint">Azure 仅当值为 preview 时附加 api-version；其他值不会显示为已生效。</small>
          </label>
        )}
        <label>
          API Key
          <input
            type="password"
            autoComplete="off"
            value={draft.apiKey}
            disabled={draft.clearCredential}
            onChange={(e) => onDraftChange({ ...draft, apiKey: e.target.value })}
            placeholder={
              draft.clearCredential
                ? '保存后将清除凭证'
                : connection.hasCredential
                  ? '已保存，留空保持不变'
                  : '保存到后端'
            }
          />
        </label>
        <div className="credential-actions">
          <span className="settings-hint">
            凭证状态：{connection.hasCredential ? `已保存（${connection.credentialScope}）` : '未配置'}
            {!connection.hasCredential && connection.hasManagedCredential ? '（使用受管认证）' : ''}
          </span>
          {connection.hasCredential && (
            <label className="settings-check">
              <input
                type="checkbox"
                checked={draft.clearCredential}
                onChange={(e) =>
                  onDraftChange({ ...draft, clearCredential: e.target.checked, apiKey: '' })
                }
              />
              保存时清除凭证
            </label>
          )}
        </div>
        {connection.callableReason && !connection.callable && (
          <small className="settings-hint">{connection.callableReason}</small>
        )}
      </section>

      <section className="detail-section" aria-label="附加请求头">
        <h3>附加请求头</h3>
        <p className="settings-hint">
          仅允许组织/项目归属与 Anthropic beta 等非敏感头；认证头由服务端管理，不能在此覆盖。
          已保存的敏感值不会回显。
        </p>
        {connection.extraHeaderNames.length > 0 && (
          <p className="settings-hint">已配置：{connection.extraHeaderNames.join('、')}</p>
        )}
        <label>
          每行“名称: 值”
          <textarea
            rows={2}
            value={draft.extraHeadersText}
            onChange={(e) => onDraftChange({ ...draft, extraHeadersText: e.target.value })}
            placeholder={'X-Title: 智启课源\nOpenAI-Organization: org_xxx'}
          />
        </label>
      </section>

      <AuthPanel connection={connection} onChanged={onAuthChanged} />

      <section className="detail-section" aria-label="模型列表">
        <div className="detail-section-head">
          <h3>模型</h3>
          <div className="detail-section-actions">
            <button className="button subtle" disabled={busy || importing} onClick={onDiscover}>
              {importing ? <Loader2 size={14} className="spin" /> : <Wand2 size={14} />}
              {importing ? '获取中…' : '从服务获取'}
            </button>
            <button className="button subtle" disabled={busy} onClick={onCreateModel}>
              <Plus size={14} />
              手动添加
            </button>
          </div>
        </div>
        {profiles.length === 0 ? (
          <p className="detail-empty">还没有模型。可从服务获取列表，或手动填写模型 ID。</p>
        ) : (
          <div className="detail-model-list">
            {profiles.map((profile) => (
              <div className="detail-model" key={profile.id}>
                <div className="detail-model-main">
                  <strong>{profile.displayName}</strong>
                  <code>{profile.modelId}</code>
                  <div className="model-facts">
                    <span>输出 {profile.maxOutputTokens?.toLocaleString() ?? '默认'}</span>
                    <span>对话 · {CAPABILITY_EVIDENCE_LABELS[profile.capabilities.chat ?? 'unknown']}</span>
                    {profile.reasoningEnabled === false && <span>推理已关闭</span>}
                    {profile.reasoningEffort && <span>推理 {profile.reasoningEffort}</span>}
                  </div>
                </div>
                <div className="detail-model-actions">
                  {defaultChatProfileId === profile.id ? (
                    <span className="model-default">
                      <Star size={12} />
                      用于问答
                    </span>
                  ) : (
                    <button className="button subtle" disabled={busy} onClick={() => onUseModel(profile)}>
                      用于问答
                    </button>
                  )}
                  <button
                    className="icon-button"
                    aria-label={`连接测试 ${profile.displayName}`}
                    title={connection.callable ? '发送一次少量文本的真实请求' : connection.callableReason ?? '当前不可调用'}
                    disabled={!connection.callable || tests[profile.id]?.running}
                    onClick={() => onTestModel(profile, false)}
                  >
                    {tests[profile.id]?.running ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`流式测试 ${profile.displayName}`}
                    title={connection.callable ? '测试流式输出' : connection.callableReason ?? '当前不可调用'}
                    disabled={!connection.callable || tests[profile.id]?.running}
                    onClick={() => onTestModel(profile, true)}
                  >
                    <Waves size={14} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`编辑 ${profile.displayName}`}
                    title="编辑模型参数与推理控制"
                    disabled={busy}
                    onClick={() => onEditModel(profile)}
                  >
                    <Settings2 size={14} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`删除模型 ${profile.displayName}`}
                    title="删除模型"
                    disabled={busy}
                    onClick={() => onDeleteModel(profile)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {profiles.map((profile) =>
          tests[profile.id] ? (
            <TestResult key={`test-${profile.id}`} test={tests[profile.id]} />
          ) : null,
        )}
      </section>

      <footer className="detail-footer">
        <button className="button subtle danger" disabled={busy} onClick={onDeleteConnection}>
          <Trash2 size={14} />
          删除连接
        </button>
        <div className="detail-footer-right">
          <button className="button subtle" disabled={busy} onClick={attemptClose}>
            关闭
          </button>
          <button className="button primary" disabled={busy || !dirty} onClick={onSave}>
            {busy ? '保存中…' : '保存修改'}
          </button>
        </div>
      </footer>

      {confirmDiscard && (
        <div className="inline-confirm" role="alertdialog" aria-label="放弃未保存的更改">
          <p>该连接有未保存的更改。</p>
          <div>
            <button className="button subtle" onClick={() => setConfirmDiscard(false)}>
              继续编辑
            </button>
            <button
              className="button primary"
              onClick={() => {
                setConfirmDiscard(false);
                onClose();
              }}
            >
              放弃更改
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
