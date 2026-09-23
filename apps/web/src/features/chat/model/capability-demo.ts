/**
 * S4 能力模拟的确定性演示数据生成器。
 *
 * 对照参考 v1.6.5 的数据结构（字段名逐项对齐，便于复刻核对）：
 * - 题目：`web/lib/quiz-types.ts` 的 QuizQuestion
 * （question_id/question/question_type/options/correct_answer/explanation/difficulty）
 * - 研究：报告 markdown（`# 标题` + `## n. 章节`，引用标识 CIT-x-x）保留为**渲染兼容类型**
 *   （旧会话已保存的 report 产物仍可展示）；生成器随“更多能力”一并移除
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
