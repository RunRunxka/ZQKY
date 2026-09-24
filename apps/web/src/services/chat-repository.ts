import type { Conversation, ConversationMeta } from '@/contracts/chat';

export class ChatStorageConflict extends Error {
  constructor() {
    super('此会话已在其他标签页更新。当前内容已保留，请备份后重新载入。');
  }
}
export interface ChatRepository {
  list(): Promise<ConversationMeta[]>;
  load(id: string): Promise<Conversation | null>;
  save(conversation: Conversation, expectedRevision?: number): Promise<number>;
  remove(id: string, expectedRevision?: number): Promise<void>;
}
export function normalizeConversation(value: Conversation): Conversation {
  if (
    !value ||
    typeof value.id !== 'string' ||
    typeof value.title !== 'string' ||
    !Array.isArray(value.messages) ||
    (value.schemaVersion !== undefined && value.schemaVersion !== 1) ||
    value.messages.some(
      (m) =>
        !m ||
        typeof m.id !== 'string' ||
        typeof m.content !== 'string' ||
        !['user', 'assistant', 'system'].includes(m.role),
    )
  ) {
    throw new Error('对话数据格式不受支持，原记录未被修改。');
  }
  const normalized: Conversation = {
    ...value,
    schemaVersion: 1,
    revision: value.revision ?? 0,
    draft: value.draft ?? '',
    modelProfileId: value.modelProfileId ?? null,
  };
  // 课程归属（H1-COURSE-SESSIONS v1）：只保留非空字符串；缺失/空串 = 未归属。
  // 旧记录缺该字段照常读、不写回、不按标题/最近访问猜测归属。
  if (typeof value.courseId === 'string' && value.courseId) {
    normalized.courseId = value.courseId;
  } else {
    delete normalized.courseId;
  }
  return normalized;
}
export function toMeta(c: Conversation): ConversationMeta {
  return {
    id: c.id,
    title: c.title,
    messageCount: c.messages.length,
    createdAt: c.createdAt,
    updatedAt: c.updatedAt,
    ...(c.courseId ? { courseId: c.courseId } : {}),
  };
}
export function createIdbChatRepository(dbName = 'zhiqikeyuan-chat'): ChatRepository {
  let dbPromise: Promise<IDBDatabase> | null = null;
  function open() {
    if (!dbPromise)
      dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
        const request = indexedDB.open(dbName, 1);
        request.onupgradeneeded = () =>
          request.result.createObjectStore('conversations', { keyPath: 'id' });
        request.onsuccess = () => {
          request.result.onversionchange = () => {
            request.result.close();
            dbPromise = null;
          };
          resolve(request.result);
        };
        request.onerror = () => {
          dbPromise = null;
          reject(request.error);
        };
        request.onblocked = () => reject(new Error('请关闭旧标签页后重试。'));
      });
    return dbPromise;
  }
  async function read<T>(run: (store: IDBObjectStore) => IDBRequest): Promise<T> {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('conversations', 'readonly');
      const req = run(tx.objectStore('conversations'));
      tx.oncomplete = () => resolve(req.result as T);
      tx.onabort = tx.onerror = () => reject(tx.error ?? req.error ?? new Error('读取失败。'));
    });
  }
  async function mutate(
    id: string,
    value: Conversation | null,
    expected?: number,
  ): Promise<number> {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('conversations', 'readwrite');
      const store = tx.objectStore('conversations');
      let revision = 0,
        failure: Error | null = null;
      const req = store.get(id);
      req.onsuccess = () => {
        try {
          const old = req.result ? normalizeConversation(req.result) : null;
          if (expected !== undefined && (old?.revision ?? 0) !== expected)
            throw new ChatStorageConflict();
          revision = (old?.revision ?? 0) + 1;
          if (value) store.put({ ...normalizeConversation(value), revision });
          else store.delete(id);
        } catch (error) {
          failure = error as Error;
          tx.abort();
        }
      };
      tx.oncomplete = () => resolve(revision);
      tx.onabort = tx.onerror = () => reject(failure ?? tx.error ?? new Error('保存失败。'));
    });
  }
  return {
    async list() {
      return (await read<Conversation[]>((s) => s.getAll()))
        .map(normalizeConversation)
        .map(toMeta)
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },
    async load(id) {
      const c = await read<Conversation | undefined>((s) => s.get(id));
      return c ? normalizeConversation(c) : null;
    },
    save(c, expected) {
      return mutate(c.id, structuredClone(c), expected);
    },
    async remove(id, expected) {
      await mutate(id, null, expected);
    },
  };
}
export function createMemoryChatRepository(): ChatRepository {
  const docs = new Map<string, Conversation>();
  return {
    async list() {
      return [...docs.values()].map(toMeta).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },
    async load(id) {
      return docs.has(id) ? structuredClone(docs.get(id)!) : null;
    },
    async save(c, expected) {
      const old = docs.get(c.id);
      if (expected !== undefined && (old?.revision ?? 0) !== expected)
        throw new ChatStorageConflict();
      const revision = (old?.revision ?? 0) + 1;
      docs.set(c.id, structuredClone({ ...normalizeConversation(c), revision }));
      return revision;
    },
    async remove(id, expected) {
      if (expected !== undefined && (docs.get(id)?.revision ?? 0) !== expected)
        throw new ChatStorageConflict();
      docs.delete(id);
    },
  };
}
