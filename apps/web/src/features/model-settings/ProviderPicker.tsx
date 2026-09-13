'use client';

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { PROVIDER_MODE_LABELS, type ModelProviderView } from '@/contracts/model-settings';
import { ProviderMark } from './ProviderMark';

/**
 * 选择供应商：按分组展示（自定义 / 网关 / 云服务 / 本机 / 专用认证）。
 *
 * 目录来自后端注册表（38 条的唯一真值），前端不维护第二份 URL 或能力表；
 * 旧条目（legacy）只用于解析既有配置，不作为新选项出现。
 */
export function ProviderPicker({
  directory,
  onPick,
  onClose,
}: {
  directory: ModelProviderView[];
  onPick: (provider: ModelProviderView) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');
  const groups = useMemo(() => {
    const order = ['direct', 'gateway', 'standard', 'local', 'oauth'] as const;
    const filtered = directory.filter((provider) => {
      const haystack = `${provider.label} ${provider.providerId} ${provider.aliases.join(' ')}`.toLowerCase();
      return haystack.includes(query.toLowerCase());
    });
    return order
      .map((mode) => ({
        mode,
        label: PROVIDER_MODE_LABELS[mode],
        items: filtered.filter((provider) => provider.mode === mode),
      }))
      .filter((group) => group.items.length > 0);
  }, [directory, query]);

  return (
    <div className="provider-picker">
      <div className="model-search">
        <Search size={15} />
        <input
          aria-label="搜索供应商"
          placeholder="搜索供应商名称或别名"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="provider-picker-scroll">
        {groups.map((group) => (
          <section key={group.mode} className="provider-group">
            <h4>{group.label}</h4>
            <div className="provider-group-grid">
              {group.items.map((provider) => (
                <button
                  key={provider.providerId}
                  type="button"
                  className="provider-option"
                  onClick={() => onPick(provider)}
                >
                  <ProviderMark providerId={provider.providerId} label={provider.label} size={26} />
                  <span>
                    <strong>{provider.label}</strong>
                    <small>{provider.requiresKey ? 'API Key' : provider.authMode === 'none' ? '无需凭证' : '专用认证'}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
        ))}
        {groups.length === 0 && <p className="detail-empty">没有匹配的供应商。</p>}
      </div>
      <footer className="detail-footer">
        <div className="detail-footer-right">
          <button className="button subtle" onClick={onClose}>
            取消
          </button>
        </div>
      </footer>
    </div>
  );
}
