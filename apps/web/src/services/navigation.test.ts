import { describe, expect, it } from 'vitest';
import { BookMarked } from 'lucide-react';
import type { NavigationItem } from '@/contracts/navigation';
import {
  HOME_LABEL,
  HOME_PATH,
  groupMainNavigation,
  navigation,
  resolveCurrentNavigationId,
} from './navigation';

describe('导航注册表', () => {
  it('每项都有唯一 id、唯一路径、合法路径与图标', () => {
    const ids = new Set<string>();
    const paths = new Set<string>();
    for (const item of navigation) {
      expect(ids.has(item.id), `重复 id：${item.id}`).toBe(false);
      expect(paths.has(item.path), `重复路径：${item.path}`).toBe(false);
      expect(item.path.startsWith('/'), `路径必须以 / 开头：${item.path}`).toBe(true);
      expect(item.icon, `缺少图标：${item.id}`).toBeTruthy();
      ids.add(item.id);
      paths.add(item.path);
    }
  });

  it('教案工作台本地可用，学习问答、沉浸阅读、学习空间、笔记本、资料库、书籍、课程、协同写作、whisper 与设置页已实现，其余均为规划中', () => {
    const implemented = navigation.filter((item) => item.status !== 'planned');
    expect(implemented.map((item) => item.id)).toEqual([
      'chat',
      'lesson-plan',
      'co-writer',
      'whisper',
      'reading',
      'space',
      'notebooks',
      'knowledge',
      'books',
      'courses',
      'settings',
    ]);
    expect(implemented[0]?.status).toBe('ready');
    expect(implemented[1]?.status).toBe('local');
    for (const item of implemented.slice(2)) {
      expect(item.status).toBe('ready');
    }
    // 课程与 whisper 按参考行为隐藏主导航入口（路由可达）
    const courses = implemented.find((item) => item.id === 'courses');
    expect(courses?.hidden).toBe(true);
    const whisper = implemented.find((item) => item.id === 'whisper');
    expect(whisper?.hidden).toBe(true);
  });

  it('每个规划模块都登记了用途简介与能力清单', () => {
    for (const item of navigation) {
      if (item.status !== 'planned') continue;
      expect(item.plan.summary.trim(), `${item.label} 缺少用途简介`).not.toBe('');
      expect(item.plan.capabilities.length, `${item.label} 缺少能力清单`).toBeGreaterThan(0);
      for (const capability of item.plan.capabilities) {
        expect(capability.trim()).not.toBe('');
      }
    }
  });

  it('D01 预留入口全部登记且为规划状态（/space、/notebooks、/knowledge-bases、/reading 已在 S5 实现）', () => {
    const plannedPaths = navigation.filter((item) => item.status === 'planned').map((n) => n.path);
    expect(plannedPaths).toEqual(
      expect.arrayContaining([
        '/papers',
        '/question-bank',
        '/templates',
        '/agents',
      ]),
    );
    expect(plannedPaths).not.toContain('/co-writer');
    expect(plannedPaths).not.toContain('/space');
    expect(plannedPaths).not.toContain('/notebooks');
    expect(plannedPaths).not.toContain('/knowledge-bases');
    expect(plannedPaths).not.toContain('/reading');
    expect(plannedPaths).not.toContain('/settings');
    expect(plannedPaths).not.toContain('/chat');
    // 笔记本不进侧栏（仅从学习空间进入），但保留路由
    const notebooks = navigation.find((item) => item.id === 'notebooks');
    expect(notebooks?.hidden).toBe(true);
    expect(notebooks?.status).toBe('ready');
    expect(navigation.some((item) => item.id === 'mcp' || item.id === 'skills')).toBe(false);
  });

  it('主功能分组连续且标题非空，底部只保留设置', () => {
    const groups = groupMainNavigation();
    expect(groups.map((group) => group.label)).toEqual(['教学工作台', '教学资源', '扩展能力']);
    for (const group of groups) {
      expect(group.items.length).toBeGreaterThan(0);
    }
    expect(navigation.filter((item) => item.position === 'bottom').map((item) => item.id)).toEqual([
      'settings',
    ]);
  });
});

describe('唯一主页与当前菜单解析（R-02/R-04）', () => {
  it('有且仅有一个主页条目，且为 /chat', () => {
    const homes = navigation.filter((item) => item.home);
    expect(homes).toHaveLength(1);
    expect(HOME_PATH).toBe('/chat');
    expect(HOME_LABEL).toBe('学习问答');
  });

  it('每个已实现路由最多解析出一个当前项，隐藏直达页上溯到可见父菜单', () => {
    const desktopCases: [string, string | null][] = [
      ['/chat', 'chat'],
      ['/lesson-plans', 'lesson-plan'],
      ['/reading/materials', 'reading'],
      ['/space/questions', 'space'],
      // T4：书籍并入教材资料库（自身隐藏），页面级路径同样落到教材资料库
      ['/books', 'knowledge'],
      ['/books/x/pages/y', 'knowledge'],
      ['/knowledge-bases/课程标准库', 'knowledge'],
      ['/settings', 'settings'],
      // 隐藏直达页在桌面侧栏标记可见父菜单
      ['/whisper', 'co-writer'],
      ['/notebooks/x', 'space'],
      // 课程与书籍同级，父菜单同为教材资料库
      ['/courses', 'knowledge'],
      ['/courses/x', 'knowledge'],
      // 404 没有对应条目
      ['/definitely-missing', null],
    ];
    for (const [pathname, expected] of desktopCases) {
      expect(resolveCurrentNavigationId(pathname, { includeHidden: false }), pathname).toBe(expected);
    }
  });

  it('桌面解析结果只能是可见项（隐藏项一律上溯或返回 null）', () => {
    const visibleIds = new Set(navigation.filter((item) => !item.hidden).map((item) => item.id));
    const pathnames = [
      ...navigation.map((item) => item.path),
      '/knowledge-bases/课程标准库',
      '/books/demo-book',
      '/books/demo-book/pages/demo-page',
      '/courses/demo-course',
      '/co-writer/room',
      '/definitely-missing',
    ];
    for (const pathname of pathnames) {
      const resolved = resolveCurrentNavigationId(pathname, { includeHidden: false });
      if (resolved === null) continue;
      expect(visibleIds.has(resolved), `${pathname} 落到不可见项 ${resolved}`).toBe(true);
    }
  });

  it('父菜单成环时返回 null 而不是无限上溯', () => {
    const cycleA = {
      id: 'test-cycle-a',
      label: '环形入口 A',
      path: '/test-cycle/a',
      status: 'ready',
      position: 'main',
      hidden: true,
      parentPath: '/test-cycle/b',
      icon: BookMarked,
    } satisfies NavigationItem;
    const cycleB = {
      ...cycleA,
      id: 'test-cycle-b',
      label: '环形入口 B',
      path: '/test-cycle/b',
      parentPath: '/test-cycle/a',
    } satisfies NavigationItem;
    navigation.push(cycleA, cycleB);
    try {
      expect(resolveCurrentNavigationId('/test-cycle/a', { includeHidden: false })).toBeNull();
      expect(resolveCurrentNavigationId('/test-cycle/b', { includeHidden: false })).toBeNull();
      // 抽屉（includeHidden=true）语义不变：标记隐藏项自身
      expect(resolveCurrentNavigationId('/test-cycle/a', { includeHidden: true })).toBe(
        'test-cycle-a',
      );
    } finally {
      for (const id of ['test-cycle-a', 'test-cycle-b']) {
        const index = navigation.findIndex((item) => item.id === id);
        if (index >= 0) navigation.splice(index, 1);
      }
    }
  });

  it('手机抽屉对隐藏直达页标记自身', () => {
    expect(resolveCurrentNavigationId('/whisper', { includeHidden: true })).toBe('whisper');
    expect(resolveCurrentNavigationId('/notebooks/x', { includeHidden: true })).toBe('notebooks');
    expect(resolveCurrentNavigationId('/courses/x', { includeHidden: true })).toBe('courses');
    // 非隐藏页两种模式一致
    expect(resolveCurrentNavigationId('/knowledge-bases', { includeHidden: true })).toBe('knowledge');
    expect(resolveCurrentNavigationId('/knowledge-bases', { includeHidden: false })).toBe(
      'knowledge',
    );
    // 书籍在抽屉里标记自身（桌面侧栏因隐藏而上溯到教材资料库）
    expect(resolveCurrentNavigationId('/books', { includeHidden: true })).toBe('books');
    expect(resolveCurrentNavigationId('/books', { includeHidden: false })).toBe('knowledge');
    expect(resolveCurrentNavigationId('/books/x/pages/y', { includeHidden: true })).toBe('books');
  });

  it('每个隐藏直达页都登记了可见父菜单且父菜单存在', () => {
    for (const item of navigation) {
      if (!item.hidden) continue;
      expect(item.parentPath, `${item.id} 缺少 parentPath`).toBeTruthy();
      expect(navigation.some((candidate) => candidate.path === item.parentPath && !candidate.hidden)).toBe(true);
    }
  });

  it('书籍与课程并入教材资料库：同为隐藏项、父菜单一致、抽屉图标可区分', () => {
    const books = navigation.find((item) => item.id === 'books');
    const courses = navigation.find((item) => item.id === 'courses');
    const knowledge = navigation.find((item) => item.id === 'knowledge');
    expect(books?.label).toBe('书籍');
    expect(books?.path).toBe('/books');
    expect(books?.hidden).toBe(true);
    expect(books?.parentPath).toBe('/knowledge-bases');
    expect(courses?.hidden).toBe(true);
    expect(courses?.parentPath).toBe('/knowledge-bases');
    // 手机抽屉用 sidebarIcon ?? icon：书籍不得再登记教材资料库的 Library，否则两枚图标同形
    expect(books?.sidebarIcon).toBeUndefined();
    expect(books?.icon).not.toBe(knowledge?.icon);
    // 桌面侧栏（过滤 hidden）的教学资源分组只保留教材资料库为可见内容入口
    const visibleResources = navigation
      .filter((item) => !item.hidden && item.group === '教学资源')
      .map((item) => item.id);
    expect(visibleResources).toContain('knowledge');
    expect(visibleResources).not.toContain('books');
    expect(visibleResources).not.toContain('courses');
  });
});
