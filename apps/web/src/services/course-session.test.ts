import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  COURSE_CONVENTIONS_LIMIT,
  buildCourseSnapshot,
  buildNewConversation,
  courseAvailabilityLabel,
  courseContextMessage,
  listCourseSessions,
  resolveCourse,
  resolveCourseSnapshot,
} from './course-session';
import { loadDemoCourses, type StudyCourse } from './courses-store';
import type { ConversationMeta } from '@/contracts/chat';

/**
 * H1-COURSE-SESSIONS v1：课程 ↔ 会话归属与轮次课程快照的契约单测（纯函数 + 一次目录读取）。
 *
 * 覆盖：归属只认稳定 courseId、不猜测；列表过滤与排序；快照冻结/截断/资源三态照抄；
 * system 消息文本如实（资源仅登记、未解析未检索）；课程"不存在"与"目录读取失败"分开。
 */

function meta(id: string, courseId: string | undefined, updatedAt: string, title = id): ConversationMeta {
  return { id, title, messageCount: 1, createdAt: updatedAt, updatedAt, ...(courseId ? { courseId } : {}) };
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('课程会话归属与列表', () => {
  it('只按稳定 courseId 过滤并按下更新时间倒序；未归属/其他课程不混入', () => {
    const metas = [
      meta('a', 'course-1', '2026-09-20T10:00:00.000Z'),
      meta('b', 'course-2', '2026-09-21T10:00:00.000Z'),
      meta('c', 'course-1', '2026-09-22T10:00:00.000Z'),
      meta('legacy', undefined, '2026-09-23T10:00:00.000Z'), // 旧会话缺 courseId：保持未归属
    ];
    expect(listCourseSessions(metas, 'course-1').map((item) => item.id)).toEqual(['c', 'a']);
    expect(listCourseSessions(metas, 'course-2').map((item) => item.id)).toEqual(['b']);
    expect(listCourseSessions(metas, 'course-3')).toEqual([]);
    // 未归属会话不出现在任何课程列表里（也不被改写归属）
    expect(metas.find((item) => item.id === 'legacy')!.courseId).toBeUndefined();
  });

  it('resolveCourse 把"课程不存在"与"目录读取失败"分开（R-11 同口径）', () => {
    loadDemoCourses();
    expect(resolveCourse('demo-course-math').state).toBe('ok');
    expect(resolveCourse('no-such-course').state).toBe('missing');
    expect(resolveCourse('').state).toBe('missing');

    const original = Storage.prototype.getItem;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      if (name === 'zhiqikeyuan:courses') throw new Error('denied');
      return original.call(this, name);
    });
    const failed = resolveCourse('demo-course-math');
    spy.mockRestore();

    expect(failed.state).toBe('unavailable');
    expect(courseAvailabilityLabel(failed)).toContain('读取失败');
    expect(courseAvailabilityLabel({ state: 'missing' })).toContain('已删除');
  });
});

describe('轮次课程快照', () => {
  const course: StudyCourse = {
    id: 'cs-1',
    name: '七年级数学',
    description: '分数与方程',
    color: 'blue',
    instructions: `先复习上一单元错题。${'补'.repeat(COURSE_CONVENTIONS_LIMIT + 50)}`,
    syllabus: [
      { id: 'u1', position: 0, title: '分数与比例', topics: [], covered: true },
      { id: 'u2', position: 1, title: '一元一次方程', topics: [], covered: false },
    ],
    resources: [
      { id: 'r1', kind: 'knowledge_base', refId: 'missing-kb', label: '课程标准库', position: 0, addedAt: '2026-09-01T00:00:00.000Z' },
    ],
    status: 'active',
    createdAt: '2026-09-01T00:00:00.000Z',
    updatedAt: '2026-09-01T00:00:00.000Z',
  };

  it('快照冻结课程名/约定（按上限截断）/大纲摘要/资源登记三态', () => {
    const snapshot = buildCourseSnapshot(course, '2026-09-22T12:00:00.000Z');
    expect(snapshot.courseId).toBe('cs-1');
    expect(snapshot.name).toBe('七年级数学');
    expect(snapshot.conventions.length).toBeLessThanOrEqual(COURSE_CONVENTIONS_LIMIT + 1);
    expect(snapshot.conventions.startsWith('先复习上一单元错题。')).toBe(true);
    expect(snapshot.syllabus).toEqual({ total: 2, covered: 1, nextTitle: '一元一次方程' });
    // 资源只承载登记形态与可用性（目录为空 → 目标缺失 = missing），不含内容
    expect(snapshot.resources).toEqual([
      { kind: 'knowledge_base', label: '课程标准库', availability: 'missing' },
    ]);
    expect(snapshot.frozenAt).toBe('2026-09-22T12:00:00.000Z');
  });

  it('system 消息文本如实：含课程名/约定/大纲/资源登记，且不声称已解析、已检索或 RAG 已接入', () => {
    const text = courseContextMessage(buildCourseSnapshot(course, '2026-09-22T12:00:00.000Z'));
    expect(text).toContain('课程名称：七年级数学');
    expect(text).toContain('课程约定');
    expect(text).toContain('先复习上一单元错题。');
    expect(text).toContain('大纲进度：共 2 个单元，已完成 1 个');
    expect(text).toContain('下一个未完成单元：一元一次方程');
    expect(text).toContain('课程标准库（knowledge_base·missing）');
    // 如实边界：资源只是登记引用
    expect(text).toMatch(/未解析|未检索/);
    expect(text).not.toMatch(/已检索到|已解析教材|RAG 已接入|已向量检索/);
  });

  it('resolveCourseSnapshot：未归属不发上下文；课程不存在与目录失败区分', () => {
    loadDemoCourses();
    expect(resolveCourseSnapshot(undefined).state).toBe('none');
    expect(resolveCourseSnapshot('no-such-course').state).toBe('missing');

    const ok = resolveCourseSnapshot('demo-course-math');
    expect(ok.state).toBe('ok');
    if (ok.state === 'ok') expect(ok.snapshot.name).toContain('七年级数学');

    const original = Storage.prototype.getItem;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      if (name === 'zhiqikeyuan:courses') throw new Error('denied');
      return original.call(this, name);
    });
    const failed = resolveCourseSnapshot('demo-course-math');
    spy.mockRestore();
    expect(failed.state).toBe('unavailable');
  });
});

describe('新建会话形状（课程页与聊天页共用）', () => {
  it('传入 courseId 才写归属；不传即普通未归属会话', () => {
    const withCourse = buildNewConversation({ id: 'c1', courseId: 'cs-1', now: '2026-09-22T12:00:00.000Z' });
    expect(withCourse.courseId).toBe('cs-1');
    expect(withCourse.schemaVersion).toBe(1);
    expect(withCourse.mode).toBe('real');
    expect(withCourse.messages).toEqual([]);

    const plain = buildNewConversation({ id: 'c2' });
    expect('courseId' in plain).toBe(false);
  });
});
