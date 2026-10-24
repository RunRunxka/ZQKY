'use client';

/**
 * 逻辑库浏览（基础库 / 我的教材共用）：年级/学科/版本筛选 + 卡片列表。
 * 选项来自 `fetchTextbookTaxonomy`；字典加载失败只影响筛选条，不把列表变成空目录。
 */

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, Database } from 'lucide-react';
import type { LibraryKind, LibrarySummary } from '@/contracts/textbook';
import { deleteLibrary, listLibraries } from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import { LIBRARY_KIND_LABEL } from './labels';
import type { TaxonomyIndex } from './taxonomy';

interface Filters {
  gradeId: string;
  subjectId: string;
  editionId: string;
}

const NO_FILTERS: Filters = { gradeId: '', subjectId: '', editionId: '' };

/** 逻辑库删除确认：写明会删库与书册关联、书册/原文保留。 */
export function deleteLibraryConfirmText(library: LibrarySummary): string {
  return (
    `彻底删除逻辑库「${library.displayName}」？\n\n` +
    `库本身与该库的书册关联（${library.documentCount} 册）会被删除，不可恢复。\n` +
    '书册、原文修订与历史引用保留；只在本库中的书册将不再出现在教材库列表。'
  );
}

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
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const removeLibrary = async (library: LibrarySummary) => {
    if (busyId !== null) return;
    setBusyId(library.libraryId);
    setActionError(null);
    try {
      await deleteLibrary(library.libraryId, { expectedRevision: library.revision });
      setConfirmId(null);
      setNotice(`已彻底删除逻辑库「${library.displayName}」；书册与原文修订保留。`);
      reload();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 404) {
        setConfirmId(null);
        setNotice(`逻辑库「${library.displayName}」已不存在。`);
        reload();
        return;
      }
      setActionError(
        error.status === 409
          ? `删除冲突（${error.code}）：${error.message} 已重新读取列表，请比较后重试。`
          : `删除逻辑库失败（${error.code}）：${error.message}`,
      );
      if (error.status === 409) reload();
    } finally {
      setBusyId(null);
    }
  };
  const emptyText =
    kind === 'base'
      ? '还没有基础库（顶部「新建逻辑库」可建；基础库一般由服务端成套建立）'
      : '还没有我的教材（点顶部「新建逻辑库」建一个，导入时在第 4 步加入它）';

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

      {notice && (
        <div className="space-banner info" role="status" data-testid="textbook-library-notice">
          {notice}
          <div className="textbook-panel-actions">
            <button className="space-button" onClick={() => setNotice(null)}>
              关闭
            </button>
          </div>
        </div>
      )}
      {actionError && (
        <div className="space-banner error" role="alert" data-testid="textbook-library-delete-error">
          {actionError}
          <div className="textbook-panel-actions">
            <button className="space-button" onClick={() => setActionError(null)}>
              关闭
            </button>
          </div>
        </div>
      )}

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
            <div
              className="space-persona-card textbook-library-card"
              key={library.libraryId}
              data-testid={`textbook-library-card-${library.libraryId}`}
            >
              <Link
                className="textbook-library-card-main"
                href={`/textbooks/libraries/${encodeURIComponent(library.libraryId)}`}
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
              <div className="textbook-library-card-actions">
                {confirmId === library.libraryId ? (
                  <>
                    <button
                      type="button"
                      className="space-button danger"
                      data-testid={`textbook-library-confirm-${library.libraryId}`}
                      disabled={busyId !== null}
                      onClick={() => void removeLibrary(library)}
                    >
                      {busyId === library.libraryId ? '删除中…' : '确认删除'}
                    </button>
                    <button
                      type="button"
                      className="space-button"
                      disabled={busyId !== null}
                      onClick={() => setConfirmId(null)}
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="space-button"
                    data-testid={`textbook-library-delete-${library.libraryId}`}
                    title={`彻底删除「${library.displayName}」（不可恢复）`}
                    disabled={busyId !== null}
                    onClick={() => {
                      setActionError(null);
                      setConfirmId(library.libraryId);
                    }}
                  >
                    删除逻辑库
                  </button>
                )}
              </div>
              {confirmId === library.libraryId && (
                <p className="textbook-hint textbook-library-confirm" role="alert">
                  {deleteLibraryConfirmText(library)}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
