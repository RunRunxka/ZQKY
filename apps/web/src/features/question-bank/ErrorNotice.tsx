'use client';

/** 统一的错误提示块（role=alert），带可选重试入口；不吞掉 code 与原因。 */

import type { ApiError } from '@/services/api-client';

export function ErrorNotice({
  label,
  error,
  onRetry,
}: {
  label: string;
  error: ApiError;
  onRetry?: () => void;
}) {
  return (
    <div className="space-banner error" role="alert">
      {label}（{error.code}）：{error.message}
      {onRetry && (
        <div className="qb-actions">
          <button className="space-button" onClick={onRetry}>
            重试
          </button>
        </div>
      )}
    </div>
  );
}
