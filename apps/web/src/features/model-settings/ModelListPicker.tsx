'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw, Search } from 'lucide-react';
import type { DiscoveryResult } from '@/contracts/model-settings';
import { discoverModels } from '@/services/model-settings-api';
import { ProviderMark } from './ProviderMark';

/**
 * 模型发现：只追加、不替换用户已有列表；已有 id 显示为"已添加"且不可重复勾选。
 *
 * 空结果与失败分开陈述：空是"该服务没有返回模型"，失败给出错误码与重试；
 * 无发现能力的供应商明确说明需手工添加，不用静态候选冒充发现结果。
 */
export function ModelListPicker({
  connectionId,
  connectionName,
  providerId,
  providerLabel,
  existingIds,
  onAdd,
  onManual,
  onClose,
}: {
  connectionId: string;
  connectionName: string;
  providerId: string | null;
  providerLabel: string | null;
  existingIds: string[];
  onAdd: (ids: string[]) => Promise<void>;
  onManual: () => void;
  onClose: () => void;
}) {
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const existing = useMemo(() => new Set(existingIds), [existingIds]);

  async function load() {
    setLoading(true);
    setError(null);
    setSelected([]);
    try {
      const next = await discoverModels(connectionId);
      setResult(next);
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : '获取模型列表失败，请重试。');
    } finally {
      setLoading(false);
    }
  }

  // 打开即拉取一次；失败可重试
  useEffect(() => {
    void load();
    // 只在 connectionId 变化时重取；restart 由"重试"按钮显式触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId]);

  const ids = result?.models.map((model) => model.id) ?? [];
  const filtered = ids.filter((id) => id.toLowerCase().includes(query.toLowerCase()));
  const manualOnly = result?.source === 'manual';

  return (
    <div className="model-picker">
      <div className="model-picker-head">
        <ProviderMark providerId={providerId} label={providerLabel ?? connectionName} size={26} />
        <div>
          <strong>{connectionName}</strong>
          <small>{result ? sourceLabel(result.source) : '正在读取模型列表'}</small>
        </div>
        <button className="button subtle" disabled={loading} onClick={() => void load()}>
          {loading ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          重试
        </button>
      </div>

      {error && (
        <p className="settings-feedback error" role="alert">
          <AlertTriangle size={14} />
          {error}
        </p>
      )}

      {loading && (
        <p role="status" className="detail-empty">
          正在获取模型列表…
        </p>
      )}

      {!loading && result && (
        <>
          {result.note && <p className="settings-hint">{result.note}</p>}
          {manualOnly ? (
            <p className="detail-empty">该供应商没有公开的模型列表接口，请手动添加模型 ID。</p>
          ) : ids.length === 0 ? (
            <p className="detail-empty">服务返回了空列表。你仍可手动添加任意合法模型 ID。</p>
          ) : (
            <>
              <div className="model-search">
                <Search size={15} />
                <input
                  aria-label="筛选发现的模型"
                  placeholder="搜索模型 ID"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <div className="discovery-list">
                {filtered.map((id) => {
                  const already = existing.has(id);
                  return (
                    <label key={id} className={already ? 'already' : ''}>
                      <input
                        type="checkbox"
                        disabled={already || saving}
                        checked={already || selected.includes(id)}
                        onChange={() =>
                          setSelected(
                            selected.includes(id)
                              ? selected.filter((value) => value !== id)
                              : [...selected, id],
                          )
                        }
                      />
                      <span>{id}</span>
                      {already && <small>已添加</small>}
                    </label>
                  );
                })}
                {filtered.length === 0 && <p className="detail-empty">没有匹配的模型 ID。</p>}
              </div>
            </>
          )}
        </>
      )}

      <footer className="detail-footer">
        <button className="button subtle" disabled={saving} onClick={onManual}>
          手动添加
        </button>
        <div className="detail-footer-right">
          <button className="button subtle" disabled={saving} onClick={onClose}>
            完成
          </button>
          <button
            className="button primary"
            disabled={saving || selected.length === 0 || manualOnly}
            onClick={async () => {
              setSaving(true);
              try {
                await onAdd(selected);
                setSelected([]);
              } finally {
                setSaving(false);
              }
            }}
          >
            {saving ? '添加中…' : `添加所选 ${selected.length} 个`}
          </button>
        </div>
      </footer>
    </div>
  );
}

function sourceLabel(source: string): string {
  if (source === 'upstream') return '来自上游实时接口';
  if (source === 'manual') return '该供应商无模型列表接口';
  if (source.startsWith('catalog:')) return '来自内置回退目录（非实时）';
  return '模型列表';
}
