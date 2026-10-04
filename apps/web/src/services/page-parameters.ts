/** Server route parameters; duplicate fixed identities are never guessed. */
export type SearchParameters = Record<string, string | string[] | undefined>;
export function pageParameters(query: SearchParameters, keys: string[]) {
  const values: Record<string, string | undefined> = {};
  for (const key of keys) {
    const value = query[key];
    if (value !== undefined && (Array.isArray(value) || !value.trim() || value !== value.trim() || value.length > 200)) {
      return { values, error: `打开地址中的 ${key} 无效或重复，请从固定记录重新打开。` };
    }
    values[key] = value;
  }
  return { values, error: null };
}
