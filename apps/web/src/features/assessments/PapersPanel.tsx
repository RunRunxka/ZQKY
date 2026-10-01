'use client';

/**
 * 第二步「原卷」：只读选用**已确认**原卷修订（不做完整原卷编辑器）。
 *
 * - 列出 `GET /papers` 的修订状态：草稿不可用于施测，必须明确标注；
 * - 选中已确认修订后把 `{paperId, paperRevisionId, title, totalScoreUnits}` 交给施测步骤；
 * - 原卷导入/确认入口只提供链接与状态回显（原卷编辑器不在此页，导航当前标注为规划中）。
 */

import Link from 'next/link';
import { RefreshCw } from 'lucide-react';
import type { PaperView } from '@/contracts/papers';
import { listPapers } from '@/services/assessments-api';
import { useAsyncResource } from './hooks';
import { formatScoreUnits, paperRevisionStateLabel, paperStatusLabel } from './labels';

export interface SelectedPaper {
  paperId: string;
  paperRevisionId: string;
  title: string;
  totalScoreUnits: number;
  scoredLeafCount: number;
}

export function PapersPanel({
  selected,
  onSelect,
  refreshToken,
}: {
  selected: SelectedPaper | null;
  onSelect: (paper: SelectedPaper | null) => void;
  refreshToken: number;
}) {
  const papers = useAsyncResource(
    (signal) => listPapers({ status: 'active', limit: 100 }, signal),
    `assessments-papers|${refreshToken}`,
  );
  const items: PaperView[] =
    papers.state.phase === 'ready' ? papers.state.data.items : (papers.lastData?.items ?? []);

  return (
    <div className="assessments-panel" data-testid="assessments-papers-panel">
      <section className="assessments-subpanel" aria-label="已确认原卷修订">
        <div className="assessments-subpanel-head">
          <h3>原卷修订</h3>
          <button className="space-button" onClick={papers.reload}>
            <RefreshCw size={13} aria-hidden /> 刷新
          </button>
        </div>

        <p className="assessments-hint">
          成绩导入固定到原卷的<strong>计分叶</strong>与满分；只有已确认修订可用于施测与成绩。
          原卷的导入/确认在「智能组卷」入口（<Link href="/papers">/papers</Link>，当前导航仍标注为规划中）；
          本页只读选用并回显状态。
        </p>

        {papers.state.phase === 'failed' && !papers.lastData && (
          <div className="space-banner error" role="alert" data-testid="assessments-papers-error">
            <div className="space-banner-row">
              <span>
                原卷列表读取失败（{papers.state.error.code}）：{papers.state.error.message}
              </span>
              <button className="space-button" onClick={papers.reload}>
                <RefreshCw size={13} aria-hidden /> 重试
              </button>
            </div>
          </div>
        )}

        {items.length === 0 && papers.state.phase === 'ready' && (
          <p className="space-empty" data-testid="assessments-papers-empty">
            <strong>还没有原卷</strong>
            <span>先在原卷模块导入并确认一份试卷，再回到这里选用。</span>
          </p>
        )}

        <ul className="assessments-list" aria-label="原卷列表">
          {items.map((paper) => {
            const confirmed = paper.currentState === 'confirmed' && Boolean(paper.currentRevisionId);
            const isSelected = selected?.paperRevisionId === paper.currentRevisionId;
            return (
              <li key={paper.paperId}>
                <div
                  className={isSelected ? 'assessments-card current' : 'assessments-card'}
                  data-testid={`assessments-paper-${paper.paperId}`}
                >
                  <div className="assessments-card-head">
                    <strong>{paper.title}</strong>
                    <span className="space-chip">{paperStatusLabel(paper.status)}</span>
                    <span className={confirmed ? 'space-chip green' : 'space-chip amber'}>
                      {paper.currentState
                        ? paperRevisionStateLabel(paper.currentState)
                        : '无修订'}
                    </span>
                  </div>
                  <div className="space-meta-row">
                    <span className="space-chip">修订 v{paper.version}</span>
                    <span className="space-chip">计分叶 {paper.scoredLeafCount}</span>
                    <span className="space-chip">满分 {formatScoreUnits(paper.totalScoreUnits)}</span>
                    {paper.blockingIssueCount > 0 && (
                      <span className="space-chip amber">阻断问题 {paper.blockingIssueCount}</span>
                    )}
                    {paper.currentRevisionId && (
                      <span className="space-chip" data-testid={`assessments-paper-revision-${paper.paperId}`}>
                        revisionId {paper.currentRevisionId}
                      </span>
                    )}
                  </div>
                  <div className="assessments-actions">
                    <button
                      className="space-button primary"
                      disabled={!confirmed}
                      aria-pressed={isSelected}
                      data-testid={`assessments-select-paper-${paper.paperId}`}
                      onClick={() =>
                        onSelect(
                          confirmed && paper.currentRevisionId
                            ? {
                                paperId: paper.paperId,
                                paperRevisionId: paper.currentRevisionId,
                                title: paper.title,
                                totalScoreUnits: paper.totalScoreUnits,
                                scoredLeafCount: paper.scoredLeafCount,
                              }
                            : null,
                        )
                      }
                    >
                      {isSelected ? '已选用该修订' : confirmed ? '选用该修订' : '草稿不可选用'}
                    </button>
                    {!confirmed && (
                      <span className="assessments-hint">
                        未确认修订不能创建施测；请在原卷模块完成校对与确认。
                      </span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>

        {selected && (
          <p className="space-banner info" role="status" data-testid="assessments-paper-selected">
            已选用原卷「{selected.title}」（revision {selected.paperRevisionId}，
            计分叶 {selected.scoredLeafCount}，满分 {formatScoreUnits(selected.totalScoreUnits)}）。
          </p>
        )}
      </section>
    </div>
  );
}
