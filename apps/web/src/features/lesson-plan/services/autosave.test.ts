import { describe, it, expect, vi, afterEach } from 'vitest';
import { createDraftWriter } from './autosave';
import { createLessonStore } from '../model/store';
import { makeEnvelope } from './drafts';
import { exampleData } from '../model/defaults';
afterEach(() => vi.useRealTimers());
describe('迁移后的状态与草稿写入', () => {
  it('编辑器实例互相隔离', () => {
    const a = createLessonStore(),
      b = createLessonStore();
    a.getState().set({ title: '实例A' });
    expect(b.getState().data.title).toBe(exampleData.title);
  });
  it('离开页面时立刻同步写入最后一次编辑', async () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const writer = createDraftWriter(
      { load: () => null, save },
      () => {},
      () => {},
    );
    writer.enqueue(makeEnvelope({ ...exampleData, title: '最后一次编辑' }, 1));
    expect(save).not.toHaveBeenCalled();
    const flushed = writer.flush();
    expect(save.mock.calls[0][0].data.title).toBe('最后一次编辑');
    await flushed;
  });
  it('异步保存按顺序执行，旧请求不覆盖新数据', async () => {
    let done!: () => void;
    const save = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<void>((r) => {
            done = r;
          }),
      )
      .mockResolvedValue(undefined);
    const writer = createDraftWriter(
      { load: () => null, save },
      () => {},
      () => {},
    );
    writer.enqueue(makeEnvelope(exampleData, 1));
    const first = writer.flush();
    writer.enqueue(makeEnvelope({ ...exampleData, title: '新版本' }, 2));
    const second = writer.flush();
    expect(save).toHaveBeenCalledTimes(1);
    done();
    await Promise.all([first, second]);
    expect(save.mock.calls.map((c) => c[0].revision)).toEqual([1, 2]);
    expect(writer.isPending()).toBe(false);
  });
  it('保存失败保留待写入版本，允许重试', async () => {
    const error = vi.fn();
    const save = vi.fn().mockRejectedValueOnce(Error('offline')).mockResolvedValue(undefined);
    const writer = createDraftWriter({ load: () => null, save }, () => {}, error);
    writer.enqueue(makeEnvelope(exampleData, 1));
    await expect(writer.flush()).rejects.toThrow('offline');
    expect(writer.isPending()).toBe(true);
    await writer.flush();
    expect(error).toHaveBeenCalledTimes(1);
    expect(writer.isPending()).toBe(false);
  });
});
