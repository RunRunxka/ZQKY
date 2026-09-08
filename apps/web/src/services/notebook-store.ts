'use client';
/**
 * S5-B 笔记本本地仓储（对照参考 NotebookSummary / NotebookRecordItem）。
 *
 * 记录与聊天"保存到笔记"共用 `zhiqikeyuan:notebook-entries`（space-store 的
 * NotebookEntry 即保存的产出，对应参考 NotebookRecordItem 的语义——参考仓库
 * 中题库条目 NotebookEntry 是另一套数字 id 模型，勿混淆）。本仓储在其上补充
 * 笔记本维度：缺省 notebookId 的记录归入默认笔记本「学习笔记」。
 *
 * 参考中记录由聊天/研究/写作等功能产生，控制台不提供"新建记录"——这里同样
 * 不臆造该入口；本地操作覆盖：新建/重命名/删除笔记本、编辑/删除/移动/复制/
 * 导出记录。
 */

const NOTEBOOKS_KEY = 'zhiqikeyuan:notebooks';
const RECORDS_KEY = 'zhiqikeyuan:notebook-entries';
const EVENT = 'zqky:notebooks';

export const DEFAULT_NOTEBOOK_ID = 'notebook-main';

export type NotebookColor = 'blue' | 'green' | 'amber' | 'purple' | 'gray';

export const NOTEBOOK_COLORS: NotebookColor[] = ['blue', 'green', 'amber', 'purple', 'gray'];

/** 笔记本（对照参考 NotebookSummary） */
export interface Notebook {
  id: string;
  name: string;
  description: string;
  color: NotebookColor;
  createdAt: string;
  updatedAt: string;
}

/** 记录（保存的产出；兼容 space-store NotebookEntry 的字段并按需补齐） */
export interface NotebookRecord {
  id: string;
  notebookId: string;
  /** 记录类型：research_report / chat 等（对照参考 NotebookRecordType） */
  type: string;
  title: string;
  summary?: string;
  /** 产生该记录时的用户提问（可选，聊天类型展示） */
  userQuery?: string;
  content: string;
  createdAt: string;
  updatedAt: string;
  metadata?: { sessionId?: string; messageId?: string; artifactId?: string };
}

function readList<T>(key: string): T[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function writeList<T>(key: string, list: T[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, JSON.stringify(list));
}

function notify(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(EVENT));
}

export function subscribeNotebooks(listener: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const storage = (event: StorageEvent) => {
    if (event.key === NOTEBOOKS_KEY || event.key === RECORDS_KEY || event.key === null) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}

// ===== 笔记本 =====

/** 全部笔记本；没有任何笔记本时自动带出默认笔记本（不写盘，直到用户首次改动） */
export function listNotebooks(): Notebook[] {
  const list = readList<Notebook>(NOTEBOOKS_KEY);
  if (list.some((n) => n.id === DEFAULT_NOTEBOOK_ID)) return list;
  return [
    {
      id: DEFAULT_NOTEBOOK_ID,
      name: '学习笔记',
      description: '聊天与研究产物默认保存位置。',
      color: 'blue',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
    ...list,
  ];
}

export function createNotebook(name: string, description = '', color: NotebookColor = 'gray'): Notebook | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  // 与有效列表（含虚拟默认笔记本）查重
  if (listNotebooks().some((n) => n.name === trimmed)) return null;
  const list = readList<Notebook>(NOTEBOOKS_KEY);
  const now = new Date().toISOString();
  const notebook: Notebook = {
    id: `nb-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name: trimmed,
    description: description.trim(),
    color,
    createdAt: now,
    updatedAt: now,
  };
  writeList(NOTEBOOKS_KEY, [...list, notebook]);
  notify();
  return notebook;
}

/** 重命名/改描述/换颜色（乐观语义由调用方负责刷新） */
export function updateNotebook(
  id: string,
  patch: { name?: string; description?: string; color?: NotebookColor },
): Notebook | null {
  const list = readList<Notebook>(NOTEBOOKS_KEY);
  const idx = list.findIndex((n) => n.id === id);
  if (idx === -1) return null;
  if (patch.name !== undefined) {
    const trimmed = patch.name.trim();
    if (!trimmed) return null;
    // 与有效列表（含虚拟默认笔记本）查重（排除自身）
    if (listNotebooks().some((n) => n.id !== id && n.name === trimmed)) return null;
  }
  list[idx] = {
    ...list[idx]!,
    ...(patch.name !== undefined ? { name: patch.name.trim() } : {}),
    ...(patch.description !== undefined ? { description: patch.description.trim() } : {}),
    ...(patch.color !== undefined ? { color: patch.color } : {}),
    updatedAt: new Date().toISOString(),
  };
  writeList(NOTEBOOKS_KEY, list);
  notify();
  return list[idx]!;
}

/** 删除笔记本：其中的记录回到默认笔记本（不静默销毁用户内容） */
export function deleteNotebook(id: string): boolean {
  if (id === DEFAULT_NOTEBOOK_ID) return false;
  const list = readList<Notebook>(NOTEBOOKS_KEY);
  const kept = list.filter((n) => n.id !== id);
  if (kept.length === list.length) return false;
  writeList(NOTEBOOKS_KEY, kept);
  const records = readList<Record<string, unknown>>(RECORDS_KEY);
  let changed = false;
  for (const record of records) {
    if (record.notebookId === id) {
      record.notebookId = DEFAULT_NOTEBOOK_ID;
      changed = true;
    }
  }
  if (changed) writeList(RECORDS_KEY, records);
  notify();
  return true;
}

// ===== 记录 =====

/** 记录标准化：补 notebookId/type/updatedAt 缺省（兼容聊天侧旧保存） */
function normalizeRecord(raw: Record<string, unknown>): NotebookRecord {
  const createdAt =
    typeof raw.createdAt === 'string' && raw.createdAt
      ? raw.createdAt
      : typeof raw.savedAt === 'string' && raw.savedAt
        ? raw.savedAt
        : new Date().toISOString();
  const metadata =
    raw.metadata && typeof raw.metadata === 'object'
      ? (raw.metadata as NotebookRecord['metadata'])
      : {
          messageId: typeof raw.messageId === 'string' ? raw.messageId : undefined,
          artifactId: typeof raw.artifactId === 'string' ? raw.artifactId : undefined,
        };
  return {
    id: String(raw.id),
    notebookId:
      typeof raw.notebookId === 'string' && raw.notebookId ? raw.notebookId : DEFAULT_NOTEBOOK_ID,
    type: typeof raw.type === 'string' && raw.type ? raw.type : 'research_report',
    title: typeof raw.title === 'string' ? raw.title : '未命名记录',
    summary: typeof raw.summary === 'string' ? raw.summary : undefined,
    userQuery: typeof raw.userQuery === 'string' ? raw.userQuery : undefined,
    content: typeof raw.content === 'string' ? raw.content : '',
    createdAt,
    updatedAt:
      typeof raw.updatedAt === 'string' && raw.updatedAt ? raw.updatedAt : createdAt,
    metadata,
  };
}

export function listRecords(): NotebookRecord[] {
  return readList<Record<string, unknown>>(RECORDS_KEY)
    .filter((raw) => raw && typeof raw.id === 'string')
    .map(normalizeRecord)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function listRecordsOf(notebookId: string): NotebookRecord[] {
  return listRecords().filter((record) => record.notebookId === notebookId);
}

/** 编辑记录（仅写变更字段；id 不可变） */
export function updateNotebookRecord(
  id: string,
  patch: { title?: string; summary?: string; content?: string; notebookId?: string },
): NotebookRecord | null {
  const records = readList<Record<string, unknown>>(RECORDS_KEY);
  const idx = records.findIndex((raw) => raw && raw.id === id);
  if (idx === -1) return null;
  const current = normalizeRecord(records[idx]!);
  records[idx] = {
    ...current,
    ...(patch.title !== undefined ? { title: patch.title.trim() || current.title } : {}),
    ...(patch.summary !== undefined ? { summary: patch.summary.trim() || undefined } : {}),
    ...(patch.content !== undefined ? { content: patch.content } : {}),
    ...(patch.notebookId !== undefined ? { notebookId: patch.notebookId } : {}),
    updatedAt: new Date().toISOString(),
  };
  writeList(RECORDS_KEY, records);
  notify();
  return normalizeRecord(records[idx]!);
}

export function removeNotebookRecord(id: string): boolean {
  const records = readList<Record<string, unknown>>(RECORDS_KEY);
  const kept = records.filter((raw) => !raw || raw.id !== id);
  if (kept.length === records.length) return false;
  writeList(RECORDS_KEY, kept);
  notify();
  return true;
}

/** 新建记录（S5-D 阅读工作区"发到笔记本"等跨页写入；目标笔记本必须存在） */
export function createNotebookRecord(input: {
  notebookId: string;
  title: string;
  content: string;
  summary?: string;
  type?: string;
  metadata?: NotebookRecord['metadata'];
}): NotebookRecord | null {
  const list = readList<Notebook>(NOTEBOOKS_KEY);
  const exists =
    input.notebookId === DEFAULT_NOTEBOOK_ID || list.some((item) => item.id === input.notebookId);
  if (!exists) return null;
  const now = new Date().toISOString();
  const record = normalizeRecord({
    id: `nbrec-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    notebookId: input.notebookId,
    type: input.type ?? 'chat',
    title: input.title.trim() || '未命名记录',
    ...(input.summary ? { summary: input.summary } : {}),
    content: input.content,
    createdAt: now,
    updatedAt: now,
    ...(input.metadata ? { metadata: input.metadata } : {}),
  });
  const records = readList<Record<string, unknown>>(RECORDS_KEY);
  writeList(RECORDS_KEY, [...records, record as unknown as Record<string, unknown>]);
  notify();
  return record;
}

/** 移动/复制记录到另一笔记本（复制生成新 id，保留来源标记） */
export function relocateRecord(
  id: string,
  targetNotebookId: string,
  mode: 'move' | 'copy',
): NotebookRecord | null {
  const records = readList<Record<string, unknown>>(RECORDS_KEY);
  const raw = records.find((item) => item && item.id === id);
  if (!raw) return null;
  const source = normalizeRecord(raw);
  if (mode === 'move') {
    return updateNotebookRecord(id, { notebookId: targetNotebookId });
  }
  const now = new Date().toISOString();
  const copy: NotebookRecord = {
    ...source,
    id: `${source.id}-copy-${Math.random().toString(36).slice(2, 8)}`,
    notebookId: targetNotebookId,
    title: `${source.title}（副本）`,
    createdAt: now,
    updatedAt: now,
    metadata: source.metadata,
  };
  writeList(RECORDS_KEY, [...records, copy]);
  notify();
  return copy;
}

/** 导出笔记本为 markdown 文本（参考 exportNotebookMarkdown 的本地形态） */
export function exportNotebookMarkdown(notebookId: string): { name: string; content: string } | null {
  const notebook = listNotebooks().find((n) => n.id === notebookId);
  if (!notebook) return null;
  const records = listRecordsOf(notebookId);
  const lines = [`# ${notebook.name}`, ''];
  if (notebook.description) lines.push(`> ${notebook.description}`, '');
  for (const record of records) {
    lines.push(`## ${record.title}`, '');
    if (record.summary) lines.push(`> ${record.summary}`, '');
    lines.push(record.content, '');
  }
  return { name: `${notebook.name}.md`, content: lines.join('\n') };
}
