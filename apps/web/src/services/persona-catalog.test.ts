import { beforeEach, describe, expect, it } from 'vitest';
import {
  createPersona,
  deletePersona,
  DEMO_PERSONAS,
  loadDemoPersonas,
  PersonaValidationError,
  readPersonas,
  updatePersona,
} from './persona-catalog';

/**
 * S5-A /space/personas 业务页与 S2 输入区共用的本地角色目录：
 * 显式演示载入（幂等）、新建/更新/删除、重名校验。
 */

describe('S5-A persona-catalog 业务操作', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('演示角色显式载入且幂等，旧数据格式兼容', () => {
    loadDemoPersonas();
    loadDemoPersonas();
    const list = readPersonas();
    expect(list).toHaveLength(DEMO_PERSONAS.length);
    expect(list.every((p) => p.source === 'demo' && typeof p.content === 'string')).toBe(true);
  });

  it('新建角色：校验空名/重名，写入 user 来源', () => {
    expect(() => createPersona({ name: '  ', description: '' })).toThrow(
      PersonaValidationError,
    );
    const created = createPersona({ name: '板书型老师', description: '逐步板书', content: '# x' });
    expect(created.source).toBe('user');
    expect(readPersonas()).toHaveLength(1);
    expect(() => createPersona({ name: '板书型老师', description: '' })).toThrow(
      PersonaValidationError,
    );
  });

  it('更新角色：改名查重、清空正文落到 undefined', () => {
    const a = createPersona({ name: '甲', description: 'a' });
    const b = createPersona({ name: '乙', description: 'b' });
    expect(() => updatePersona(a.id, { name: '乙' })).toThrow(PersonaValidationError);
    const renamed = updatePersona(a.id, { name: '甲二', content: '' });
    expect(renamed.name).toBe('甲二');
    expect(renamed.content).toBeUndefined();
    expect(updatePersona(b.id, { description: '新简介' }).description).toBe('新简介');
  });

  it('删除角色：按 id 生效，不存在返回 false', () => {
    const a = createPersona({ name: '丙', description: '' });
    expect(deletePersona(a.id)).toBe(true);
    expect(readPersonas()).toHaveLength(0);
    expect(deletePersona(a.id)).toBe(false);
  });
});
