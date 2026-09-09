import { beforeEach, describe, expect, it } from 'vitest';
import {
  createDocument,
  deleteDocument,
  getDocument,
  listDocuments,
  renameDocument,
  restoreVersion,
  saveDocumentContent,
  snapshotVersion,
} from './writing-store';
import {
  composeWritingAiResult,
  createWritingAiService,
} from '@/features/writing/writing-ai';

beforeEach(() => window.localStorage.clear());

describe('writing-store（S5-E）', () => {
  it('创建/重命名/自动保存/删除往返；空内容自动保存幂等', () => {
    const doc = createDocument({ title: '教学文稿' });
    expect(doc.content).toBe('');
    expect(renameDocument(doc.docId, '教学文稿（改）')?.title).toBe('教学文稿（改）');
    expect(() => renameDocument(doc.docId, '  ')).toThrow(/标题不能为空/);
    saveDocumentContent(doc.docId, '第一段内容。');
    expect(getDocument(doc.docId)?.content).toBe('第一段内容。');
    // 内容不变不产生更新
    const current = getDocument(doc.docId)!;
    saveDocumentContent(doc.docId, '第一段内容。');
    expect(getDocument(doc.docId)?.updatedAt).toBe(current.updatedAt);
    expect(deleteDocument(doc.docId)).toBe(true);
    expect(getDocument(doc.docId)).toBeNull();
  });

  it('模板创建；列表按更新时间倒序', async () => {
    const a = createDocument({ title: 'A', withTemplate: true });
    expect(a.content).toContain('教学设计示例');
    await new Promise((resolve) => setTimeout(resolve, 5));
    const b = createDocument({ title: 'B' });
    await new Promise((resolve) => setTimeout(resolve, 5));
    saveDocumentContent(b.docId, '最新更新');
    expect(listDocuments()[0]!.docId).toBe(b.docId);
  });

  it('版本：快照/恢复（恢复前自动快照，可恢复回来）', () => {
    const doc = createDocument({ title: '版本文稿' });
    saveDocumentContent(doc.docId, 'v1 内容');
    snapshotVersion(doc.docId, 'v1 版本');
    saveDocumentContent(doc.docId, 'v2 内容');
    const version = getDocument(doc.docId)!.versions[0]!;
    restoreVersion(doc.docId, version.versionId);
    expect(getDocument(doc.docId)?.content).toBe('v1 内容');
    // 恢复动作本身生成“恢复前自动快照”，内容可再恢复
    const versions = getDocument(doc.docId)!.versions;
    expect(versions).toHaveLength(2);
    expect(versions[1]!.label).toContain('恢复前自动快照');
    expect(versions[1]!.content).toBe('v2 内容');
  });
});

describe('writing-ai（S5-E 显式模拟）', () => {
  const service = createWritingAiService({ chunkDelayMs: 0 });

  it('改写/润色/扩写/生成结果均带【模拟生成】标注', () => {
    for (const mode of ['rewrite', 'polish', 'expand', 'generate'] as const) {
      const result = composeWritingAiResult({ mode, instruction: '', sourceText: '原文句子。' });
      expect(result).toContain('【模拟生成】');
    }
  });

  it('流式输出多段增量并以 end 收尾；指令纳入结果', async () => {
    const events: Array<{ type: string; delta?: string }> = [];
    await service.run(
      { docId: 'doc-1', turnId: 't1', mode: 'rewrite', instruction: '更口语化', sourceText: '原文内容', signal: new AbortController().signal },
      (event) => events.push(event),
    );
    expect(events[0]!.type).toBe('turn-start');
    expect(events[events.length - 1]!.type).toBe('end');
    const text = events.filter((event) => event.type === 'text').map((event) => event.delta ?? '').join('');
    expect(text).toContain('更口语化');
    expect(events.filter((event) => event.type === 'text').length).toBeGreaterThan(2);
  });

  it('armFailure：一次可重试错误，重试后正常', async () => {
    const failing: Array<{ type: string }> = [];
    service.armFailure();
    await service.run({ docId: 'd', turnId: 't', mode: 'polish', instruction: '', sourceText: 'x', signal: new AbortController().signal }, (event) => failing.push(event));
    expect(failing.some((event) => event.type === 'error')).toBe(true);
    const ok: Array<{ type: string }> = [];
    await service.run({ docId: 'd', turnId: 't', mode: 'polish', instruction: '', sourceText: 'x', signal: new AbortController().signal }, (event) => ok.push(event));
    expect(ok[ok.length - 1]!.type).toBe('end');
  });

  it('取消：中止后不再有新事件', async () => {
    const controller = new AbortController();
    const events: Array<{ type: string }> = [];
    const run = service.run(
      { docId: 'd', turnId: 't', mode: 'expand', instruction: '', sourceText: 'x', signal: controller.signal },
      (event) => {
        events.push(event);
        if (event.type === 'text') controller.abort();
      },
    );
    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
    const count = events.length;
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(events.length).toBe(count);
  });
});
