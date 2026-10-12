/**
 * 预览分页：第 3 页起编号、页尾标记文案、模块显隐/新增/排版对分页的影响。
 */
import { describe, expect, it } from 'vitest';
import {
  A4_HEIGHT_PX,
  FIRST_CONTENT_PAGE,
  buildPreviewBlocks,
  layoutPreview,
  pageEndLabel,
  paginateBlocks,
} from './pagination';
import { emptyLessonData, processToV2 } from '../model/lesson-data';
import { DEFAULT_LESSON_STYLE, defaultModuleLayout, normalizeStyle } from '../model/modules';

function longText(lines: number): string {
  return Array.from({ length: lines }, (_, index) => `第 ${index + 1} 行内容用于撑高分页。`).join('\n');
}

describe('预览分页', () => {
  it('第一张内容纸的页码是 3（封面 1 / 目录 2 不预览）', () => {
    const data = emptyLessonData();
    const layout = layoutPreview(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(layout.pages[0].number).toBe(FIRST_CONTENT_PAGE);
    expect(pageEndLabel(layout.pages[0].number)).toBe('第 3 页结束');
  });

  it('默认布局生成七张内容表的行块（基本信息在首位）', () => {
    const data = emptyLessonData();
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const ids = blocks.map((block) => block.id);
    expect(ids[0]).toBe('basic.band');
    expect(ids).toContain('analysis.band');
    expect(ids).toContain('process.head');
    expect(ids).toContain('reflection');
  });

  it('新增自定义模块实时追加单表（band + 正文行）', () => {
    const data = emptyLessonData();
    const modules = [
      ...defaultModuleLayout(),
      { id: 'custom-1', kind: 'custom' as const, label: '课前测试安排', hidden: false, body: '测试 10 分钟。' },
    ];
    const blocks = buildPreviewBlocks(data, modules, DEFAULT_LESSON_STYLE);
    const bandIndex = blocks.findIndex((block) => block.id === 'custom-1.band');
    const bodyIndex = blocks.findIndex((block) => block.id === 'custom-1.body');
    expect(bandIndex).toBeGreaterThan(-1);
    expect(bodyIndex).toBe(bandIndex + 1);
    expect(blocks[bodyIndex].cells[0]).toBe('测试 10 分钟。');
  });

  it('隐藏模块后其行块消失（教学过程隐藏则表头也不出现）', () => {
    const data = emptyLessonData();
    const modules = defaultModuleLayout().map((entry) =>
      entry.id === 'process' ? { ...entry, hidden: true } : entry,
    );
    const blocks = buildPreviewBlocks(data, modules, DEFAULT_LESSON_STYLE);
    expect(blocks.some((block) => block.id.startsWith('process.'))).toBe(false);
    expect(blocks.some((block) => block.moduleId === 'process')).toBe(false);
  });

  it('内容足够长时按内容流分页，页码连续递增', () => {
    const data = emptyLessonData();
    data.analysis = {
      learning: longText(40),
      textbook: longText(40),
      content: longText(40),
      ideological: longText(20),
    };
    data.reflection = longText(30);
    const layout = layoutPreview(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(layout.pages.length).toBeGreaterThan(1);
    expect(layout.pages.map((page) => page.number)).toEqual(
      layout.pages.map((_, index) => FIRST_CONTENT_PAGE + index),
    );
    expect(pageEndLabel(layout.pages.at(-1)!.number)).toBe(`第 ${FIRST_CONTENT_PAGE + layout.pages.length - 1} 页结束`);
  });

  it('超长单块不会造成死循环（与页面可用高度无关，仍能收敛出页）', () => {
    const style = normalizeStyle(DEFAULT_LESSON_STYLE);
    expect(A4_HEIGHT_PX - style.pageMargin * 2).toBeGreaterThan(0);
    const data = emptyLessonData();
    data.reflection = longText(400);
    const layout = layoutPreview(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(layout.pages.length).toBeGreaterThanOrEqual(1);
  });

  it('教学过程按阶段插入小标题行；阶段标签不同的相邻行各自成组', () => {
    const data = emptyLessonData();
    data.processV2 = [
      { id: 'a', phase: 'introduction', phaseLabel: '课程引入', title: '导入', teacherActivity: '教师', studentActivity: '学生', intent: '意图' },
      { id: 'b', phase: 'practice', phaseLabel: '练习巩固', title: '练习', teacherActivity: '教师', studentActivity: '学生', intent: '意图' },
    ];
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const phaseIds = blocks.filter((block) => block.kind === 'process-phase').map((block) => block.id);
    expect(phaseIds).toEqual(['process.phase.introduction:课程引入', 'process.phase.practice:练习巩固']);
    expect(blocks.find((block) => block.id === 'process.head')?.cells).toEqual([
      '教学环节',
      '教师活动',
      '学生活动',
      '设计意图',
    ]);
  });

  it('字号变大后同一内容占用更多页面（排版进分页计算）', () => {
    const data = emptyLessonData();
    data.analysis = { learning: longText(60), textbook: longText(60), content: '', ideological: '' };
    const small = layoutPreview(data, defaultModuleLayout(), { ...DEFAULT_LESSON_STYLE, baseSize: 12 });
    const large = layoutPreview(data, defaultModuleLayout(), { ...DEFAULT_LESSON_STYLE, baseSize: 20 });
    expect(large.pages.length).toBeGreaterThanOrEqual(small.pages.length);
    expect(large.pages.length).toBeGreaterThan(1);
  });

  it('旧两列 process 有内容时映射为三列行参与分页（不丢数据）', () => {
    const data = emptyLessonData();
    data.process = [{ id: 'p1', stage: '导入', design: '教师活动', secondary: '设计意图' }];
    expect(processToV2(data)).toHaveLength(1);
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(blocks.some((block) => block.id === 'process.p1')).toBe(true);
  });

  it('教学目标三行标出同一 vMerge 组；重点难点只在有内容时出现', () => {
    const data = emptyLessonData();
    const empty = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const merged = empty.filter((block) => block.mergeGroup === 'objectives');
    expect(merged.map((block) => block.id)).toEqual([
      'objectives.knowledge',
      'objectives.ability',
      'objectives.ideological',
    ]);
    expect(merged[0].groupLabel).toBe('教学目标');
    expect(merged.map((block) => block.subLabel)).toEqual(['知识', '能力', '思政']);
    expect(empty.some((block) => block.id === 'objectives.keyPoints')).toBe(false);

    data.keyPoints = '教学重点：写景语言';
    const withKeyPoints = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(withKeyPoints.some((block) => block.id === 'objectives.keyPoints')).toBe(true);
  });

  it('教学过程为空时给出占位行（不出现无正文的空表头）', () => {
    const data = emptyLessonData();
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const emptyRow = blocks.find((block) => block.id === 'process.empty');
    expect(emptyRow?.cells[0]).toContain('暂无教学环节');

    data.processV2 = [
      { id: 'r1', phase: 'introduction', phaseLabel: '', title: '导入', teacherActivity: 'A', studentActivity: 'B', intent: 'C' },
    ];
    const filled = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(filled.some((block) => block.id === 'process.empty')).toBe(false);
  });

  it('模块标题不留在页尾：band 永远与它后面的行同页', () => {
    const data = emptyLessonData();
    // 先撑满一页，再让下一个模块标题恰好落在页尾。
    data.analysis = { learning: longText(30), textbook: '', content: '', ideological: '' };
    data.reflection = longText(3);
    const pages = paginateBlocks(buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE), DEFAULT_LESSON_STYLE);
    for (const page of pages) {
      const last = page.blocks.at(-1);
      expect(last?.kind).not.toBe('band');
    }
  });

  it('分页结果为空时也给出一张空纸（页码仍从 3 开始）', () => {
    const pages = paginateBlocks([], DEFAULT_LESSON_STYLE);
    expect(pages).toHaveLength(1);
    expect(pages[0].number).toBe(FIRST_CONTENT_PAGE);
  });
});
