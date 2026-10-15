import { describe, expect, it } from 'vitest';
import { averageRateOf, passRateOf, weakestOf } from './analysis-kpi';

describe('学情概要指标口径', () => {
  it('班级平均得分率按小题加权，忽略无人作答的题', () => {
    const rate = averageRateOf([
      { itemId: 'a', itemPath: '1', maxScoreUnits: 500, recordedCount: 4, totalScoreUnits: 1000, scoreRate: 0.5 },
      { itemId: 'b', itemPath: '2', maxScoreUnits: 1000, recordedCount: 2, totalScoreUnits: 1000, scoreRate: 0.5 },
      { itemId: 'c', itemPath: '3', maxScoreUnits: 300, recordedCount: 0, totalScoreUnits: 0, scoreRate: null },
    ]);
    // (1000 + 1000) / (4×500 + 2×1000) = 2000 / 4000
    expect(rate).toBe(0.5);
  });

  it('没有任何有效作答时平均得分率为 null（不补 0）', () => {
    expect(averageRateOf([])).toBeNull();
    expect(
      averageRateOf([{ itemId: 'a', itemPath: '1', maxScoreUnits: 500, recordedCount: 0, totalScoreUnits: 0, scoreRate: null }]),
    ).toBeNull();
  });

  it('及格率 = 第二档及以上的学生数 / 有效学生数', () => {
    const rate = passRateOf({
      buckets: [
        { label: '低 (<60%)', count: 3 },
        { label: '中 (60–85%)', count: 5 },
        { label: '高 (≥85%)', count: 2 },
      ],
    });
    expect(rate).toBeCloseTo(0.7);
  });

  it('分布为空时及格率为 null', () => {
    expect(passRateOf({ buckets: [{ label: '低 (<60%)', count: 0 }] })).toBeNull();
  });

  it('最弱知识点取得分率最低者', () => {
    expect(
      weakestOf([
        { knowledgePointId: 'k1', name: '函数性质', path: null, scoreRate: 0.9, questionCount: 3 },
        { knowledgePointId: 'k2', name: '导数应用', path: null, scoreRate: 0.4, questionCount: 2 },
      ]),
    ).toEqual({ name: '导数应用', scoreRate: 0.4 });
    expect(weakestOf([])).toBeNull();
  });
});
