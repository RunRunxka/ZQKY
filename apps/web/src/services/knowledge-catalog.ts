/**
 * 知识来源目录（S2 输入区，演示数据仓储）。
 *
 * 知识来源是会话级检索范围声明（对照参考 KnowledgeSelector 的会话级语义）。
 * 目标项目尚无真实知识库/RAG 服务（对应 /knowledge-bases 业务页在 S5 实施），
 * 这里提供与 extension-catalog 同构的本地演示目录：显式“载入演示数据”入口、
 * localStorage 持久化、跨组件订阅。选择知识来源仅声明范围，模拟侧如实说明
 * “未执行真实检索”。
 */
export interface KnowledgeEntry {
  id: string;
  name: string;
  description: string;
  /** S5-B：默认库（唯一；新建不自动设默认） */
  isDefault?: boolean;
  /** S5-B：登记的文档（本地登记，不解析不索引） */
  docs?: KbDocument[];
  /** S5-B：登记的外部源（github/web，仅登记不同步） */
  sources?: KbExternalSource[];
  /** B-H1-KB：模拟索引版本（旧数据缺省归一化为 []，不写库） */
  indexVersions?: KbIndexVersion[];
  createdAt?: string;
  updatedAt?: string;
}

/** B-H1-KB：文档入库流水线状态（解析/索引为显式模拟） */
export type KbDocStatus = 'registered' | 'parsing' | 'indexing' | 'ready' | 'error';

/** B-H1-KB：进度表示（字段对齐参考 ProgressInfo 的可见子集） */
export interface KbDocProgress {
  /** 中文阶段名，如「解析中」「切片」「向量化」 */
  stage: string;
  /** 0-100 */
  percent: number;
  current?: number;
  total?: number;
}

/** 登记文档：目标项目无解析/索引服务，登记仅保存元信息并显式标注未解析 */
export interface KbDocument {
  id: string;
  name: string;
  /** 字节数（选取文件时读取；演示数据缺省） */
  size?: number;
  registeredAt: string;
  // ===== B-H1-KB 新增，全部可选；旧数据缺省归一化 =====
  /** 缺省 'registered'（旧记录含义不变：未解析 · 未索引） */
  status?: KbDocStatus;
  /** 失败/取消说明 */
  statusNote?: string | null;
  progress?: KbDocProgress | null;
  /** 模拟解析产出的字符数（显式模拟，不读取真实文件内容） */
  parsedChars?: number;
  /** 模拟切片数 */
  chunks?: number;
}

/** B-H1-KB：索引版本（模拟；字段对齐参考 IndexVersion） */
export interface KbIndexVersion {
  id: string;
  /** 从 1 递增 */
  version: number;
  createdAt: string;
  docCount: number;
  chunkCount: number;
  /** 例：'内置本地索引（模拟）' */
  provider: string;
  ready: boolean;
  note?: string | null;
}

/** 外部源登记（参考的 GitHub/网页源同步依赖后端，这里仅登记并显式说明） */
export interface KbExternalSource {
  id: string;
  kind: 'github' | 'web';
  /** 仓库地址或网页 URL */
  ref: string;
  registeredAt: string;
}
const KEY = 'zqky.replica.knowledge.v1';
const EVENT = 'zqky:knowledge';

export const DEMO_KNOWLEDGE: KnowledgeEntry[] = [
  {
    id: 'demo-kb-curriculum',
    name: '课程标准库',
    description: '义务教育与高中课程标准摘要（演示数据，无真实检索）。',
    isDefault: true,
    docs: [
      { id: 'demo-doc-std-math', name: '义务教育数学课程标准（摘录）.md', size: 18432, registeredAt: '2026-09-01T08:00:00.000Z' },
      { id: 'demo-doc-std-chinese', name: '义务教育语文课程标准（摘录）.md', size: 16210, registeredAt: '2026-09-01T08:05:00.000Z' },
    ],
    sources: [{ id: 'demo-src-curriculum', kind: 'web', ref: 'https://example.com/curriculum-standard', registeredAt: '2026-09-01T08:10:00.000Z' }],
  },
  {
    id: 'demo-kb-teaching',
    name: '教学设计案例库',
    description: '校本教研中的教学设计示例（演示数据，无真实检索）。',
    docs: [{ id: 'demo-doc-case-1', name: '《背影》教学设计案例.md', size: 9877, registeredAt: '2026-09-02T09:00:00.000Z' }],
  },
];

function validate(parsed: unknown): KnowledgeEntry[] {
  if (
    !Array.isArray(parsed) ||
    !parsed.every(
      (item) =>
        item &&
        typeof item.id === 'string' &&
        typeof item.name === 'string' &&
        typeof item.description === 'string',
    )
  )
    throw new Error('知识来源目录格式不兼容，原数据已保留。');
  return parsed;
}

/**
 * B-H1-KB：读取归一化。仅归一化内存中的返回对象，不写回 localStorage
 * （避免干扰用户已有数据）：`indexVersions ?? []`、每个 doc `status ?? 'registered'`。
 */
function normalizeEntry(entry: KnowledgeEntry): KnowledgeEntry {
  return {
    ...entry,
    indexVersions: entry.indexVersions ?? [],
    docs: entry.docs?.map((doc) => ({ ...doc, status: doc.status ?? 'registered' })),
  };
}

export function readKnowledge(): KnowledgeEntry[] {
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // 结构损坏不能当空库覆盖：抛出统一说明，调用方如实提示且不写库
    throw new Error('知识来源目录格式不兼容，原数据已保留。');
  }
  return validate(parsed).map(normalizeEntry);
}

export function loadDemoKnowledge() {
  const existing = readKnowledge();
  const merged = [...existing];
  for (const demo of DEMO_KNOWLEDGE) {
    if (!merged.some((item) => item.id === demo.id)) merged.push(demo);
  }
  window.localStorage.setItem(KEY, JSON.stringify(merged));
  window.dispatchEvent(new Event(EVENT));
}

// ===== S5-B 业务页操作 =====

export class KnowledgeValidationError extends Error {}

function writeKnowledge(list: KnowledgeEntry[]): void {
  window.localStorage.setItem(KEY, JSON.stringify(list));
  window.dispatchEvent(new Event(EVENT));
}

function findNameClash(list: KnowledgeEntry[], name: string, excludeId?: string): boolean {
  return list.some((kb) => kb.id !== excludeId && kb.name === name);
}

/** 新建知识库（本地目录；重名拒绝） */
export function createKnowledge(name: string, description: string): KnowledgeEntry {
  const trimmed = name.trim();
  if (!trimmed) throw new KnowledgeValidationError('名称不能为空。');
  if (trimmed.length > 60) throw new KnowledgeValidationError('名称过长（不超过 60 字）。');
  const list = readKnowledge();
  if (findNameClash(list, trimmed))
    throw new KnowledgeValidationError('已存在同名知识库，请换一个名称。');
  const now = new Date().toISOString();
  const entry: KnowledgeEntry = {
    id: `kb-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name: trimmed,
    description: description.trim(),
    docs: [],
    sources: [],
    createdAt: now,
    updatedAt: now,
  };
  writeKnowledge([...list, entry]);
  return entry;
}

export function updateKnowledge(
  id: string,
  patch: { name?: string; description?: string },
): KnowledgeEntry {
  const list = readKnowledge();
  const idx = list.findIndex((kb) => kb.id === id);
  if (idx === -1) throw new KnowledgeValidationError('知识库不存在或已被删除。');
  if (patch.name !== undefined) {
    const trimmed = patch.name.trim();
    if (!trimmed) throw new KnowledgeValidationError('名称不能为空。');
    if (findNameClash(list, trimmed, id))
      throw new KnowledgeValidationError('已存在同名知识库，请换一个名称。');
    list[idx] = { ...list[idx]!, name: trimmed };
  }
  if (patch.description !== undefined)
    list[idx] = { ...list[idx]!, description: patch.description.trim() };
  list[idx] = { ...list[idx]!, updatedAt: new Date().toISOString() };
  writeKnowledge(list);
  return list[idx]!;
}

/** 删除知识库；默认库被删后不自动指定新默认 */
export function deleteKnowledge(id: string): boolean {
  const list = readKnowledge();
  const kept = list.filter((kb) => kb.id !== id);
  if (kept.length === list.length) return false;
  writeKnowledge(kept);
  return true;
}

/** 设为默认库（唯一；重复设置幂等） */
export function setDefaultKnowledge(id: string): void {
  const list = readKnowledge();
  for (const kb of list) kb.isDefault = kb.id === id;
  writeKnowledge(list);
}

function mutateEntry(id: string, mutate: (entry: KnowledgeEntry) => KnowledgeEntry): KnowledgeEntry | null {
  const list = readKnowledge();
  const idx = list.findIndex((kb) => kb.id === id);
  if (idx === -1) return null;
  list[idx] = { ...mutate(list[idx]!), updatedAt: new Date().toISOString() };
  writeKnowledge(list);
  return list[idx]!;
}

/** 登记文档（仅元信息；显式"未解析/未索引"，status 归一为 registered） */
export function addKbDocument(kbId: string, doc: { name: string; size?: number }): KbDocument | null {
  const trimmed = doc.name.trim();
  if (!trimmed) return null;
  const record: KbDocument = {
    id: `doc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name: trimmed,
    ...(doc.size !== undefined ? { size: doc.size } : {}),
    registeredAt: new Date().toISOString(),
    status: 'registered',
  };
  const entry = mutateEntry(kbId, (kb) => ({ ...kb, docs: [...(kb.docs ?? []), record] }));
  return entry ? record : null;
}

/**
 * B-H1-KB：局部更新某文档（模拟流水线推进用）。
 * 返回更新后的 doc；库或文档不存在返回 null。
 */
export function updateKbDocument(
  kbId: string,
  docId: string,
  patch: Partial<Pick<KbDocument, 'status' | 'statusNote' | 'progress' | 'parsedChars' | 'chunks'>>,
): KbDocument | null {
  const kb = readKnowledge().find((item) => item.id === kbId);
  if (!kb) return null;
  const doc = (kb.docs ?? []).find((item) => item.id === docId);
  if (!doc) return null;
  const updated: KbDocument = { ...doc, ...patch };
  mutateEntry(kbId, (entry) => ({
    ...entry,
    docs: (entry.docs ?? []).map((item) => (item.id === docId ? updated : item)),
  }));
  return updated;
}

/** B-H1-KB：追加模拟索引版本；version = (max 现有 version) + 1 */
export function addKbIndexVersion(
  kbId: string,
  input: { docCount: number; chunkCount: number; provider: string; note?: string | null },
): KbIndexVersion | null {
  const existing = readKnowledge().find((kb) => kb.id === kbId);
  if (!existing) return null;
  const maxVersion = (existing.indexVersions ?? []).reduce(
    (max, version) => Math.max(max, version.version),
    0,
  );
  const record: KbIndexVersion = {
    id: `idx-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    version: maxVersion + 1,
    createdAt: new Date().toISOString(),
    docCount: input.docCount,
    chunkCount: input.chunkCount,
    provider: input.provider,
    ready: true,
    ...(input.note !== undefined ? { note: input.note } : {}),
  };
  const entry = mutateEntry(kbId, (kb) => ({
    ...kb,
    indexVersions: [...(kb.indexVersions ?? []), record],
  }));
  return entry ? record : null;
}

/** B-H1-KB：UI 徽标/进度用汇总；纯函数，无副作用 */
export interface KbPipelineSummary {
  total: number;
  ready: number;
  error: number;
  active: number;
  status: 'empty' | 'registered' | 'processing' | 'ready' | 'error';
}

export function kbPipelineSummary(kb: KnowledgeEntry): KbPipelineSummary {
  const docs = kb.docs ?? [];
  const total = docs.length;
  const ready = docs.filter((doc) => doc.status === 'ready').length;
  const error = docs.filter((doc) => doc.status === 'error').length;
  const active = docs.filter((doc) => doc.status === 'parsing' || doc.status === 'indexing').length;
  let status: KbPipelineSummary['status'];
  if (total === 0) status = 'empty';
  else if (active > 0) status = 'processing';
  else if (error > 0) status = 'error';
  else if (ready === total) status = 'ready';
  else status = 'registered';
  return { total, ready, error, active, status };
}

export function removeKbDocument(kbId: string, docId: string): boolean {
  const entry = mutateEntry(kbId, (kb) => ({
    ...kb,
    docs: (kb.docs ?? []).filter((doc) => doc.id !== docId),
  }));
  return entry !== null;
}

/** 登记外部源（github/web；不执行同步） */
export function addKbSource(
  kbId: string,
  kind: 'github' | 'web',
  ref: string,
): KbExternalSource | null {
  const trimmed = ref.trim();
  if (!trimmed) return null;
  const record: KbExternalSource = {
    id: `src-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    kind,
    ref: trimmed,
    registeredAt: new Date().toISOString(),
  };
  const entry = mutateEntry(kbId, (kb) => ({
    ...kb,
    sources: [...(kb.sources ?? []), record],
  }));
  return entry ? record : null;
}

export function removeKbSource(kbId: string, sourceId: string): boolean {
  const entry = mutateEntry(kbId, (kb) => ({
    ...kb,
    sources: (kb.sources ?? []).filter((source) => source.id !== sourceId),
  }));
  return entry !== null;
}

export function subscribeKnowledge(listener: () => void) {
  const storage = (event: StorageEvent) => {
    if (event.key === KEY || event.key === null) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}
