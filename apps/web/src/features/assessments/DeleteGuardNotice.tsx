'use client';

/**
 * 「彻底删除」被引用守卫拒绝（409）时的组件内原因清单（R5-FE 取回，R10-FE 去归档 + 分组）。
 *
 * - 原样显示服务端 `code` 与 `message`，不弹原生 alert；
 * - `details.counts` 逐项列出并**分成两组**（2026-10-13 用户反馈"这些都在什么地方"）：
 *   `blockingKeys` 里的键 = 真正挡住删除、要去别处处置的引用；
 *   其余键 = **随本次删除一起清掉、无需处理**的行（服务端一并给出只是如实告知）；
 * - 未知键用原始键名兜底，不隐藏任何一条引用；未给 `blockingKeys` 的域保持单列表展示；
 * - 归档功能已按用户裁定舍弃，这里不提供「改为归档」兜底；
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
  blockingKeys = [],
  testId,
}: {
  state: DeleteGuardState;
  targetName: string;
  /** 该域里「挡住删除、必须先处置」的计数键；其余键按"随删除清掉"展示。 */
  blockingKeys?: readonly string[];
  testId?: string;
}) {
  const categorized = blockingKeys.length > 0;
  const blocking = state.reasons.filter((reason) => blockingKeys.includes(reason.key));
  const cascading = state.reasons.filter((reason) => !blockingKeys.includes(reason.key));

  return (
    <div className="space-banner error" role="alert" data-testid={testId}>
      <p>
        不能彻底删除「{targetName}」（{state.error.code}）：{state.error.message}
      </p>
      {categorized && blocking.length > 0 && (
        <>
          <p>必须先处置（它们挡住删除，且不随删除清掉）：</p>
          <ul className="assessments-issue-list" aria-label="阻断删除的引用">
            {blocking.map((reason) => (
              <li key={reason.key}>
                {reason.label} {reason.count} 条
              </li>
            ))}
          </ul>
        </>
      )}
      {categorized && blocking.length === 0 && state.reasons.length > 0 && (
        <p className="assessments-hint">
          服务端没有列出具体阻断项（details.counts 为空或形状不符）；请按上面的说明处置后再试。
        </p>
      )}
      {categorized && cascading.length > 0 && (
        <>
          <p>随删除一起清掉（无需先处理）：</p>
          <ul className="assessments-issue-list" aria-label="随删除清掉的引用">
            {cascading.map((reason) => (
              <li key={reason.key}>
                {reason.label} {reason.count} 条
              </li>
            ))}
          </ul>
        </>
      )}
      {!categorized && state.reasons.length > 0 && (
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
          服务端未给出逐项引用计数；请先按服务端说明处理相关数据，再重试删除。
        </p>
      )}
    </div>
  );
}
