import { describe, it, expect } from 'vitest';
import { RuleBasedFillProvider, mergeProposal } from './fill';
import { exampleData, emptyData, requirementExample } from '../model/defaults';
import { paginate } from './pagination';
import { validateData } from './drafts';
import { flattenForDocx } from './export';
import { createLessonStore } from '../model/store';
const useLessonStore = createLessonStore();
const provider = new RuleBasedFillProvider();
describe('要求填充', () => {
  it('识别中文字段、环节与作业边界', async () => {
    const r = await provider.parse(requirementExample);
    expect(r.patch.title).toBe('荷塘月色');
    expect(r.patch.process).toHaveLength(2);
    expect(r.patch.exercises).toContain('150字');
    expect(r.warnings).toEqual([]);
  });
  it('保留未识别内容并拒绝无效课时', async () => {
    const r = await provider.parse('总课时：0\n神秘字段：abc');
    expect(r.patch.totalLessons).toBeUndefined();
    expect(r.warnings).toHaveLength(2);
  });
  it('同时保留重点和难点与多行内容', async () => {
    const r = await provider.parse('教学重点：重点A\n补充内容\n教学难点：难点B');
    expect(r.patch.keyPoints).toBe('教学重点：重点A\n补充内容\n教学难点：难点B');
  });
  it('识别简单自然语言并提示剩余要求', async () => {
    const r = await provider.parse('课题为《荷塘月色》，共2课时，第1课时，安排一节新课。');
    expect(r.patch.title).toBe('荷塘月色');
    expect(r.patch.totalLessons).toBe('2');
    expect(r.warnings.length).toBeGreaterThan(0);
  });
  it('支持JSON及分节过程', async () => {
    const r = await provider.parse(
      '教学过程：\n```json\n[{"stage":"导入","design":"读课文"}]\n```',
    );
    expect(r.patch.process?.[0].design).toBe('读课文');
    const b = await provider.parse('教学过程：\n一、导入\n读课文\n二、总结\n全班交流');
    expect(b.patch.process).toHaveLength(2);
  });
  it('追加不丢失旧字段，替换仅影响识别字段', () => {
    expect(mergeProposal(exampleData, { title: '新课题' }, 'overwrite').keyPoints).toBe(
      exampleData.keyPoints,
    );
    expect(mergeProposal(exampleData, { exercises: '补充' }, 'append').exercises).toContain(
      exampleData.exercises,
    );
  });
});
describe('导出与分页', () => {
  it('长文本拆页后没有丢字', () => {
    const text = '认真阅读课文，体会景物描写与情感的关系。'.repeat(220);
    const p = paginate({ ...emptyData, coreCompetencies: text });
    expect(p.length).toBeGreaterThan(2);
    expect(
      p
        .flat()
        .filter((r) => r.id.startsWith('core'))
        .map((r) => r.main.replaceAll('\n', ''))
        .join(''),
    ).toBe(text);
  });
  it('二次备课很长时保留全部内容', () => {
    const text = '观察记录'.repeat(150);
    const p = paginate({
      ...emptyData,
      process: [{ id: 'x', stage: '过程', design: '内容', secondary: text }],
    });
    expect(
      p
        .flat()
        .filter((r) => r.process)
        .map((r) => r.secondary?.replaceAll('\n', ''))
        .join(''),
    ).toBe(text);
  });
  it('Word映射包含全部环节和二次备课', () => {
    const out = flattenForDocx(exampleData);
    for (const p of exampleData.process) {
      expect(out.firstDesign + out.restDesign).toContain(p.design);
      expect(out.firstSecondary + out.restSecondary).toContain(p.secondary);
    }
  });
});
describe('数据恢复', () => {
  it('拒绝畸形数据和重复环节ID', () => {
    expect(() => validateData({ title: 42 })).toThrow();
    expect(() =>
      validateData({ ...exampleData, process: [exampleData.process[0], exampleData.process[0]] }),
    ).toThrow();
    expect(() => validateData(exampleData)).not.toThrow();
  });
  it('撤销批量替换可重做', () => {
    const s = useLessonStore.getState();
    s.hydrate(exampleData, 0);
    s.replace(emptyData);
    s.undo();
    expect(useLessonStore.getState().data.title).toBe('荷塘月色');
    s.redo();
    expect(useLessonStore.getState().data.title).toBe('');
  });
});
