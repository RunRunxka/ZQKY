'use client';

/**
 * 历史登记（只读）：既有浏览器本地目录 `@/services/knowledge-catalog` 的登记记录。
 *
 * 说明口径：这是历史本地登记，不参与真实检索；`ready` 也只表示本地登记状态，
 * 不代表已有真实索引。读取失败按错误显示（含重试），不当作空目录、不覆盖原数据。
 */

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronRight, Database } from 'lucide-react';
import {
  readKnowledge,
  subscribeKnowledge,
  type KnowledgeEntry,
} from '@/services/knowledge-catalog';

type ListState =
  | { phase: 'loading' }
  | { phase: 'ready'; entries: KnowledgeEntry[] }
  | { phase: 'failed'; message: string };

export function HistoryRegistrations() {
  const [state, setState] = useState<ListState>({ phase: 'loading' });

  const refresh = useCallback(() => {
    try {
      setState({ phase: 'ready', entries: readKnowledge() });
    } catch (cause) {
      setState({
        phase: 'failed',
        message: cause instanceof Error ? cause.message : '本地登记目录无法读取，原数据未修改。',
      });
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeKnowledge(refresh);
  }, [refresh]);

  return (
    <div className="textbook-history">
      <div className="space-banner info" role="note">
        历史本地登记：这些条目保存在当前浏览器，只作为旧入口保留，<strong>不参与真实检索</strong>；
        其中的「已就绪」是历史登记状态，不代表已有可检索索引。旧课程引用仍按旧 ID 打开。
      </div>

      {state.phase === 'loading' && (
        <div aria-hidden>
          {[0, 1].map((index) => (
            <div className="space-skeleton" key={index} style={{ height: 76 }} />
          ))}
        </div>
      )}

      {state.phase === 'failed' && (
        <div className="space-banner error" role="alert">
          本地登记读取失败：{state.message}
          <div className="textbook-panel-actions">
            <button className="space-button" onClick={refresh}>
              重试
            </button>
          </div>
        </div>
      )}

      {state.phase === 'ready' && state.entries.length === 0 && (
        <div className="space-empty">
          <span className="textbook-empty-icon" aria-hidden>
            <Database size={20} />
          </span>
          <strong>没有历史本地登记</strong>
          <span>旧版浏览器登记记录为空；真实教材请用「导入教材」走服务端入库流程。</span>
        </div>
      )}

      {state.phase === 'ready' && state.entries.length > 0 && (
        <ul className="textbook-history-list">
          {state.entries.map((entry) => (
            <li key={entry.id}>
              <Link
                className="textbook-history-item"
                href={`/knowledge-bases/${encodeURIComponent(entry.name)}`}
              >
                <span className="textbook-history-body">
                  <strong>{entry.name}</strong>
                  <span>{entry.description || '（无简介）'}</span>
                </span>
                <span className="space-meta-row">
                  <span className="space-chip">登记文档 {entry.docs?.length ?? 0}</span>
                  <span className="space-chip">本地登记</span>
                </span>
                <ChevronRight size={16} aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
