'use client';

/**
 * 报告概要指标条（学情图表上方）：参测人次 / 班级平均得分率 / 及格率 / 最弱知识点。
 * 数据全部来自本报告已有的三个只读接口（小题统计、知识点统计、分布）；任一来源读取失败，
 * 只影响它对应的指标（显示「—」并可重试），不把失败当成 0。
 */

import { useMemo } from 'react';
import { AnimatedCount } from '@/components/motion/AnimatedCount';
import { learningAnalysisApi as api } from '@/services/learning-analysis-api';
import { averageRateOf, passRateOf, weakestOf } from './analysis-kpi';
import { useAsyncResource } from './score-hooks';
import '@/components/layout/space.css';
import './styles/analysis-kpi.css';

export function AnalysisKpiStrip({
  runId,
  participants,
}: {
  runId: string;
  /** 报告冻结人次快照的数量；运行视图尚未读到时为 null。 */
  participants: number | null;
}) {
  const items = useAsyncResource(
    (signal) => api.getAnalysisItemStats(runId, signal),
    `la-kpi-items|${runId}`,
  );
  const knowledge = useAsyncResource(
    (signal) => api.getAnalysisKnowledgeStats(runId, signal),
    `la-kpi-knowledge|${runId}`,
  );
  const distribution = useAsyncResource(
    (signal) => api.getAnalysisDistribution(runId, signal),
    `la-kpi-distribution|${runId}`,
  );

  const averageRate = items.lastData ? averageRateOf(items.lastData) : null;
  const passRate = distribution.lastData ? passRateOf(distribution.lastData) : null;
  const weakest = knowledge.lastData ? weakestOf(knowledge.lastData.items) : null;
  const failed = [items, knowledge, distribution].some((r) => r.state.phase === 'failed');

  const cards = useMemo(
    () => [
      {
        key: 'participants',
        label: '参测人次',
        value: participants,
        suffix: '',
        hint: '报告冻结的人次快照',
      },
      {
        key: 'average',
        label: '班级平均得分率',
        value: averageRate === null ? null : Math.round(averageRate * 100),
        suffix: '%',
        hint: '小题加权，无有效作答不计',
      },
      {
        key: 'pass',
        label: '及格率',
        value: passRate === null ? null : Math.round(passRate * 100),
        suffix: '%',
        hint: '得分率 ≥ 60% 的学生占比',
      },
    ],
    [participants, averageRate, passRate],
  );

  return (
    <section className="analysis-kpi" aria-label="报告概要" data-testid="la-kpi-strip">
      {cards.map((card) => (
        <article key={card.key} className="analysis-kpi-card" data-testid={`la-kpi-${card.key}`}>
          <p className="analysis-kpi-label">{card.label}</p>
          <p className="analysis-kpi-value">
            <AnimatedCount value={card.value ?? undefined} />
            {card.value !== null && card.suffix}
          </p>
          <p className="analysis-kpi-hint">{card.hint}</p>
        </article>
      ))}
      <article className="analysis-kpi-card" data-testid="la-kpi-weakest">
        <p className="analysis-kpi-label">最弱知识点</p>
        <p className="analysis-kpi-name">{weakest ? weakest.name : '—'}</p>
        <p className="analysis-kpi-hint">
          {weakest ? `得分率 ${Math.round(weakest.scoreRate * 100)}%` : '暂无知识点得分数据'}
        </p>
      </article>
      {failed && (
        <div className="analysis-kpi-failed space-banner error" role="alert">
          <span>部分概要指标读取失败，对应数值暂显示「—」。</span>
          <button
            type="button"
            className="button subtle"
            onClick={() => {
              items.reload();
              knowledge.reload();
              distribution.reload();
            }}
          >
            重试
          </button>
        </div>
      )}
    </section>
  );
}
