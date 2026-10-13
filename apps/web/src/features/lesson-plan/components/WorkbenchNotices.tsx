'use client';
/** 工作台提示条（本地草稿、后端同步、导出结果）：如实显示原因，并提供明确的处置入口。 */
import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

export interface WorkbenchNotice {
  id: string;
  tone: 'info' | 'success' | 'warn' | 'error';
  title: string;
  message?: ReactNode;
  actions?: Array<{ label: string; onClick: () => void; testId?: string }>;
  dismissible?: boolean;
}

const ICONS = {
  info: Info,
  success: CheckCircle2,
  warn: AlertTriangle,
  error: XCircle,
} as const;

export function WorkbenchNotices({
  notices,
  onDismiss,
}: {
  notices: WorkbenchNotice[];
  onDismiss: (id: string) => void;
}) {
  if (notices.length === 0) return null;
  return (
    <div className="lw-notices" data-testid="lw-notices">
      {notices.map((notice) => {
        const Icon = ICONS[notice.tone];
        return (
          <div key={notice.id} className={`lw-notice ${notice.tone}`} role="status" data-testid={`lw-notice-${notice.id}`}>
            <Icon size={15} aria-hidden />
            <div className="lw-notice-body">
              <strong>{notice.title}</strong>
              {notice.message && <p>{notice.message}</p>}
            </div>
            <div className="lw-notice-actions">
              {notice.actions?.map((action) => (
                <button
                  key={action.label}
                  type="button"
                  className="lw-button small"
                  data-testid={action.testId}
                  onClick={action.onClick}
                >
                  {action.label}
                </button>
              ))}
              {notice.dismissible !== false && (
                <button
                  type="button"
                  className="lw-icon-button"
                  aria-label={`关闭提示：${notice.title}`}
                  onClick={() => onDismiss(notice.id)}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
