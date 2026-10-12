import { describe, expect, it } from 'vitest';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { buildKnowledgeTree, collectNodeIds, countText, subtreeTotals } from './knowledge-tree';

function point(id: string, overrides: Partial<KnowledgePointView> = {}): KnowledgePointView {
  return {
    id,
    subjectId: 'math',
    code: id,
    name: id,
    description: '',
    parentId: null,
    parentCode: null,
    sortOrder: 0,
    status: 'active',
    revision: 1,
    revisionId: `${id}-r`,
    version: 1,
    aliases: [],
    createdAt: '2026-10-11T00:00:00Z',
    ...overrides,
  };
}

describe('知识点分类树', () => {
  it('按 parentId 成树并按 sortOrder/code 排序', () => {
    const tree = buildKnowledgeTree([
      point('b', { code: 'B', sortOrder: 2 }),
      point('a', { code: 'A', sortOrder: 1 }),
      point('a-2', { code: 'A2', parentId: 'a', parentCode: 'A', sortOrder: 2 }),
      point('a-1', { code: 'A1', parentId: 'a', parentCode: 'A', sortOrder: 1 }),
    ]);
    expect(tree.roots.map((node) => node.id)).toEqual(['a', 'b']);
    expect(tree.roots[0]?.children.map((node) => node.id)).toEqual(['a-1', 'a-2']);
    expect(tree.unknownParentCount).toBe(0);
    expect(tree.cycleCount).toBe(0);
  });

  it('父节点不在结果集时放进 detached，不伪造层级', () => {
    const tree = buildKnowledgeTree([point('orphan', { parentId: 'missing' }), point('root')]);
    expect(tree.roots.map((node) => node.id)).toEqual(['root']);
    expect(tree.detached.map((node) => node.id)).toEqual(['orphan']);
    expect(tree.unknownParentCount).toBe(1);
  });

  it('子树计数 = 自身 + 后代；任一节点未知则整棵子树未知（不写 0）', () => {
    const tree = buildKnowledgeTree([
      point('p1'),
      point('p2', { parentId: 'p1' }),
      point('p3', { parentId: 'p1' }),
      point('q1'),
    ]);
    const totals = subtreeTotals(tree.roots, new Map([['p1', 1], ['p2', 2], ['p3', 3], ['q1', 0]]));
    expect(totals.get('p1')).toBe(6);
    expect(totals.get('p2')).toBe(2);
    expect(totals.get('q1')).toBe(0);

    const partial = subtreeTotals(tree.roots, new Map([['p1', 1], ['p3', 3], ['q1', 4]]));
    expect(partial.get('p1')).toBeUndefined();
    expect(partial.get('p3')).toBe(3);
    expect(partial.get('q1')).toBe(4);
    expect(countText(partial.get('p1'))).toBe('—');
    expect(countText(partial.get('q1'))).toBe('4');
  });

  it('collectNodeIds 去重并包含 detached 节点', () => {
    const tree = buildKnowledgeTree([
      point('p1'),
      point('p2', { parentId: 'p1' }),
      point('orphan', { parentId: 'missing' }),
    ]);
    expect(collectNodeIds(tree).sort()).toEqual(['orphan', 'p1', 'p2']);
  });
});
