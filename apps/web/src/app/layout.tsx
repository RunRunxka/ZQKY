import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import '@/styles/globals.css';
import '@/styles/motion.css';
import '@/components/layout/workspace-shell.css';
import { MotionPreference } from '@/components/layout/MotionPreference';
import { HOME_LABEL } from '@/services/navigation';
import { ModuleWorkspaceShell } from '@/components/layout/ModuleWorkspaceShell';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
// 默认标题跟随唯一主页，不再是教案工作台（R-02）。
export const metadata: Metadata = {
  title: `智启课源 · ${HOME_LABEL}`,
  description: '中文学习与备课工作台',
  // 品牌图标（T4b）：app/icon.svg 的文件约定与 metadata.icons 实测不产生重复 link
  // （写了 metadata.icons 时只输出这一条，且 href 稳定）；SVG 用 sizes="any" 供浏览器标签页选用。
  icons: { icon: [{ url: '/icon.svg', type: 'image/svg+xml', sizes: 'any' }] },
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <MotionPreference />
        <NavigationPreference>
          <ModuleWorkspaceShell>{children}</ModuleWorkspaceShell>
        </NavigationPreference>
      </body>
    </html>
  );
}
