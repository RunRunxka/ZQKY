import { describe, expect, it } from 'vitest';
import { groupMainNavigation, navigation } from './navigation';

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

  it('教案工作台本地可用，学习问答、沉浸阅读、学习空间、笔记本、资料库、书籍、课程与设置页已实现，其余均为规划中', () => {
    const implemented = navigation.filter((item) => item.status !== 'planned');
    expect(implemented.map((item) => item.id)).toEqual([
      'chat',
      'lesson-plan',
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
    // 课程按参考行为隐藏主导航入口（路由可达）
    const courses = implemented.find((item) => item.id === 'courses');
    expect(courses?.hidden).toBe(true);
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
        '/co-writer',
        '/agents',
      ]),
    );
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
