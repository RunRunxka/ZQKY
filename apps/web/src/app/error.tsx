'use client';
import { StatusShell } from '@/components/layout/ShellScope';
import { HomeReturnLink } from '@/components/layout/HomeReturnLink';

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <StatusShell pageTitle="页面暂时无法打开">
      <h1>页面暂时无法打开</h1>
      <p>已保存的本机草稿仍保留在浏览器中。</p>
      <div className="status-actions">
        <button className="button primary" onClick={reset}>
          重新尝试
        </button>
        <HomeReturnLink label="返回主页" />
      </div>
    </StatusShell>
  );
}
