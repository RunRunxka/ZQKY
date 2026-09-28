'use client';

/**
 * 已入库题目详情（抽屉）：全文 / 答案 / 解析 / 分类 / 来源，支持带乐观锁的编辑与
 * 归档删除（二次确认）。409 冲突保留用户输入，展示服务端最新内容并给出两个明确动作。
 */

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Modal } from '@/components/ui/Modal';
import type { QuestionDetail } from '@/contracts/question-bank';
import { ApiError } from '@/services/api-client';
import { deleteQuestion, getQuestion, patchQuestion } from '@/services/question-bank-api';
import { ContentForm, type QuestionFormValue } from './ContentForm';
import { contentErrors, copyContent, copyMetadata, metadataErrors } from './draft-form';
import { asApiError, errorText } from './hooks';
import { ANSWER_STATE_LABEL, difficultyLabel, formatDateTime } from './labels';
import { QuestionPreview } from './QuestionPreview';
import type { TaxonomyIndex } from './taxonomy';

type LoadState =
  | { phase: 'loading' }
  | { phase: 'ready'; detail: QuestionDetail }
  | { phase: 'failed'; error: ApiError };

function formValueOf(detail: QuestionDetail): QuestionFormValue {
  return {
    content: copyContent(detail.content),
    metadata: copyMetadata(detail.metadata),
  };
}

export function QuestionDetailPanel({
  questionId,
  taxonomy,
  onClose,
  onChanged,
}: {
  questionId: string;
  taxonomy: TaxonomyIndex;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [state, setState] = useState<LoadState>({ phase: 'loading' });
  const [value, setValue] = useState<QuestionFormValue | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteArmed, setDeleteArmed] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setState({ phase: 'loading' });
      try {
        const detail = await getQuestion(questionId, signal);
        setState({ phase: 'ready', detail });
        return detail;
      } catch (cause) {
        setState({ phase: 'failed', error: asApiError(cause) });
        return null;
      }
    },
    [questionId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then((detail) => {
      if (detail) setValue(formValueOf(detail));
    });
    return () => controller.abort();
  }, [load]);

  async function save() {
    if (state.phase !== 'ready' || !value) return;
    const issues = [...contentErrors(value.content), ...metadataErrors(value.metadata)];
    if (issues.length > 0) {
      setError(issues.join(' '));
      return;
    }
    setBusy(true);
    setError(null);
    setConflict(null);
    setNotice(null);
    try {
      const updated = await patchQuestion(questionId, {
        expectedRevision: state.detail.revision,
        content: value.content,
        metadata: value.metadata,
      });
      setState({ phase: 'ready', detail: updated });
      setValue(formValueOf(updated));
      setEditing(false);
      setNotice(`已保存，当前修订 r${updated.revision}。`);
      onChanged();
    } catch (cause) {
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        setConflict(
          `内容已在别处被修改（${apiError.code}）：${apiError.message} 你的修改已保留，下面是服务端最新内容。`,
        );
        const latest = await load();
        if (latest) onChanged();
      } else {
        setError(errorText(cause));
      }
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (state.phase !== 'ready') return;
    setBusy(true);
    setError(null);
    try {
      await deleteQuestion(questionId, state.detail.revision);
      onChanged();
      onClose();
    } catch (cause) {
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        setConflict(
          `内容已在别处被修改（${apiError.code}）：${apiError.message} 已重新读取服务端最新内容，请确认后重试。`,
        );
        await load();
      } else {
        setError(errorText(cause));
      }
      setDeleteArmed(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={editing ? '编辑题目' : '题目详情'} onClose={onClose}>
      <div className="qb-panel qb-detail">
        {state.phase === 'loading' && (
          <div className="space-skeleton" style={{ height: 160 }} aria-hidden />
        )}

        {state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            题目读取失败（{state.error.code}）：{state.error.message}
            <div className="qb-actions">
              <button className="space-button" onClick={() => void load()}>
                重试
              </button>
            </div>
          </div>
        )}

        {state.phase === 'ready' && (
          <>
            <div className="space-meta-row">
              <span className="space-chip">{state.detail.questionId}</span>
              <span className="space-chip blue">
                {state.detail.status === 'confirmed' ? '已入库' : '已归档'}
              </span>
              <span
                className={
                  state.detail.answerState === 'not_provided'
                    ? 'space-chip amber'
                    : 'space-chip green'
                }
              >
                {ANSWER_STATE_LABEL[state.detail.answerState]}
              </span>
              <span className="space-chip">
                难度：{difficultyLabel(state.detail.metadata.difficulty)}
              </span>
              <span className="space-chip">修订 r{state.detail.revision}</span>
            </div>

            {error && (
              <p className="space-banner error" role="alert">
                {error}
              </p>
            )}
            {notice && (
              <p className="space-banner info" role="status">
                {notice}
              </p>
            )}

            {conflict && (
              <div className="space-banner error" role="alert">
                {conflict}
                {editing && value && (
                  <>
                    <p className="qb-hint">服务端最新内容：</p>
                    <QuestionPreview content={state.detail.content} compact />
                    <div className="qb-actions">
                      <button
                        className="space-button primary"
                        onClick={() => void save()}
                        disabled={busy}
                      >
                        用我的修改重试
                      </button>
                      <button
                        className="space-button"
                        disabled={busy}
                        onClick={() => {
                          setValue(formValueOf(state.detail));
                          setConflict(null);
                          setNotice('已放弃我的修改，表单为服务端最新内容。');
                        }}
                      >
                        放弃我的修改
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {editing && value ? (
              <>
                <ContentForm
                  value={value}
                  onChange={setValue}
                  disabled={busy}
                  taxonomy={taxonomy}
                  idPrefix="qb-question-edit"
                />
                <div className="qb-actions">
                  <button
                    className="space-button primary"
                    onClick={() => void save()}
                    disabled={busy}
                  >
                    {busy ? '保存中…' : '保存修改'}
                  </button>
                  <button
                    className="space-button"
                    disabled={busy}
                    onClick={() => {
                      setEditing(false);
                      setValue(formValueOf(state.detail));
                      setConflict(null);
                    }}
                  >
                    取消编辑
                  </button>
                </div>
              </>
            ) : (
              <>
                <QuestionPreview content={state.detail.content} />
                <dl className="qb-meta-list">
                  <div>
                    <dt>分类</dt>
                    <dd>
                      学段 {taxonomy.stageLabel(state.detail.metadata.stageId) || '—'} · 年级{' '}
                      {taxonomy.gradeLabel(state.detail.metadata.gradeId) || '—'} · 学科{' '}
                      {taxonomy.subjectLabel(state.detail.metadata.subjectId) || '—'} · 版本{' '}
                      {taxonomy.editionLabel(state.detail.metadata.editionId) || '—'}
                    </dd>
                  </div>
                  <div>
                    <dt>知识点</dt>
                    <dd>
                      {state.detail.metadata.knowledgeTags.length > 0
                        ? state.detail.metadata.knowledgeTags.join('、')
                        : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt>来源</dt>
                    <dd>
                      {state.detail.sourceImportId ? (
                        <>
                          导入批次{' '}
                          <Link
                            className="qb-link"
                            href={`/question-bank/imports/${state.detail.sourceImportId}`}
                          >
                            {state.detail.sourceImportId}
                          </Link>
                          ；
                        </>
                      ) : (
                        '无导入批次；'
                      )}
                      {state.detail.sources.length > 0
                        ? state.detail.sources
                            .map(
                              (span) => `${span.blockId}（字符 ${span.charStart}–${span.charEnd}）`,
                            )
                            .join('；')
                        : '无原文区间'}
                    </dd>
                  </div>
                  <div>
                    <dt>入库时间</dt>
                    <dd>{formatDateTime(state.detail.confirmedAt)}</dd>
                  </div>
                </dl>
                <div className="qb-actions">
                  <button
                    className="space-button primary"
                    onClick={() => setEditing(true)}
                    disabled={busy}
                  >
                    编辑题目
                  </button>
                  {deleteArmed ? (
                    <>
                      <button
                        className="space-button danger"
                        onClick={() => void remove()}
                        disabled={busy}
                      >
                        确认归档删除
                      </button>
                      <button
                        className="space-button"
                        onClick={() => setDeleteArmed(false)}
                        disabled={busy}
                      >
                        取消
                      </button>
                    </>
                  ) : (
                    <button
                      className="space-button danger"
                      onClick={() => setDeleteArmed(true)}
                      disabled={busy}
                    >
                      归档删除…
                    </button>
                  )}
                </div>
                {deleteArmed && (
                  <p className="qb-hint" role="alert">
                    归档删除会让题目不再出现在列表中（逻辑失效），不会删除其他题目的来源记录。确认继续？
                  </p>
                )}
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
