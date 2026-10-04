import { PracticesWorkspace } from '@/features/practices/PracticesWorkspace';
import { pageParameters, type SearchParameters } from '@/services/page-parameters';

export const metadata = { title: '智启课源 · 针对练习' };
export default async function PracticesPage({ searchParams }: { searchParams: Promise<SearchParameters> }) {
  const { values, error } = pageParameters(await searchParams, ['practiceSetId', 'practiceRevisionId', 'analysisRunId']);
  if (error) return <div className="space-page"><p role="alert">{error}</p></div>;
  return <PracticesWorkspace key={`${values.practiceSetId ?? ''}|${values.practiceRevisionId ?? ''}|${values.analysisRunId ?? ''}`}
    initialPracticeSetId={values.practiceSetId} initialPracticeRevisionId={values.practiceRevisionId} initialAnalysisRunId={values.analysisRunId} />;
}
