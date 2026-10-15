import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/services/api-client';
import { learningAnalysisApi } from '@/services/learning-analysis-api';
import { AnalysisKpiStrip } from './AnalysisKpiStrip';

vi.mock('@/services/learning-analysis-api', () => ({
  learningAnalysisApi: {
    getAnalysisItemStats: vi.fn(),
    getAnalysisKnowledgeStats: vi.fn(),
    getAnalysisDistribution: vi.fn(),
  },
}));

const api = vi.mocked(learningAnalysisApi);

describe('AnalysisKpiStrip 概要指标', () => {
  afterEach(cleanup);

  beforeEach(() => {
    api.getAnalysisItemStats.mockReset().mockResolvedValue([
      { itemId: 'a', itemPath: '1', maxScoreUnits: 500, recordedCount: 4, totalScoreUnits: 1000, scoreRate: 0.5 },
      { itemId: 'b', itemPath: '2', maxScoreUnits: 1000, recordedCount: 2, totalScoreUnits: 1500, scoreRate: 0.75 },
    ]);
    api.getAnalysisKnowledgeStats.mockReset().mockResolvedValue({
      items: [
        { knowledgePointId: 'k1', name: '函数性质', path: null, scoreRate: 0.9, questionCount: 3 },
        { knowledgePointId: 'k2', name: '导数应用', path: null, scoreRate: 0.4, questionCount: 2 },
      ],
    });
    api.getAnalysisDistribution.mockReset().mockResolvedValue({
      buckets: [
        { label: '低 (<60%)', count: 3 },
        { label: '中 (60–85%)', count: 5 },
        { label: '高 (≥85%)', count: 2 },
      ],
    });
  });

  it('四项指标分别来自人次快照、小题加权、分布后两档与最弱知识点', async () => {
    render(<AnalysisKpiStrip runId="run-1" participants={10} />);

    await waitFor(() => expect(screen.getByTestId('la-kpi-pass')).toHaveTextContent('70%'));
    expect(screen.getByTestId('la-kpi-participants')).toHaveTextContent('10');
    // (1000 + 1500) / (4×500 + 2×1000) = 2500 / 4000 = 62.5% → 四舍五入 63%
    expect(screen.getByTestId('la-kpi-average')).toHaveTextContent('63%');
    expect(screen.getByTestId('la-kpi-weakest')).toHaveTextContent('导数应用');
    expect(screen.getByTestId('la-kpi-weakest')).toHaveTextContent('得分率 40%');
  });

  it('某一来源失败只让对应指标显示「—」，并给出可重试的提示', async () => {
    api.getAnalysisDistribution.mockRejectedValueOnce(
      new ApiError('SERVICE_UNAVAILABLE', '后端未上线', 501, true),
    );
    render(<AnalysisKpiStrip runId="run-1" participants={null} />);

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('部分概要指标读取失败'),
    );
    expect(screen.getByTestId('la-kpi-pass')).toHaveTextContent('—');
    expect(screen.getByTestId('la-kpi-participants')).toHaveTextContent('—');
    // 其他来源不受影响
    expect(screen.getByTestId('la-kpi-average')).toHaveTextContent('63%');
    expect(screen.getByTestId('la-kpi-weakest')).toHaveTextContent('导数应用');
  });
});
