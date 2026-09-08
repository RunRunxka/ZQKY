'use client';
import { useState } from 'react';
import {
  KNOWN_GENERATION_PARAMS,
  KNOWN_PARAM_LABELS,
  type ModelConnectionView,
  type ModelProfileView,
  type ProfileInput,
} from '@/contracts/model-settings';

export type ProfileFormValue = ProfileInput;
export function ProfileForm({
  profile,
  connections,
  onCancel,
  onSave,
  initialConnectionId,
  busy = false,
}: {
  profile: ModelProfileView | null;
  connections: ModelConnectionView[];
  initialConnectionId?: string;
  onCancel: () => void;
  onSave: (value: ProfileFormValue) => void;
  busy?: boolean;
}) {
  const [connectionId, setConnectionId] = useState(
    profile?.connectionId ?? initialConnectionId ?? connections[0]?.id ?? '',
  );
  const [displayName, setDisplayName] = useState(profile?.displayName ?? '');
  const [modelId, setModelId] = useState(profile?.modelId ?? '');
  const [context, setContext] = useState(String(profile?.contextTokens ?? ''));
  const [output, setOutput] = useState(String(profile?.maxOutputTokens ?? ''));
  const [supported, setSupported] = useState(profile?.supportedParams ?? []);
  const [params, setParams] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(profile?.params ?? {}).map(([k, v]) => [k, String(v)])),
  );
  return (
    <form
      className="settings-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!busy)
          onSave({
            connectionId,
            displayName: displayName.trim(),
            modelId: modelId.trim(),
            purpose: 'chat',
            contextTokens: context ? Number(context) : null,
            maxOutputTokens: output ? Number(output) : null,
            supportedParams: supported,
            params: Object.fromEntries(
              supported
                .filter((k) => params[k] !== undefined && params[k] !== '')
                .map((k) => [k, Number(params[k])]),
            ),
          });
      }}
    >
      <label>
        所属连接
        <select value={connectionId} onChange={(e) => setConnectionId(e.target.value)} required>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.displayName}
            </option>
          ))}
        </select>
      </label>
      <label>
        显示名称
        <input
          required
          maxLength={64}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
      </label>
      <label>
        模型 ID
        <input
          required
          maxLength={128}
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          placeholder="供应商提供的模型 ID"
        />
      </label>
      <div className="settings-field-row">
        <label>
          上下文长度
          <input
            type="number"
            min={1}
            max={100000000}
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="tokens，未知留空"
          />
        </label>
        <label>
          输出上限
          <input
            type="number"
            min={1}
            max={1000000}
            value={output}
            onChange={(e) => setOutput(e.target.value)}
            placeholder="tokens，默认 2048"
          />
        </label>
      </div>
      <details className="settings-advanced">
        <summary>生成参数与能力</summary>
        <p className="settings-hint">仅勾选供应商明确支持的参数；留空使用供应商默认值。</p>
        {KNOWN_GENERATION_PARAMS.map((k) => (
          <div className="settings-param" key={k}>
            <label className="settings-check">
              <input
                type="checkbox"
                checked={supported.includes(k)}
                onChange={() =>
                  setSupported(
                    supported.includes(k) ? supported.filter((x) => x !== k) : [...supported, k],
                  )
                }
              />
              {KNOWN_PARAM_LABELS[k]}
            </label>
            {supported.includes(k) && (
              <input
                aria-label={`${k} 值`}
                type="number"
                step="0.1"
                min={0}
                max={k === 'temperature' ? 2 : 1}
                value={params[k] ?? ''}
                onChange={(e) => setParams({ ...params, [k]: e.target.value })}
                placeholder="默认"
              />
            )}
          </div>
        ))}
        <p className="settings-hint">
          对话与流式能力通过实际测试验证。图像、工具调用、RAG 尚未接通。
        </p>
      </details>
      <footer>
        <button type="button" className="button subtle" onClick={onCancel} disabled={busy}>
          取消
        </button>
        <button type="submit" className="button primary" disabled={busy || !connectionId}>
          {busy ? '保存中…' : profile ? '保存修改' : '创建模型'}
        </button>
      </footer>
    </form>
  );
}
