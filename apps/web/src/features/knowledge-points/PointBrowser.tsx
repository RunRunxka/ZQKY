'use client';

/**
 * 知识点浏览：学科/状态/关键字筛选 + 列表 / 父树两种视图。
 *
 * 严格区分三态：读取失败显示错误码与重试（**不当空目录**）；空结果显示空态；
 * 父树由 `parentId` / `parentCode` 计算（见 `./tree`），父级不在当前结果的节点
 * 单独成组如实展示。
 */

import { useState } from 'react';
import { List, Plus, RefreshCw, Search, TreePine } from 'lucide-react';
import type { KnowledgePointStatus } from '@/contracts/knowledge';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { knowledgeStatusLabel } from './labels';
import { useAsyncResource } from './hooks';
import { buildPointTree, type PointTreeNode } from './tree';

export interface PointBrowserProps {
  subjects: { id: string; label: string }[];
  taxonomyReady: boolean;
  subjectId: string;
  status: '' | KnowledgePointStatus;
  selectedPointId: string | null;
  onSubjectChange: (value: string) => void;
  onStatusChange: (value: '' | KnowledgePointStatus) => void;
  onSelect: (pointId: string) => void;
  onCreate: () => void;
  /** 创建成功后由父级触发刷新。 */
  refreshToken: number;
}

const STATUS_OPTIONS: { value: '' | KnowledgePointStatus; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'active', label: '在用' },
  { value: 'archived', label: '已归档' },
];

export function PointBrowser({
  subjects,
  taxonomyReady,
  subjectId,
  status,
  selectedPointId,
  onSubjectChange,
  onStatusChange,
  onSelect,
  onCreate,
  refreshToken,
}: PointBrowserProps) {
  const [view, setView] = useState<'list' | 'tree'>('list');
  const [draftQuery, setDraftQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');

  const listKey = `${subjectId}|${status}|${appliedQuery}|${refreshToken}`;
  const points = useAsyncResource(
    (signal) =>
      listKnowledgePoints(
        {
          subjectId: subjectId || undefined,
          status: status || undefined,
          q: appliedQuery || undefined,
          limit: 100,
        },
        signal,
      ),
    `kp-list|${listKey}`,
  );

  function applySearch() {
    setAppliedQuery(draftQuery.trim());
  }

  const items = points.state.phase === 'ready' ? points.state.data.items : [];
  const tree = points.state.phase === 'ready' ? buildPointTree(items) : null;

  return (
    <section className="kp-browser" aria-label="知识点列表">
      <div className="space-toolbar kp-toolbar">
        <label className="kp-field kp-field-inline">
          <span className="kp-field-label">学科</span>
          {taxonomyReady ? (
            <select
              className="space-select"
              value={subjectId}
              aria-label="按学科筛选"
              onChange={(event) => onSubjectChange(event.target.value)}
            >
              <option value="">全部学科</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              className="space-search"
              value={subjectId}
              placeholder="学科 id"
              aria-label="按学科筛选"
              onChange={(event) => onSubjectChange(event.target.value)}
            />
          )}
        </label>

        <div className="space-segment" role="group" aria-label="按状态筛选">
          {STATUS_OPTIONS.map((option) => (
            <button
              key={option.value || 'all'}
              className={status === option.value ? 'current' : ''}
              aria-pressed={status === option.value}
              onClick={() => onStatusChange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <form
          className="kp-search-form"
          onSubmit={(event) => {
            event.preventDefault();
            applySearch();
          }}
        >
          <input
            className="space-search"
            value={draftQuery}
            aria-label="按关键字搜索知识点"
            placeholder="按编码 / 名称 / 别名搜索"
            onChange={(event) => setDraftQuery(event.target.value)}
          />
          <button className="space-button" type="submit">
            <Search size={14} aria-hidden />
            搜索
          </button>
        </form>

        <div className="space-segment" role="group" aria-label="视图">
          <button
            className={view === 'list' ? 'current' : ''}
            aria-pressed={view === 'list'}
            onClick={() => setView('list')}
          >
            <List size={13} aria-hidden />
            列表
          </button>
          <button
            className={view === 'tree' ? 'current' : ''}
            aria-pressed={view === 'tree'}
            onClick={() => setView('tree')}
          >
            <TreePine size={13} aria-hidden />
            父树
          </button>
        </div>

        <button className="space-button" onClick={points.reload}>
          <RefreshCw size={14} aria-hidden />
          刷新
        </button>
        <button className="space-button primary" onClick={onCreate}>
          <Plus size={14} aria-hidden />
          新建知识点
        </button>
      </div>

      {points.state.phase === 'loading' && (
        <div aria-busy="true" aria-label="正在读取知识点">
          <div className="space-skeleton" style={{ height: 64 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 64 }} aria-hidden />
        </div>
      )}

      {points.state.phase === 'failed' && (
        <div className="space-banner error" role="alert" data-testid="kp-list-error">
          <div className="space-banner-row">
            <span>
              知识点读取失败（{points.state.error.code}）：{points.state.error.message}
            </span>
            <button className="space-button" onClick={points.reload}>
              重试
            </button>
          </div>
          <span>这不代表没有知识点；请修复后重试，页面不会用空列表替代失败。</span>
        </div>
      )}

      {points.state.phase === 'ready' && items.length === 0 && (
        <div className="space-empty">
          <strong>没有符合条件的数据</strong>
          <span>
            当前筛选（学科 / 状态 / 关键字）下服务端返回 0 条知识点。可调整筛选或新建知识点。
          </span>
        </div>
      )}

      {points.state.phase === 'ready' && items.length > 0 && view === 'list' && (
        <ul className="kp-list">
          {items.map((point) => (
            <li key={point.id}>
              <button
                className={point.id === selectedPointId ? 'kp-card current' : 'kp-card'}
                aria-current={point.id === selectedPointId}
                onClick={() => onSelect(point.id)}
              >
                <span className="kp-card-main">
                  <span className="kp-card-name">{point.name}</span>
                  <span className="kp-card-code">{point.code}</span>
                </span>
                <span className="space-meta-row">
                  {point.parentCode && <span className="space-chip">父级 {point.parentCode}</span>}
                  <span className="space-chip">版本 v{point.version}</span>
                  <span className="space-chip">编辑锁 r{point.revision}</span>
                  <span
                    className={
                      point.status === 'archived' ? 'space-chip amber' : 'space-chip green'
                    }
                  >
                    {knowledgeStatusLabel(point.status)}
                  </span>
                  {point.aliases.length > 0 && (
                    <span className="space-chip">别名 {point.aliases.length}</span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {points.state.phase === 'ready' && items.length > 0 && view === 'tree' && tree && (
        <div className="kp-tree" role="tree" aria-label="知识点父树">
          {tree.roots.map((node) => (
            <PointTreeBranch
              key={node.point.id}
              node={node}
              depth={0}
              selectedPointId={selectedPointId}
              onSelect={onSelect}
            />
          ))}
          {tree.detached.length > 0 && (
            <div className="kp-tree-detached">
              <p className="space-banner info" role="status">
                有 {tree.detached.length}{' '}
                个知识点的父级不在当前结果里（分页截断、跨学科或已被删除）， 下面按服务端返回的
                `parentCode`/`parentId` 原样列出，不编造层级。
                {tree.cycleCount > 0 && ` 其中 ${tree.cycleCount} 个处于环引用（设计上不应出现）。`}
              </p>
              {tree.detached.map((node) => (
                <PointTreeBranch
                  key={`detached-${node.point.id}`}
                  node={node}
                  depth={0}
                  selectedPointId={selectedPointId}
                  onSelect={onSelect}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {points.state.phase === 'ready' && (
        <p className="space-footnote">
          共 {points.state.data.total} 条（本页 {items.length} 条，上限 100）。 父树只由
          `parentId`/`parentCode` 计算；归档保留历史引用，但新关联不能再选已归档知识点。
        </p>
      )}
    </section>
  );
}

function PointTreeBranch({
  node,
  depth,
  selectedPointId,
  onSelect,
}: {
  node: PointTreeNode;
  depth: number;
  selectedPointId: string | null;
  onSelect: (pointId: string) => void;
}) {
  const { point } = node;
  const unknownParent = point.parentId !== null && depth === 0 && node.children.length === 0;
  return (
    <div className="kp-tree-branch" role="treeitem" aria-selected={point.id === selectedPointId}>
      <button
        className={point.id === selectedPointId ? 'kp-tree-node current' : 'kp-tree-node'}
        style={{ paddingLeft: `${8 + depth * 18}px` }}
        onClick={() => onSelect(point.id)}
      >
        <span className="kp-card-name">{point.name}</span>
        <span className="kp-card-code">{point.code}</span>
        <span className="space-meta-row">
          {unknownParent && point.parentCode && (
            <span className="space-chip amber">父级 {point.parentCode}（不在当前结果）</span>
          )}
          {point.status === 'archived' && <span className="space-chip amber">已归档</span>}
        </span>
      </button>
      {node.children.map((child) => (
        <PointTreeBranch
          key={child.point.id}
          node={child}
          depth={depth + 1}
          selectedPointId={selectedPointId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
