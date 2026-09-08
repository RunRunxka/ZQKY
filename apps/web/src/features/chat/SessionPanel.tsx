'use client';
import { MessageSquare, Pencil, Plus, Trash2 } from 'lucide-react';
import type { ConversationMeta } from '@/contracts/chat';

export function SessionPanel({
  conversations,
  activeId,
  onNew,
  onSelect,
  onRename,
  onRemove,
}: {
  conversations: ConversationMeta[];
  activeId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="chat-sessions-inner">
      <button className="button subtle chat-new-button" onClick={onNew}>
        <Plus size={15} />
        新对话
      </button>
      {conversations.length === 0 && <p className="chat-empty-hint">还没有历史会话。</p>}
      <ul className="chat-session-list">
        {conversations.map((conversation) => (
          <li key={conversation.id} className={conversation.id === activeId ? 'current' : ''}>
            <button
              className="chat-session-item"
              aria-label={`打开会话 ${conversation.title}`}
              onClick={() => onSelect(conversation.id)}
            >
              <MessageSquare size={15} />
              <span className="chat-session-title">{conversation.title}</span>
              <small>
                {new Date(conversation.updatedAt).toLocaleString('zh-CN', {
                  month: 'numeric',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </small>
            </button>
            <span className="chat-session-actions">
              <button
                className="icon-button"
                aria-label={`重命名会话 ${conversation.title}`}
                onClick={() => onRename(conversation.id)}
              >
                <Pencil size={13} />
              </button>
              <button
                className="icon-button"
                aria-label={`删除会话 ${conversation.title}`}
                onClick={() => onRemove(conversation.id)}
              >
                <Trash2 size={13} />
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
