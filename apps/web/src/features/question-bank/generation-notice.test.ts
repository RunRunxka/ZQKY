/**
 * F10-QB：AI 补题错误码文案。
 * 纪律：模型/配置类失败指向模型服务与模型设置；生成级失败说明「整批失败、零草稿」；
 * 未知码原样转述服务端 message，不编造。
 */

import { describe, expect, it } from 'vitest';
import {
  GENERATION_FAILURE_FALLBACK,
  GENERATION_RETRY_SEMANTICS,
  generationFailureText,
} from './generation-notice';

describe('AI 补题错误文案', () => {
  it('模型服务类失败指向模型服务，不归因到题目内容', () => {
    expect(generationFailureText('AUTH_REQUIRED')).toContain('模型服务认证失败');
    expect(generationFailureText('RATE_LIMITED')).toContain('模型服务限流');
    expect(generationFailureText('UPSTREAM_UNAVAILABLE')).toContain('模型服务当前不可用');
    expect(generationFailureText('MODEL_PROFILE_NOT_FOUND')).toContain('不会自动改用其他模型');
    expect(generationFailureText('MODEL_CONFIG_DRIFT')).toContain('未调用模型');
    expect(generationFailureText('AUTH_REQUIRED')).not.toContain('试题内容无效');
  });

  it('生成级失败一律说明「没有生成任何草稿」', () => {
    for (const code of [
      'GENERATION_INVALID_JSON',
      'GENERATION_OUTPUT_TRUNCATED',
      'GENERATION_CANDIDATE_COUNT_MISMATCH',
      'GENERATION_UNKNOWN_KNOWLEDGE',
      'GENERATION_CONTENT_INVALID',
      'GENERATION_KNOWLEDGE_UNAVAILABLE',
    ]) {
      expect(generationFailureText(code)).toContain('没有生成任何草稿');
    }
  });

  it('入口闸门失败指向可操作下一步', () => {
    expect(generationFailureText('KNOWLEDGE_POINT_ARCHIVED')).toContain('改选在用知识点');
    expect(generationFailureText('KNOWLEDGE_SUBJECT_MISMATCH')).toContain('同一学科');
    expect(generationFailureText('SERVICE_UNAVAILABLE')).toContain('后端');
  });

  it('未知码优先原样转述服务端 message，再回落到统一文案', () => {
    expect(generationFailureText('SOMETHING_NEW', '服务端给的原始原因')).toBe('服务端给的原始原因');
    expect(generationFailureText('SOMETHING_NEW')).toContain('SOMETHING_NEW');
    expect(generationFailureText('SOMETHING_NEW', '')).toBe(
      `AI 补题失败（SOMETHING_NEW）：${GENERATION_FAILURE_FALLBACK}`,
    );
    expect(generationFailureText(null)).toBe(GENERATION_FAILURE_FALLBACK);
  });

  it('重试语义固定：沿用冻结输入与模型，不换当前聊天模型', () => {
    expect(GENERATION_RETRY_SEMANTICS).toContain('冻结');
    expect(GENERATION_RETRY_SEMANTICS).toContain('不会换成当前聊天模型');
  });
});
