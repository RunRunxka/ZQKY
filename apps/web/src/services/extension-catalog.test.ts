// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  readExtensions,
  removeExtension,
  saveExtension,
  subscribeExtensions,
  type ExtensionEntry,
} from './extension-catalog';
const entry: ExtensionEntry = {
  id: 'one',
  kind: 'skill',
  name: '课堂提问',
  description: '模拟',
  content: '提出问题',
  enabled: false,
};
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  });
});
describe('独立模拟扩展目录', () => {
  it('保存、启用和删除广播同一目录变化', () => {
    const listener = vi.fn();
    const dispose = subscribeExtensions(listener);
    saveExtension(entry);
    saveExtension({ ...entry, enabled: true });
    expect(readExtensions()).toEqual([{ ...entry, enabled: true }]);
    removeExtension(entry.id);
    expect(readExtensions()).toEqual([]);
    expect(listener).toHaveBeenCalledTimes(3);
    dispose();
    saveExtension(entry);
    expect(listener).toHaveBeenCalledTimes(3);
  });
  it('拒绝重名且不覆盖已有配置', () => {
    saveExtension(entry);
    expect(() => saveExtension({ ...entry, id: 'two' })).toThrow('名称已存在');
    expect(readExtensions()).toEqual([entry]);
  });
  it('损坏存储不会被写入操作静默覆盖', () => {
    window.localStorage.setItem('zqky.replica.extensions.v1', 'broken');
    expect(() => saveExtension(entry)).toThrow();
    expect(window.localStorage.getItem('zqky.replica.extensions.v1')).toBe('broken');
  });
});
