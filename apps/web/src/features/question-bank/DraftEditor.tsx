'use client';

/**
 * 草稿编辑表单（校对页右侧）：
 * - 保存 / 标记已校对 / 标记排除 / 标记原文未提供答案，全部走 `PATCH /question-drafts/{id}`
 *   并如实显示服务端返回的 `reviewState`（编辑已校对草稿会回到待校对，界面不乐观隐藏）；
 * - 拆分按字符偏移走 `POST /question-imports/{id}/split?draftId=`；
 * - 409 冲突保留用户输入，展示服务端最新内容供比较，给出「用我的修改重试」与「放弃我的修改」；
 * - F10-QB：知识点关联可查看与更新（整表替换；未改动时不发送、服务端沿用旧关联），
 *   跨学科编辑先说明服务端会 422 要求显式替换/清空，并把字段级错误定位到关联行；
 *   历史标签（旧字段 knowledgeTags）与正式关联分开呈现。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DraftReviewState, DraftView, QuestionImportDetail } from '@/contracts/question-bank';
import {
  getQuestionAsset,
  patchQuestionDraft,
  splitQuestionDraft,
} from '@/services/question-bank-api';
import { ContentForm, type QuestionFormValue } from './ContentForm';
import {
  contentErrors,
  contentFromDraft,
  confirmBlockers,
  metadataErrors,
  metadataFromDraft,
} from './draft-form';
import { asApiError } from './hooks';
import {
  linksToInputs,
  locateLinkIssues,
  readKnowledgeLinks,
  subjectChangeState,
  type KnowledgeLinkView,
  type LinkIssueLocation,
} from './knowledge-links';
import { EXTRACTION_METHOD_LABEL, AI_CANDIDATE_CHIP, reviewStateLabel } from './labels';
import { KnowledgeLinksPanel } from './KnowledgeLinksPanel';
import { QuestionPreview } from './QuestionPreview';
import type { TaxonomyIndex } from './taxonomy';

export function formValueOfDraft(draft: DraftView): QuestionFormValue {
  return { content: contentFromDraft(draft), metadata: metadataFromDraft(draft) };
}

/** 服务端草稿的正式关联（字段缺失按「未提供」→ 空列表展示，不猜造）。 */
function serverLinksOf(draft: DraftView): KnowledgeLinkView[] {
  const read = readKnowledgeLinks(draft as unknown as Record<string, unknown>);
  return read.status === 'provided' ? read.links : [];
}

const NO_LINK_ISSUES: LinkIssueLocation = { byIndex: new Map(), general: [] };

const REVIEW_ACTIONS: { state: DraftReviewState; label: string }[] = [
  { state: 'reviewed', label: '标记已校对' },
  { state: 'needs_review', label: '退回待校对' },
  { state: 'excluded', label: '标记排除' },
];

type DraftEditorProps = {
  importId: string;
  draft: DraftView;
  taxonomy: TaxonomyIndex;
  onDraftUpdated: (draft: DraftView) => void;
  onDetailReplaced: (detail: QuestionImportDetail) => void;
  onReloadDraft: (draftId: string, isCurrent?: () => boolean) => Promise<DraftView | null>;
};

export function DraftEditor(props: DraftEditorProps) {
  return <DraftEditorSession key={`${props.importId}|${props.draft.draftId}`} {...props} />;
}

function DraftEditorSession({
  importId,
  draft,
  taxonomy,
  onDraftUpdated,
  onDetailReplaced,
  onReloadDraft,
}: DraftEditorProps) {
  const [value, setValue] = useState<QuestionFormValue>(() => formValueOfDraft(draft));
  const [dirty, setDirtyState] = useState(false);
  const dirtyRef = useRef(false);
  const setDirty = (next: boolean) => { dirtyRef.current = next; setDirtyState(next); };
  const [linkDraft, setLinkDraft] = useState<KnowledgeLinkView[]>(() => serverLinksOf(draft));
  const [linksTouched, setLinksTouchedState] = useState(false);
  const linksTouchedRef = useRef(false);
  const setLinksTouched = (next: boolean) => { linksTouchedRef.current = next; setLinksTouchedState(next); };
  const [linkIssues, setLinkIssues] = useState<LinkIssueLocation>(NO_LINK_ISSUES);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<DraftView | null>(null);
  const [charOffset, setCharOffset] = useState('');
  const [splitError, setSplitError] = useState<string | null>(null);
  const mountedRef = useRef(false);
  const writeEpochRef = useRef(0);
  const writingRef = useRef(false);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      writeEpochRef.current += 1;
    };
  }, []);
  const active = (token: number) => mountedRef.current && token === writeEpochRef.current;
  const loadAsset = useCallback(
    (assetId: string, signal: AbortSignal) =>
      getQuestionAsset('draft', draft.draftId, assetId, signal),
    [draft.draftId],
  );

  // 服务端内容更新且本地无未保存编辑时同步表单；有编辑时保留用户输入（冲突路径另行提示）。
  useEffect(() => {
    if (!dirtyRef.current) setValue(formValueOfDraft(draft));
  }, [draft, dirty]);

  // 关联同理：用户没动过关联才跟随服务端（不覆盖用户正在编辑的关联）
  useEffect(() => {
    if (!linksTouchedRef.current) {
      setLinkDraft(serverLinksOf(draft));
      setLinkIssues(NO_LINK_ISSUES);
    }
  }, [draft, linksTouched]);

  const linksRead = useMemo(
    () => readKnowledgeLinks(draft as unknown as Record<string, unknown>),
    [draft],
  );
  const subjectChange = useMemo(
    () =>
      subjectChangeState(
        draft.metadata.subjectId,
        value.metadata.subjectId,
        linksRead.status === 'provided' ? linksRead.links : linkDraft,
      ),
    [draft, value, linksRead, linkDraft],
  );

  function update(next: QuestionFormValue) {
    setValue(next);
    setDirty(true);
  }

  function patchLinks(next: KnowledgeLinkView[]) {
    setLinkDraft(next);
    setLinksTouched(true);
    setLinkIssues(NO_LINK_ISSUES);
  }

  function expectedRevision(): number {
    return snapshot ? snapshot.revision : draft.revision;
  }

  async function handleWriteError(cause: unknown, token: number) {
    if (!active(token)) return;
    const apiError = asApiError(cause);
    if (apiError.status === 409) {
      setConflict(
        `内容已在别处被修改（${apiError.code}）：${apiError.message} 你的编辑已保留，下面是服务端最新内容。`,
      );
      const latest = await onReloadDraft(draft.draftId, () => active(token));
      if (!active(token)) return;
      setSnapshot(latest);
      return;
    }
    if (apiError.status === 422 || apiError.status === 404) {
      // 用**服务端关联**定位（未改动时行序与展示一致），消息里的知识点 id 也逐字匹配
      const located = locateLinkIssues(cause, linkDraft);
      if (located.byIndex.size > 0 || located.general.length > 0) {
        setLinkIssues(located);
        setError(
          `知识点关联校验失败（${apiError.code}）：${apiError.message} 具体条目见下方「知识点关联」区块，修正后可直接重试。`,
        );
        return;
      }
    }
    setError(`保存失败（${apiError.code}）：${apiError.message}`);
  }

  async function persist(options: {
    reviewState?: DraftReviewState;
    missingAnswerAcknowledged?: boolean;
  }) {
    if (writingRef.current) return;
    const issues = [...contentErrors(value.content), ...metadataErrors(value.metadata)];
    if (issues.length > 0) {
      setError(issues.join(' '));
      return;
    }
    const token = ++writeEpochRef.current;
    writingRef.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    setLinkIssues(NO_LINK_ISSUES);
    try {
      const updated = await patchQuestionDraft(draft.draftId, {
        expectedRevision: expectedRevision(),
        content: value.content,
        metadata: value.metadata,
        reviewState: options.reviewState ?? null,
        missingAnswerAcknowledged: options.missingAnswerAcknowledged ?? null,
        // 只有用户显式改动过才整表替换；未改动时缺省 → 服务端不动旧关联（不静默清空）
        knowledgeLinks: linksTouched ? linksToInputs(linkDraft) : undefined,
      });
      if (!active(token)) return;
      onDraftUpdated(updated);
      setValue(formValueOfDraft(updated));
      setDirty(false);
      setSnapshot(null);
      setConflict(null);
      setLinksTouched(false);
      setLinkDraft(serverLinksOf(updated));
      setNotice(
        options.reviewState
          ? `已保存；服务端当前校对状态：${reviewStateLabel(updated.reviewState)}。`
          : options.missingAnswerAcknowledged
            ? '已标记「原文未提供答案」；入库前无需再补齐答案。'
            : `已保存；服务端当前校对状态：${reviewStateLabel(updated.reviewState)}。`,
      );
    } catch (cause) {
      await handleWriteError(cause, token);
    } finally {
      if (active(token)) {
        writingRef.current = false;
        setBusy(false);
      }
    }
  }

  async function split() {
    if (writingRef.current) return;
    const offset = Number(charOffset);
    if (!Number.isInteger(offset) || offset < 1) {
      setSplitError('拆分位置需要是大于 0 的整数（以字符偏移计）。');
      return;
    }
    const token = ++writeEpochRef.current;
    writingRef.current = true;
    setBusy(true);
    setSplitError(null);
    setNotice(null);
    try {
      const detail = await splitQuestionDraft(importId, draft.draftId, {
        expectedRevision: expectedRevision(),
        charOffset: offset,
      });
      if (!active(token)) return;
      onDetailReplaced(detail);
      setCharOffset('');
      setDirty(false);
      setSnapshot(null);
      setConflict(null);
      setNotice('已按字符偏移拆分，原草稿标记为排除，请在左侧选择新草稿继续校对。');
    } catch (cause) {
      if (!active(token)) return;
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        setConflict(
          `内容已在别处被修改（${apiError.code}）：${apiError.message} 拆分位置已保留，下面是服务端最新内容。`,
        );
        const latest = await onReloadDraft(draft.draftId, () => active(token));
        if (!active(token)) return;
        setSnapshot(latest);
      } else {
        setSplitError(`拆分失败（${apiError.code}）：${apiError.message}`);
      }
    } finally {
      if (active(token)) {
        writingRef.current = false;
        setBusy(false);
      }
    }
  }

  const blockers = confirmBlockers(value.content, draft.missingAnswerAcknowledged);

  return (
    <section className="qb-editor" aria-label="草稿编辑">
      <header className="qb-editor-head">
        <h2>草稿编辑</h2>
        <span
          className={
            draft.reviewState === 'reviewed'
              ? 'space-chip green'
              : draft.reviewState === 'excluded'
                ? 'space-chip'
                : 'space-chip amber'
          }
          data-testid="qb-review-state"
        >
          {reviewStateLabel(draft.reviewState)}
        </span>
        <span className="space-chip">{EXTRACTION_METHOD_LABEL[draft.extractionMethod]}</span>
        {draft.extractionMethod === 'ai' && (
          <span className="space-chip amber" data-testid="qb-draft-ai-source">
            {AI_CANDIDATE_CHIP}
          </span>
        )}
        <span className="space-chip">修订 r{draft.revision}</span>
        {draft.missingAnswerAcknowledged && (
          <span className="space-chip amber">原文未提供答案</span>
        )}
        {dirty && <span className="space-chip blue">有未保存的编辑</span>}
      </header>

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
      {dirty && !conflict && (
        <p className="space-banner info" role="status">
          有未保存的编辑；保存后请以服务端返回的校对状态为准。
        </p>
      )}

      {conflict && (
        <div className="space-banner error" role="alert">
          {conflict}
          <div className="qb-snapshot">
            <p className="qb-hint">服务端最新内容：</p>
            {snapshot ? (
              <>
                <p className="qb-snapshot-line">修订 r{snapshot.revision}</p>
                <p className="qb-block-text">{snapshot.content.stemMarkdown}</p>
                <p className="qb-hint">
                  校对状态：{reviewStateLabel(snapshot.reviewState)} · 选项{' '}
                  {snapshot.content.options.length} 个 · 答案{' '}
                  {snapshot.content.answer?.choiceKeys.join('、') ||
                    (snapshot.content.answer?.accepted === true
                      ? '对'
                      : snapshot.content.answer?.accepted === false
                        ? '错'
                        : snapshot.content.answer?.textMarkdown || '缺失')}
                </p>
              </>
            ) : (
              <p className="qb-hint">
                服务端最新内容读取失败：可先「用我的修改重试」，或稍后刷新页面。
              </p>
            )}
          </div>
          <div className="qb-actions">
            <button
              className="space-button primary"
              onClick={() => void persist({})}
              disabled={busy}
            >
              用我的修改重试
            </button>
            <button
              className="space-button"
              disabled={busy}
              onClick={() => {
                const latest = snapshot ?? draft;
                setValue(formValueOfDraft(latest));
                setDirty(false);
                setSnapshot(null);
                setConflict(null);
                setLinkDraft(serverLinksOf(latest));
                setLinksTouched(false);
                setLinkIssues(NO_LINK_ISSUES);
                setNotice('已放弃我的修改，表单为服务端最新内容。');
              }}
            >
              放弃我的修改
            </button>
          </div>
        </div>
      )}

      <section className="qb-subpanel" aria-label="草稿内容预览">
        <h3>内容预览</h3>
        <QuestionPreview
          content={value.content}
          loadAsset={loadAsset}
          assetScope={`${draft.draftId}|${draft.revision}`}
        />
      </section>

      <ContentForm
        value={value}
        onChange={update}
        disabled={busy}
        taxonomy={taxonomy}
        idPrefix="qb-draft"
      />

      <KnowledgeLinksPanel
        read={linksRead}
        links={linkDraft}
        touched={linksTouched}
        editable
        disabled={busy}
        subjectId={value.metadata.subjectId}
        originalSubjectId={draft.metadata.subjectId}
        subjectChange={subjectChange}
        issues={linkIssues}
        legacyTags={value.metadata.knowledgeTags}
        idPrefix="qb-draft-links"
        newLinkSource="human"
        onAdd={(link) => patchLinks([...linkDraft, link])}
        onRemove={(index) => patchLinks(linkDraft.filter((_, itemIndex) => itemIndex !== index))}
        onRoleChange={(index, role) =>
          patchLinks(
            linkDraft.map((item, itemIndex) => (itemIndex === index ? { ...item, role } : item)),
          )
        }
        onClear={() => patchLinks([])}
        onReset={() => {
          setLinkDraft(linksRead.status === 'provided' ? linksRead.links : []);
          setLinksTouched(false);
          setLinkIssues(NO_LINK_ISSUES);
        }}
      />

      {blockers.length > 0 && (
        <ul className="qb-warning-list" role="status">
          {blockers.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}

      <div className="qb-actions">
        <button className="space-button primary" onClick={() => void persist({})} disabled={busy}>
          {busy ? '保存中…' : '保存修改'}
        </button>
        {REVIEW_ACTIONS.map((action) => (
          <button
            key={action.state}
            className="space-button"
            disabled={busy}
            onClick={() => void persist({ reviewState: action.state })}
          >
            {action.label}
          </button>
        ))}
        <button
          className="space-button"
          disabled={busy}
          onClick={() => void persist({ missingAnswerAcknowledged: true })}
        >
          标记原文未提供答案
        </button>
      </div>

      <fieldset className="qb-subpanel">
        <legend>拆分草稿</legend>
        <p className="qb-hint">
          按字符偏移把当前草稿拆成两道：偏移必须落在该草稿的原文区间内；拆分后原草稿会被排除。
        </p>
        <div className="qb-actions">
          <label className="qb-field" htmlFor="qb-split-offset">
            拆分位置（字符偏移）
            <input
              id="qb-split-offset"
              type="number"
              min={1}
              value={charOffset}
              disabled={busy}
              onChange={(event) => setCharOffset(event.target.value)}
            />
          </label>
          <button className="space-button" onClick={() => void split()} disabled={busy}>
            拆分
          </button>
        </div>
        {splitError && (
          <p className="space-banner error" role="alert">
            {splitError}
          </p>
        )}
      </fieldset>
    </section>
  );
}
