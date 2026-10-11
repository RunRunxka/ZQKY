'use client';
import { useCallback, useState } from 'react';
import { PapersPanel, type SelectedPaper } from './PapersPanel';
import { KnowledgeDonut } from './KnowledgeDonut';
import { paperKnowledgeDistribution, type KnowledgeDistributionBucket } from '@/services/assessments-api';

/** 试卷管理独立页（C4-3）：试卷面板 + 选中试卷的知识点占比环状图（AI 分类聚合）。 */
export function PapersWorkspacePage() {
  const [selected, setSelected] = useState<SelectedPaper | null>(null);
  const [refreshToken] = useState(0);
  const [distribution, setDistribution] = useState<KnowledgeDistributionBucket[] | null>(null);
  const paperId = selected?.paperId ?? null;

  const loadDistribution = useCallback(async (id: string | null) => {
    if (!id) {
      setDistribution(null);
      return;
    }
    try {
      setDistribution(await paperKnowledgeDistribution(id));
    } catch {
      setDistribution(null);
    }
  }, []);

  return (
    <div className="papers-page">
      <PapersPanel
        selected={selected}
        onSelect={(paper) => {
          setSelected(paper);
          void loadDistribution(paper?.paperId ?? null);
        }}
        refreshToken={refreshToken}
      />
      {paperId && distribution !== null && <KnowledgeDonut distribution={distribution} />}
      {paperId && distribution === null && (
        <p className="b4-meta">知识点占比加载失败或该试卷暂无关联数据。</p>
      )}
    </div>
  );
}
