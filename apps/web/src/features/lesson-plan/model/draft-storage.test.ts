/**
 * 本地草稿信封：归档键兼容读取、排版/模块缺省补全、坏稿不覆盖、云端 id 记忆。
 */
import { describe, expect, it } from 'vitest';
import {
  ACTIVE_PLAN_KEY,
  LOCAL_DRAFT_KEY,
  clearActivePlanId,
  clearLocalDraft,
  normalizeDraftEnvelope,
  readActivePlanId,
  readLocalDraft,
  readRawLocalDraft,
  writeActivePlanId,
  writeLocalDraft,
  type WorkbenchDraft,
} from './draft-storage';
import { DEFAULT_LESSON_STYLE, defaultModuleLayout } from './modules';
import { emptyLessonData } from './lesson-data';

function memoryStorage(seed: Record<string, string> = {}): Storage {
  const map = new Map(Object.entries(seed));
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => void map.delete(key),
    setItem: (key: string, value: string) => void map.set(key, value),
  } as Storage;
}

function draft(): WorkbenchDraft {
  const data = emptyLessonData();
  data.title = '荷塘月色';
  return {
    data,
    modules: defaultModuleLayout(),
    removed: [{ id: 'custom-9', kind: 'custom', label: '已移除模块', hidden: false, body: '内容' }],
    style: { ...DEFAULT_LESSON_STYLE, baseSize: 16, fontId: 'misans' },
    revision: 3,
    updatedAt: '2026-10-12T08:00:00.000Z',
  };
}

describe('本地草稿读写', () => {
  it('写入后可完整读回（正文、排版、模块、已移除项）', () => {
    const storage = memoryStorage();
    writeLocalDraft(storage, draft());
    const result = readLocalDraft(storage);
    expect(result.status).toBe('ok');
    if (result.status !== 'ok') return;
    expect(result.draft.data.title).toBe('荷塘月色');
    expect(result.draft.style.baseSize).toBe(16);
    expect(result.draft.style.fontId).toBe('misans');
    expect(result.draft.modules).toHaveLength(7);
    expect(result.draft.removed.map((entry) => entry.id)).toEqual(['custom-9']);
  });

  it('读取归档旧草稿（只有 data，没有 style/modules）：补默认值，不报错', () => {
    const storage = memoryStorage({
      [LOCAL_DRAFT_KEY]: JSON.stringify({
        schemaVersion: 1,
        revision: 2,
        updatedAt: '2026-10-01T00:00:00.000Z',
        data: { title: '旧教案', totalLessons: '2', currentLessonNo: '1', lessonTypes: ['review'], otherTypeText: '', coreCompetencies: '', keyPoints: '', teachingDesign: '', process: [], exercises: '', reflection: '' },
      }),
    });
    const result = readLocalDraft(storage);
    expect(result.status).toBe('ok');
    if (result.status !== 'ok') return;
    expect(result.draft.data.title).toBe('旧教案');
    expect(result.draft.data.lessonTypes).toEqual(['review']);
    expect(result.draft.style).toEqual(DEFAULT_LESSON_STYLE);
    expect(result.draft.modules).toHaveLength(7);
  });

  it('空存储返回 empty（不是错误）', () => {
    expect(readLocalDraft(memoryStorage()).status).toBe('empty');
  });

  it('坏 JSON / 版本不兼容 / 结构损坏都返回 error，且原始字节仍可取回', () => {
    const broken = memoryStorage({ [LOCAL_DRAFT_KEY]: '{not json' });
    expect(readLocalDraft(broken).status).toBe('error');
    expect(readRawLocalDraft(broken)).toBe('{not json');

    const wrongVersion = memoryStorage({
      [LOCAL_DRAFT_KEY]: JSON.stringify({ schemaVersion: 2, revision: 1, updatedAt: '', data: { title: 'x' } }),
    });
    expect(readLocalDraft(wrongVersion).status).toBe('error');
    expect(readRawLocalDraft(wrongVersion)).not.toBeNull();

    const shapeless = memoryStorage({
      [LOCAL_DRAFT_KEY]: JSON.stringify({ schemaVersion: 1, revision: 1, updatedAt: '', data: { random: true } }),
    });
    expect(readLocalDraft(shapeless).status).toBe('error');
  });

  it('旧默认排版一次性迁移到模板口径；用户改过的值保留', () => {
    const legacy = {
      fontId: 'puhuiti',
      baseSize: 14,
      headingSize: 16,
      labelSize: 12,
      lineHeight: 1.7,
      pageMargin: 48,
      moduleGap: 16,
      paragraphGap: 6,
    };
    const migrated = normalizeDraftEnvelope({
      schemaVersion: 1,
      revision: 1,
      updatedAt: '2026-10-01T00:00:00.000Z',
      data: { title: '旧默认' },
      style: legacy,
    });
    expect(migrated.style?.baseSize).toBe(DEFAULT_LESSON_STYLE.baseSize);
    expect(migrated.style?.labelSize).toBe(DEFAULT_LESSON_STYLE.labelSize);
    expect(migrated.style?.lineHeight).toBe(DEFAULT_LESSON_STYLE.lineHeight);
    expect(migrated.style?.pageMargin).toBe(72);
    expect(migrated.style?.moduleGap).toBe(8);
    expect(migrated.style?.paragraphGap).toBe(0);

    // 已写 styleVersion=2 的草稿不再迁移：用户主动选 48/14 时保留。
    const versioned = normalizeDraftEnvelope({
      schemaVersion: 1,
      styleVersion: 2,
      revision: 1,
      updatedAt: '2026-10-01T00:00:00.000Z',
      data: { title: '自定义' },
      style: legacy,
    });
    expect(versioned.style?.baseSize).toBe(14);
    expect(versioned.style?.pageMargin).toBe(48);
  });

  it('normalizeDraftEnvelope 对 style 越界值做夹取（不写坏预览）', () => {
    const envelope = normalizeDraftEnvelope({
      schemaVersion: 1,
      revision: 1,
      updatedAt: '2026-10-12T00:00:00.000Z',
      data: { title: 'x' },
      style: { fontId: 'not-a-font', baseSize: 999, lineHeight: 0 },
    });
    expect(envelope.style?.fontId).toBe(DEFAULT_LESSON_STYLE.fontId);
    expect(envelope.style?.baseSize).toBe(20);
    expect(envelope.style?.lineHeight).toBe(1);
  });

  it('clearLocalDraft 只删草稿键；云端记忆 id 独立读写', () => {
    const storage = memoryStorage();
    writeLocalDraft(storage, draft());
    writeActivePlanId(storage, 'plan-1');
    expect(readActivePlanId(storage)).toBe('plan-1');
    clearLocalDraft(storage);
    expect(readLocalDraft(storage).status).toBe('empty');
    expect(readActivePlanId(storage)).toBe('plan-1');
    clearActivePlanId(storage);
    expect(readActivePlanId(storage)).toBeNull();
    expect(ACTIVE_PLAN_KEY).toBe('zhiqikeyuan:lesson-plan:active:v1');
  });
});
