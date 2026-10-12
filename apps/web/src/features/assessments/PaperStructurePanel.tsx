'use client';

/**
 * 试卷拆题结构（浏览）：展示已导入试卷的**小题拆分与知识点关联结果**。
 *
 * 明确的范围（R5-FE）：
 * - 只显示结构——题号 / 父题 / 计分叶 / 满分 / 关联知识点（名称 + 角色 + 来源）/
 *   每题内容的结构摘要（块数量与字数）/ 原文块的类型与处置 / 解析问题清单；
 * - **不渲染试卷正文、图片与公式**，也不提供整卷内容阅读器（用户明确不需要）；
 * - 读取失败显示具体错误码与重试入口，不把失败当空卷；没有小题时说明原因而不是空白。
 */

import { useAsyncResource } from './hooks';
import { getPaperRevisionContent } from '@/services/assessments-api';
import type { PaperView } from '@/contracts/papers';
import {
  formatScoreUnits,
  paperRevisionStateLabel,
  paperStateChipClass,
  scoredLeafItems,
  shortId,
} from './labels';
import { itemContentSummary } from './PaperImportReview';

export function PaperStructurePanel({ paper }: { paper: PaperView }) {
  const revisionId = paper.currentRevisionId;
  const content = useAsyncResource(
    (signal) =>
      revisionId
        ? getPaperRevisionContent(paper.paperId, revisionId, signal)
        : Promise.resolve(null),
    `paper-structure|${paper.paperId}|${revisionId ?? 'none'}`,
  );

  return (
    <section
      className="assessments-subpanel"
      aria-label="试卷拆题结构"
      data-testid="paper-structure-panel"
    >
      <div className="assessments-subpanel-head">
        <h4>拆题结构（小题与知识点）</h4>
        <span className={paperStateChipClass(paper.currentState)}>
          {paper.currentState ? paperRevisionStateLabel(paper.currentState) : '无修订'}
        </span>
        <span className="space-chip">修订 v{paper.version}</span>
        <span className="space-chip">小题 {paper.itemCount}</span>
        <span className="space-chip">计分叶 {paper.scoredLeafCount}</span>
        <span className="space-chip">满分 {formatScoreUnits(paper.totalScoreUnits)}</span>
        {paper.blockingIssueCount > 0 && (
          <span className="space-chip amber">阻断问题 {paper.blockingIssueCount}</span>
        )}
      </div>

      {!revisionId && (
        <p className="assessments-hint" data-testid="paper-structure-no-revision">
          这份试卷还没有可读取的修订：先完成导入校对并确认入库。
        </p>
      )}

      {revisionId && content.state.phase === 'failed' && (
        <p className="space-banner error" role="alert" data-testid="paper-structure-error">
          拆题结构读取失败（{content.state.error.code}）：{content.state.error.message}
          {content.lastData ? ' 下方仍显示上一次成功读取的结构。' : ''}
          <button className="space-button" onClick={content.reload}>
            重试读取结构
          </button>
        </p>
      )}

      {revisionId && content.lastData && (
        <>
          <p className="assessments-meta" title={`修订 ${content.lastData.paperRevisionId}`}>
            {content.lastData.title} · 修订 {shortId(content.lastData.paperRevisionId)} · 创建{' '}
            {content.lastData.createdAt}
            {content.lastData.confirmedAt ? ` · 确认 ${content.lastData.confirmedAt}` : ''}
          </p>
          {content.lastData.items.length === 0 ? (
            <p className="assessments-hint" data-testid="paper-structure-empty">
              这份修订还没有拆出小题；回到「编辑」打开校对面板补录或调整拆题结果。
            </p>
          ) : (
            <ul className="paper-item-list" aria-label="小题与知识点">
              {scoredLeafItems(content.lastData.items).length > 0 && (
                <li className="assessments-hint">
                  计分叶：
                  {scoredLeafItems(content.lastData.items)
                    .map((item) => item.questionNo || item.itemId)
                    .join('、')}
                </li>
              )}
              {content.lastData.items.map((item) => (
                <li className="paper-item-row" key={item.itemId}>
                  <span className="paper-item-no">题 {item.questionNo || item.itemId}</span>
                  <span className="space-chip">{item.isScored ? '计分叶' : '容器/不计分'}</span>
                  {item.maxScoreUnits !== null && (
                    <span className="space-chip">满分 {formatScoreUnits(item.maxScoreUnits)}</span>
                  )}
                  {item.knowledge.map((link) => (
                    <span className="space-chip blue" key={link.knowledgePointId}>
                      {link.knowledgeNameSnapshot} · {link.role} · {link.source}
                    </span>
                  ))}
                  {item.knowledge.length === 0 && (
                    <span className="space-chip amber">未关联知识点</span>
                  )}
                  <span className="assessments-hint">{itemContentSummary(item.content)}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="assessments-hint">
            原文块 {content.lastData.blocks.length} 个、解析问题 {content.lastData.issues.length}{' '}
            条；正文、图片与公式不在本页展示，结构以服务端持久化快照为准。
          </p>
        </>
      )}

      {revisionId && content.state.phase === 'loading' && (
        <p className="assessments-hint">正在读取拆题结构…</p>
      )}
    </section>
  );
}
