'use client';
import { useState } from 'react';
import {
  KNOWN_GENERATION_PARAMS,
  KNOWN_PARAM_LABELS,
  REASONING_EFFORT_LABELS,
  REASONING_EFFORT_VALUES,
  REASONING_STYLE_LABELS,
  type ModelConnectionView,
  type ModelProfileView,
  type ProfileInput,
  type ReasoningEffort,
} from '@/contracts/model-settings';

export type ProfileFormValue = ProfileInput;

/**
 * 模型参数表单。推理控制独立于生成参数：三态开关 + 受控深度枚举，
 * reasoningStyle 只读派生（后端按供应商填），前端据此提示该供应商如何表达推理。
 */
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
  // 三态：null=跟随供应商默认，true/false=显式
  const [reasoningEnabled, setReasoningEnabled] = useState<boolean | null>(
    profile?.reasoningEnabled ?? null,
  );
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort | ''>(
    profile?.reasoningEffort ?? '',
  );
  const selectedConnection = connections.find((connection) => connection.id === connectionId) ?? null;
  const styleHint = profile?.reasoningStyle ?? null;

  function submit() {
    if (busy) return;
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
      reasoningEnabled,
      reasoningEffort: reasoningEffort === '' ? null : reasoningEffort,
    });
  }

  return (
    <form
      className="settings-form"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
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
          placeholder={selectedConnection?.providerId === 'azure_openai' ? 'Azure deployment 名称' : '供应商提供的模型 ID'}
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

      <fieldset className="settings-reasoning">
        <legend>推理控制</legend>
        <p className="settings-hint">
          按供应商约束控制思考过程
          {styleHint ? `（该供应商使用 ${styleHint}）` : ''}。留作“跟随默认”时不改变既有行为。
        </p>
        <label>
          推理开关
          <select
            value={reasoningEnabled === null ? 'auto' : reasoningEnabled ? 'on' : 'off'}
            onChange={(e) => {
              const value = e.target.value;
              const next = value === 'auto' ? null : value === 'on';
              setReasoningEnabled(next);
              if (next === false) setReasoningEffort('');
            }}
          >
            <option value="auto">跟随供应商默认</option>
            <option value="on">开启</option>
            <option value="off">关闭</option>
          </select>
        </label>
        <label>
          推理深度
          <select
            value={reasoningEffort}
            disabled={reasoningEnabled === false}
            onChange={(e) => setReasoningEffort(e.target.value as ReasoningEffort | '')}
          >
            <option value="">未指定</option>
            {REASONING_EFFORT_VALUES.map((effort) => (
              <option key={effort} value={effort}>
                {REASONING_EFFORT_LABELS[effort]}
              </option>
            ))}
          </select>
        </label>
        {reasoningEnabled === false && (
          <small className="settings-hint">已关闭推理，深度选项不可用。</small>
        )}
        {styleHint && (
          <small className="settings-hint">
            运行时字段：<code>{REASONING_STYLE_LABELS[styleHint]}</code>
          </small>
        )}
      </fieldset>

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
          个别模型会由后端固定或移除某些参数（例如 Kimi 系列不接受自定义温度）；保存成功不代表上游已采用。
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
