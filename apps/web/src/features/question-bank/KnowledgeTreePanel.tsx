'use client';

/**
 * 知识点分类卡（参考图左卡，R4-FE 2026-10-11）。
 *
 * - 树形：外层知识点可折叠；每个节点右侧计数 = 该节点**子树**命中当前难度/搜索条件的题目数
 *   （自身 + 后代，`subtreeTotals` 汇总；未展开的节点同样显示总数）；
 * - 顶部「全部题目（N）」= 当前条件下全部题目数，点击清除知识点筛选；
 * - 计数来自 `GET /questions?knowledgePointId=…&limit=1` 的 `total`（受限并发，真实数据）；
 *   任一节点计数读取失败显示 `—` 与重试入口，**不把失败当 0**；
 * - 知识点列表读取失败显示错误码与重试，不当空树；父级未知的节点单独分组，不猜层级。
 */

import { useEffect, useMemo, useState } from 'react';
import { ChevronRight, RefreshCw } from 'lucide-react';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { AnimatedCount } from '@/components/motion/AnimatedCount';
import { ErrorNotice } from './ErrorNotice';
import type { AsyncState } from './hooks';
import {
  buildKnowledgeTree,
  collectNodeIds,
  subtreeTotals,
  type KnowledgeNode,
} from './knowledge-tree';
import { fetchQuestionCount, fetchQuestionCounts } from './question-counts';
import type { QuestionFilters } from './QuestionListCard';

interface CountState {
  own: Map<string, number>;
  failed: string[];
  root: number | undefined;
  rootFailed: boolean;
}

export function KnowledgeTreePanel({
  points,
  onReloadPoints,
  filters,
  selectedId,
  onSelect,
  refreshToken,
}: {
  points: AsyncState<KnowledgePointView[]>;
  onReloadPoints: () => void;
  /** 采用计数口径的筛选条件：难度与关键词（知识点筛选就是本树的选择结果，不参与计数）。 */
  filters: QuestionFilters;
  selectedId: string;
  onSelect: (knowledgePointId: string) => void;
  refreshToken: number;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [counts, setCounts] = useState<CountState | null>(null);
  const [countsBusy, setCountsBusy] = useState(false);
  const [countsEpoch, setCountsEpoch] = useState(0);

  const tree = useMemo(
    () => buildKnowledgeTree(points.phase === 'ready' ? points.data : []),
    [points],
  );
  const nodeIds = useMemo(() => collectNodeIds(tree), [tree]);
  const idsKey = nodeIds.join(',');

  useEffect(() => {
    if (points.phase !== 'ready') return;
    const controller = new AbortController();
    let alive = true;
    const base = { difficulty: filters.difficulty || undefined, q: filters.q || undefined };
    setCountsBusy(true);
    void (async () => {
      let root: number | undefined;
      let rootFailed = false;
      try {
        root = await fetchQuestionCount(undefined, base, controller.signal);
      } catch {
        if (controller.signal.aborted) return;
        rootFailed = true;
      }
      const result = await fetchQuestionCounts(idsKey ? idsKey.split(',') : [], base, controller.signal);
      if (!alive || controller.signal.aborted) return;
      setCounts({ own: result.own, failed: result.failedIds, root, rootFailed });
      setCountsBusy(false);
    })();
    return () => {
      alive = false;
      controller.abort();
    };
  }, [points.phase, idsKey, filters.difficulty, filters.q, refreshToken, countsEpoch]);

  const totals = useMemo(
    () => subtreeTotals(tree.roots, counts?.own ?? new Map()),
    [tree, counts],
  );
  const detachedTotals = useMemo(
    () => subtreeTotals(tree.detached, counts?.own ?? new Map()),
    [tree, counts],
  );
  const failedCount = counts?.failed.length ?? 0;
  const countsReady = counts !== null;

  function toggle(nodeId: string) {
    setExpanded((previous) => ({ ...previous, [nodeId]: previous[nodeId] !== true }));
  }

  function renderNode(node: KnowledgeNode, totalsMap: Map<string, number | undefined>) {
    const children = node.children;
    const open = expanded[node.id] === true;
    const selected = selectedId === node.id;
    return (
      <li className="qb-tree-node" key={node.id}>
        <div className="qb-tree-row">
          {children.length > 0 ? (
            <button
              className="qb-tree-toggle"
              type="button"
              aria-expanded={open}
              aria-label={`${open ? '折叠' : '展开'}知识点 ${node.name}`}
              onClick={() => toggle(node.id)}
            >
              <ChevronRight className={open ? 'qb-tree-caret open' : 'qb-tree-caret'} size={14} aria-hidden />
            </button>
          ) : (
            <span className="qb-tree-toggle-space" aria-hidden />
          )}
          <button
            className={selected ? 'qb-tree-label current' : 'qb-tree-label'}
            type="button"
            aria-pressed={selected}
            title={`${node.name}（${node.code}）`}
            onClick={() => onSelect(node.id)}
          >
            {node.name}
          </button>
          <span className="qb-tree-count">（<AnimatedCount value={totalsMap.get(node.id)} />）</span>
        </div>
        {open && children.length > 0 && (
          <ul className="qb-tree-children">{children.map((child) => renderNode(child, totalsMap))}</ul>
        )}
      </li>
    );
  }

  return (
    <section className="space-card qb-tree-card" aria-label="知识点分类">
      <div className="qb-card-head">
        <h2>知识点分类</h2>
        {countsBusy && (
          <span className="qb-hint" role="status">
            计数读取中…
          </span>
        )}
      </div>

      {points.phase === 'loading' && (
        <div aria-busy="true" aria-label="正在读取知识点分类">
          <div className="space-skeleton" style={{ height: 28 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 28 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 28 }} aria-hidden />
        </div>
      )}

      {points.phase === 'failed' && (
        <ErrorNotice label="知识点分类读取失败" error={points.error} onRetry={onReloadPoints} />
      )}

      {points.phase === 'ready' && (
        <>
          {countsReady && failedCount > 0 && (
            <p className="space-banner error" role="alert" data-testid="qb-tree-count-error">
              有 {failedCount} 个知识点的题量计数读取失败，已显示为「—」（不是 0）。
              <button className="space-button" type="button" onClick={() => setCountsEpoch((n) => n + 1)}>
                <RefreshCw size={14} aria-hidden />
                重试计数
              </button>
            </p>
          )}

          <ul className="qb-tree">
            <li className="qb-tree-node">
              <div className="qb-tree-row">
                <span className="qb-tree-toggle-space" aria-hidden />
                <button
                  className={selectedId === '' ? 'qb-tree-label current' : 'qb-tree-label'}
                  type="button"
                  aria-pressed={selectedId === ''}
                  onClick={() => onSelect('')}
                >
                  全部题目
                </button>
                <span className="qb-tree-count">（<AnimatedCount value={counts?.root} />）</span>
              </div>
            </li>
            {tree.roots.map((node) => renderNode(node, totals))}
          </ul>

          {tree.detached.length > 0 && (
            <div className="qb-tree-detached">
              <p className="qb-hint">
                父级未知的知识点 {tree.unknownParentCount} 个（父节点不在当前列表结果里），原样列出、不猜层级：
              </p>
              <ul className="qb-tree">{tree.detached.map((node) => renderNode(node, detachedTotals))}</ul>
            </div>
          )}

          {tree.roots.length === 0 && tree.detached.length === 0 && (
            <div className="space-empty">
              <strong>还没有知识点</strong>
              <span>先到「知识点」页面按教材目录创建知识点，这里会同步出现分类与题量。</span>
            </div>
          )}
        </>
      )}
    </section>
  );
}
