import { ReviewWorkspace } from '@/features/question-bank/ReviewWorkspace';

export const metadata = { title: '智启课源 · 试题校对' };

export default async function QuestionImportReviewPage({
  params,
}: {
  params: Promise<{ importId: string }>;
}) {
  const { importId } = await params;
  return <ReviewWorkspace importId={importId} />;
}
