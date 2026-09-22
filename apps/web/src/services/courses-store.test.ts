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
  readResourceDirectories,
  snapshotError,
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
import {
  __setCollectionLockProviderForTests,
  createInMemoryCollectionLockProvider,
} from './collection-lock';

beforeEach(() => {
  window.localStorage.clear();
  // 仅测试：注入 in-process 互斥 provider（jsdom 无 Web Locks，不注入时写会返回 unsupported）
  expect(__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())).toBe(true);
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

  it('资源：候选来自知识库/笔记本/书籍目录；附加去重；目标消失显示不可用', async () => {
    loadDemoKnowledge();
    await loadDemoBooks();
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

describe('R-11 资源目录故障容错', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  const KB_KEY = 'zqky.replica.knowledge.v1';

  it('知识目录 JSON 损坏：快照标记该目录失败，不抛出、不冒充空目录', () => {
    window.localStorage.setItem(KB_KEY, '{not json');
    const snapshot = readResourceDirectories();
    expect(snapshot.knowledge).toBeNull();
    expect(snapshot.knowledgeError).toBeTruthy();
    // 其他目录仍成功读取，不因知识目录失败而连带失败
    expect(snapshot.notebooks).not.toBeNull();
    expect(snapshot.books).not.toBeNull();
    expect(snapshotError(snapshot)).toBeTruthy();
    // 候选列表不得把失败目录当成空
    expect(() => listResourceCandidates(snapshot)).not.toThrow();
  });

  it('结构非法（合法 JSON 非数组）：同样标记失败而不抛', () => {
    window.localStorage.setItem(KB_KEY, JSON.stringify({ not: 'array' }));
    const snapshot = readResourceDirectories();
    expect(snapshot.knowledge).toBeNull();
    expect(snapshot.knowledgeError).toBeTruthy();
  });

  it('存储读取被拒：标记失败且不抛（保护原数据）', () => {
    const real = Storage.prototype.getItem;
    Storage.prototype.getItem = function (key: string) {
      if (String(key).includes('knowledge')) throw new Error('injected');
      return real.call(this, key);
    };
    try {
      const snapshot = readResourceDirectories();
      expect(snapshot.knowledge).toBeNull();
      expect(snapshot.knowledgeError).toBeTruthy();
    } finally {
      Storage.prototype.getItem = real;
    }
  });

  it('三态区分：目录失败=unknown、目标缺失=missing、命中=available', () => {
    createCourse('容错课程', '');
    const courseId = readCourses().find((c) => c.name === '容错课程')!.id;
    const attached = attachCourseResource(courseId, 'knowledge_base', 'kb-x', '目标知识库');
    const course = attached!;

    // 1) 目录读取失败 → unknown（不断言目标已删除）
    window.localStorage.setItem(KB_KEY, '{broken');
    const failed = courseResourceStates(course, readResourceDirectories())[0]!;
    expect(failed.availability).toBe('unknown');
    expect(failed.available).toBe(false);
    expect(failed.error).toBeTruthy();

    // 2) 目录成功但目标不存在 → missing（保持原"不可用"语义）
    window.localStorage.setItem(KB_KEY, JSON.stringify([]));
    const missing = courseResourceStates(course, readResourceDirectories())[0]!;
    expect(missing.availability).toBe('missing');
    expect(missing.available).toBe(false);

    // 3) 目标命中 → available 且有跳转地址
    window.localStorage.setItem(
      KB_KEY,
      JSON.stringify([{ id: 'kb-x', name: '目标知识库', description: 'd' }]),
    );
    const hit = courseResourceStates(course, readResourceDirectories())[0]!;
    expect(hit.availability).toBe('available');
    expect(hit.available).toBe(true);
    expect(hit.href).toBe('/knowledge-bases/' + encodeURIComponent('目标知识库'));
  });

  it('故障与重试不修改课程存储，也不删除失效引用', () => {
    createCourse('数据保护课程', '');
    const courseId = readCourses().find((c) => c.name === '数据保护课程')!.id;
    attachCourseResource(courseId, 'knowledge_base', 'kb-keep', '保留引用');
    const before = window.localStorage.getItem('zhiqikeyuan:courses')!;

    window.localStorage.setItem(KB_KEY, '{broken');
    const snapshot = readResourceDirectories();
    const course = readCourses().find((c) => c.id === courseId)!;
    courseResourceStates(course, snapshot);

    // 引用仍在、存储逐字节未变
    expect(course.resources.map((r) => r.refId)).toEqual(['kb-keep']);
    expect(window.localStorage.getItem('zhiqikeyuan:courses')).toBe(before);

    // 修复数据后重试恢复可用，无需清空浏览器数据
    window.localStorage.setItem(KB_KEY, JSON.stringify([{ id: 'kb-keep', name: '保留引用', description: 'd' }]));
    const recovered = courseResourceStates(course, readResourceDirectories())[0]!;
    expect(recovered.availability).toBe('available');
    expect(window.localStorage.getItem('zhiqikeyuan:courses')).toBe(before);
  });

  it('知识目录失败不阻断其他目录的候选（笔记本/书籍仍可用）', async () => {
    await loadDemoBooks();
    window.localStorage.setItem(KB_KEY, '{broken');
    const snapshot = readResourceDirectories();
    const candidates = listResourceCandidates(snapshot);
    // 书籍候选仍出现；不含任何知识库候选（失败目录未冒充空）
    expect(candidates.some((c) => c.kind === 'book')).toBe(true);
    expect(candidates.some((c) => c.kind === 'knowledge_base')).toBe(false);
  });
});
