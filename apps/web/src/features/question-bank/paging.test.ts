import { describe, expect, it } from 'vitest';
import { offsetOf, pageOf, pageWindow, totalPagesOf } from './paging';

describe('分页窗口', () => {
  it('首页与末页始终在内，跳过区间用省略号', () => {
    expect(pageWindow(1, 7)).toEqual([1, 2, 'gap', 7]);
    expect(pageWindow(4, 7)).toEqual([1, 'gap', 3, 4, 5, 'gap', 7]);
    expect(pageWindow(7, 7)).toEqual([1, 'gap', 6, 7]);
  });

  it('页数很少时不出现省略号', () => {
    expect(pageWindow(2, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(1, 1)).toEqual([1]);
  });

  it('越界当前页收敛到合法范围；无页时返回空数组', () => {
    expect(pageWindow(99, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(0, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(1, 0)).toEqual([]);
  });

  it('总数/页码/offset 互转（空列表也按第 1 页显示）', () => {
    expect(totalPagesOf(128, 20)).toBe(7);
    expect(totalPagesOf(0, 20)).toBe(1);
    expect(offsetOf(3, 20)).toBe(40);
    expect(pageOf(40, 20)).toBe(3);
    expect(pageOf(0, 20)).toBe(1);
  });
});
