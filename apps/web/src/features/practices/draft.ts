import type { PracticeDraftItem, PracticeSuggestion, PracticeNode } from '@/contracts/b4';
import { surfaceBlocks } from '@/features/learning-analysis/ui';

/** 教师点击“作为一计分叶加入”才调用；分叶结构可继续显式编辑，不推断复合题。 */
export function itemFromSuggestion(suggestion: PracticeSuggestion, itemKey: string, ordinal: number): PracticeDraftItem {
  const ids = suggestion.knowledgePoints.map((point) => point.knowledgePointId);
  return { itemKey, questionRevisionId: suggestion.questionRevisionId, ordinal, maxScore: '1', selectedKnowledgePointIds: [...new Set(ids)],
    itemStructure: { nodes: [{ nodeKey: `${itemKey}-1`, parentNodeKey: null, questionNo: String(ordinal), ordinal: 1, isScored: true, maxScore: '1', knowledgePointIds: [...new Set(ids)], sourceBlockIds: surfaceBlocks(suggestion.content).map((block) => block.id) }] } };
}

export function moveItem(items: PracticeDraftItem[], index: number, direction: -1 | 1): PracticeDraftItem[] {
  const other = index + direction;
  if (other < 0 || other >= items.length) return items;
  const reordered = [...items];
  [reordered[index], reordered[other]] = [reordered[other], reordered[index]];
  return reordered.map((item, position) => ({ ...item, ordinal: position + 1 }));
}

export function withNode(item: PracticeDraftItem, index: number, patch: Partial<PracticeNode>): PracticeDraftItem {
  return { ...item, itemStructure: { nodes: item.itemStructure.nodes.map((node, position) => position === index ? { ...node, ...patch } : node) } };
}
