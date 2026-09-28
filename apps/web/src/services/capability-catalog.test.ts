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
  it('单层菜单：对话/追问澄清/智能出题/可视化 + RAG 模式；隐藏能力不出现在首页菜单', () => {
    // UX-PERF-CLOSEOUT v1：移除“更多能力”飞出层与其三项次要能力，
    // 同级 RAG 入口现在接入真实本地教材服务。
    expect(CHAT_CAPABILITIES.map((cap) => cap.value)).toEqual([
      '',
      'ask_questions',
      'deep_question',
      'visualize',
      'rag',
    ]);
    // 已删除的三项能力不得以任何形式回流目录
    for (const removed of ['deep_solve', 'deep_research', 'immersive_watching'])
      expect(CHAT_CAPABILITIES.map((cap) => cap.value)).not.toContain(removed);
    // mastery_path / course_study 为工作区自有能力，不进首页菜单（参考 legacy/隐藏规则）
    expect(CHAT_CAPABILITIES.map((cap) => cap.value)).not.toContain('mastery_path');
    expect(CHAT_CAPABILITIES.map((cap) => cap.value)).not.toContain('course_study');
  });

  it('RAG 模式：同级目录项，使用真实教材服务，无额外配置', () => {
    const rag = getCapability('rag');
    expect(rag.label).toBe('RAG 模式');
    expect(rag.unavailableNote).toBeUndefined();
    expect(rag.needsConfig).toBeFalsy(); // 不是二级菜单，也不是配置型能力
    expect(capabilityAvailableInReal('rag')).toBe(true);
  });

  it('needsConfig 仅出题/可视化需要配置确认；未知值回退对话', () => {
    expect(getCapability('').needsConfig).toBeFalsy();
    expect(getCapability('deep_question').needsConfig).toBe(true);
    expect(getCapability('visualize').needsConfig).toBe(true);
    expect(getCapability('不存在')?.value).toBe('');
  });

  it('真实对话与教材追问可用；未实现的出题与可视化仍禁用', () => {
    expect(capabilityAvailableInReal('')).toBe(true);
    expect(capabilityAvailableInReal('deep_question')).toBe(false);
    expect(capabilityAvailableInReal('visualize')).toBe(false);
    expect(capabilityAvailableInReal('ask_questions')).toBe(true);
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

  it('可视化默认配置可用；已移除的研究表单不再参与校验', () => {
    const forms = createDefaultCapabilityForms();
    expect(capabilityValidationErrors('visualize', forms)).toEqual([]);
    // 已删除的能力值不产生校验错误（也不会被任何菜单项选中）
    expect(capabilityValidationErrors('deep_research', forms)).toEqual([]);
    expect(Object.keys(forms).sort()).toEqual(['deep_question', 'visualize']);
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

  it('可视化快照为纯数据；对话与已移除能力无配置快照', () => {
    const forms = createDefaultCapabilityForms();
    forms.visualize.render_mode = 'mermaid';
    const snapshot = capabilityConfigSnapshot('visualize', forms) as Record<string, unknown>;
    expect(snapshot.render_mode).toBe('mermaid');
    expect(capabilityConfigSnapshot('', forms)).toBeUndefined();
    expect(capabilityConfigSnapshot('deep_research', forms)).toBeUndefined();
  });
});
