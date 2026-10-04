import { test, expect } from '@playwright/test';
import type {
  DocumentDetail,
  LibraryDetail,
  SourceSpanView,
  TextbookTaxonomy,
} from '../../apps/web/src/contracts/textbook';

// Deterministic frontend fixtures, never a real textbook import or RAG quality verdict.
const taxonomy: TextbookTaxonomy = {
  stages: [{ id: 'junior', label: '初中' }],
  grades: [{ id: 'g7', label: '七年级', stageId: 'junior' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'rj', label: '人教版' }],
};
const document: DocumentDetail = {
  documentId: 'ui-doc',
  ownerId: 'system',
  title: '七年级数学上册（隔离教材）',
  libraryIds: ['ui-library'],
  gradeIds: ['g7'],
  subjectId: 'math',
  editionId: 'rj',
  metadataRevisionId: 'meta-ui',
  currentRevision: {
    revisionId: 'rev-ui',
    originalFileSha256: 'original-ui',
    normalizedTextSha256: 'normalized-ui',
    parserVersion: 'fixture',
    charCount: 1200,
    chunkCount: 12,
    createdAt: '2026-10-04T00:00:00Z',
  },
  pendingRevisionId: null,
  deletedAt: null,
  revision: 4,
  metadata: {
    metadataRevisionId: 'meta-ui',
    title: '七年级数学上册（隔离教材）',
    stageId: 'junior',
    gradeIds: ['g7'],
    subjectId: 'math',
    editionId: 'rj',
    publicationLabel: '2024年版',
    volumeLabel: '上册',
  },
  warnings: [],
};
const library: LibraryDetail = {
  libraryId: 'ui-library',
  kind: 'base',
  ownerId: 'system',
  displayName: '七年级数学基础库（隔离验收）',
  gradeId: 'g7',
  subjectId: 'math',
  editionId: 'rj',
  documentCount: 2,
  readyDocumentCount: 1,
  revision: 3,
  deletedAt: null,
  documents: [
    document,
    {
      ...document,
      documentId: 'ui-pending',
      title: '七年级数学下册（待入库）',
      currentRevision: null,
      pendingRevisionId: 'rev-pending',
    },
  ],
};
const source: SourceSpanView = {
  documentRevisionId: 'rev-ui',
  normalizedTextSha256: 'normalized-ui',
  charStart: 0,
  charEnd: 1200,
  text: Array.from(
    { length: 12 },
    (_, i) =>
      `第${i + 1}段：隔离教材来源示例。以数轴解释有理数加法，保留例题条件、步骤和结论；这段文字仅用于检查长内容的阅读排版。`,
  ).join('\n\n'),
  locator: {
    kind: 'markdown',
    lineStart: 1,
    lineEnd: 24,
    pageStart: null,
    pageEnd: null,
    blockStart: null,
    blockEnd: null,
  },
};

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
]) {
  test(`教材列表、详情、长原文和分类冲突保留输入 ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname.replace('/api/v1', '');
      if (path === '/textbook-taxonomy') return route.fulfill({ json: taxonomy });
      if (path === '/textbook-libraries')
        return route.fulfill({
          json: { libraries: url.searchParams.get('kind') === 'base' ? [library] : [] },
        });
      if (path === '/textbook-libraries/ui-library') return route.fulfill({ json: library });
      if (path === '/textbooks/ui-doc') {
        if (route.request().method() === 'PATCH')
          return route.fulfill({
            status: 409,
            json: {
              code: 'REVISION_CONFLICT',
              message: '隔离验收：分类已被其他操作修改',
              retryable: false,
            },
          });
        return route.fulfill({ json: document });
      }
      if (path === '/textbook-revisions/rev-ui/source') return route.fulfill({ json: source });
      return route.fulfill({ status: 503, json: { detail: '隔离视觉验收：未提供的服务不可用' } });
    });
    const capture = async (name: string) => {
      await page.evaluate(() => document.fonts.ready);
      await expect
        .poll(() =>
          page
            .locator('[data-motion-reveal]')
            .evaluateAll((nodes) =>
              nodes.every((node) => !(node instanceof HTMLElement) || !node.style.transform),
            ),
        )
        .toBe(true);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth - innerWidth),
        name,
      ).toBeLessThanOrEqual(1);
      await page.screenshot({
        path: info.outputPath(`${name}-${viewport.width}.png`),
        fullPage: true,
      });
    };
    await page.goto('/knowledge-bases');
    const libraryLink = page.getByRole('link', { name: /七年级数学基础库（隔离验收）/ });
    await expect(libraryLink).toBeVisible();
    await capture('textbook-list');
    await libraryLink.click();
    await expect(page.getByRole('heading', { name: library.displayName })).toBeVisible();
    await expect(page.getByText('有待入库修订')).toBeVisible();
    await capture('textbook-detail');
    await page.getByRole('button', { name: '来源预览', exact: true }).first().click();
    await page.getByRole('button', { name: '读取原文', exact: true }).click();
    await expect(page.locator('.textbook-source-text')).toContainText('第12段');
    await capture('textbook-source');
    await page.locator('.textbook-source-text').scrollIntoViewIfNeeded();
    await capture('textbook-source-body');
    await page.getByRole('button', { name: '编辑分类', exact: true }).first().click();
    const title = page.locator('.textbook-edit').getByLabel('标题', { exact: true });
    await title.fill('教师填写保持（隔离冲突）');
    const gradeLines = await page
      .locator('.textbook-grade-options .textbook-check')
      .evaluateAll((labels) =>
        labels.map((label) => {
          const text = Array.from(label.childNodes).find(
            (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
          );
          if (!text) return 0;
          const range = document.createRange();
          range.selectNodeContents(text);
          return range.getClientRects().length;
        }),
      );
    expect(gradeLines).toEqual([1]);
    const fieldHeights = await page
      .locator(
        '.textbook-edit .textbook-metadata input:not([type="checkbox"]), .textbook-edit .textbook-metadata select',
      )
      .evaluateAll((fields) => fields.map((field) => field.getBoundingClientRect().height));
    expect(fieldHeights.length).toBeGreaterThan(1);
    expect(Math.max(...fieldHeights) - Math.min(...fieldHeights)).toBeLessThanOrEqual(1);
    await page.getByRole('button', { name: '保存分类', exact: true }).click();
    await expect(page.locator('.textbook-edit').getByRole('alert')).toContainText('冲突');
    await expect(title).toHaveValue('教师填写保持（隔离冲突）');
    await capture('textbook-conflict');
    await title.scrollIntoViewIfNeeded();
    await capture('textbook-conflict-input');
  });
}
