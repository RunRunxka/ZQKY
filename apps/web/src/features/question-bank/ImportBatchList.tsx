'use client';

/**
 * 导入批次列表：文件名 / 状态 / 草稿数（已校对、未归属）/ 警告 / 时间，
 * 点击进入校对页。加载、失败（含重试）、空态与真实数据严格区分。
 */

import Link from 'next/link';
import { ChevronRight, FileText } from 'lucide-react';
import { listQuestionImports } from '@/services/question-bank-api';
import { ErrorNotice } from './ErrorNotice';
import { useAsyncResource } from './hooks';
import { formatBytes, formatDateTime, importStateChipClass, importStateLabel } from './labels';

export function ImportBatchList({ refreshToken }: { refreshToken: number }) {
  const { state, reload } = useAsyncResource(
    (signal) => listQuestionImports(signal),
    `question-imports:${refreshToken}`,
  );

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
      {imports.map((item) => (
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
        </li>
      ))}
    </ul>
  );
}
