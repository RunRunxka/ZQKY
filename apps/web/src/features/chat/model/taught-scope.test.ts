import { afterEach, describe, expect, it, vi } from 'vitest';
import { describeSelection, isSelectionUsable, loadTaughtScope } from '@/services/taught-scope';
import type { TextbookTaxonomy } from '@/contracts/textbook';

const taxonomy: TextbookTaxonomy = {
  stages: [{ id: 'st-1', label: '高中' }],
  grades: [{ id: 'g1', label: '高一', stageId: 'st-1' }],
  subjects: [{ id: 's1', label: '数学' }],
  editions: [{ id: 'e1', label: '人教A版' }],
};

afterEach(() => vi.unstubAllGlobals());

describe('任教范围读取与展示', () => {
  it('按字典标签渲染可读文案；字典缺失时省略该段，不猜造名称', () => {
    const selection = {
      gradeId: 'g1',
      subjectId: 's1',
      editionId: 'e1',
      documentIds: ['d1', 'd2', 'd3'],
    };
    expect(describeSelection(selection, taxonomy)).toBe('高一 · 数学 · 人教A版 · 3 册');
    expect(describeSelection(selection, null)).toBe('3 册');
    expect(
      describeSelection({ ...selection, subjectId: 'unknown' }, taxonomy),
    ).toBe('高一 · 人教A版 · 3 册');
    // 未保存范围不渲染成「未设置」之类的伪造文案
    expect(describeSelection(null, taxonomy)).toBeNull();
  });

  it('服务端已保存且范围就绪才是 ready；未保存是 empty，读取失败是 failed（不是空范围）', async () => {
    const selection = { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] };
    const serve = (settings: unknown, status = 200) =>
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string) =>
          url.includes('teaching-settings')
            ? status === 200
              ? Response.json(settings)
              : Response.json({ code: 'SERVICE_UNAVAILABLE', message: '教材目录未就绪。' }, { status })
            : Response.json(taxonomy),
        ),
      );

    serve({
      ownerId: 'system',
      selection,
      revision: 2,
      updatedAt: null,
      scopeReady: true,
      scopeReason: null,
    });
    const ready = await loadTaughtScope();
    expect(ready.state).toBe('ready');
    expect(ready.selection).toEqual(selection);
    expect(ready.taxonomy?.grades[0]?.label).toBe('高一');
    expect(isSelectionUsable(ready)).toBe(true);

    serve({
      ownerId: 'system',
      selection: null,
      revision: 1,
      updatedAt: null,
      scopeReady: false,
      scopeReason: '尚未保存任教范围。',
    });
    const empty = await loadTaughtScope();
    expect(empty.state).toBe('empty');
    expect(empty.selection).toBeNull();
    expect(empty.reason).toContain('尚未保存');
    expect(isSelectionUsable(empty)).toBe(false);

    serve(null, 503);
    const failed = await loadTaughtScope();
    expect(failed.state).toBe('failed');
    expect(failed.error).toContain('教材目录未就绪');
    expect(failed.selection).toBeNull();
    expect(isSelectionUsable(failed)).toBe(false);
  });

  it('字典读取失败不阻断范围本身：仍为 ready，只标注标签不可用', async () => {
    const selection = { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.includes('teaching-settings')
          ? Response.json({
              ownerId: 'system',
              selection,
              revision: 1,
              updatedAt: null,
              scopeReady: true,
              scopeReason: null,
            })
          : Response.json({ code: 'SERVICE_UNAVAILABLE', message: '字典未就绪。' }, { status: 503 }),
      ),
    );
    const scope = await loadTaughtScope();
    expect(scope.state).toBe('ready');
    expect(scope.taxonomy).toBeNull();
    expect(scope.taxonomyError).toContain('字典未就绪');
    expect(describeSelection(scope.selection, scope.taxonomy)).toBe('1 册');
  });
});
