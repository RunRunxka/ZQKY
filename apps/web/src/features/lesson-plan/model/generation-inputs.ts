/** 按教案键持久化的生成前置选择（P2 修复：Provider 重挂载不再静默清空）。
 *
 * `ServerControls` 位于 `LessonPlanProvider`（key=mode|documentId|revisionId）之内，
 * 创建/导入后台稿、切换文档、打开历史或浏览器刷新都会整树重挂载，把
 * `useState(initialGenerationInputs)` 的报告外选择（模型/时长/教师要求/固定题/固定练习）
 * 静默归零。这里提供模块级内存 Map + localStorage 双层缓存：同会话重挂载走内存，
 * F5 刷新走 localStorage 显式键；任一层读取失败或结构损坏按缺失处理，
 * 绝不写入破坏其他键。
 */
import type { LessonEvidenceView } from '@/contracts/lesson-plans';

export interface GenerationInputs {
  modelProfileId: string;
  requirements: string;
  durationMinutes: number;
  evidence: LessonEvidenceView | null;
  questionRevisionIds: string[];
  practiceRevisionIds: string[];
  classReady: boolean;
}

export const initialGenerationInputs: GenerationInputs = {
  modelProfileId: '', requirements: '', durationMinutes: 40,
  evidence: null, questionRevisionIds: [], practiceRevisionIds: [], classReady: false,
};

/** 本机（无后台文档）会话的固定桶；创建/导入成功后经 adopt 携带到新教案键。 */
export const LOCAL_INPUTS_BUCKET = 'local';

const STORAGE_KEY = 'zhiqikeyuan:lesson-plan:generation-inputs:v1';
const MEMORY_LIMIT = 12;
const storage = () => (typeof localStorage === 'undefined' ? null : localStorage);
const memory = new Map<string, GenerationInputs>();

function valid(value: unknown): value is GenerationInputs {
  return !!value && typeof value === 'object' && typeof (value as GenerationInputs).modelProfileId === 'string'
    && typeof (value as GenerationInputs).requirements === 'string'
    && typeof (value as GenerationInputs).durationMinutes === 'number'
    && Array.isArray((value as GenerationInputs).questionRevisionIds)
    && Array.isArray((value as GenerationInputs).practiceRevisionIds)
    && typeof (value as GenerationInputs).classReady === 'boolean';
}

function readStore(): Record<string, unknown> {
  const raw = storage()?.getItem(STORAGE_KEY) ?? null;
  if (raw === null) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
  } catch { return {}; }
}

function writeStore(key: string, value: GenerationInputs | null) {
  try {
    const store = readStore();
    if (value === null) delete store[key];
    else {
      store[key] = value;
      // 只按最近写入保留有限个桶，刚写入的键永不淘汰。
      const keys = Object.keys(store).filter((name) => name !== key);
      const excess = keys.length + 1 - MEMORY_LIMIT;
      for (const name of excess > 0 ? keys.slice(0, excess) : []) delete store[name];
    }
    storage()?.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch { /* 存储不可用时保留内存层；写入失败不中断教师输入。 */ }
}

function remember(key: string, value: GenerationInputs | null) {
  if (value === null) memory.delete(key);
  else {
    memory.delete(key);
    memory.set(key, value);
    while (memory.size > MEMORY_LIMIT) {
      const oldest = memory.keys().next().value;
      if (oldest === undefined || oldest === key) break;
      memory.delete(oldest as string);
    }
  }
}

export function readGenerationInputs(key: string): GenerationInputs {
  const cached = memory.get(key);
  if (cached) return cached;
  const stored = readStore()[key];
  if (valid(stored)) {
    memory.set(key, stored);
    return stored;
  }
  return { ...initialGenerationInputs };
}

export function writeGenerationInputs(key: string, value: GenerationInputs) {
  remember(key, value);
  writeStore(key, value);
}

/** 新建/导入后台教案成功：把来源会话的教师自有选择带到新教案键；
 * 证据绑定原会话核验、资格须重新核验，因此 evidence 清空、classReady 置 false。 */
export function adoptGenerationInputs(fromKey: string, toKey: string) {
  if (fromKey === toKey) return;
  const source = readGenerationInputs(fromKey);
  writeGenerationInputs(toKey, { ...source, evidence: null, classReady: false });
}

/** 教案彻底删除后清掉对应桶；当前会话若仍持有该键，下次读取回落初始值。 */
export function clearGenerationInputs(key: string) {
  remember(key, null);
  writeStore(key, null);
}
