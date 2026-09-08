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
  const response = await fetch('/templates/lesson-plan-template.docx');
  if (!response.ok) throw Error('模板加载失败，请刷新后重试');
  const doc = new Docxtemplater(new PizZip(await response.arrayBuffer()), {
    paragraphLoop: true,
    linebreaks: true,
  });
  doc.render(flattenForDocx(data));
  return doc
    .getZip()
    .generate({
      type: 'blob',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
}
export async function exportDocx(data: LessonPlanData) {
  download(await buildDocx(data), `教案-${safeName(data.title)}.docx`);
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
