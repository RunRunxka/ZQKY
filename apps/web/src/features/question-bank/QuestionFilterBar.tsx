'use client';

/**
 * 题库顶部筛选条（参考图卡片，R4-FE 2026-10-11）：
 * 「选择知识点」下拉 + 「难度」下拉（全部难度 / 基础 / 中等 / 困难）+ 「搜索题目」输入框 +
 * 右侧「＋ 添加题目」品牌蓝主按钮与「批量导入」次按钮。
 *
 * 知识点选项来自知识点库在用列表（父级一次读取，失败时本卡显示错误与重试，**不当空目录**）；
 * 关键词输入 300ms 防抖后应用（回车立即应用），筛选变化由父级重置到第一页。
 */

import { useEffect, useRef, useState } from 'react';
import { Plus, RefreshCw, Upload } from 'lucide-react';
import type { KnowledgePointView } from '@/contracts/knowledge';
import type { AsyncState } from './hooks';
import type { QuestionFilters } from './QuestionListCard';

const SEARCH_DEBOUNCE_MS = 300;

const DIFFICULTY_OPTIONS: { value: QuestionFilters['difficulty']; label: string }[] = [
  { value: '', label: '全部难度' },
  { value: 'easy', label: '基础' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '困难' },
];

export function QuestionFilterBar({
  points,
  onReloadPoints,
  filters,
  onFiltersChange,
  onOpenAdd,
  onOpenImport,
}: {
  points: AsyncState<KnowledgePointView[]>;
  onReloadPoints: () => void;
  filters: QuestionFilters;
  onFiltersChange: (next: QuestionFilters) => void;
  onOpenAdd: () => void;
  onOpenImport: () => void;
}) {
  const [draftQuery, setDraftQuery] = useState(filters.q);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  // 外部重置（清空筛选）时同步输入框；与已应用值相同则不改动，避免打字被覆盖。
  useEffect(() => setDraftQuery(filters.q), [filters.q]);

  useEffect(() => {
    if (draftQuery === filters.q) return;
    const timer = setTimeout(() => {
      onFiltersChange({ ...filtersRef.current, q: draftQuery });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [draftQuery, filters.q, onFiltersChange]);

  function applyQuery() {
    if (draftQuery !== filtersRef.current.q) {
      onFiltersChange({ ...filtersRef.current, q: draftQuery });
    }
  }

  return (
    <form
      className="space-card qb-filter-card"
      aria-label="题目筛选"
      onSubmit={(event) => {
        event.preventDefault();
        applyQuery();
      }}
    >
      <label className="qb-field qb-filter-point" htmlFor="qb-filter-knowledge">
        选择知识点
        <select
          id="qb-filter-knowledge"
          className="space-select"
          value={filters.knowledgePointId}
          disabled={points.phase !== 'ready'}
          onChange={(event) =>
            onFiltersChange({ ...filters, knowledgePointId: event.target.value })
          }
        >
          <option value="">全部知识点</option>
          {points.phase === 'ready' &&
            points.data.map((point) => (
              <option key={point.id} value={point.id}>
                {point.name}
              </option>
            ))}
        </select>
      </label>

      <label className="qb-field qb-filter-difficulty" htmlFor="qb-filter-difficulty">
        难度
        <select
          id="qb-filter-difficulty"
          className="space-select"
          value={filters.difficulty}
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              difficulty: event.target.value as QuestionFilters['difficulty'],
            })
          }
        >
          {DIFFICULTY_OPTIONS.map((option) => (
            <option key={option.value || 'all'} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="qb-field qb-filter-search" htmlFor="qb-filter-q">
        搜索题目
        <input
          id="qb-filter-q"
          type="search"
          value={draftQuery}
          placeholder="题干关键词"
          onChange={(event) => setDraftQuery(event.target.value)}
        />
      </label>

      <div className="qb-filter-actions">
        <button className="space-button primary" type="button" onClick={onOpenAdd}>
          <Plus size={14} aria-hidden />
          添加题目
        </button>
        <button className="space-button" type="button" onClick={onOpenImport}>
          <Upload size={14} aria-hidden />
          批量导入
        </button>
      </div>

      {points.phase === 'failed' && (
        <p className="space-banner error qb-filter-notice" role="alert">
          知识点读取失败（{points.error.code}）：{points.error.message} 知识点筛选与分类计数暂不可用。
          <button className="space-button" type="button" onClick={onReloadPoints}>
            <RefreshCw size={14} aria-hidden />
            重试读取知识点
          </button>
        </p>
      )}
    </form>
  );
}
