import { beforeEach, describe, expect, it } from 'vitest';
import { CollectionStorageError, readStrictList, writeStrictList } from './local-collection';

beforeEach(() => window.localStorage.clear());

/**
 * 跨库存储保护（GAP_AUDIT ①）：books/courses/space/notebook 统一走
 * readStrictList/writeStrictList；损坏数据抛错且原字节保留，不再被空库覆盖。
 * 各 store 的行为等价性由既有用例覆盖；此处验证共享工具本身的契约。
 */
describe('local-collection 存储加固', () => {
  it('键不存在返回空数组；损坏 JSON 与非数组抛错且保留原始字节', () => {
    expect(readStrictList('zhiqikeyuan:test-a')).toEqual([]);
    const damaged = '[{"id":"x"';
    window.localStorage.setItem('zhiqikeyuan:test-a', damaged);
    expect(() => readStrictList('zhiqikeyuan:test-a')).toThrow(CollectionStorageError);
    expect(window.localStorage.getItem('zhiqikeyuan:test-a')).toBe(damaged);

    const broken = '{"not":"array"}';
    window.localStorage.setItem('zhiqikeyuan:test-a', broken);
    expect(() => readStrictList('zhiqikeyuan:test-a')).toThrow(/格式异常/);
    expect(window.localStorage.getItem('zhiqikeyuan:test-a')).toBe(broken);
  });

  it('写前严格校验：目标键损坏时写入抛错且字节不变', () => {
    const damaged = '[broken';
    window.localStorage.setItem('zhiqikeyuan:test-b', damaged);
    expect(() => writeStrictList('zhiqikeyuan:test-b', [{ id: 1 }])).toThrow(CollectionStorageError);
    expect(window.localStorage.getItem('zhiqikeyuan:test-b')).toBe(damaged);
  });

  it('写入被拒（存储异常）时回滚原字节', () => {
    const real = window.localStorage;
    real.setItem('zhiqikeyuan:test-c', JSON.stringify([{ id: 'old' }]));
    const fake = {
      getItem: (key: string) => real.getItem(key),
      setItem: (key: string, value: string) => {
        if (key === 'zhiqikeyuan:test-c') throw new DOMException('QuotaExceededError', 'QuotaExceededError');
        real.setItem(key, value);
      },
      removeItem: (key: string) => real.removeItem(key),
      clear: () => real.clear(),
      key: (index: number) => real.key(index),
      get length() {
        return real.length;
      },
    };
    Object.defineProperty(window, 'localStorage', { configurable: true, get: () => fake });
    try {
      expect(() => writeStrictList('zhiqikeyuan:test-c', [{ id: 'new' }])).toThrow(/已回滚/);
    } finally {
      Object.defineProperty(window, 'localStorage', { configurable: true, value: real });
    }
    expect(JSON.parse(window.localStorage.getItem('zhiqikeyuan:test-c')!)).toEqual([{ id: 'old' }]);
  });

  it('各业务库键损坏时读取抛错（books/courses/space/notebook 同契约）', () => {
    const keys = [
      'zhiqikeyuan:books',
      'zhiqikeyuan:courses',
      'zhiqikeyuan:notebook-entries',
    ];
    for (const key of keys) {
      window.localStorage.setItem(key, '[corrupt');
      expect(() => readStrictList(key), key).toThrow(CollectionStorageError);
      window.localStorage.removeItem(key);
    }
  });
});
