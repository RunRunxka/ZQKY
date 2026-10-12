import { ReviewWorkspace } from '@/features/question-bank/ReviewWorkspace';

export const metadata = { title: '智启课源 · 试题校对' };

/**
 * 导入批次校对（`/question-bank/imports/[importId]`）：左原文（含未归属原文）/ 右草稿编辑，
 * 下方 AI 整理建议、合并与确认入库；所有写入带乐观锁，冲突保留输入。
 *
 * 壳与滚动容器由 layout 的 ModuleWorkspaceShell 统一提供（`question-bank` 登记为业务根）。
 */
export default async function QuestionImportReviewPage({
  params,
}: {
  params: Promise<{ importId: string }>;
}) {
  const { importId } = await params;
  return <ReviewWorkspace importId={importId} />;
}
