'use client';

/**
 * 成绩四态的徽章与图例（TEACHING-LOOP B3 · F20-I）。
 *
 * 颜色只是辅助：每个徽章同时给**字形 + 文案**；图例把四态写清楚（0 是有效记录、
 * 空白绝不补 0、缺考/免考不计 0）。渲染口径由 `labels.ts` 的纯函数决定，便于单测。
 */

import {
  SCORE_STATUS_LEGEND,
  scoreStatusChipClass,
  scoreStatusGlyph,
  scoreStatusLabel,
  scoreStatusShort,
  type RawCellKind,
} from './labels';

export function ScoreStatusBadge({
  status,
  text,
  testId,
}: {
  status: RawCellKind;
  /** 覆盖显示文本（recorded 显示分数、原表单元格显示原文本）。 */
  text?: string;
  testId?: string;
}) {
  const label = status === 'unparsed' ? '未识别（以服务端为准）' : scoreStatusLabel(status);
  const short = status === 'unparsed' ? '未识别' : scoreStatusShort(status);
  return (
    <span
      className={scoreStatusChipClass(status)}
      data-status={status}
      data-testid={testId}
      title={label}
    >
      <span className="score-status-glyph" aria-hidden>
        {scoreStatusGlyph(status)}
      </span>
      <span className="score-status-text">{text ?? short}</span>
      <span className="visually-hidden">（{label}）</span>
    </span>
  );
}

/** 四态图例：页面与测试共用的说明块（不能只靠颜色）。 */
export function ScoreStatusLegend({ testId = 'score-status-legend' }: { testId?: string }) {
  return (
    <ul className="score-legend" data-testid={testId} aria-label="成绩四态图例">
      {SCORE_STATUS_LEGEND.map((entry) => (
        <li key={entry.status} className="score-legend-item">
          <ScoreStatusBadge status={entry.status} />
          <span className="score-legend-note">{entry.note}</span>
        </li>
      ))}
    </ul>
  );
}
