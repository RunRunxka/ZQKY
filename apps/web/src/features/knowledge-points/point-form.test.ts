import { describe, expect, it } from 'vitest';
import type { KnowledgePointView } from '@/contracts/knowledge';
import {
  PARENT_CLEAR,
  PARENT_UNCHANGED,
  planPointCreate,
  planPointUpdate,
  splitAliases,
} from './point-form';

function point(overrides: Partial<KnowledgePointView> = {}): KnowledgePointView {
  return {
    id: 'kp-1',
    subjectId: 'math',
    code: 'M.7.1',
    name: '有理数',
    description: '整数与分数',
    parentId: 'kp-0',
    parentCode: 'M.7',
    sortOrder: 1,
    status: 'active',
    revision: 3,
    revisionId: 'kr-3',
    version: 2,
    aliases: ['有理数概念', '有理数定义'],
    createdAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

function values(overrides: Partial<Parameters<typeof planPointUpdate>[1]> = {}) {
  return {
    name: '有理数',
    description: '整数与分数',
    parentId: PARENT_UNCHANGED,
    sortOrder: '1',
    aliasesText: '有理数概念、有理数定义',
    ...overrides,
  };
}

const NO_CLEAR = { description: false, aliases: false };

describe('splitAliases', () => {
  it('按「、」「,」「;」「/」与换行拆分并去空白', () => {
    expect(splitAliases('有理数、分数, 整数;比值/比例\n小数')).toEqual([
      '有理数',
      '分数',
      '整数',
      '比值',
      '比例',
      '小数',
    ]);
    expect(splitAliases('   ')).toEqual([]);
  });
});

describe('planPointUpdate：留空 = 不修改，清空必须显式', () => {
  it('表单与当前值一致时不产生请求（界面据此禁用保存）', () => {
    const plan = planPointUpdate(point(), values(), NO_CLEAR);
    expect(plan.request).toBeNull();
    expect(plan.actions).toEqual([]);
    expect(plan.errors).toEqual([]);
  });

  it('清空说明必须经 clearFields；只把输入框清空不会静默变成清空', () => {
    const silent = planPointUpdate(point(), values({ description: '' }), NO_CLEAR);
    expect(silent.request).toBeNull();
    expect(silent.hints.join()).toContain('留空表示不修改');

    const explicit = planPointUpdate(point(), values({ description: '' }), {
      ...NO_CLEAR,
      description: true,
    });
    expect(explicit.request).toEqual({ expectedRevision: 3, clearFields: ['description'] });
    expect(explicit.actions).toContain('清空说明');
  });

  it('清空父级用 clearFields parentId；改挂父级用 parentId', () => {
    const clear = planPointUpdate(point(), values({ parentId: PARENT_CLEAR }), NO_CLEAR);
    expect(clear.request).toEqual({ expectedRevision: 3, clearFields: ['parentId'] });

    const move = planPointUpdate(point(), values({ parentId: 'kp-9' }), NO_CLEAR);
    expect(move.request).toEqual({ expectedRevision: 3, parentId: 'kp-9' });
    expect(move.request?.clearFields).toBeUndefined();
  });

  it('别名清空与修改互斥；重复/超量给出错误', () => {
    const clear = planPointUpdate(point(), values(), { ...NO_CLEAR, aliases: true });
    expect(clear.request).toEqual({ expectedRevision: 3, clearFields: ['aliases'] });

    const edited = planPointUpdate(point(), values({ aliasesText: '有理数、新别名' }), NO_CLEAR);
    expect(edited.request?.aliases).toEqual(['有理数', '新别名']);

    const duplicate = planPointUpdate(point(), values({ aliasesText: 'A、A' }), NO_CLEAR);
    expect(duplicate.errors.join()).toContain('不允许重复');
    expect(duplicate.request).toBeNull();

    const tooMany = planPointUpdate(
      point(),
      values({ aliasesText: Array.from({ length: 33 }, (_, index) => `a${index}`).join('、') }),
      NO_CLEAR,
    );
    expect(tooMany.errors.join()).toContain('最多 32 个');
  });

  it('改名与排序：名称不可清空，排序必须是非负整数', () => {
    const rename = planPointUpdate(point(), values({ name: '有理数与无理数' }), NO_CLEAR);
    expect(rename.request).toEqual({ expectedRevision: 3, name: '有理数与无理数' });

    const emptyName = planPointUpdate(point(), values({ name: '  ' }), NO_CLEAR);
    expect(emptyName.errors.join()).toContain('名称不能为空');

    const badSort = planPointUpdate(point(), values({ sortOrder: 'abc' }), NO_CLEAR);
    expect(badSort.errors.join()).toContain('整数');
    expect(badSort.request).toBeNull();

    const sort = planPointUpdate(point(), values({ sortOrder: '5' }), NO_CLEAR);
    expect(sort.request).toEqual({ expectedRevision: 3, sortOrder: 5 });
  });

  it('一次提交可同时改多个字段并带多个清空项', () => {
    const plan = planPointUpdate(
      point({ aliases: [] }),
      values({
        name: '新名字',
        description: '',
        parentId: PARENT_CLEAR,
        sortOrder: '9',
        aliasesText: '',
      }),
      { description: true, aliases: false },
    );
    expect(plan.request).toEqual({
      expectedRevision: 3,
      name: '新名字',
      sortOrder: 9,
      clearFields: ['description', 'parentId'],
    });
    expect(plan.errors).toEqual([]);
  });
});

describe('planPointCreate', () => {
  it('必填校验：学科/编码/名称缺一不可，且不改写输入', () => {
    const plan = planPointCreate({
      subjectId: '',
      code: '',
      name: '',
      description: '',
      parentCode: '',
      sortOrder: '',
      aliasesText: '',
    });
    expect(plan.request).toBeNull();
    expect(plan.errors).toHaveLength(3);
  });

  it('可选字段留空时省略，非空时按契约字段名提交', () => {
    const plan = planPointCreate({
      subjectId: ' math ',
      code: ' M.7.2 ',
      name: ' 数轴 ',
      description: ' 原点与方向 ',
      parentCode: ' M.7 ',
      sortOrder: '2',
      aliasesText: '数轴、原点',
    });
    expect(plan.errors).toEqual([]);
    expect(plan.request).toEqual({
      subjectId: 'math',
      code: 'M.7.2',
      name: '数轴',
      description: ' 原点与方向 ',
      parentCode: 'M.7',
      sortOrder: 2,
      aliases: ['数轴', '原点'],
    });

    const minimal = planPointCreate({
      subjectId: 'math',
      code: 'M.7.3',
      name: '绝对值',
      description: '',
      parentCode: '',
      sortOrder: '',
      aliasesText: '',
    });
    expect(minimal.request).toEqual({ subjectId: 'math', code: 'M.7.3', name: '绝对值' });
  });
});
