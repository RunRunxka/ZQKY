import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createBook, readBooks, updateBook } from '../../../../apps/web/src/services/books-store'; // 仅修正相对路径：断言与探针语义保持原样

const KEY = 'zhiqikeyuan:books';
const STAMP = `${KEY}-write`;
beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });
afterEach(() => vi.restoreAllMocks());

// These assert the defect exists. Passing is NOT product acceptance.
it('defect: all three conflicts skip data writes but create returns a nonexistent book', () => {
  const get = Storage.prototype.getItem;
  const set = Storage.prototype.setItem;
  let stampReads = 0;
  let dataWrites = 0;
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function(this: Storage, key: string) {
    if (key === STAMP) return JSON.stringify({seq: ++stampReads, writer:'peer'});
    return get.call(this, key);
  });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function(this: Storage, key: string, value: string) {
    if (key === KEY) dataWrites++;
    return set.call(this, key, value);
  });
  const result = createBook('Unsaved but returned', 'User input');
  expect(stampReads).toBe(6);
  expect(dataWrites).toBe(0);
  expect(result.id).toBeTruthy();
  expect(readBooks().some(book => book.id === result.id)).toBe(false);
});

it('defect: peer commits after second stamp check then its saved text is overwritten', () => {
  const a = createBook('A', 'old A');
  const b = createBook('B', 'old B');
  const set = Storage.prototype.setItem;
  let injected = false;
  let peerReadBack = false;
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function(this: Storage, key: string, value: string) {
    if (key === STAMP && !injected) {
      injected = true;
      const saved = updateBook(b.id, {description:'saved peer text'});
      peerReadBack = saved.description === 'saved peer text' &&
        readBooks().find(book => book.id === b.id)?.description === 'saved peer text';
    }
    return set.call(this, key, value);
  });
  const savedA = updateBook(a.id, {description:'saved A text'});
  expect(injected).toBe(true);
  expect(peerReadBack).toBe(true);
  expect(savedA.description).toBe('saved A text');
  expect(readBooks().find(book => book.id === a.id)?.description).toBe('saved A text');
  expect(readBooks().find(book => book.id === b.id)?.description).toBe('old B');
});
