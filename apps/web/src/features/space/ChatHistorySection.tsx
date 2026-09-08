'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Archive,
  ArchiveRestore,
  ArchiveX,
  ExternalLink,
  Pencil,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { SpaceMain } from './SpaceMain';
import { createIdbChatRepository } from '@/services/chat-repository';
import type { ChatServiceKind } from '@/contracts/chat';

/** 汇总两条仓储（真实/模拟）的会话条目——与聊天侧同库同身份，不另造副本 */
interface HistoryEntry {
  mode: ChatServiceKind;
  id: string;
  title: string;
  messageCount: number;
  lastMessage: string;
  createdAt: string;
  updatedAt: string;
  archived: boolean;
  revision: number;
}

type KindFilter = 'all' | 'real' | 'mock';
type ArchiveFilter = 'active' | 'archived' | 'all';

const MODE_LABEL: Record<ChatServiceKind, string> = { real: '真实', mock: '模拟' };

function truncate(text: string, max = 80): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > max ? `${flat.slice(0, max)}…` : flat;
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
}

export function ChatHistorySection() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [kindFilter, setKindFilter] = useState<KindFilter>('all');
  const [archiveFilter, setArchiveFilter] = useState<ArchiveFilter>('active');
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const repos = {
        real: createIdbChatRepository('zhiqikeyuan-chat'),
        mock: createIdbChatRepository('zhiqikeyuan-chat-mock'),
      } as const;
      const modes: ChatServiceKind[] = ['real', 'mock'];
      const all: HistoryEntry[] = [];
      for (const mode of modes) {
        const metas = await repos[mode].list();
        for (const meta of metas) {
          const conversation = await repos[mode].load(meta.id);
          if (!conversation) continue;
          const last = conversation.messages[conversation.messages.length - 1];
          all.push({
            mode,
            id: conversation.id,
            title: conversation.title,
            messageCount: conversation.messages.length,
            lastMessage: last ? truncate(last.content) : '',
            createdAt: conversation.createdAt,
            updatedAt: conversation.updatedAt,
            archived: conversation.archived ?? false,
            revision: conversation.revision ?? 0,
          });
        }
      }
      all.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
      setEntries(all);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法读取本地会话历史。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** 变更前重新载入该会话，用最新 revision 提交（防跨页/跨标签冲突） */
  async function mutate(id: string, mode: ChatServiceKind, patch: { archived?: boolean; title?: string }) {
    setBusy(true);
    setError(null);
    try {
      const repo = createIdbChatRepository(mode === 'mock' ? 'zhiqikeyuan-chat-mock' : 'zhiqikeyuan-chat');
      const conversation = await repo.load(id);
      if (!conversation) {
        setError('会话不存在或已被删除，正在刷新列表。');
        await load();
        return;
      }
      await repo.save({ ...conversation, ...patch }, conversation.revision ?? 0);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '操作失败，原数据未修改。');
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(entry: HistoryEntry) {
    const ok = window.confirm(`删除会话「${entry.title}」？删除后无法恢复。`);
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      const repo = createIdbChatRepository(entry.mode === 'mock' ? 'zhiqikeyuan-chat-mock' : 'zhiqikeyuan-chat');
      const conversation = await repo.load(entry.id);
      if (conversation) await repo.remove(entry.id, conversation.revision ?? 0);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '删除失败，原数据未修改。');
    } finally {
      setBusy(false);
    }
  }

  function beginRename(entry: HistoryEntry) {
    setRenamingId(entry.id);
    setRenameDraft(entry.title);
  }

  async function commitRename(entry: HistoryEntry) {
    setRenamingId(null);
    const title = renameDraft.trim();
    if (!title || title === entry.title) return;
    await mutate(entry.id, entry.mode, { title });
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entries.filter((entry) => {
      if (kindFilter !== 'all' && entry.mode !== kindFilter) return false;
      if (archiveFilter === 'active' && entry.archived) return false;
      if (archiveFilter === 'archived' && !entry.archived) return false;
      if (q && !`${entry.title}\n${entry.lastMessage}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [entries, query, kindFilter, archiveFilter]);

  const archivedCount = entries.filter((e) => e.archived).length;
  const activeCount = entries.length - archivedCount;

  return (
    <SpaceMain
      title="会话历史"
      description="真实与模拟问答的全部会话；重开、重命名、归档或删除。"
      actions={
        <button className="space-button" onClick={() => void load()} disabled={busy || loading}>
          <RefreshCw size={14} />
          刷新
        </button>
      }
    >
      <div className="space-toolbar">
        <input
          className="space-search"
          type="search"
          placeholder="搜索标题或最后一条消息…"
          aria-label="搜索会话历史"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="space-segment" role="group" aria-label="按模式筛选">
          {(
            [
              ['all', '全部'],
              ['real', '真实'],
              ['mock', '模拟'],
            ] as [KindFilter, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              className={kindFilter === value ? 'current' : ''}
              aria-pressed={kindFilter === value}
              onClick={() => setKindFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="space-segment" role="group" aria-label="按归档筛选">
          {(
            [
              ['active', `进行中 (${activeCount})`],
              ['archived', `已归档 (${archivedCount})`],
              ['all', '全部'],
            ] as [ArchiveFilter, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              className={archiveFilter === value ? 'current' : ''}
              aria-pressed={archiveFilter === value}
              onClick={() => setArchiveFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="space-banner error" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div aria-hidden>
          {[0, 1, 2, 3].map((i) => (
            <div className="space-skeleton" key={i} style={{ height: 64 }} />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="space-empty">
          <strong>还没有会话记录</strong>
          <span>到学习问答发起第一次对话后，会话会出现在这里。</span>
          <Link className="space-button primary" href="/chat">
            去学习问答
          </Link>
        </div>
      ) : filtered.length === 0 ? (
        <div className="space-empty">
          <strong>没有符合条件的历史会话</strong>
          <span>调整搜索词或筛选条件后再试。</span>
        </div>
      ) : (
        <ul className="space-session-list">
          {filtered.map((entry) => (
            <li className="space-session-card" key={`${entry.mode}:${entry.id}`}>
              <div className="space-session-top">
                {renamingId === entry.id ? (
                  <input
                    className="space-session-rename"
                    aria-label="会话名称"
                    value={renameDraft}
                    autoFocus
                    onChange={(e) => setRenameDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void commitRename(entry);
                      if (e.key === 'Escape') setRenamingId(null);
                    }}
                    onBlur={() => void commitRename(entry)}
                  />
                ) : (
                  <span className="space-session-title">{entry.title}</span>
                )}
                <span className={`space-chip ${entry.mode === 'mock' ? 'blue' : ''}`}>
                  {MODE_LABEL[entry.mode]}
                </span>
                {entry.archived && <span className="space-chip amber">已归档</span>}
                <span className="space-session-actions">
                  {renamingId !== entry.id && (
                    <button
                      className="icon-button"
                      aria-label={`重命名会话 ${entry.title}`}
                      disabled={busy}
                      onClick={() => beginRename(entry)}
                    >
                      <Pencil size={14} />
                    </button>
                  )}
                  {entry.archived ? (
                    <button
                      className="icon-button"
                      aria-label={`恢复会话 ${entry.title}`}
                      disabled={busy}
                      onClick={() => void mutate(entry.id, entry.mode, { archived: false })}
                    >
                      <ArchiveRestore size={14} />
                    </button>
                  ) : (
                    <button
                      className="icon-button"
                      aria-label={`归档会话 ${entry.title}`}
                      disabled={busy}
                      onClick={() => void mutate(entry.id, entry.mode, { archived: true })}
                    >
                      <Archive size={14} />
                    </button>
                  )}
                  <button
                    className="icon-button"
                    aria-label={`删除会话 ${entry.title}`}
                    disabled={busy}
                    onClick={() => void handleDelete(entry)}
                  >
                    <Trash2 size={14} />
                  </button>
                </span>
              </div>
              {entry.lastMessage && (
                <p className="space-session-preview">{entry.lastMessage}</p>
              )}
              <div className="space-meta-row">
                <span>{entry.messageCount} 条消息</span>
                <span>更新于 {formatTime(entry.updatedAt)}</span>
                <Link
                  className="space-button"
                  href={entry.mode === 'mock' ? `/chat/${entry.id}?mode=mock` : `/chat/${entry.id}`}
                >
                  <ExternalLink size={13} />
                  重新打开
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="space-footnote">
        <ArchiveX size={12} aria-hidden /> 已归档会话不再出现在聊天侧栏，可在此恢复。
      </p>
    </SpaceMain>
  );
}
