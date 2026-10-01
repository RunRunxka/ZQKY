'use client';

/**
 * 已入库题目列表：学科/年级/版本/状态/知识点/关键词筛选 + 分页；题型、题干预览、
 * 答案状态（缺失也照实显示）、难度与历史知识点标签；点击打开详情抽屉。
 *
 * F10-QB 增量：
 * - **知识点筛选**（后端只匹配当前最新修订上的正式关联；历史修订不算当前归属）；
 * - AI 补题入口（六态任务面板，产物是待校对候选批次）；
 * - 列表里的 `knowledgeTags` 明确标注为「历史标签（旧字段）」，与正式关联分开呈现
 *   （正式关联在详情抽屉的「知识点关联」区块）。
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Sparkles } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { QuestionStatus, QuestionSummary } from '@/contracts/question-bank';
import { listQuestions, type QuestionQuery } from '@/services/question-bank-api';
import { ErrorNotice } from './ErrorNotice';
import { GenerationPanel } from './GenerationPanel';
import { useAsyncResource } from './hooks';
import { ANSWER_STATE_LABEL, difficultyLabel, formatDateTime, questionTypeLabel } from './labels';
import { KnowledgePointSelect } from './KnowledgePointFields';
import { QuestionDetailPanel } from './QuestionDetailPanel';
import type { TaxonomyIndex } from './taxonomy';

const PAGE_SIZE = 20;

interface Filters {
  subjectId: string;
  gradeId: string;
  editionId: string;
  status: '' | QuestionStatus;
  knowledgePointId: string;
  q: string;
}

const EMPTY_FILTERS: Filters = {
  subjectId: '',
  gradeId: '',
  editionId: '',
  status: '',
  knowledgePointId: '',
  q: '',
};

function queryOf(filters: Filters, offset: number): QuestionQuery {
  return {
    subjectId: filters.subjectId || undefined,
    gradeId: filters.gradeId || undefined,
    editionId: filters.editionId || undefined,
    status: filters.status || undefined,
    knowledgePointId: filters.knowledgePointId || undefined,
    q: filters.q || undefined,
    offset,
    limit: PAGE_SIZE,
  };
}

export function QuestionLibrary({
  taxonomy,
  onImportsChanged,
}: {
  taxonomy: TaxonomyIndex;
  /** AI 补题发布候选批次后，通知父级刷新「导入批次」列表。 */
  onImportsChanged?: () => void;
}) {
  const router = useRouter();
  const [draftFilters, setDraftFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [openQuestionId, setOpenQuestionId] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [generationOpen, setGenerationOpen] = useState(false);

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
      <div className="qb-library-head">
        <p className="qb-hint">
          题目列表来自后端；知识点筛选只匹配当前最新修订上的正式知识点关联，
          历史修订与旧标签（knowledgeTags）不参与筛选。
        </p>
        <button
          className="space-button primary"
          data-testid="qb-generation-open"
          onClick={() => setGenerationOpen(true)}
        >
          <Sparkles size={14} aria-hidden />
          AI 补题
        </button>
      </div>

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
          onChange={(value) =>
            // 学科变化：已选知识点可能属于旧学科（后端按学科建关联），清空避免筛出空列表
            setDraftFilters((prev) => ({ ...prev, subjectId: value, knowledgePointId: '' }))
          }
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
        <KnowledgePointSelect
          id="qb-filter-knowledge"
          subjectId={draftFilters.subjectId}
          value={draftFilters.knowledgePointId}
          includeAll
          allLabel="全部知识点"
          testId="qb-library-knowledge-filter"
          onChange={(value) =>
            setDraftFilters((prev) => ({ ...prev, knowledgePointId: value }))
          }
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

      {generationOpen && (
        <Modal title="AI 补题" onClose={() => setGenerationOpen(false)}>
          <GenerationPanel
            taxonomy={taxonomy}
            onClose={() => setGenerationOpen(false)}
            onPublished={() => {
              setRefreshToken((value) => value + 1);
              onImportsChanged?.();
            }}
            onOpenImport={(importId) => {
              setGenerationOpen(false);
              router.push(`/question-bank/imports/${importId}`);
            }}
          />
        </Modal>
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
        {question.knowledgeTags.length > 0 && (
          <span className="qb-legacy-tags-label">历史标签（旧字段）</span>
        )}
        {question.knowledgeTags.map((tag) => (
          <span key={tag} className="space-chip qb-legacy-tag">
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
