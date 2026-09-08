import { describe, expect, it } from 'vitest';
import {
  CHAT_CAPABILITIES,
  capabilityAvailableInReal,
  capabilityConfigSnapshot,
  capabilityValidationErrors,
  createDefaultCapabilityForms,
  getCapability,
  summarizeCapabilityConfig,
} from './capability-catalog';

describe('能力目录（对照参考 v1.6.5 capability 目录）', () => {
  it('主列表为常用能力、次要能力收进“更多能力”，隐藏能力不出现在首页菜单', () => {
    const primary = CHAT_CAPABILITIES.filter((cap) => !cap.secondary).map((cap) => cap.value);
    const secondary = CHAT_CAPABILITIES.filter((cap) => cap.secondary).map((cap) => cap.value);
    // 顺序对照参考 catalogOrder：chat → ask_questions → deep_question → visualize；
    // 次要：deep_solve / deep_research / immersive_watching
    expect(primary).toEqual(['', 'ask_questions', 'deep_question', 'visualize']);
    expect(secondary).toEqual(['deep_solve', 'deep_research', 'immersive_watching']);
    // mastery_path / course_study 为工作区自有能力，不进首页菜单（参考 legacy/隐藏规则）
    expect(CHAT_CAPABILITIES.map((cap) => cap.value)).not.toContain('mastery_path');
    expect(CHAT_CAPABILITIES.map((cap) => cap.value)).not.toContain('course_study');
  });

  it('needsConfig 仅出题/可视化/研究需要配置确认；未知值回退对话', () => {
    expect(getCapability('').needsConfig).toBeFalsy();
    expect(getCapability('deep_question').needsConfig).toBe(true);
    expect(getCapability('visualize').needsConfig).toBe(true);
    expect(getCapability('deep_research').needsConfig).toBe(true);
    expect(getCapability('deep_solve').needsConfig).toBeFalsy();
    expect(getCapability('不存在')?.value).toBe('');
  });

  it('真实模式仅对话能力可用：其余标注不可用而非静默转模拟', () => {
    expect(capabilityAvailableInReal('')).toBe(true);
    expect(capabilityAvailableInReal('deep_question')).toBe(false);
    expect(capabilityAvailableInReal('visualize')).toBe(false);
    expect(capabilityAvailableInReal('deep_research')).toBe(false);
  });
});

describe('能力配置校验（对照参考各面板必填规则）', () => {
  it('出题：自定义模式主题必填；仿题模式需要试卷；数量至少 1', () => {
    const forms = createDefaultCapabilityForms();
    expect(capabilityValidationErrors('deep_question', forms)).toContain('出题主题不能为空。');
    forms.deep_question.topic = '二次函数';
    expect(capabilityValidationErrors('deep_question', forms)).toEqual([]);
    forms.deep_question.mode = 'mimic';
    expect(capabilityValidationErrors('deep_question', forms).join('')).toContain('仿照试卷模式');
    forms.deep_question.paper_name = '期中卷.pdf';
    expect(capabilityValidationErrors('deep_question', forms)).toEqual([]);
    forms.deep_question.num_questions = 0;
    expect(capabilityValidationErrors('deep_question', forms).join('')).toContain('至少');
  });

  it('可视化默认配置可用；研究 mode/depth 必选，手动深度需要子问题 ≥2', () => {
    const forms = createDefaultCapabilityForms();
    expect(capabilityValidationErrors('visualize', forms)).toEqual([]);
    expect(capabilityValidationErrors('deep_research', forms)).toHaveLength(2); // mode + depth
    forms.deep_research.mode = 'report';
    forms.deep_research.depth = 'manual';
    forms.deep_research.manual_subtopics = 1; // 低于下限必须报错
    expect(capabilityValidationErrors('deep_research', forms).join('')).toContain('至少 2');
    forms.deep_research.manual_subtopics = 4;
    expect(capabilityValidationErrors('deep_research', forms)).toEqual([]);
  });
});

describe('配置快照与摘要（发送冻结/模拟复述同源）', () => {
  it('快照为纯数据；摘要逐字段可读且与快照一致', () => {
    const forms = createDefaultCapabilityForms();
    forms.deep_question.topic = '光合作用';
    forms.deep_question.num_questions = 5;
    forms.deep_question.question_types = ['choice', 'fill_in_blank'];
    const snapshot = capabilityConfigSnapshot('deep_question', forms);
    expect(snapshot).toEqual({
      mode: 'custom',
      topic: '光合作用',
      num_questions: 5,
      difficulty: 'auto',
      question_types: ['choice', 'fill_in_blank'],
      paper_name: '',
    });
    const summary = summarizeCapabilityConfig('deep_question', snapshot);
    expect(summary).toContain('主题=光合作用');
    expect(summary).toContain('题目数量=5');
    expect(summary).toContain('选择题、填空题');
  });

  it('研究手动深度快照包含子问题与迭代上限；对话能力无配置快照', () => {
    const forms = createDefaultCapabilityForms();
    forms.deep_research.mode = 'notes';
    forms.deep_research.depth = 'manual';
    const snapshot = capabilityConfigSnapshot('deep_research', forms) as Record<string, unknown>;
    expect(snapshot.manual_subtopics).toBe(4);
    expect(snapshot.manual_max_iterations).toBe(3);
    expect(capabilityConfigSnapshot('', forms)).toBeUndefined();
  });
});
