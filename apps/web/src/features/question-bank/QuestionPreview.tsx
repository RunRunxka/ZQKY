'use client';

/** 试题只读预览：题干、选项（标出答案 key）、答案摘要与解析。AI 建议与题目详情共用。 */

import type { QuestionContent } from '@/contracts/question-bank';
import { questionTypeLabel } from './labels';
import { answerHasContent } from './draft-form';
import { ContentMarkdown, RichBlocks, RichContentRenderer, type RichAssetLoader } from '@/components/ui/RichContentRenderer';

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
  loadAsset,
  assetScope,
}: {
  content: QuestionContent;
  compact?: boolean;
  loadAsset?: RichAssetLoader;
  assetScope?: string;
}) {
  const answerKeys = content.answer?.choiceKeys ?? [];
  return (
    <div className={compact ? 'qb-preview compact' : 'qb-preview'}>
      {content.richContent
        ? <RichContentRenderer content={content.richContent} loadAsset={loadAsset} assetScope={assetScope} />
        : <div className="qb-preview-stem"><ContentMarkdown text={content.stemMarkdown} /></div>}
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
              {content.richContent?.optionBlocks[option.key]
                ? <RichBlocks blocks={content.richContent.optionBlocks[option.key]} loadAsset={loadAsset} assetScope={assetScope} />
                : <ContentMarkdown text={option.textMarkdown} />}
            </li>
          ))}
        </ul>
      )}
      <div className="qb-preview-line">
        <span className="qb-preview-label">{questionTypeLabel(content.type)}答案</span>
        <div className={answerHasContent(content.answer) ? '' : 'qb-warn-text'}>
          {content.richContent?.answerBlocks.length
            ? <RichBlocks blocks={content.richContent.answerBlocks} loadAsset={loadAsset} assetScope={assetScope} />
            : answerSummary(content)}
        </div>
      </div>
      {content.explanationMarkdown && (
        <div className="qb-preview-explanation">解析：{content.richContent?.explanationBlocks.length
          ? <RichBlocks blocks={content.richContent.explanationBlocks} loadAsset={loadAsset} assetScope={assetScope} />
          : <ContentMarkdown text={content.explanationMarkdown} />}</div>
      )}
    </div>
  );
}
