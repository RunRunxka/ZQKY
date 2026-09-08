import { beforeEach, describe, expect, it } from 'vitest';
import {
  CourseValidationError,
  attachCourseResource,
  createCourse,
  courseResourceStates,
  deleteCourse,
  detachCourseResource,
  listResourceCandidates,
  loadDemoCourses,
  parseSyllabusText,
  readCourses,
  setCourseArchived,
  setCourseSyllabus,
  syllabusSummary,
  toggleUnitCovered,
  updateCourse,
} from './courses-store';
import { loadDemoKnowledge } from './knowledge-catalog';
import { loadDemoBooks } from './books-store';

beforeEach(() => {
  window.localStorage.clear();
});

describe('courses-store', () => {
  it('createCourse 校验重名/空名；update/delete/archive 正常', () => {
    const course = createCourse('测试课程', '说明', 'green');
    expect(course.status).toBe('active');
    expect(course.color).toBe('green');
    expect(() => createCourse('测试课程', '')).toThrow(CourseValidationError);
    expect(() => createCourse('  ', '')).toThrow('课程名称不能为空。');

    const updated = updateCourse(course.id, { name: '测试课程（改）', instructions: '课前复习' });
    expect(updated.name).toBe('测试课程（改）');
    expect(updated.instructions).toBe('课前复习');
    expect(() => updateCourse(course.id, { name: '' })).toThrow();

    const archived = setCourseArchived(course.id, true);
    expect(archived?.status).toBe('archived');
    expect(setCourseArchived(course.id, false)?.status).toBe('active');
    expect(deleteCourse(course.id)).toBe(true);
    expect(deleteCourse(course.id)).toBe(false);
  });

  it('大纲：文本解析逐行、covered 学员手判、next 指向首个未完成', () => {
    const course = createCourse('大纲课程', '');
    const units = parseSyllabusText('分数与比例 | 分数大小比较，比例应用\n\n一元一次方程 | 解方程, 应用题');
    expect(units).toHaveLength(2);
    expect(units[0]?.topics).toEqual(['分数大小比较', '比例应用']);
    expect(units[1]?.topics).toEqual(['解方程', '应用题']);

    setCourseSyllabus(course.id, units);
    let summary = syllabusSummary(readCourses()[0]!);
    expect(summary).toMatchObject({ total: 2, covered: 0 });
    expect(summary.next?.title).toBe('分数与比例');

    toggleUnitCovered(course.id, units[0]!.id);
    summary = syllabusSummary(readCourses()[0]!);
    expect(summary.covered).toBe(1);
    expect(summary.next?.title).toBe('一元一次方程');

    // 再勾一次取消
    toggleUnitCovered(course.id, units[0]!.id);
    expect(syllabusSummary(readCourses()[0]!).covered).toBe(0);
  });

  it('资源：候选来自知识库/笔记本/书籍目录；附加去重；目标消失显示不可用', () => {
    loadDemoKnowledge();
    loadDemoBooks();
    const candidates = listResourceCandidates();
    expect(candidates.some((item) => item.kind === 'knowledge_base' && item.label === '课程标准库')).toBe(true);
    expect(candidates.some((item) => item.kind === 'notebook' && item.refId === 'notebook-main')).toBe(true);
    expect(candidates.some((item) => item.kind === 'book' && item.refId === 'demo-book-fractions')).toBe(true);

    const course = createCourse('资源课程', '');
    attachCourseResource(course.id, 'knowledge_base', 'demo-kb-curriculum', '课程标准库');
    expect(() =>
      attachCourseResource(course.id, 'knowledge_base', 'demo-kb-curriculum', '课程标准库'),
    ).toThrow(/已附加/);
    attachCourseResource(course.id, 'book', 'demo-book-fractions', '分数入门（演示书籍）');
    // 幽灵引用（目录中没有）：available=false、href=null
    attachCourseResource(course.id, 'notebook', 'ghost-notebook', '已删除的笔记本');

    let states = courseResourceStates(readCourses()[0]!);
    expect(states.find((state) => state.resource.refId === 'demo-kb-curriculum')).toMatchObject({
      available: true,
      href: '/knowledge-bases/' + encodeURIComponent('课程标准库'),
    });
    expect(states.find((state) => state.resource.refId === 'demo-book-fractions')).toMatchObject({
      available: true,
      href: '/books/demo-book-fractions',
    });
    expect(states.find((state) => state.resource.refId === 'ghost-notebook')).toMatchObject({
      available: false,
      href: null,
    });

    const ghostId = states.find((state) => state.resource.refId === 'ghost-notebook')!.resource.id;
    const afterDetach = detachCourseResource(course.id, ghostId);
    expect(afterDetach?.resources).toHaveLength(2);
    states = courseResourceStates(afterDetach!);
    expect(states.every((state) => state.available)).toBe(true);
  });

  it('演示载入幂等；演示资源在未载入知识库时不可用', () => {
    loadDemoCourses();
    loadDemoCourses();
    const courses = readCourses();
    expect(courses.filter((course) => course.id.startsWith('demo-course-'))).toHaveLength(2);
    const active = courses.find((course) => course.id === 'demo-course-math')!;
    // 未 loadDemoKnowledge：课程标准库引用不可用（对照参考 Unavailable）
    expect(courseResourceStates(active)[0]?.available).toBe(false);
    loadDemoKnowledge();
    expect(courseResourceStates(active)[0]?.available).toBe(true);
    const archived = courses.find((course) => course.id === 'demo-course-archived')!;
    expect(archived.status).toBe('archived');
  });
});
