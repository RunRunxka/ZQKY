/**
 * 知识点分类树（纯函数，可单测；R4-FE 2026-10-11）。
 *
 * 数据来源只有知识点库列表的 `parentId`（经 `@/services/knowledge-points-api`，不复制第二份客户端）：
 * - 父节点在本页结果里 → 挂到父节点下（按 `sortOrder`、再按 `code` 排序）；
 * - 父节点**不在**当前结果（分页截断、跨学科、已删除）→ 归入 `detached` 并保留原 id 原样显示，
 *   **不伪造父节点、不当作根节点正常层级**；
 * - 数据出现环（设计上不可能）时把涉及节点放进 `detached` 并计数，避免无限递归。
 *
 * 计数：每个节点的显示数 = 该节点**子树**范围内命中当前筛选条件的题目数
 * （自身 + 所有后代，由 `subtreeTotals` 汇总）。任何一层计数读取失败都记为「未知」，
 * 界面显示 `—` 并给出重试入口，**不会把失败当 0**。
 */

import type { KnowledgePointView } from '@/contracts/knowledge';

export interface KnowledgeNode {
  id: string;
  name: string;
  code: string;
  subjectId: string;
  sortOrder: number;
  children: KnowledgeNode[];
}

export interface KnowledgeTree {
  roots: KnowledgeNode[];
  /** 父节点不在当前结果集 / 环内的节点（如实展示，不编造层级）。 */
  detached: KnowledgeNode[];
  /** 父节点未知的节点数（`detached` 的子集）。 */
  unknownParentCount: number;
  /** 检测到环引用的节点数（正常数据为 0）。 */
  cycleCount: number;
}

function toNode(point: KnowledgePointView): KnowledgeNode {
  return {
    id: point.id,
    name: point.name,
    code: point.code,
    subjectId: point.subjectId,
    sortOrder: point.sortOrder,
    children: [],
  };
}

function compareNodes(left: KnowledgeNode, right: KnowledgeNode): number {
  if (left.sortOrder !== right.sortOrder) return left.sortOrder - right.sortOrder;
  return left.code.localeCompare(right.code, 'zh-Hans-CN');
}

export function buildKnowledgeTree(points: readonly KnowledgePointView[]): KnowledgeTree {
  const nodes = new Map<string, KnowledgeNode>();
  for (const point of points) nodes.set(point.id, toNode(point));

  const roots: KnowledgeNode[] = [];
  const detached: KnowledgeNode[] = [];
  let unknownParentCount = 0;

  for (const point of points) {
    const node = nodes.get(point.id);
    if (!node) continue;
    const parentId = point.parentId;
    const parent = parentId !== null && parentId !== point.id ? nodes.get(parentId) : undefined;
    if (parent) {
      parent.children.push(node);
    } else if (parentId !== null) {
      // 父节点不在当前结果集（或自指）：如实放到「父级未知」组，不猜层级
      unknownParentCount += 1;
      detached.push(node);
    } else {
      roots.push(node);
    }
  }

  const rendered = new Set<string>();
  const walk = (node: KnowledgeNode): void => {
    if (rendered.has(node.id)) return;
    rendered.add(node.id);
    for (const child of node.children) walk(child);
  };
  for (const node of roots) walk(node);
  for (const node of detached) walk(node);

  // 既不是根、父节点也在本页里 → 只可能是环引用（设计上不应出现）；如实放进 detached 并计数，
  // 每个环只挂一次（首节点带着其余成员渲染），避免重复展示。
  const unreachable = points.filter((item) => !rendered.has(item.id));
  for (const item of unreachable) {
    if (rendered.has(item.id)) continue;
    detached.push(nodes.get(item.id) as KnowledgeNode);
    walk(nodes.get(item.id) as KnowledgeNode);
  }
  const cycleCount = unreachable.length;

  const sortLevel = (list: KnowledgeNode[], seen: Set<string>): void => {
    list.sort(compareNodes);
    for (const node of list) {
      if (seen.has(node.id)) continue;
      seen.add(node.id);
      sortLevel(node.children, seen);
    }
  };
  const sorting = new Set<string>();
  sortLevel(roots, sorting);
  sortLevel(detached, sorting);

  return { roots, detached, unknownParentCount, cycleCount };
}

/**
 * 子树计数：`own` 是每个节点自身命中的题目数（缺键 = 计数未知）。
 *
 * - 自身与全部后代都已知 → 求和；
 * - 任一节点未知 → 该祖先整棵子树记为未知（`undefined`），**不用 0 顶替**，
 *   界面显示 `—`，让「没读到」与「真的是 0」在视觉上可区分。
 */
export function subtreeTotals(
  roots: readonly KnowledgeNode[],
  own: ReadonlyMap<string, number>,
): Map<string, number | undefined> {
  const totals = new Map<string, number | undefined>();
  const visit = (node: KnowledgeNode): number | undefined => {
    const selfCount = own.get(node.id);
    let sum = selfCount;
    let unknownChild = false;
    // 无论某个子节点是否未知都要继续遍历：已知的兄弟节点仍要给出真实计数（不能显示成 —）
    for (const child of node.children) {
      const childTotal = visit(child);
      if (childTotal === undefined) unknownChild = true;
      else if (sum !== undefined) sum += childTotal;
    }
    const total = selfCount === undefined || unknownChild ? undefined : sum;
    totals.set(node.id, total);
    return total;
  };
  for (const root of roots) visit(root);
  return totals;
}

/** 树里所有节点的 id（含 detached），供计数请求做去重与并发调度。 */
export function collectNodeIds(tree: KnowledgeTree): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  const walk = (node: KnowledgeNode): void => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    ids.push(node.id);
    for (const child of node.children) walk(child);
  };
  for (const node of tree.roots) walk(node);
  for (const node of tree.detached) walk(node);
  return ids;
}

/** 计数文案：未知显示 `—`（不把读取失败写成 0）。 */
export function countText(value: number | undefined): string {
  return value === undefined ? '—' : String(value);
}
