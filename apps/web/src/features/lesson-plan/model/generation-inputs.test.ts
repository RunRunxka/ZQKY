/** L1-P2 生成前置输入按教案键持久化：重挂载/刷新不静默清空。 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  LOCAL_INPUTS_BUCKET, adoptGenerationInputs, clearGenerationInputs,
  initialGenerationInputs, readGenerationInputs, writeGenerationInputs,
} from './generation-inputs';

const storageKey = 'zhiqikeyuan:lesson-plan:generation-inputs:v1';

beforeEach(() => { localStorage.clear(); clearGenerationInputs(LOCAL_INPUTS_BUCKET); clearGenerationInputs('lesson-a'); clearGenerationInputs('lesson-new'); clearGenerationInputs('lesson-c'); clearGenerationInputs('lesson-d'); });
afterEach(() => { localStorage.clear(); });

describe('generation inputs persistence', () => {
  it('写入后按键读回；未写过的键回落初始值', () => {
    expect(readGenerationInputs('lesson-a')).toEqual(initialGenerationInputs);
    writeGenerationInputs('lesson-a', { ...initialGenerationInputs, modelProfileId: 'm1', requirements: '要求', durationMinutes: 60 });
    expect(readGenerationInputs('lesson-a')).toMatchObject({ modelProfileId: 'm1', requirements: '要求', durationMinutes: 60 });
    expect(readGenerationInputs('lesson-b')).toEqual(initialGenerationInputs);
  });
  it('坏结构/坏 JSON 按缺失处理，不抛错也不覆盖存储', () => {
    localStorage.setItem(storageKey, JSON.stringify({ 'lesson-a': { modelProfileId: 42 } }));
    expect(readGenerationInputs('lesson-a')).toEqual(initialGenerationInputs);
    localStorage.setItem(storageKey, '{broken');
    expect(readGenerationInputs('lesson-a')).toEqual(initialGenerationInputs);
    expect(localStorage.getItem(storageKey)).toBe('{broken');
    clearGenerationInputs('lesson-a');
  });
  it('localStorage 缺失（SSR）时只用内存层', () => {
    const original = localStorage;
    Object.defineProperty(window, 'localStorage', { configurable: true, value: undefined });
    try {
      writeGenerationInputs('lesson-c', { ...initialGenerationInputs, durationMinutes: 90 });
      expect(readGenerationInputs('lesson-c').durationMinutes).toBe(90);
    } finally { Object.defineProperty(window, 'localStorage', { configurable: true, value: original }); }
  });
  it('adopt 把教师自有选择带到新键并清 evidence/classReady；local 桶同样适用', () => {
    writeGenerationInputs(LOCAL_INPUTS_BUCKET, { ...initialGenerationInputs, modelProfileId: 'm1', requirements: '要求', durationMinutes: 60, evidence: { scopeSnapshot: {} as never, evidenceRefs: [], evidence: [] }, classReady: true });
    adoptGenerationInputs(LOCAL_INPUTS_BUCKET, 'lesson-new');
    expect(readGenerationInputs('lesson-new')).toMatchObject({ modelProfileId: 'm1', requirements: '要求', durationMinutes: 60, evidence: null, classReady: false });
    expect(readGenerationInputs(LOCAL_INPUTS_BUCKET).evidence).not.toBeNull();
  });
  it('clear 删除对应桶后回落初始值', () => {
    writeGenerationInputs('lesson-d', { ...initialGenerationInputs, modelProfileId: 'm2' });
    clearGenerationInputs('lesson-d');
    expect(readGenerationInputs('lesson-d')).toEqual(initialGenerationInputs);
  });
  it('write null 淘汰最旧桶，容量上限 12', () => {
    for (let index = 0; index < 15; index += 1) writeGenerationInputs(`lesson-${index}`, { ...initialGenerationInputs, modelProfileId: `m${index}` });
    const store = JSON.parse(localStorage.getItem(storageKey)!);
    expect(Object.keys(store).length).toBeLessThanOrEqual(12);
    expect(store['lesson-14']).toMatchObject({ modelProfileId: 'm14' });
  });
});
