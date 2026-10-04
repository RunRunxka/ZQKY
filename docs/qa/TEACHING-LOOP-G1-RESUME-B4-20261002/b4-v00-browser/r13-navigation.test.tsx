// Independent navigation evidence ONLY. Actual server page, workspace and
// QuestionLibrary stay real; taxonomy/list data and generation body are doubles.
// No real backend, four-DB, service, model or browser acceptance is claimed.
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import QuestionBankPage from '@/app/question-bank/page';
import type { SearchParameters } from '@/services/page-parameters';

const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  query: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: navigation.push, replace: vi.fn(), back: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/question-bank',
  useSearchParams: () => navigation.query,
}));
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) =>
    <a href={href} {...props}>{children}</a>,
}));
vi.mock('@/services/textbook-api', () => ({
  fetchTextbookTaxonomy: vi.fn(async () => ({ stages: [], grades: [], subjects: [], editions: [] })),
}));
vi.mock('@/services/question-bank-api', () => ({
  listQuestions: vi.fn(async () => ({ questions: [], total: 0, offset: 0, limit: 20 })),
}));
vi.mock('@/features/question-bank/ImportBatchList', () => ({
  ImportBatchList: () => <p>独立导航批次替身</p>,
}));
vi.mock('@/features/question-bank/ImportQuestionPanel', () => ({
  ImportQuestionPanel: () => <div>独立导入弹窗替身</div>,
}));
vi.mock('@/features/question-bank/KnowledgePointFields', () => ({
  KnowledgePointSelect: () => <div>独立知识点筛选替身</div>,
}));
vi.mock('@/features/question-bank/QuestionDetailPanel', () => ({
  QuestionDetailPanel: () => <div>独立详情替身</div>,
}));
vi.mock('@/features/question-bank/GenerationPanel', () => ({
  GenerationPanel: () => <div data-testid="r13-generation-body">补题组件实际已打开</div>,
}));

async function pageWithQuery(query: SearchParameters = {}) {
  navigation.query = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (typeof value === 'string') navigation.query.set(key, value);
  }
  // Use the real thin server page to validate and pass the route intent. No new
  // guessed component prop or direct call to a product event handler is used.
  return QuestionBankPage({ searchParams: Promise.resolve(query) });
}

const libraryTab = () => screen.getByRole('tab', { name: '已入库题目' });
const importsTab = () => screen.getByRole('tab', { name: '导入批次' });
const practice = 'practice /+?';
let originalShowModal: PropertyDescriptor | undefined;
let originalClose: PropertyDescriptor | undefined;

function assertPushedIntent(tab: 'imports' | 'library') {
  const href = navigation.push.mock.calls.at(-1)?.[0];
  expect(typeof href).toBe('string');
  const actual = new URL(href as string, window.location.origin);
  expect(actual.pathname).toBe('/question-bank');
  expect(actual.searchParams.get('tab')).toBe(tab);
  expect(actual.searchParams.get('returnPracticeSetId')).toBe(practice);
}

beforeEach(() => {
  originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
  originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    writable: true,
    value: function showModal(this: HTMLDialogElement) { this.open = true; },
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    writable: true,
    value: function close(this: HTMLDialogElement) { this.open = false; },
  });
  navigation.push.mockReset();
  navigation.query = new URLSearchParams();
  window.history.replaceState(null, '', '/question-bank');
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', originalShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, 'close', originalClose);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
  window.history.replaceState(null, '', '/question-bank');
});

describe('R13 independent query navigation with controlled fragment timing', () => {
  it('client query intent selects library despite delayed repeated hash; encoded context/manual tabs/legacy library stay valid', async () => {
    const view = render(await pageWithQuery());
    expect(importsTab()).toHaveAttribute('aria-selected', 'true');
    // Deterministic control: preserve the mounted workspace, then deliver the
    // observed duplicate fragment separately from the authoritative query.
    window.history.replaceState(null, '', '/question-bank#library#library');
    view.rerender(await pageWithQuery({ tab: 'library', returnPracticeSetId: practice }));
    await waitFor(() => expect(libraryTab()).toHaveAttribute('aria-selected', 'true'));
    expect(importsTab()).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('link', { name: '返回练习并重新选正式题' })).toHaveAttribute(
      'href', '/practices?practiceSetId=practice%20%2F%2B%3F',
    );
    fireEvent.click(importsTab());
    expect(importsTab()).toHaveAttribute('aria-selected', 'true');
    assertPushedIntent('imports');
    fireEvent.click(libraryTab());
    expect(libraryTab()).toHaveAttribute('aria-selected', 'true');
    assertPushedIntent('library');
    view.unmount();
    window.history.replaceState(null, '', '/question-bank#library');
    render(await pageWithQuery());
    await waitFor(() => expect(libraryTab()).toHaveAttribute('aria-selected', 'true'));
  });

  it('generation query opens actual library generation state after cached library; legacy generation/manual tabs stay valid', async () => {
    window.history.replaceState(null, '', '/question-bank#library');
    const view = render(await pageWithQuery({ returnPracticeSetId: practice }));
    await waitFor(() => expect(libraryTab()).toHaveAttribute('aria-selected', 'true'));
    expect(screen.queryByTestId('r13-generation-body')).not.toBeInTheDocument();
    // A cached library already exists; simply changing initialGenerationOpen
    // without synchronizing the actual QuestionLibrary state is insufficient.
    window.history.replaceState(null, '', '/question-bank#library#library');
    view.rerender(await pageWithQuery({ tab: 'generation', returnPracticeSetId: practice }));
    await waitFor(() => expect(screen.getByTestId('r13-generation-body')).toBeInTheDocument());
    expect(libraryTab()).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('link', { name: '返回练习并重新选正式题' })).toHaveAttribute(
      'href', '/practices?practiceSetId=practice%20%2F%2B%3F',
    );
    fireEvent.click(importsTab());
    expect(importsTab()).toHaveAttribute('aria-selected', 'true');
    assertPushedIntent('imports');
    fireEvent.click(libraryTab());
    expect(libraryTab()).toHaveAttribute('aria-selected', 'true');
    assertPushedIntent('library');
    view.unmount();
    window.history.replaceState(null, '', '/question-bank#generation');
    render(await pageWithQuery({ returnPracticeSetId: practice }));
    await waitFor(() => expect(screen.getByTestId('r13-generation-body')).toBeInTheDocument());
    expect(libraryTab()).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('link', { name: '返回练习并重新选正式题' })).toHaveAttribute(
      'href', '/practices?practiceSetId=practice%20%2F%2B%3F',
    );
  });
});
