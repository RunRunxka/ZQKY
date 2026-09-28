'use client';

/**
 * 已入库题目列表：学科/年级/版本/状态/关键词筛选 + 分页；题型、题干预览、
 * 答案状态（缺失也照实显示）、难度与知识点标签；点击打开详情抽屉。
 */

import { useState } from 'react';
import { Search } from 'lucide-react';
import type { QuestionStatus, QuestionSummary } from '@/contracts/question-bank';
import { listQuestions, type QuestionQuery } from '@/services/question-bank-api';
import { ErrorNotice } from './ErrorNotice';
import { useAsyncResource } from './hooks';
import { ANSWER_STATE_LABEL, difficultyLabel, formatDateTime, questionTypeLabel } from './labels';
import { QuestionDetailPanel } from './QuestionDetailPanel';
import type { TaxonomyIndex } from './taxonomy';

const PAGE_SIZE = 20;

interface Filters {
  subjectId: string;
  gradeId: string;
  editionId: string;
  status: '' | QuestionStatus;
  q: string;
}

const EMPTY_FILTERS: Filters = {
  subjectId: '',
  gradeId: '',
  editionId: '',
  status: '',
  q: '',
};

function queryOf(filters: Filters, offset: number): QuestionQuery {
  return {
    subjectId: filters.subjectId || undefined,
    gradeId: filters.gradeId || undefined,
    editionId: filters.editionId || undefined,
    status: filters.status || undefined,
    q: filters.q || undefined,
    offset,
    limit: PAGE_SIZE,
  };
}

export function QuestionLibrary({ taxonomy }: { taxonomy: TaxonomyIndex }) {
  const [draftFilters, setDraftFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [openQuestionId, setOpenQuestionId] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const { state, reload } = useAsyncResource(
    (signal) => listQuestions(queryOf(applied, offset), signal),
    JSON.stringify({ applied, offset, refreshToken }),
  );

  function applyFilters(filters: Filters) {
    setApplied(filters);
    setOffset(0);
  }

  return (
    <section className="qb-library" aria-label="已入库题目">
      <form
        className="qb-filters"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilters(draftFilters);
        }}
      >
        <TaxonomyFilter
          id="qb-filter-subject"
          label="学科"
          value={draftFilters.subjectId}
          options={taxonomy.subjects}
          ready={taxonomy.ready}
          onChange={(value) => setDraftFilters((prev) => ({ ...prev, subjectId: value }))}
        />
        <TaxonomyFilter
          id="qb-filter-grade"
          label="年级"
          value={draftFilters.gradeId}
          options={taxonomy.grades}
          ready={taxonomy.ready}
          onChange={(value) => setDraftFilters((prev) => ({ ...prev, gradeId: value }))}
        />
        <TaxonomyFilter
          id="qb-filter-edition"
          label="版本"
          value={draftFilters.editionId}
          options={taxonomy.editions}
          ready={taxonomy.ready}
          onChange={(value) => setDraftFilters((prev) => ({ ...prev, editionId: value }))}
        />
        <label className="qb-field" htmlFor="qb-filter-status">
          状态
          <select
            id="qb-filter-status"
            className="space-select"
            value={draftFilters.status}
            onChange={(event) =>
              setDraftFilters((prev) => ({
                ...prev,
                status: event.target.value as Filters['status'],
              }))
            }
          >
            <option value="">全部</option>
            <option value="confirmed">已入库</option>
            <option value="archived">已归档</option>
          </select>
        </label>
        <label className="qb-field qb-filter-keyword" htmlFor="qb-filter-q">
          关键词
          <input
            id="qb-filter-q"
            value={draftFilters.q}
            placeholder="题干关键词"
            onChange={(event) => setDraftFilters((prev) => ({ ...prev, q: event.target.value }))}
          />
        </label>
        <div className="qb-actions">
          <button className="space-button primary" type="submit">
            <Search size={14} aria-hidden />
            查询
          </button>
          <button
            className="space-button"
            type="button"
            onClick={() => {
              setDraftFilters(EMPTY_FILTERS);
              applyFilters(EMPTY_FILTERS);
            }}
          >
            重置
          </button>
        </div>
      </form>

      {state.phase === 'loading' && (
        <div className="qb-list" aria-busy="true" aria-label="正在读取题目">
          <div className="space-skeleton" style={{ height: 96 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 96 }} aria-hidden />
        </div>
      )}

      {state.phase === 'failed' && (
        <ErrorNotice label="题目列表读取失败" error={state.error} onRetry={reload} />
      )}

      {state.phase === 'ready' && state.data.questions.length === 0 && (
        <div className="space-empty">
          <strong>没有符合条件的题目</strong>
          <span>调整筛选条件，或先在「导入批次」里导入试题并完成校对入库。</span>
        </div>
      )}

      {state.phase === 'ready' && state.data.questions.length > 0 && (
        <>
          <ul className="qb-list qb-question-list">
            {state.data.questions.map((question) => (
              <QuestionRow
                key={question.questionId}
                question={question}
                onOpen={() => setOpenQuestionId(question.questionId)}
              />
            ))}
          </ul>
          <div className="qb-pagination">
            <button
              className="space-button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              上一页
            </button>
            <span>
              第 {offset + 1}–{Math.min(offset + PAGE_SIZE, state.data.total)} 条 / 共{' '}
              {state.data.total} 条
            </span>
            <button
              className="space-button"
              disabled={offset + PAGE_SIZE >= state.data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              下一页
            </button>
          </div>
        </>
      )}

      {openQuestionId && (
        <QuestionDetailPanel
          questionId={openQuestionId}
          taxonomy={taxonomy}
          onClose={() => setOpenQuestionId(null)}
          onChanged={() => setRefreshToken((value) => value + 1)}
        />
      )}
    </section>
  );
}

function QuestionRow({ question, onOpen }: { question: QuestionSummary; onOpen: () => void }) {
  return (
    <li className="qb-question-card">
      <div className="space-meta-row">
        <span className="space-chip blue">{questionTypeLabel(question.type)}</span>
        <span className={question.status === 'confirmed' ? 'space-chip green' : 'space-chip'}>
          {question.status === 'confirmed' ? '已入库' : '已归档'}
        </span>
        <span
          className={question.answerState === 'not_provided' ? 'space-chip amber' : 'space-chip'}
        >
          {ANSWER_STATE_LABEL[question.answerState]}
        </span>
        <span className="space-chip">难度：{difficultyLabel(question.difficulty)}</span>
        <span className="space-chip">修订 r{question.revision}</span>
        <span>{formatDateTime(question.confirmedAt)}</span>
      </div>
      <p className="qb-stem-preview">{question.stemPreview}</p>
      <div className="space-meta-row">
        {question.knowledgeTags.map((tag) => (
          <span key={tag} className="space-chip">
            {tag}
          </span>
        ))}
        <button className="space-button" onClick={onOpen}>
          查看题目
        </button>
      </div>
    </li>
  );
}

function TaxonomyFilter({
  id,
  label,
  value,
  options,
  ready,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: { id: string; label: string }[];
  ready: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <label className="qb-field" htmlFor={id}>
      {label}
      {ready ? (
        <select
          id={id}
          className="space-select"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">全部</option>
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          value={value}
          placeholder="分类 id"
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}
