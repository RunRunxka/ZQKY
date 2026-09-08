import type {
  FillProposal,
  FillProvider,
  LessonPlanData,
  LessonType,
  ProcessItem,
  TextField,
} from '../model/types';
const aliases: Record<string, TextField> = {
  课题: 'title',
  标题: 'title',
  总课时: 'totalLessons',
  本课题总课时: 'totalLessons',
  课时: 'currentLessonNo',
  本节课: 'currentLessonNo',
  核心素养: 'coreCompetencies',
  核心素养目标: 'coreCompetencies',
  目标: 'coreCompetencies',
  重难点: 'keyPoints',
  '教学重、难点': 'keyPoints',
  教学重点: 'keyPoints',
  教学难点: 'keyPoints',
  教学设计: 'teachingDesign',
  板书: 'teachingDesign',
  课堂练习: 'exercises',
  作业: 'exercises',
  课堂练习及作业布置: 'exercises',
  教学反思: 'reflection',
  反思: 'reflection',
};
function item(stage: string, design = '', secondary = ''): ProcessItem {
  return { id: crypto.randomUUID(), stage, design, secondary };
}
export class RuleBasedFillProvider implements FillProvider {
  id = 'rule-based';
  async parse(input: string): Promise<FillProposal> {
    const patch: Partial<LessonPlanData> = {},
      warnings: string[] = [];
    let current: TextField | undefined;
    let inProcess = false;
    const process: ProcessItem[] = [];
    const json = input.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (json) {
      try {
        const arr = JSON.parse(json[1]);
        if (!Array.isArray(arr) || arr.length > 100) throw Error();
        for (const p of arr) {
          if (
            !p ||
            typeof p.stage !== 'string' ||
            typeof p.design !== 'string' ||
            (p.secondary !== undefined && typeof p.secondary !== 'string')
          )
            throw Error();
          process.push(item(p.stage, p.design, p.secondary ?? ''));
        }
      } catch {
        warnings.push('JSON 教学过程未通过校验，请使用包含 stage、design、secondary 的数组。');
        process.length = 0;
      }
    }
    for (const line of input
      .replace(/```(?:json)?\s*[\s\S]*?```/g, '')
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)) {
      const match = line.match(/^([^:：]{1,20})[:：]\s*(.*)$/);
      const label = match?.[1].trim(),
        value = match?.[2] ?? '';
      if (label && aliases[label]) {
        current = aliases[label];
        inProcess = false;
        let val = value;
        if (current === 'keyPoints' && /重点|难点/.test(label)) val = `${label}：${value}`;
        if (current === 'totalLessons' || current === 'currentLessonNo') {
          const n = value.match(/\d+/);
          if (!n || +n[0] < 1 || +n[0] > 99) {
            warnings.push(`${label}：请输入1—99之间的数字`);
            current = undefined;
            continue;
          }
          val = n[0];
        }
        patch[current] = patch[current] ? `${patch[current]}\n${val}` : val;
        continue;
      }
      if (label === '课型') {
        inProcess = false;
        current = undefined;
        const types: LessonType[] = [];
        if (/新课/.test(value)) types.push('new');
        if (/复习/.test(value)) types.push('review');
        if (/讲评/.test(value)) types.push('exercise');
        if (/实验/.test(value)) types.push('experiment');
        if (/其他|其它/.test(value)) types.push('other');
        if (types.length) patch.lessonTypes = types;
        else warnings.push(`未识别课型：${value}`);
        continue;
      }
      if (label === '教学过程') {
        inProcess = true;
        current = undefined;
        if (!value) continue;
      }
      if (inProcess) {
        const content = label === '教学过程' ? value : line;
        const parts = content.split(/[|｜]/).map((s) => s.trim());
        if (parts.length >= 2) {
          process.push(item(parts[0], parts[1], parts.slice(2).join(' | ')));
          continue;
        }
        if (/^[一二三四五六七八九十\d]+[、.．]/.test(content)) {
          process.push(item(content));
          continue;
        }
        if (process.length) {
          process[process.length - 1].design +=
            (process[process.length - 1].design ? '\n' : '') + content;
          continue;
        }
        warnings.push(`未识别教学环节：${content}`);
        continue;
      }
      if (current && !match) {
        patch[current] = `${patch[current]}\n${line}`;
        continue;
      }
      // Conservative sentence support: only explicit title, counts and lesson type; never invent pedagogy.
      const title = line.match(/(?:课题|题目|标题)(?:是|为)\s*[《“「]?([^》”」，,。；;]+)[》”」]?/);
      const total = line.match(/(?:共|总共|总课时(?:为|是)?)\s*(\d+)\s*(?:个)?课时/);
      const no = line.match(/第\s*(\d+)\s*课时/);
      if (title) patch.title = title[1].trim();
      if (total && +total[1] > 0 && +total[1] <= 99) patch.totalLessons = total[1];
      if (no && +no[1] > 0 && +no[1] <= 99) patch.currentLessonNo = no[1];
      if (/新课/.test(line)) patch.lessonTypes = ['new'];
      warnings.push(
        `${title || total || no ? '该句仅提取明确的课题、课时或课型，请检查其余要求' : '未识别内容'}：${line}`,
      );
    }
    if (process.length) patch.process = process;
    return { patch, warnings, source: input };
  }
}
export function mergeProposal(
  data: LessonPlanData,
  patch: Partial<LessonPlanData>,
  mode: 'overwrite' | 'append',
): LessonPlanData {
  const result = { ...data, ...patch };
  if (mode === 'append') {
    for (const key of [
      'coreCompetencies',
      'keyPoints',
      'teachingDesign',
      'exercises',
      'reflection',
    ] as const) {
      if (patch[key]) result[key] = [data[key], patch[key]].filter(Boolean).join('\n');
    }
    if (patch.process) result.process = [...data.process, ...patch.process];
  }
  return result;
}
