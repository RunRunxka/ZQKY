import type { Metadata } from 'next';
import { StatusShell } from '@/components/layout/ShellScope';
import { HomeReturnLink } from '@/components/layout/HomeReturnLink';

export const metadata: Metadata = { title: '智启课源 · 页面不存在' };

export default function NotFound() {
  return (
    <StatusShell pageTitle="页面不存在">
      <h1>页面不存在</h1>
      <p>这个地址没有对应的页面，可能是链接已过期或输入有误。</p>
      <HomeReturnLink />
    </StatusShell>
  );
}
