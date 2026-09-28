'use client';

/**
 * 逻辑库浏览（基础库 / 我的教材共用）：年级/学科/版本筛选 + 卡片列表。
 * 选项来自 `fetchTextbookTaxonomy`；字典加载失败只影响筛选条，不把列表变成空目录。
 */

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, Database } from 'lucide-react';
import type { LibraryKind } from '@/contracts/textbook';
import { listLibraries } from '@/services/textbook-api';
import { useAsyncResource } from './hooks';
import { LIBRARY_KIND_LABEL } from './labels';
import type { TaxonomyIndex } from './taxonomy';

interface Filters {
  gradeId: string;
  subjectId: string;
  editionId: string;
}

const NO_FILTERS: Filters = { gradeId: '', subjectId: '', editionId: '' };

export function LibraryBrowser({
  kind,
  taxonomy,
  refreshToken = 0,
}: {
  kind: LibraryKind;
  taxonomy: TaxonomyIndex;
  /** 变更时强制刷新（导入/删除后由父级递增）。 */
  refreshToken?: number;
}) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const key = `${kind}|${filters.gradeId}|${filters.subjectId}|${filters.editionId}|${refreshToken}`;
  const { state, reload } = useAsyncResource(
    (signal) =>
      listLibraries(
        {
          kind,
          gradeId: filters.gradeId || undefined,
          subjectId: filters.subjectId || undefined,
          editionId: filters.editionId || undefined,
        },
        signal,
      ),
    key,
  );

  const filterActive = Boolean(filters.gradeId || filters.subjectId || filters.editionId);
  const emptyText = kind === 'base' ? '还没有基础库' : '还没有我的教材';

  return (
    <div className="textbook-browser">
      <div className="space-toolbar textbook-filters">
        <label className="textbook-filter" htmlFor={`textbook-filter-grade-${kind}`}>
          <span>年级</span>
          <select
            id={`textbook-filter-grade-${kind}`}
            className="space-select"
            value={filters.gradeId}
            disabled={!taxonomy.ready}
            onChange={(event) => setFilters({ ...filters, gradeId: event.target.value })}
          >
            <option value="">全部年级</option>
            {taxonomy.grades.map((grade) => (
              <option key={grade.id} value={grade.id}>
                {grade.label}
              </option>
            ))}
          </select>
        </label>
        <label className="textbook-filter" htmlFor={`textbook-filter-subject-${kind}`}>
          <span>学科</span>
          <select
            id={`textbook-filter-subject-${kind}`}
            className="space-select"
            value={filters.subjectId}
            disabled={!taxonomy.ready}
            onChange={(event) => setFilters({ ...filters, subjectId: event.target.value })}
          >
            <option value="">全部学科</option>
            {taxonomy.subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.label}
              </option>
            ))}
          </select>
        </label>
        <label className="textbook-filter" htmlFor={`textbook-filter-edition-${kind}`}>
          <span>版本</span>
          <select
            id={`textbook-filter-edition-${kind}`}
            className="space-select"
            value={filters.editionId}
            disabled={!taxonomy.ready}
            onChange={(event) => setFilters({ ...filters, editionId: event.target.value })}
          >
            <option value="">全部版本</option>
            {taxonomy.editions.map((edition) => (
              <option key={edition.id} value={edition.id}>
                {edition.label}
              </option>
            ))}
          </select>
        </label>
        {filterActive && (
          <button className="space-button" onClick={() => setFilters(NO_FILTERS)}>
            清除筛选
          </button>
        )}
        {!taxonomy.ready && <span className="textbook-hint">字典未加载，筛选暂不可用。</span>}
      </div>

      {state.phase === 'loading' && (
        <div aria-hidden>
          {[0, 1, 2].map((index) => (
            <div className="space-skeleton" key={index} style={{ height: 84 }} />
          ))}
        </div>
      )}

      {state.phase === 'failed' && (
        <div className="space-banner error" role="alert">
          教材库读取失败（{state.error.code}）：{state.error.message}
          <div className="textbook-panel-actions">
            <button className="space-button" onClick={reload}>
              重试
            </button>
          </div>
        </div>
      )}

      {state.phase === 'ready' && state.data.libraries.length === 0 && (
        <div className="space-empty">
          <span className="textbook-empty-icon" aria-hidden>
            <Database size={20} />
          </span>
          <strong>{filterActive ? '当前筛选没有匹配的库' : emptyText}</strong>
          <span>
            {filterActive
              ? '清除筛选后查看全部；筛选只影响展示，不修改任何数据。'
              : kind === 'base'
                ? '基础库由服务端目录维护；同步完成前这里不会显示占位数据。'
                : '导入教材并选择「我的教材」类逻辑库后，会出现在这里。'}
          </span>
          {filterActive && (
            <button className="space-button" onClick={() => setFilters(NO_FILTERS)}>
              清除筛选
            </button>
          )}
        </div>
      )}

      {state.phase === 'ready' && state.data.libraries.length > 0 && (
        <div className="space-card-grid">
          {state.data.libraries.map((library) => (
            <Link
              className="space-persona-card"
              key={library.libraryId}
              href={`/knowledge-bases/libraries/${encodeURIComponent(library.libraryId)}`}
            >
              <ChevronRight className="kb-card-chevron" size={16} aria-hidden />
              <div className="space-card-title">{library.displayName}</div>
              <div className="space-meta-row">
                <span className="space-chip">{LIBRARY_KIND_LABEL[library.kind]}</span>
                {library.gradeId && (
                  <span className="space-chip">年级：{taxonomy.gradeLabel(library.gradeId)}</span>
                )}
                <span className="space-chip">学科：{taxonomy.subjectLabel(library.subjectId)}</span>
                <span className="space-chip">版本：{taxonomy.editionLabel(library.editionId)}</span>
              </div>
              <div className="space-meta-row">
                <span className="space-chip">书册 {library.documentCount}</span>
                <span className={`space-chip ${library.readyDocumentCount > 0 ? 'green' : ''}`}>
                  已就绪 {library.readyDocumentCount}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
