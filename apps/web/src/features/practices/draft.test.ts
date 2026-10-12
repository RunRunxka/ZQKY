/**
 * 练习草稿纯函数（R8-FE）：排序重排 ordinal 与简单题号，复合/自定义题号不动。
 */

import { describe, expect, it } from 'vitest';
import type { PracticeDraftItem } from '@/contracts/b4';
import { moveItem, renumber } from './draft';

function item(key: string, ordinal: number, questionNo = String(ordinal), nodes = 1): PracticeDraftItem {
  return {
    itemKey: key,
    questionRevisionId: `qrev-${key}`,
    ordinal,
    maxScore: '1',
    selectedKnowledgePointIds: ['kp-1'],
    itemStructure: {
      nodes: Array.from({ length: nodes }, (_, index) => ({
        nodeKey: `${key}-${index + 1}`,
        parentNodeKey: null,
        questionNo: nodes === 1 ? questionNo : `${questionNo}(${index + 1})`,
        ordinal: index + 1,
        isScored: true,
        maxScore: '1',
        knowledgePointIds: ['kp-1'],
        sourceBlockIds: ['b1'],
      })),
    },
  };
}

describe('moveItem', () => {
  it('交换顺序并重排 ordinal 与简单题号', () => {
    const moved = moveItem([item('a', 1), item('b', 2)], 1, -1);
    expect(moved.map((entry) => entry.itemKey)).toEqual(['b', 'a']);
    expect(moved.map((entry) => entry.ordinal)).toEqual([1, 2]);
    expect(moved.map((entry) => entry.itemStructure.nodes[0].questionNo)).toEqual(['1', '2']);
  });

  it('复合题号（多节点）不随位置改写', () => {
    const moved = moveItem([item('a', 1), item('b', 2, '2', 2)], 1, -1);
    expect(moved[0].itemStructure.nodes.map((node) => node.questionNo)).toEqual(['2(1)', '2(2)']);
  });

  it('教师手改过的题号不随位置改写', () => {
    const moved = moveItem([item('a', 1), item('b', 2, '二、2')], 1, -1);
    expect(moved[0].itemStructure.nodes[0].questionNo).toBe('二、2');
  });

  it('越界原样返回', () => {
    const items = [item('a', 1)];
    expect(moveItem(items, 0, -1)).toBe(items);
  });
});

describe('renumber', () => {
  it('移除后重排 ordinal 与简单题号', () => {
    const result = renumber([item('a', 2), item('b', 3)]);
    expect(result.map((entry) => entry.ordinal)).toEqual([1, 2]);
    expect(result.map((entry) => entry.itemStructure.nodes[0].questionNo)).toEqual(['1', '2']);
  });
});
