/**
 * 施测与成绩模块的呈现判定与文案（纯函数）单测（R5-FE 2026-10-11）。
 *
 * 覆盖的是会被界面直接显示的判定：性别列的诚实显示、姓名搜索、分页夹取、
 * 分数文本（整数单位 → 文本，不走浮点）、学科显示的三态区分、守卫原因清单、
 * 占比文本（服务端未给占比时不得冒充 0%）。
 */

import { describe, expect, it } from 'vitest';
import type { StudentView } from '@/contracts/roster';
import {
  CLASS_REFERENCE_LABELS,
  PAPER_REFERENCE_LABELS,
  clampPage,
  filterStudentsByName,
  formatScoreUnits,
  genderText,
  nameOrShortId,
  pageCount,
  ratioPercentText,
  referenceCounts,
  shortId,
  subjectText,
} from './labels';

function student(overrides: Partial<StudentView> = {}): StudentView {
  return {
    id: 'st-1',
    studentNo: '0001',
    name: '张三',
    status: 'active',
    revision: 1,
    memberships: [],
    createdAt: '2026-10-01T00:00:00Z',
    ...overrides,
  };
}

describe('性别列：只显示服务端真的给出的值', () => {
  it('缺失/null/空串/纯空白一律显示「未记录」', () => {
    expect(genderText(undefined)).toBe('未记录');
    expect(genderText(null)).toBe('未记录');
    expect(genderText('')).toBe('未记录');
    expect(genderText('   ')).toBe('未记录');
  });

  it('服务端给出值时原样显示（不翻译、不推断）', () => {
    expect(genderText('男')).toBe('男');
    expect(genderText('女')).toBe('女');
    expect(genderText(' 其它 ')).toBe('其它');
  });
});

describe('姓名搜索与分页（服务端没有分页参数，这里是视图层切片）', () => {
  const roster = [
    student({ id: 'a', name: '张三' }),
    student({ id: 'b', name: '李四' }),
    student({ id: 'c', name: '张小明' }),
  ];

  it('空查询返回全集副本；命中按包含匹配；大小写不敏感', () => {
    expect(filterStudentsByName(roster, '').map((item) => item.id)).toEqual(['a', 'b', 'c']);
    expect(filterStudentsByName(roster, '张').map((item) => item.id)).toEqual(['a', 'c']);
    expect(filterStudentsByName(roster, ' 李四 ').map((item) => item.id)).toEqual(['b']);
    expect(filterStudentsByName(roster, '不存在')).toEqual([]);
    expect(filterStudentsByName(roster, 'Zhang')).toEqual([]);
  });

  it('页数至少 1 页，页码夹到范围（筛选后不会停在空页）', () => {
    expect(pageCount(0, 10)).toBe(1);
    expect(pageCount(10, 10)).toBe(1);
    expect(pageCount(11, 10)).toBe(2);
    expect(pageCount(32, 10)).toBe(4);
    expect(clampPage(9, 2)).toBe(1);
    expect(clampPage(-3, 2)).toBe(0);
    expect(clampPage(1, 2)).toBe(1);
  });
});

describe('分数文本：整数单位不做浮点累加', () => {
  it('整数/两位/一位小数与缺失都正确', () => {
    expect(formatScoreUnits(100)).toBe('1');
    expect(formatScoreUnits(1050)).toBe('10.5');
    expect(formatScoreUnits(1030)).toBe('10.3');
    expect(formatScoreUnits(0)).toBe('0');
    expect(formatScoreUnits(null)).toBe('—');
    expect(formatScoreUnits(undefined)).toBe('—');
    expect(formatScoreUnits(-250)).toBe('-2.5');
  });
});

describe('学科显示：字典命中 / 未收录 / 字典不可用三态必须能区分', () => {
  const subjects = [{ id: 'math', label: '数学' }];

  it('命中给标签', () => {
    expect(subjectText('math', subjects, false)).toBe('数学');
  });

  it('字典读到了但没有该学科 → 未收录（不猜标签）', () => {
    expect(subjectText('physics-revision-uuid-1', subjects, false)).toBe(
      '字典未收录（physics-…）',
    );
  });

  it('字典读取失败 → 明确说不可用，不冒充「未收录」', () => {
    expect(subjectText('math', null, true)).toBe('学科字典不可用（math）');
  });
});

describe('短号与名称回落', () => {
  it('短号区分「没有」与「太长」', () => {
    expect(shortId(null)).toBe('—');
    expect(shortId('short')).toBe('short');
    expect(shortId('abcdefghijklmn')).toBe('abcdefgh…');
  });

  it('名称缺失时回落短号，不伪造名称', () => {
    expect(nameOrShortId('数学期末', 'p-1')).toBe('数学期末');
    expect(nameOrShortId('   ', 'abcdefghijklmn')).toBe('abcdefgh…');
  });
});

describe('受引用守卫的 409 原因清单', () => {
  it('只列计数 >0 的键，未知键用原键名兜底（不隐藏引用）', () => {
    const reasons = referenceCounts(
      { counts: { memberships: 2, rosterImports: 0, assessments: 1, somethingNew: 3 } },
      CLASS_REFERENCE_LABELS,
    );
    expect(reasons).toEqual([
      { key: 'memberships', label: '班级归属记录', count: 2 },
      { key: 'assessments', label: '参测范围引用', count: 1 },
      { key: 'somethingNew', label: 'somethingNew', count: 3 },
    ]);
  });

  it('形状不符（没有 counts）返回空数组，不抛错', () => {
    expect(referenceCounts(null, PAPER_REFERENCE_LABELS)).toEqual([]);
    expect(referenceCounts({}, PAPER_REFERENCE_LABELS)).toEqual([]);
    expect(referenceCounts({ counts: { assessments: 'x' } }, PAPER_REFERENCE_LABELS)).toEqual([]);
  });
});

describe('知识点占比文本：不用前端自算的比例冒充服务端', () => {
  it('服务端给了比例才显示百分比', () => {
    expect(ratioPercentText(0.25)).toBe('25%');
    expect(ratioPercentText(0.333)).toBe('33%');
    expect(ratioPercentText(1)).toBe('100%');
    expect(ratioPercentText(0)).toBe('0%');
  });

  it('未给比例显示「占比未知」，不显示 0%', () => {
    expect(ratioPercentText(null)).toBe('占比未知');
    expect(ratioPercentText(undefined)).toBe('占比未知');
    expect(ratioPercentText(Number.NaN)).toBe('占比未知');
  });
});
