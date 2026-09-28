/**
 * 草稿编辑表单的纯逻辑：答案形态切换、结构预检与文本归一。
 *
 * 这里只做本地预检（早提示），最终判定与错误码以后端为准：服务端
 * `validate_for_confirm` 与 DraftPatchRequest 的严格校验仍是唯一权威。
 */

import type {
  DraftView,
  QuestionAnswer,
  QuestionContent,
  QuestionMetadata,
  QuestionOption,
  QuestionType,
} from '@/contracts/question-bank';

export const CHOICE_TYPES: readonly QuestionType[] = ['single_choice', 'multiple_choice'];
export const TEXT_ANSWER_TYPES: readonly QuestionType[] = ['fill_blank', 'short_answer'];

export const MAX_OPTIONS = 26;
export const MAX_OPTION_KEY_LENGTH = 8;
export const MAX_KNOWLEDGE_TAGS = 32;

export function isChoiceType(type: QuestionType): boolean {
  return CHOICE_TYPES.includes(type);
}

export function isTextAnswerType(type: QuestionType): boolean {
  return TEXT_ANSWER_TYPES.includes(type);
}

export function emptyAnswer(): QuestionAnswer {
  return { choiceKeys: [], accepted: null, textMarkdown: null };
}

/** 答案是否有内容（与后端 `answer_has_content` 同规则）。 */
export function answerHasContent(answer: QuestionAnswer | null | undefined): boolean {
  if (!answer) return false;
  if (answer.choiceKeys.length > 0) return true;
  if (answer.accepted !== null && answer.accepted !== undefined) return true;
  return Boolean(answer.textMarkdown && answer.textMarkdown.trim());
}

/** 归一答案：文本去空白；全部字段为空时返回 null（等价「原文未提供答案」）。 */
export function normalizeAnswer(answer: QuestionAnswer | null | undefined): QuestionAnswer | null {
  if (!answer) return null;
  const choiceKeys = [...new Set(answer.choiceKeys.filter((key) => key.trim().length > 0))];
  const text = answer.textMarkdown?.trim() ?? '';
  const result: QuestionAnswer = {
    choiceKeys,
    accepted: answer.accepted ?? null,
    textMarkdown: text ? text : null,
  };
  return answerHasContent(result) ? result : null;
}

/** 深拷贝内容，避免表单直接改到服务端快照对象。 */
export function copyContent(content: QuestionContent): QuestionContent {
  return {
    type: content.type,
    stemMarkdown: content.stemMarkdown,
    options: content.options.map((option) => ({ ...option })),
    answer: content.answer
      ? {
          choiceKeys: [...content.answer.choiceKeys],
          accepted: content.answer.accepted,
          textMarkdown: content.answer.textMarkdown,
        }
      : null,
    explanationMarkdown: content.explanationMarkdown,
    assetIds: [...content.assetIds],
  };
}

export function copyMetadata(metadata: QuestionMetadata): QuestionMetadata {
  return { ...metadata, knowledgeTags: [...metadata.knowledgeTags] };
}

export function contentFromDraft(draft: DraftView): QuestionContent {
  return copyContent(draft.content);
}

export function metadataFromDraft(draft: DraftView): QuestionMetadata {
  return copyMetadata(draft.metadata);
}

/** 下一个未被占用的选项 key：A…Z，超出后 O27、O28…（与后端 key 长度上限 8 兼容）。 */
export function nextOptionKey(options: readonly QuestionOption[]): string {
  const used = new Set(options.map((option) => option.key));
  for (let index = 0; index < 26; index += 1) {
    const key = String.fromCharCode(65 + index);
    if (!used.has(key)) return key;
  }
  let index = options.length + 1;
  while (used.has(`O${index}`)) index += 1;
  return `O${index}`;
}

/**
 * 切换题型时保留仍有效的答案数据：
 * - 选择题：只保留仍存在于选项中的 key；
 * - 判断题：保留 accepted；
 * - 填空/简答：保留文本答案；
 * - 其他：三者都保留（由服务端结构校验兜底）。
 */
export function changeContentType(content: QuestionContent, type: QuestionType): QuestionContent {
  const optionKeys = new Set(content.options.map((option) => option.key));
  const answer = content.answer ?? emptyAnswer();
  let next: QuestionAnswer;
  if (isChoiceType(type)) {
    const keys = answer.choiceKeys.filter((key) => optionKeys.has(key));
    next = {
      choiceKeys: type === 'single_choice' ? keys.slice(0, 1) : keys,
      accepted: null,
      textMarkdown: null,
    };
  } else if (type === 'true_false') {
    next = { choiceKeys: [], accepted: answer.accepted, textMarkdown: null };
  } else if (isTextAnswerType(type)) {
    next = { choiceKeys: [], accepted: null, textMarkdown: answer.textMarkdown };
  } else {
    next = {
      choiceKeys: answer.choiceKeys.filter((key) => optionKeys.has(key)),
      accepted: answer.accepted,
      textMarkdown: answer.textMarkdown,
    };
  }
  return { ...content, type, answer: normalizeAnswer(next) };
}

/** 结构化预检：返回必须修正的错误（服务端仍会独立复核）。 */
export function contentErrors(content: QuestionContent): string[] {
  const errors: string[] = [];
  if (!content.stemMarkdown.trim()) errors.push('题干不能为空。');
  if (content.options.length > MAX_OPTIONS) errors.push(`选项最多 ${MAX_OPTIONS} 个。`);
  const keys = content.options.map((option) => option.key.trim());
  if (keys.some((key) => key.length === 0)) errors.push('选项 key 不能为空。');
  if (keys.some((key) => key.length > MAX_OPTION_KEY_LENGTH)) {
    errors.push(`选项 key 不能超过 ${MAX_OPTION_KEY_LENGTH} 个字符。`);
  }
  if (new Set(keys).size !== keys.length) errors.push('选项 key 不能重复。');
  if (content.options.some((option) => !option.textMarkdown.trim())) {
    errors.push('选项内容不能为空。');
  }
  if (isChoiceType(content.type) && content.options.length === 0) {
    errors.push('选择题至少需要 1 个选项。');
  }
  const answerKeys = content.answer?.choiceKeys ?? [];
  const unknown = answerKeys.filter((key) => !keys.includes(key));
  if (unknown.length > 0) errors.push(`答案 key 不在选项中：${unknown.join('、')}。`);
  if (content.type === 'single_choice' && answerKeys.length > 1) {
    errors.push('单选题的答案只能有 1 个选项。');
  }
  if (isTextAnswerType(content.type) && answerKeys.length > 0) {
    errors.push('填空题/简答题的答案应为文本，不能选选项 key。');
  }
  return errors;
}

/** 分类预检：只拦截明确超出契约上限的填写。 */
export function metadataErrors(metadata: QuestionMetadata): string[] {
  const errors: string[] = [];
  if (metadata.knowledgeTags.length > MAX_KNOWLEDGE_TAGS) {
    errors.push(`知识点标签最多 ${MAX_KNOWLEDGE_TAGS} 个。`);
  }
  if (metadata.knowledgeTags.some((tag) => tag.trim().length === 0)) {
    errors.push('知识点标签不能为空。');
  }
  return errors;
}

/**
 * 入库前的本地预检：提示可提前修正的问题；服务端 `failures` 仍会逐条复核。
 */
export function confirmBlockers(
  content: QuestionContent,
  missingAnswerAcknowledged: boolean,
): string[] {
  const issues: string[] = [];
  if (isChoiceType(content.type) && content.options.length === 0) {
    issues.push('选择题必须至少有一个选项。');
  }
  if (!answerHasContent(content.answer) && !missingAnswerAcknowledged) {
    issues.push('答案缺失：需先「标记原文未提供答案」，或补齐答案后才能入库。');
  }
  return issues;
}

/** 知识点标签输入（逗号 / 顿号 / 空格 / 分号分隔）→ 去重数组。 */
export function tagsFromText(text: string): string[] {
  const parts = text
    .split(/[,，、;；\s]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return [...new Set(parts)];
}

export function tagsToText(tags: readonly string[]): string {
  return tags.join('、');
}
