import { redirect } from 'next/navigation';

/**
 * 参考仓库 /space/skills 为独立管理页；按本项目既定决策（Skills 管理只在设置，
 * 不复制第二套管理），旧入口统一重定向到设置的 Skills 区。
 */
export default function SpaceSkillsPage() {
  redirect('/settings#skills');
}
