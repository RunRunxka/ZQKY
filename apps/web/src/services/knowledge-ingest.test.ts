import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  addKbDocument,
  addKbIndexVersion,
  createKnowledge,
  readKnowledge,
  updateKbDocument,
  type KbDocument,
} from './knowledge-catalog';
import {
  __resetKbIngestsForTest,
  cancelKbDocIngest,
  cancelKbIngestAll,
  KB_INDEX_PROVIDER,
  KB_INGEST_STAGE_DELAY_MS,
  kbSimulatedChunks,
  kbSimulatedParsedChars,
  resumeKbIngests,
  simulateKbDocIngest,
  simulateKbIngestAll,
} from './knowledge-ingest';

const DELAY = 100;

function getDoc(kbId: string, docId: string): KbDocument {
  const doc = readKnowledge()
    .find((kb) => kb.id === kbId)
    ?.docs?.find((item) => item.id === docId);
  if (!doc) throw new Error(`document not found: ${kbId}/${docId}`);
  return doc;
}

function versions(kbId: string) {
  return readKnowledge().find((kb) => kb.id === kbId)?.indexVersions ?? [];
}

beforeEach(() => {
  // 环境兜底：Node 26 内置 experimental localStorage 会在 jsdom 环境下遮蔽
  // window.localStorage（见 extension-catalog.test.ts 既有做法）。
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  });
  window.localStorage.clear();
  vi.useFakeTimers();
});

afterEach(() => {
  __resetKbIngestsForTest();
  vi.useRealTimers();
});

describe('B-H1-KB knowledge-ingest 显式模拟流水线', () => {
  it('正常路径：registered → parsing → indexing → ready，含三阶段进度与确定性产物', () => {
    const kb = createKnowledge('正常库', '');
    const doc = addKbDocument(kb.id, { name: '第一章.md' })!;
    expect(getDoc(kb.id, doc.id).status).toBe('registered');

    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY);
    let current = getDoc(kb.id, doc.id);
    expect(current.status).toBe('parsing');
    expect(current.progress).toEqual({ stage: '解析中', percent: 35 });

    vi.advanceTimersByTime(DELAY);
    current = getDoc(kb.id, doc.id);
    expect(current.status).toBe('indexing');
    expect(current.progress).toEqual({ stage: '索引中', percent: 75 });

    vi.advanceTimersByTime(DELAY);
    current = getDoc(kb.id, doc.id);
    expect(current.status).toBe('ready');
    expect(current.progress).toBeNull();
    // 确定性推导：1200 + name.length * 7；chunks = floor(chars / 400)
    const expectedChars = 1200 + '第一章.md'.length * 7; // 1242
    expect(current.parsedChars).toBe(expectedChars);
    expect(current.parsedChars).toBe(kbSimulatedParsedChars({ name: '第一章.md' }));
    expect(current.chunks).toBe(3);
    expect(current.chunks).toBe(kbSimulatedChunks(expectedChars));
    expect(current.statusNote).toContain('模拟');

    // 单文档全部就绪 → 追加一个索引版本
    const list = versions(kb.id);
    expect(list).toHaveLength(1);
    expect(list[0]!.version).toBe(1);
    expect(list[0]!.docCount).toBe(1);
    expect(list[0]!.chunkCount).toBe(3);
    expect(list[0]!.provider).toBe(KB_INDEX_PROVIDER);
    expect(list[0]!.ready).toBe(true);
  });

  it('fail 路径：以 error 收尾且不追加版本，可重试成功', () => {
    const kb = createKnowledge('失败库', '');
    const doc = addKbDocument(kb.id, { name: '失败演示.md' })!;

    simulateKbDocIngest(kb.id, doc.id, { fail: true, stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    let current = getDoc(kb.id, doc.id);
    expect(current.status).toBe('error');
    expect(current.statusNote).toContain('失败');
    expect(current.progress).toBeNull();
    expect(versions(kb.id)).toHaveLength(0);

    // 重试（不布防失败）：复用同一文档，无需重新登记
    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    current = getDoc(kb.id, doc.id);
    expect(current.status).toBe('ready');
    expect(current.statusNote).not.toContain('失败');
    expect(versions(kb.id)).toHaveLength(1);
  });

  it('取消：进行中 → error + 取消说明，定时器不再推进且可重试', () => {
    const kb = createKnowledge('取消库', '');
    const doc = addKbDocument(kb.id, { name: '取消演示.md' })!;

    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY);
    expect(getDoc(kb.id, doc.id).status).toBe('parsing');

    cancelKbDocIngest(kb.id, doc.id);
    const cancelled = getDoc(kb.id, doc.id);
    expect(cancelled.status).toBe('error');
    expect(cancelled.statusNote).toContain('取消');

    vi.advanceTimersByTime(DELAY * 5);
    expect(getDoc(kb.id, doc.id).status).toBe('error');

    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    expect(getDoc(kb.id, doc.id).status).toBe('ready');
  });

  it('cancelKbIngestAll：库内进行中全部标记取消说明', () => {
    const kb = createKnowledge('批量取消库', '');
    const a = addKbDocument(kb.id, { name: '甲.md' })!;
    const b = addKbDocument(kb.id, { name: '乙.md' })!;

    simulateKbIngestAll(kb.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY);
    expect(getDoc(kb.id, a.id).status).toBe('parsing');
    expect(getDoc(kb.id, b.id).status).toBe('parsing');

    cancelKbIngestAll(kb.id);
    expect(getDoc(kb.id, a.id).status).toBe('error');
    expect(getDoc(kb.id, b.id).status).toBe('error');
    expect(getDoc(kb.id, a.id).statusNote).toContain('取消');
    expect(getDoc(kb.id, b.id).statusNote).toContain('取消');
  });

  it('全部 ready 追加一个版本；重复恢复/重跑不重复追加', () => {
    const kb = createKnowledge('全量库', '');
    const a = addKbDocument(kb.id, { name: '甲.md' })!;
    const b = addKbDocument(kb.id, { name: '乙.md' })!;

    simulateKbIngestAll(kb.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    expect(getDoc(kb.id, a.id).status).toBe('ready');
    expect(getDoc(kb.id, b.id).status).toBe('ready');
    expect(versions(kb.id)).toHaveLength(1);
    const version = versions(kb.id)[0]!;
    expect(version.docCount).toBe(2);
    const expectedChunks =
      kbSimulatedChunks(kbSimulatedParsedChars({ name: '甲.md' })) +
      kbSimulatedChunks(kbSimulatedParsedChars({ name: '乙.md' }));
    expect(version.chunkCount).toBe(expectedChunks);

    // 重复恢复（已无 parsing/indexing）+ 重复全量（ready 跳过）：版本数不变
    resumeKbIngests(kb.id);
    vi.advanceTimersByTime(DELAY * 3);
    simulateKbIngestAll(kb.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    expect(versions(kb.id)).toHaveLength(1);
    expect(versions(kb.id)[0]!.chunkCount).toBe(expectedChunks);
  });

  it('已存在相同 (docCount, chunkCount) 版本时不重复追加', () => {
    const kb = createKnowledge('去重库', '');
    const doc = addKbDocument(kb.id, { name: '第一章.md' })!;
    // 预置与解析结果一致的版本，模拟「刷新后重跑但结果未变」
    addKbIndexVersion(kb.id, { docCount: 1, chunkCount: 3, provider: KB_INDEX_PROVIDER });

    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    expect(getDoc(kb.id, doc.id).status).toBe('ready');
    expect(versions(kb.id)).toHaveLength(1);
  });

  it('resumeKbIngests：parsing/indexing 从下一阶段继续推进', () => {
    const kb = createKnowledge('恢复库', '');
    const a = addKbDocument(kb.id, { name: '甲.md' })!;
    const b = addKbDocument(kb.id, { name: '乙.md' })!;
    updateKbDocument(kb.id, a.id, { status: 'parsing', progress: { stage: '解析中', percent: 35 } });
    updateKbDocument(kb.id, b.id, { status: 'indexing', progress: { stage: '索引中', percent: 75 } });

    // resumeKbIngests 不带 options：使用默认单阶段延迟
    resumeKbIngests(kb.id);
    vi.advanceTimersByTime(KB_INGEST_STAGE_DELAY_MS);
    // a: parsing → indexing；b: indexing → ready
    expect(getDoc(kb.id, a.id).status).toBe('indexing');
    expect(getDoc(kb.id, b.id).status).toBe('ready');
    expect(versions(kb.id)).toHaveLength(0);

    vi.advanceTimersByTime(KB_INGEST_STAGE_DELAY_MS);
    expect(getDoc(kb.id, a.id).status).toBe('ready');
    expect(versions(kb.id)).toHaveLength(1);
    expect(versions(kb.id)[0]!.docCount).toBe(2);
  });

  it('simulateKbDocIngest 对 ready 文档无操作；重复调用取消旧 handle', () => {
    const kb = createKnowledge('无操作库', '');
    const doc = addKbDocument(kb.id, { name: '甲.md' })!;
    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    expect(getDoc(kb.id, doc.id).status).toBe('ready');

    simulateKbDocIngest(kb.id, doc.id, { stageDelayMs: DELAY });
    vi.advanceTimersByTime(DELAY * 3);
    expect(getDoc(kb.id, doc.id).status).toBe('ready');
    expect(versions(kb.id)).toHaveLength(1);
  });
});
