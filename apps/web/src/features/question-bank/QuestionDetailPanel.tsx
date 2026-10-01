'use client';

/**
 * 已入库题目详情（抽屉）：全文 / 答案 / 解析 / 分类 / 来源，支持带乐观锁的编辑与
 * 归档删除（二次确认）。409 冲突保留用户输入，展示服务端最新内容并给出两个明确动作。
 *
 * F10-QB 增量：
 * - **知识点关联**可查看与更新（整表替换；未改动时不发送、服务端沿用旧关联，界面明说）；
 * - 历史标签（旧字段 knowledgeTags）与正式关联**分开呈现**，不合并、不丢弃；
 * - 跨学科改题：先说明服务端会 422 要求显式替换/清空，并把 422 的字段级错误定位到关联行；
 * - 来源可追溯 AI 候选路径：`sourceImportId` 指向的批次里若有 `extractionMethod=ai` 草稿，
 *   如实说明「AI 候选经人工校对确认后入库」；批次读不到时明确「无法核对」，不猜造。
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Modal } from '@/components/ui/Modal';
import type { QuestionDetail } from '@/contracts/question-bank';
import { ApiError } from '@/services/api-client';
import {
  deleteQuestion,
  getQuestion,
  getQuestionImport,
  patchQuestion,
} from '@/services/question-bank-api';
import { ContentForm, type QuestionFormValue } from './ContentForm';
import { contentErrors, copyContent, copyMetadata, metadataErrors } from './draft-form';
import { asApiError, errorText, useAsyncResource } from './hooks';
import {
  linksToInputs,
  locateLinkIssues,
  readKnowledgeLinks,
  subjectChangeState,
  type KnowledgeLinkView,
  type LinkIssueLocation,
} from './knowledge-links';
import { ANSWER_STATE_LABEL, difficultyLabel, formatDateTime } from './labels';
import { KnowledgeLinksPanel } from './KnowledgeLinksPanel';
import { QuestionPreview } from './QuestionPreview';
import {
  aiSourceTraceOf,
  aiSourceTraceText,
  aiSourceTraceUnavailableText,
} from './source-trace';
import type { TaxonomyIndex } from './taxonomy';

type LoadState =
  | { phase: 'loading' }
  | { phase: 'ready'; detail: QuestionDetail }
  | { phase: 'failed'; error: ApiError };

const NO_LINK_ISSUES: LinkIssueLocation = { byIndex: new Map(), general: [] };

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
  const [linkDraft, setLinkDraft] = useState<KnowledgeLinkView[]>([]);
  const [linksTouched, setLinksTouched] = useState(false);
  const [linkIssues, setLinkIssues] = useState<LinkIssueLocation>(NO_LINK_ISSUES);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteArmed, setDeleteArmed] = useState(false);

  const detail = state.phase === 'ready' ? state.detail : null;
  const linksRead = useMemo(
    () => readKnowledgeLinks(detail as unknown as Record<string, unknown> | null),
    [detail],
  );
  const serverLinks = linksRead.status === 'provided' ? linksRead.links : [];

  /** 来源批次核对（AI 候选路径）：只有存在 sourceImportId 才请求；失败不猜造。 */
  const sourceImportId = detail?.sourceImportId ?? null;
  const trace = useAsyncResource(
    async (signal) => {
      if (!sourceImportId) return null;
      return aiSourceTraceOf(await getQuestionImport(sourceImportId, signal));
    },
    `qb-source-trace|${sourceImportId ?? ''}`,
  );

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setState({ phase: 'loading' });
      try {
        const next = await getQuestion(questionId, signal);
        setState({ phase: 'ready', detail: next });
        return next;
      } catch (cause) {
        setState({ phase: 'failed', error: asApiError(cause) });
        return null;
      }
    },
    [questionId],
  );

  const syncLinks = useCallback((next: QuestionDetail) => {
    const read = readKnowledgeLinks(next as unknown as Record<string, unknown>);
    setLinkDraft(read.status === 'provided' ? read.links : []);
    setLinksTouched(false);
    setLinkIssues(NO_LINK_ISSUES);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then((next) => {
      if (!next) return;
      setValue(formValueOf(next));
      syncLinks(next);
    });
    return () => controller.abort();
  }, [load, syncLinks]);

  const subjectChange = useMemo(
    () =>
      subjectChangeState(
        detail?.metadata.subjectId ?? '',
        value?.metadata.subjectId ?? '',
        linksRead.status === 'provided' ? linksRead.links : linkDraft,
      ),
    [detail, value, linksRead, linkDraft],
  );

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
    setLinkIssues(NO_LINK_ISSUES);
    try {
      const updated = await patchQuestion(questionId, {
        expectedRevision: state.detail.revision,
        content: value.content,
        metadata: value.metadata,
        // 只有用户显式改动过才整表替换；未改动时缺省 → 服务端沿用旧正式关联（不静默清空）
        knowledgeLinks: linksTouched ? linksToInputs(linkDraft) : undefined,
      });
      setState({ phase: 'ready', detail: updated });
      setValue(formValueOf(updated));
      syncLinks(updated);
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
        return;
      }
      if (apiError.status === 422 || apiError.status === 404) {
        // 字段级定位：knowledgeLinks[i] 或消息里的知识点 id；不能静默失败
        const located = locateLinkIssues(cause, linkDraft);
        setLinkIssues(located);
        if (located.byIndex.size > 0 || located.general.length > 0) {
          setError(
            `知识点关联校验失败（${apiError.code}）：${apiError.message} 具体条目见下方「知识点关联」区块；修改后可直接重试。`,
          );
          setEditing(true);
          return;
        }
        setError(
          `保存失败（${apiError.code}）：${apiError.message}${
            subjectChange.blocked
              ? ' 学科已修改且存在冲突的旧关联：请显式替换或清空关联后再保存。'
              : ''
          }`,
        );
        setEditing(true);
        return;
      }
      setError(errorText(cause));
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

  function patchLinks(next: KnowledgeLinkView[]) {
    setLinkDraft(next);
    setLinksTouched(true);
    setLinkIssues(NO_LINK_ISSUES);
  }

  function addLink(link: KnowledgeLinkView) {
    patchLinks([...linkDraft, link]);
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
                          syncLinks(state.detail);
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
                <KnowledgeLinksPanel
                  read={linksRead}
                  links={linkDraft}
                  touched={linksTouched}
                  editable
                  disabled={busy}
                  subjectId={value.metadata.subjectId}
                  originalSubjectId={state.detail.metadata.subjectId}
                  subjectChange={subjectChange}
                  issues={linkIssues}
                  legacyTags={value.metadata.knowledgeTags}
                  idPrefix="qb-question-links"
                  onAdd={addLink}
                  onRemove={(index) =>
                    patchLinks(linkDraft.filter((_, itemIndex) => itemIndex !== index))
                  }
                  onRoleChange={(index, role) =>
                    patchLinks(
                      linkDraft.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, role } : item,
                      ),
                    )
                  }
                  onClear={() => patchLinks([])}
                  onReset={() => {
                    setLinkDraft(serverLinks);
                    setLinksTouched(false);
                    setLinkIssues(NO_LINK_ISSUES);
                  }}
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
                      syncLinks(state.detail);
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
                    <dt>候选来源</dt>
                    <dd data-testid="qb-source-ai-trace">
                      {!sourceImportId
                        ? '没有导入批次可核对（本题不是由导入候选确认而来）。'
                        : trace.state.phase === 'loading'
                          ? '正在核对来源批次…'
                          : trace.state.phase === 'failed'
                            ? aiSourceTraceUnavailableText(
                                trace.state.error.code,
                                trace.state.error.message,
                              )
                            : trace.state.data
                              ? aiSourceTraceText(trace.state.data)
                              : '来源批次详情为空：无法核对候选来源。'}
                    </dd>
                  </div>
                  <div>
                    <dt>入库时间</dt>
                    <dd>{formatDateTime(state.detail.confirmedAt)}</dd>
                  </div>
                </dl>

                <KnowledgeLinksPanel
                  read={linksRead}
                  links={serverLinks}
                  touched={false}
                  editable={false}
                  subjectId={state.detail.metadata.subjectId}
                  originalSubjectId={state.detail.metadata.subjectId}
                  subjectChange={subjectChangeState(
                    state.detail.metadata.subjectId,
                    state.detail.metadata.subjectId,
                    serverLinks,
                  )}
                  issues={NO_LINK_ISSUES}
                  legacyTags={state.detail.metadata.knowledgeTags}
                  idPrefix="qb-question-links"
                />

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
