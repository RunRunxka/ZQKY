'use client';

/**
 * 导入教材面板：选文件 → 可选元数据 → 上传解析（按阶段轮询草稿到终态）→
 * 预览解析结果 → 确认警告 → 选择目标逻辑库 → 提交入库。
 *
 * 真实状态一律来自后端：本面板不做任何定时器伪推进；解析未完成时按
 * `IMPORT_STATE_LABEL` 显示阶段并轮询 `GET /textbook-imports/{id}`，组件卸载即停。
 * `needsOcr`/`failed` 时明确报错，不显示成功。
 * 提交键（submissionId）由一次用户意图持有：请求级重试复用，成功后释放。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FileText, Upload } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { DocumentMetadataInput, ImportDraftView, JobView } from '@/contracts/textbook';
import { formatBytes } from '@/services/doc-attachments';
import {
  commitImport,
  createImport,
  getImport,
  listLibraries,
  patchImport,
  type ImportMetadataEnvelope,
} from '@/services/textbook-api';
import { asApiError, errorText, useAsyncResource, usePolling } from './hooks';
import { newSubmissionId } from './ids';
import { IMPORT_ACCEPT, IMPORT_SUFFIX_HINT, importFileError } from './import-file';
import {
  commitBlockReason,
  importStateLabel,
  isImportActive,
  LIBRARY_KIND_LABEL,
  REGION_LABEL,
  SOURCE_KIND_LABEL,
} from './labels';
import { EMPTY_METADATA, MetadataForm, metadataErrors, normalizeMetadata } from './MetadataForm';
import type { TaxonomyIndex } from './taxonomy';

/** 预览最多展示的块数（其余由「共 N 块」说明，不截断数据本身）。 */
const PREVIEW_LIMIT = 5;

export interface ImportTarget {
  documentId: string;
  title: string;
  /** 该册当前已发布修订 id；服务端据此做并发保护（过期会 409）。 */
  expectedCurrentRevisionId?: string | null;
}

export function ImportPanel({
  taxonomy,
  onClose,
  onCommitted,
  onOpenJobs,
  onTargetStale,
  updateTarget = null,
  initialMetadata = null,
  initialMetadataError = null,
  pollIntervalMs = 1500,
}: {
  taxonomy: TaxonomyIndex;
  onClose: () => void;
  /** 提交成功后的裸 `JobView`；草稿状态由面板随后自行回读。 */
  onCommitted?: (job: JobView) => void;
  onOpenJobs?: () => void;
  /** 更新目标的期望修订已过期（409）时通知父级刷新书册，用户可保留填写后重试。 */
  onTargetStale?: () => void;
  updateTarget?: ImportTarget | null;
  /** 更新模式的书册分类预填（来自 `GET /textbooks/{id}`）。 */
  initialMetadata?: DocumentMetadataInput | null;
  /** 预填读取失败的原因；不阻断手填。 */
  initialMetadataError?: string | null;
  /** 轮询间隔（生产默认 1.5s；测试可缩小，不小于 1s 的约定由默认值保证）。 */
  pollIntervalMs?: number;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [useMetadata, setUseMetadata] = useState(false);
  const [metadata, setMetadata] = useState<DocumentMetadataInput>(EMPTY_METADATA);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metadataBusy, setMetadataBusy] = useState(false);
  const [metadataNotice, setMetadataNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [staleTarget, setStaleTarget] = useState(false);
  const [draft, setDraft] = useState<ImportDraftView | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [warningsAck, setWarningsAck] = useState(false);
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<string[]>([]);
  const [commitBusy, setCommitBusy] = useState(false);
  const [commitError, setCommitError] = useState<string | null>(null);
  const [committedJob, setCommittedJob] = useState<JobView | null>(null);
  const [committed, setCommitted] = useState(false);
  const submissionRef = useRef<string | null>(null);
  const draftIdRef = useRef<string | null>(null);
  const activeImportId = draft?.importId ?? null;

  const libraries = useAsyncResource((signal) => listLibraries({}, signal), 'import-libraries');

  /** 草稿状态只经这里写入：换草稿时重置提交幂等键/确认状态，并预填服务端已有元数据。 */
  const applyDraft = useCallback((next: ImportDraftView | null) => {
    setDraft(next);
    if (!next || next.importId === draftIdRef.current) return;
    draftIdRef.current = next.importId;
    submissionRef.current = null;
    setWarningsAck(false);
    setCommitted(false);
    setCommittedJob(null);
    setCommitError(null);
    setMetadataNotice(null);
    setMetadataError(null);
    if (next.metadata) {
      const serverMetadata = next.metadata;
      setUseMetadata(true);
      setMetadata((value) => (value === EMPTY_METADATA ? serverMetadata : value));
    }
  }, []);

  const refreshDraft = useCallback(async () => {
    if (!activeImportId) return;
    try {
      const next = await getImport(activeImportId);
      applyDraft(next);
      setPollError(null);
    } catch (error) {
      setPollError(errorText(error));
    }
  }, [activeImportId, applyDraft]);

  // 提交后继续按阶段轮询到终态（ready/failed/cancelled）；入库进度以「入库任务」面板为准
  usePolling(refreshDraft, Boolean(draft && isImportActive(draft.state)), pollIntervalMs);

  // 更新模式的分类预填：不覆盖用户已输入的内容
  useEffect(() => {
    if (!initialMetadata) return;
    setUseMetadata(true);
    setMetadata((value) => (value === EMPTY_METADATA ? initialMetadata : value));
  }, [initialMetadata]);

  const parsed = draft?.parsed ?? null;
  const needsOcr = Boolean(parsed?.needsOcr);
  const warnings = useMemo(() => {
    const list = draft?.warnings ?? [];
    return parsed ? [...new Set([...list, ...parsed.warnings])] : list;
  }, [draft?.warnings, parsed]);
  const terminalFailure = draft?.state === 'failed' || draft?.state === 'cancelled';
  const canCommit = Boolean(
    draft &&
      draft.canCommit &&
      !needsOcr &&
      !terminalFailure &&
      selectedLibraryIds.length > 0 &&
      (warnings.length === 0 || warningsAck) &&
      !committed,
  );
  // 不能提交时的具体原因（未确认元数据 / 需要 OCR / 状态不对 / 缺库或警告确认）
  const blockReason = commitBlockReason({
    draft,
    libraryCount: selectedLibraryIds.length,
    hasWarnings: warnings.length > 0,
    warningsAcknowledged: warningsAck,
    committed,
  });

  function pickFile(next: File | null) {
    if (!next) return;
    const error = importFileError(next);
    if (error) {
      setFile(null);
      setFileError(error);
      return;
    }
    setFile(next);
    setFileError(null);
    setRequestError(null);
  }

  function validatedMetadata(): DocumentMetadataInput | null {
    const errors = metadataErrors(metadata);
    if (errors.length > 0) {
      setMetadataError(errors.join(' '));
      return null;
    }
    setMetadataError(null);
    return normalizeMetadata(metadata);
  }

  async function upload() {
    if (!file) {
      setFileError('请先选择要导入的文件。');
      return;
    }
    // metadataJson 信封：元数据（含确认）+ 更新目标与期望修订（无目标=新增书册）
    const envelope: ImportMetadataEnvelope = {};
    if (useMetadata) {
      const confirmed = validatedMetadata();
      if (!confirmed) return;
      envelope.metadata = confirmed;
      envelope.confirmMetadata = true;
    }
    if (updateTarget) {
      envelope.targetDocumentId = updateTarget.documentId;
      if (updateTarget.expectedCurrentRevisionId) {
        envelope.expectedCurrentRevisionId = updateTarget.expectedCurrentRevisionId;
      }
    }
    setUploading(true);
    setRequestError(null);
    setStaleTarget(false);
    setPollError(null);
    try {
      const created = await createImport(file, envelope);
      applyDraft(created.draft);
    } catch (error) {
      const apiError = asApiError(error);
      if (updateTarget && apiError.status === 409) {
        // 期望修订过期：保留用户填写，刷新书册后再重试
        setStaleTarget(true);
        setRequestError(
          `该书册已被更新，请刷新后重试（${apiError.code}）：${apiError.message} 你已填写的内容已保留。`,
        );
        onTargetStale?.();
      } else {
        setRequestError(`上传失败（${apiError.code}）：${apiError.message}`);
      }
    } finally {
      setUploading(false);
    }
  }

  async function saveMetadata() {
    if (!draft) return;
    const payload = validatedMetadata();
    if (!payload) return;
    setMetadataBusy(true);
    setMetadataNotice(null);
    try {
      const next = await patchImport(draft.importId, {
        expectedRevision: draft.revision,
        metadata: payload,
      });
      if (next) applyDraft(next);
      else await refreshDraft();
      setMetadataNotice('分类已保存。');
    } catch (error) {
      const apiError = asApiError(error);
      // 409：保留用户填写，重新读取草稿供比较
      setMetadataError(
        apiError.status === 409
          ? `保存冲突（${apiError.code}）：${apiError.message} 已保留你的填写，并重新读取了最新草稿，请比较后重试。`
          : apiError.message,
      );
      if (apiError.status === 409) await refreshDraft();
    } finally {
      setMetadataBusy(false);
    }
  }

  async function commit() {
    if (!draft) return;
    if (selectedLibraryIds.length === 0) {
      setCommitError('请选择至少一个目标逻辑库。');
      return;
    }
    if (warnings.length > 0 && !warningsAck) {
      setCommitError('请先确认解析警告。');
      return;
    }
    // 同一次点击的请求级重试复用同一提交键（服务端幂等）
    submissionRef.current = submissionRef.current ?? newSubmissionId();
    setCommitBusy(true);
    setCommitError(null);
    try {
      const job = await commitImport(draft.importId, {
        expectedRevision: draft.revision,
        submissionId: submissionRef.current,
        libraryIds: selectedLibraryIds,
        acknowledgeWarnings: warningsAck,
      });
      setCommittedJob(job);
      setCommitted(true);
      submissionRef.current = null;
      onCommitted?.(job);
      // 草稿状态以服务端为准；轮询到终态前继续显示阶段
      await refreshDraft();
    } catch (error) {
      const apiError = asApiError(error);
      // 请求失败保留提交键：重试同一意图时服务端可幂等识别
      setCommitError(`提交失败（${apiError.code}）：${apiError.message}`);
    } finally {
      setCommitBusy(false);
    }
  }

  return (
    <Modal title={updateTarget ? '更新教材' : '导入教材'} onClose={onClose}>
      <div className="textbook-panel">
        {updateTarget && (
          <div className="space-banner info" role="note">
            更新目标：<strong>{updateTarget.title}</strong>（目标书册 {updateTarget.documentId}
            ，期望修订 {updateTarget.expectedCurrentRevisionId ?? '（服务端以该册当前修订为准）'}
            ）。 上传新文件并提交后替换该册的当前修订；失败时旧修订保持不变。
            {draft?.targetDocumentId && (
              <>
                {' '}
                草稿已绑定目标书册 {draft.targetDocumentId}
                {draft.expectedCurrentRevisionId
                  ? `（期望修订 ${draft.expectedCurrentRevisionId}）`
                  : ''}
                。
              </>
            )}
          </div>
        )}

        <section className="textbook-panel-section" aria-labelledby="textbook-import-file">
          <h3 id="textbook-import-file">1 · 选择文件</h3>
          <p className="textbook-hint">
            支持 {IMPORT_SUFFIX_HINT}，单文件不超过 100 MiB；扫描版 PDF
            需要文本层，否则无法解析入库。
          </p>
          <label className="textbook-field" htmlFor="textbook-import-file-input">
            <span>教材文件</span>
            <input
              id="textbook-import-file-input"
              type="file"
              accept={IMPORT_ACCEPT}
              onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
            />
          </label>
          {file && (
            <p className="textbook-file-line">
              <FileText size={14} aria-hidden />
              {file.name} · {formatBytes(file.size)}
            </p>
          )}
          {fileError && (
            <p className="space-banner error" role="alert">
              {fileError}
            </p>
          )}
        </section>

        <section className="textbook-panel-section" aria-labelledby="textbook-import-metadata">
          <h3 id="textbook-import-metadata">2 · 分类元数据（可选）</h3>
          <label className="textbook-check">
            <input
              type="checkbox"
              checked={useMetadata}
              onChange={(event) => {
                setUseMetadata(event.target.checked);
                setMetadataError(null);
              }}
            />
            填写学段/年级/学科/版本等信息
          </label>
          {useMetadata && (
            <>
              {!taxonomy.ready && (
                <p className="space-banner info" role="note">
                  字典未加载（读取失败或仍在加载）：可稍后在书册「编辑分类」补全。
                </p>
              )}
              <MetadataForm
                value={metadata}
                onChange={setMetadata}
                taxonomy={taxonomy}
                idPrefix="textbook-import"
                disabled={uploading || metadataBusy}
              />
            </>
          )}
          {metadataError && (
            <p className="space-banner error" role="alert">
              {metadataError}
            </p>
          )}
          {initialMetadataError && (
            <p className="space-banner error" role="alert">
              目标书册分类预填失败：{initialMetadataError}（请手动填写分类，保存即确认）
            </p>
          )}
          {metadataNotice && (
            <p className="space-banner info" role="status">
              {metadataNotice}
            </p>
          )}
          <div className="textbook-panel-actions">
            {!draft && (
              <button
                className="space-button primary"
                onClick={() => void upload()}
                disabled={uploading || !file}
              >
                <Upload size={14} aria-hidden />
                {uploading ? '上传中…' : '上传并解析'}
              </button>
            )}
            {draft && (
              <>
                <button
                  className="space-button"
                  onClick={() => void saveMetadata()}
                  disabled={metadataBusy || !useMetadata}
                >
                  {metadataBusy ? '保存中…' : '保存分类'}
                </button>
                <button className="space-button" onClick={() => applyDraft(null)}>
                  重新选择文件
                </button>
              </>
            )}
          </div>
          {requestError && (
            <div className="space-banner error" role="alert">
              {requestError}
              <div className="textbook-panel-actions">
                <button
                  className="space-button"
                  onClick={() => void upload()}
                  disabled={uploading || !file}
                >
                  重试上传
                </button>
                {staleTarget && (
                  <button className="space-button" onClick={() => onTargetStale?.()}>
                    刷新书册信息
                  </button>
                )}
              </div>
            </div>
          )}
        </section>

        {draft && (
          <section className="textbook-panel-section" aria-labelledby="textbook-import-parsed">
            <h3 id="textbook-import-parsed">3 · 解析结果</h3>
            <div className="space-meta-row">
              <span className="space-chip blue">阶段：{importStateLabel(draft.state)}</span>
              <span className="space-chip">文件：{draft.uploadedFileName}</span>
              <span className="space-chip">{formatBytes(draft.uploadedBytes)}</span>
              <span className="space-chip">草稿修订 r{draft.revision}</span>
              {draft.targetDocumentId && (
                <span className="space-chip">目标书册：{draft.targetDocumentId}</span>
              )}
            </div>

            {isImportActive(draft.state) && (
              <p className="textbook-hint" role="status">
                服务端正在处理（阶段：{importStateLabel(draft.state)}
                ），界面按阶段轮询实际状态，不预估进度。
              </p>
            )}
            {draft.state === 'needs_review' && (
              <p className="textbook-hint" role="status">
                解析完成，待确认：核对预览与警告，选择目标逻辑库后提交入库。
              </p>
            )}
            {pollError && (
              <div className="space-banner error" role="alert">
                读取草稿状态失败：{pollError}
                <div className="textbook-panel-actions">
                  <button className="space-button" onClick={() => void refreshDraft()}>
                    重试读取
                  </button>
                </div>
              </div>
            )}

            {draft.state === 'failed' && (
              <div className="space-banner error" role="alert">
                解析失败{draft.errorCode ? `（${draft.errorCode}）` : ''}：后端未生成可入库修订。
                <div className="textbook-panel-actions">
                  <button
                    className="space-button"
                    onClick={() => void upload()}
                    disabled={uploading || !file}
                  >
                    重试上传
                  </button>
                </div>
              </div>
            )}
            {draft.state === 'cancelled' && (
              <div className="space-banner info" role="status">
                该次解析已取消，未写入任何修订。
              </div>
            )}

            {needsOcr && (
              <div className="space-banner error" role="alert">
                需要文本层或人工处理：该文件未提取到可用文本（可能为扫描件），无法分块与向量化，本次不会入库。
              </div>
            )}

            {parsed && (
              <div className="textbook-parsed">
                <div className="space-meta-row">
                  <span className="space-chip">来源：{SOURCE_KIND_LABEL[parsed.sourceKind]}</span>
                  <span className="space-chip">字符 {parsed.charCount}</span>
                  <span className="space-chip">块 {parsed.chunkCount}</span>
                  <span className="space-chip">正文块 {parsed.bodyChunkCount}</span>
                  <span className="space-chip">习题块 {parsed.exerciseChunkCount}</span>
                  {parsed.pageCount !== null && (
                    <span className="space-chip">页数 {parsed.pageCount}</span>
                  )}
                  {parsed.blockCount !== null && (
                    <span className="space-chip">段落 {parsed.blockCount}</span>
                  )}
                </div>

                {warnings.length > 0 && (
                  <div className="space-banner error" role="alert">
                    <strong>解析警告（{warnings.length} 条）</strong>
                    <ul className="textbook-warning-list">
                      {warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                    <label className="textbook-check">
                      <input
                        type="checkbox"
                        checked={warningsAck}
                        onChange={(event) => setWarningsAck(event.target.checked)}
                      />
                      我已核对以上警告，确认继续入库
                    </label>
                  </div>
                )}

                {parsed.preview.length > 0 ? (
                  <>
                    <h4 className="textbook-subhead">
                      分块预览（显示前 {Math.min(PREVIEW_LIMIT, parsed.preview.length)} / 共{' '}
                      {parsed.preview.length} 块）
                    </h4>
                    <ol className="textbook-preview-list">
                      {parsed.preview.slice(0, PREVIEW_LIMIT).map((chunk) => (
                        <li key={chunk.ordinal} className="textbook-preview-item">
                          <div className="space-meta-row">
                            <span className="space-chip">{REGION_LABEL[chunk.region]}</span>
                            <span className="space-chip">
                              字符 {chunk.charStart}–{chunk.charEnd}
                            </span>
                            {chunk.chapterPath.length > 0 && (
                              <span className="space-chip">{chunk.chapterPath.join(' / ')}</span>
                            )}
                          </div>
                          <p className="textbook-preview-text">{chunk.text}</p>
                        </li>
                      ))}
                    </ol>
                  </>
                ) : (
                  <p className="textbook-hint">后端未返回分块预览。</p>
                )}
              </div>
            )}
          </section>
        )}

        {draft && (
          <section className="textbook-panel-section" aria-labelledby="textbook-import-libraries">
            <h3 id="textbook-import-libraries">4 · 加入逻辑库</h3>
            {libraries.state.phase === 'loading' && (
              <div className="space-skeleton" style={{ height: 56 }} aria-hidden />
            )}
            {libraries.state.phase === 'failed' && (
              <div className="space-banner error" role="alert">
                逻辑库列表读取失败：{libraries.state.error.message}
                <div className="textbook-panel-actions">
                  <button className="space-button" onClick={libraries.reload}>
                    重试
                  </button>
                </div>
              </div>
            )}
            {libraries.state.phase === 'ready' && libraries.state.data.libraries.length === 0 && (
              <p className="space-banner info" role="note">
                还没有可用逻辑库：请先由服务端建立基础库，或创建「我的教材」库后再入库。
              </p>
            )}
            {libraries.state.phase === 'ready' && libraries.state.data.libraries.length > 0 && (
              <div className="textbook-library-options">
                {libraries.state.data.libraries.map((library) => (
                  <label key={library.libraryId} className="textbook-check">
                    <input
                      type="checkbox"
                      checked={selectedLibraryIds.includes(library.libraryId)}
                      onChange={() =>
                        setSelectedLibraryIds((current) =>
                          current.includes(library.libraryId)
                            ? current.filter((id) => id !== library.libraryId)
                            : [...current, library.libraryId],
                        )
                      }
                    />
                    {library.displayName}
                    <span className="space-chip">{LIBRARY_KIND_LABEL[library.kind]}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="textbook-panel-actions">
              <button
                className="space-button primary"
                onClick={() => void commit()}
                disabled={!canCommit || commitBusy}
              >
                {commitBusy ? '提交中…' : '提交入库'}
              </button>
              {blockReason && <span className="textbook-hint">{blockReason}</span>}
            </div>
            {commitError && (
              <div className="space-banner error" role="alert">
                {commitError}
                <div className="textbook-panel-actions">
                  <button
                    className="space-button"
                    onClick={() => void commit()}
                    disabled={commitBusy}
                  >
                    重试提交
                  </button>
                </div>
              </div>
            )}
            {committed && (
              <div className="space-banner info" role="status">
                已提交入库任务{committedJob ? `（任务 ${committedJob.jobId}）` : ''}
                ；入库进度以「入库任务」面板的服务端状态为准。
                {onOpenJobs && (
                  <div className="textbook-panel-actions">
                    <button className="space-button" onClick={onOpenJobs}>
                      查看入库任务
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </Modal>
  );
}
