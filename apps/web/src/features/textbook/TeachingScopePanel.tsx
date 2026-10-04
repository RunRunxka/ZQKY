'use client';

/**
 * 任教范围面板（/knowledge-bases 页面顶部）：当前范围只读展示 + 显式修改。
 *
 * 边界（RAG-QUALITY v1.1 · F2-SCOPE-UI）：
 * - 打开页面只 `GET /teaching-settings`，不做任何写入；保存必须由用户点击触发；
 * - 保存前先 `POST /teaching-settings/scope-check` 预检，未通过不 PUT；
 *   未选书册在本地拦截，什么请求都不发（空 selection 服务端会 422）；
 * - PUT 带 `expectedRevision`（乐观锁）；409 REVISION_CONFLICT 保留用户选择并给「刷新后重试」；
 * - 切换年级/学科/版本会清空已选书册并重列候选，绝不把旧组合的选择带进新组合；
 * - 标签只用字典（`fetchTextbookTaxonomy`）标签；字典不可用时显示说明而不显示内部 id；
 * - 预检/保存失败一律保留输入可重试，不自动保存、不伪造成功。
 */

import { useState } from 'react';
import { BookOpenCheck, CheckCircle2, RefreshCw } from 'lucide-react';
import type {
  DocumentSummary,
  ScopeCheckView,
  TextbookSelection,
  TeachingSettingsView,
} from '@/contracts/textbook';
import {
  checkScope,
  getTeachingSettings,
  listDocuments,
  putTeachingSettings,
} from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import type { TaxonomyIndex } from './taxonomy';

interface ScopeDraft {
  gradeId: string;
  subjectId: string;
  editionId: string;
  documentIds: string[];
}

const EMPTY_DRAFT: ScopeDraft = { gradeId: '', subjectId: '', editionId: '', documentIds: [] };

function draftFrom(view: TeachingSettingsView | null): ScopeDraft {
  const selection = view?.selection ?? null;
  if (!selection) return { ...EMPTY_DRAFT };
  return {
    gradeId: selection.gradeId,
    subjectId: selection.subjectId,
    editionId: selection.editionId,
    documentIds: [...selection.documentIds],
  };
}

/** 候选只列当前修订非空、未删除的书册（与服务端范围解析的最小前提一致）。 */
function usableCandidates(documents: DocumentSummary[]): DocumentSummary[] {
  return documents.filter((item) => item.deletedAt === null && item.currentRevision !== null);
}

/** 当前修订可用且没有新修订在入库中 → 标记为可检索；真正的可检索性以服务端预检为准。 */
function isRetrievable(document: DocumentSummary): boolean {
  return Boolean(document.currentRevision && !document.pendingRevisionId && !document.deletedAt);
}

function documentChips(
  document: DocumentSummary,
  taxonomy: TaxonomyIndex,
): { text: string; tone: '' | 'green' | 'amber' }[] {
  const chips: { text: string; tone: '' | 'green' | 'amber' }[] = [];
  const grades = taxonomy.gradeLabels(document.gradeIds);
  if (grades) chips.push({ text: `年级：${grades}`, tone: '' });
  const edition = taxonomy.editionLabel(document.editionId);
  if (edition) chips.push({ text: `版本：${edition}`, tone: '' });
  if (document.currentRevision) {
    chips.push({ text: `字符 ${document.currentRevision.charCount}`, tone: '' });
    chips.push({ text: `块 ${document.currentRevision.chunkCount}`, tone: '' });
  }
  chips.push(
    isRetrievable(document)
      ? { text: '可检索', tone: 'green' }
      : { text: '有新修订待入库', tone: 'amber' },
  );
  return chips;
}

export function TeachingScopePanel({ taxonomy }: { taxonomy: TaxonomyIndex }) {
  const [settingsToken, setSettingsToken] = useState(0);
  const settings = useAsyncResource(
    (signal) => getTeachingSettings(signal),
    `teaching-settings|${settingsToken}`,
  );
  /** PUT 成功后直接采用服务端返回的视图，避免只靠二次 GET 才能显示新范围。 */
  const [savedView, setSavedView] = useState<TeachingSettingsView | null>(null);

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ScopeDraft>(EMPTY_DRAFT);
  const [candidateToken, setCandidateToken] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<ScopeCheckView | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const current: TeachingSettingsView | null =
    savedView ?? (settings.state.phase === 'ready' ? settings.state.data : null);
  const selection = current?.selection ?? null;
  const revision = current?.revision ?? 0;

  const comboComplete = Boolean(draft.gradeId && draft.subjectId && draft.editionId);
  const candidates = useAsyncResource(
    async (signal) => {
      if (!comboComplete) return [] as DocumentSummary[];
      const page = await listDocuments(
        {
          gradeId: draft.gradeId,
          subjectId: draft.subjectId,
          editionId: draft.editionId,
        },
        signal,
      );
      return usableCandidates(page.documents);
    },
    comboComplete ? `${draft.gradeId}|${draft.subjectId}|${draft.editionId}|${candidateToken}` : 'incomplete',
  );
  const candidateList = candidates.state.phase === 'ready' ? candidates.state.data : null;
  const candidateIds = new Set((candidateList ?? []).map((item) => item.documentId));
  const outsideSelection =
    candidateList === null
      ? []
      : draft.documentIds.filter((documentId) => !candidateIds.has(documentId));
  const titleOf = (documentId: string): string | null =>
    candidateList?.find((item) => item.documentId === documentId)?.title ?? null;

  function clearFeedback() {
    setActionError(null);
    setConflict(null);
    setCheckResult(null);
    setNotice(null);
  }

  function openEditor() {
    setDraft(draftFrom(current));
    clearFeedback();
    setEditing(true);
  }

  function closeEditor() {
    setEditing(false);
    clearFeedback();
  }

  function changeCombo(patch: Partial<Pick<ScopeDraft, 'gradeId' | 'subjectId' | 'editionId'>>) {
    // 新组合不继承旧书册：候选与已选必须成套，避免把不匹配的书册带进范围
    setDraft((previous) => ({ ...previous, ...patch, documentIds: [] }));
    clearFeedback();
  }

  function toggleDocument(documentId: string) {
    setDraft((previous) => ({
      ...previous,
      documentIds: previous.documentIds.includes(documentId)
        ? previous.documentIds.filter((item) => item !== documentId)
        : [...previous.documentIds, documentId],
    }));
    clearFeedback();
  }

  function dropOutsideSelection() {
    setDraft((previous) => ({
      ...previous,
      documentIds: previous.documentIds.filter((documentId) => candidateIds.has(documentId)),
    }));
    clearFeedback();
  }

  function resetDraft() {
    setDraft(draftFrom(current));
    clearFeedback();
  }

  /** 冲突后只重新读取（GET），绝不重放提交；用户的选择原样保留。 */
  function refreshAfterConflict() {
    setConflict(null);
    setActionError(null);
    setCheckResult(null);
    setSavedView(null);
    setSettingsToken((value) => value + 1);
    setCandidateToken((value) => value + 1);
    setNotice('已重新读取服务端任教范围：请核对后再次保存（你的选择仍保留）。');
  }

  async function save() {
    if (!current) {
      setActionError('尚未读到服务端的任教范围（revision 未知），不能提交修改；请先重试读取。');
      return;
    }
    if (!comboComplete) {
      setConflict(null);
      setNotice(null);
      setCheckResult(null);
      setActionError('请先选择年级、学科、版本，再确认书册。');
      return;
    }
    if (draft.documentIds.length === 0) {
      setConflict(null);
      setNotice(null);
      setCheckResult(null);
      setActionError('至少要确认一册书册，才能保存任教范围。');
      return;
    }

    const next: TextbookSelection = {
      gradeId: draft.gradeId,
      subjectId: draft.subjectId,
      editionId: draft.editionId,
      documentIds: draft.documentIds,
    };
    setBusy(true);
    setActionError(null);
    setConflict(null);
    setNotice(null);
    try {
      const check = await checkScope(next);
      setCheckResult(check);
      if (!check.scopeReady) return; // 预检未通过：不写服务端，原因如实显示
      const updated = await putTeachingSettings({ expectedRevision: revision, selection: next });
      if (updated) {
        setSavedView(updated);
      } else {
        setSavedView(null);
        setSettingsToken((value) => value + 1);
      }
      setCheckResult(null);
      setEditing(false);
      setCandidateToken((value) => value + 1);
      setNotice('任教范围已保存：只有确认过的书册会进入之后的检索，已有历史消息不受影响。');
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409 && error.code === 'REVISION_CONFLICT') {
        setConflict(`范围已在别处更新：${error.message}`);
      } else {
        setActionError(
          `保存失败（${error.code}）：${error.message} 你的选择已保留，可重新预检后重试。`,
        );
      }
    } finally {
      setBusy(false);
    }
  }

  const statusChip = (() => {
    if (!selection) return <span className="space-chip amber">尚未设置</span>;
    if (current?.scopeReady) return <span className="space-chip green">已就绪</span>;
    return <span className="space-chip amber">未就绪</span>;
  })();

  return (
    <section className="textbook-scope" aria-labelledby="textbook-scope-heading" data-motion-reveal>
      <div className="textbook-scope-head">
        <h2 id="textbook-scope-heading" className="textbook-scope-title">
          <BookOpenCheck size={16} aria-hidden />
          任教范围
        </h2>
        <div className="textbook-panel-actions textbook-scope-actions">
          {current && statusChip}
          {settings.state.phase === 'ready' && !editing && (
            <button className="space-button primary" onClick={openEditor}>
              修改范围
            </button>
          )}
          {editing && (
            <button className="space-button" onClick={closeEditor} disabled={busy}>
              收起
            </button>
          )}
        </div>
      </div>

      <p className="textbook-hint">
        只有这里确认过的书册才会进入检索范围；未确认的书册不会被检索到。修改只影响之后的新提问，
        不会改写已有历史消息里的引用。
      </p>

      {settings.state.phase === 'loading' && !savedView && (
        <div aria-hidden>
          <div className="space-skeleton" style={{ height: 56 }} />
        </div>
      )}

      {settings.state.phase === 'failed' && !savedView && (
        <div className="space-banner error" role="alert">
          任教范围读取失败（{settings.state.error.code}）：{settings.state.error.message}
          读取失败不等于没有范围；这里不显示猜测结果。
          <div className="textbook-panel-actions">
            <button className="space-button" onClick={settings.reload}>
              重试读取
            </button>
          </div>
        </div>
      )}

      {current && (
        <div className="textbook-scope-current">
          {selection ? (
            <>
              <div className="space-meta-row textbook-scope-tags">
                {taxonomy.ready ? (
                  <>
                    <span className="space-chip blue">
                      年级：{taxonomy.gradeLabel(selection.gradeId)}
                    </span>
                    <span className="space-chip blue">
                      学科：{taxonomy.subjectLabel(selection.subjectId)}
                    </span>
                    <span className="space-chip blue">
                      版本：{taxonomy.editionLabel(selection.editionId)}
                    </span>
                  </>
                ) : (
                  <span className="space-chip amber">字典未加载，年级/学科/版本名称暂不可用</span>
                )}
                <span className="space-chip green">
                  已确认 {selection.documentIds.length} 册进入检索
                </span>
              </div>
              {!taxonomy.ready && (
                <p className="textbook-hint">
                  字典读取失败时只显示数量、不显示内部标识；字典恢复后这里会显示可读的年级/学科/版本。
                </p>
              )}
            </>
          ) : (
            <p className="textbook-hint">
              尚未设置任教范围：点「修改范围」确认年级、学科、版本与至少一册书册后，教材问题才会进入检索。
            </p>
          )}

          {selection && !current.scopeReady && (
            <p className="space-banner textbook-scope-reason" role="status">
              范围未就绪：{current.scopeReason ?? '服务端未给出原因，请重新预检或联系维护者。'}
            </p>
          )}
        </div>
      )}

      {notice && (
        <div className="space-banner info" role="status">
          {notice}
        </div>
      )}

      {editing && (
        <div className="textbook-scope-editor">
          <h3 className="textbook-subhead">修改任教范围</h3>
          {!taxonomy.ready ? (
            <p className="textbook-hint">
              年级/学科/版本字典未加载，暂时无法改范围（这里不显示内部标识）；请先在上方重试读取字典。
            </p>
          ) : (
            <>
              <div className="space-toolbar textbook-filters">
                <label className="textbook-filter" htmlFor="textbook-scope-grade">
                  <span>年级</span>
                  <select
                    id="textbook-scope-grade"
                    className="space-select"
                    value={draft.gradeId}
                    disabled={busy}
                    onChange={(event) => changeCombo({ gradeId: event.target.value })}
                  >
                    <option value="">请选择年级</option>
                    {taxonomy.grades.map((grade) => (
                      <option key={grade.id} value={grade.id}>
                        {grade.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="textbook-filter" htmlFor="textbook-scope-subject">
                  <span>学科</span>
                  <select
                    id="textbook-scope-subject"
                    className="space-select"
                    value={draft.subjectId}
                    disabled={busy}
                    onChange={(event) => changeCombo({ subjectId: event.target.value })}
                  >
                    <option value="">请选择学科</option>
                    {taxonomy.subjects.map((subject) => (
                      <option key={subject.id} value={subject.id}>
                        {subject.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="textbook-filter" htmlFor="textbook-scope-edition">
                  <span>版本</span>
                  <select
                    id="textbook-scope-edition"
                    className="space-select"
                    value={draft.editionId}
                    disabled={busy}
                    onChange={(event) => changeCombo({ editionId: event.target.value })}
                  >
                    <option value="">请选择版本</option>
                    {taxonomy.editions.map((edition) => (
                      <option key={edition.id} value={edition.id}>
                        {edition.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {!comboComplete && (
                <p className="textbook-hint">
                  先选好年级、学科、版本，这里才会列出该组合下的书册；切换任一项会清空已选书册。
                </p>
              )}

              {comboComplete && candidates.state.phase === 'loading' && (
                <div aria-hidden>
                  {[0, 1].map((index) => (
                    <div className="space-skeleton" key={index} style={{ height: 64 }} />
                  ))}
                </div>
              )}

              {comboComplete && candidates.state.phase === 'failed' && (
                <div className="space-banner error" role="alert">
                  书册列表读取失败（{candidates.state.error.code}）：
                  {candidates.state.error.message}
                  当前没有可信的候选项，请重试；这里不会把失败当成「没有书册」。
                  <div className="textbook-panel-actions">
                    <button className="space-button" onClick={candidates.reload}>
                      重试列表
                    </button>
                  </div>
                </div>
              )}

              {comboComplete && candidates.state.phase === 'ready' && (
                <fieldset className="textbook-scope-documents">
                  <legend className="textbook-subhead">
                    确认进入检索范围的书册（已选 {draft.documentIds.length} 册）
                  </legend>
                  {candidates.state.data.length === 0 ? (
                    <p className="textbook-hint">
                      该组合下没有当前修订可用的书册：请先到「基础库 / 我的教材」导入并完成入库，再回来确认。
                    </p>
                  ) : (
                    <ul className="textbook-scope-list">
                      {candidates.state.data.map((document) => (
                        <li key={document.documentId}>
                          <label className="textbook-check textbook-scope-item" htmlFor={`textbook-scope-doc-${document.documentId}`}>
                            <input
                              id={`textbook-scope-doc-${document.documentId}`}
                              type="checkbox"
                              checked={draft.documentIds.includes(document.documentId)}
                              disabled={busy}
                              onChange={() => toggleDocument(document.documentId)}
                            />
                            <span className="textbook-scope-item-body">
                              <strong>{document.title}</strong>
                              <span className="space-meta-row">
                                {documentChips(document, taxonomy).map((chip) => (
                                  <span
                                    key={chip.text}
                                    className={`space-chip${chip.tone ? ` ${chip.tone}` : ''}`}
                                  >
                                    {chip.text}
                                  </span>
                                ))}
                              </span>
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                </fieldset>
              )}

              {outsideSelection.length > 0 && (
                <>
                  <p className="textbook-hint">
                    已确认的书册中有 {outsideSelection.length} 册不在当前候选列表（分类可能已变更）：
                    {outsideSelection
                      .map((documentId) => titleOf(documentId))
                      .filter((title): title is string => Boolean(title))
                      .join('、')}
                    {outsideSelection.every((documentId) => titleOf(documentId) === null)
                      ? '名称不可用（不在当前候选列表）'
                      : ''}
                    。保存时预检会指出问题。
                  </p>
                  <div className="textbook-panel-actions">
                    <button className="space-button" onClick={dropOutsideSelection} disabled={busy}>
                      从范围中移除这些书册
                    </button>
                  </div>
                </>
              )}

              {checkResult && !checkResult.scopeReady && (
                <div className="space-banner error" role="alert">
                  预检未通过：{checkResult.reason ?? '服务端未说明原因。'}
                  {checkResult.missingDocumentIds.length > 0 && (
                    <>
                      不可用书册：
                      {checkResult.missingDocumentIds
                        .map((documentId) => titleOf(documentId))
                        .filter((title): title is string => Boolean(title))
                        .join('、') || '（不在当前候选列表，名称不可用）'}
                      。
                    </>
                  )}
                  未保存任何修改。
                </div>
              )}

              {checkResult?.scopeReady && (
                <p className="textbook-hint" role="status">
                  <CheckCircle2 size={14} aria-hidden /> 预检通过：
                  {checkResult.documents.length} 册将进入检索范围。
                </p>
              )}

              {conflict && (
                <div className="space-banner error" role="alert">
                  {conflict}你的选择已保留，尚未写入。
                  <div className="textbook-panel-actions">
                    <button className="space-button" onClick={refreshAfterConflict} disabled={busy}>
                      <RefreshCw size={14} aria-hidden />
                      刷新后重试
                    </button>
                  </div>
                </div>
              )}

              {actionError && (
                <div className="space-banner error" role="alert">
                  {actionError}
                </div>
              )}

              <div className="textbook-panel-actions">
                <button className="space-button primary" onClick={() => void save()} disabled={busy}>
                  {busy ? '正在预检并保存…' : '保存任教范围'}
                </button>
                <button className="space-button" onClick={resetDraft} disabled={busy}>
                  撤销修改
                </button>
                <button className="space-button" onClick={closeEditor} disabled={busy}>
                  取消
                </button>
              </div>
              <p className="textbook-hint">
                保存顺序：先由服务端预检（书册存在、分类一致、已进入当前索引代），通过后才带版本号写入；
                任何一步失败都会保留上面的选择。
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
