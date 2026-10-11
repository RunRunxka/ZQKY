import {
  BookMarked,
  BookOpen,
  ClipboardList,
  FilePenLine,
  FileQuestion,
  GraduationCap,
  Library,
  MessageSquare,
  Settings2,
  House,
  Settings,
} from 'lucide-react';
import type { NavigationItem } from '@/contracts/navigation';

/**
 * 全站模块登记的唯一运行时来源：图标、分组、模块状态都登记在此，
 * WorkspaceShell 从这里读取，不各自维护副本。（规划页已随 Agent 化改造移除。）
 */
export const navigation: NavigationItem[] = [
  {
    id: 'chat',
    label: '学习问答',
    path: '/chat',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    // 全站唯一主页：品牌按钮、404/错误页返回入口与默认标题都从这一条派生
    home: true,
    icon: MessageSquare,
    sidebarIcon: House,
  },
  {
    id: 'lesson-plan',
    label: '教案工作台',
    path: '/lesson-plans',
    status: 'local',
    position: 'main',
    group: '教学工作台',
    icon: FilePenLine,
  },
  {
    // 题库紧跟教案工作台（RAG-REBUILD v1.0）：独立题库已是真实存储，不再是规划状态。
    id: 'question-bank',
    label: '题库',
    path: '/question-bank',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: FileQuestion,
  },
  {
    // 独立知识点库（TEACHING-LOOP B1 后端 + B2 前端）：与「教材资料库」是两套数据。
    id: 'knowledge-points',
    label: '知识点',
    path: '/knowledge-points',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: BookOpen,
  },
  {
    // C4-3：班级管理/试卷管理拆为独立页面（与五步工作区并存；深链兼容）
    id: 'assessments-roster',
    label: '班级管理',
    path: '/assessments/roster',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: ClipboardList,
  },
  {
    id: 'assessments-papers',
    label: '试卷管理',
    path: '/assessments/papers',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: FileQuestion,
  },
  {
    // 施测与成绩（TEACHING-LOOP B3 / T60 + F20-I）：五步工作区，成绩导入为真实后端。
    id: 'assessments',
    label: '施测与成绩',
    path: '/assessments',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: ClipboardList,
  },
  {
    id: 'learning-analysis', label: '学情分析', path: '/learning-analysis',
    status: 'ready', position: 'main', group: '教学工作台', icon: GraduationCap,
  },
  {
    id: 'practices', label: '针对练习', path: '/practices',
    status: 'ready', position: 'main', group: '教学工作台', icon: ClipboardList,
  },
  {
    id: 'knowledge',
    label: '教材资料库',
    path: '/knowledge-bases',
    status: 'ready',
    position: 'main',
    group: '教学资源',
    icon: Library,
  },
  {
    // 书籍并入教材资料库（T4）：桌面侧栏不再有独立顶级项，页内入口见 KnowledgeBasesSection。
    // 不登记 sidebarIcon：手机抽屉用 icon 的 BookMarked，与教材资料库的 Library 区分。
    id: 'books',
    label: '书籍',
    path: '/books',
    status: 'ready',
    position: 'main',
    hidden: true,
    parentPath: '/knowledge-bases',
    group: '教学资源',
    icon: BookMarked,
  },
  {
    // 参考中 /courses 主导航被临时隐藏（路由与数据完好）；目标遵循同样行为
    id: 'courses',
    label: '课程',
    path: '/courses',
    status: 'ready',
    position: 'main',
    hidden: true,
    // 与书籍同属“书籍/课程”内容阅读；桌面侧栏标记教材资料库为父菜单（与书籍同级上溯）
    parentPath: '/knowledge-bases',
    group: '教学资源',
    icon: GraduationCap,
  },
  {
    id: 'settings',
    label: '设置',
    path: '/settings',
    status: 'ready',
    position: 'bottom',
    icon: Settings2,
    sidebarIcon: Settings,
  },
];

export interface NavigationGroup {
  label: string;
  items: NavigationItem[];
}

/** 全站唯一主页与标签：从登记表派生，任何地方都不得再硬编码主页路径。 */
const homeItem = navigation.find((item) => item.home === true);
if (!homeItem) throw new Error('navigation 登记表必须且只能有一个 home 条目');
export const HOME_PATH = homeItem.path;
export const HOME_LABEL = homeItem.label;

/** 主功能按登记顺序分组；顺序变化时分组随之更新 */
export function groupMainNavigation(): NavigationGroup[] {
  const groups: NavigationGroup[] = [];
  for (const item of navigation) {
    if (item.position !== 'main') continue;
    const label = item.group ?? '';
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }
  return groups;
}

function longestPathMatch(pathname: string, items: NavigationItem[]): NavigationItem | undefined {
  // 最长前缀优先：`/space` 与 `/space/mcp` 之类不会同时命中，最多一条为当前。
  return items
    .filter((item) => pathname === item.path || pathname.startsWith(`${item.path}/`))
    .sort((a, b) => b.path.length - a.path.length)[0];
}

/**
 * 单一当前菜单解析：桌面侧栏与手机抽屉共用同一函数，任一界面最多一个当前项。
 *
 * - `includeHidden=false`（桌面侧栏）：命中隐藏直达页时沿 `parentPath` 上溯，
 *   直到最近可见项（父菜单本身也可能隐藏，如 /books → /knowledge-bases）；
 * - `includeHidden=true`（手机抽屉）：直接标记隐藏项本身，便于焦点圈定。
 *
 * 上溯最多 `navigation.length` 步，父菜单缺失、自环或成环时返回 null（宁可无高亮，也不谎报）。
 */
export function resolveCurrentNavigationId(
  pathname: string | null,
  { includeHidden }: { includeHidden: boolean },
): string | null {
  if (!pathname) return null;
  const direct = longestPathMatch(pathname, navigation);
  if (!direct) return null;
  if (includeHidden) return direct.id;
  let current = direct;
  for (let hops = 0; current.hidden && hops < navigation.length; hops += 1) {
    if (!current.parentPath) return null;
    const parent = longestPathMatch(current.parentPath, navigation);
    if (!parent || parent.id === current.id) return null;
    current = parent;
  }
  return current.hidden ? null : current.id;
}
