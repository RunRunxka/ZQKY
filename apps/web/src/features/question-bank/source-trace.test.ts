/**
 * F10-QB：AI 候选来源追溯（批次里 extractionMethod=ai 的草稿数）。
 * 断言方向：0 条与「读不到批次」必须可区分；确认状态照实转述，不声称自动入库。
 */

import { describe, expect, it } from 'vitest';
import type { DraftView, QuestionImportDetail } from '@/contracts/question-bank';
import { aiSourceTraceOf, aiSourceTraceText, aiSourceTraceUnavailableText } from './source-trace';

const CONTENT = {
  type: 'single_choice' as const,
  stemMarkdown: '题干',
  options: [{ key: 'A', textMarkdown: '甲' }],
  answer: null,
  explanationMarkdown: null,
  assetIds: [],
};

function draft(extractionMethod: DraftView['extractionMethod'], draftId: string): DraftView {
  return {
    draftId,
    importId: 'imp-1',
    revision: 1,
    content: CONTENT,
    metadata: {
      stageId: '',
      gradeId: '',
      subjectId: 'math',
      editionId: '',
      knowledgeTags: [],
      difficulty: 'unspecified',
    },
    sourceSpans: [],
    extractionMethod,
    reviewState: 'needs_review',
    missingAnswerAcknowledged: false,
    warnings: [],
    duplicateOfQuestionId: null,
    knowledgeLinks: [],
  };
}

function detail(overrides: Partial<QuestionImportDetail> = {}): QuestionImportDetail {
  return {
    importId: 'imp-1',
    ownerId: 'local-user',
    state: 'confirmed',
    revision: 1,
    uploadedFileName: 'ai-generation-job-1.json',
    uploadedBytes: 10,
    draftCount: 2,
    reviewedCount: 0,
    unassignedCount: 0,
    warnings: [],
    createdAt: '2026-10-01T00:00:00Z',
    drafts: [draft('ai', 'd-1'), draft('rule', 'd-2')],
    unassignedBlocks: [],
    ...overrides,
  };
}

describe('AI 候选来源追溯', () => {
  it('统计 AI 草稿数并转述批次确认状态', () => {
    const trace = aiSourceTraceOf(detail());
    expect(trace).toEqual({ aiDraftCount: 1, draftCount: 2, confirmed: true });
    const text = aiSourceTraceText(trace);
    expect(text).toContain('1/2');
    expect(text).toContain('extractionMethod=ai');
    expect(text).toContain('必须人工校对并确认后才成为题目');
  });

  it('没有 AI 草稿时明确说「没有 AI 来源」，不说成无法核对', () => {
    const trace = aiSourceTraceOf(detail({ drafts: [draft('rule', 'd-1')] }));
    expect(trace.aiDraftCount).toBe(0);
    expect(aiSourceTraceText(trace)).toContain('没有 AI 来源草稿');
  });

  it('未确认批次不声称已入库；读取失败保留错误码且不当成「没有 AI 候选」', () => {
    const pending = aiSourceTraceOf(detail({ state: 'needs_review' }));
    expect(aiSourceTraceText(pending)).toContain('还未确认入库');
    const unavailable = aiSourceTraceUnavailableText('SERVICE_UNAVAILABLE', '题库服务未装配。');
    expect(unavailable).toContain('SERVICE_UNAVAILABLE');
    expect(unavailable).toContain('无法核对');
  });
});
