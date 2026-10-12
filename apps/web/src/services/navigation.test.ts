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

describe('导航注册表（推倒重做最小骨架）', () => {
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

  it('登记对话、教案工作台、教材资料库、知识点、题库、练习、学情分析、班级管理、试卷管理与设置十项', () => {
    expect(navigation.map((item) => item.id)).toEqual([
      'chat',
      'lesson-plans',
      'textbooks',
      'knowledge-points',
      'question-bank',
      'practices',
      'learning-analysis',
      'assessments-roster',
      'assessments-papers',
      'settings',
    ]);
    expect(navigation.find((item) => item.id === 'chat')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'lesson-plans')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'textbooks')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'knowledge-points')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'question-bank')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'practices')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'learning-analysis')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'assessments-roster')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'assessments-papers')?.status).toBe('ready');
    expect(navigation.find((item) => item.id === 'settings')?.status).toBe('ready');
  });

  it('主功能分组为工作台、教学资源与学情与施测，底部只保留设置', () => {
    const groups = groupMainNavigation();
    expect(groups.map((group) => group.label)).toEqual(['工作台', '教学资源', '学情与施测']);
    for (const group of groups) {
      expect(group.items.length).toBeGreaterThan(0);
    }
    expect(navigation.filter((item) => item.position === 'bottom').map((item) => item.id)).toEqual([
      'settings',
    ]);
  });
});

describe('唯一主页与当前菜单解析', () => {
  it('有且仅有一个主页条目，且为 /chat', () => {
    const homes = navigation.filter((item) => item.home);
    expect(homes).toHaveLength(1);
    expect(HOME_PATH).toBe('/chat');
    expect(HOME_LABEL).toBe('对话');
  });

  it('每个已实现路由最多解析出一个当前项', () => {
    const cases: [string, string | null][] = [
      ['/chat', 'chat'],
      ['/lesson-plans', 'lesson-plans'],
      ['/textbooks', 'textbooks'],
      ['/textbooks/libraries/lib-1', 'textbooks'],
      ['/knowledge-points', 'knowledge-points'],
      ['/question-bank', 'question-bank'],
      ['/question-bank/imports/imp-1', 'question-bank'],
      ['/practices', 'practices'],
      ['/learning-analysis', 'learning-analysis'],
      ['/assessments/roster', 'assessments-roster'],
      ['/assessments/papers', 'assessments-papers'],
      ['/settings', 'settings'],
      ['/definitely-missing', null],
    ];
    for (const [pathname, expected] of cases) {
      expect(resolveCurrentNavigationId(pathname, { includeHidden: false }), pathname).toBe(expected);
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
});
