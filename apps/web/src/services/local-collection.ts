/**
 * 本地集合存储统一加固（GAP_AUDIT ①，R27 同类缺陷的跨库修复）：
 * - 读取：键不存在才返回空数组；JSON 损坏 / 非数组 / 存储拒绝一律抛
 *   CollectionStorageError，绝不把损坏库当空库（防止下一次写入覆盖可恢复数据）。
 * - 写入：先严格校验（读取抛错则不写入），再写入；写入失败回滚原字节并抛错。
 * 各仓储保留自身的事件通知与条目级过滤，只委托读取/写入。
 */

export class CollectionStorageError extends Error {}

export function readStrictList<T>(key: string): T[] {
  if (typeof window === 'undefined') return [];
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(key);
  } catch (cause) {
    throw new CollectionStorageError(`本地数据（${key}）读取被拒绝，原数据未修改。`, { cause });
  }
  if (raw === null) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new CollectionStorageError(`本地数据（${key}）已损坏，无法安全解析；为保护原数据未做修改。`);
  }
  if (!Array.isArray(parsed)) {
    throw new CollectionStorageError(`本地数据（${key}）格式异常（应为数组）；为保护原数据未做修改。`);
  }
  return parsed as T[];
}

export function writeStrictList<T>(key: string, list: T[]): void {
  if (typeof window === 'undefined') return;
  readStrictList(key); // 写前严格校验：损坏即抛错，不进入写入
  const original = window.localStorage.getItem(key);
  try {
    window.localStorage.setItem(key, JSON.stringify(list));
  } catch (cause) {
    if (original !== null) {
      try {
        window.localStorage.setItem(key, original);
      } catch {
        // 回滚失败保留现场，仍抛出原始错误
      }
    }
    throw new CollectionStorageError(`写入本地数据（${key}）失败（存储可能已满）；本次修改已回滚，原数据保留。`, { cause });
  }
}
