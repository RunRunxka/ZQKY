import { describe, expect, it } from 'vitest';
import { isTextbookEvidence } from './rag-v2';

const evidence = {
  evidenceId: 'ev-demo', documentRevisionId: 'revision-demo', normalizedTextSha256: 'a'.repeat(64),
  charStart: 0, charEnd: 8, documentId: 'document-demo', title: '教材', editionLabel: '示例版本',
  subjectLabel: '数学', chapterPath: ['函数'], text: '一次函数示例原文', originalFileSha256: 'b'.repeat(64),
  locator: { kind: 'markdown', lineStart: 1, lineEnd: 2, pageStart: null, pageEnd: null, blockStart: null, blockEnd: null },
  isSuperseded: false,
};

describe('Python nullable readable compatibility', () => {
  it.each([undefined, null])('accepts an absent readable projection: %s', (readable) => {
    expect(isTextbookEvidence({ ...evidence, readable })).toBe(true);
  });
  it('rejects a malformed nonnull projection', () => {
    expect(isTextbookEvidence({ ...evidence, readable: { version: 'rag-readable-v1', text: 7, removedImageCount: 0 } })).toBe(false);
  });
});
