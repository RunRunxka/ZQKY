/**
 * 教案工作台本地草稿（沿用归档 `DraftRepository` + `createDraftWriter` 的语义）。
 *
 * 键兼容：`zhiqikeyuan:lesson-plan:v1`（归档同一把钥匙、`schemaVersion=1`）——
 * 旧草稿（只有 `data`）可以继续读取，缺的排版/模块布局取默认值。
 *
 * 失败保护：读取失败 / 结构损坏 / 版本不兼容时**不返回空草稿、也不允许自动覆盖**：
 * 返回 `error` 状态并保留原始字节（`readRawLocalDraft`），由界面提示教师处置。
 */
import type { DraftEnvelope, LessonPlanData, LessonWorkbenchStyleWire } from '@/contracts/lesson-plans';
import { isRecord } from './records';
import { withLessonDefaults } from './lesson-data';
import {
  DEFAULT_LESSON_STYLE,
  normalizeModules,
  normalizeStyle,
  type LessonModuleEntry,
} from './modules';

/** 浏览器存储的安全入口（无 window / 隐私模式不可用 → null，调用方按"无本地记忆"处理）。 */
export function safeBrowserStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export const LOCAL_DRAFT_KEY = 'zhiqikeyuan:lesson-plan:v1';
/** 当前打开的云端教案 id（本机记忆；读取失败不删除）。 */
export const ACTIVE_PLAN_KEY = 'zhiqikeyuan:lesson-plan:active:v1';

/** 排版默认值版本：2 = 模板口径（14pt / 24pt exact / 72px 边距 / 8px 模块间距 / 0 段距）。 */
export const STYLE_VERSION = 2;

/** R12 旧默认：仅当草稿排版完全等于这套值时，才一次性迁移到模板口径。 */
const LEGACY_DEFAULT_STYLE: LessonWorkbenchStyleWire = {
  fontId: 'puhuiti',
  baseSize: 14,
  headingSize: 16,
  labelSize: 12,
  lineHeight: 1.7,
  pageMargin: 48,
  moduleGap: 16,
  paragraphGap: 6,
};

const STYLE_KEYS: Array<keyof LessonWorkbenchStyleWire> = [
  'fontId',
  'baseSize',
  'headingSize',
  'labelSize',
  'lineHeight',
  'pageMargin',
  'moduleGap',
  'paragraphGap',
];

/** 旧草稿没有 styleVersion：只有整套值仍是旧默认时升级，用户改过任意一项就保留。 */
function upgradeLegacyStyle(style: LessonWorkbenchStyleWire): LessonWorkbenchStyleWire {
  const isLegacyDefault = STYLE_KEYS.every((key) => style[key] === LEGACY_DEFAULT_STYLE[key]);
  return isLegacyDefault ? { ...DEFAULT_LESSON_STYLE } : style;
}

export interface WorkbenchDraft {
  data: LessonPlanData;
  modules: LessonModuleEntry[];
  removed: LessonModuleEntry[];
  style: LessonWorkbenchStyleWire;
  revision: number;
  updatedAt: string;
}

export type LocalDraftRead =
  | { status: 'empty' }
  | { status: 'ok'; draft: WorkbenchDraft }
  | { status: 'error'; message: string };

export const LOCAL_DRAFT_ERROR_MESSAGE = '本地草稿读取失败，已暂停自动保存以免覆盖原稿。';

/** 正文可识别的键：一个都没有说明这不是教案草稿（结构损坏）。 */
const DATA_KEYS = ['title', 'basic', 'analysis', 'processV2', 'coreCompetencies', 'reflection'] as const;

function hasLessonShape(value: unknown): boolean {
  return isRecord(value) && DATA_KEYS.some((name) => name in value);
}

export function normalizeDraftEnvelope(value: unknown): DraftEnvelope {
  if (!isRecord(value)) throw new Error('草稿不是对象');
  if (value.schemaVersion !== 1) throw new Error(`草稿版本不兼容：${String(value.schemaVersion)}`);
  if (!hasLessonShape(value.data)) throw new Error('草稿正文结构损坏');
  const normalizedStyle = normalizeStyle(value.style);
  const style =
    value.styleVersion === STYLE_VERSION ? normalizedStyle : upgradeLegacyStyle(normalizedStyle);
  return {
    schemaVersion: 1,
    styleVersion: STYLE_VERSION,
    revision: typeof value.revision === 'number' ? value.revision : 0,
    updatedAt: typeof value.updatedAt === 'string' ? value.updatedAt : new Date(0).toISOString(),
    data: withLessonDefaults(value.data),
    style,
    modules: normalizeModules(value.modules),
    removedModules: Array.isArray(value.removedModules)
      ? normalizeModules(value.removedModules).filter((entry) => entry.kind === 'custom')
      : [],
  };
}

export function readLocalDraft(storage: Storage): LocalDraftRead {
  const raw = storage.getItem(LOCAL_DRAFT_KEY);
  if (raw === null) return { status: 'empty' };
  try {
    const parsed = JSON.parse(raw) as unknown;
    const envelope = normalizeDraftEnvelope(parsed);
    return {
      status: 'ok',
      draft: {
        data: envelope.data,
        modules: normalizeModules(envelope.modules),
        removed: normalizeModules(envelope.removedModules).filter((entry) => entry.kind === 'custom'),
        style: envelope.style ?? normalizeStyle(undefined),
        revision: envelope.revision,
        updatedAt: envelope.updatedAt,
      },
    };
  } catch {
    return { status: 'error', message: LOCAL_DRAFT_ERROR_MESSAGE };
  }
}

/** 原始字节（坏草稿备份/导出用；绝不用于自动恢复）。 */
export function readRawLocalDraft(storage: Storage): string | null {
  return storage.getItem(LOCAL_DRAFT_KEY);
}

export function writeLocalDraft(storage: Storage, draft: WorkbenchDraft): void {
  const envelope: DraftEnvelope = {
    schemaVersion: 1,
    styleVersion: STYLE_VERSION,
    revision: draft.revision,
    updatedAt: draft.updatedAt,
    data: draft.data,
    style: draft.style,
    modules: draft.modules.map((entry) => ({
      id: entry.id,
      kind: entry.kind,
      ...(entry.builtinId ? { builtinId: entry.builtinId } : {}),
      label: entry.label,
      ...(entry.hidden ? { hidden: true } : {}),
      ...(entry.body !== undefined ? { body: entry.body } : {}),
    })),
    removedModules: draft.removed.map((entry) => ({
      id: entry.id,
      kind: entry.kind,
      ...(entry.builtinId ? { builtinId: entry.builtinId } : {}),
      label: entry.label,
      ...(entry.body !== undefined ? { body: entry.body } : {}),
    })),
  };
  storage.setItem(LOCAL_DRAFT_KEY, JSON.stringify(envelope));
}

export function clearLocalDraft(storage: Storage): void {
  storage.removeItem(LOCAL_DRAFT_KEY);
}

export function readActivePlanId(storage: Storage): string | null {
  const value = storage.getItem(ACTIVE_PLAN_KEY);
  return value && value.trim() ? value : null;
}

export function writeActivePlanId(storage: Storage, lessonPlanId: string): void {
  storage.setItem(ACTIVE_PLAN_KEY, lessonPlanId);
}

export function clearActivePlanId(storage: Storage): void {
  storage.removeItem(ACTIVE_PLAN_KEY);
}

/** 教案归属（学科 + 班级）本机记忆：教案必须属于某班某科，新建/导出时复用上次选择。 */
export const LESSON_OWNERSHIP_KEY = 'zhiqikeyuan:lesson-plan:ownership:v1';

export interface LessonOwnership {
  subjectId: string;
  classId: string;
}

const EMPTY_OWNERSHIP: LessonOwnership = { subjectId: '', classId: '' };

export function readOwnership(storage: Storage): LessonOwnership {
  const raw = storage.getItem(LESSON_OWNERSHIP_KEY);
  if (!raw) return EMPTY_OWNERSHIP;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) return EMPTY_OWNERSHIP;
    const subjectId = typeof parsed.subjectId === 'string' ? parsed.subjectId : '';
    const classId = typeof parsed.classId === 'string' ? parsed.classId : '';
    return { subjectId, classId };
  } catch {
    // 记忆损坏不当成"已选"：返回空，让界面重新选（不覆盖、不猜）。
    return EMPTY_OWNERSHIP;
  }
}

export function writeOwnership(storage: Storage, ownership: LessonOwnership): void {
  storage.setItem(LESSON_OWNERSHIP_KEY, JSON.stringify(ownership));
}
