import React from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { LessonPlanWorkspace } from '@/features/lesson-plan/LessonPlanWorkspace';
import { createLessonStore } from '@/features/lesson-plan/model/store';
import { useServerPersistence } from '@/features/lesson-plan/model/useServerPersistence';
import { emptyData } from '@/features/lesson-plan/model/defaults';
import { serverSessionKey } from '@/features/lesson-plan/model/server-cache';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
function view(version = 1): LessonView {
  const revisionId = `cache-review-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: 'cache-review', subjectId: 'chinese', classId: 'anonymous-class', revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: 'cache-review', revisionId, version,
      data: { ...structuredClone(emptyData), title: '原固定正文', reflection: '教师反思', process: [{ id: 'teacher-stage', stage: '导入', design: '教师正文', secondary: '教师二次备课' }] },
      contentHash: `cache-review-hash-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'anonymous-class', classNameAtSave: '匿名隔离班', analysis: null },
      analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' } };
}
function bag() {
  const values = new Map<string, string>();
  let failed = true;
  const storage = { getItem: (key: string) => values.get(key) ?? null,
    setItem: vi.fn((key: string, value: string) => { if (failed) throw new Error('隔离注入的一次可恢复写失败'); values.set(key, value); }),
    removeItem: vi.fn((key: string) => { values.delete(key); }), clear: () => values.clear(), key: (index: number) => [...values.keys()][index] ?? null,
    get length() { return values.size; },
  } satisfies Storage;
  return { storage, values, recover: () => { failed = false; } };
}
function api() {
  return { ...lessonPlanApi, getLesson: vi.fn(async () => view()), listLessons: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 50 })),
    saveLesson: vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, body) => ({ ...view(2), currentRevision: { ...view(2).currentRevision, data: structuredClone(body.data) } })) };
}
beforeEach(() => {
  localStorage.clear(); router.push.mockReset(); router.replace.mockReset();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); });

describe('B6 review cache retry via current public editor controls', () => {
  it('EXPECTED: a recovered storage must leave a public explicit save retry for the unique input', async () => {
    const storage = bag(), services = api();
    render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId="cache-review" services={{ lessonApi: services, recoveryStorage: storage.storage }} /></NavigationPreference>);
    await screen.findByLabelText('课题');
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '仅存在当前编辑器的教师新正文' } });
    expect(screen.getByLabelText('课题')).toHaveValue('仅存在当前编辑器的教师新正文');
    expect(screen.getByLabelText('课题')).toBeDisabled();
    expect(storage.values.get(serverSessionKey('cache-review'))).toBeUndefined();
    expect(services.saveLesson).not.toHaveBeenCalled();
    storage.recover();
    fireEvent.click(screen.getByRole('button', { name: '读取后台最新版本' }));
    await waitFor(() => expect(services.getLesson).toHaveBeenCalledTimes(2));
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: '学习问答' }));
    await screen.findByRole('dialog', { name: '离开当前教案' });
    expect(screen.getByRole('button', { name: '保存成功后离开' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '保留恢复缓存后离开' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '明确放弃未保存编辑后离开' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '取消离开，继续编辑' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '离开当前教案' })).not.toBeInTheDocument());
    // Correct behavior oracle: there must be a public retry after the transient storage condition has recovered.
    expect(screen.getByRole('button', { name: '保存后台稿' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: '保存后台稿' }));
    await waitFor(() => expect(services.saveLesson).toHaveBeenCalledTimes(1));
    expect(services.saveLesson.mock.calls[0][1].data.title).toBe('仅存在当前编辑器的教师新正文');
  });

  it('CONTROL: existing server.save can recover the identical cached body after the storage condition clears', async () => {
    const storage = bag(), services = api(), store = createLessonStore();
    const hook = renderHook(() => useServerPersistence(store, { view: view(), api: services, storage: storage.storage }));
    act(() => store.getState().set({ title: '仅存在当前编辑器的教师新正文' }));
    const before = structuredClone(store.getState().data);
    expect(hook.result.current.syncState).toBe('cache_error');
    storage.recover();
    await act(async () => { expect(await hook.result.current.save()).toBe(true); });
    expect(services.saveLesson).toHaveBeenCalledTimes(1);
    expect(services.saveLesson.mock.calls[0][1].data).toEqual(before);
    expect(hook.result.current.syncState).toBe('saved');
  });

  it('BACKUP: public JSON backup still freezes the in-memory full body while cache_error blocks normal saving', async () => {
    const storage = bag(), services = api(), downloaded: string[] = [];
    let blob: Blob | undefined;
    const OriginalURL = URL;
    vi.stubGlobal('URL', class extends OriginalURL {
      static createObjectURL(value: Blob) { blob = value; return 'blob:review-only'; }
      static revokeObjectURL() {}
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { downloaded.push(this.download); });
    render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId="cache-review" services={{ lessonApi: services, recoveryStorage: storage.storage }} /></NavigationPreference>);
    await screen.findByLabelText('课题');
    const edited = { ...view().currentRevision.data, title: '仅存在当前编辑器的教师新正文' };
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: edited.title } });
    expect(screen.getByLabelText('课题')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '导出教案' }));
    fireEvent.click(screen.getByRole('button', { name: /备份草稿/ }));
    expect(downloaded).toHaveLength(1);
    expect(downloaded[0]).toMatch(/\.json$/);
    const raw = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(reader.error); reader.readAsText(blob!);
    });
    const envelope = JSON.parse(raw);
    expect(envelope.schemaVersion).toBe(1);
    expect(envelope.revision).toBe(1);
    expect(envelope.data).toEqual(edited);
    expect(services.saveLesson).not.toHaveBeenCalled();
    expect(storage.values.get(serverSessionKey('cache-review'))).toBeUndefined();
  });
});
