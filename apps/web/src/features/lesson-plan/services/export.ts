import type { LessonPlanData } from '../model/types';
import { lessonTypeLabels } from '../model/types';
export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob),
    a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
export function safeName(title: string) {
  return (title.trim() || '未命名教案').replace(/[<>:"/\\|?*\x00-\x1F]/g, '_').slice(0, 70);
}
export function flattenForDocx(data: LessonPlanData) {
  const first = data.process.slice(0, 2),
    rest = data.process.slice(2);
  const design = (items: typeof first) => items.map((p) => `${p.stage}\n${p.design}`).join('\n\n');
  const secondary = (items: typeof first) =>
    items.map((p) => `${p.stage}\n${p.secondary}`).join('\n\n');
  return {
    ...data,
    lessonTypesText: Object.entries(lessonTypeLabels)
      .map(
        ([k, v]) =>
          `${data.lessonTypes.includes(k as keyof typeof lessonTypeLabels) ? '☑' : '□'}${v}${k === 'other' && data.lessonTypes.includes('other') && data.otherTypeText ? `（${data.otherTypeText}）` : ''}`,
      )
      .join('  '),
    firstDesign: design(first),
    firstSecondary: secondary(first),
    restDesign: design(rest),
    restSecondary: secondary(rest),
  };
}
export async function buildDocx(data: LessonPlanData) {
  const [{ default: PizZip }, { default: Docxtemplater }] = await Promise.all([
    import('pizzip'),
    import('docxtemplater'),
  ]);
  // C3：教学设计模板 v2（封面 + 目录 + 五大正文表，三列教学过程）；旧模板仅作回退。
  const response = await fetch('/templates/lesson-plan-template-v2.docx');
  if (!response.ok) throw Error('模板加载失败，请刷新后重试');
  const doc = new Docxtemplater(new PizZip(await response.arrayBuffer()), {
    paragraphLoop: true,
    linebreaks: true,
  });
  doc.render(flattenForDocxV2(data));
  return doc
    .getZip()
    .generate({
      type: 'blob',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
}

/** 模板 v2 字段映射：封面/目录由模板自带（导出自动补齐第 1、2 页），正文从第 3 页起与预览一致。 */
export function flattenForDocxV2(data: LessonPlanData) {
  const basic = data.basic ?? { courseName: '', teacher: '', audience: '', hours: '', teachingTime: '', location: '', chapter: '' };
  const analysis = data.analysis ?? { learning: '', textbook: '', content: '', ideological: '' };
  const strategy = data.strategy ?? { designThinking: '', teachingFlow: '', methods: '' };
  const evaluation = data.evaluation ?? { afterClassTest: '', homework: '' };
  const rows = (data.processV2 && data.processV2.length > 0)
    ? data.processV2
    : data.process.map((p) => ({
        id: p.id, phase: 'exploration' as const, phaseLabel: '', title: p.stage,
        teacherActivity: p.design, studentActivity: '', intent: p.secondary,
      }));
  return {
    title: data.title,
    courseName: basic.courseName || data.title,
    teacher: basic.teacher,
    audience: basic.audience,
    hours: basic.hours,
    teachingTime: basic.teachingTime,
    location: basic.location,
    chapter: basic.chapter,
    analysisLearning: analysis.learning,
    analysisTextbook: analysis.textbook,
    analysisContent: analysis.content,
    analysisIdeological: analysis.ideological,
    coreCompetencies: data.coreCompetencies,
    keyPoints: data.keyPoints,
    strategyDesignThinking: strategy.designThinking,
    strategyTeachingFlow: strategy.teachingFlow,
    strategyMethods: strategy.methods,
    teachingDesign: data.teachingDesign,
    processV2: rows,
    evaluationAfterClassTest: evaluation.afterClassTest,
    evaluationHomework: evaluation.homework,
    reflection: data.reflection,
  };
}
export async function exportDocx(data: LessonPlanData, sourceLabel?: string) {
  download(await buildDocx(data), `教案-${safeName(data.title)}${sourceLabel ? `-${safeName(sourceLabel)}` : ''}.docx`);
}
export async function exportPdf(title: string) {
  await document.fonts.ready;
  const old = document.title;
  document.title = `教案-${safeName(title)}`;
  const restore = () => {
    document.title = old;
    window.removeEventListener('afterprint', restore);
  };
  window.addEventListener('afterprint', restore);
  try {
    window.print();
  } catch (error) {
    restore();
    throw error;
  }
}
