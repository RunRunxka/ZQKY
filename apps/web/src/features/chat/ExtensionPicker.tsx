'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Blocks, Search, X } from 'lucide-react';
import type { ExtensionEntry } from '@/services/extension-catalog';

/** 退场动画时长：与 --motion-pop / 原版 0.16s 对齐 */
const EXIT_DURATION = 160;

/**
 * 模拟模式扩展选择入口：分开展示已启用的 MCP 与 Skills，支持搜索、选中态与移除。
 * 复用 services/extension-catalog 的目录数据（由父级注入，单一来源），不维护第二套目录。
 * 键盘：Escape 关闭并恢复焦点；触发按钮与选项均有清晰可访问名称。
 * 管理链接定位 /settings#mcp、/settings#skills。
 * 动画对照原版 ChatComposer AnimatePresence：进场 y6/scale.96，退场 y4/scale.97，
 * 160ms cubic-bezier(.16,1,.3,1)（R8）；退场期间面板保持挂载并 inert，动画结束再卸载。
 * R9：进入发送状态（disabled）时关闭已打开的菜单并禁用全部选项，不恢复焦点
 * （焦点已在输入区等可操作位置），覆盖键盘返回输入框发送的路径。
 */
export function ExtensionPicker({
  entries,
  selected,
  onToggle,
  disabled,
}: {
  entries: ExtensionEntry[];
  selected: string[];
  onToggle(id: string): void;
  disabled?: boolean;
}) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const exitTimer = useRef<number | null>(null);
  const enabled = entries.filter((item) => item.enabled);
  const mcps = enabled.filter((item) => item.kind === 'mcp');
  const skills = enabled.filter((item) => item.kind === 'skill');
  const match = (item: ExtensionEntry) =>
    `${item.name} ${item.description}`.toLowerCase().includes(query.toLowerCase());

  function clearExitTimer() {
    if (exitTimer.current) {
      clearTimeout(exitTimer.current);
      exitTimer.current = null;
    }
  }
  function openPanel() {
    clearExitTimer(); // 快速开关：取消未完成的退场卸载，动画正确重启
    setMounted(true);
    setOpen(true);
  }
  function closePanel(restoreFocus: boolean) {
    if (!open) return;
    setOpen(false); // 触发 .closing 退场动画，结束后卸载
    if (restoreFocus) triggerRef.current?.focus();
    clearExitTimer();
    exitTimer.current = window.setTimeout(() => {
      setMounted(false);
      exitTimer.current = null;
    }, EXIT_DURATION);
  }
  useEffect(() => {
    if (disabled && open) closePanel(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);
  useEffect(() => {
    if (open) {
      const frame = requestAnimationFrame(() => searchRef.current?.focus());
      return () => cancelAnimationFrame(frame);
    }
  }, [open]);
  useEffect(() => () => clearExitTimer(), []);
  useEffect(() => {
    // R10：菜单打开时才注册外部点击监听（此前条件写反导致打开时永远不监听）；
    // 外部点击关闭不恢复焦点——焦点留在用户刚点击的位置
    if (!mounted || !open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) closePanel(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, open]);

  function renderItem(item: ExtensionEntry) {
    const isSelected = selected.includes(item.id);
    return (
      <li key={item.id}>
        <button
          type="button"
          disabled={disabled}
          aria-pressed={isSelected}
          aria-label={`${isSelected ? '移除' : '选择'}${item.kind === 'mcp' ? 'MCP' : '技能'} ${item.name}`}
          onClick={() => onToggle(item.id)}
        >
          <span className="chat-ext-item-text">
            <strong>{item.name}</strong>
            <small>{item.description || '暂无描述'}</small>
          </span>
          <span className="chat-ext-item-state">{isSelected ? '已选' : '选择'}</span>
        </button>
      </li>
    );
  }

  return (
    <div className="chat-ext-picker" ref={panelRef}>
      <button
        ref={triggerRef}
        type="button"
        className="chat-ext-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="选择本轮扩展（MCP 与技能）"
        disabled={disabled}
        onClick={() => (open ? closePanel(true) : openPanel())}
      >
        <Blocks size={14} />
        扩展
        {selected.length > 0 && <span className="chat-ext-count">{selected.length}</span>}
      </button>
      {mounted && (
        <div
          className={`chat-ext-panel ${open ? '' : 'closing'}`}
          role="dialog"
          aria-label="选择本轮扩展"
          inert={!open}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.stopPropagation();
              closePanel(true);
            }
          }}
        >
          <div className="chat-ext-search">
            <Search size={13} />
            <input
              ref={searchRef}
              aria-label="搜索扩展"
              placeholder="搜索已启用的扩展"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="button" aria-label="关闭扩展选择" onClick={() => closePanel(true)}>
              <X size={13} />
            </button>
          </div>
          {!enabled.length && (
            <p className="chat-ext-empty">还没有已启用的扩展。可在设置中添加并启用模拟扩展。</p>
          )}
          {mcps.length > 0 && (
            <section>
              <h4>MCP（模拟工具调用）</h4>
              <ul>{mcps.filter(match).map(renderItem)}</ul>
            </section>
          )}
          {skills.length > 0 && (
            <section>
              <h4>Skills（技能上下文）</h4>
              <ul>{skills.filter(match).map(renderItem)}</ul>
            </section>
          )}
          {enabled.length > 0 &&
            !mcps.filter(match).length &&
            !skills.filter(match).length && (
              <p className="chat-ext-empty">没有匹配“{query}”的已启用扩展。</p>
            )}
          <footer className="chat-ext-links">
            <Link href="/settings#mcp">管理 MCP</Link>
            <Link href="/settings#skills">管理 Skills</Link>
          </footer>
        </div>
      )}
    </div>
  );
}
