import { beforeEach, expect, it } from 'vitest';
import {
  addAnnotation, addBookmark, appendMessage, createMaterial, createSession,
  createWorkspace, deleteWorkspace, loadDemoReading, readAnnotations,
  readBookmarks, readMaterials, readSessions,
} from '../../../apps/web/src/services/reading-store';

beforeEach(() => window.localStorage.clear());

it('R26: loading demo preserves existing user annotations, bookmarks and sessions', () => {
  const material = createMaterial({ title: '用户材料', text: '用户笔记原文' });
  const workspace = createWorkspace('用户集合');
  const annotation = addAnnotation({ materialId: material.id, kind: 'note', quote: material.text, note: '不能丢失' });
  const bookmark = addBookmark(material.id, 'p-0', '用户书签');
  const session = createSession(workspace.id, material.id);
  appendMessage(session.id, { role: 'user', content: '我的问题' });
  const savedSession = readSessions().find((item) => item.id === session.id);
  loadDemoReading();
  expect.soft(readAnnotations()).toContainEqual(annotation);
  expect.soft(readBookmarks()).toContainEqual(bookmark);
  expect.soft(readSessions()).toContainEqual(savedSession);
});

it('R26: deleting the demo workspace and loading demo again does not duplicate material identities', () => {
  loadDemoReading();
  deleteWorkspace('demo-reading-ws');
  loadDemoReading();
  const ids = readMaterials().map((item) => item.id);
  expect(new Set(ids).size).toBe(ids.length);
});

it('R27: corrupt storage must be reported and preserved instead of replaced on the next write', () => {
  const key = 'zhiqikeyuan:reading-materials';
  const damaged = '[{"id":"precious","text":"recoverable"}';
  window.localStorage.setItem(key, damaged);
  expect.soft(() => createMaterial({ title: '新材料', text: '新正文' })).toThrow();
  expect(window.localStorage.getItem(key)).toBe(damaged);
});
