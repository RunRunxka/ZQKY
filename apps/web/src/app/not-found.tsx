import Link from 'next/link';
export default function NotFound() {
  return (
    <main className="status-page">
      <h1>页面不存在</h1>
      <Link className="button primary" href="/lesson-plans">
        返回教案工作台
      </Link>
    </main>
  );
}
