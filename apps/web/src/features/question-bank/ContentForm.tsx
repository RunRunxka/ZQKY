'use client';

/**
 * 试题内容 / 分类的共享表单（草稿校对与已入库题目编辑共用）。
 * 纯受控组件：不自己发请求，也不持服务端状态；分类字典不可用时降级为直接填 id。
 */

import type {
  Difficulty,
  QuestionContent,
  QuestionMetadata,
  QuestionType,
} from '@/contracts/question-bank';
import { DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from '@/contracts/question-bank';
import {
  MAX_OPTIONS,
  changeContentType,
  emptyAnswer,
  isChoiceType,
  isTextAnswerType,
  nextOptionKey,
  normalizeAnswer,
  tagsFromText,
  tagsToText,
} from './draft-form';
import type { TaxonomyIndex } from './taxonomy';

export interface QuestionFormValue {
  content: QuestionContent;
  metadata: QuestionMetadata;
}

const QUESTION_TYPES = Object.keys(QUESTION_TYPE_LABEL) as QuestionType[];
const DIFFICULTIES = Object.keys(DIFFICULTY_LABEL) as Difficulty[];

export function ContentForm({
  value,
  onChange,
  disabled: parentDisabled = false,
  taxonomy,
  idPrefix,
}: {
  value: QuestionFormValue;
  onChange: (next: QuestionFormValue) => void;
  disabled?: boolean;
  taxonomy: TaxonomyIndex;
  idPrefix: string;
}) {
  const { content, metadata } = value;
  const disabled = parentDisabled || Boolean(content.richContent);

  function setContent(patch: Partial<QuestionContent>) {
    if (content.richContent && patch.richContent === undefined) return;
    onChange({ ...value, content: { ...content, ...patch } });
  }

  function setMetadata(patch: Partial<QuestionMetadata>) {
    onChange({ ...value, metadata: { ...metadata, ...patch } });
  }

  function setAnswerKeys(keys: string[], accepted: boolean | null = null) {
    setContent({ answer: normalizeAnswer({ choiceKeys: keys, accepted, textMarkdown: null }) });
  }

  const answer = content.answer ?? emptyAnswer();
  const answerKeys = answer.choiceKeys;
  const showOptions = isChoiceType(content.type) || content.type === 'other';

  return (
    <div className="qb-form">
      {content.richContent && <div className="space-banner info" role="status">
        当前题面使用富内容。转为文本编辑后，本次新修订将保留下面的文本并移除富内容；旧修订不变。
        <button type="button" className="space-button" disabled={parentDisabled}
          onClick={() => setContent({ richContent: null })}>明确转为 Markdown 编辑</button>
      </div>}
      <div className="qb-form-grid">
        <label className="qb-field" htmlFor={`${idPrefix}-type`}>
          题型
          <select
            id={`${idPrefix}-type`}
            className="space-select"
            value={content.type}
            disabled={disabled}
            onChange={(event) =>
              setContent(changeContentType(content, event.target.value as QuestionType))
            }
          >
            {QUESTION_TYPES.map((type) => (
              <option key={type} value={type}>
                {QUESTION_TYPE_LABEL[type]}
              </option>
            ))}
          </select>
        </label>
        <label className="qb-field" htmlFor={`${idPrefix}-difficulty`}>
          难度
          <select
            id={`${idPrefix}-difficulty`}
            className="space-select"
            value={metadata.difficulty}
            disabled={disabled}
            onChange={(event) => setMetadata({ difficulty: event.target.value as Difficulty })}
          >
            {DIFFICULTIES.map((difficulty) => (
              <option key={difficulty} value={difficulty}>
                {DIFFICULTY_LABEL[difficulty]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="qb-field" htmlFor={`${idPrefix}-stem`}>
        题干
        <textarea
          id={`${idPrefix}-stem`}
          className="qb-textarea"
          rows={4}
          value={content.stemMarkdown}
          disabled={disabled}
          onChange={(event) => setContent({ stemMarkdown: event.target.value })}
        />
      </label>

      {showOptions && (
        <fieldset className="qb-fieldset">
          <legend>选项</legend>
          <ul className="qb-option-list">
            {content.options.map((option, index) => (
              <li key={`${option.key}-${index}`} className="qb-option-row">
                <label
                  className="qb-field qb-option-key"
                  htmlFor={`${idPrefix}-option-${index}-key`}
                >
                  选项 {index + 1} 标识
                  <input
                    id={`${idPrefix}-option-${index}-key`}
                    value={option.key}
                    maxLength={8}
                    disabled={disabled}
                    onChange={(event) => {
                      const previous = option.key;
                      const nextKey = event.target.value;
                      const options = content.options.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, key: nextKey } : item,
                      );
                      const migrated = answerKeys.map((key) => (key === previous ? nextKey : key));
                      onChange({
                        ...value,
                        content: {
                          ...content,
                          options,
                          answer: normalizeAnswer({ ...answer, choiceKeys: migrated }),
                        },
                      });
                    }}
                  />
                </label>
                <label
                  className="qb-field qb-option-text"
                  htmlFor={`${idPrefix}-option-${index}-text`}
                >
                  选项 {index + 1} 内容
                  <input
                    id={`${idPrefix}-option-${index}-text`}
                    value={option.textMarkdown}
                    disabled={disabled}
                    onChange={(event) =>
                      setContent({
                        options: content.options.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, textMarkdown: event.target.value }
                            : item,
                        ),
                      })
                    }
                  />
                </label>
                <button
                  type="button"
                  className="space-button"
                  disabled={disabled}
                  aria-label={`删除选项 ${option.key || index + 1}`}
                  onClick={() => {
                    const options = content.options.filter((_, itemIndex) => itemIndex !== index);
                    const keys = answerKeys.filter((key) => key !== option.key);
                    onChange({
                      ...value,
                      content: {
                        ...content,
                        options,
                        answer: normalizeAnswer({ ...answer, choiceKeys: keys }),
                      },
                    });
                  }}
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
          {content.options.length < MAX_OPTIONS && (
            <button
              type="button"
              className="space-button"
              disabled={disabled}
              onClick={() =>
                setContent({
                  options: [
                    ...content.options,
                    { key: nextOptionKey(content.options), textMarkdown: '' },
                  ],
                })
              }
            >
              添加选项
            </button>
          )}
        </fieldset>
      )}

      {content.type === 'single_choice' && (
        <fieldset className="qb-fieldset">
          <legend>答案（单选）</legend>
          <div className="qb-radio-list">
            {content.options.map((option) => (
              <label key={option.key} className="qb-check">
                <input
                  type="radio"
                  name={`${idPrefix}-answer-single`}
                  checked={answerKeys.length === 1 && answerKeys[0] === option.key}
                  disabled={disabled}
                  onChange={() => setAnswerKeys([option.key])}
                />
                {option.key}
              </label>
            ))}
            <label className="qb-check">
              <input
                type="radio"
                name={`${idPrefix}-answer-single`}
                checked={answerKeys.length === 0}
                disabled={disabled}
                onChange={() => setAnswerKeys([])}
              />
              未提供答案
            </label>
          </div>
        </fieldset>
      )}

      {content.type === 'multiple_choice' && (
        <fieldset className="qb-fieldset">
          <legend>答案（多选）</legend>
          <div className="qb-radio-list">
            {content.options.map((option) => (
              <label key={option.key} className="qb-check">
                <input
                  type="checkbox"
                  checked={answerKeys.includes(option.key)}
                  disabled={disabled}
                  onChange={() =>
                    setAnswerKeys(
                      answerKeys.includes(option.key)
                        ? answerKeys.filter((key) => key !== option.key)
                        : [...answerKeys, option.key],
                    )
                  }
                />
                {option.key}
              </label>
            ))}
          </div>
          <p className="qb-hint">全部不选表示原文未提供答案，需要在入库前显式确认。</p>
        </fieldset>
      )}

      {content.type === 'true_false' && (
        <fieldset className="qb-fieldset">
          <legend>答案（判断）</legend>
          <div className="qb-radio-list">
            <label className="qb-check">
              <input
                type="radio"
                name={`${idPrefix}-answer-tf`}
                checked={answer.accepted === true}
                disabled={disabled}
                onChange={() =>
                  setContent({
                    answer: normalizeAnswer({
                      ...answer,
                      choiceKeys: [],
                      accepted: true,
                      textMarkdown: null,
                    }),
                  })
                }
              />
              对
            </label>
            <label className="qb-check">
              <input
                type="radio"
                name={`${idPrefix}-answer-tf`}
                checked={answer.accepted === false}
                disabled={disabled}
                onChange={() =>
                  setContent({
                    answer: normalizeAnswer({
                      ...answer,
                      choiceKeys: [],
                      accepted: false,
                      textMarkdown: null,
                    }),
                  })
                }
              />
              错
            </label>
            <label className="qb-check">
              <input
                type="radio"
                name={`${idPrefix}-answer-tf`}
                checked={answer.accepted === null}
                disabled={disabled}
                onChange={() =>
                  setContent({
                    answer: normalizeAnswer({
                      ...answer,
                      choiceKeys: [],
                      accepted: null,
                      textMarkdown: null,
                    }),
                  })
                }
              />
              未提供答案
            </label>
          </div>
        </fieldset>
      )}

      {(isTextAnswerType(content.type) || content.type === 'other') && (
        <label className="qb-field" htmlFor={`${idPrefix}-answer-text`}>
          答案（文本）
          <textarea
            id={`${idPrefix}-answer-text`}
            className="qb-textarea"
            rows={3}
            value={answer.textMarkdown ?? ''}
            disabled={disabled}
            onChange={(event) =>
              setContent({
                answer: normalizeAnswer({ ...answer, textMarkdown: event.target.value }),
              })
            }
          />
        </label>
      )}

      {content.type === 'other' && (
        <fieldset className="qb-fieldset">
          <legend>答案（可选的选项 key）</legend>
          <div className="qb-radio-list">
            {content.options.map((option) => (
              <label key={option.key} className="qb-check">
                <input
                  type="checkbox"
                  checked={answerKeys.includes(option.key)}
                  disabled={disabled}
                  onChange={() =>
                    setAnswerKeys(
                      answerKeys.includes(option.key)
                        ? answerKeys.filter((key) => key !== option.key)
                        : [...answerKeys, option.key],
                      answer.accepted,
                    )
                  }
                />
                {option.key}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <label className="qb-field" htmlFor={`${idPrefix}-explanation`}>
        解析
        <textarea
          id={`${idPrefix}-explanation`}
          className="qb-textarea"
          rows={3}
          value={content.explanationMarkdown ?? ''}
          disabled={disabled}
          onChange={(event) =>
            setContent({ explanationMarkdown: event.target.value ? event.target.value : null })
          }
        />
      </label>

      <fieldset className="qb-fieldset">
        <legend>分类</legend>
        <div className="qb-form-grid">
          <TaxonomyField
            id={`${idPrefix}-stage`}
            label="学段"
            value={metadata.stageId}
            options={taxonomy.stages}
            ready={taxonomy.ready}
            disabled={disabled}
            onChange={(next) => setMetadata({ stageId: next })}
          />
          <TaxonomyField
            id={`${idPrefix}-grade`}
            label="年级"
            value={metadata.gradeId}
            options={taxonomy.grades}
            ready={taxonomy.ready}
            disabled={disabled}
            onChange={(next) => setMetadata({ gradeId: next })}
          />
          <TaxonomyField
            id={`${idPrefix}-subject`}
            label="学科"
            value={metadata.subjectId}
            options={taxonomy.subjects}
            ready={taxonomy.ready}
            disabled={disabled}
            onChange={(next) => setMetadata({ subjectId: next })}
          />
          <TaxonomyField
            id={`${idPrefix}-edition`}
            label="版本"
            value={metadata.editionId}
            options={taxonomy.editions}
            ready={taxonomy.ready}
            disabled={disabled}
            onChange={(next) => setMetadata({ editionId: next })}
          />
          <label className="qb-field" htmlFor={`${idPrefix}-tags`}>
            历史知识点标签（旧字段）
            <input
              id={`${idPrefix}-tags`}
              value={tagsToText(metadata.knowledgeTags)}
              placeholder="用顿号或逗号分隔"
              disabled={disabled}
              onChange={(event) => setMetadata({ knowledgeTags: tagsFromText(event.target.value) })}
            />
          </label>
        </div>
        <p className="qb-hint">
          旧字段 knowledgeTags 只是文本标签：不会创建正式知识点关联，也不参与知识点筛选；
          正式关联在下方「知识点关联」区块维护，两者分开保留、不合并。
        </p>
        {!taxonomy.ready && (
          <p className="qb-hint">
            分类字典未读取成功：可直接填写分类 id，或稍后重试读取字典后再选。
          </p>
        )}
      </fieldset>
    </div>
  );
}

function TaxonomyField({
  id,
  label,
  value,
  options,
  ready,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: { id: string; label: string }[];
  ready: boolean;
  disabled: boolean;
  onChange: (next: string) => void;
}) {
  if (!ready) {
    return (
      <label className="qb-field" htmlFor={id}>
        {label}
        <input
          id={id}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    );
  }
  return (
    <label className="qb-field" htmlFor={id}>
      {label}
      <select
        id={id}
        className="space-select"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">未设置</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
