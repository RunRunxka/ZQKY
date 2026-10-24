/**
 * 预览分页：第 3 页起编号、页尾标记文案、模板四表结构、模块显隐/新增/排版对分页的影响。
 */
import { describe, expect, it } from 'vitest';
import {
  A4_HEIGHT_PX,
  FIRST_CONTENT_PAGE,
  TITLE_RESERVE_PX,
  buildPreviewBlocks,
  layoutPreview,
  pageEndLabel,
  paginateBlocks,
  sectionPageMap,
  splitReflection,
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

  it('默认布局生成模板四表的行块（基本信息在首位）', () => {
    const data = emptyLessonData();
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const ids = blocks.map((block) => block.id);
    expect(ids[0]).toBe('basic.band');
    expect(ids).toContain('analysis.band');
    expect(ids).toContain('objectives.band');
    expect(ids).toContain('strategy.band');
    expect(ids).toContain('process.head');
    expect(ids).toContain('evaluation.band');
    expect(ids).toContain('reflection.band');
    expect(ids).toContain('reflection');
  });

  it('基本信息表按模板 4 列成对排布，教学章节跨 3 列', () => {
    const data = emptyLessonData();
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const courseRow = blocks.find((block) => block.id === 'basic.courseName');
    expect(courseRow?.tableId).toBe('basic');
    expect(courseRow?.columns).toBe(4);
    expect(courseRow?.cells.map((cell) => cell.text)).toEqual(['课程名称', '', '授课对象', '']);
    const chapterRow = blocks.find((block) => block.id === 'basic.chapter');
    expect(chapterRow?.cells).toHaveLength(2);
    expect(chapterRow?.cells[1].colspan).toBe(3);
    expect(courseRow?.cells[0].role).toBe('label');
  });

  it('教学目标与策略同表：三行 vMerge + 重点/难点两行 + 策略跨 2 列', () => {
    const data = emptyLessonData();
    data.keyPoints = '教学重点：写景语言\n教学难点：体会情感';
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const group = blocks.filter((block) => block.mergeGroup === 'objectives');
    expect(group.map((block) => block.id)).toEqual([
      'objectives.knowledge',
      'objectives.ability',
      'objectives.ideological',
    ]);
    expect(group[0].groupLabel).toBe('教学目标');
    expect(group[0].cells[0].rowspan).toBe(3);
    expect(group.map((block) => block.subLabel)).toEqual(['知识目标', '能力目标', '思政目标']);

    const key = blocks.find((block) => block.id === 'objectives.key');
    const difficulty = blocks.find((block) => block.id === 'objectives.difficulty');
    expect(key?.tableId).toBe('objectives');
    expect(difficulty?.cells[1].text).toContain('体会情感');
    expect(key?.cells[1].colspan).toBe(2);

    const strategy = blocks.find((block) => block.id === 'strategy.designThinking');
    expect(strategy?.tableId).toBe('objectives');
    expect(strategy?.cells[1].colspan).toBe(2);
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
    expect(blocks[bodyIndex].cells[0].text).toBe('测试 10 分钟。');
    expect(blocks[bodyIndex].columns).toBe(2);
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

  it('教学过程按阶段插入小标题行；两行表头与 vMerge 结构符合模板', () => {
    const data = emptyLessonData();
    data.processV2 = [
      { id: 'a', phase: 'introduction', phaseLabel: '课程引入', title: '导入', teacherActivity: '教师', studentActivity: '学生', intent: '意图' },
      { id: 'b', phase: 'practice', phaseLabel: '练习巩固', title: '练习', teacherActivity: '教师', studentActivity: '学生', intent: '意图' },
    ];
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const phaseIds = blocks.filter((block) => block.kind === 'process-phase').map((block) => block.id);
    expect(phaseIds).toEqual(['process.phase.introduction:课程引入', 'process.phase.practice:练习巩固']);

    const head = blocks.find((block) => block.id === 'process.head');
    expect(head?.cells.map((cell) => cell.text)).toEqual(['教学环节', '教学活动', '设计意图']);
    expect(head?.cells[0].rowspan).toBe(2);
    expect(head?.cells[1].colspan).toBe(2);
    const sub = blocks.find((block) => block.id === 'process.head.sub');
    expect(sub?.cells.map((cell) => cell.text)).toEqual(['教师活动', '学生活动']);
    expect(head?.mergeGroup).toBe('process-header');
    expect(sub?.mergeGroup).toBe('process-header');
  });

  it('阶段标签留空时使用阶段名（与导出同口径）', () => {
    const data = emptyLessonData();
    data.processV2 = [
      { id: 'a', phase: 'warmup', phaseLabel: '', title: '导入', teacherActivity: '教师', studentActivity: '学生', intent: '意图' },
    ];
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const phase = blocks.find((block) => block.kind === 'process-phase');
    expect(phase?.label).toBe('课前热身');
  });

  it('字号变大后同一内容占用更多页面（排版进分页计算）', () => {
    const data = emptyLessonData();
    data.analysis = { learning: longText(60), textbook: longText(60), content: '', ideological: '' };
    const small = layoutPreview(data, defaultModuleLayout(), { ...DEFAULT_LESSON_STYLE, baseSize: 12 });
    const large = layoutPreview(data, defaultModuleLayout(), { ...DEFAULT_LESSON_STYLE, baseSize: 20 });
    expect(large.pages.length).toBeGreaterThanOrEqual(small.pages.length);
    expect(large.pages.length).toBeGreaterThan(1);
  });

  it('旧两列 process 有内容时映射为四列行参与分页（不丢数据）', () => {
    const data = emptyLessonData();
    data.process = [{ id: 'p1', stage: '导入', design: '教师活动', secondary: '设计意图' }];
    expect(processToV2(data)).toHaveLength(1);
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(blocks.some((block) => block.id === 'process.p1')).toBe(true);
  });

  it('评价反馈按模板四项子标题成格（（三）（四）保留标题）', () => {
    const data = emptyLessonData();
    data.evaluation = { afterClassTest: '测试结果良好', homework: '作业完成率高' };
    data.exercises = '练习册第 3 题';
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const ids = ['evaluation.afterClassTest', 'evaluation.homework', 'evaluation.afterClassSurvey', 'evaluation.supervisorFeedback'];
    const evaluation = ids.map((id) => blocks.find((block) => block.id === id));
    expect(evaluation.map((block) => block?.id)).toEqual(ids);
    expect(evaluation.every((block) => block?.tableId === 'evaluation' && block?.subRow)).toBe(true);
    const texts = evaluation.map((block) => block?.cells[0].text ?? '');
    expect(texts[0]).toContain('（一）学生课后测试情况');
    expect(texts[0]).toContain('测试结果良好');
    expect(texts[1]).toContain('（二）学生课后作业情况');
    expect(texts[1]).toContain('作业完成率高');
    expect(texts[1]).toContain('练习册第 3 题');
    expect(texts[2]).toBe('（三）学生课后调查反馈');
    expect(texts[3]).toBe('（四）督导专家课后反馈');
  });

  it('教学反思按模板三个小标题拆分', () => {
    expect(splitReflection('（一）目标达成度分析\n达成较好\n（二）教学特色与可供借鉴之处\n案例教学\n（三）教学后记\n继续改进')).toEqual({
      achievement: '达成较好',
      features: '案例教学',
      postscript: '继续改进',
    });
    const data = emptyLessonData();
    data.reflection = '整体达成度较高';
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const ids = ['reflection', 'reflection.features', 'reflection.postscript'];
    const reflection = ids.map((id) => blocks.find((block) => block.id === id));
    expect(reflection.map((block) => block?.id)).toEqual(ids);
    expect(reflection[0]?.cells[0].text).toContain('整体达成度较高');
  });

  it('教学过程为空时给出占位行（不出现无正文的空表头）', () => {
    const data = emptyLessonData();
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const emptyRow = blocks.find((block) => block.id === 'process.empty');
    expect(emptyRow?.cells[0].text).toContain('暂无教学环节');

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
      expect(last?.kind).not.toBe('custom-band');
    }
  });

  it('目标第 2/3 行按第 3 列测量，不再把正文按标签列宽放大', () => {
    const data = emptyLessonData();
    const text = longText(8);
    data.coreCompetencies = `知识：${text}\n能力：${text}\n思政：${text}`;
    const blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const knowledge = blocks.find((block) => block.id === 'objectives.knowledge')!;
    const ability = blocks.find((block) => block.id === 'objectives.ability')!;
    const ideological = blocks.find((block) => block.id === 'objectives.ideological')!;
    expect(ability.columnOffset).toBe(1);
    expect(ideological.columnOffset).toBe(1);
    // 同样 8 行文本：修复前能力/思政按 113px 宽测量，会是知识行的数倍高。
    expect(Math.abs(ability.height - knowledge.height)).toBeLessThanOrEqual(2);
    expect(Math.abs(ideological.height - knowledge.height)).toBeLessThanOrEqual(2);
    expect(ability.height).toBeLessThan(8 * 18.67 * 1.714 + 20);
  });

  it('目标三行跨页：rowspan 按本页行数，续页标签留空（与 Word vMerge 一致）且不丢字', () => {
    const data = emptyLessonData();
    const objectiveText = longText(40);
    data.coreCompetencies = `知识：${objectiveText}\n能力：${objectiveText}\n思政：${objectiveText}`;
    data.analysis = { learning: longText(20), textbook: '', content: '', ideological: '' };
    const style = normalizeStyle(DEFAULT_LESSON_STYLE);
    const pages = paginateBlocks(buildPreviewBlocks(data, defaultModuleLayout(), style), style);
    const groupPages = pages.filter((page) =>
      page.blocks.some((block) => block.mergeGroup === 'objectives'),
    );
    expect(groupPages.length).toBeGreaterThan(1);

    for (const page of pages) {
      const rows = page.blocks.filter((block) => block.mergeGroup === 'objectives');
      if (rows.length === 0) continue;
      const merged = rows[0].cells.find((cell) => cell.role === 'label' && (cell.rowspan ?? 0) > 0);
      expect(merged?.rowspan).toBe(rows.length);
      if (rows[0].id !== 'objectives.knowledge') {
        expect(rows[0].cells[0].text).toBe('');
      }
    }

    const ids = pages
      .flatMap((page) => page.blocks)
      .filter((block) => block.mergeGroup === 'objectives')
      .map((block) => block.id.replace(/~cont\d+$/, ''));
    expect(new Set(ids)).toEqual(
      new Set(['objectives.knowledge', 'objectives.ability', 'objectives.ideological']),
    );
    for (const label of ['知识', '能力', '思政']) {
      const parts = pages
        .flatMap((page) => page.blocks)
        .filter((block) => block.mergeGroup === 'objectives' && block.subLabel === `${label}目标`);
      const joined = parts.map((block) => block.cells.at(-1)?.text ?? '').join('');
      expect(joined.replace(/\s+/g, '')).toBe(objectiveText.replace(/\s+/g, ''));
    }

    const capacity = A4_HEIGHT_PX - style.pageMargin * 2;
    for (const page of pages.slice(0, -1)) {
      const used = page.blocks.reduce((sum, block) => sum + block.height + block.gapBefore, 0);
      const limit = page.number === FIRST_CONTENT_PAGE ? capacity - TITLE_RESERVE_PX : capacity;
      expect(used).toBeGreaterThan(limit * 0.6);
    }
  });

  it('教学目标 other 文本与导出同口径：无标签进知识行，混合重点行进思政行', () => {
    const data = emptyLessonData();
    data.coreCompetencies = '一段没有标签的目标';
    let blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(blocks.find((block) => block.id === 'objectives.knowledge')?.cells[2].text).toBe(
      '一段没有标签的目标',
    );

    data.coreCompetencies = '知识：甲\n教学重点：乙';
    blocks = buildPreviewBlocks(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    expect(blocks.find((block) => block.id === 'objectives.ideological')?.cells[1].text).toContain(
      '教学重点：乙',
    );
  });

  it('sectionPageMap 给出正文页码（从 1 起）', () => {
    const data = emptyLessonData();
    data.analysis = { learning: longText(60), textbook: longText(60), content: '', ideological: '' };
    const layout = layoutPreview(data, defaultModuleLayout(), DEFAULT_LESSON_STYLE);
    const map = sectionPageMap(layout.pages);
    expect(map.basic).toBe(1);
    expect(map.analysis).toBeGreaterThanOrEqual(1);
    expect(map.reflection).toBeGreaterThanOrEqual(map.analysis);
  });

  it('超长行跨页拆分：本页填满，续行在下一页且不丢字', () => {
    const data = emptyLessonData();
    const text = longText(300);
    data.analysis = { learning: text, textbook: '', content: '', ideological: '' };
    const style = normalizeStyle(DEFAULT_LESSON_STYLE);
    const layout = layoutPreview(data, defaultModuleLayout(), style);
    expect(layout.pages.length).toBeGreaterThan(2);

    const capacity = A4_HEIGHT_PX - style.pageMargin * 2;
    const titleReserve = TITLE_RESERVE_PX;
    for (const page of layout.pages) {
      const used = page.blocks.reduce((sum, block) => sum + block.height + block.gapBefore, 0);
      const limit = page.number === FIRST_CONTENT_PAGE ? capacity - titleReserve : capacity;
      expect(used).toBeLessThanOrEqual(limit + 2);
    }

    const parts = layout.pages
      .flatMap((page) => page.blocks)
      .filter((block) => block.id === 'analysis.learning' || block.id.startsWith('analysis.learning~cont'));
    expect(parts.length).toBeGreaterThan(2);
    expect(parts.some((block) => block.continuation)).toBe(true);
    const joined = parts.map((block) => block.cells[1]?.text ?? '').join('');
    expect(joined.replace(/\s+/g, '')).toBe(text.replace(/\s+/g, ''));
  });

  it('长行拆分后本页利用率 ≥ 90%，续行保留候选 id、标签只在首段', () => {
    const data = emptyLessonData();
    data.analysis = { learning: longText(120), textbook: '', content: '', ideological: '' };
    const style = normalizeStyle(DEFAULT_LESSON_STYLE);
    const layout = layoutPreview(data, defaultModuleLayout(), style);
    const first = layout.pages[0];
    const capacity = A4_HEIGHT_PX - style.pageMargin * 2;
    const titleReserve = TITLE_RESERVE_PX;
    const used = first.blocks.reduce((sum, block) => sum + block.height + block.gapBefore, 0);
    expect(used).toBeGreaterThan((capacity - titleReserve) * 0.9);

    const parts = layout.pages
      .flatMap((page) => page.blocks)
      .filter((block) => block.id === 'analysis.learning' || block.id.startsWith('analysis.learning~cont'));
    expect(parts.length).toBeGreaterThan(1);
    const [head, tail] = parts;
    expect(head.cells[0].text.replace(/\s+/g, '')).toBe('学情分析');
    expect(tail.cells[0].text).toBe('');
    expect(tail.cells[1].candidateIds).toContain('analysis.learning');
    expect(tail.continuation).toBe(true);
  });

  it('可拆行不会因为整行放不下而留下整段空白', () => {
    const data = emptyLessonData();
    data.analysis = { learning: longText(60), textbook: '', content: '', ideological: '' };
    data.reflection = longText(20);
    const style = normalizeStyle(DEFAULT_LESSON_STYLE);
    const pages = paginateBlocks(buildPreviewBlocks(data, defaultModuleLayout(), style), style);
    const capacity = A4_HEIGHT_PX - style.pageMargin * 2;
    for (const page of pages) {
      const used = page.blocks.reduce((sum, block) => sum + block.height + block.gapBefore, 0);
      const limit = page.number === FIRST_CONTENT_PAGE
        ? capacity - TITLE_RESERVE_PX
        : capacity;
      // 允许不可拆的标题/表头/短行留下少量空间，但不应出现半页空白。
      expect(used).toBeGreaterThan(limit * 0.75);
    }
  });

  it('分页结果为空时也给出一张空纸（页码仍从 3 开始）', () => {
    const pages = paginateBlocks([], DEFAULT_LESSON_STYLE);
    expect(pages).toHaveLength(1);
    expect(pages[0].number).toBe(FIRST_CONTENT_PAGE);
  });
});
