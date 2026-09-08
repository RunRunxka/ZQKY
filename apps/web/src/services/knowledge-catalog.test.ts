import { beforeEach, describe, expect, it } from 'vitest';
import {
  addKbDocument,
  addKbSource,
  createKnowledge,
  deleteKnowledge,
  DEMO_KNOWLEDGE,
  KnowledgeValidationError,
  loadDemoKnowledge,
  readKnowledge,
  removeKbDocument,
  removeKbSource,
  setDefaultKnowledge,
  updateKnowledge,
} from './knowledge-catalog';

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
