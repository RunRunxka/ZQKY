/**
 * F10-QB：正式知识点关联的读取 / 整表替换载荷 / 学科冲突 / 字段级错误定位。
 *
 * 断言方向（与后端 B2-RV07 语义一致）：
 * - 字段缺失 ≠ 空数组：缺失时不得声称「无关联」；
 * - 形状不认识的条目丢弃并计数，不猜造引用；
 * - 学科变化且旧关联学科不一致 → 必须显式替换/清空（blocked），界面文案说明会被 422 拒绝；
 * - 422 的 `knowledgeLinks[i]` 与消息里的知识点 id 都能定位到具体行。
 */

import { describe, expect, it } from 'vitest';
import { ApiError } from '@/services/api-client';
import {
  KNOWLEDGE_LINKS_MISSING_NOTICE,
  linkSourceLabel,
  linksToInputs,
  locateLinkIssues,
  readKnowledgeLinks,
  roleLabel,
  sameLinkInputs,
  subjectChangeNotice,
  subjectChangeState,
  type KnowledgeLinkView,
} from './knowledge-links';

function link(overrides: Partial<KnowledgeLinkView> = {}): KnowledgeLinkView {
  return {
    knowledgePointId: 'kp-1',
    knowledgeRevisionId: 'kpr-1',
    knowledgeNameSnapshot: '有理数',
    subjectIdSnapshot: 'math',
    role: 'primary',
    ...overrides,
  };
}

describe('readKnowledgeLinks：字段缺失与损坏条目不猜造', () => {
  it('字段不存在 / 为 null / 不是数组 → missing（不是「无关联」）', () => {
    expect(readKnowledgeLinks({})).toEqual({ status: 'missing' });
    expect(readKnowledgeLinks({ knowledgeLinks: null })).toEqual({ status: 'missing' });
    expect(readKnowledgeLinks({ knowledgeLinks: 'x' })).toEqual({ status: 'missing' });
    expect(readKnowledgeLinks(null)).toEqual({ status: 'missing' });
    expect(KNOWLEDGE_LINKS_MISSING_NOTICE).toContain('不会');
  });

  it('空数组 → provided 且 0 条（明确无关联）', () => {
    expect(readKnowledgeLinks({ knowledgeLinks: [] })).toEqual({
      status: 'provided',
      links: [],
      skipped: 0,
    });
  });

  it('形状不认识的条目丢弃并计数；草稿来源只保留 human/ai', () => {
    const raw: unknown[] = [
      link({ source: 'ai' }),
      link({ knowledgePointId: '', knowledgeRevisionId: 'x' }),
      { ...link(), role: 'tertiary' },
      { knowledgePointId: 'kp-2' },
      { ...link(), source: 'assistant' },
    ];
    const read = readKnowledgeLinks({ knowledgeLinks: raw });
    expect(read.status).toBe('provided');
    if (read.status !== 'provided') return;
    expect(read.links.map((item) => item.knowledgePointId)).toEqual(['kp-1', 'kp-1']);
    expect(read.skipped).toBe(3);
    expect(read.links[0]?.source).toBe('ai');
    // 来源字段不认识 → 不写（不猜造），但条目本身可读
    expect(read.links[1]?.source).toBeUndefined();
  });
});

describe('整表替换载荷与比较', () => {
  it('只发送知识点与角色；顺序无关地比较等价性', () => {
    const inputs = linksToInputs([
      link({ knowledgePointId: 'kp-2', role: 'secondary' }),
      link({ knowledgePointId: 'kp-1' }),
    ]);
    expect(inputs).toEqual([
      { knowledgePointId: 'kp-2', role: 'secondary' },
      { knowledgePointId: 'kp-1', role: 'primary' },
    ]);
    expect(sameLinkInputs(inputs, [...inputs].reverse())).toBe(true);
    expect(sameLinkInputs(inputs, [{ knowledgePointId: 'kp-1', role: 'primary' }])).toBe(false);
    expect(sameLinkInputs([], [])).toBe(true);
  });

  it('角色与来源文案唯一一份', () => {
    expect(roleLabel('primary')).toBe('主知识点');
    expect(roleLabel('secondary')).toBe('次要知识点');
    expect(linkSourceLabel('ai')).toBe('AI 补题关联');
    expect(linkSourceLabel('human')).toBe('人工关联');
    expect(linkSourceLabel(undefined)).toBe('来源未标注');
  });
});

describe('学科变化：冲突行与显式处置要求', () => {
  it('学科未变 → 不 blocked，也不编造冲突', () => {
    const state = subjectChangeState('math', 'math', [link()]);
    expect(state.changed).toBe(false);
    expect(state.blocked).toBe(false);
    expect(subjectChangeNotice(state, false)).toBeNull();
  });

  it('学科变化且旧关联学科不一致 → blocked；未改动关联时明说会被 422 拒绝', () => {
    const state = subjectChangeState('math', 'physics', [link(), link({ subjectIdSnapshot: 'physics' })]);
    expect(state.changed).toBe(true);
    expect(state.conflictIndexes).toEqual([0]);
    expect(state.blocked).toBe(true);
    const notice = subjectChangeNotice(state, false);
    expect(notice).toContain('422');
    expect(notice).toContain('显式替换为新学科知识点，或显式清空');
    expect(subjectChangeNotice(state, true)).toContain('整表替换');
  });

  it('学科清空（新学科为空）→ 服务端不做学科比对，不算冲突', () => {
    const state = subjectChangeState('math', '', [link()]);
    expect(state.changed).toBe(true);
    expect(state.blocked).toBe(false);
  });

  it('学科变化且未改动、无冲突 → 说明服务端会继承；已改动 → 说明整表替换', () => {
    const state = subjectChangeState('math', 'physics', [link({ subjectIdSnapshot: 'physics' })]);
    expect(state.changed).toBe(true);
    expect(state.blocked).toBe(false);
    expect(subjectChangeNotice(state, true)).toContain('整表替换');
    expect(subjectChangeNotice(state, false)).toContain('服务端会继承');
  });
});

describe('写入错误的字段级定位', () => {
  it('details.issues[].field=knowledgeLinks[i] 定位到行，其余为整体错误', () => {
    const error = new ApiError(
      'KNOWLEDGE_REFERENCE_INVALID',
      '改题目学科后不能继承与新学科不一致的旧知识点关联。',
      422,
      false,
      undefined,
      {
        issues: [
          {
            field: 'knowledgeLinks[1].knowledgePointId',
            code: 'KNOWLEDGE_REFERENCE_INVALID',
            message: '知识点 kp-2（力）属于学科 physics，与新学科 math 不一致；请显式替换或清空该关联。',
          },
          { code: 'OTHER', message: '整体校验失败。' },
        ],
      },
    );
    const located = locateLinkIssues(error, [link(), link({ knowledgePointId: 'kp-2' })]);
    expect(located.byIndex.get(1)).toContain('kp-2');
    expect(located.byIndex.has(0)).toBe(false);
    expect(located.general).toEqual(['整体校验失败。']);
  });

  it('没有 details 时按消息里的知识点 id 逐字定位（404/422 归档/学科不符）', () => {
    const error = new ApiError(
      'KNOWLEDGE_SUBJECT_MISMATCH',
      '知识点 kp-9 属于学科 physics，与题目学科（math）不一致。',
      422,
      false,
    );
    const located = locateLinkIssues(error, [link(), link({ knowledgePointId: 'kp-9' })]);
    expect(located.byIndex.get(1)).toContain('kp-9');
    expect(located.general).toEqual([]);
  });

  it('完全无法定位时作为整体错误原样显示（不静默失败）', () => {
    const error = new ApiError('REVISION_CONFLICT', '题目已被其他操作更新。', 409, false);
    const located = locateLinkIssues(error, [link()]);
    expect(located.byIndex.size).toBe(0);
    expect(located.general).toEqual(['题目已被其他操作更新。']);
  });
});
