'use client';
import { useEffect, useRef, useState } from 'react';
import { FolderOpen, Library, MessagesSquare, Plus, UserRound } from 'lucide-react';
import type { PersonaEntry } from '@/services/persona-catalog';
import type { KnowledgeEntry } from '@/services/knowledge-catalog';

const EXIT_DURATION = 160;

/**
 * “添加内容”菜单（S2）：对照参考 ChatComposer 的 Plus/ChatSpaceMenu 入口——
 * 附件选取、角色人设、知识来源、会话引用。角色与知识来源为演示目录
 * （空态提供“载入演示数据”显式入口，不自动写入用户存储）；
 * 会话引用来自当前模式的真实会话列表（不含当前会话）。
 * 书籍/笔记/题库等入口在对应业务页（S5）落地后再进入本菜单，不放死按钮。
 */
export function ComposerAddMenu({
  disabled,
  conversations,
  activeId,
  personas,
  knowledge,
  selectedPersona,
  selectedKnowledge,
  selectedHistory,
  onTogglePersona,
  onToggleKnowledge,
  onToggleHistory,
  onPickFiles,
  onLoadDemoPersonas,
  onLoadDemoKnowledge,
}: {
  disabled?: boolean;
  conversations: { id: string; title: string }[];
  activeId: string | null;
  personas: PersonaEntry[];
  knowledge: KnowledgeEntry[];
  selectedPersona: string | null;
  selectedKnowledge: string[];
  selectedHistory: string[];
  onTogglePersona(id: string | null): void;
  onToggleKnowledge(id: string): void;
  onToggleHistory(id: string): void;
  onPickFiles(): void;
  onLoadDemoPersonas(): void;
  onLoadDemoKnowledge(): void;
}) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const exitTimer = useRef<number | null>(null);
  const referenceable = conversations.filter((c) => c.id !== activeId);
  const selectionCount =
    (selectedPersona ? 1 : 0) + selectedKnowledge.length + selectedHistory.length;

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

  return (
    <div className="chat-add-picker" ref={panelRef}>
      <button
        ref={triggerRef}
        type="button"
        className="chat-add-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="添加文件与上下文"
        title="添加文件与上下文"
        disabled={disabled}
        onClick={() => (open ? closePanel(true) : openPanel())}
      >
        <Plus size={18} strokeWidth={1.8} />
        {selectionCount > 0 && <span className="chat-ext-count">{selectionCount}</span>}
      </button>
      {mounted && (
        <div
          className={`chat-ext-panel chat-add-panel ${open ? '' : 'closing'}`}
          role="dialog"
          aria-label="添加文件与上下文"
          inert={!open}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.stopPropagation();
              closePanel(true);
            }
          }}
        >
          <button type="button" className="chat-add-action" disabled={disabled} onClick={onPickFiles}>
            <FolderOpen size={15} strokeWidth={1.7} />
            <span className="chat-cap-item-text">
              <strong>上传附件</strong>
              <small>图片、Office 文档、代码与文本（无解析服务，发送仅携带元数据）</small>
            </span>
          </button>

          <section>
            <h4>
              <UserRound size={12} /> 角色人设（演示目录，会话级）
            </h4>
            {personas.length === 0 ? (
              <p className="chat-ext-empty">
                还没有角色。可载入演示数据体验（不覆盖已有数据）。
                <button type="button" className="chat-field-button" onClick={onLoadDemoPersonas}>
                  载入演示数据
                </button>
              </p>
            ) : (
              <ul>
                {personas.map((persona) => {
                  const selected = selectedPersona === persona.id;
                  return (
                    <li key={persona.id}>
                      <button
                        type="button"
                        aria-pressed={selected}
                        onClick={() => onTogglePersona(selected ? null : persona.id)}
                      >
                        <span className="chat-ext-item-text">
                          <strong>{persona.name}</strong>
                          <small>{persona.description}</small>
                        </span>
                        <span className="chat-ext-item-state">{selected ? '已选' : '选择'}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section>
            <h4>
              <Library size={12} /> 知识来源（演示目录，仅声明检索范围）
            </h4>
            {knowledge.length === 0 ? (
              <p className="chat-ext-empty">
                还没有知识来源。可载入演示数据体验（无真实检索）。
                <button type="button" className="chat-field-button" onClick={onLoadDemoKnowledge}>
                  载入演示数据
                </button>
              </p>
            ) : (
              <ul>
                {knowledge.map((entry) => {
                  const selected = selectedKnowledge.includes(entry.id);
                  return (
                    <li key={entry.id}>
                      <button
                        type="button"
                        aria-pressed={selected}
                        onClick={() => onToggleKnowledge(entry.id)}
                      >
                        <span className="chat-ext-item-text">
                          <strong>{entry.name}</strong>
                          <small>{entry.description}</small>
                        </span>
                        <span className="chat-ext-item-state">{selected ? '已选' : '选择'}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section>
            <h4>
              <MessagesSquare size={12} /> 会话引用（纳入本轮上下文说明）
            </h4>
            {referenceable.length === 0 ? (
              <p className="chat-ext-empty">还没有其他会话可引用。</p>
            ) : (
              <ul>
                {referenceable.slice(0, 8).map((conversation) => {
                  const selected = selectedHistory.includes(conversation.id);
                  return (
                    <li key={conversation.id}>
                      <button
                        type="button"
                        aria-pressed={selected}
                        onClick={() => onToggleHistory(conversation.id)}
                      >
                        <span className="chat-ext-item-text">
                          <strong>{conversation.title}</strong>
                        </span>
                        <span className="chat-ext-item-state">{selected ? '已选' : '选择'}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

/** 上下文引用树（对照参考 ContextReferenceTree 的行式摘要 + 移除） */
export function ContextRefTree({
  personaName,
  knowledgeNames,
  historyTitles,
  onRemovePersona,
  onRemoveKnowledge,
  onRemoveHistory,
}: {
  personaName: string | null;
  knowledgeNames: { id: string; name: string }[];
  historyTitles: { id: string; title: string }[];
  onRemovePersona(): void;
  onRemoveKnowledge(id: string): void;
  onRemoveHistory(id: string): void;
}) {
  const hasAny = !!personaName || knowledgeNames.length > 0 || historyTitles.length > 0;
  if (!hasAny) return null;
  return (
    <div className="chat-ref-tree" role="list" aria-label="已选上下文引用">
      <span className="chat-ref-tree-label">
        已选引用 · {(personaName ? 1 : 0) + knowledgeNames.length + historyTitles.length}
      </span>
      <div className="chat-ref-tree-rows">
        {personaName && (
          <span className="chat-ref-row" role="listitem">
            角色 · {personaName}
            <button type="button" aria-label={`移除角色 ${personaName}`} onClick={onRemovePersona}>
              ×
            </button>
          </span>
        )}
        {knowledgeNames.map((entry) => (
          <span key={entry.id} className="chat-ref-row" role="listitem">
            知识 · {entry.name}
            <button type="button" aria-label={`移除知识来源 ${entry.name}`} onClick={() => onRemoveKnowledge(entry.id)}>
              ×
            </button>
          </span>
        ))}
        {historyTitles.map((entry) => (
          <span key={entry.id} className="chat-ref-row" role="listitem">
            会话 · {entry.title}
            <button type="button" aria-label={`移除会话引用 ${entry.title}`} onClick={() => onRemoveHistory(entry.id)}>
              ×
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
