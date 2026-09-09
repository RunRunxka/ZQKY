'use client';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { Check, ChevronDown, Search } from 'lucide-react';
import type { ModelCatalog } from '@/contracts/model-settings';
import { Modal } from '@/components/ui/Modal';
import { ModelBrandIcon } from './ModelBrandIcon';

function PickerPanel({
  children,
  popover,
  onClose,
}: {
  children: ReactNode;
  popover: boolean;
  onClose: () => void;
}) {
  if (!popover)
    return (
      <Modal title="选择问答模型" onClose={onClose}>
        {children}
      </Modal>
    );
  return (
    <div className="chat-model-popover" role="dialog" aria-label="选择问答模型">
      {children}
    </div>
  );
}

export function ModelSelector({
  catalog,
  value,
  onChange,
  disabled = false,
  presentation = 'modal',
}: {
  catalog: ModelCatalog | null;
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
  presentation?: 'modal' | 'popover';
}) {
  const [open, setOpen] = useState(false),
    [query, setQuery] = useState('');
  const effective = value ?? catalog?.defaultChatProfileId;
  const active = catalog?.profiles.find((p) => p.id === effective);
  const root = useRef<HTMLDivElement>(null);
  function closePicker() {
    setOpen(false);
    if (presentation === 'popover')
      root.current?.querySelector<HTMLButtonElement>('.model-select-trigger')?.focus();
  }
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);
  useEffect(() => {
    if (!open || presentation !== 'popover') return;
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open, presentation]);
  return (
    <div
      className="model-selector"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation();
          closePicker();
        }
      }}
    >
      <button
        className="model-select-trigger"
        aria-label="选择模型"
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={disabled}
        onClick={() => setOpen(!open)}
      >
        {presentation === 'popover' ? (
          <ModelBrandIcon modelId={active?.modelId} />
        ) : (
          <span className={`model-dot ${active?.connection?.hasCredential ? 'ready' : ''}`} />
        )}
        <span>
          {active?.displayName ?? (effective ? '原模型已不可用' : '选择模型')}
          {!value && active ? ' · 默认' : ''}
        </span>
        <ChevronDown size={14} />
      </button>
      {open && (
        <PickerPanel popover={presentation === 'popover'} onClose={closePicker}>
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
            disabled={disabled}
            onClick={() => {
              onChange(null);
              closePicker();
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
                        disabled={disabled}
                        onClick={() => {
                          onChange(p.id);
                          closePicker();
                        }}
                      >
                        {presentation === 'popover' && <ModelBrandIcon modelId={p.modelId} />}
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
        </PickerPanel>
      )}
    </div>
  );
}
