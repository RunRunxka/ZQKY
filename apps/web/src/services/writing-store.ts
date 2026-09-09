/**
 * 协同写作本地仓储（S5-E）。真实多人文档服务未接入：文档、版本与草稿本地持久化，
 * AI 修改为统一事件模型的显式模拟（见 writing-ai.ts）。
 * 存储采用与 reading-store 相同的加固模式：严格读取（损坏/格式异常抛错不覆盖）、
 * 单批原子提交带回滚（R27 同类缺陷在本库从源头避免）。
 */

export interface WritingDocumentVersion {
  versionId: string;
  content: string;
  label: string;
  savedAt: string;
}

export interface WritingDocument {
  docId: string;
  title: string;
  content: string;
  versions: WritingDocumentVersion[];
  createdAt: string;
  updatedAt: string;
}

const DOCS_KEY = 'zhiqikeyuan:writing-docs';
const EVENT = 'zqky:writing';

export class WritingValidationError extends Error {}
export class WritingStorageError extends Error {}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function readList(): WritingDocument[] {
  if (typeof window === 'undefined') return [];
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(DOCS_KEY);
  } catch (cause) {
    throw new WritingStorageError('写作文档读取被拒绝，原数据未修改。', { cause });
  }
  if (raw === null) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new WritingStorageError('写作文档数据已损坏，无法安全解析；为保护原数据未做修改。');
  }
  if (!Array.isArray(parsed)) throw new WritingStorageError('写作文档数据格式异常（应为数组）；为保护原数据未做修改。');
  return parsed.filter(
    (item): item is WritingDocument => Boolean(item) && typeof item.docId === 'string' && typeof item.title === 'string',
  );
}

function commit(list: WritingDocument[]): void {
  if (typeof window === 'undefined') return;
  readList(); // 写前严格校验
  const original = window.localStorage.getItem(DOCS_KEY);
  try {
    window.localStorage.setItem(DOCS_KEY, JSON.stringify(list));
  } catch (cause) {
    if (original !== null) {
      try {
        window.localStorage.setItem(DOCS_KEY, original);
      } catch {
        // 回滚失败保留现场
      }
    }
    throw new WritingStorageError('写入写作文档失败（存储可能已满）；本次修改已回滚，原数据保留。', { cause });
  }
  notify();
}

function notify(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(EVENT));
}

export function subscribeWriting(listener: () => void): () => void {
  const storage = (event: StorageEvent) => {
    if (event.key === EVENT || event.key === null || event.key?.startsWith('zhiqikeyuan:writing')) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}

export function listDocuments(): WritingDocument[] {
  return readList().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getDocument(docId: string): WritingDocument | null {
  return readList().find((doc) => doc.docId === docId) ?? null;
}

const SAMPLE_TEMPLATE = [
  '# 教学设计示例（模板）',
  '',
  '## 教学目标',
  '',
  '- 理解核心概念并能举例说明；',
  '- 完成基础练习，正确率 80% 以上。',
  '',
  '## 教学过程',
  '',
  '1. 情境导入：用生活实例引出主题；',
  '2. 新知讲解：拆解概念与依据；',
  '3. 巩固练习：课堂小练 + 讲评。',
].join('\n');

export function createDocument(input: { title?: string; withTemplate?: boolean }): WritingDocument {
  const now = new Date().toISOString();
  const title = (input.title ?? '').trim() || '未命名文稿';
  const doc: WritingDocument = {
    docId: uid('doc'),
    title,
    content: input.withTemplate ? SAMPLE_TEMPLATE : '',
    versions: [],
    createdAt: now,
    updatedAt: now,
  };
  commit([...readList(), doc]);
  return doc;
}

/** 自动保存正文（autosave 防抖后调用；内容不变则跳过） */
export function saveDocumentContent(docId: string, content: string): WritingDocument | null {
  const list = readList();
  const idx = list.findIndex((doc) => doc.docId === docId);
  if (idx === -1) return null;
  if (list[idx]!.content === content) return list[idx]!;
  list[idx] = { ...list[idx]!, content, updatedAt: new Date().toISOString() };
  commit(list);
  return list[idx]!;
}

export function renameDocument(docId: string, title: string): WritingDocument | null {
  const trimmed = title.trim();
  if (!trimmed) throw new WritingValidationError('文稿标题不能为空。');
  const list = readList();
  const idx = list.findIndex((doc) => doc.docId === docId);
  if (idx === -1) return null;
  list[idx] = { ...list[idx]!, title: trimmed, updatedAt: new Date().toISOString() };
  commit(list);
  return list[idx]!;
}

export function deleteDocument(docId: string): boolean {
  const list = readList();
  const kept = list.filter((doc) => doc.docId !== docId);
  if (kept.length === list.length) return false;
  commit(kept);
  return true;
}

/** 快照当前内容为版本（AI 应用前自动快照；也可手动保存） */
export function snapshotVersion(docId: string, label: string): WritingDocumentVersion | null {
  const list = readList();
  const idx = list.findIndex((doc) => doc.docId === docId);
  if (idx === -1) return null;
  const doc = list[idx]!;
  const version: WritingDocumentVersion = {
    versionId: uid('ver'),
    content: doc.content,
    label: label.trim() || '手动版本',
    savedAt: new Date().toISOString(),
  };
  list[idx] = { ...doc, versions: [...doc.versions, version], updatedAt: new Date().toISOString() };
  commit(list);
  return version;
}

/** 恢复版本：当前内容先自动快照，再写回版本内容（可再恢复回来，不丢失） */
export function restoreVersion(docId: string, versionId: string): WritingDocument | null {
  const list = readList();
  const idx = list.findIndex((doc) => doc.docId === docId);
  if (idx === -1) return null;
  const doc = list[idx]!;
  const version = doc.versions.find((item) => item.versionId === versionId);
  if (!version) return null;
  if (doc.content !== version.content) snapshotVersion(docId, `恢复前自动快照（${new Date().toLocaleString('zh-CN')}）`);
  const next = readList();
  const nextIdx = next.findIndex((item) => item.docId === docId);
  next[nextIdx] = {
    ...next[nextIdx]!,
    content: version.content,
    updatedAt: new Date().toISOString(),
  };
  commit(next);
  return next[nextIdx]!;
}
