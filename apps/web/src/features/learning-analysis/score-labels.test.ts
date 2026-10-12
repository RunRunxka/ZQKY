/**
 * 四态读法与计分叶纯函数（取回自归档 assessments 测试的最小集，R6-FE）。
 * 断言口径：显式 0 是有效记录、空白按 missing（绝不补 0）、缺考/免考不参与 0 分、
 * 未识别文本不猜；引用守卫计数逐项列出且未知键不隐藏。
 */

import { describe, expect, it } from 'vitest';
import {
  formatScoreUnits,
  leafLabel,
  rawCellReading,
  referenceCounts,
  scoreImportStateLabel,
  scoredLeafItems,
  shortId,
} from './score-labels';

describe('成绩四态读法', () => {
  it('显式 0 分是有效记录，不是空白', () => {
    const reading = rawCellReading({ text: '0' });
    expect(reading.kind).toBe('recorded');
    expect(reading.displayText).toBe('0');
    expect(reading.note).toBe('显式 0 分（有效记录）');
  });

  it('空白单元格按 missing 处理且不补 0', () => {
    const reading = rawCellReading({ text: '   ' });
    expect(reading.kind).toBe('missing');
    expect(reading.note).toContain('不补 0');
  });

  it('缺考 / 免考中英文标记都识别，未知文本不猜成 0', () => {
    expect(rawCellReading({ text: '缺考' }).kind).toBe('absent');
    expect(rawCellReading({ text: 'Absent' }).kind).toBe('absent');
    expect(rawCellReading({ text: '免考' }).kind).toBe('exempt');
    expect(rawCellReading({ text: 'EXEMPT' }).kind).toBe('exempt');
    const unknown = rawCellReading({ text: '未识别文本' });
    expect(unknown.kind).toBe('unparsed');
    expect(unknown.note).toBe('无法本地判读，以服务端为准');
  });

  it('服务端有效状态优先；公式单元格按缓存值预览', () => {
    const served = rawCellReading({ text: '0', effectiveStatus: 'missing' });
    expect(served.kind).toBe('missing');
    expect(served.note).toContain('服务端有效状态');
    const formula = rawCellReading({ text: '=SUM(C2:C5)', cachedText: '0', isFormula: true });
    expect(formula.kind).toBe('recorded');
    expect(formula.displayText).toBe('0');
    expect(formula.note).toContain('公式视图');
  });
});

describe('分数与计分叶展示', () => {
  it('分数单位是 ×100：格式化为十进制文本', () => {
    expect(formatScoreUnits(10000)).toBe('100');
    expect(formatScoreUnits(2550)).toBe('25.50');
    expect(formatScoreUnits(null)).toBe('—');
  });

  it('计分叶：isScored 且没有计分子项，按 ordinal 排序并显示题号与满分', () => {
    const items = [
      { itemId: 'i1', parentItemId: null, questionNo: '一', ordinal: 1, isScored: true, maxScoreUnits: 10000 },
      { itemId: 'i2', parentItemId: 'i1', questionNo: '1(1)', ordinal: 2, isScored: true, maxScoreUnits: 4000 },
      { itemId: 'i3', parentItemId: null, questionNo: '二', ordinal: 3, isScored: false, maxScoreUnits: null },
    ];
    const leaves = scoredLeafItems(items);
    expect(leaves.map((leaf) => leaf.itemId)).toEqual(['i2']);
    expect(leafLabel(leaves[0])).toBe('1(1)（满分 40）');
  });

  it('短号只截断长 ID，空值给 —（不伪造名称）', () => {
    expect(shortId('abcdefghijklmn')).toBe('abcdefgh…');
    expect(shortId('short')).toBe('short');
    expect(shortId(null)).toBe('—');
    expect(scoreImportStateLabel('confirmed')).toBe('已确认入库');
  });
});

describe('引用守卫计数', () => {
  it('逐项列出 >0 的引用，未知键保留原始键名', () => {
    const counts = referenceCounts(
      { counts: { scoreRevisions: 2, otherRefs: 1, zero: 0 } },
      { scoreRevisions: '已生成的成绩版本' },
    );
    expect(counts).toEqual([
      { key: 'scoreRevisions', label: '已生成的成绩版本', count: 2 },
      { key: 'otherRefs', label: 'otherRefs', count: 1 },
    ]);
  });

  it('形状不符时返回空数组（不把未知结构当引用原因）', () => {
    expect(referenceCounts(undefined, {})).toEqual([]);
    expect(referenceCounts({ counts: 'nope' }, {})).toEqual([]);
  });
});
