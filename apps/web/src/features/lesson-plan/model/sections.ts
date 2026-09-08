import { FileText, Target, Flag, Lightbulb, Route, ClipboardList, NotebookPen } from 'lucide-react';
export const sections = [
  { id: 'basic', label: '基本信息', icon: FileText, desc: '从课题开始，搭好这节课的框架。' },
  { id: 'core', label: '核心素养目标', icon: Target, field: 'coreCompetencies' },
  { id: 'key', label: '教学重、难点', icon: Flag, field: 'keyPoints' },
  { id: 'design', label: '教学设计', icon: Lightbulb, field: 'teachingDesign' },
  { id: 'process', label: '教学过程', icon: Route },
  { id: 'exercises', label: '练习与作业', icon: ClipboardList, field: 'exercises' },
  { id: 'reflection', label: '教学反思', icon: NotebookPen, field: 'reflection' },
] as const;
