import { LearningAnalysisWorkspace } from '@/features/learning-analysis/LearningAnalysisWorkspace';
import { pageParameters, type SearchParameters } from '@/services/page-parameters';

export const metadata = { title: '智启课源 · 学情分析' };
export default async function LearningAnalysisPage({ searchParams }: { searchParams: Promise<SearchParameters> }) {
  const { values, error } = pageParameters(await searchParams, ['assessmentId', 'scoreRevisionId', 'runId']);
  if (error) return <div className="space-page"><p role="alert">{error}</p></div>;
  return <LearningAnalysisWorkspace key={`${values.assessmentId ?? ''}|${values.scoreRevisionId ?? ''}|${values.runId ?? ''}`}
    initialAssessmentId={values.assessmentId} initialScoreRevisionId={values.scoreRevisionId} initialRunId={values.runId} />;
}
