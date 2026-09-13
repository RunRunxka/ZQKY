/** 供应商标识：优先复用仓库已有图标（public/provider-icons），缺失时用中性首字母。 */

export interface ProviderMark {
  /** public/provider-icons 下的文件名（不含扩展名）；缺失则用首字母 */
  icon?: string;
  /** 首字母回退 */
  initials: string;
}

const MARKS: Record<string, ProviderMark> = {
  custom: { initials: '自' },
  custom_anthropic: { initials: '自' },
  azure_openai: { icon: 'azure-color', initials: 'Az' },
  openrouter: { icon: 'openrouter', initials: 'OR' },
  orcarouter: { initials: 'Or' },
  edenai: { initials: 'Ed' },
  aihubmix: { icon: 'aihubmix-color', initials: 'Ai' },
  siliconflow: { icon: 'siliconcloud-color', initials: 'Si' },
  novita: { initials: 'No' },
  atlascloud: { initials: 'At' },
  volcengine: { icon: 'volcengine-color', initials: 'Vo' },
  volcengine_coding_plan: { icon: 'volcengine-color', initials: 'Vo' },
  byteplus: { icon: 'bytedance-color', initials: 'By' },
  byteplus_coding_plan: { icon: 'bytedance-color', initials: 'By' },
  anthropic: { icon: 'anthropic', initials: 'An' },
  openai: { icon: 'openai', initials: 'AI' },
  openai_codex: { icon: 'openai', initials: 'Cx' },
  github_copilot: { icon: 'githubcopilot', initials: 'GH' },
  codebuddy: { initials: 'CB' },
  deepseek: { icon: 'deepseek-color', initials: 'DS' },
  gemini: { icon: 'gemini-color', initials: 'Ge' },
  zhipu: { icon: 'zhipu-color', initials: 'GL' },
  dashscope: { icon: 'qwen-color', initials: 'QW' },
  moonshot: { icon: 'moonshot', initials: 'Ki' },
  minimax: { icon: 'minimax-color', initials: 'MM' },
  minimax_anthropic: { icon: 'minimax-color', initials: 'MM' },
  mistral: { icon: 'mistral-color', initials: 'Mi' },
  stepfun: { icon: 'stepfun-color', initials: 'St' },
  xiaomi_mimo: { icon: 'xiaomimimo', initials: 'Mi' },
  groq: { icon: 'groq', initials: 'Gq' },
  qianfan: { icon: 'baiducloud-color', initials: 'QF' },
  vllm: { icon: 'vllm-color', initials: 'vL' },
  ollama: { icon: 'ollama', initials: 'Ol' },
  lm_studio: { icon: 'lmstudio', initials: 'LM' },
  llama_cpp: { initials: 'lc' },
  lemonade: { initials: 'Le' },
  ovms: { initials: 'OV' },
  nvidia_nim: { icon: 'nvidia-color', initials: 'NV' },
};

export function providerMark(providerId: string | null | undefined, label?: string | null): ProviderMark {
  if (providerId) {
    const mark = MARKS[providerId];
    if (mark) return mark;
  }
  const source = (label ?? providerId ?? '').trim();
  return { initials: source ? source.slice(0, 2) : '?' };
}
