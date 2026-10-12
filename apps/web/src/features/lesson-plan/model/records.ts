/** 记录判定的小工具（多处共用，避免每个模块各写一份）。 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
