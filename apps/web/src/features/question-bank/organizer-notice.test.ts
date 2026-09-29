import { describe, expect, it } from 'vitest';
import {
  isOrganizerBatchFailure,
  ORGANIZER_CANCELLED_NOTICE,
  ORGANIZER_FAILURE_COPY,
  ORGANIZER_FAILURE_FALLBACK,
  ORGANIZER_SUGGESTION_SEMANTICS,
  organizerFailureText,
  organizerStaleSuggestionText,
} from './organizer-notice';

/** 归因纪律：上游/模型问题不得写成题目内容问题。 */
const FORBIDDEN_ATTRIBUTIONS = ['试题内容无效', '题目内容无效', '题目内容有问题', '题目错误'];

describe('AI 整理错误文案：五类失败', () => {
  it('认证 / 限流 / 网络一律指向模型服务，并给出下一步', () => {
    expect(organizerFailureText('AUTH_REQUIRED')).toContain('模型服务认证失败');
    expect(organizerFailureText('AUTH_REQUIRED')).toContain('「模型设置」');
    expect(organizerFailureText('RATE_LIMITED')).toContain('模型服务限流');
    expect(organizerFailureText('RATE_LIMITED')).toContain('其他聊天模型');
    expect(organizerFailureText('UPSTREAM_UNAVAILABLE')).toContain('模型服务当前不可用');
    expect(organizerFailureText('UPSTREAM_UNAVAILABLE')).toContain('网络或上游故障');
  });

  it('模型配置类失败提示修复，并声明不会自动改用其他模型', () => {
    for (const code of [
      'MODEL_NOT_CONFIGURED',
      'MODEL_PROFILE_NOT_FOUND',
      'MODEL_PURPOSE_MISMATCH',
    ]) {
      const text = organizerFailureText(code);
      expect(text).toContain('「模型设置」');
      expect(text).toContain('不会自动改用其他模型');
    }
  });

  it('截断与非法 JSON：该批未生成可应用建议，原文与草稿未被修改', () => {
    const truncated = organizerFailureText('ORGANIZER_OUTPUT_TRUNCATED');
    expect(truncated).toContain('截断');
    expect(truncated).toContain('该批未生成可应用建议，原文与草稿未被修改');

    const invalidJson = organizerFailureText('ORGANIZER_INVALID_JSON');
    expect(invalidJson).toContain('不是合法 JSON');
    expect(invalidJson).toContain('该批未生成可应用建议，原文与草稿未被修改');

    expect(organizerFailureText('ORGANIZER_INVALID_CONTENT')).toContain(
      '该批未生成可应用建议，原文与草稿未被修改',
    );
    expect(organizerFailureText('ORGANIZER_UNKNOWN_SOURCE_BLOCK')).toContain(
      '该批未生成可应用建议，原文与草稿未被修改',
    );
  });

  it('旧语义任务：要求重新选择模型，并声明建议已保留', () => {
    const text = organizerFailureText('ORGANIZER_MODEL_RESELECT_REQUIRED');
    expect(text).toContain('该整理任务是在旧版本下创建的');
    expect(text).toContain('重新选择模型');
    expect(text).toContain('已生成的建议已保留');
  });

  it('取消：在途未完成批次的建议不会保存', () => {
    expect(ORGANIZER_CANCELLED_NOTICE).toContain('在途未完成批次的建议不会保存');
    expect(ORGANIZER_CANCELLED_NOTICE).toContain('已完成批次的建议仍保留');
  });

  it('未知错误码优先原样转述服务端 message，不编造文案', () => {
    expect(organizerFailureText('SOMETHING_NEW', '上游返回了新的失败原因。')).toBe(
      '上游返回了新的失败原因。',
    );
    expect(organizerFailureText('SOMETHING_NEW', '   ')).toContain('SOMETHING_NEW');
    expect(organizerFailureText(null)).toBe(ORGANIZER_FAILURE_FALLBACK);
  });

  it('所有已知文案都不把失败归因到题目内容', () => {
    for (const [code, text] of Object.entries(ORGANIZER_FAILURE_COPY)) {
      expect(text.length).toBeGreaterThan(0);
      for (const forbidden of FORBIDDEN_ATTRIBUTIONS) {
        expect(`${code}:${text}`).not.toContain(forbidden);
      }
    }
  });

  it('批级失败码表与服务端分类一致', () => {
    expect(isOrganizerBatchFailure('ORGANIZER_OUTPUT_TRUNCATED')).toBe(true);
    expect(isOrganizerBatchFailure('ORGANIZER_INVALID_JSON')).toBe(true);
    expect(isOrganizerBatchFailure('ORGANIZE_DRAFT_CHANGED')).toBe(true);
    expect(isOrganizerBatchFailure('AUTH_REQUIRED')).toBe(false);
    expect(isOrganizerBatchFailure('MODEL_PROFILE_NOT_FOUND')).toBe(false);
    expect(isOrganizerBatchFailure(null)).toBe(false);
  });

  it('建议语义与过期建议提示都明说「不覆盖人工草稿 / 不会自动入库」', () => {
    expect(ORGANIZER_SUGGESTION_SEMANTICS).toContain('永不直接覆盖人工草稿');
    expect(ORGANIZER_SUGGESTION_SEMANTICS).toContain('不会自动入库');
    expect(organizerStaleSuggestionText(3, 5)).toContain('r3 → 当前 r5');
    expect(organizerStaleSuggestionText(3, null)).toContain('草稿已不在批次中');
  });
});
