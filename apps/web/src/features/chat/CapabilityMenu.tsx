'use client';
import { useEffect, useRef, useState } from 'react';
import {
  BarChart3,
  BrainCircuit,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  MessageSquare,
  Microscope,
  PenLine,
  Sparkles,
  Youtube,
  type LucideIcon,
} from 'lucide-react';
import { CHAT_CAPABILITIES, getCapability } from '@/services/capability-catalog';

const EXIT_DURATION = 160;

const CAPABILITY_ICONS: Record<string, LucideIcon> = {
  '': MessageSquare,
  ask_questions: CircleHelp,
  deep_question: PenLine,
  visualize: BarChart3,
  deep_solve: BrainCircuit,
  deep_research: Microscope,
  immersive_watching: Youtube,
};

function CapMenuItem({
  value,
  label,
  description,
  icon: Icon,
  selected,
  disabled,
  disabledNote,
  onSelect,
}: {
  value: string;
  label: string;
  description: string;
  icon: LucideIcon;
  selected: boolean;
  disabled?: boolean;
  disabledNote?: string;
  onSelect(value: string): void;
}) {
  return (
    <button
      type="button"
      className={`chat-cap-item ${selected ? 'selected' : ''}`}
      disabled={disabled}
      aria-pressed={selected}
      title={disabled ? disabledNote : undefined}
      onClick={() => onSelect(value)}
    >
      <Icon size={15} strokeWidth={1.7} className="chat-cap-item-icon" />
      <span className="chat-cap-item-text">
        <strong>
          {label}
          {disabled && disabledNote ? <small>{disabledNote}</small> : null}
        </strong>
        <small>{description}</small>
      </span>
      {selected && <Check size={14} strokeWidth={2} className="chat-cap-item-check" />}
    </button>
  );
}

/**
 * 能力选择菜单（S2）：对照参考 ChatComposer 的能力 chip 与弹层——
 * 主列表为常用能力，次要能力收进“更多能力”飞出层（悬停/点击展开）。
 * 不可用能力（真实模式下非对话能力）置灰并标注“真实服务未接入”，
 * 不静默转模拟。动画沿用 160ms 弹层 token，退场后卸载（与 ExtensionPicker 一致）。
 */
export function CapabilityMenu({
  value,
  onSelect,
  disabled,
  unavailable,
}: {
  value: string;
  onSelect(value: string): void;
  disabled?: boolean;
  /** 不可用的能力值集合：置灰、不可选，标注原因 */
  unavailable?: ReadonlySet<string>;
}) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const exitTimer = useRef<number | null>(null);
  const active = getCapability(value);
  const ActiveIcon = CAPABILITY_ICONS[active.value] ?? Sparkles;
  const primary = CHAT_CAPABILITIES.filter((cap) => !cap.secondary);
  const secondary = CHAT_CAPABILITIES.filter((cap) => cap.secondary);

  function clearExitTimer() {
    if (exitTimer.current) {
      clearTimeout(exitTimer.current);
      exitTimer.current = null;
    }
  }
  function openPanel() {
    clearExitTimer();
    setMounted(true);
    setOpen(true);
  }
  function closePanel(restoreFocus: boolean) {
    if (!open) return;
    setOpen(false);
    setMoreOpen(false);
    if (restoreFocus) triggerRef.current?.focus();
    clearExitTimer();
    exitTimer.current = window.setTimeout(() => {
      setMounted(false);
      exitTimer.current = null;
    }, EXIT_DURATION);
  }
  function handleSelect(next: string) {
    onSelect(next);
    closePanel(true);
  }

  useEffect(() => {
    if (disabled && open) closePanel(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);
  useEffect(() => () => clearExitTimer(), []);
  useEffect(() => {
    if (!mounted || !open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) closePanel(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, open]);

  const renderItem = (cap: (typeof CHAT_CAPABILITIES)[number]) => {
    const unavailableHere = unavailable?.has(cap.value) ?? false;
    return (
      <CapMenuItem
        key={cap.value}
        value={cap.value}
        label={cap.label}
        description={cap.description}
        icon={CAPABILITY_ICONS[cap.value] ?? Sparkles}
        selected={active.value === cap.value}
        disabled={disabled || unavailableHere}
        disabledNote={unavailableHere ? '真实服务未接入' : undefined}
        onSelect={handleSelect}
      />
    );
  };

  return (
    <div className="chat-cap-picker" ref={panelRef}>
      <button
        ref={triggerRef}
        type="button"
        className={`chat-ext-trigger chat-cap-trigger ${open ? 'open' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`选择业务能力，当前：${active.label}`}
        disabled={disabled}
        onClick={() => (open ? closePanel(true) : openPanel())}
      >
        <ActiveIcon size={14} />
        <span className="chat-cap-trigger-label">{active.label}</span>
        <ChevronDown size={12} className={`chat-cap-caret ${open ? 'open' : ''}`} />
      </button>
      {mounted && (
        <div
          className={`chat-ext-panel chat-cap-panel ${open ? '' : 'closing'}`}
          role="dialog"
          aria-label="选择业务能力"
          inert={!open}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.stopPropagation();
              closePanel(true);
            }
          }}
        >
          <div className="chat-cap-list">{primary.map(renderItem)}</div>
          <div
            className="chat-cap-more"
            onMouseEnter={() => setMoreOpen(true)}
            onMouseLeave={() => setMoreOpen(false)}
          >
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen((v) => !v)}
            >
              <Sparkles size={15} strokeWidth={1.7} />
              <span className="chat-cap-item-text">
                <strong>更多能力</strong>
                <small>智能体循环驱动的模式</small>
              </span>
              <ChevronRight size={14} strokeWidth={2} />
            </button>
            <div className={`chat-cap-flyout ${moreOpen ? 'open' : ''}`} inert={!moreOpen}>
              <div className="chat-cap-list">{secondary.map(renderItem)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
