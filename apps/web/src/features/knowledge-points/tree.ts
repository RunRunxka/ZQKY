/**
 * 知识点父树（纯函数，可单测）。
 *
 * 数据来源只有列表里的 `parentId` / `parentCode`：
 * - 父节点在本页结果里 → 挂到父节点下（按 `sortOrder`、再按 `code` 排序）；
 * - 父节点**不在**当前结果（分页截断、跨学科、已删除）→ 归入 `detached` 并保留
 *   `parentCode/parentId` 原样显示，**不伪造父节点、不当作根节点正常层级**；
 * - 数据出现环（设计上不可能）时把涉及节点放进 `detached` 并计数，避免无限递归。
 */

import type { KnowledgePointView } from '@/contracts/knowledge';

export interface PointTreeNode {
  point: KnowledgePointView;
  children: PointTreeNode[];
}

export interface PointTree {
  roots: PointTreeNode[];
  /** 父节点不在当前结果集 / 环内的节点（如实展示，不编造层级）。 */
  detached: PointTreeNode[];
  /** 父节点未知的节点数（`detached` 的子集）。 */
  unknownParentCount: number;
  /** 检测到环引用的节点数（正常数据为 0）。 */
  cycleCount: number;
}

function comparePoints(left: KnowledgePointView, right: KnowledgePointView): number {
  if (left.sortOrder !== right.sortOrder) return left.sortOrder - right.sortOrder;
  return left.code.localeCompare(right.code, 'zh-Hans-CN');
}

export function buildPointTree(points: readonly KnowledgePointView[]): PointTree {
  const nodes = new Map<string, PointTreeNode>();
  for (const point of points) {
    nodes.set(point.id, { point, children: [] });
  }

  const roots: PointTreeNode[] = [];
  const detached: PointTreeNode[] = [];
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
  const walk = (node: PointTreeNode): void => {
    if (rendered.has(node.point.id)) return;
    rendered.add(node.point.id);
    for (const child of node.children) walk(child);
  };
  for (const node of roots) walk(node);
  for (const node of detached) walk(node);

  // 既不是根、父节点也在本页里 → 只可能是环引用（设计上不应出现）；如实放进 detached 并计数，
  // 每个环只挂一次（首节点带着其余成员渲染），避免重复展示。
  const unreachable = points.filter((item) => !rendered.has(item.id));
  for (const item of unreachable) {
    if (rendered.has(item.id)) continue;
    const node = nodes.get(item.id) as PointTreeNode;
    detached.push(node);
    walk(node);
  }
  const cycleCount = unreachable.length;

  const sortLevel = (list: PointTreeNode[], seen: Set<string>): void => {
    list.sort((left, right) => comparePoints(left.point, right.point));
    for (const node of list) {
      if (seen.has(node.point.id)) continue;
      seen.add(node.point.id);
      sortLevel(node.children, seen);
    }
  };
  const sorting = new Set<string>();
  sortLevel(roots, sorting);
  sortLevel(detached, sorting);

  return { roots, detached, unknownParentCount, cycleCount };
}
