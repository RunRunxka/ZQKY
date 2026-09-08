import 'fake-indexeddb/auto';
import { describe, it, expect } from 'vitest';
import { createIdbChatRepository } from './chat-repository';
const doc = {
  id: 'one',
  title: '旧会话',
  messages: [],
  createdAt: '2026-09-06',
  updatedAt: '2026-09-06',
};
describe('IndexedDB transaction persistence', () => {
  it('兼容旧记录，事务提交后返回版本，拒绝两个标签页的静默覆盖', async () => {
    const name = crypto.randomUUID(),
      a = createIdbChatRepository(name),
      b = createIdbChatRepository(name);
    expect(await a.save(doc, 0)).toBe(1);
    const old = await b.load('one');
    expect(old?.schemaVersion).toBe(1);
    expect(await a.save({ ...doc, title: '新内容' }, 1)).toBe(2);
    await expect(b.save({ ...old!, title: '过期内容' }, 1)).rejects.toThrow('其他标签页');
    expect((await a.load('one'))?.title).toBe('新内容');
    await expect(b.remove('one', 1)).rejects.toThrow('其他标签页');
  });
  it('未知数据版本不覆盖原记录', async () => {
    const a = createIdbChatRepository(crypto.randomUUID());
    await a.save(doc, 0);
    await expect(a.save({ ...doc, schemaVersion: 99 }, 1)).rejects.toThrow('格式不受支持');
    expect((await a.load('one'))?.title).toBe('旧会话');
  });
  it('S5-A 归档位随会话保存与读取（旧记录缺省视为未归档）', async () => {
    const a = createIdbChatRepository(crypto.randomUUID());
    await a.save(doc, 0);
    expect((await a.load('one'))?.archived).toBeUndefined();
    const loaded = await a.load('one');
    await a.save({ ...loaded!, archived: true }, loaded!.revision ?? 0);
    expect((await a.load('one'))?.archived).toBe(true);
  });
});
