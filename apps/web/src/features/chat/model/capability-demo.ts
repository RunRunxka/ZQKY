/**
 * S4 能力模拟的确定性演示数据生成器。
 *
 * 对照参考 v1.6.5 的数据结构（字段名逐项对齐，便于复刻核对）：
 * - 题目：`web/lib/quiz-types.ts` 的 QuizQuestion
 * （question_id/question/question_type/options/correct_answer/explanation/difficulty）
 * - 研究：报告 markdown（`# 标题` + `## n. 章节`，引用标识 CIT-x-x，
 *   见 `web/lib/deep-research-report.ts`）+ 子问题（OutlineItem 语义）
 * - 可视化：render_mode 分支（chartjs/svg/mermaid/html/geogebra/manim），
 *   审查结果对照 MathAnimatorResult.render.visual_review 的形态
 *
 * 全部内容为本地演示：不捏造真实知识点，题干/资料均带演示标识；
 * 不访问网络、不执行 Manim——媒体产物为明确标识的示意内容。
 */

export type QuizArtifactQuestionType =
  | 'choice'
  | 'concept'
  | 'fill_in_blank'
  | 'short_answer'
  | 'written'
  | 'coding';

/** 对照参考 QuizQuestion 的题目结构（S4 模拟产物 quiz.data.questions[]） */
export interface QuizArtifactQuestion {
  question_id: string;
  question: string;
  question_type: QuizArtifactQuestionType;
  options?: Record<string, string>;
  correct_answer: string;
  explanation: string;
  difficulty: string;
}

/** 对照参考研究引用的条目形态（citation_id = CIT-x-x） */
export interface ResearchCitation {
  citation_id: string;
  title: string;
  snippet: string;
}

/** 研究报告产物 data（S4；S5 业务页复用同一结构） */
export interface ReportArtifactData {
  mode: string;
  depth: string;
  subtopics: string[];
  citations: ResearchCitation[];
}

const TYPE_LABELS: Record<QuizArtifactQuestionType, string> = {
  choice: '选择题',
  concept: '概念题',
  fill_in_blank: '填空题',
  short_answer: '简答题',
  written: '写作题',
  coding: '编程题',
};

export function quizTypeLabel(type: QuizArtifactQuestionType): string {
  return TYPE_LABELS[type];
}

/** 按配置确定性分配题型（白名单内轮转；空白名单=自动循环） */
export function planQuestionTypes(count: number, whitelist: string[]): QuizArtifactQuestionType[] {
  const pool: QuizArtifactQuestionType[] = whitelist.filter((t): t is QuizArtifactQuestionType =>
    (Object.keys(TYPE_LABELS) as string[]).includes(t),
  );
  const effective = pool.length > 0 ? pool : (['choice', 'concept', 'fill_in_blank', 'short_answer'] as const);
  return Array.from({ length: count }, (_, i) => effective[i % effective.length]!);
}

const CHOICE_KEYS = ['A', 'B', 'C', 'D'] as const;

/** 生成一道确定性演示题（内容为演示占位，不捏造真实知识点） */
export function makeDemoQuestion(
  index: number,
  topic: string,
  type: QuizArtifactQuestionType,
  difficulty: string,
): QuizArtifactQuestion {
  const n = index + 1;
  const subject = topic || '演示主题';
  const base: QuizArtifactQuestion = {
    question_id: `q-${n}`,
    question: `【演示】第 ${n} 题：围绕「${subject}」的${TYPE_LABELS[type]}题干（本地演示内容，不用于真实测评）。`,
    question_type: type,
    correct_answer: '',
    explanation: `【演示解析】本题考查「${subject}」的核心概念辨析。完整题目内容在真实服务接入后由模型生成，当前为结构演示。`,
    difficulty,
  };
  if (type === 'choice') {
    base.options = {
      A: `选项 A（关于 ${subject} 的表述一）`,
      B: `选项 B（关于 ${subject} 的表述二）`,
      C: `选项 C（关于 ${subject} 的表述三）`,
      D: `选项 D（与 ${subject} 无关的干扰项）`,
    };
    base.correct_answer = 'A';
  } else if (type === 'concept') {
    base.correct_answer = `【演示】「${subject}」的概念要点：定义、特征与常见误区（演示参考答案）。`;
  } else if (type === 'fill_in_blank') {
    base.question = `【演示】第 ${n} 题：请补全关于「${subject}」的关键表述：______（本地演示题干）。`;
    base.correct_answer = `【演示】参考答案：与「${subject}」对应的关键术语。`;
  } else if (type === 'short_answer') {
    base.correct_answer = `【演示】参考答案要点：围绕「${subject}」从原因、过程、影响三方面作答。`;
  } else if (type === 'written') {
    base.correct_answer = `【演示】写作提示：围绕「${subject}」立意，结构建议引论—本论—结论。`;
  } else {
    base.correct_answer = `【演示】参考实现思路：用函数封装「${subject}」的核心计算，边界条件单独处理。`;
  }
  return base;
}

/** 题目数组的 markdown 序列化（quiz 产物的 content：复制/下载与结构同源） */
export function quizQuestionsToMarkdown(
  topic: string,
  questions: QuizArtifactQuestion[],
): string {
  const lines: string[] = [`# 出题结果（模拟）`, '', `主题：${topic || '（未填）'}`, ''];
  questions.forEach((q, i) => {
    lines.push(`## 第 ${i + 1} 题 · ${quizTypeLabel(q.question_type)}${q.difficulty ? ` · 难度 ${q.difficulty}` : ''}`);
    lines.push('', q.question, '');
    if (q.options) {
      for (const key of CHOICE_KEYS) {
        if (q.options[key]) lines.push(`- ${key}. ${q.options[key]}`);
      }
      lines.push('');
    }
    lines.push(`**参考答案**：${q.correct_answer}`, '', `**解析**：${q.explanation}`, '');
  });
  lines.push('> 本产物为本地模拟生成，题干与解析均为演示内容，不用于真实测评。');
  return lines.join('\n');
}

/** 研究子问题（确定性；manual 深度用配置数量） */
export function makeResearchSubtopics(question: string, count: number): string[] {
  const subject = question.trim() || '演示研究主题';
  const angles = ['是什么（定义与边界）', '为什么（成因与机制）', '怎么样（现状与案例）', '怎么做（方法与路径）', '谁相关（主体与影响面）', '有何风险（局限与反驳）'];
  return Array.from({ length: count }, (_, i) => `子问题 ${i + 1}：${subject}——${angles[i % angles.length]!}`);
}

/** 研究引用（本地演示资料；CIT-x-x 对照参考 citation_id 格式） */
export function makeResearchCitations(subtopics: string[]): ResearchCitation[] {
  return subtopics.map((topic, i) => ({
    citation_id: `CIT-${i + 1}-1`,
    title: `演示资料 ${i + 1}：${topic.slice(0, 18)}…`,
    snippet: `【演示资料】关于「${topic}」的本地演示摘录。不访问真实网络与检索服务，仅用于引用定位与报告结构演示。`,
  }));
}

/** 研究报告 markdown（对照参考结构：标题 + 编号章节 + 结论 + 引用列表） */
export function researchReportToMarkdown(
  question: string,
  modeLabel: string,
  subtopics: string[],
  citations: ResearchCitation[],
): string {
  const subject = question.trim() || '演示研究主题';
  const lines: string[] = [
    `# 研究报告（模拟）：${subject}`,
    '',
    `产出类型：${modeLabel}（本地模拟，资料为演示内容）`,
    '',
    '## 1. 引言',
    '',
    `本报告围绕「${subject}」展开。以下分析基于本地演示资料，不捏造真实检索结果。`,
    '',
  ];
  subtopics.forEach((topic, i) => {
    const cit = citations[i];
    lines.push(`## ${i + 2}. ${topic}`, '', `【演示分析】围绕该子问题的结构与要点展开（本地演示内容）。${cit ? `（${cit.citation_id}）` : ''}`, '');
  });
  lines.push(`## ${subtopics.length + 2}. 结论`, '', '【演示结论】综合上述子问题，形成对主题的阶段认识（演示占位）。', '');
  if (citations.length) {
    lines.push('## 引用与资料', '', ...citations.map((c) => `- ${c.citation_id} ${c.title}：${c.snippet}`), '');
  }
  return lines.join('\n');
}
