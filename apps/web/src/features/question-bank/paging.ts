/**
 * 分页窗口（纯函数，可单测；R4-FE 2026-10-11）。
 *
 * 参考图样式：上一页 / 页码 / 省略号 / 下一页。窗口规则：
 * - 始终包含第 1 页与最后一页；
 * - 当前页前后各保留一页；
 * - 被跳过的区间用 `'gap'` 表示（渲染成省略号），绝不把跳过的页码画成可点页。
 */

export type PageItem = number | 'gap';

export function pageWindow(current: number, totalPages: number): PageItem[] {
  if (!Number.isFinite(totalPages) || totalPages < 1) return [];
  const last = Math.floor(totalPages);
  const active = Math.min(Math.max(Math.floor(current), 1), last);
  const wanted = new Set<number>([1, last, active - 1, active, active + 1]);
  const pages = [...wanted].filter((page) => page >= 1 && page <= last).sort((a, b) => a - b);
  const items: PageItem[] = [];
  let previous = 0;
  for (const page of pages) {
    if (previous && page - previous > 1) items.push('gap');
    items.push(page);
    previous = page;
  }
  return items;
}

/** 总页数：总数 / 每页条数（至少 1 页，空列表也为 1 页，便于「共 0 条记录」显示）。 */
export function totalPagesOf(total: number, pageSize: number): number {
  if (!Number.isFinite(total) || total <= 0 || pageSize <= 0) return 1;
  return Math.ceil(total / pageSize);
}

/** 当前页（从 1 开始）对应的 offset，用于请求。 */
export function offsetOf(page: number, pageSize: number): number {
  return Math.max(0, (Math.max(1, Math.floor(page)) - 1) * pageSize);
}

/** 当前 offset 对应的页码（服务端 offset 与本地页码互转，只认 offset 的整数倍）。 */
export function pageOf(offset: number, pageSize: number): number {
  if (!Number.isFinite(offset) || offset <= 0 || pageSize <= 0) return 1;
  return Math.floor(offset / pageSize) + 1;
}
