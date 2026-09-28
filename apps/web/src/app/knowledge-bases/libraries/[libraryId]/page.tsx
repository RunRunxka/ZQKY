import { LibraryDetailSection } from '@/features/textbook/LibraryDetailSection';

export const metadata = { title: '智启课源 · 教材库详情' };

/**
 * 逻辑库详情（`/knowledge-bases/libraries/[libraryId]`）。
 * 静态段 `libraries` 优先于既有 `[kbName]` 动态段；库 id 由 Next 解码后原样透传。
 */
export default async function LibraryDetailPage({
  params,
}: {
  params: Promise<{ libraryId: string }>;
}) {
  const { libraryId } = await params;
  return <LibraryDetailSection libraryId={libraryId} />;
}
