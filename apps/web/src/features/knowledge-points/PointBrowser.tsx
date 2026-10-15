'use client';

/**
 * 知识点树（左栏卡片）：范围（任教范围 / 学科全部）+ 学科/年级/状态/关键字筛选 +
 * 可展开父树 / 列表两种视图。
 *
 * 范围口径（设计 3.2）：
 * - **默认「任教范围内教材」**（`scope=taught`，窄口径）；服务端未就绪时给 409
 *   `KNOWLEDGE_SCOPE_UNAVAILABLE` → 列表区显示服务端原因 + 「去设置任教范围」入口，
 *   **绝不静默回退成「全部」**；用户可显式切到「学科全部教材」（`scope=subject`）。
 * - 年级筛选优先用 `GET /textbook-taxonomy` 的年级字典；字典不可用时降级为「汇总当前结果
 *   `gradeIds`」，并在页面上如实说明这个局限（不凭空造年级）。
 *
 * 严格区分三态：读取失败显示错误码与重试（**不当空目录**）；空结果显示空态；
 * 父树由 `parentId` / `parentCode` 计算（见 `./tree`），父级不在当前结果的节点
 * 单独成组如实展示。
 *
 * 视觉（R3-FE）：卡片 = 标题 + 搜索框（占位「搜索知识点」）+ 次级筛选行 + 树；
 * 树节点 = 箭头（展开/收起）+ 名称（按层级缩进），选中节点浅蓝底 + 品牌蓝文字。
 * 展开/收起只影响显示，不改变任何请求参数。
 */

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, List, Plus, RefreshCw, Search, TreePine } from 'lucide-react';
import type { KnowledgePointScope, KnowledgePointStatus } from '@/contracts/knowledge';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import {
  KNOWLEDGE_POINT_SCOPE_LABEL,
  KNOWLEDGE_SCOPE_UNAVAILABLE_CODE,
  TAUGHT_SCOPE_SETTINGS_HREF,
  collectResultGradeIds,
  knowledgeStatusLabel,
} from './labels';
import { useAsyncResource } from './hooks';
import { buildPointTree, type PointTreeNode } from './tree';
import { SlidingGroup } from '@/components/ui/SlidingGroup';

export interface PointBrowserProps {
  subjects: { id: string; label: string }[];
  taxonomyReady: boolean;
  /** `GET /textbook-taxonomy` 的年级字典；不可用时传空数组（自动降级为结果汇总）。 */
  grades?: { id: string; label: string }[];
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

// 默认学科口径：新架构不把「任教范围」作为前置（该口径未就绪时保持服务端拒绝语义，
// 显式切到 taught 才会请求，不做静默回退）。
const DEFAULT_SCOPE: KnowledgePointScope = 'subject';

export function PointBrowser({
  subjects,
  taxonomyReady,
  grades = [],
  subjectId,
  status,
  selectedPointId,
  onSubjectChange,
  onStatusChange,
  onSelect,
  onCreate,
  refreshToken,
}: PointBrowserProps) {
  // 默认树视图：知识点天然按教材目录成树；列表口径保留给「按编码逐个核对」的场景
  const [view, setView] = useState<'list' | 'tree'>('tree');
  const [draftQuery, setDraftQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [scope, setScope] = useState<KnowledgePointScope>(DEFAULT_SCOPE);
  const [gradeId, setGradeId] = useState('');
  /** 已折叠的节点 id：默认全部展开；折叠状态只影响显示。 */
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set<string>());

  const listKey = `${subjectId}|${status}|${appliedQuery}|${scope}|${gradeId}|${refreshToken}`;
  const points = useAsyncResource(
    (signal) =>
      listKnowledgePoints(
        {
          subjectId: subjectId || undefined,
          status: status || undefined,
          q: appliedQuery || undefined,
          scope,
          gradeId: gradeId || undefined,
          limit: 100,
        },
        signal,
      ),
    `kp-list|${listKey}`,
  );

  function applySearch() {
    setAppliedQuery(draftQuery.trim());
  }

  function toggleNode(pointId: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(pointId)) next.delete(pointId);
      else next.add(pointId);
      return next;
    });
  }

  const items = points.state.phase === 'ready' ? points.state.data.items : [];
  const tree = points.state.phase === 'ready' ? buildPointTree(items) : null;
  const scopeUnavailable =
    points.state.phase === 'failed' &&
    points.state.error.code === KNOWLEDGE_SCOPE_UNAVAILABLE_CODE;
  const gradesFromTaxonomy = grades.length > 0;
  // 降级来源：字典不可用时只汇总本页服务端确实返回的 gradeIds（不造年级）
  const fallbackGradeIds = gradesFromTaxonomy ? [] : collectResultGradeIds(items);
  const gradeOptions = gradesFromTaxonomy
    ? grades.map((grade) => ({ id: grade.id, label: grade.label }))
    : fallbackGradeIds.map((id) => ({ id, label: id }));
  if (gradeId && !gradeOptions.some((option) => option.id === gradeId)) {
    // 已选年级不在当前选项里：保留它（不静默丢掉筛选条件），仍可手动切回
    gradeOptions.push({ id: gradeId, label: gradeId });
  }
  const gradeLabelOf = (id: string) =>
    grades.find((grade) => grade.id === id)?.label ?? id;

  return (
    <section className="kp-tree-card" aria-label="知识点树">
      <header className="kp-card-head">
        <div className="kp-card-heading">
          <h2 className="kp-card-title">知识点树</h2>
          <p className="kp-card-sub">
            {points.state.phase === 'ready'
              ? `本页 ${items.length} 个节点 · 共 ${points.state.data.total} 个`
              : '按教材目录成树；节点可人工增改'}
          </p>
        </div>
        <div className="kp-card-actions">
          <button className="space-button" onClick={points.reload}>
            <RefreshCw size={14} aria-hidden />
            刷新
          </button>
          <button className="space-button primary" onClick={onCreate}>
            <Plus size={14} aria-hidden />
            新建知识点
          </button>
        </div>
      </header>

      <form
        className="kp-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          applySearch();
        }}
      >
        <Search size={15} aria-hidden className="kp-search-icon" />
        <input
          className="kp-search-input"
          value={draftQuery}
          aria-label="按关键字搜索知识点"
          placeholder="搜索知识点"
          onChange={(event) => setDraftQuery(event.target.value)}
        />
        <button className="space-button kp-search-submit" type="submit">
          搜索
        </button>
      </form>

      <div className="kp-filters">
        <SlidingGroup activeKey={scope} className="space-segment" role="group" aria-label="按教材范围筛选">
          {(Object.keys(KNOWLEDGE_POINT_SCOPE_LABEL) as KnowledgePointScope[]).map((value) => (
            <button
              key={value}
              className={scope === value ? 'current' : ''}
              aria-pressed={scope === value}
              data-testid={`kp-scope-${value}`}
              onClick={() => setScope(value)}
            >
              {KNOWLEDGE_POINT_SCOPE_LABEL[value]}
            </button>
          ))}
        </SlidingGroup>

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

        <label className="kp-field kp-field-inline">
          <span className="kp-field-label">年级</span>
          <select
            className="space-select"
            value={gradeId}
            aria-label="按年级筛选"
            disabled={gradeOptions.length === 0}
            onChange={(event) => setGradeId(event.target.value)}
          >
            <option value="">全部年级</option>
            {gradeOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <SlidingGroup activeKey={status} className="space-segment" role="group" aria-label="按状态筛选">
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
        </SlidingGroup>

        <SlidingGroup activeKey={view} className="space-segment kp-view-switch" role="group" aria-label="视图">
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
        </SlidingGroup>
      </div>

      {points.state.phase === 'loading' && (
        <div aria-busy="true" aria-label="正在读取知识点">
          <div className="space-skeleton" style={{ height: 64 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 64 }} aria-hidden />
        </div>
      )}

      {points.state.phase === 'failed' && scopeUnavailable && (
        <div className="space-banner error" role="alert" data-testid="kp-scope-unavailable">
          <div className="space-banner-row">
            <span>
              「{KNOWLEDGE_POINT_SCOPE_LABEL.taught}」当前不可用（
              {points.state.error.code}）：{points.state.error.message}
            </span>
            <Link className="space-button" href={TAUGHT_SCOPE_SETTINGS_HREF}>
              去设置任教范围
            </Link>
            <button className="space-button" onClick={points.reload}>
              重试
            </button>
          </div>
          <span>
            页面<strong>没有</strong>改成显示全部知识点：任教范围未就绪时列表为空是服务端明确
            拒绝的结果。可先去「教材资料库」保存任教范围，或显式切到「
            {KNOWLEDGE_POINT_SCOPE_LABEL.subject}」。
          </span>
          <div className="kp-actions">
            <button
              className="space-button"
              data-testid="kp-scope-switch-subject"
              onClick={() => setScope('subject')}
            >
              改用「{KNOWLEDGE_POINT_SCOPE_LABEL.subject}」（显式切换）
            </button>
          </div>
        </div>
      )}

      {points.state.phase === 'failed' && !scopeUnavailable && (
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

      <p className="kp-hint" data-testid="kp-scope-hint">
        {scope === 'taught'
          ? '当前只显示任教范围内教材来源的知识点（窄口径）。范围未就绪时会在上方给出原因与设置入口，不会静默改成「全部」。'
          : `当前显示「${KNOWLEDGE_POINT_SCOPE_LABEL.subject}」来源的知识点：用于备课/复习时跨册查看；可切到「${KNOWLEDGE_POINT_SCOPE_LABEL.taught}」按任教范围收窄（需先保存任教范围）。`}
      </p>

      {!gradesFromTaxonomy && (
        <p className="kp-hint" data-testid="kp-grade-fallback">
          年级字典（/textbook-taxonomy）当前不可用：年级筛选项由本页结果里的 `gradeIds`
          汇总而来（只含当前筛选下出现过的年级），不是完整字典，因此可能缺少其他年级。
        </p>
      )}

      {points.state.phase === 'ready' && items.length === 0 && (
        <div className="space-empty">
          <strong>没有符合条件的数据</strong>
          <span>
            当前筛选（{KNOWLEDGE_POINT_SCOPE_LABEL[scope]} / 学科 / 年级 / 状态 / 关键字）下服务端
            返回 0 条知识点。可调整筛选或新建知识点。
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
                  {(point.gradeIds ?? []).map((id) => (
                    <span key={id} className="space-chip blue" title={id}>
                      年级 {gradeLabelOf(id)}
                    </span>
                  ))}
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
              collapsed={collapsed}
              gradeLabelOf={gradeLabelOf}
              onToggle={toggleNode}
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
                  collapsed={collapsed}
                  gradeLabelOf={gradeLabelOf}
                  onToggle={toggleNode}
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
  collapsed,
  gradeLabelOf,
  onToggle,
  onSelect,
}: {
  node: PointTreeNode;
  depth: number;
  selectedPointId: string | null;
  collapsed: ReadonlySet<string>;
  gradeLabelOf: (gradeId: string) => string;
  onToggle: (pointId: string) => void;
  onSelect: (pointId: string) => void;
}) {
  const { point } = node;
  const hasChildren = node.children.length > 0;
  const expanded = hasChildren && !collapsed.has(point.id);
  const unknownParent = point.parentId !== null && depth === 0 && node.children.length === 0;
  const current = point.id === selectedPointId;
  return (
    <div
      className="kp-tree-branch"
      role="treeitem"
      aria-selected={current}
      aria-expanded={hasChildren ? expanded : undefined}
    >
      <div
        className={current ? 'kp-tree-row current' : 'kp-tree-row'}
        style={{ paddingLeft: `${depth * 18}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            className={expanded ? 'kp-tree-toggle expanded' : 'kp-tree-toggle'}
            aria-label={`${expanded ? '收起' : '展开'} ${point.name}`}
            aria-expanded={expanded}
            onClick={() => onToggle(point.id)}
          >
            <ChevronRight size={14} aria-hidden />
          </button>
        ) : (
          <span className="kp-tree-toggle kp-tree-leaf" aria-hidden />
        )}
        <button
          type="button"
          className="kp-tree-node"
          aria-current={current}
          onClick={() => onSelect(point.id)}
        >
          <span className="kp-tree-name">{point.name}</span>
          <span className="kp-tree-code">{point.code}</span>
          {(point.gradeIds ?? []).map((id) => (
            <span key={id} className="space-chip blue kp-tree-chip" title={id}>
              年级 {gradeLabelOf(id)}
            </span>
          ))}
          {unknownParent && point.parentCode && (
            <span className="space-chip amber kp-tree-chip">父级 {point.parentCode}（不在当前结果）</span>
          )}
          {point.status === 'archived' && (
            <span className="space-chip amber kp-tree-chip">已归档</span>
          )}
        </button>
      </div>
      {expanded && (
        <div className="kp-tree-children" role="group">
          {node.children.map((child) => (
            <PointTreeBranch
              key={child.point.id}
              node={child}
              depth={depth + 1}
              selectedPointId={selectedPointId}
              collapsed={collapsed}
              gradeLabelOf={gradeLabelOf}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}
