/**
 * 手动录入题目的 Markdown 组装（纯函数，可单测；R4-FE 2026-10-11）。
 *
 * 题库唯一写入口是「导入草稿 → 人工校对 → 确认入库」，所以手动录入要拼成后端规则拆题
 * （`app/services/question_bank/rules.py`）可识别的 Markdown 文档：
 *
 * - 题号起始行：`1. 题干`（教师首行已带题号/中文序号时不重复加号，避免出现「1. 1.」）；
 * - 选项：每行一个，按 A/B/C… 自动编号（`A. 文本`，后端选项正则直接命中）；
 * - `答案：` / `解析：` 标注行：后端把标注段归入当前草稿。
 *
 * 题干为空返回 `null`（调用方据此拦在本地，不发无意义请求）。
 */

export const MANUAL_QUESTION_FILE_NAME = '手动录入-题目.md';

const QUESTION_START = /^(\s*[（(]\s*\d{1,3}\s*[)）]|第\s*\d{1,3}\s*题|\d{1,3}\s*[.、．)）]|[一二三四五六七八九十]{1,3}\s*[、.．])/;

const OPTION_KEYS = 'ABCDEFGH';

export interface ManualQuestionInput {
  stem: string;
  /** 每行一个选项；只对选择题使用。 */
  optionsText: string;
  answer: string;
  explanation: string;
}

export function composeManualQuestion(input: ManualQuestionInput): string | null {
  const stemLines = input.stem.replace(/\r\n?/g, '\n').split('\n');
  const firstIndex = stemLines.findIndex((line) => line.trim() !== '');
  if (firstIndex < 0) return null;

  const stem = [...stemLines];
  if (!QUESTION_START.test(stemLines[firstIndex] as string)) {
    stem[firstIndex] = `1. ${(stemLines[firstIndex] as string).trimStart()}`;
  }

  const optionLines = input.optionsText
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line !== '')
    .map((line, index) => {
      const key = OPTION_KEYS[index] ?? `选项${index + 1}`;
      return `${key}. ${line}`;
    });

  const blocks: string[] = [stem.join('\n').trim()];
  if (optionLines.length > 0) blocks.push(optionLines.join('\n'));

  const markers: string[] = [];
  const answer = input.answer.trim();
  const explanation = input.explanation.trim();
  if (answer) markers.push(`答案：${answer}`);
  if (explanation) markers.push(`解析：${explanation}`);
  if (markers.length > 0) blocks.push(markers.join('\n'));

  return `${blocks.join('\n\n')}\n`;
}
