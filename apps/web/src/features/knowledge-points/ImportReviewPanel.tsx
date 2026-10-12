'use client';

/**
 * 表格导入校对：表头映射 → 行处理动作（create/update/ignore）→ 整批确认。
 *
 * - 预览只展示，**不能一上传就入库**；确认前每一行必须有最终动作（后端 422
 *   `KNOWLEDGE_ROW_INVALID` 逐行定位），阻断问题（父树/重复/归档等）未解决时禁止确认；
 * - 保存校对带 `expectedRevision`；409 保留本地编辑并刷新服务端版本供比较；
 * - 确认带幂等 `submissionId`：同批次重复提交命中重放 → 显示「已确认（重放）」；
 *   传输失败（拿不到响应）时如实说「结果未知」，并引导用**同一提交标识**重试；
 * - 确认结果条与「已确认」状态都带稳定 testid，且刷新批次不会把它卸载掉；
 * - AI 候选批次（`source="ai"`）在视觉上与人工表格导入明显区分。
 */

import { useEffect, useRef, useState } from 'react';
import { CheckCheck, RefreshCw, Save } from 'lucide-react';
import type { ErrorIssue } from '@/contracts/api';
import {
  KNOWLEDGE_IMPORT_FIELDS,
  type KnowledgeImportConfirmResult,
  type KnowledgeImportRowView,
  type KnowledgeImportView,
  type KnowledgeRowAction,
} from '@/contracts/knowledge';
import { Modal } from '@/components/ui/Modal';
import { ApiError } from '@/services/api-client';
import {
  confirmKnowledgeImport,
  getKnowledgeImport,
  patchKnowledgeImport,
} from '@/services/knowledge-points-api';
import { asApiError, useAsyncResource } from './hooks';
import {
  blockingIssues,
  importSourceLabel,
  importStateChipClass,
  importStateLabel,
  isBlockingIssue,
  issueLocationLabel,
  rowActionLabel,
} from './labels';

interface EditState {
  forId: string;
  decisions: Record<number, KnowledgeRowAction>;
  mapping: Record<string, string>;
}

const EMPTY_EDITS: EditState = { forId: '', decisions: {}, mapping: {} };

export function ImportReviewPanel({
  importId,
  onChanged,
  onConfirmed,
}: {
  importId: string;
  onChanged?: () => void;
  onConfirmed?: (result: KnowledgeImportConfirmResult) => void;
}) {
  const detail = useAsyncResource(
    (signal) => getKnowledgeImport(importId, signal),
    `kp-import|${importId}`,
  );
  // 最近一次成功读取的批次：确认/校对后的刷新期间继续渲染正文，
  // 这样「已确认入库 / 已确认（重放）」的结果条不会被刷新卸载掉。
  const view = detail.lastData;
  const loadError = detail.state.phase === 'failed' ? detail.state.error : null;
  const refreshing = detail.state.phase === 'loading' && view !== null;

  if (!view) {
    if (loadError) {
      return (
        <div className="kp-import-review">
          <div className="space-banner error" role="alert">
            <div className="space-banner-row">
              <span>
                导入批次读取失败（{loadError.code}）：{loadError.message}
              </span>
              <button className="space-button" onClick={detail.reload}>
                <RefreshCw size={13} aria-hidden />
                重试
              </button>
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="kp-import-review" aria-busy="true" aria-label="正在读取导入批次">
        <div className="space-skeleton" style={{ height: 90 }} aria-hidden />
        <div className="space-skeleton" style={{ height: 260 }} aria-hidden />
      </div>
    );
  }

  // 正文 key 用批次 id（刷新同一批次不重置编辑态与确认结果）。
  return (
    <ImportReviewBody
      key={view.importId}
      view={view}
      reload={detail.reload}
      refreshing={refreshing}
      loadError={loadError}
      onChanged={onChanged}
      onConfirmed={onConfirmed}
    />
  );
}

function ImportReviewBody({
  view,
  reload,
  refreshing,
  loadError,
  onChanged,
  onConfirmed,
}: {
  view: KnowledgeImportView;
  reload: () => void;
  /** 刷新同一批次中（保留当前编辑与结果条，不用骨架替换）。 */
  refreshing: boolean;
  /** 刷新失败（页面仍显示上一次成功读取的数据）。 */
  loadError: ApiError | null;
  onChanged?: () => void;
  onConfirmed?: (result: KnowledgeImportConfirmResult) => void;
}) {
  const [edits, setEdits] = useState<EditState>(EMPTY_EDITS);
  const [busy, setBusy] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [rowIssues, setRowIssues] = useState<ErrorIssue[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [result, setResult] = useState<KnowledgeImportConfirmResult | null>(null);
  const submissionRef = useRef<{ importId: string; id: string } | null>(null);

  // 编辑态只在批次身份变化时初始化：409/刷新后不会冲掉用户逐行选择的动作。
  useEffect(() => {
    setEdits((prev) =>
      prev.forId === view.importId ? prev : { ...EMPTY_EDITS, forId: view.importId },
    );
  }, [view.importId]);

  const mapping: Record<string, string> = { ...view.mapping, ...edits.mapping };
  const decisionOf = (row: KnowledgeImportRowView): KnowledgeRowAction | null =>
    edits.decisions[row.rowNo] ?? row.decision;
  const decidedRows = view.rows.filter((row) => decisionOf(row) !== null);
  const unresolvedRows = view.rows.filter((row) => decisionOf(row) === null);
  const blocking = view.rows.flatMap((row) => blockingIssues(row.issues));
  const batchBlocking = blockingIssues(view.issues);
  const canConfirm =
    blocking.length === 0 && batchBlocking.length === 0 && unresolvedRows.length === 0;

  function ensureSubmissionId(): string {
    if (!submissionRef.current || submissionRef.current.importId !== view.importId) {
      submissionRef.current = { importId: view.importId, id: crypto.randomUUID() };
    }
    return submissionRef.current.id;
  }

  function openConfirm() {
    ensureSubmissionId();
    setConfirmOpen(true);
  }

  async function saveRows() {
    if (decidedRows.length === 0) {
      setErrorText('还没有已选定的行动作；请先为需要处理的行选择 create / update / ignore。');
      return;
    }
    setBusy(true);
    setErrorText(null);
    setRowIssues([]);
    setNotice(null);
    try {
      const next = await patchKnowledgeImport(view.importId, {
        expectedRevision: view.revision,
        // 只保存已明确选择的行：未选择的行不在这里被静默改成 ignore
        rows: decidedRows.map((row) => ({
          rowNo: row.rowNo,
          decision: decisionOf(row) as KnowledgeRowAction,
          expectedRevision: row.baseRevision,
        })),
      });
      setEdits({ ...EMPTY_EDITS, forId: next.importId });
      setNotice(`已保存校对（批次修订 r${next.revision}，共 ${decidedRows.length} 行）。`);
      reload();
      onChanged?.();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409) {
        setErrorText(
          `当前版本 ${error.details?.currentRevision ?? '未知'}，已刷新为最新，请重试：${error.message} 你选择的动作已保留。`,
        );
        reload();
      } else if (error.status === 422) {
        setRowIssues(error.details?.issues ?? []);
        setErrorText(`保存校对失败（${error.code}）：${error.message}`);
      } else {
        setErrorText(`保存校对失败（${error.code}）：${error.message} 已选动作保留，可直接重试。`);
      }
    } finally {
      setBusy(false);
    }
  }

  async function saveMapping() {
    setBusy(true);
    setErrorText(null);
    setRowIssues([]);
    setNotice(null);
    try {
      const next = await patchKnowledgeImport(view.importId, {
        expectedRevision: view.revision,
        mapping,
      });
      setEdits({ ...EMPTY_EDITS, forId: next.importId });
      setNotice(`已保存表头映射并重算行（批次修订 r${next.revision}）。`);
      reload();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409) {
        setErrorText(
          `当前版本 ${error.details?.currentRevision ?? '未知'}，已刷新为最新，请重试：${error.message}`,
        );
        reload();
      } else {
        setErrorText(`保存映射失败（${error.code}）：${error.message}`);
      }
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setConfirmBusy(true);
    setErrorText(null);
    setRowIssues([]);
    try {
      const payload = await confirmKnowledgeImport(view.importId, {
        expectedRevision: view.revision,
        submissionId: ensureSubmissionId(),
        actions: view.rows.map((row) => ({
          rowNo: row.rowNo,
          decision: decisionOf(row) as KnowledgeRowAction,
          expectedRevision: row.baseRevision,
        })),
      });
      setResult(payload);
      setConfirmOpen(false);
      setEdits({ ...EMPTY_EDITS, forId: view.importId });
      reload();
      onChanged?.();
      onConfirmed?.(payload);
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 422) {
        setRowIssues(error.details?.issues ?? []);
        setErrorText(
          `批次未确认（${error.code}）：${error.message} 阻断问题逐行标出，解决后再确认。`,
        );
      } else if (error.status === 409) {
        setErrorText(
          `当前版本 ${error.details?.currentRevision ?? '未知'}，已刷新为最新，请重试：${error.message}`,
        );
        reload();
      } else if (error.status === 0) {
        // 拿不到响应（网络/代理层失败）：服务端可能已写入也可能没写入，
        // 不说「没有写入」，引导用同一提交标识重试（幂等，同载荷不会重复写）。
        setErrorText(
          `确认结果未知（${error.code}）：${error.message} 可能已写入也可能未写入；` +
            `请直接重试——同一个提交标识会按幂等处理，同载荷不会重复写入。`,
        );
      } else {
        setErrorText(`确认失败（${error.code}）：${error.message} 没有任何知识点被写入，可重试。`);
      }
    } finally {
      setConfirmBusy(false);
    }
  }

  const isAi = view.source === 'ai';

  return (
    <div
      className={isAi ? 'kp-import-review ai' : 'kp-import-review'}
      data-testid="kp-import-review"
    >
      <header className="kp-import-head">
        <div>
          <h3 data-testid="kp-import-file">{view.fileAsset.originalName || '（无文件名）'}</h3>
          <div className="space-meta-row">
            <span
              className={isAi ? 'space-chip amber' : 'space-chip'}
              data-testid="kp-import-source"
            >
              {importSourceLabel(view.source)}
            </span>
            <span className={importStateChipClass(view.state)} data-testid="kp-import-state">
              {importStateLabel(view.state)}
            </span>
            <span className="space-chip">批次修订 r{view.revision}</span>
            <span className="space-chip">行 {view.rows.length}</span>
            {blocking.length + batchBlocking.length > 0 && (
              <span className="space-chip amber" data-testid="kp-import-blocking">
                阻断问题 {blocking.length + batchBlocking.length}
              </span>
            )}
          </div>
        </div>
        <button className="space-button" onClick={reload}>
          <RefreshCw size={13} aria-hidden />
          重新读取批次
        </button>
      </header>

      {isAi && (
        <p className="space-banner info" role="status" data-testid="kp-ai-banner">
          AI 候选批次：候选尚未入库（不是正式知识点），逐行校对并整批确认后才写入正式知识点表。
        </p>
      )}

      {refreshing && (
        <p className="kp-hint" role="status" data-testid="kp-import-refreshing">
          正在刷新批次（保留当前校对进度与确认结果）…
        </p>
      )}

      {loadError && (
        <div className="space-banner error" role="alert" data-testid="kp-import-refresh-failed">
          <div className="space-banner-row">
            <span>
              刷新批次失败（{loadError.code}）：{loadError.message}
              页面仍显示上一次成功读取的数据，你的校对不会被清空。
            </span>
            <button className="space-button" onClick={reload}>
              <RefreshCw size={13} aria-hidden />
              重试
            </button>
          </div>
        </div>
      )}

      {view.warnings.length > 0 && (
        <div className="space-banner">
          <strong>解析提示 {view.warnings.length} 条</strong>
          <ul className="kp-warning-list">
            {view.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {view.issues.length > 0 && (
        <ul className="kp-issue-list">
          {view.issues.map((issue, index) => (
            <li key={`batch-${issue.code}-${index}`}>
              批次级：{issueLocationLabel(issue)}
              {issue.code}：{issue.message}
            </li>
          ))}
        </ul>
      )}

      {view.source === 'file' && view.headers.length > 0 && (
        <section className="kp-subpanel" aria-label="表头映射">
          <h4>表头映射（只允许知识点六个字段）</h4>
          <div className="kp-mapping-grid">
            {view.headers.map((header) => (
              <label key={header} className="kp-field kp-field-narrow">
                <span className="kp-field-label">{header}</span>
                <select
                  className="space-select"
                  value={mapping[header] ?? ''}
                  aria-label={`表头 ${header} 映射字段`}
                  disabled={busy}
                  onChange={(event) =>
                    setEdits((prev) => ({
                      ...prev,
                      mapping: { ...prev.mapping, [header]: event.target.value },
                    }))
                  }
                >
                  <option value="">不映射</option>
                  {KNOWLEDGE_IMPORT_FIELDS.map((field) => (
                    <option key={field} value={field}>
                      {field}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <button className="space-button" disabled={busy} onClick={() => void saveMapping()}>
            <Save size={13} aria-hidden />
            保存映射并重算行
          </button>
        </section>
      )}

      <section className="kp-subpanel" aria-label="行校对">
        <div className="kp-subpanel-head">
          <h4>行校对（每行必须有最终动作）</h4>
          <span className="kp-hint">
            {unresolvedRows.length > 0
              ? `还有 ${unresolvedRows.length} 行未选择动作`
              : '所有行已选择动作'}
          </span>
        </div>

        <ul className="kp-row-list">
          {view.rows.map((row) => {
            const decision = decisionOf(row);
            const rowIssueList = row.issues;
            const hasBlocking = rowIssueList.some(isBlockingIssue);
            return (
              <li
                key={row.rowNo}
                className={hasBlocking ? 'kp-row-card blocking' : 'kp-row-card'}
                data-testid={`kp-row-${row.rowNo}`}
              >
                <div className="kp-row-head">
                  <span className="space-chip">第 {row.rowNo} 行</span>
                  <span className={hasBlocking ? 'space-chip amber' : 'space-chip'}>
                    {hasBlocking ? '有阻断问题' : '仅提示'}
                  </span>
                  {row.targetKnowledgePointId ? (
                    <span className="space-chip blue">更新目标 {row.targetKnowledgePointId}</span>
                  ) : (
                    <span className="space-chip">未匹配既有知识点</span>
                  )}
                  {row.baseVersion !== null && (
                    <span className="space-chip">目标版本 v{row.baseVersion}</span>
                  )}
                  <label className="kp-field kp-field-inline">
                    <span className="kp-field-label">处理动作</span>
                    <select
                      className="space-select"
                      value={decision ?? ''}
                      aria-label={`第 ${row.rowNo} 行处理动作`}
                      disabled={busy}
                      onChange={(event) =>
                        setEdits((prev) => ({
                          ...prev,
                          decisions: {
                            ...prev.decisions,
                            [row.rowNo]: event.target.value as KnowledgeRowAction,
                          },
                        }))
                      }
                    >
                      <option value="">未选择（确认前必须选定）</option>
                      <option value="create">create（新建）</option>
                      <option value="update">update（更新既有）</option>
                      <option value="ignore">ignore（忽略）</option>
                    </select>
                  </label>
                  {decision && <span className="space-chip">{rowActionLabel(decision)}</span>}
                </div>

                <dl className="kp-row-fields">
                  <div>
                    <dt>编码</dt>
                    <dd>{row.code || '（空）'}</dd>
                  </div>
                  <div>
                    <dt>名称</dt>
                    <dd>{row.name || '（空）'}</dd>
                  </div>
                  <div>
                    <dt>父级编码</dt>
                    <dd>{row.parentCode || '（无）'}</dd>
                  </div>
                  <div>
                    <dt>说明</dt>
                    <dd>{row.description || '（空）'}</dd>
                  </div>
                  <div>
                    <dt>别名</dt>
                    <dd>{row.aliases.length > 0 ? row.aliases.join('、') : '（无）'}</dd>
                  </div>
                </dl>

                {rowIssueList.length > 0 && (
                  <ul className="kp-issue-list">
                    {rowIssueList.map((issue, index) => (
                      <li key={`${row.rowNo}-${issue.code}-${index}`}>
                        {issueLocationLabel(issue)}
                        {issue.code}：{issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>

        {view.rows.length === 0 && (
          <p className="space-empty">
            <strong>该批次没有数据行</strong>
            <span>可能表头为空或表格没有内容；请检查文件后重新上传。</span>
          </p>
        )}

        <div className="kp-actions">
          <button
            className="space-button"
            disabled={busy || decidedRows.length === 0}
            onClick={() => void saveRows()}
          >
            <Save size={13} aria-hidden />
            {busy ? '保存中…' : `保存校对（${decidedRows.length} 行）`}
          </button>
          <button
            className="space-button primary"
            disabled={busy || !canConfirm || view.state === 'confirmed'}
            onClick={openConfirm}
          >
            <CheckCheck size={14} aria-hidden />
            整批确认入库
          </button>
          {view.state === 'confirmed' && <span className="space-chip green">该批次已确认</span>}
          {!canConfirm && (
            <span className="kp-hint">
              {unresolvedRows.length > 0
                ? `还有 ${unresolvedRows.length} 行没有选定动作，确认入口暂不可用。`
                : `还有 ${blocking.length + batchBlocking.length} 个阻断问题，解决后确认入口才可用。`}
            </span>
          )}
        </div>
      </section>

      {errorText && (
        <p className="space-banner error" role="alert">
          {errorText}
        </p>
      )}

      {rowIssues.length > 0 && (
        <ul className="kp-issue-list" data-testid="kp-confirm-issues">
          {rowIssues.map((issue, index) => (
            <li key={`confirm-${issue.code}-${index}`}>
              {issueLocationLabel(issue)}
              {issue.code}：{issue.message}
            </li>
          ))}
        </ul>
      )}

      {notice && (
        <p className="space-banner info" role="status">
          {notice}
        </p>
      )}

      {result ? (
        <p className="space-banner info" role="status" data-testid="kp-confirm-result">
          {result.replayed
            ? '已确认（重放）：同一提交标识此前已入库，本次未重复写入。'
            : `已确认入库：新建 ${result.created.length} 条、更新 ${result.updated.length} 条、忽略 ${result.ignored.length} 行。`}
        </p>
      ) : view.state === 'confirmed' ? (
        // 已确认批次（本页没有本次会话的回执，例如刷新后或有另一处已确认）也渲染同一元素：
        // 只陈述服务端状态，不在此处编造写入计数或重放结论。
        <p className="space-banner info" role="status" data-testid="kp-confirm-result">
          该批次已确认入库；本页没有本次会话的提交回执（不显示写入计数，也不重复写入）。
        </p>
      ) : null}

      {confirmOpen && (
        <Modal title="整批确认入库" onClose={() => setConfirmOpen(false)}>
          <p className="kp-hint">
            将按下列动作一次性写入正式知识点表（后端在同一事务内重校验父树/重复/归档）：
          </p>
          <ul className="kp-confirm-summary">
            {view.rows.map((row) => {
              const decision = decisionOf(row);
              return (
                <li key={row.rowNo}>
                  第 {row.rowNo} 行 · {decision ? rowActionLabel(decision) : '（未选择）'} ·{' '}
                  {row.code || '（无编码）'}
                  {row.name ? ` ${row.name}` : ''}
                </li>
              );
            })}
          </ul>
          <p className="kp-hint">
            提交标识：{submissionRef.current?.id ?? '（点确认时生成）'}
            （幂等；失败重试复用同一标识）。
          </p>
          <div className="kp-actions">
            <button
              className="space-button primary"
              disabled={confirmBusy}
              onClick={() => void confirm()}
            >
              {confirmBusy ? '确认中…' : '确认入库'}
            </button>
            <button
              className="space-button"
              disabled={confirmBusy}
              onClick={() => setConfirmOpen(false)}
            >
              取消
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
