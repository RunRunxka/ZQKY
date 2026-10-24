import {
  MessageSquare,
  House,
  Settings2,
  Settings,
  Library,
  LibraryBig,
  ListTree,
  FileQuestion,
  LineChart,
  Activity,
  Users,
  FileText,
  NotebookPen,
  ClipboardList,
} from 'lucide-react';
import type { NavigationItem } from '@/contracts/navigation';

/**
 * 全站模块登记的唯一运行时来源（推倒重做最小骨架）：
 * 对话（home）+ 教材资料库 + 知识点 + 设置（模型配置）。业务模块随重建逐项回归时在此登记。
 */
export const navigation: NavigationItem[] = [
  {
    id: 'chat',
    label: '对话',
    path: '/chat',
    status: 'ready',
    position: 'main',
    group: '工作台',
    // 全站唯一主页：品牌按钮、404/错误页返回入口与默认标题都从这一条派生
    home: true,
    icon: MessageSquare,
    sidebarIcon: House,
  },
  {
    // 教案工作台：三栏（模块轨 · 章节编辑 · 第 3 页起 A4 校样台）+ 悬浮 dock；导出由后端补齐封面目录
    id: 'lesson-plans',
    label: '教案工作台',
    path: '/lesson-plans',
    status: 'ready',
    position: 'main',
    group: '工作台',
    icon: NotebookPen,
    sidebarIcon: NotebookPen,
  },
  {
    // 教材资料库（需求 7）：基础库 / 我的教材 / 历史登记 + 导入入库；数据全部来自 FastAPI
    id: 'textbooks',
    label: '教材资料库',
    path: '/textbooks',
    status: 'ready',
    position: 'main',
    group: '教学资源',
    icon: Library,
    sidebarIcon: LibraryBig,
  },
  {
    // 知识点（需求 3）：按教材目录成树的知识点库，节点可自定义增改；数据全部来自 FastAPI
    id: 'knowledge-points',
    label: '知识点',
    path: '/knowledge-points',
    status: 'ready',
    position: 'main',
    group: '教学资源',
    icon: ListTree,
    sidebarIcon: ListTree,
  },
  {
    // 题库（需求 4）：按知识点×难度分类，教材课后习题提取与批量导入；数据全部来自 FastAPI
    id: 'question-bank',
    label: '题库',
    path: '/question-bank',
    status: 'ready',
    position: 'main',
    group: '教学资源',
    icon: FileQuestion,
    sidebarIcon: FileQuestion,
  },
  {
    // 练习（需求 8）：学情/描述驱动题库出题与选拔，教师微调并确认后导出学生卷/教师卷/成绩模板
    id: 'practices',
    label: '练习',
    path: '/practices',
    status: 'ready',
    position: 'main',
    group: '教学资源',
    icon: ClipboardList,
    sidebarIcon: ClipboardList,
  },
  {
    // 学情分析（需求 5）：小题分导入、班级/试卷/时间筛选、五项图表与 AI 评价；数据全部来自 FastAPI
    id: 'learning-analysis',
    label: '学情分析',
    path: '/learning-analysis',
    status: 'ready',
    position: 'main',
    group: '学情与施测',
    icon: LineChart,
    sidebarIcon: Activity,
  },
  {
    // 班级管理（需求 6）：班级/学生名单管理与 xlsx 一键导入；删除=归档可恢复
    id: 'assessments-roster',
    label: '班级管理',
    path: '/assessments/roster',
    status: 'ready',
    position: 'main',
    group: '学情与施测',
    icon: Users,
    sidebarIcon: Users,
  },
  {
    // 试卷管理（需求 6）：导入试卷（DOCX/PDF 文本层）→ 校对拆题 → AI 知识点分类占比；不显示试卷内容
    id: 'assessments-papers',
    label: '试卷管理',
    path: '/assessments/papers',
    status: 'ready',
    position: 'main',
    group: '学情与施测',
    icon: FileText,
    sidebarIcon: FileText,
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
  // 最长前缀优先：`/chat` 与 `/chat/x` 之类不会同时命中，最多一条为当前。
  return items
    .filter((item) => pathname === item.path || pathname.startsWith(`${item.path}/`))
    .sort((a, b) => b.path.length - a.path.length)[0];
}

/**
 * 单一当前菜单解析：桌面侧栏与手机抽屉共用同一函数，任一界面最多一个当前项。
 *
 * - `includeHidden=false`（桌面侧栏）：命中隐藏直达页时沿 `parentPath` 上溯，
 *   直到最近可见项（父菜单本身也可能隐藏）；
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
