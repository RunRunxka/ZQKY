export type ExtensionKind = 'mcp' | 'skill';
export interface ExtensionEntry {
  id: string;
  kind: ExtensionKind;
  name: string;
  description: string;
  content: string;
  enabled: boolean;
}
const KEY = 'zqky.replica.extensions.v1';
const EVENT = 'zqky:extensions';
export function readExtensions(): ExtensionEntry[] {
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return [];
  const parsed: unknown = JSON.parse(raw);
  if (
    !Array.isArray(parsed) ||
    !parsed.every(
      (item) =>
        item &&
        typeof item.id === 'string' &&
        (item.kind === 'mcp' || item.kind === 'skill') &&
        typeof item.name === 'string' &&
        typeof item.description === 'string' &&
        typeof item.content === 'string' &&
        typeof item.enabled === 'boolean',
    )
  )
    throw new Error('扩展目录格式不兼容，原数据已保留。');
  return parsed;
}
export function saveExtension(entry: ExtensionEntry) {
  const next = readExtensions().filter((item) => item.id !== entry.id);
  if (!entry.name.trim()) throw new Error('请输入名称。');
  if (next.some((item) => item.kind === entry.kind && item.name === entry.name))
    throw new Error('名称已存在。');
  window.localStorage.setItem(KEY, JSON.stringify([...next, entry]));
  window.dispatchEvent(new Event(EVENT));
}
export function removeExtension(id: string) {
  window.localStorage.setItem(
    KEY,
    JSON.stringify(readExtensions().filter((item) => item.id !== id)),
  );
  window.dispatchEvent(new Event(EVENT));
}
export function subscribeExtensions(listener: () => void) {
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
