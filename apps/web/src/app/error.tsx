'use client';
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="status-page">
      <h1>页面暂时无法打开</h1>
      <p>已保存的本机草稿仍保留在浏览器中。</p>
      <button className="button primary" onClick={reset}>
        重新尝试
      </button>
    </main>
  );
}
