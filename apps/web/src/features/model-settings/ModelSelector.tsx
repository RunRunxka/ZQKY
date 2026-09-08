'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Check, ChevronDown, Search } from 'lucide-react';
import type { ModelCatalog } from '@/contracts/model-settings';
import { Modal } from '@/components/ui/Modal';

export function ModelSelector({
  catalog,
  value,
  onChange,
  disabled = false,
}: {
  catalog: ModelCatalog | null;
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [query, setQuery] = useState('');
  const effective = value ?? catalog?.defaultChatProfileId;
  const active = catalog?.profiles.find((p) => p.id === effective);
  return (
    <div className="model-selector">
      <button
        className="model-select-trigger"
        aria-label="选择模型"
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <span className={`model-dot ${active?.connection?.hasCredential ? 'ready' : ''}`} />
        <span>
          {active?.displayName ?? (effective ? '原模型已不可用' : '选择模型')}
          {!value && active ? ' · 默认' : ''}
        </span>
        <ChevronDown size={14} />
      </button>
      {open && (
        <Modal title="选择问答模型" onClose={() => setOpen(false)}>
          <div className="model-search">
            <Search size={16} />
            <input
              autoFocus
              aria-label="搜索模型"
              placeholder="搜索模型或连接"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            className="model-choice"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
          >
            <span>使用全局默认模型</span>
            {!value && <Check size={16} />}
          </button>
          <div className="model-choice-list">
            {catalog?.connections.map((c) => {
              const profiles = catalog.profiles.filter(
                (p) =>
                  p.connectionId === c.id &&
                  (p.purpose === 'chat' || p.purpose === null) &&
                  `${p.displayName} ${p.modelId} ${c.displayName}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
              );
              return (
                profiles.length > 0 && (
                  <section key={c.id}>
                    <h3>{c.displayName}</h3>
                    {profiles.map((p) => (
                      <button
                        key={p.id}
                        className="model-choice"
                        onClick={() => {
                          onChange(p.id);
                          setOpen(false);
                        }}
                      >
                        <span>
                          <strong>{p.displayName}</strong>
                          <small>
                            {p.modelId}
                            {!c.hasCredential ? ' · 需填写凭证' : ''}
                          </small>
                        </span>
                        {value === p.id && <Check size={16} />}
                      </button>
                    ))}
                  </section>
                )
              );
            })}
          </div>
          {!catalog?.profiles.length && <p>还没有可用的模型，请先添加连接和模型。</p>}
          <footer>
            <Link href="/settings" onClick={() => setOpen(false)} className="button subtle">
              管理模型
            </Link>
          </footer>
        </Modal>
      )}
    </div>
  );
}
