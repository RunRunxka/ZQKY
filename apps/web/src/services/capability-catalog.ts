/**
 * 业务能力目录（S2 输入区）。
 *
 * 目录内容对照参考仓库 v1.6.5 `web/features/capabilities/presentation.tsx`
 * 的 CHAT_CAPABILITIES / VISIBLE_CHAT_CAPABILITIES。**UX-PERF-CLOSEOUT v1 起移除
 * 参考的“更多能力”二级飞出层**：原先收在飞出层的三项（deep_solve / deep_research /
 * immersive_watching）在真实模式下本就不可选，属不可达产品代码，已按批次要求整体
 * 删除（目录项、飞出层、专属配置表单与样式）；`mastery_path` 为精通之路工作区自有
 * 能力、`course_study` 为课程绑定能力，都不出现在首页菜单（legacy 规则同参考）。
 *
 * 需要显式配置的能力对照 `CapabilityConfigCard` 的 ConfigurableCapability
 * （deep_question / visualize；math_animator 是 visualize 的渲染模式，不属于独立能力）。
 * 配置字段与默认值对照参考：
 * - lib/quiz-types.ts（DEFAULT_QUIZ_CONFIG）
 * - lib/visualize-types.ts（DEFAULT_VISUALIZE_CONFIG）
 *
 * 服务模式边界：真实后端当前仅支持普通对话（chat）；其余能力（含 `rag`）在真实模式
 * 为**不可选**状态，并在菜单内直接标注原因，不静默转模拟、不把请求发到普通聊天冒充成功。
 * `rag` 是 UX-PERF-CLOSEOUT v1 新增的入口占位：宿主内部 adapter 契约已就绪，但
 * `get_rag_adapter()` 恒定不可用、capability 仍为 planned，因此该模式不发请求、
 * 不返回任何检索结果。
 */

export type CapabilityConfigValue = Record<string, unknown>;

export interface CapabilityDef {
  /** 目录值；chat 能力为空字符串（同参考） */
  value: string;
  label: string;
  description: string;
  /** 发送前需在能力配置卡中显式确认（同参考 ConfigurableCapability）；缺省=false */
  needsConfig?: boolean;
  /**
   * 真实模式不可用时的行内说明。缺省「真实服务未接入」；
   * 仅当原因与「服务未接入」不同（例如规划中的 RAG 模式）时才显式给出。
   */
  unavailableNote?: string;
}

/** 首页能力菜单（顺序对照参考 catalogOrder；中文文案为智启课源表述） */
export const CHAT_CAPABILITIES: CapabilityDef[] = [
  {
    value: '',
    label: '对话',
    description: '灵活对话，可配合扩展工具',
  },
  {
    value: 'ask_questions',
    label: '追问澄清',
    description: '让模型先向你提问补全上下文',
  },
  {
    value: 'deep_question',
    label: '智能出题',
    description: '自动校验的题目生成',
    needsConfig: true,
  },
  {
    value: 'visualize',
    label: '可视化',
    description: '生成图表、示意图、页面或数学动画',
    needsConfig: true,
  },
  {
    // 取代原“更多能力”飞出层的位置：同一列表、同一行样式、同一选中语义，无二级菜单。
    value: 'rag',
    label: 'RAG 模式',
    description: '基于教材资料库的定位与讲解',
    unavailableNote: '未接入 · 规划中',
  },
];

export function getCapability(value: string): CapabilityDef {
  return CHAT_CAPABILITIES.find((cap) => cap.value === value) ?? CHAT_CAPABILITIES[0]!;
}

/** 真实模式可用的能力：当前真实后端仅支持普通对话 */
export function capabilityAvailableInReal(value: string): boolean {
  return value === '';
}

/** 能力配置表单类型（字段名对照参考 lib/*-types.ts，便于逐项核对） */

/** 智能出题（Quiz）：mode/topic/num_questions/difficulty/question_types */
export interface QuizFormConfig {
  mode: 'custom' | 'mimic';
  topic: string;
  num_questions: number;
  difficulty: string;
  /** 多选题型白名单；空 = 自动（对照参考：空列表 planner 自由选择） */
  question_types: string[];
  /** 仿题模式的试卷文件名（本地演示：仅记录文件名，无解析服务） */
  paper_name: string;
}

export const QUIZ_QUESTION_TYPE_LABELS: { value: string; label: string }[] = [
  { value: 'choice', label: '选择题' },
  { value: 'concept', label: '概念题' },
  { value: 'fill_in_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' },
  { value: 'written', label: '写作题' },
  { value: 'coding', label: '编程题' },
];

export const DEFAULT_QUIZ_CONFIG: QuizFormConfig = {
  mode: 'custom',
  topic: '',
  num_questions: 3,
  difficulty: 'auto',
  question_types: [],
  paper_name: '',
};

/** 可视化：render_mode/quality/style_hint（渲染模式对照参考 VISUALIZE_RENDER_LABELS） */
export interface VisualizeFormConfig {
  render_mode: string;
  quality: 'low' | 'medium' | 'high';
  style_hint: string;
}

export const VISUALIZE_RENDER_LABELS: { value: string; label: string }[] = [
  { value: 'auto', label: '自动' },
  { value: 'chartjs', label: 'Chart.js 图表' },
  { value: 'svg', label: 'SVG 图形' },
  { value: 'mermaid', label: 'Mermaid 图' },
  { value: 'html', label: 'HTML 页面' },
  { value: 'geogebra', label: 'GeoGebra' },
  { value: 'manim_video', label: '数学动画（视频）' },
  { value: 'manim_image', label: '分镜（图片）' },
];

export const DEFAULT_VISUALIZE_CONFIG: VisualizeFormConfig = {
  render_mode: 'auto',
  quality: 'medium',
  style_hint: '',
};

/** 深度研究表单已随“更多能力”飞出层一并移除（UX-PERF-CLOSEOUT v1） */

export interface CapabilityFormState {
  deep_question: QuizFormConfig;
  visualize: VisualizeFormConfig;
}

export function createDefaultCapabilityForms(): CapabilityFormState {
  return {
    deep_question: { ...DEFAULT_QUIZ_CONFIG },
    visualize: { ...DEFAULT_VISUALIZE_CONFIG },
  };
}

/** 配置校验（对照参考各面板的必填规则）；返回用户可读的错误列表 */
export function capabilityValidationErrors(
  value: string,
  forms: CapabilityFormState,
): string[] {
  const errors: string[] = [];
  if (value === 'deep_question') {
    const quiz = forms.deep_question;
    if (quiz.mode === 'custom' && !quiz.topic.trim())
      errors.push('出题主题不能为空。');
    if (quiz.mode === 'mimic' && !quiz.paper_name)
      errors.push('仿照试卷模式需要先上传试卷文件（当前为本地演示，仅记录文件名）。');
    if (quiz.num_questions < 1) errors.push('题目数量至少为 1。');
  }
  if (value === 'visualize') {
    const vis = forms.visualize;
    if (!vis.render_mode) errors.push('请选择渲染模式。');
    if (vis.render_mode === 'manim_video' || vis.render_mode === 'manim_image') {
      // 数学动画路由的说明在 S4 展开；配置本身无需必填
    }
  }
  return errors;
}

/** 冻结进快照的配置摘要数据（纯数据，供模拟服务与消息展示复用） */
export function capabilityConfigSnapshot(
  value: string,
  forms: CapabilityFormState,
): Record<string, unknown> | undefined {
  if (value === 'deep_question') {
    const q = forms.deep_question;
    return {
      mode: q.mode,
      topic: q.topic.trim(),
      num_questions: q.num_questions,
      difficulty: q.difficulty,
      question_types: [...q.question_types],
      paper_name: q.paper_name,
    };
  }
  if (value === 'visualize') {
    const v = forms.visualize;
    return { render_mode: v.render_mode, quality: v.quality, style_hint: v.style_hint.trim() };
  }
  return undefined;
}

/** 面向模拟回复的配置摘要：直接读取冻结的配置记录，字段缺失时如实回退 */
export function summarizeCapabilityConfig(
  value: string,
  config: Record<string, unknown> | undefined,
): string {
  const cfg = config ?? {};
  const str = (key: string): string => {
    const v = cfg[key];
    return typeof v === 'string' ? v : '';
  };
  const num = (key: string): number => {
    const v = cfg[key];
    return typeof v === 'number' && Number.isFinite(v) ? v : 0;
  };
  const list = (key: string): string[] => {
    const v = cfg[key];
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
  };
  if (value === 'deep_question') {
    const types = list('question_types').length
      ? list('question_types')
          .map((t) => QUIZ_QUESTION_TYPE_LABELS.find((x) => x.value === t)?.label ?? t)
          .join('、')
      : '自动分配题型';
    const mode = str('mode') === 'mimic' ? `仿照试卷（${str('paper_name') || '未命名'}）` : '自定义';
    const difficulty = str('difficulty') || 'auto';
    return `模式=${mode}、主题=${str('topic') || '（空）'}、题目数量=${num('num_questions') || '（未设置）'}、难度=${difficulty === 'auto' ? '自动' : difficulty}、题型=${types}`;
  }
  if (value === 'visualize') {
    const render = str('render_mode') || 'auto';
    return `渲染模式=${VISUALIZE_RENDER_LABELS.find((x) => x.value === render)?.label ?? render}、质量=${str('quality') || 'medium'}、风格提示=${str('style_hint') || '无'}`;
  }
  return '';
}
