'use client';
import { useEffect, useRef } from 'react';
import { Check, ChevronDown, Circle, UserRound } from 'lucide-react';
import { loadDemoPersonas, type PersonaEntry } from '@/services/persona-catalog';

/** 参考工具栏中的角色与上下文胶囊；继续使用原目录/会话选择，预算仅为透明估算。 */
export function ComposerContextChips({
  mock,
  personas,
  personaId,
  onPersona,
  disabled,
  contextTokens,
  contentChars,
}: {
  mock: boolean;
  personas: PersonaEntry[];
  personaId: string | null;
  onPersona(id: string | null): void;
  disabled: boolean;
  contextTokens?: number | null;
  contentChars: number;
}) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) {
        root.current
          ?.querySelectorAll('details[open]')
          .forEach((node) => node.removeAttribute('open'));
      }
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, []);
  const tokens = Math.ceil(contentChars / 2);
  const percent = contextTokens ? Math.ceil((tokens / contextTokens) * 100) : null;
  return (
    <div
      className="chat-context-chips"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          const details = (event.target as HTMLElement).closest('details');
          if (details) {
            event.stopPropagation();
            details.open = false;
            details.querySelector('summary')?.focus();
          }
        }
      }}
    >
      {mock && (
        <details className="chat-context-chip chat-persona-chip">
          <summary
            aria-label="选择角色"
            onClick={(event) => {
              if (disabled) event.preventDefault();
            }}
            aria-disabled={disabled}
          >
            <UserRound size={16} strokeWidth={1.65} />
            <span>{personas.find((p) => p.id === personaId)?.name ?? '默认'}</span>
            <ChevronDown size={11} />
          </summary>
          <div className="chat-chip-popover">
            <button
              disabled={disabled}
              onClick={(event) => {
                onPersona(null);
                event.currentTarget.closest('details')!.open = false;
              }}
            >
              <UserRound size={15} />
              默认角色{!personaId && <Check size={14} />}
            </button>
            {personas.map((persona) => (
              <button
                key={persona.id}
                disabled={disabled}
                onClick={(event) => {
                  onPersona(persona.id);
                  event.currentTarget.closest('details')!.open = false;
                }}
              >
                <UserRound size={15} />
                <span>{persona.name}</span>
                {personaId === persona.id && <Check size={14} />}
              </button>
            ))}
            {!personas.length && (
              <button disabled={disabled} onClick={loadDemoPersonas}>
                载入演示角色
              </button>
            )}
            <p>角色仅用于当前模拟会话。</p>
          </div>
        </details>
      )}
      <details className="chat-context-chip chat-budget-chip">
        <summary aria-label="查看上下文估算">
          <Circle size={13} strokeWidth={1.65} />
          <span>{percent === null ? '—' : `${percent}%`}</span>
        </summary>
        <div className="chat-chip-popover">
          <strong>上下文估算</strong>
          <p>
            当前消息与输入约 {tokens.toLocaleString()} tokens
            {contextTokens
              ? `，模型上下文上限 ${contextTokens.toLocaleString()}`
              : '，模型上下文上限未知'}
            。
          </p>
          <p>
            按约 2 字符 / token
            估算，不含系统提示或附件；实际请求沿用原有历史截断与输出预留规则，以供应商返回用量为准。
          </p>
        </div>
      </details>
    </div>
  );
}
