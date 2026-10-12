import { describe, expect, it } from 'vitest';
import type { KnowledgePointView } from '@/contracts/knowledge';
import { buildPointTree } from './tree';

function point(id: string, overrides: Partial<KnowledgePointView> = {}): KnowledgePointView {
  return {
    id,
    subjectId: 'math',
    code: id.toUpperCase(),
    name: `知识点 ${id}`,
    description: '',
    parentId: null,
    parentCode: null,
    sortOrder: 0,
    status: 'active',
    revision: 1,
    revisionId: `kr-${id}`,
    version: 1,
    aliases: [],
    createdAt: '2026-09-30T00:00:00Z',
    ...overrides,
  };
}

describe('buildPointTree', () => {
  it('按 parentId 建树，并按 sortOrder、再按 code 稳定排序', () => {
    const tree = buildPointTree([
      point('c', { parentId: 'a', sortOrder: 2 }),
      point('a', { code: 'A' }),
      point('b', { parentId: 'a', sortOrder: 1, code: 'B' }),
    ]);
    expect(tree.roots.map((node) => node.point.id)).toEqual(['a']);
    expect(tree.roots[0]?.children.map((node) => node.point.id)).toEqual(['b', 'c']);
    expect(tree.detached).toEqual([]);
    expect(tree.unknownParentCount).toBe(0);
  });

  it('父级不在当前结果时如实放进 detached，不伪造层级', () => {
    const tree = buildPointTree([
      point('a'),
      point('b', { parentId: 'missing', parentCode: 'M.9' }),
    ]);
    expect(tree.roots.map((node) => node.point.id)).toEqual(['a']);
    expect(tree.detached.map((node) => node.point.id)).toEqual(['b']);
    expect(tree.unknownParentCount).toBe(1);
    expect(tree.detached[0]?.point.parentCode).toBe('M.9');
  });

  it('自指与环不会造成无限递归，全部节点仍被渲染', () => {
    const tree = buildPointTree([
      point('self', { parentId: 'self' }),
      point('x', { parentId: 'y' }),
      point('y', { parentId: 'x' }),
    ]);
    expect(tree.cycleCount).toBe(2);
    const seen = new Set<string>();
    const collect = (nodes: typeof tree.detached): string[] =>
      nodes.flatMap((node) => {
        if (seen.has(node.point.id)) return [];
        seen.add(node.point.id);
        return [node.point.id, ...collect(node.children)];
      });
    expect(collect(tree.detached).sort()).toEqual(['self', 'x', 'y']);
  });

  it('空列表返回空树', () => {
    expect(buildPointTree([])).toEqual({
      roots: [],
      detached: [],
      unknownParentCount: 0,
      cycleCount: 0,
    });
  });
});
