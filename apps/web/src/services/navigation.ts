import {
  BookMarked,
  BookOpen,
  ClipboardList,
  FilePenLine,
  FileQuestion,
  FolderOpen,
  GraduationCap,
  LayoutTemplate,
  Library,
  MessageSquare,
  PanelsTopLeft,
  Settings2,
  House,
  PenLine,
  BookText,
  LayoutGrid,
  Settings,
} from 'lucide-react';
import type { NavigationItem } from '@/contracts/navigation';

/**
 * 全站模块登记的唯一运行时来源：图标、分组、模块状态与规划页内容都登记在此，
 * WorkspaceShell 与规划状态页从这里读取，不各自维护副本。
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
    id: 'papers',
    label: '智能组卷',
    path: '/papers',
    status: 'planned',
    position: 'main',
    group: '教学工作台',
    icon: ClipboardList,
    plan: {
      summary: '组织试卷与课堂小练，右侧实时预览，支持 A3/A4 排版与导出。',
      capabilities: [
        '手动录入与结构化导入题目（本地组卷）',
        'A3 正式试卷 / A4 课堂小练排版',
        '从题库智能选题',
        '根据教材生成试题',
      ],
    },
  },
  {
    id: 'co-writer',
    label: '协同写作',
    path: '/co-writer',
    status: 'planned',
    position: 'main',
    group: '教学工作台',
    icon: PanelsTopLeft,
    sidebarIcon: PenLine,
    plan: {
      summary: '多人协同撰写讲义与文稿，支持自动保存、版本与 AI 辅助修改。',
      capabilities: ['协同编辑与自动保存', '版本历史与撤销', 'AI 辅助修改与 Whisper 双席位房间'],
    },
  },
  {
    id: 'reading',
    label: '沉浸阅读',
    path: '/reading',
    status: 'planned',
    position: 'main',
    group: '教学工作台',
    icon: BookOpen,
    sidebarIcon: BookText,
    plan: {
      summary: '沉浸式阅读学习材料，支持批注、书签与阅读进度。',
      capabilities: ['材料与集合管理', '批注 / 书签 / 阅读进度', '伴生阅读助手'],
    },
  },
  {
    id: 'space',
    label: '学习空间',
    path: '/space',
    status: 'planned',
    position: 'main',
    group: '教学工作台',
    icon: FolderOpen,
    sidebarIcon: LayoutGrid,
    plan: {
      summary: '沉淀会话历史、题库、角色目录与 CLI 应用的个人学习空间。',
      capabilities: ['会话历史归档', '题库与笔记本', '角色目录与 CLI 应用登记'],
    },
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
    id: 'question-bank',
    label: '题库',
    path: '/question-bank',
    status: 'planned',
    position: 'main',
    group: '教学资源',
    icon: FileQuestion,
    plan: {
      summary: '沉淀试题、答案与解析，按知识点、题型和难度组织。',
      capabilities: ['题目录入与版本管理', '知识点、题型、难度筛选', '为智能组卷提供选题来源'],
    },
  },
  {
    id: 'templates',
    label: '模板中心',
    path: '/templates',
    status: 'planned',
    position: 'main',
    group: '教学资源',
    icon: LayoutTemplate,
    plan: {
      summary: '管理 DOCX 模板的上传检查、字段映射与版本。',
      capabilities: ['DOCX 模板上传与支持范围检查', '字段映射与样例试填', '模板版本管理'],
    },
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
