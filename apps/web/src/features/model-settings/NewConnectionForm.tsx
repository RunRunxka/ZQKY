'use client';

import { ProviderMark } from './ProviderMark';

export interface DraftConnectionForm {
  displayName: string;
  baseUrl: string;
  apiKey: string;
  apiVersion: string;
}

/**
 * 新建连接草稿表单（MR-16）。
 *
 * Custom / Azure / vLLM 等供应商没有默认地址，必须先收集必填字段再 POST。
 * 之前先在无草稿的情况下直接创建、失败后残留空 overlay，用户无法通过界面创建。
 * 这里只负责收集；创建由父层提交，失败保留输入并显示错误。
 */
export function NewConnectionForm({
  providerLabel,
  providerId,
  defaultApiBase,
  baseUrlRequired,
  busy,
  error,
  draft,
  onDraftChange,
  onSubmit,
  onCancel,
}: {
  providerLabel: string;
  providerId: string;
  defaultApiBase: string;
  baseUrlRequired: boolean;
  busy: boolean;
  error: string | null;
  draft: DraftConnectionForm;
  onDraftChange: (next: DraftConnectionForm) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const canSubmit =
    !busy && draft.displayName.trim().length > 0 && (!baseUrlRequired || draft.baseUrl.trim().length > 0);

  return (
    <form
      className="settings-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
    >
      <p className="settings-hint">
        正在添加 <strong>{providerLabel}</strong>
        {baseUrlRequired ? '。该供应商没有默认地址，请填写 Base URL。' : '。可留空使用供应商默认地址。'}
      </p>
      <label>
        显示名称
        <input
          required
          maxLength={64}
          value={draft.displayName}
          onChange={(e) => onDraftChange({ ...draft, displayName: e.target.value })}
        />
      </label>
      <label>
        Base URL
        <input
          value={draft.baseUrl}
          onChange={(e) => onDraftChange({ ...draft, baseUrl: e.target.value })}
          placeholder={defaultApiBase || 'https://api.example.com/v1'}
        />
        <small className="settings-hint">
          {defaultApiBase
            ? `留空使用供应商默认地址（${defaultApiBase}）。`
            : '该供应商需要显式地址。'}
        </small>
      </label>
      {providerId === 'azure_openai' && (
        <label>
          API 版本（Azure）
          <input
            value={draft.apiVersion}
            onChange={(e) => onDraftChange({ ...draft, apiVersion: e.target.value })}
            placeholder="仅填 preview 会实际转发"
          />
        </label>
      )}
      <label>
        API Key
        <input
          type="password"
          autoComplete="off"
          value={draft.apiKey}
          onChange={(e) => onDraftChange({ ...draft, apiKey: e.target.value })}
          placeholder="保存到服务端凭证存储"
        />
      </label>
      {error && (
        <p className="settings-feedback error" role="alert">
          <ProviderMark providerId={providerId} label={providerLabel} size={18} />
          {error}
        </p>
      )}
      <footer className="settings-form-actions">
        <button type="button" className="button subtle" disabled={busy} onClick={onCancel}>
          取消
        </button>
        <button type="submit" className="button primary" disabled={!canSubmit}>
          {busy ? '创建中…' : '创建连接'}
        </button>
      </footer>
    </form>
  );
}
