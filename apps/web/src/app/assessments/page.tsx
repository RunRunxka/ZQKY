import { AssessmentsWorkspace } from '@/features/assessments/AssessmentsWorkspace';
import { pageParameters, type SearchParameters } from '@/services/page-parameters';

export const metadata = { title: '智启课源 · 施测与成绩' };

export default async function AssessmentsPage({ searchParams }: { searchParams: Promise<SearchParameters> }) {
  const { values, error } = pageParameters(await searchParams, ['assessmentId', 'step']);
  if (error || (values.step && values.step !== 'score' && values.step !== 'history') || (values.step && !values.assessmentId)) {
    return <div className="space-page"><p role="alert">{error ?? '请从固定施测记录打开成绩或历史。'}</p></div>;
  }
  return <AssessmentsWorkspace key={`${values.assessmentId ?? ''}|${values.step ?? ''}`}
    initialAssessmentId={values.assessmentId} initialStep={values.step as 'score' | 'history' | undefined} />;
}
