import { ReviewWorkspace } from '@/features/question-bank/ReviewWorkspace';
import { pageParameters, type SearchParameters } from '@/services/page-parameters';

export const metadata = { title: '智启课源 · 试题校对' };

export default async function QuestionImportReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ importId: string }>;
  searchParams: Promise<SearchParameters>;
}) {
  const { importId } = await params;
  const { values, error } = pageParameters(await searchParams, ['returnPracticeSetId']);
  if (error) return <div className="space-page"><p role="alert">{error}</p></div>;
  return <ReviewWorkspace importId={importId} returnPracticeSetId={values.returnPracticeSetId} />;
}
