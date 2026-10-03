import { QuestionBankWorkspace, type QuestionBankTab } from '@/features/question-bank/QuestionBankWorkspace';
import { pageParameters, type SearchParameters } from '@/services/page-parameters';

export const metadata = { title: '智启课源 · 题库' };

export default async function QuestionBankPage({ searchParams }: { searchParams: Promise<SearchParameters> }) {
  const { values, error } = pageParameters(await searchParams, ['returnPracticeSetId', 'tab']);
  if (error) return <div className="space-page"><p role="alert">{error}</p></div>;
  if (values.tab !== undefined && !['imports', 'library', 'generation'].includes(values.tab)) {
    return <div className="space-page"><p role="alert">打开地址中的 tab 无效，请从题库入口重新打开。</p></div>;
  }
  return <QuestionBankWorkspace returnPracticeSetId={values.returnPracticeSetId} requestedTab={values.tab as QuestionBankTab | undefined} />;
}
