'use client';
import { useState } from 'react';
import {
  MODEL_PROTOCOL_LABELS,
  type ModelConnectionView,
  type ModelProtocol,
} from '@/contracts/model-settings';

const PROTOCOLS = Object.keys(MODEL_PROTOCOL_LABELS) as ModelProtocol[];

export interface ConnectionFormValue {
  displayName: string;
  protocol: ModelProtocol;
  baseUrl: string;
  apiKey?: string;
  extraHeaders?: Record<string, string>;
}

export function ConnectionForm({
  connection,
  onCancel,
  onSave,
  busy = false,
}: {
  connection: ModelConnectionView | null;
  onCancel: () => void;
  onSave: (value: ConnectionFormValue) => void;
  busy?: boolean;
}) {
  const [displayName, setDisplayName] = useState(connection?.displayName ?? '');
  const [protocol, setProtocol] = useState<ModelProtocol>(connection?.protocol ?? 'openai-chat');
  const [baseUrl, setBaseUrl] = useState(connection?.baseUrl ?? '');
  const [apiKey, setApiKey] = useState('');
  const [headersText, setHeadersText] = useState('');

  function submit() {
    if (busy || !displayName.trim() || !baseUrl.trim()) return;
    const extraHeaders = parseHeaders(headersText);
    onSave({
      displayName: displayName.trim(),
      protocol,
      baseUrl: baseUrl.trim(),
      ...(apiKey ? { apiKey } : {}),
      ...(Object.keys(extraHeaders).length > 0 ? { extraHeaders } : {}),
    });
  }

  return (
    <form
      className="settings-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label>
        显示名称
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
          maxLength={64}
        />
      </label>
      <label>
        协议
        <select value={protocol} onChange={(e) => setProtocol(e.target.value as ModelProtocol)}>
          {PROTOCOLS.map((item) => (
            <option key={item} value={item}>
              {MODEL_PROTOCOL_LABELS[item]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Base URL
        <input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://api.example.com/v1"
          required
        />
      </label>
      <label>
        API Key
        <input
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={connection?.hasCredential ? '已保存，留空保持不变' : '仅写入当前服务进程'}
        />
      </label>
      <small className="settings-hint">
        认证头按协议自动处理（OpenAI 系 Bearer、Anthropic x-api-key），凭证不会回显也不会写入文件。
      </small>
      <label>
        附加请求头（可选，每行“名称: 值”）
        <textarea
          rows={2}
          value={headersText}
          onChange={(e) => setHeadersText(e.target.value)}
          placeholder="X-Title: 智启课源"
        />
      </label>
      <footer className="settings-form-actions">
        <button type="button" className="button subtle" onClick={onCancel}>
          取消
        </button>
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? '保存中…' : connection ? '保存修改' : '创建连接'}
        </button>
      </footer>
    </form>
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
