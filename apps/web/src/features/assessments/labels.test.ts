/**
 * 四态呈现判定 / 分数文本 / 定位与承认推导的单测（F20-I 硬要求）。
 *
 * 重点：0 是有效记录、空白绝不显示成 0、缺考/免考各有独立文案与字形；
 * 分数格式化只用整数单位做字符串运算（不经过浮点累加）。
 */

import { describe, expect, it } from 'vitest';
import {
  ABSENT_TOKENS,
  EXEMPT_TOKENS,
  cellValueText,
  formatScoreUnits,
  issueLocationLabel,
  matrixRowTotalText,
  parseScoreText,
  rawCellReading,
  scoreStatusChipClass,
  scoreStatusGlyph,
  scoreStatusLabel,
  scoreUnitsText,
  SCORE_STATUS_LEGEND,
} from './labels';

describe('分数文本：整数单位 ↔ 十进制字符串（字符串运算）', () => {
  it('parseScoreText 只接受 0–9999、最多两位小数', () => {
    expect(parseScoreText('0')).toEqual({ ok: true, units: 0 });
    expect(parseScoreText('8')).toEqual({ ok: true, units: 800 });
    expect(parseScoreText('7.5')).toEqual({ ok: true, units: 750 });
    expect(parseScoreText('0.05')).toEqual({ ok: true, units: 5 });
    expect(parseScoreText('12.34')).toEqual({ ok: true, units: 1234 });
    expect(parseScoreText('')).toMatchObject({ ok: false });
    expect(parseScoreText(' ')).toMatchObject({ ok: false });
    expect(parseScoreText('-1')).toMatchObject({ ok: false });
    expect(parseScoreText('1.234')).toMatchObject({ ok: false });
    expect(parseScoreText('10000')).toMatchObject({ ok: false });
    expect(parseScoreText('缺考')).toMatchObject({ ok: false });
  });

  it('formatScoreUnits 最多两位小数且去掉多余的 0', () => {
    expect(formatScoreUnits(0)).toBe('0');
    expect(formatScoreUnits(5)).toBe('0.05');
    expect(formatScoreUnits(50)).toBe('0.5');
    expect(formatScoreUnits(800)).toBe('8');
    expect(formatScoreUnits(750)).toBe('7.5');
    expect(formatScoreUnits(1234)).toBe('12.34');
    expect(formatScoreUnits(2100)).toBe('21');
    expect(formatScoreUnits(null)).toBe('—');
    expect(scoreUnitsText(0)).toBe('0 分');
    expect(scoreUnitsText(null)).toBe('（无分数）');
  });

  it('单位与文本互转不产生浮点误差（0.1 + 0.2 场景）', () => {
    const a = parseScoreText('0.1');
    const b = parseScoreText('0.2');
    expect(a.ok && b.ok).toBe(true);
    if (a.ok && b.ok) expect(formatScoreUnits(a.units + b.units)).toBe('0.3');
  });
});

describe('原表单元格的本地读法（0 / missing / absent / exempt 严格区分）', () => {
  it('显式 0 是有效记录，不是空白', () => {
    const reading = rawCellReading({ text: '0' });
    expect(reading.kind).toBe('recorded');
    expect(reading.displayText).toBe('0');
    expect(reading.note).toContain('显式 0');
  });

  it('服务端有效状态优先于原始空白，保持有效0和已覆盖的缺考/免考', () => {
    expect(rawCellReading({ text: '', effectiveStatus: 'recorded', scoreUnits: 0 })).toMatchObject({
      kind: 'recorded', displayText: '0',
    });
    expect(rawCellReading({ text: '', effectiveStatus: 'absent' }).kind).toBe('absent');
    expect(rawCellReading({ text: '0', effectiveStatus: 'exempt' }).kind).toBe('exempt');
  });

  it('空白是 missing，绝不折算成 0', () => {
    const reading = rawCellReading({ text: '' });
    expect(reading.kind).toBe('missing');
    expect(reading.displayText).toBe('（空白）');
    expect(reading.note).toContain('不补 0');
  });

  it('缺考 / 免考标记各有独立读法（与服务端口径逐字一致）', () => {
    for (const token of ABSENT_TOKENS) {
      expect(rawCellReading({ text: token }).kind).toBe('absent');
    }
    for (const token of EXEMPT_TOKENS) {
      expect(rawCellReading({ text: token }).kind).toBe('exempt');
    }
    expect(ABSENT_TOKENS).toEqual(['缺考', 'absent']);
    expect(EXEMPT_TOKENS).toEqual(['免考', 'exempt']);
    // 服务端不认的写法不能本地判成缺考/免考
    expect(rawCellReading({ text: '缺席' }).kind).toBe('unparsed');
    expect(rawCellReading({ text: '免试' }).kind).toBe('unparsed');
  });

  it('公式单元格按缓存值预览并注明公式视图', () => {
    const reading = rawCellReading({ text: '=SUM(D2:E2)', cachedText: '7.5', isFormula: true });
    expect(reading.kind).toBe('recorded');
    expect(reading.displayText).toBe('7.5');
    expect(reading.note).toContain('公式视图');
    expect(rawCellReading({ text: '=SUM(D2:E2)', cachedText: '', isFormula: true }).kind).toBe(
      'unparsed',
    );
  });

  it('未知文本标 unparsed，不猜成 0 也不猜成缺考', () => {
    expect(rawCellReading({ text: '待补' }).kind).toBe('unparsed');
    expect(rawCellReading({ text: 'x' }).kind).toBe('unparsed');
  });

  it('四种状态有不同文案与字形（不只靠颜色；图例覆盖四态）', () => {
    const labels = (['recorded', 'missing', 'absent', 'exempt'] as const).map(scoreStatusLabel);
    expect(new Set(labels).size).toBe(4);
    const glyphs = (['recorded', 'missing', 'absent', 'exempt'] as const).map(scoreStatusGlyph);
    expect(new Set(glyphs).size).toBe(4);
    expect(scoreStatusChipClass('missing')).toBe('score-status score-status-missing');
    expect(SCORE_STATUS_LEGEND.map((entry) => entry.status)).toEqual([
      'recorded',
      'missing',
      'absent',
      'exempt',
    ]);
  });

  it('矩阵单元格值：非 recorded 不给 0', () => {
    expect(cellValueText({ status: 'recorded', scoreUnits: 0 })).toBe('0 分');
    expect(cellValueText({ status: 'missing' })).toBe('空白');
    expect(cellValueText({ status: 'absent' })).toBe('缺考');
    expect(cellValueText({ status: 'exempt' })).toBe('免考');
  });

  it('总分只在全员 recorded 时展示', () => {
    expect(matrixRowTotalText({ totalUnits: 2100, totalMaxUnits: 2100 })).toBe('21 / 21 分');
    expect(matrixRowTotalText({ totalUnits: null, totalMaxUnits: 2100 })).toContain('不展示总分');
    expect(matrixRowTotalText({ totalUnits: null, totalMaxUnits: 2100 })).toContain('21');
  });
});

describe('物理定位与承认范围推导', () => {
  it('问题定位给原表行号与列字母', () => {
    expect(
      issueLocationLabel({ row: 3, column: 'E', code: 'SCORE_CELL_OVER_MAX', message: '超限' }),
    ).toBe('[原表第 3 行 · 列 E] ');
    expect(issueLocationLabel({ field: 'title', code: 'X', message: 'y' })).toBe('[字段 title] ');
    expect(issueLocationLabel({ code: 'X', message: 'y' })).toBe('');
  });

});
