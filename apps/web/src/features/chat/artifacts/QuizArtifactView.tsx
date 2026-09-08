'use client';
import { useMemo, useState } from 'react';
import { Check, ChevronRight, X } from 'lucide-react';
import type { ChatArtifact } from '@/contracts/chat';
import {
  recordQuizAnswer,
  saveQuizEntries,
  type QuizBankEntry,
} from '@/services/space-store';
import { quizTypeLabel, type QuizArtifactQuestion } from '../model/capability-demo';

/**
 * S4 出题产物视图（quiz.data.questions，字段对照参考 QuizQuestion）：
 * 选择题点选即判定，填空/概念本地比对，简答/写作/编程不判对错、展示参考答案对照；
 * 判定为本地确定性比对并显式说明（不伪装 AI 判定服务）。"保存到题库"写入
 * space-store 与业务页同一仓储（S5 /space/questions 读取），同 id 幂等。
 */

interface ParsedData {
  topic: string;
  questions: QuizArtifactQuestion[];
}

function parseData(artifact: ChatArtifact): ParsedData | null {
  if (!artifact.data || typeof artifact.data !== 'object') return null;
  const raw = artifact.data as { topic?: unknown; questions?: unknown };
  if (!Array.isArray(raw.questions)) return null;
  const questions = raw.questions.filter(
    (q): q is QuizArtifactQuestion => !!q && typeof q === 'object' && 'question_id' in q,
  );
  return { topic: typeof raw.topic === 'string' ? raw.topic : '', questions };
}

type Verdict = 'correct' | 'wrong' | 'open';

const CHOICE_KEYS = ['A', 'B', 'C', 'D', 'E', 'F'] as const;

export function QuizArtifactView({
  artifact,
  messageId,
}: {
  artifact: ChatArtifact;
  messageId: string;
}) {
  const parsed = useMemo(() => parseData(artifact), [artifact]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [verdicts, setVerdicts] = useState<Record<string, Verdict>>({});
  const [savedState, setSavedState] = useState<'idle' | 'saved'>('idle');
  const [savedCount, setSavedCount] = useState(0);

  if (!parsed) {
    return (
      <div className="chat-quiz-view">
        <p className="chat-quiz-note">该产物缺少结构化题目数据，以下为文本内容。</p>
        <pre className="chat-quiz-fallback">{artifact.content}</pre>
      </div>
    );
  }

  const judge = (q: QuizArtifactQuestion, answer: string): Verdict => {
    if (q.question_type === 'choice') return answer === q.correct_answer ? 'correct' : 'wrong';
    if (q.question_type === 'fill_in_blank' || q.question_type === 'concept')
      return answer.trim() && answer.trim() === q.correct_answer.trim() ? 'correct' : 'wrong';
    // 简答/写作/编程：本地不做对错判定（不伪装 AI 判定），展示参考答案对照
    return 'open';
  };

  const submitText = (q: QuizArtifactQuestion) => {
    const answer = answers[q.question_id] ?? '';
    if (!answer.trim()) return;
    const verdict = judge(q, answer);
    setVerdicts((cur) => ({ ...cur, [q.question_id]: verdict }));
    recordQuizAnswer(`${messageId}:${q.question_id}`, {
      answer,
      correct: verdict === 'open' ? null : verdict === 'correct',
    });
  };

  const saveAll = () => {
    const entries: Omit<QuizBankEntry, 'savedAt'>[] = parsed.questions.map((q) => ({
      id: `${messageId}:${q.question_id}`,
      messageId,
      questionId: q.question_id,
      topic: parsed.topic,
      question: q.question,
      questionType: q.question_type,
      options: q.options,
      correctAnswer: q.correct_answer,
      explanation: q.explanation,
      difficulty: q.difficulty,
      ...(answers[q.question_id]
        ? {
            lastAnswer: {
              answer: answers[q.question_id]!,
              correct:
                verdicts[q.question_id] === 'open'
                  ? null
                  : verdicts[q.question_id] === 'correct',
              at: new Date().toISOString(),
            },
          }
        : {}),
    }));
    const { added } = saveQuizEntries(entries);
    setSavedCount(added);
    setSavedState('saved');
  };

  return (
    <div className="chat-quiz-view">
      <p className="chat-quiz-note">
        共 {parsed.questions.length} 题（主题：{parsed.topic || '（未填）'}）。判定为本地比对；
        简答/写作/编程不判对错，展示参考答案对照。题目与解析为演示内容。
      </p>
      <ol className="chat-quiz-list">
        {parsed.questions.map((q, index) => {
          const verdict = verdicts[q.question_id];
          const selected = answers[q.question_id] ?? '';
          return (
            <li key={q.question_id} className="chat-quiz-item">
              <header>
                <span className="chat-quiz-index">第 {index + 1} 题</span>
                <span className="chat-quiz-type">{quizTypeLabel(q.question_type)}</span>
                {q.difficulty && <span className="chat-quiz-diff">难度 {q.difficulty}</span>}
                {verdict && (
                  <span className={`chat-quiz-verdict ${verdict}`}>
                    {verdict === 'correct' && (
                      <>
                        <Check size={12} /> 回答正确
                      </>
                    )}
                    {verdict === 'wrong' && (
                      <>
                        <X size={12} /> 回答错误
                      </>
                    )}
                    {verdict === 'open' && <span>已记录，请对照参考答案</span>}
                  </span>
                )}
              </header>
              <p className="chat-quiz-question">{q.question}</p>
              {q.options ? (
                <div className="chat-quiz-options" role="group" aria-label={`第 ${index + 1} 题选项`}>
                  {CHOICE_KEYS.filter((k) => q.options?.[k]).map((key) => {
                    const isPicked = selected === key;
                    const isAnswer = q.correct_answer === key;
                    const showState = verdict !== undefined;
                    return (
                      <button
                        key={key}
                        type="button"
                        className={`chat-quiz-option ${isPicked ? 'picked' : ''} ${
                          showState ? (isAnswer ? 'right' : isPicked ? 'wrong' : '') : ''
                        }`}
                        disabled={verdict !== undefined}
                        onClick={() => {
                          setAnswers((cur) => ({ ...cur, [q.question_id]: key }));
                          const v = judge(q, key);
                          setVerdicts((cur) => ({ ...cur, [q.question_id]: v }));
                          recordQuizAnswer(`${messageId}:${q.question_id}`, {
                            answer: key,
                            correct: v === 'correct',
                          });
                        }}
                      >
                        <strong>{key}.</strong> {q.options?.[key]}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="chat-quiz-text">
                  <textarea
                    aria-label={`第 ${index + 1} 题作答`}
                    placeholder="输入你的作答（本地记录，可用于保存到题库）"
                    value={selected}
                    disabled={verdict !== undefined}
                    onChange={(e) =>
                      setAnswers((cur) => ({ ...cur, [q.question_id]: e.target.value }))
                    }
                  />
                  {verdict === undefined && (
                    <button
                      type="button"
                      className="chat-quiz-submit"
                      onClick={() => submitText(q)}
                    >
                      提交作答 <ChevronRight size={12} />
                    </button>
                  )}
                </div>
              )}
              {verdict !== undefined && (
                <div className="chat-quiz-explain">
                  <p>
                    <strong>参考答案：</strong>
                    {q.question_type === 'choice'
                      ? `${q.correct_answer}. ${q.options?.[q.correct_answer] ?? ''}`
                      : q.correct_answer}
                  </p>
                  <p>
                    <strong>解析：</strong>
                    {q.explanation}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <div className="chat-quiz-actions">
        <button type="button" className="chat-quiz-save" onClick={saveAll}>
          {savedState === 'saved'
            ? `已保存到题库（新增 ${savedCount} 题）`
            : '保存到题库（本地仓储）'}
        </button>
        <span className="chat-quiz-save-note">
          与业务页（学习空间 · 题库）共用同一本地仓储，同题幂等不重复。
        </span>
      </div>
    </div>
  );
}
