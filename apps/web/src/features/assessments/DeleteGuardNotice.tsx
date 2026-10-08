'use client';

/**
 * 「彻底删除」被引用守卫拒绝（409）时的组件内原因清单。
 *
 * - 原样显示服务端 `code` 与 `message`，不弹原生 alert；
 * - `details.counts` 逐项列出（标签 + 计数 + 条；未知键用原始键名兜底，不隐藏引用）；
 * - 提供「改为归档」快捷入口：归档是可恢复操作，历史引用保留；
 * - 乐观锁冲突 / 404 不走这里（各面板按既有 banner 呈现），避免把版本变化说成引用问题。
 */

import type { ApiError } from '@/services/api-client';
import type { ReferenceCount } from './labels';

export interface DeleteGuardState {
  /** 被拒绝的对象 id（用于按对象归属渲染与测试定位）。 */
  targetId: string;
  /** 展开的 409 信封；`counts` 已单独解析为 `reasons`。 */
  error: ApiError;
  reasons: ReferenceCount[];
}

export function DeleteGuardNotice({
  state,
  targetName,
  archiving = false,
  onArchive,
  testId,
}: {
  state: DeleteGuardState;
  targetName: string;
  archiving?: boolean;
  onArchive?: () => void;
  testId?: string;
}) {
  return (
    <div className="space-banner error" role="alert" data-testid={testId}>
      <p>
        不能彻底删除「{targetName}」（{state.error.code}）：{state.error.message}
      </p>
      {state.reasons.length > 0 && (
        <>
          <p>还有 {state.reasons.length} 类下游数据引用它：</p>
          <ul className="assessments-issue-list" aria-label="引用原因清单">
            {state.reasons.map((reason) => (
              <li key={reason.key}>
                {reason.label} {reason.count} 条
              </li>
            ))}
          </ul>
        </>
      )}
      {state.reasons.length === 0 && (
        <p className="assessments-hint">
          服务端未给出逐项引用计数；请先处理相关数据，或改为归档保证历史完整。
        </p>
      )}
      {onArchive && (
        <div className="assessments-actions">
          <button
            className="space-button"
            disabled={archiving}
            data-testid={testId ? `${testId}-archive` : undefined}
            onClick={onArchive}
          >
            {archiving ? '归档中…' : '改为归档（不删除历史）'}
          </button>
        </div>
      )}
    </div>
  );
}
