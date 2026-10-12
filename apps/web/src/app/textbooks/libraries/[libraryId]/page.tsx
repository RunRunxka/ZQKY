import { LibraryDetailSection } from '@/features/textbook/LibraryDetailSection';

export const metadata = { title: '智启课源 · 教材库详情' };

/**
 * 逻辑库详情（`/textbooks/libraries/[libraryId]`）：库信息 + 书册列表（更新 / 编辑分类 /
 * 删除 / 来源预览）。壳由 ModuleWorkspaceShell 统一提供（root=`textbooks`），
 * 库 id 由 Next 解码后原样透传。
 */
export default async function TextbookLibraryPage({
  params,
}: {
  params: Promise<{ libraryId: string }>;
}) {
  const { libraryId } = await params;
  return <LibraryDetailSection libraryId={libraryId} />;
}
