import type { LessonPlanData } from '../model/types';
export interface PrintRow {
  id: string;
  label: string;
  main: string;
  secondary?: string;
  process?: boolean;
  continued?: boolean;
  height: number;
}
// A conservative line budget at 14px, 1.8 line-height, matching print.css.
function lines(text: string, columns: number): string[] {
  const out: string[] = [];
  const paragraphs = text.split('\n');
  for (const [index, paragraph] of paragraphs.entries()) {
    let line = '',
      width = 0;
    for (const c of paragraph) {
      const w = /[\u0000-\u00ff]/.test(c) ? 0.58 : 1;
      if (width + w > columns) {
        out.push(line);
        line = '';
        width = 0;
      }
      line += c;
      width += w;
    }
    out.push(line + (index < paragraphs.length - 1 ? '\n' : ''));
  }
  return out;
}
export function paginate(data: LessonPlanData, fontSize = 14): PrintRow[][] {
  const ratio = 14 / fontSize,
    rows: PrintRow[] = [];
  const add = (id: string, label: string, text: string, secondary?: string, process = false) => {
    const mainLines = lines(text, (process ? 29 : 37) * ratio),
      secondaryLines = secondary === undefined ? [] : lines(secondary, 5.5 * ratio);
    const count = Math.max(mainLines.length, secondaryLines.length, 1);
    const maxLines = 18;
    const heading = process ? lines(label, 29 * ratio).length * fontSize * 1.8 + 35 : 0;
    for (let start = 0; start < count; start += maxLines) {
      const n = Math.min(maxLines, count - start);
      rows.push({
        id: `${id}-${start}`,
        label,
        main: mainLines.slice(start, start + maxLines).join(''),
        secondary:
          secondary === undefined
            ? undefined
            : secondaryLines.slice(start, start + maxLines).join(''),
        process,
        continued: start > 0,
        height: Math.max(process ? 85 : 65, n * fontSize * 1.8 + 32 + heading),
      });
    }
  };
  add('core', '核心素养目标', data.coreCompetencies);
  add('key', '教学重、难点', data.keyPoints);
  add('design', '教学设计', data.teachingDesign);
  for (const p of data.process) add(p.id, p.stage, p.design, p.secondary, true);
  if (!data.process.length) add('empty-process', '教学过程', '', '', true);
  add('exercises', '课堂练习及\n作业布置', data.exercises);
  add('reflection', '教学反思', data.reflection);
  const pages: PrintRow[][] = [[]];
  let remaining = 730;
  for (const row of rows) {
    if (row.height > remaining && pages.at(-1)!.length) {
      pages.push([]);
      remaining = 835;
    }
    pages.at(-1)!.push(row);
    remaining -= row.height;
  }
  return pages;
}
