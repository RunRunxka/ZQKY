import type {
  DistributionResponse,
  ItemStatView,
  KnowledgeStatItem,
} from '@/contracts/learning-analysis';

/** 报告概要指标（全部由已读取的图表数据推得；无数据即为 null，界面显示「—」，不补 0）。 */
export interface AnalysisKpis {
  /** 参测人次：报告冻结的人次快照数量。 */
  participants: number | null;
  /** 班级平均得分率（0–1）：小题加权 Σ 得分 / Σ(有效作答人次 × 满分)。 */
  averageRate: number | null;
  /** 及格率（0–1）：得分率 ≥ 60% 的学生数 / 有效学生数（分布口径，见 {@link passRateOf}）。 */
  passRate: number | null;
  /** 最弱知识点：得分率最低的一项（无数据为 null）。 */
  weakest: { name: string; scoreRate: number } | null;
}

/** 班级平均得分率：小题加权。无人有效作答的题不进分母（与后端 item_stats 口径一致）。 */
export function averageRateOf(items: ItemStatView[]): number | null {
  let earned = 0;
  let possible = 0;
  for (const item of items) {
    if (item.recordedCount <= 0 || item.maxScoreUnits <= 0) continue;
    earned += item.totalScoreUnits;
    possible += item.recordedCount * item.maxScoreUnits;
  }
  return possible > 0 ? earned / possible : null;
}

/**
 * 及格率：分布的第一档是「低 (<60%)」（后端 DISTRIBUTION_BUCKETS 的首项），其余档即 ≥60%。
 * 这里把 60% 视为及格线，是后端分档的既定口径，不是本地新定义。
 */
export function passRateOf(distribution: DistributionResponse): number | null {
  const total = distribution.buckets.reduce((sum, bucket) => sum + bucket.count, 0);
  if (total <= 0) return null;
  const passed = distribution.buckets.slice(1).reduce((sum, bucket) => sum + bucket.count, 0);
  return passed / total;
}

/** 最弱知识点：得分率最低者；同分取先出现者。 */
export function weakestOf(
  items: KnowledgeStatItem[],
): { name: string; scoreRate: number } | null {
  let weakest: KnowledgeStatItem | null = null;
  for (const item of items) {
    if (weakest === null || item.scoreRate < weakest.scoreRate) weakest = item;
  }
  return weakest ? { name: weakest.name, scoreRate: weakest.scoreRate } : null;
}
