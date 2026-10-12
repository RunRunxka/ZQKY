/**
 * 练习草稿的纯函数（R8-FE 2026-10-12，取自归档 `features/practices/draft.ts`）。
 *
 * 语义不变：教师显式采用建议才产生计分叶；分叶结构可继续显式编辑，不推断复合题。
 */

import type { PracticeDraftItem, PracticeNode, PracticeSuggestion } from '@/contracts/b4';
import { surfaceBlocks } from './ui';

/** 教师点击「作为一计分叶加入」才调用；分叶结构可继续显式编辑，不推断复合题。 */
export function itemFromSuggestion(
  suggestion: PracticeSuggestion,
  itemKey: string,
  ordinal: number,
  maxScore = '1',
): PracticeDraftItem {
  const ids = suggestion.knowledgePoints.map((point) => point.knowledgePointId);
  return {
    itemKey,
    questionRevisionId: suggestion.questionRevisionId,
    ordinal,
    maxScore,
    selectedKnowledgePointIds: [...new Set(ids)],
    itemStructure: {
      nodes: [
        {
          nodeKey: `${itemKey}-1`,
          parentNodeKey: null,
          questionNo: String(ordinal),
          ordinal: 1,
          isScored: true,
          maxScore,
          knowledgePointIds: [...new Set(ids)],
          sourceBlockIds: surfaceBlocks(suggestion.content).map((block) => block.id),
        },
      ],
    },
  };
}

/**
 * 重排 ordinal（1 起）时同步「简单的单节点题号」：
 * 只在该题只有一个节点、且节点题号正好等于它原来的 ordinal（纯序号、非复合题号）时才改写，
 * 保证卷面题号与顺序一致；复合题号（如 `1(1)`）或教师手改过的题号一律不动。
 */
function alignQuestionNo(item: PracticeDraftItem, position: number): PracticeDraftItem {
  const nodes = item.itemStructure.nodes;
  // 以「原 ordinal」判定节点题号是否为纯序号，再写入新位置。
  const plainSequence = nodes.length === 1 && nodes[0].questionNo === String(item.ordinal);
  const next = { ...item, ordinal: position };
  if (!plainSequence) return next;
  return { ...next, itemStructure: { nodes: [{ ...nodes[0], questionNo: String(position) }] } };
}

/** 上移/下移并重排 ordinal（1 起）；越界原样返回。 */
export function moveItem(items: PracticeDraftItem[], index: number, direction: -1 | 1): PracticeDraftItem[] {
  const other = index + direction;
  if (other < 0 || other >= items.length) return items;
  const reordered = [...items];
  [reordered[index], reordered[other]] = [reordered[other], reordered[index]];
  return reordered.map((item, position) => alignQuestionNo(item, position + 1));
}

export function withNode(item: PracticeDraftItem, index: number, patch: Partial<PracticeNode>): PracticeDraftItem {
  return {
    ...item,
    itemStructure: {
      nodes: item.itemStructure.nodes.map((node, position) =>
        position === index ? { ...node, ...patch } : node,
      ),
    },
  };
}

/** 移除后重排 ordinal，让题号与顺序始终一致（简单单节点题号同步）。 */
export function renumber(items: PracticeDraftItem[]): PracticeDraftItem[] {
  return items.map((item, position) => alignQuestionNo(item, position + 1));
}
