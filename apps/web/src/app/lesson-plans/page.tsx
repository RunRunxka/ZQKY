import { LessonPlanWorkspace } from '@/features/lesson-plan/LessonPlanWorkspace';
import { pageParameters, type SearchParameters } from '@/services/page-parameters';

export const metadata = { title: '智启课源 · 教案工作台' };

export default async function LessonPlansPage({ searchParams }: { searchParams: Promise<SearchParameters> }) {
  const { values, error } = pageParameters(await searchParams, ['lessonPlanId', 'revisionId', 'analysisRunId']);
  const routeError = error ?? (values.revisionId && !values.lessonPlanId ? '请从后台教案的固定历史记录打开修订。' : undefined);
  return <LessonPlanWorkspace key={routeError ?? ''}
    initialLessonPlanId={values.lessonPlanId} initialRevisionId={values.revisionId}
    initialAnalysisRunId={values.analysisRunId} initialRouteError={routeError} />;
}
