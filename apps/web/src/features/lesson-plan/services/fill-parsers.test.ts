/** 生成流文本 → 表格字段（逐格）解析：识别标签、教学过程行、未识别行的如实保留。 */
import { describe, expect, it } from 'vitest';
import { applyFillToData, mergeCandidateData, parseModuleText } from './fill-parsers';
import { emptyLessonData } from '../model/lesson-data';
import { readObjectives } from '../model/objectives';

describe('parseModuleText', () => {
  it('教学分析：按【小节】标签逐格填充；标签前的内容进首字段、标签后的续行归当前小节', () => {
    const text = ['学生对通感句不熟悉。', '【学情分析】需要例子。', '【教材分析】本单元以写景散文为主。', '后续说明。'].join('\n');
    const result = parseModuleText('analysis', text);
    expect(result.fields.map((field) => field.field)).toEqual([
      'analysis.learning',
      'analysis.textbook',
    ]);
    expect(result.fields[0].value).toBe('学生对通感句不熟悉。\n需要例子。');
    expect(result.fields[1].value).toBe('本单元以写景散文为主。\n后续说明。');
    expect(result.unparsed).toEqual([]);
  });

  it('教学目标：三行与重点难点分别落到对应字段', () => {
    const text = '知识：梳理游踪\n能力：赏析语言\n思政：体会情怀\n教学重点：通感\n教学难点：情感层次';
    const result = parseModuleText('objectives', text);
    const fields = Object.fromEntries(result.fields.map((field) => [field.field, field.value]));
    expect(fields['objectives.knowledge']).toBe('梳理游踪');
    expect(fields['objectives.ability']).toBe('赏析语言');
    expect(fields['objectives.ideological']).toBe('体会情怀');
    expect(fields['objectives.keyPoints']).toBe('教学重点：通感\n教学难点：情感层次');
  });

  it('教学过程：竖线分行成三列 + 阶段小标题行（新阶段标签切换分组）', () => {
    const text = [
      '【课程引入】',
      '情境导入 | 展示画面 | 交流初读感受 | 唤起体验',
      '【深入研讨】',
      '小组讨论 | 巡视指导 | 品读语句 | 突破难点',
      '没有标签的孤行',
    ].join('\n');
    const result = parseModuleText('process', text);
    expect(result.processRows).toHaveLength(3);
    expect(result.processRows[0]).toMatchObject({
      phaseLabel: '课程引入',
      phase: 'introduction',
      title: '情境导入',
      teacherActivity: '展示画面',
      studentActivity: '交流初读感受',
      intent: '唤起体验',
    });
    expect(result.processRows[1]).toMatchObject({ phaseLabel: '深入研讨', phase: 'exploration' });
    expect(result.processRows[2]).toMatchObject({ title: '没有标签的孤行', teacherActivity: '' });
    expect(result.unparsed).toEqual([]);
  });

  it('没有阶段标签时按环节名推断阶段，且不编造阶段小标题', () => {
    const result = parseModuleText('process', '总结提升 | 归纳方法 | 自评互评 | 形成结构化认识');
    expect(result.processRows[0]).toMatchObject({ phase: 'conclusion', phaseLabel: '' });
  });

  it('评价反馈与反思：标签/纯文本都落到字段', () => {
    const evaluation = parseModuleText('evaluation', '【课后测试情况】均分 82。\n【作业情况】交齐。');
    expect(evaluation.fields.map((field) => field.field)).toEqual([
      'evaluation.afterClassTest',
      'evaluation.homework',
    ]);
    const reflection = parseModuleText('reflection', '目标基本达成，下一次压缩讲授时间。');
    expect(reflection.fields[0]).toMatchObject({ field: 'reflection' });
  });

  it('未知模块键：整段文本进 unparsed，不伪造字段', () => {
    const result = parseModuleText('unknown-key', '随便一段');
    expect(result.fields).toHaveLength(0);
    expect(result.unparsed).toEqual(['随便一段']);
  });
});

describe('applyFillToData / mergeCandidateData', () => {
  it('只覆盖解析到的字段，未覆盖字段保持原样（候选不破坏草稿）', () => {
    const data = emptyLessonData();
    data.title = '荷塘月色';
    data.reflection = '原有反思';
    const results = [parseModuleText('analysis', '【学情分析】新学情')];
    const next = applyFillToData(data, results);
    expect(next.analysis?.learning).toBe('新学情');
    expect(next.reflection).toBe('原有反思');
    expect(data.analysis?.learning).toBe('');
  });

  it('目标字段经 codec 写回，能被 readObjectives 读回', () => {
    const data = emptyLessonData();
    const results = [parseModuleText('objectives', '知识：A\n能力：B')];
    const next = applyFillToData(data, results);
    const view = readObjectives(next.coreCompetencies);
    expect(view.rows).toMatchObject({ knowledge: 'A', ability: 'B' });
  });

  it('mergeCandidateData 给出的 filledFields 与预览行 id 一致', () => {
    const data = emptyLessonData();
    const results = [parseModuleText('process', '导入 | 教师 | 学生 | 意图')];
    const merged = mergeCandidateData(data, results);
    expect(merged.filledFields.has('process')).toBe(true);
    expect(merged.data.processV2).toHaveLength(1);
    expect(data.processV2).toHaveLength(0);
  });
});
