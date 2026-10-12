/**
 * 知识点表单 → 请求体的纯函数层（不碰 DOM、不发请求，便于单测锁定语义）。
 *
 * 契约语义（`@/contracts/knowledge` 与后端 `KnowledgePointUpdateRequest`）：
 * - **空白/缺省 = 不修改**；要清空必须放进 `clearFields`（description/parentId/aliases）
 *   或显式选择「清空」动作 —— 本模块负责把界面意图翻成这两条不同路径。
 * - 名称不可清空（`name` 最短 1）；排序没有清空语义（留空 = 不修改）。
 * - `expectedRevision` 是可变实体乐观锁；改名由服务端追加修订（返回新的 revisionId/version）。
 */

import type {
  KnowledgePointCreateRequest,
  KnowledgePointUpdateRequest,
  KnowledgePointView,
} from '@/contracts/knowledge';

/** 可明确清空的可选字段（与后端 `clearFields` 取值一致）。 */
export const CLEARABLE_FIELDS = ['description', 'parentId', 'aliases'] as const;
export type ClearableField = (typeof CLEARABLE_FIELDS)[number];

/** 父级下拉的哨兵值：不修改（保留原父级）。 */
export const PARENT_UNCHANGED = '';
/** 父级下拉的哨兵值：明确清空父级。 */
export const PARENT_CLEAR = '__clear__';

export const MAX_SORT_ORDER = 1_000_000;
export const MAX_ALIASES = 32;
export const MAX_DESCRIPTION = 4000;

export interface PointClearFlags {
  description: boolean;
  aliases: boolean;
}

export interface PointUpdateValues {
  name: string;
  description: string;
  /** PARENT_UNCHANGED / PARENT_CLEAR / 目标知识点 id */
  parentId: string;
  sortOrder: string;
  aliasesText: string;
}

export interface PointFormPlan {
  /** null = 没有可提交的修改（界面据此禁用保存，不发明空请求）。 */
  request: KnowledgePointUpdateRequest | null;
  errors: string[];
  /** 本次提交将会执行的动作（含「清空」，供界面明示）。 */
  actions: string[];
  /** 「留空 = 不修改」的提示（不是错误）。 */
  hints: string[];
}

/** 别名分隔符与后端 `_ALIAS_SPLIT` 一致：、,;；/ 与换行。 */
export function splitAliases(raw: string): string[] {
  return raw
    .split(/[、,;；/\n\r]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function sameStringList(left: readonly string[], right: readonly string[]): boolean {
  if (left.length !== right.length) return false;
  return left.every((item, index) => item === right[index]);
}

function aliasErrors(aliases: readonly string[]): string[] {
  const errors: string[] = [];
  if (aliases.length > MAX_ALIASES) {
    errors.push(`别名最多 ${MAX_ALIASES} 个（当前 ${aliases.length} 个）。`);
  }
  if (aliases.some((item) => item.length === 0)) {
    errors.push('别名不允许空字符串。');
  }
  if (new Set(aliases).size !== aliases.length) {
    errors.push('别名不允许重复（同一别名只保留一份）。');
  }
  return errors;
}

function parseSortOrder(raw: string): { value?: number; error?: string } {
  const text = raw.trim();
  if (text === '') return {};
  if (!/^\d+$/.test(text)) return { error: `排序需为 0–${MAX_SORT_ORDER} 的整数。` };
  const value = Number.parseInt(text, 10);
  if (value > MAX_SORT_ORDER) return { error: `排序需为 0–${MAX_SORT_ORDER} 的整数。` };
  return { value };
}

/**
 * 把编辑表单翻成更新请求。
 *
 * 与「服务端空白默认不修改」严格对齐：留空的说明/别名只会给出可读提示
 * （提示去勾选「清空」），**不会**被悄悄当成清空，也不会被静默忽略成成功。
 */
export function planPointUpdate(
  current: KnowledgePointView,
  values: PointUpdateValues,
  clear: PointClearFlags,
): PointFormPlan {
  const errors: string[] = [];
  const actions: string[] = [];
  const hints: string[] = [];
  const clearFields: ClearableField[] = [];

  const name = values.name.trim();
  if (name === '') {
    errors.push('名称不能为空（清空名称不是有效修改）。');
  } else if (name !== current.name) {
    actions.push(`修改名称 → ${name}`);
  }

  const description = values.description;
  if (clear.description) {
    if (current.description !== '') {
      clearFields.push('description');
      actions.push('清空说明');
    } else {
      hints.push('该知识点当前没有说明，无需清空。');
    }
    if (description.trim() !== '') {
      hints.push('已勾选「清空说明」：输入框中的文本不会被提交。');
    }
  } else if (description.trim() !== '' && description !== current.description) {
    actions.push('修改说明');
  } else if (description.trim() === '' && current.description !== '') {
    hints.push('说明留空表示不修改；如需清空请勾选「清空说明」。');
  }

  if (values.parentId === PARENT_CLEAR) {
    if (current.parentId !== null || current.parentCode !== null) {
      clearFields.push('parentId');
      actions.push('清空父级');
    } else {
      hints.push('该知识点当前没有父级，无需清空。');
    }
  } else if (values.parentId !== PARENT_UNCHANGED && values.parentId !== current.parentId) {
    actions.push('改挂父级');
  }

  const sort = parseSortOrder(values.sortOrder);
  if (sort.error) errors.push(sort.error);
  else if (sort.value !== undefined && sort.value !== current.sortOrder) {
    actions.push(`排序改为 ${sort.value}`);
  }

  const aliases = splitAliases(values.aliasesText);
  if (clear.aliases) {
    if (current.aliases.length > 0) {
      clearFields.push('aliases');
      actions.push('清空全部别名');
    } else {
      hints.push('该知识点当前没有别名，无需清空。');
    }
    if (aliases.length > 0) {
      hints.push('已勾选「清空全部别名」：输入框中的别名不会被提交。');
    }
  } else if (aliases.length === 0) {
    if (current.aliases.length > 0) {
      hints.push('别名留空表示不修改；如需清空请勾选「清空全部别名」。');
    }
  } else {
    errors.push(...aliasErrors(aliases));
    if (!sameStringList(aliases, current.aliases)) {
      actions.push(`别名改为：${aliases.join('、')}`);
    }
  }

  if (errors.length > 0 || actions.length === 0) {
    return { request: null, errors, actions, hints };
  }

  const request: KnowledgePointUpdateRequest = { expectedRevision: current.revision };
  if (name !== current.name) request.name = name;
  if (!clear.description && description.trim() !== '' && description !== current.description) {
    request.description = description;
  }
  if (
    values.parentId !== PARENT_UNCHANGED &&
    values.parentId !== PARENT_CLEAR &&
    values.parentId !== current.parentId
  ) {
    request.parentId = values.parentId;
  }
  if (sort.value !== undefined && sort.value !== current.sortOrder) {
    request.sortOrder = sort.value;
  }
  if (!clear.aliases && aliases.length > 0 && !sameStringList(aliases, current.aliases)) {
    request.aliases = aliases;
  }
  if (clearFields.length > 0) request.clearFields = clearFields;
  return { request, errors, actions, hints };
}

/* ------------------------------------------------------------------ 建立 */

export interface PointCreateValues {
  subjectId: string;
  code: string;
  name: string;
  description: string;
  parentCode: string;
  sortOrder: string;
  aliasesText: string;
}

export interface PointCreatePlan {
  request: KnowledgePointCreateRequest | null;
  errors: string[];
}

/** 建立请求：学科/编码/名称必填；空白可选字段省略（服务端用缺省值）。 */
export function planPointCreate(values: PointCreateValues): PointCreatePlan {
  const errors: string[] = [];
  const subjectId = values.subjectId.trim();
  const code = values.code.trim();
  const name = values.name.trim();
  if (subjectId === '') errors.push('请选择学科。');
  if (code === '') errors.push('请填写编码（学科内唯一）。');
  else if (code.length > 64) errors.push('编码最长 64 个字符。');
  if (name === '') errors.push('请填写名称。');
  else if (name.length > 200) errors.push('名称最长 200 个字符。');
  const description = values.description;
  if (description.length > MAX_DESCRIPTION) {
    errors.push(`说明最长 ${MAX_DESCRIPTION} 个字符。`);
  }
  const sort = parseSortOrder(values.sortOrder);
  if (sort.error) errors.push(sort.error);
  const aliases = splitAliases(values.aliasesText);
  errors.push(...aliasErrors(aliases));

  if (errors.length > 0) return { request: null, errors };

  const request: KnowledgePointCreateRequest = { subjectId, code, name };
  if (description.trim() !== '') request.description = description;
  const parentCode = values.parentCode.trim();
  if (parentCode !== '') request.parentCode = parentCode;
  if (sort.value !== undefined) request.sortOrder = sort.value;
  if (aliases.length > 0) request.aliases = aliases;
  return { request, errors: [] };
}
