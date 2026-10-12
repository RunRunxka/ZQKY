'use client';

/**
 * 题目列表卡（参考图右卡，R4-FE 2026-10-11）。
 *
 * 行 = 题干（Markdown + KaTeX 渲染，沿用项目既有渲染模式）+ 难度徽标 + 「编辑」「删除」文字操作；
 * 底部 = 「共 N 条记录」+ 上一页 / 页码（省略号）/ 下一页。
 *
 * 纪律：
 * - 三态严格区分（loading / failed / ready），失败显示错误码与重试，**不当空列表**；
 * - 「删除」= 归档删除（后端 `DELETE /questions/{id}` + `expectedRevision`），二次确认后才发请求，
 *   成功刷新由父级重取服务端权威列表；失败原样显示原因，不假装成功；
 * - 题干来自服务端列表摘要（`stemPreview`）；完整题干与富内容在详情/校对面板渲染。
 */

import { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import type { QuestionSummary } from '@/contracts/question-bank';
import { deleteQuestion, listQuestions, type QuestionQuery } from '@/services/question-bank-api';
import { ContentMarkdown } from './rich-content';
import { ErrorNotice } from './ErrorNotice';
import { asApiError, useAsyncResource } from './hooks';
import { difficultyBadgeClass, difficultyLabel } from './labels';
import { offsetOf, pageOf, pageWindow, totalPagesOf } from './paging';

export const QUESTION_PAGE_SIZE = 20;

export interface QuestionFilters {
  knowledgePointId: string;
  difficulty: '' | 'easy' | 'medium' | 'hard';
  q: string;
}

export const EMPTY_QUESTION_FILTERS: QuestionFilters = {
  knowledgePointId: '',
  difficulty: '',
  q: '',
};

function queryOf(filters: QuestionFilters, offset: number): QuestionQuery {
  return {
    knowledgePointId: filters.knowledgePointId || undefined,
    difficulty: filters.difficulty || undefined,
    q: filters.q || undefined,
    offset,
    limit: QUESTION_PAGE_SIZE,
  };
}

export function QuestionListCard({
  filters,
  offset,
  onOffsetChange,
  refreshToken,
  actionError,
  onEdit,
  onDeleted,
  onAdd,
}: {
  filters: QuestionFilters;
  offset: number;
  onOffsetChange: (next: number) => void;
  /** 外部写入（确认入库、编辑、删除、导入）后 +1，强制重取服务端权威列表。 */
  refreshToken: number;
  /** 父级（树/筛选）操作失败的提示；与列表自身错误分开呈现。 */
  actionError?: string | null;
  onEdit: (question: QuestionSummary) => void;
  onDeleted: () => void;
  onAdd: () => void;
}) {
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { state, reload } = useAsyncResource(
    (signal) => listQuestions(queryOf(filters, offset), signal),
    JSON.stringify({ filters, offset, refreshToken }),
  );

  const total = state.phase === 'ready' ? state.data.total : 0;
  const pages = totalPagesOf(total, QUESTION_PAGE_SIZE);
  const current = pageOf(offset, QUESTION_PAGE_SIZE);

  function gotoPage(page: number) {
    onOffsetChange(offsetOf(page, QUESTION_PAGE_SIZE));
  }

  /**
   * 归档删除：二次确认（说明后果）后带当前修订提交。
   * 409（其它入口已改题）→ 刷新列表并提示重试；其它失败原样显示，列表不变。
   */
  async function remove(question: QuestionSummary) {
    const confirmed = window.confirm(
      `归档删除题目「${question.stemPreview}」？\n` +
        '归档后该题不再出现在列表中；来源与历史修订保留，可由服务端追溯。',
    );
    if (!confirmed) return;
    setDeleteBusyId(question.questionId);
    setDeleteError(null);
    try {
      await deleteQuestion(question.questionId, question.revision);
      onDeleted();
    } catch (cause) {
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        setDeleteError(
          `删除未执行（${apiError.code}）：${apiError.message} 列表已刷新为服务端最新修订，可重试。`,
        );
        reload();
      } else if (apiError.status === 404) {
        setDeleteError(`删除未执行（${apiError.code}）：${apiError.message} 列表已刷新。`);
        reload();
      } else {
        setDeleteError(
          `删除失败（${apiError.code}）：${apiError.message} 没有删除任何数据，可直接重试。`,
        );
      }
    } finally {
      setDeleteBusyId(null);
    }
  }

  return (
    <section className="space-card qb-list-card" aria-label="题目列表">
      <div className="qb-card-head">
        <h2>题目列表</h2>
      </div>

      {actionError && (
        <div className="space-banner error" role="alert">
          {actionError}
        </div>
      )}
      {deleteError && (
        <div className="space-banner error" role="alert" data-testid="qb-question-delete-error">
          {deleteError}
        </div>
      )}

      {state.phase === 'loading' && (
        <div className="qb-list" aria-busy="true" aria-label="正在读取题目">
          <div className="space-skeleton" style={{ height: 76 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 76 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 76 }} aria-hidden />
        </div>
      )}

      {state.phase === 'failed' && (
        <ErrorNotice label="题目列表读取失败" error={state.error} onRetry={reload} />
      )}

      {state.phase === 'ready' && (
        <>
          {state.data.questions.length > 0 && (
            <ul className="qb-list qb-question-list">
              {state.data.questions.map((question) => (
                <li className="qb-question-row" key={question.questionId}>
                  <div className="qb-question-stem">
                    {question.stemPreview.trim() ? (
                      <ContentMarkdown text={question.stemPreview} />
                    ) : (
                      <span className="qb-warn-text">题干（服务端未返回预览）</span>
                    )}
                  </div>
                  <div className="qb-question-side">
                    <span className={difficultyBadgeClass(question.difficulty)}>
                      {difficultyLabel(question.difficulty)}
                    </span>
                    {question.answerState === 'not_provided' && (
                      <span className="space-chip amber">答案缺失</span>
                    )}
                    <div className="qb-row-actions">
                      <button
                        className="qb-text-action"
                        type="button"
                        onClick={() => onEdit(question)}
                      >
                        <Pencil size={13} aria-hidden />
                        编辑
                      </button>
                      <button
                        className="qb-text-action danger"
                        type="button"
                        aria-label={`删除题目 ${question.stemPreview}`}
                        disabled={deleteBusyId === question.questionId}
                        onClick={() => void remove(question)}
                      >
                        <Trash2 size={13} aria-hidden />
                        {deleteBusyId === question.questionId ? '删除中…' : '删除'}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {state.data.questions.length === 0 && (
            <div className="space-empty">
              <strong>没有符合条件的题目</strong>
              <span>
                调整知识点、难度或关键词；也可以从教材课后习题或文件导入，经人工校对后入库。
              </span>
              <div className="qb-actions">
                <button className="space-button primary" type="button" onClick={onAdd}>
                  <Plus size={14} aria-hidden />
                  添加题目
                </button>
              </div>
            </div>
          )}

          <div className="qb-list-foot">
            <span className="qb-total">共 {total} 条记录</span>
            {pages > 1 && (
              <nav className="qb-pager" aria-label="题目列表分页">
                <button
                  className="qb-page"
                  type="button"
                  disabled={current <= 1}
                  onClick={() => gotoPage(current - 1)}
                >
                  上一页
                </button>
                {pageWindow(current, pages).map((item, index) =>
                  item === 'gap' ? (
                    <span className="qb-page-gap" key={`gap-${index}`} aria-hidden>
                      …
                    </span>
                  ) : (
                    <button
                      key={item}
                      className={item === current ? 'qb-page current' : 'qb-page'}
                      type="button"
                      aria-current={item === current ? 'page' : undefined}
                      onClick={() => gotoPage(item)}
                    >
                      {item}
                    </button>
                  ),
                )}
                <button
                  className="qb-page"
                  type="button"
                  disabled={current >= pages}
                  onClick={() => gotoPage(current + 1)}
                >
                  下一页
                </button>
              </nav>
            )}
          </div>
        </>
      )}
    </section>
  );
}
