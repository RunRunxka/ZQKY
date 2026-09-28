'use client';

/**
 * `/question-bank/imports/[importId]` 校对工作台：
 * 左原文（含未归属原文）/ 右草稿编辑，顶部草稿切换条；下方 AI 整理建议、
 * 合并、确认入库。所有写入都带乐观锁，冲突保留输入；失败与空态严格区分。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Sparkles } from 'lucide-react';
// 与既有内容页共享 space 设计语言（只读引入，不修改共享层）
import '@/components/layout/space.css';
import '@/features/question-bank/styles/question-bank.css';
import type {
  DraftView,
  DuplicateResolution,
  QuestionImportDetail,
} from '@/contracts/question-bank';
import { ApiError } from '@/services/api-client';
import {
  applyQuestionSuggestion,
  confirmQuestionImport,
  getQuestionImport,
  mergeQuestionDrafts,
  organizeQuestions,
  type OrganizeJobResult,
} from '@/services/question-bank-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { ConfirmPanel, type ConfirmState } from './ConfirmPanel';
import { DraftEditor } from './DraftEditor';
import { ErrorNotice } from './ErrorNotice';
import { asApiError, useAsyncResource } from './hooks';
import { importStateLabel, questionTypeLabel, reviewStateLabel } from './labels';
import { MergePanel } from './MergePanel';
import {
  fetchLocalOrganizerModel,
  organizerModelLabel,
  type LocalOrganizerModel,
} from './model-profile';
import { SourcePane } from './SourcePane';
import { SuggestionPanel } from './SuggestionPanel';
import { buildTaxonomyIndex } from './taxonomy';

type LoadState =
  | { phase: 'loading' }
  | { phase: 'ready'; detail: QuestionImportDetail }
  | { phase: 'failed'; error: ApiError };

/** 父级用服务端返回的草稿替换本地副本，并重算摘要计数（与后端视图同规则）。 */
export function withDraft(detail: QuestionImportDetail, draft: DraftView): QuestionImportDetail {
  const drafts = detail.drafts.map((item) => (item.draftId === draft.draftId ? draft : item));
  return {
    ...detail,
    drafts,
    draftCount: drafts.length,
    reviewedCount: drafts.filter((item) => item.reviewState === 'reviewed').length,
  };
}

/** 默认选中的草稿：保留仍存在的选择，否则优先第一个待校对草稿。 */
export function pickDraftId(detail: QuestionImportDetail, previous: string | null): string | null {
  if (previous && detail.drafts.some((draft) => draft.draftId === previous)) return previous;
  const first =
    detail.drafts.find((draft) => draft.reviewState === 'needs_review') ?? detail.drafts[0];
  return first ? first.draftId : null;
}

export function ReviewWorkspace({ importId }: { importId: string }) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ phase: 'loading' });
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [pageNotice, setPageNotice] = useState<{ kind: 'error' | 'info'; text: string } | null>(
    null,
  );

  const taxonomy = useAsyncResource((signal) => fetchTextbookTaxonomy(signal), 'qb-taxonomy');
  const index = useMemo(
    () => buildTaxonomyIndex(taxonomy.state.phase === 'ready' ? taxonomy.state.data : null),
    [taxonomy.state],
  );

  // AI 整理只用本机 Ollama 模型（契约 v1.1）：状态来自 /rag/status 的 summarization 分区
  const organizer = useAsyncResource(
    (signal) => fetchLocalOrganizerModel(signal),
    'qb-organizer-model',
  );
  const organizerModel: LocalOrganizerModel | null =
    organizer.state.phase === 'ready' ? organizer.state.data : null;
  const organizerReady = organizerModel?.available === true;

  const [mergeSelection, setMergeSelection] = useState<string[]>([]);
  const [mergeBusy, setMergeBusy] = useState(false);
  const [mergeError, setMergeError] = useState<string | null>(null);
  const [mergeNotice, setMergeNotice] = useState<string | null>(null);

  const [includeUnassigned, setIncludeUnassigned] = useState(false);
  const [organizeBusy, setOrganizeBusy] = useState(false);
  const [organizeError, setOrganizeError] = useState<string | null>(null);
  const [job, setJob] = useState<OrganizeJobResult | null>(null);
  const [busySuggestionId, setBusySuggestionId] = useState<string | null>(null);

  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmState, setConfirmState] = useState<ConfirmState>({ phase: 'idle' });
  const [resolutions, setResolutions] = useState<Record<string, DuplicateResolution>>({});
  const submissionIdRef = useRef<string | null>(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setState({ phase: 'loading' });
      try {
        const detail = await getQuestionImport(importId, signal);
        setState({ phase: 'ready', detail });
        // 与详情同一次更新里选定默认草稿：避免先渲染「未选择」再补选造成闪烁
        setSelectedDraftId((previous) => pickDraftId(detail, previous));
        return detail;
      } catch (cause) {
        setState({ phase: 'failed', error: asApiError(cause) });
        return null;
      }
    },
    [importId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const detail = state.phase === 'ready' ? state.detail : null;
  const drafts = detail?.drafts ?? [];
  const selectedDraft = drafts.find((draft) => draft.draftId === selectedDraftId) ?? null;

  useEffect(() => {
    if (!detail) return;
    if (selectedDraftId && detail.drafts.some((draft) => draft.draftId === selectedDraftId)) return;
    const first =
      detail.drafts.find((draft) => draft.reviewState === 'needs_review') ??
      detail.drafts[0] ??
      null;
    setSelectedDraftId(first ? first.draftId : null);
  }, [detail, selectedDraftId]);

  /** 静默刷新：保留当前视图，失败时明确提示而不是清空已显示的数据。 */
  const silentRefresh = useCallback(async () => {
    try {
      const next = await getQuestionImport(importId);
      setState({ phase: 'ready', detail: next });
      setSelectedDraftId((previous) => pickDraftId(next, previous));
      return next;
    } catch (cause) {
      const error = asApiError(cause);
      setPageNotice({
        kind: 'error',
        text: `刷新批次失败（${error.code}）：${error.message} 页面仍显示上一次成功读取的数据。`,
      });
      return null;
    }
  }, [importId]);

  const reloadDraft = useCallback(
    async (draftId: string): Promise<DraftView | null> => {
      const next = await silentRefresh();
      return next?.drafts.find((draft) => draft.draftId === draftId) ?? null;
    },
    [silentRefresh],
  );

  function replaceDraft(draft: DraftView) {
    setState((prev) =>
      prev.phase === 'ready' ? { phase: 'ready', detail: withDraft(prev.detail, draft) } : prev,
    );
  }

  async function mergeSelected() {
    if (mergeSelection.length < 2) {
      setMergeError('至少选择两道草稿才能合并。');
      return;
    }
    const revisions: Record<string, number> = {};
    for (const draftId of mergeSelection) {
      const draft = drafts.find((item) => item.draftId === draftId);
      if (!draft) {
        setMergeError('所选草稿已不在批次中，请刷新后重试。');
        return;
      }
      if (draft.reviewState === 'excluded') {
        setMergeError('已排除的草稿不能合并。');
        return;
      }
      revisions[draftId] = draft.revision;
    }
    setMergeBusy(true);
    setMergeError(null);
    setMergeNotice(null);
    try {
      const next = await mergeQuestionDrafts(importId, { expectedRevisions: revisions });
      setState({ phase: 'ready', detail: next });
      setMergeSelection([]);
      setMergeNotice('已合并：原草稿被排除，合并结果需重新校对后再入库。');
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409) {
        setMergeError(
          `合并冲突（${error.code}）：${error.message} 已保留你的选择，并重新读取服务端草稿供比较。`,
        );
        await silentRefresh();
      } else {
        setMergeError(`合并失败（${error.code}）：${error.message}`);
      }
    } finally {
      setMergeBusy(false);
    }
  }

  async function runOrganize() {
    if (!organizerModel || !organizerModel.available) {
      setOrganizeError(
        organizerModel?.reason ??
          '本机概括模型状态未知：请先确认本机 Ollama 可用后重新检查本机模型。',
      );
      return;
    }
    setOrganizeBusy(true);
    setOrganizeError(null);
    try {
      const result = await organizeQuestions(importId, {
        draftIds: drafts
          .filter((draft) => draft.reviewState !== 'excluded')
          .map((draft) => draft.draftId),
        includeUnassigned,
        // 本地模型名；空串 = 服务端默认本机模型（绝不传聊天 profileId）
        modelProfileId: organizerModel.modelName,
      });
      setJob(result);
    } catch (cause) {
      const error = asApiError(cause);
      setOrganizeError(
        `AI 整理失败（${error.code}）：${error.message} 未修改任何草稿，可稍后重试。`,
      );
    } finally {
      setOrganizeBusy(false);
    }
  }

  async function reviewSuggestion(suggestionId: string, accept: boolean) {
    const suggestion = job?.suggestions.find((item) => item.suggestionId === suggestionId);
    if (!suggestion) return;
    setBusySuggestionId(suggestionId);
    setOrganizeError(null);
    try {
      const updated = await applyQuestionSuggestion(suggestionId, {
        expectedDraftRevision: suggestion.baseDraftRevision,
        accept,
      });
      replaceDraft(updated);
      setSelectedDraftId(updated.draftId);
      setJob((prev) =>
        prev
          ? {
              ...prev,
              suggestions: prev.suggestions.map((item) =>
                item.suggestionId === suggestionId
                  ? { ...item, state: accept ? 'applied' : 'rejected' }
                  : item,
              ),
            }
          : prev,
      );
      setPageNotice({
        kind: 'info',
        text: accept
          ? `已应用 AI 建议：草稿回到${reviewStateLabel(updated.reviewState)}，请重新校对后再入库。`
          : '已忽略该 AI 建议，草稿内容未改变。',
      });
    } catch (cause) {
      const error = asApiError(cause);
      setOrganizeError(
        `${accept ? '应用' : '忽略'}建议失败（${error.code}）：${error.message} 草稿未被修改。`,
      );
    } finally {
      setBusySuggestionId(null);
    }
  }

  function ensureSubmissionId(): string {
    if (!submissionIdRef.current) {
      submissionIdRef.current = crypto.randomUUID();
      setSubmissionId(submissionIdRef.current);
    }
    return submissionIdRef.current;
  }

  async function confirm() {
    const reviewed = drafts.filter((draft) => draft.reviewState === 'reviewed');
    if (reviewed.length === 0) {
      setConfirmState({
        phase: 'failed',
        error: new ApiError('NO_REVIEWED_DRAFTS', '还没有已校对的草稿。', 0, false),
      });
      return;
    }
    setConfirmBusy(true);
    setPageNotice(null);
    try {
      const result = await confirmQuestionImport(importId, {
        submissionId: ensureSubmissionId(),
        importId,
        items: reviewed.map((draft) => ({
          draftId: draft.draftId,
          expectedDraftRevision: draft.revision,
        })),
        // 只提交仍然在本次 items 里的重复处理，避免陈旧条目污染幂等指纹
        duplicateResolutions: reviewed
          .map((draft) => resolutions[draft.draftId])
          .filter((item): item is DuplicateResolution => Boolean(item)),
      });
      setConfirmState({ phase: 'done', result });
      if (result.failures.length === 0) await silentRefresh();
    } catch (cause) {
      setConfirmState({ phase: 'failed', error: asApiError(cause) });
    } finally {
      setConfirmBusy(false);
    }
  }

  return (
    <div className="space-page question-bank-page">
      <header className="space-header">
        <Link className="space-back qb-back" href="/question-bank">
          <ArrowLeft size={14} aria-hidden />
          返回题库
        </Link>
        <h1>试题校对</h1>
        {detail ? (
          <p className="space-description">
            {detail.uploadedFileName} · {importStateLabel(detail.state)} · 草稿 {detail.draftCount}{' '}
            道 （已校对 {detail.reviewedCount}） · 未归属原文 {detail.unassignedCount} 块
          </p>
        ) : (
          <p className="space-description">
            导入文件的本地解析与规则拆题结果，需要人工校对后才能入库。
          </p>
        )}
      </header>

      <main className="space-content qb-review-content">
        {state.phase === 'loading' && (
          <div className="qb-review-loading" aria-busy="true" aria-label="正在读取导入批次">
            <div className="space-skeleton" style={{ height: 120 }} aria-hidden />
            <div className="space-skeleton" style={{ height: 320 }} aria-hidden />
          </div>
        )}

        {state.phase === 'failed' && (
          <ErrorNotice label="导入批次读取失败" error={state.error} onRetry={() => void load()} />
        )}

        {detail && (
          <>
            {pageNotice && (
              <p
                className={pageNotice.kind === 'error' ? 'space-banner error' : 'space-banner info'}
                role={pageNotice.kind === 'error' ? 'alert' : 'status'}
              >
                {pageNotice.text}
                <button className="space-button" onClick={() => setPageNotice(null)}>
                  关闭
                </button>
              </p>
            )}

            {detail.warnings.length > 0 && (
              <div className="space-banner">
                <strong>解析警告 {detail.warnings.length} 条</strong>
                <ul className="qb-warning-list">
                  {detail.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            {drafts.length === 0 ? (
              <div className="space-empty">
                <strong>该批次还没有草稿</strong>
                <span>
                  解析可能仍在进行或未拆出题目；可返回题库列表稍后重试，原文块仍保留在批次里。
                </span>
              </div>
            ) : (
              <>
                <nav className="qb-draft-strip" aria-label="草稿列表">
                  {drafts.map((draft, position) => (
                    <button
                      key={draft.draftId}
                      className={
                        draft.draftId === selectedDraftId ? 'qb-draft-tab current' : 'qb-draft-tab'
                      }
                      aria-current={draft.draftId === selectedDraftId}
                      onClick={() => setSelectedDraftId(draft.draftId)}
                    >
                      <span className="qb-draft-tab-title">
                        #{position + 1} {questionTypeLabel(draft.content.type)}
                      </span>
                      <span className="qb-draft-tab-stem">
                        {draft.content.stemMarkdown.slice(0, 40)}
                        {draft.content.stemMarkdown.length > 40 ? '…' : ''}
                      </span>
                      <span className="space-chip">{reviewStateLabel(draft.reviewState)}</span>
                    </button>
                  ))}
                </nav>

                <div className="qb-review-layout">
                  <SourcePane draft={selectedDraft} unassignedBlocks={detail.unassignedBlocks} />
                  {selectedDraft && (
                    <DraftEditor
                      key={selectedDraft.draftId}
                      importId={importId}
                      draft={selectedDraft}
                      taxonomy={index}
                      onDraftUpdated={replaceDraft}
                      onDetailReplaced={(next) => setState({ phase: 'ready', detail: next })}
                      onReloadDraft={reloadDraft}
                    />
                  )}
                </div>

                <section className="qb-tools" aria-label="整理与入库">
                  <div className="qb-subpanel">
                    <h2>AI 整理</h2>
                    <p className="qb-hint">
                      使用<strong>本机模型</strong>
                      把草稿整理成更规范的题目结构（教材与题目不外发云端）；
                      结果只是待校对建议，不会覆盖你的人工修改，也不会自动入库。
                    </p>
                    <p
                      className={organizerReady ? 'qb-hint' : 'qb-hint qb-warn-text'}
                      data-testid="qb-organizer-model"
                      role={organizerReady ? undefined : 'status'}
                    >
                      {organizerModelLabel(organizerModel)}
                    </p>
                    <label className="qb-check">
                      <input
                        type="checkbox"
                        checked={includeUnassigned}
                        disabled={organizeBusy}
                        onChange={(event) => setIncludeUnassigned(event.target.checked)}
                      />
                      同时把未归属原文交给模型参考
                    </label>
                    <div className="qb-actions">
                      <button
                        className="space-button primary"
                        disabled={organizeBusy || !organizerReady}
                        onClick={() => void runOrganize()}
                      >
                        <Sparkles size={14} aria-hidden />
                        {organizeBusy ? '整理中…' : 'AI 整理草稿'}
                      </button>
                      <button
                        className="space-button"
                        disabled={organizeBusy}
                        onClick={organizer.reload}
                      >
                        重新检查本机模型
                      </button>
                    </div>
                    {!organizerReady && (
                      <p className="qb-hint">
                        「AI 整理」在本机模型可用前不可点：先在本机 Ollama 拉取并运行默认模型 （如
                        qwen2.5:7b），再点「重新检查本机模型」。
                      </p>
                    )}
                    {organizeError && (
                      <p className="space-banner error" role="alert">
                        {organizeError}
                      </p>
                    )}
                  </div>

                  <SuggestionPanel
                    job={job}
                    suggestions={job?.suggestions ?? []}
                    drafts={drafts}
                    busySuggestionId={busySuggestionId}
                    onApply={(suggestion) => void reviewSuggestion(suggestion.suggestionId, true)}
                    onIgnore={(suggestion) => void reviewSuggestion(suggestion.suggestionId, false)}
                  />

                  <MergePanel
                    drafts={drafts}
                    selected={mergeSelection}
                    busy={mergeBusy}
                    error={mergeError}
                    notice={mergeNotice}
                    onToggle={(draftId) =>
                      setMergeSelection((prev) =>
                        prev.includes(draftId)
                          ? prev.filter((item) => item !== draftId)
                          : [...prev, draftId],
                      )
                    }
                    onMerge={() => void mergeSelected()}
                  />

                  <ConfirmPanel
                    drafts={drafts}
                    submissionId={submissionId}
                    state={confirmState}
                    busy={confirmBusy}
                    resolutions={resolutions}
                    onResolutionChange={(draftId, action) =>
                      setResolutions((prev) => ({
                        ...prev,
                        [draftId]: {
                          draftId,
                          action,
                          existingQuestionId:
                            action === 'link_existing'
                              ? (drafts.find((draft) => draft.draftId === draftId)
                                  ?.duplicateOfQuestionId ?? null)
                              : null,
                        },
                      }))
                    }
                    onConfirm={() => void confirm()}
                    onOpenLibrary={() => router.push('/question-bank#library')}
                    onReload={() => void silentRefresh()}
                  />
                </section>
              </>
            )}

            <p className="space-footnote">
              题目来自导入文件的本地解析与规则拆题；AI
              整理结果只是待校对建议，必须人工校对后才能入库。
            </p>
          </>
        )}
      </main>
    </div>
  );
}
