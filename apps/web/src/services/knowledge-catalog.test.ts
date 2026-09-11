import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  addKbDocument,
  addKbIndexVersion,
  addKbSource,
  createKnowledge,
  deleteKnowledge,
  DEMO_KNOWLEDGE,
  kbPipelineSummary,
  KnowledgeValidationError,
  loadDemoKnowledge,
  readKnowledge,
  removeKbDocument,
  removeKbSource,
  setDefaultKnowledge,
  updateKbDocument,
  updateKnowledge,
  type KbDocument,
  type KnowledgeEntry,
} from './knowledge-catalog';

const RAW_KEY = 'zqky.replica.knowledge.v1';

/**
 * 环境兜底：Node 26 内置 experimental localStorage 会在 jsdom 环境下遮蔽
 * `window.localStorage`（未提供 --localstorage-file 时为空）。这里以内存实现
 * 显式 stub，保证测试稳定，与 extension-catalog.test.ts 的既有做法一致。
 */
function stubLocalStorage() {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  });
}

beforeEach(() => {
  stubLocalStorage();
  window.localStorage.clear();
});

/**
 * S5-B 知识库目录：S2 聊天知识来源与 S5-B 业务页共用同一份本地目录。
 * CRUD/默认库/文档登记（不解析）/来源登记（不同步）。
 */

describe('S5-B knowledge-catalog 业务操作', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('演示数据显式载入且幂等；旧格式数据兼容读取', () => {
    loadDemoKnowledge();
    loadDemoKnowledge();
    const list = readKnowledge();
    expect(list).toHaveLength(DEMO_KNOWLEDGE.length);
    expect(list.filter((kb) => kb.isDefault)).toHaveLength(1);
    expect(list.every((kb) => (kb.docs?.length ?? 0) > 0)).toBe(true);
  });

  it('新建/更新/删除知识库：重名与空名校验', () => {
    expect(() => createKnowledge('  ', '')).toThrow(KnowledgeValidationError);
    const kb = createKnowledge('七年级数学资料', '章节材料');
    expect(kb.docs).toEqual([]);
    expect(() => createKnowledge('七年级数学资料', '')).toThrow(KnowledgeValidationError);
    expect(updateKnowledge(kb.id, { name: '七年级数学（改）' }).name).toBe('七年级数学（改）');
    expect(() => updateKnowledge(kb.id, { name: '  ' })).toThrow(KnowledgeValidationError);
    expect(deleteKnowledge(kb.id)).toBe(true);
    expect(deleteKnowledge(kb.id)).toBe(false);
  });

  it('默认库唯一：设置与删除不自动指定新默认', () => {
    const a = createKnowledge('库A', '');
    const b = createKnowledge('库B', '');
    setDefaultKnowledge(a.id);
    expect(readKnowledge().filter((kb) => kb.isDefault).map((kb) => kb.id)).toEqual([a.id]);
    setDefaultKnowledge(b.id);
    expect(readKnowledge().filter((kb) => kb.isDefault).map((kb) => kb.id)).toEqual([b.id]);
    deleteKnowledge(b.id);
    expect(readKnowledge().filter((kb) => kb.isDefault)).toHaveLength(0);
  });

  it('文档登记与移除：仅元信息、空名拒绝', () => {
    const kb = createKnowledge('登记测试库', '');
    const doc = addKbDocument(kb.id, { name: '第一章.md', size: 1024 });
    expect(doc).not.toBeNull();
    expect(addKbDocument(kb.id, { name: '  ' })).toBeNull();
    expect(readKnowledge().find((item) => item.id === kb.id)!.docs).toHaveLength(1);
    expect(removeKbDocument(kb.id, doc!.id)).toBe(true);
    expect(readKnowledge().find((item) => item.id === kb.id)!.docs).toHaveLength(0);
  });

  it('来源登记与移除：github/web 仅登记', () => {
    const kb = createKnowledge('来源测试库', '');
    const source = addKbSource(kb.id, 'github', 'https://github.com/owner/repo');
    expect(source).not.toBeNull();
    expect(addKbSource(kb.id, 'web', '   ')).toBeNull();
    expect(readKnowledge().find((item) => item.id === kb.id)!.sources).toHaveLength(1);
    expect(removeKbSource(kb.id, source!.id)).toBe(true);
    expect(readKnowledge().find((item) => item.id === kb.id)!.sources).toHaveLength(0);
  });
});

describe('B-H1-KB knowledge-catalog：状态/索引版本/归一化', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('addKbDocument 返回 doc 带 status registered', () => {
    const kb = createKnowledge('状态测试库', '');
    const doc = addKbDocument(kb.id, { name: '第一章.md', size: 1024 })!;
    expect(doc.status).toBe('registered');
    expect(readKnowledge().find((item) => item.id === kb.id)!.docs![0]!.status).toBe('registered');
  });

  it('旧数据缺 status/indexVersions：读取归一化但不写回 localStorage', () => {
    const legacy = [
      {
        id: 'legacy-kb',
        name: '旧库',
        description: '旧格式',
        docs: [{ id: 'legacy-doc', name: '旧文档.md', size: 100, registeredAt: '2026-09-01T00:00:00.000Z' }],
      },
    ];
    const raw = JSON.stringify(legacy);
    window.localStorage.setItem(RAW_KEY, raw);

    const list = readKnowledge();
    expect(list[0]!.indexVersions).toEqual([]);
    expect(list[0]!.docs![0]!.status).toBe('registered');
    // 归一化仅为内存行为：底层存储必须保持原样，不写入 status/indexVersions
    expect(window.localStorage.getItem(RAW_KEY)).toBe(raw);
  });

  it('updateKbDocument：局部更新并返回更新后文档；找不到返回 null', () => {
    const kb = createKnowledge('更新测试库', '');
    const doc = addKbDocument(kb.id, { name: '材料.md' })!;
    const updated = updateKbDocument(kb.id, doc.id, {
      status: 'parsing',
      progress: { stage: '解析中', percent: 35 },
    });
    expect(updated).not.toBeNull();
    expect(updated!.status).toBe('parsing');
    expect(updated!.progress).toEqual({ stage: '解析中', percent: 35 });
    expect(readKnowledge().find((item) => item.id === kb.id)!.docs![0]!.status).toBe('parsing');
    expect(updateKbDocument(kb.id, 'missing-doc', { status: 'ready' })).toBeNull();
    expect(updateKbDocument('missing-kb', doc.id, { status: 'ready' })).toBeNull();
  });

  it('addKbIndexVersion：version 从 1 递增', () => {
    const kb = createKnowledge('版本测试库', '');
    const v1 = addKbIndexVersion(kb.id, { docCount: 1, chunkCount: 3, provider: '内置本地索引（模拟）' });
    expect(v1!.version).toBe(1);
    expect(v1!.ready).toBe(true);
    const v2 = addKbIndexVersion(kb.id, { docCount: 2, chunkCount: 8, provider: '内置本地索引（模拟）' });
    expect(v2!.version).toBe(2);
    expect(readKnowledge().find((item) => item.id === kb.id)!.indexVersions).toHaveLength(2);
    expect(addKbIndexVersion('missing-kb', { docCount: 1, chunkCount: 1, provider: 'x' })).toBeNull();
  });

  it('kbPipelineSummary：各分支与优先级', () => {
    const entry = (docs: KnowledgeEntry['docs']): KnowledgeEntry => ({
      id: 'k',
      name: 'k',
      description: '',
      docs,
    });
    const doc = (status: KbDocument['status']): KbDocument => ({
      id: Math.random().toString(36),
      name: 'd',
      registeredAt: '2026-09-01T00:00:00.000Z',
      status,
    });

    expect(kbPipelineSummary(entry([])).status).toBe('empty');

    const registered = kbPipelineSummary(entry([doc('registered')]));
    expect(registered).toEqual({ total: 1, ready: 0, error: 0, active: 0, status: 'registered' });

    // active 优先于 error/ready
    const processing = kbPipelineSummary(
      entry([doc('parsing'), doc('error'), doc('ready')]),
    );
    expect(processing.status).toBe('processing');
    expect(processing.active).toBe(1);
    expect(processing.error).toBe(1);

    const errored = kbPipelineSummary(entry([doc('ready'), doc('error')]));
    expect(errored.status).toBe('error');
    expect(errored.ready).toBe(1);
    expect(errored.error).toBe(1);

    const ready = kbPipelineSummary(entry([doc('ready'), doc('ready')]));
    expect(ready).toEqual({ total: 2, ready: 2, error: 0, active: 0, status: 'ready' });
  });
});
