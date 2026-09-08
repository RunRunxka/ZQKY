import {
  BookMarked,
  Bot,
  BookOpen,
  ClipboardList,
  FilePenLine,
  FileQuestion,
  FolderOpen,
  GraduationCap,
  LayoutTemplate,
  Library,
  MessageSquare,
  NotebookPen,
  PanelsTopLeft,
  Settings2,
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
    icon: MessageSquare,
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
    plan: {
      summary: '多人协同撰写教案与文稿。',
      capabilities: ['协同编辑与评注', '版本对比与恢复'],
    },
  },
  {
    id: 'reading',
    label: '沉浸阅读',
    path: '/reading',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: BookOpen,
  },
  {
    id: 'space',
    label: '学习空间',
    path: '/space',
    status: 'ready',
    position: 'main',
    group: '教学工作台',
    icon: FolderOpen,
  },
  {
    id: 'notebooks',
    label: '笔记本',
    path: '/notebooks',
    status: 'ready',
    position: 'main',
    hidden: true,
    group: '教学工作台',
    icon: NotebookPen,
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
    id: 'books',
    label: '书籍',
    path: '/books',
    status: 'ready',
    position: 'main',
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
    id: 'agents',
    label: 'Agent 任务',
    path: '/agents',
    status: 'planned',
    position: 'main',
    group: '扩展能力',
    icon: Bot,
    plan: {
      summary: '以任务方式编排备课、组卷等自动化流程。',
      capabilities: ['任务创建与状态跟踪', '受控业务工具调用（检索、校验、渲染）'],
    },
  },
  {
    id: 'settings',
    label: '设置',
    path: '/settings',
    status: 'ready',
    position: 'bottom',
    icon: Settings2,
  },
];

export interface NavigationGroup {
  label: string;
  items: NavigationItem[];
}

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
