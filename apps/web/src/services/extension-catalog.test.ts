// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  BUILTIN_SKILLS,
  buildTurnExtensionSnapshot,
  readExtensions,
  removeExtension,
  saveExtension,
  seedBuiltinSkills,
  skillTakesEffect,
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

describe('技能生效快照（Skill 注入通道）', () => {
  it('只把已启用且正文非空的技能冻结进快照', () => {
    saveExtension({ ...entry, id: 'on', enabled: true });
    saveExtension({ ...entry, id: 'off', name: '未启用', enabled: false });
    saveExtension({ ...entry, id: 'empty', name: '空正文', content: '   ', enabled: true });
    saveExtension({ id: 'tool', kind: 'mcp', name: '本地目录', description: '', content: '', enabled: true });
    expect(buildTurnExtensionSnapshot()).toEqual({
      mcps: [],
      skills: [{ id: 'on', name: '课堂提问', description: '模拟', content: '提出问题' }],
    });
  });

  it('没有任何有效技能时不携带 extensions（保持旧请求形态）', () => {
    saveExtension({ ...entry, enabled: false });
    expect(buildTurnExtensionSnapshot()).toBeUndefined();
  });

  it('skillTakesEffect 只认技能且要求正文非空', () => {
    expect(skillTakesEffect({ ...entry, enabled: true })).toBe(true);
    expect(skillTakesEffect({ ...entry, content: '  ' })).toBe(false);
    expect(skillTakesEffect({ ...entry, kind: 'mcp' })).toBe(false);
  });
});

describe('内置教学技能载入', () => {
  it('幂等：重复载入不重复新增，且不改动用户已修改的同名条目', () => {
    const first = seedBuiltinSkills();
    expect(first.added).toBe(BUILTIN_SKILLS.length);
    expect(first.skipped).toBe(0);
    const seeded = readExtensions()[0]!;
    saveExtension({ ...seeded, enabled: false, description: '我的改动', content: '我的正文' });
    const second = seedBuiltinSkills();
    expect(second).toEqual({ added: 0, skipped: BUILTIN_SKILLS.length });
    const kept = readExtensions().find((item) => item.id === seeded.id)!;
    expect(kept.enabled).toBe(false);
    expect(kept.description).toBe('我的改动');
    expect(kept.content).toBe('我的正文');
  });

  it('载入的技能默认启用，正文非空并会进入快照', () => {
    seedBuiltinSkills();
    const seeded = readExtensions().filter((item) => item.kind === 'skill');
    expect(seeded).toHaveLength(BUILTIN_SKILLS.length);
    expect(seeded.every((item) => item.enabled && skillTakesEffect(item))).toBe(true);
    expect(buildTurnExtensionSnapshot()?.skills).toHaveLength(BUILTIN_SKILLS.length);
  });

  it('损坏存储时载入失败且不覆盖原数据', () => {
    window.localStorage.setItem('zqky.replica.extensions.v1', 'broken');
    expect(() => seedBuiltinSkills()).toThrow();
    expect(window.localStorage.getItem('zqky.replica.extensions.v1')).toBe('broken');
  });
});
