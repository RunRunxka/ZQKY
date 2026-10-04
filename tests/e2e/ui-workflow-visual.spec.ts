import { test, expect, type Page as BrowserPage, type TestInfo } from '@playwright/test';
import {
  run,
  classRow,
  evidenceRow,
  practice,
  revision,
  page as fixturePage,
} from '../../apps/web/src/features/practices/test-fixtures';
import type {
  EvidenceRow,
  ExportArtifact,
  NoteView,
  PracticeRevisionView,
  PracticeSetView,
  StudentReportRow,
} from '../../apps/web/src/contracts/b4';
import type {
  AssessmentDetailView,
  AssessmentList,
} from '../../apps/web/src/contracts/assessments';
import type { ClassList } from '../../apps/web/src/contracts/roster';
import type { RichContentV2 } from '../../apps/web/src/contracts/teaching-loop';

const viewports = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
];

// Explicit deterministic API fixtures, derived from the existing unit fixtures.
// These screenshots verify rendering; they are not evidence of a real backend workflow.
const content: RichContentV2 = {
  ...structuredClone(revision.items[0].content),
  stemBlocks: [
    ...structuredClone(revision.items[0].content.stemBlocks),
    {
      id: 'visual-long-text',
      kind: 'paragraph',
      text: '隔离视觉夹具：核对共同材料、完整题干、表格、公式及教师答案。'.repeat(4),
    },
    {
      id: 'visual-table',
      kind: 'table',
      columnCount: 8,
      cells: Array.from({ length: 16 }, (_, index) => ({
        text: index < 8 ? `数据列${index + 1}` : `固定值${index - 7}`,
        isHeader: index < 8,
        rowSpan: 1,
        colSpan: 1,
      })),
    },
    { id: 'visual-formula', kind: 'formula', latex: '\\frac{1}{2} + \\frac{1}{3} = \\frac{5}{6}' },
  ],
};
const visualEvidence: EvidenceRow = { ...structuredClone(evidenceRow), content: { ...content } };
const draft: PracticeRevisionView = {
  ...structuredClone(revision),
  version: 2,
  items: revision.items.map((item) => ({ ...structuredClone(item), content })),
};
const reviewed: PracticeRevisionView = {
  ...structuredClone(draft),
  practiceRevisionId: 'reviewed-a',
  version: 1,
  state: 'reviewed',
  reviewedAt: '2026-10-02T10:00:00Z',
};
const visualPractice: PracticeSetView = {
  ...structuredClone(practice),
  revision: 2,
  currentRevision: draft,
  revisions: [reviewed, draft],
};
const studentRow: StudentReportRow = {
  participant: structuredClone(run.participants[0]),
  knowledgePoint: structuredClone(run.knowledgePoints[0]),
  observation: 'needs_consolidation',
  informationIncomplete: true,
  expectedCount: 2,
  validCount: 1,
  stateCounts: { recorded: 1, missing: 1, absent: 0, exempt: 0 },
  totalScoreUnits: 0,
  totalMaxScoreUnits: 200,
};
const assessment: AssessmentDetailView = {
  assessment: {
    assessmentId: run.assessmentId,
    paperRevisionId: run.paperRevisionId,
    paperId: 'paper-source',
    paperTitle: run.paperTitle,
    subjectId: run.subjectId,
    title: '隔离视觉施测',
    assessmentType: 'quiz',
    heldOn: '2026-10-02',
    activeScoreRevisionId: run.scoreRevisionId,
    state: 'closed',
    revision: 1,
    classIds: ['class-a'],
    participantCount: 1,
    createdAt: '2026-10-02',
  },
  participants: [
    {
      participantId: 'pa',
      studentId: 'student-a',
      studentNoSnapshot: '001',
      nameSnapshot: '甲',
      classId: 'class-a',
      attemptNo: 1,
      attendance: 'present',
      classConfirmed: false,
      classConfirmationNote: null,
      classConfirmationAt: null,
    },
  ],
};
const emptyAssessments: AssessmentList = fixturePage([]);
const emptyClasses: ClassList = fixturePage([]);

async function installFixtures(page: BrowserPage) {
  const requests: Array<{ method: string; path: string; status: number }> = [];
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api\/v1/, '');
    let status = 200;
    let body: unknown;
    if (request.method() === 'PATCH' && path === '/practice-sets/practice-a/draft') {
      status = 409;
      body = {
        code: 'REVISION_CONFLICT',
        message: '隔离夹具：保存发生版本冲突，输入应保留。',
        retryable: false,
        details: { currentRevision: 3 },
      };
    } else if (request.method() !== 'GET') {
      status = 503;
      body = {
        code: 'VISUAL_FIXTURE_UNSUPPORTED',
        message: '隔离视觉夹具不执行业务写入。',
        retryable: false,
      };
    } else if (path === '/analysis-runs') body = fixturePage([run]);
    else if (path === '/analysis-runs/run-old') body = run;
    else if (path === '/analysis-runs/run-old/classes') body = fixturePage([classRow]);
    else if (path === '/analysis-runs/run-old/students') body = fixturePage([studentRow]);
    else if (path === '/analysis-runs/run-old/evidence') body = fixturePage([visualEvidence]);
    else if (path === '/analysis-runs/run-old/notes') body = fixturePage<NoteView>([]);
    else if (path === '/assessments') body = emptyAssessments;
    else if (path === '/assessments/assessment-old') body = assessment;
    else if (path === '/classes') body = emptyClasses;
    else if (path === '/practice-sets') body = fixturePage([visualPractice]);
    else if (path === '/practice-sets/practice-a') body = visualPractice;
    else if (path === '/practice-sets/practice-a/revisions/reviewed-a') body = reviewed;
    else if (path === '/practice-sets/practice-a/revisions/draft-a') body = draft;
    else if (/^\/practice-sets\/practice-a\/revisions\/(reviewed-a|draft-a)\/exports$/.test(path))
      body = fixturePage<ExportArtifact>([]);
    else {
      status = 503;
      body = {
        code: 'VISUAL_FIXTURE_UNSUPPORTED',
        message: `隔离视觉夹具未提供此读取：${path}`,
        retryable: false,
      };
    }
    requests.push({ method: request.method(), path, status });
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  });
  return requests;
}

async function capture(page: BrowserPage, info: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await expect
    .poll(() =>
      page
        .locator('[data-motion-reveal], [role="tabpanel"]')
        .evaluateAll((nodes) =>
          nodes.every(
            (node) =>
              !(node instanceof HTMLElement) ||
              (node.style.transform === '' && node.style.opacity === ''),
          ),
        ),
    )
    .toBe(true);
  const layout = await page.evaluate(() => {
    const scroller = document.querySelector<HTMLElement>('.module-workspace-content');
    const header = document.querySelector<HTMLElement>('.space-header')?.getBoundingClientRect();
    const content = document.querySelector<HTMLElement>('.space-content')?.getBoundingClientRect();
    return {
      rootOverflow: document.documentElement.scrollWidth - innerWidth,
      workspaceOverflow: scroller ? scroller.scrollWidth - scroller.clientWidth : 0,
      leftDifference: header && content ? Math.abs(header.x - content.x) : null,
      widthDifference: header && content ? Math.abs(header.width - content.width) : null,
    };
  });
  expect(layout.rootOverflow, `${name}: document overflow`).toBeLessThanOrEqual(1);
  expect(layout.workspaceOverflow, `${name}: workspace overflow`).toBeLessThanOrEqual(1);
  expect(layout.leftDifference, `${name}: header alignment`).not.toBeNull();
  expect(layout.leftDifference!).toBeLessThanOrEqual(1);
  expect(layout.widthDifference!).toBeLessThanOrEqual(1);
  await info.attach(`${name}-layout`, {
    body: JSON.stringify(layout),
    contentType: 'application/json',
  });
  await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true });
}

for (const viewport of viewports) {
  test(`教学闭环有数据视觉夹具：${viewport.width}，固定依据、完整题面与只读历史`, async ({
    page,
  }, info) => {
    test.setTimeout(120000);
    await page.setViewportSize(viewport);
    const requests = await installFixtures(page);

    await page.goto('/learning-analysis?runId=run-old');
    await expect(page.locator('.unified-shell')).toHaveAttribute('data-navigation-ready', 'true');
    const facts = page.getByRole('region', { name: '报告事实与证据', exact: true });
    const classTable = facts.locator('.b4-table-wrap');
    await expect(classTable.getByRole('cell').filter({ hasText: '2 / 3' })).toBeVisible();
    await expect(classTable.getByText('固定知识点', { exact: false })).toBeVisible();
    await classTable.scrollIntoViewIfNeeded();
    if (viewport.width === 390) {
      expect(
        await classTable.evaluate((node) => node.scrollWidth - node.clientWidth),
      ).toBeGreaterThan(0);
      await classTable.evaluate((node) => {
        node.scrollLeft = node.scrollWidth;
      });
      expect(await classTable.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
      await classTable.evaluate((node) => {
        node.scrollLeft = 0;
      });
    }
    await capture(page, info, `analysis-classes-${viewport.width}`);

    await facts.getByRole('tab', { name: '全部题证据', exact: true }).click();
    const evidence = facts
      .locator('details')
      .filter({ has: page.locator('summary').filter({ hasText: '甲 · 人次1 · 1(1)' }) })
      .first();
    await evidence.locator(':scope > summary').click();
    await expect(evidence.getByText('固定共同材料', { exact: true })).toBeVisible();
    await expect(evidence.getByText('教师答案甲', { exact: true })).toBeVisible();
    await expect(evidence.getByText('教师解析乙', { exact: true })).toBeVisible();
    await expect(evidence.locator('.katex')).toBeVisible();
    await expect(evidence.locator('.katex .mfrac').first()).toBeVisible();
    await expect(evidence.locator('.katex-error')).toHaveCount(0);
    if (viewport.width === 390)
      expect(
        await evidence
          .locator('.rich-table-scroll')
          .evaluate((node) => node.scrollWidth - node.clientWidth),
      ).toBeGreaterThan(0);
    await evidence.scrollIntoViewIfNeeded();
    await capture(page, info, `analysis-evidence-${viewport.width}`);

    await page.goto('/practices?practiceSetId=practice-a');
    const editor = page.getByRole('region', { name: '练习草稿编辑', exact: true });
    const score = editor.getByRole('textbox', { name: '第1题整题满分', exact: true });
    await expect(score).toBeEnabled();
    await expect(score).toHaveValue('1');
    await score.fill('2');
    const leafScore = editor.getByRole('textbox', { name: '第1题节点1满分', exact: true });
    await leafScore.fill('2');
    await editor.getByRole('button', { name: '保存草稿', exact: true }).click();
    await expect(editor.getByRole('alert')).toContainText('REVISION_CONFLICT');
    await expect(score).toHaveValue('2');
    await expect(leafScore).toHaveValue('2');
    await expect(editor.getByText('有未保存修改', { exact: false })).toBeVisible();
    await editor.getByRole('alert').scrollIntoViewIfNeeded();
    await capture(page, info, `practice-draft-conflict-${viewport.width}`);

    const contents = page.getByRole('region', { name: '服务端完整练习审阅', exact: true });
    await contents.locator('details > summary').click();
    await expect(contents.getByText('教师答案甲', { exact: true })).toBeVisible();
    await expect(contents.getByText('教师解析乙', { exact: true })).toBeVisible();
    await contents.scrollIntoViewIfNeeded();
    await capture(page, info, `practice-draft-content-${viewport.width}`);

    await page
      .getByRole('region', { name: '练习修订历史', exact: true })
      .getByRole('button', { name: /v1 · 已审核，只读/ })
      .click();
    const leave = page.getByRole('dialog', { name: '处理未保存练习', exact: true });
    await expect(leave).toBeVisible();
    await leave.getByRole('button', { name: '保留恢复稿并离开', exact: true }).click();
    await expect(leave).toHaveCount(0);
    await expect(page.getByRole('heading', { name: '审核版只读', exact: true })).toBeVisible();
    await expect(editor).toHaveCount(0);
    await expect(page.getByRole('textbox', { name: '第1题整题满分', exact: true })).toHaveCount(0);
    await contents.locator('details > summary').click();
    await expect(contents.getByText('固定审核内容', { exact: false })).toBeVisible();
    await expect(contents.getByText('固定共同材料', { exact: true })).toBeVisible();
    await expect(contents.getByText('教师答案甲', { exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: '固定练习导出', exact: true })).toBeVisible();
    await contents.scrollIntoViewIfNeeded();
    await capture(page, info, `practice-reviewed-history-${viewport.width}`);

    expect(requests.filter((request) => request.method !== 'GET')).toEqual([
      { method: 'PATCH', path: '/practice-sets/practice-a/draft', status: 409 },
    ]);
    expect(
      requests.filter((request) => request.status === 503),
      'Every API read used by these views has an explicit fixture',
    ).toEqual([]);
    await info.attach('isolated-api-fixtures', {
      body: JSON.stringify(requests, null, 2),
      contentType: 'application/json',
    });
  });
}
