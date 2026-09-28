'use client';

/** 试题只读预览：题干、选项（标出答案 key）、答案摘要与解析。AI 建议与题目详情共用。 */

import type { QuestionContent } from '@/contracts/question-bank';
import { questionTypeLabel } from './labels';
import { answerHasContent } from './draft-form';

/** 答案摘要：缺失时明确返回「答案缺失」，不隐藏、不猜造。 */
export function answerSummary(content: QuestionContent): string {
  const answer = content.answer;
  if (!answerHasContent(answer)) return '答案缺失';
  if (!answer) return '答案缺失';
  if (content.type === 'true_false' && answer.accepted !== null) {
    return answer.accepted ? '对' : '错';
  }
  if (answer.choiceKeys.length > 0) return answer.choiceKeys.join('、');
  if (answer.textMarkdown && answer.textMarkdown.trim()) return answer.textMarkdown;
  return '答案缺失';
}

export function QuestionPreview({
  content,
  compact = false,
}: {
  content: QuestionContent;
  compact?: boolean;
}) {
  const answerKeys = content.answer?.choiceKeys ?? [];
  return (
    <div className={compact ? 'qb-preview compact' : 'qb-preview'}>
      <p className="qb-preview-stem">{content.stemMarkdown}</p>
      {content.options.length > 0 && (
        <ul className="qb-preview-options">
          {content.options.map((option) => (
            <li
              key={option.key}
              className={
                answerKeys.includes(option.key) ? 'qb-preview-option correct' : 'qb-preview-option'
              }
            >
              <span className="qb-preview-key">{option.key}</span>
              <span>{option.textMarkdown}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="qb-preview-line">
        <span className="qb-preview-label">{questionTypeLabel(content.type)}答案</span>
        <span className={answerHasContent(content.answer) ? '' : 'qb-warn-text'}>
          {answerSummary(content)}
        </span>
      </p>
      {content.explanationMarkdown && (
        <p className="qb-preview-explanation">解析：{content.explanationMarkdown}</p>
      )}
    </div>
  );
}
