'use client';

/**
 * 导入批次列表：文件名 / 状态 / 草稿数（已校对、未归属）/ 警告 / 时间，
 * 点击进入校对页。加载、失败（含重试）、空态与真实数据严格区分。
 *
 * 删除语义（R10，2026-10-13 用户裁定「批次只是导入记录，不因来源追溯而不能删」）：
 * - **彻底删除**：任何状态都可删（含已确认入库）；批次与解析产物（原文块、草稿、AI 建议、
 *   并入记录、生成来源）随批次清除，**题目一律保留**（服务端把题目的来源行批次指针置空、
 *   来源跨度保留），**受管原件（blobs）保留**待独立清理策略；
 * - **放弃**（未确认批次）：服务端只把状态置 `cancelled`，批次记录/原文/草稿保留，供追溯；
 * - 若服务端仍返回引用守卫 409（未来新增守卫的防御性渲染），逐项渲染计数并保留「放弃」快捷入口；
 * - 任何失败都显示服务端原因与下一步，不静默失败、不假装删除成功。
 */

import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, FileText } from 'lucide-react';
import type {
  QuestionImportInUseDetails,
  QuestionImportState,
  QuestionImportSummary,
} from '@/contracts/question-bank';
import { deleteQuestionImport, discardQuestionImport, listQuestionImports } from '@/services/question-bank-api';
import { ErrorNotice } from './ErrorNotice';
import { asApiError, useAsyncResource } from './hooks';
import {
  formatBytes,
  formatDateTime,
  importStateChipClass,
  importStateLabel,
  parseQuestionImportInUseDetails,
} from './labels';

/** 可放弃的批次状态（与服务端 `discard_import` 守卫一致：confirmed 一律 409）。 */
const DISCARDABLE_STATES: readonly QuestionImportState[] = [
  'uploaded',
  'extracting',
  'needs_review',
  'failed',
];

/**
 * 「彻底删除」入口对所有状态开放（R10）：批次是导入记录，题目不受影响——
 * 服务端删除时把题目的来源行批次指针置空（来源跨度保留），因此 confirmed 不再是例外。
 */
const DELETE_BLOCKED_STATES: readonly QuestionImportState[] = [];

/** 删除被拒的原因（逐条渲染；`counts` 缺失时不编造计数）。 */
interface DeleteBlock {
  code: string;
  message: string;
  counts: QuestionImportInUseDetails | null;
}

export function ImportBatchList({ refreshToken }: { refreshToken: number }) {
  const { state, reload } = useAsyncResource(
    (signal) => listQuestionImports(signal),
    `question-imports:${refreshToken}`,
  );
  const [discardBusyId, setDiscardBusyId] = useState<string | null>(null);
  const [discardError, setDiscardError] = useState<string | null>(null);
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteBlocks, setDeleteBlocks] = useState<Record<string, DeleteBlock>>({});

  function rememberBlock(importId: string, block: DeleteBlock) {
    setDeleteBlocks((prev) => ({ ...prev, [importId]: block }));
  }

  function forgetBlock(importId: string) {
    setDeleteBlocks((prev) => {
      if (!(importId in prev)) return prev;
      const next = { ...prev };
      delete next[importId];
      return next;
    });
  }

  /**
   * 放弃未确认批次：二次确认后用当前 `revision` 提交（服务端乐观锁）。
   * 成功后刷新列表取服务端权威状态（显示「已取消」）；失败不改变列表，
   * 409（revision 过期）时同样刷新，用户可按最新 revision 再次确认。
   */
  async function discard(item: QuestionImportSummary) {
    const confirmed = window.confirm(
      `放弃批次「${item.uploadedFileName}」？批次记录、原文与草稿保留，但放弃后不能再校对或确认入库。`,
    );
    if (!confirmed) return;
    setDiscardBusyId(item.importId);
    setDiscardError(null);
    try {
      await discardQuestionImport(item.importId, { expectedRevision: item.revision });
      forgetBlock(item.importId);
      reload();
    } catch (cause) {
      const apiError = asApiError(cause);
      setDiscardError(`放弃批次失败（${apiError.code}）：${apiError.message}`);
      if (apiError.status === 409) reload();
    } finally {
      setDiscardBusyId(null);
    }
  }

  /**
   * 彻底删除批次与解析产物（原件保留；不可恢复）：二次确认后提交。
   * R10：任何状态都可删——**题目不受影响**（服务端把题目的来源行批次指针置空、来源跨度保留）。
   * 若服务端仍返回引用守卫 409（未来新增守卫的防御），原因与逐项计数留在该批次下面并给「放弃」；
   * 成功或 404（已被别处删除）都刷新列表，避免继续显示不存在的批次。
   */
  async function removeBatch(item: QuestionImportSummary) {
    const confirmed = window.confirm(
      `彻底删除批次「${item.uploadedFileName}」？将删除批次与解析产物（原文块、草稿、AI 建议、并入记录），\n` +
        '已入库的题目保留（来源跨度保留、批次指针置空）；受管原件保留；此操作不可恢复。\n' +
        '只想从列表收起时请用「放弃」。',
    );
    if (!confirmed) return;
    setDeleteBusyId(item.importId);
    setDeleteError(null);
    forgetBlock(item.importId);
    try {
      await deleteQuestionImport(item.importId);
      reload();
    } catch (cause) {
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        rememberBlock(item.importId, {
          code: apiError.code,
          message: apiError.message,
          counts: parseQuestionImportInUseDetails(apiError.details),
        });
      } else if (apiError.status === 404) {
        setDeleteError(`彻底删除失败（${apiError.code}）：${apiError.message} 列表已刷新。`);
        reload();
      } else {
        setDeleteError(
          `彻底删除失败（${apiError.code}）：${apiError.message} 没有删除任何数据，可直接重试。`,
        );
      }
    } finally {
      setDeleteBusyId(null);
    }
  }

  /** 列表主体按显式三态渲染；放弃/删除错误横幅独立于主体，刷新时不闪断。 */
  function renderBody() {
    if (state.phase === 'loading') {
      return (
        <div className="qb-list" aria-busy="true" aria-label="正在读取导入批次">
          <div className="space-skeleton" style={{ height: 86 }} aria-hidden />
          <div className="space-skeleton" style={{ height: 86 }} aria-hidden />
        </div>
      );
    }

    if (state.phase === 'failed') {
      return <ErrorNotice label="导入批次读取失败" error={state.error} onRetry={reload} />;
    }

    const imports = state.data.imports;
    if (imports.length === 0) {
      return (
        <div className="space-empty">
          <strong>还没有导入批次</strong>
          <span>用「导入试题」上传 .md / .pdf / .docx 文件后，解析与校对进度会出现在这里。</span>
        </div>
      );
    }

    return (
      <ul className="qb-list qb-import-list">
        {imports.map((item) => {
          const block = deleteBlocks[item.importId] ?? null;
          const deletable = !DELETE_BLOCKED_STATES.includes(item.state);
          return (
            <li key={item.importId}>
              <Link className="qb-import-card" href={`/question-bank/imports/${item.importId}`}>
                <span className="qb-import-icon" aria-hidden>
                  <FileText size={18} />
                </span>
                <span className="qb-import-body">
                  <strong className="qb-import-name">{item.uploadedFileName}</strong>
                  <span className="space-meta-row">
                    <span className={importStateChipClass(item.state)}>
                      {importStateLabel(item.state)}
                    </span>
                    <span>草稿 {item.draftCount}</span>
                    <span>已校对 {item.reviewedCount}</span>
                    <span className={item.unassignedCount > 0 ? 'qb-warn-text' : undefined}>
                      未归属原文 {item.unassignedCount}
                    </span>
                    <span>{formatBytes(item.uploadedBytes)}</span>
                    <span>{formatDateTime(item.createdAt)}</span>
                  </span>
                  {item.warnings.length > 0 && (
                    <span className="qb-warnings">
                      警告 {item.warnings.length} 条：{item.warnings.slice(0, 2).join('；')}
                      {item.warnings.length > 2 ? ' …' : ''}
                    </span>
                  )}
                </span>
                <ChevronRight className="qb-import-chevron" size={16} aria-hidden />
              </Link>

              {item.state === 'confirmed' && (
                <p className="qb-hint" data-testid={`qb-import-retained-${item.importId}`}>
                  已确认入库：删除该批次只清除导入记录与解析产物，**题目保留**（来源跨度保留、
                  批次指针置空）；如需删除题目请到题库列表操作。
                </p>
              )}

              {block && (
                <div
                  className="space-banner error"
                  role="alert"
                  data-testid={`qb-import-delete-blocked-${item.importId}`}
                >
                  <strong>不能彻底删除该批次</strong>
                  <span>
                    {block.code}：{block.message}
                  </span>
                  {block.counts ? (
                    <ul className="qb-warning-list" data-testid={`qb-import-delete-counts-${item.importId}`}>
                      <li>正式题来源登记：{block.counts.sourceRefCount} 处</li>
                      <li>已并入正式题的草稿：{block.counts.mergedDraftCount} 道</li>
                    </ul>
                  ) : (
                    <span>
                      服务端没有给出逐项计数：原因以上述说明为准，不在此处编造计数。
                    </span>
                  )}
                  <div className="qb-actions">
                    <button
                      className="space-button"
                      disabled={discardBusyId === item.importId}
                      onClick={() => void discard(item)}
                    >
                      {discardBusyId === item.importId ? '放弃中…' : '改为放弃（只收起，不删记录）'}
                    </button>
                    <button className="space-button" onClick={() => forgetBlock(item.importId)}>
                      关掉这条原因
                    </button>
                  </div>
                </div>
              )}

              {(DISCARDABLE_STATES.includes(item.state) || deletable) && (
                <div className="qb-actions">
                  {DISCARDABLE_STATES.includes(item.state) && (
                    <button
                      className="space-button danger"
                      aria-label={`放弃批次 ${item.uploadedFileName}`}
                      disabled={discardBusyId === item.importId}
                      onClick={() => void discard(item)}
                    >
                      {discardBusyId === item.importId ? '放弃中…' : '放弃'}
                    </button>
                  )}
                  {deletable && (
                    <button
                      className="space-button danger"
                      aria-label={`彻底删除批次 ${item.uploadedFileName}`}
                      data-testid={`qb-import-delete-${item.importId}`}
                      disabled={deleteBusyId === item.importId}
                      onClick={() => void removeBatch(item)}
                    >
                      {deleteBusyId === item.importId ? '删除中…' : '彻底删除'}
                    </button>
                  )}
                </div>
              )}            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <>
      {discardError && (
        <div className="space-banner error" role="alert">
          {discardError}
        </div>
      )}
      {deleteError && (
        <div className="space-banner error" role="alert" data-testid="qb-import-delete-error">
          {deleteError}
        </div>
      )}
      {renderBody()}
    </>
  );
}
