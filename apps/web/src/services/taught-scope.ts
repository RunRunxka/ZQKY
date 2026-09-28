/**
 * 任教范围读取与展示（RAG-REBUILD v1.0 · F1-CHAT）。
 *
 * 边界：
 * - 只读 `GET /teaching-settings`（F0 已在 `textbook-api.ts` 提供客户端函数）；
 * - **读取失败绝不降级为空范围**：调用方据 `state === 'failed'` 阻断并显示原因；
 * - `describeSelection` 只使用服务端已保存的 id 与字典标签，缺标签时省略该段，
 *   不按名称猜测、不在前端拼造范围文案。
 */

import { getTeachingSettings, fetchTextbookTaxonomy } from '@/services/textbook-api';
import type {
  TextbookSelection,
  TextbookTaxonomy,
  TeachingSettingsView,
} from '@/contracts/textbook';

export type TaughtScopeState = 'loading' | 'ready' | 'empty' | 'failed';

export interface TaughtScopeSnapshot {
  state: TaughtScopeState;
  /** 已保存的任教范围；'empty'/'failed' 时为 null（不猜造） */
  selection: TextbookSelection | null;
  /** 服务端给出的范围原因（未保存/未就绪时的如实说明） */
  reason: string | null;
  /** 字典：标签展示用；读取失败为 null（不影响范围本身是否可用） */
  taxonomy: TextbookTaxonomy | null;
  taxonomyError: string | null;
  /** state='failed' 时的可读原因 */
  error: string | null;
  /** 服务端 revision：写回时必须带（只读展示不需要） */
  revision: number | null;
}

export function emptyTaughtScope(): TaughtScopeSnapshot {
  return {
    state: 'loading',
    selection: null,
    reason: null,
    taxonomy: null,
    taxonomyError: null,
    error: null,
    revision: null,
  };
}

/**
 * 读取任教范围与展示字典。
 * - 任一关键读取失败 → state='failed' 且 error 可读（**不是** empty）；
 * - 服务端未保存选择（selection=null 或 scopeReady=false）→ state='empty'；
 * - 已保存 → state='ready'（即使字典读取失败也仍是 ready：范围本身可用，只是标签缺失）。
 */
export async function loadTaughtScope(signal?: AbortSignal): Promise<TaughtScopeSnapshot> {
  let view: TeachingSettingsView;
  try {
    view = await getTeachingSettings(signal);
  } catch (error) {
    if (signal?.aborted) throw error;
    return {
      ...emptyTaughtScope(),
      state: 'failed',
      error: error instanceof Error ? error.message : '无法读取任教范围。',
    };
  }
  const selection = view.selection ?? null;
  let taxonomy: TextbookTaxonomy | null = null;
  let taxonomyError: string | null = null;
  try {
    taxonomy = await fetchTextbookTaxonomy(signal);
  } catch (error) {
    if (signal?.aborted) throw error;
    taxonomyError = error instanceof Error ? error.message : '无法读取年级/学科/版本字典。';
  }
  const ready = !!selection && view.scopeReady;
  return {
    state: ready ? 'ready' : 'empty',
    selection: ready ? selection : null,
    reason: view.scopeReason ?? (ready ? null : '服务端尚未保存可用的任教范围。'),
    taxonomy,
    taxonomyError,
    error: null,
    revision: view.revision ?? null,
  };
}

function labelOf<T extends { id: string; label: string }>(
  list: T[] | undefined,
  id: string,
): string | null {
  return list?.find((item) => item.id === id)?.label ?? null;
}

/**
 * 把 `{gradeId, subjectId, editionId, documentIds}` 渲染成可读文案
 * （如「高一 · 数学 · 人教A版 · 3 册」）。
 *
 * - 字典缺失/未命中时**省略该段**（不显示 uuid、不猜名称）；
 * - `selection` 为空时返回 null（调用方据此不显示范围，而不是显示「未设置」冒充已配置）。
 */
export function describeSelection(
  selection: TextbookSelection | null | undefined,
  taxonomy: TextbookTaxonomy | null | undefined,
  options?: { documentsLabel?: string },
): string | null {
  if (!selection) return null;
  const parts: string[] = [];
  const grade = labelOf(taxonomy?.grades, selection.gradeId);
  if (grade) parts.push(grade);
  const subject = labelOf(taxonomy?.subjects, selection.subjectId);
  if (subject) parts.push(subject);
  const edition = labelOf(taxonomy?.editions, selection.editionId);
  if (edition) parts.push(edition);
  const count = selection.documentIds.length;
  parts.push(options?.documentsLabel ?? `${count} 册`);
  return parts.join(' · ');
}

/** 范围是否可直接用于发起定位（ready 且有书册）。 */
export function isSelectionUsable(scope: TaughtScopeSnapshot): boolean {
  return scope.state === 'ready' && !!scope.selection && scope.selection.documentIds.length > 0;
}
