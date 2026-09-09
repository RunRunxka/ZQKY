import type { AskUserAnswer, ChatArtifact } from '@/contracts/chat';
import type { ChatService } from '@/features/chat/model/chat-service';
import {
  RESEARCH_MODE_LABELS,
  summarizeCapabilityConfig,
  VISUALIZE_RENDER_LABELS,
} from '@/services/capability-catalog';

import {
  makeDemoQuestion,
  makeResearchCitations,
  makeResearchSubtopics,
  planQuestionTypes,
  quizQuestionsToMarkdown,
  quizTypeLabel,
  researchReportToMarkdown,
  type QuizArtifactQuestion,
} from '@/features/chat/model/capability-demo';

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException('aborted', 'AbortError'));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

function chunkText(text: string, size = 16): string[] {
  const chars = [...text];
  const chunks: string[] = [];
  for (let index = 0; index < chars.length; index += size) {
    chunks.push(chars.slice(index, index + size).join(''));
  }
  return chunks;
}

export interface MockChatService extends ChatService {
  readonly kind: 'mock';
  /**
   * 布防一次模拟失败：下一次发送按确定性脚本收尾——选择了 MCP 时，第一个模拟
   * 工具以明确错误结束（本轮按错误收尾，保留正文与过程）；未选择 MCP 时保持
   * 原有行为（先输出少量正文再返回可重试错误）。
   */
  armFailure(): void;
  /** 布防追问场景：下一次发送在正文中途暂停，先问 2 题卡再问 1 题卡，回答后同轮续写 */
  armAskUser(): void;
  /** 布防一次追问提交失败：下一次追问提交先返回卡片级错误，重试成功 */
  armReplyFailure(): void;
}

/** 追问等待的本地挂起点：回答到达或信号中止前，run 保持活动（不能提前正常返回） */
function waitForReply(
  replies: Map<string, (answers: AskUserAnswer[]) => void>,
  interactionId: string,
  signal: AbortSignal,
): Promise<AskUserAnswer[]> {
  return new Promise<AskUserAnswer[]>((resolve, reject) => {
    let settled = false;
    const onAbort = () => {
      if (settled) return;
      settled = true;
      replies.delete(interactionId);
      reject(new DOMException('aborted', 'AbortError'));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener('abort', onAbort, { once: true });
    replies.set(interactionId, (answers) => {
      if (settled) return;
      settled = true;
      signal.removeEventListener('abort', onAbort);
      resolve(answers);
    });
  });
}

function describeAnswer(answer: AskUserAnswer | undefined, fallbackPrompt: string): string {
  if (!answer || answer.skipped || (!answer.labels.length && !answer.freeText?.trim()))
    return `「${fallbackPrompt}」已按跳过处理`;
  const parts: string[] = [];
  if (answer.labels.length) parts.push(`选择了「${answer.labels.join('、')}」`);
  if (answer.freeText?.trim()) parts.push(`补充说明：${answer.freeText.trim()}`);
  return parts.join('；') || `「${fallbackPrompt}」已按跳过处理`;
}

/**
 * 本地模拟服务：不访问真实模型、MCP 或外部工具；
 * 回复带【模拟回复】标识，数据由调用方保存到与真实会话隔离的存储。
 * 扩展场景确定性可复现：无扩展 / 单扩展 / 多扩展 / 一次工具失败 / 执行中取消
 * （取消由信号中止触发，运行中的工具由 store 收尾）。
 * 追问场景（armAskUser）确定性覆盖：同轮两卡、单选+多选/自由文本、回答驱动续写、
 * 全部跳过、一次提交失败可重试、等待中取消。
 */
export function createMockChatService(options?: { chunkDelayMs?: number }): MockChatService {
  const chunkDelay = options?.chunkDelayMs ?? 70;
  let failNext = false;
  let askNext = false;
  let replyFailNext = false;
  const pendingReplies = new Map<string, (answers: AskUserAnswer[]) => void>();
  return {
    kind: 'mock',
    armFailure() {
      failNext = true;
    },
    armAskUser() {
      askNext = true;
    },
    armReplyFailure() {
      replyFailNext = true;
    },
    async submitReply(request) {
      const resolver = pendingReplies.get(request.interactionId);
      if (!resolver)
        return {
          accepted: false,
          code: 'NO_ACTIVE_WAIT',
          message: '该追问没有正在进行的等待，无法提交。',
        };
      // 幂等：同一 interactionId 的挂起点只会被消费一次
      if (replyFailNext) {
        // 卡片级失败：不消费挂起点，保留草稿可重试
        replyFailNext = false;
        return {
          accepted: false,
          code: 'MOCK_REPLY_ERROR',
          message: '已按你的要求模拟一次回答提交失败，可直接重试。',
        };
      }
      pendingReplies.delete(request.interactionId);
      resolver(request.answers);
      return { accepted: true };
    },
    async run(request, emit) {
      const turn = { sessionId: request.sessionId, turnId: request.turnId };
      const shouldFail = failNext;
      failNext = false;
      const shouldAsk = askNext;
      askNext = false;
      const question =
        [...request.messages].reverse().find((m) => m.role === 'user')?.content ?? '';
      const snapshot = request.extensions;
      // S2：能力快照（发送时冻结）。模拟侧按配置如实复述；无解析服务，
      // 附件内容不读取、知识来源不执行真实检索，均明确说明。
      const capability = snapshot?.capability;
      const capabilitySummary = capability
        ? summarizeCapabilityConfig(capability.value, capability.config)
        : '';
      const composerNotes: string[] = [];
      if (capability && capability.value)
        composerNotes.push(
          `本轮能力：${capability.label}（配置：${capabilitySummary || '未携带'}）`,
        );
      if (snapshot?.persona) composerNotes.push(`角色人设：${snapshot.persona.name}（演示目录）`);
      if (snapshot?.knowledge?.length)
        composerNotes.push(
          `知识来源：${snapshot.knowledge.map((k) => k.name).join('、')}（仅声明检索范围，未执行真实检索）`,
        );
      if (snapshot?.historyRefs?.length)
        composerNotes.push(
          `引用会话：${snapshot.historyRefs.map((h) => `「${h.title}」`).join('、')}（已按标题纳入上下文说明）`,
        );
      if (snapshot?.attachments?.length)
        composerNotes.push(
          `附件 ${snapshot.attachments.length} 个：${snapshot.attachments.map((a) => a.filename).join('、')}（未读取文件内容——当前无解析服务，不伪装上传成功）`,
        );

      emit({ ...turn, type: 'turn-start' });
      emit({
        ...turn,
        type: 'process',
        delta: '[模拟] 在本地理解问题并组织回答，不访问模型、MCP 或外部工具。',
      });
      if (capability?.value)
        emit({
          ...turn,
          type: 'process',
          delta: `[模拟] 按「${capability.label}」能力执行（发送时冻结的配置）：${capabilitySummary}。`,
        });
      // S4：能力专属阶段序列在各自分支内 start/end；普通对话/追问用一个 organize 阶段
      const isCapabilityTurn =
        !!capability?.value &&
        ['deep_solve', 'deep_question', 'deep_research', 'visualize'].includes(capability.value);
      if (!isCapabilityTurn)
        emit({
          ...turn,
          type: 'stage',
          stageId: 'organize',
          label: '正在组织回答',
          phase: 'start',
        });
      await sleep(chunkDelay, request.signal);

      // ===== 追问场景（纯追问专用）：正文→提问→回答记录→续写，同 sessionId/turnId 继续 =====
      // 触发来源：armAskUser 布防 或「追问澄清」能力（ask_questions，能力语义=先提问补全上下文）；
      // 仅当没有扩展、也没有产物型能力时走这里；带能力/扩展的追问在下方组合流中
      // （工具→单卡→续写→产物，见 S3 组合流），否则工具卡会被追问流程截断。
      const hasExtensions =
        (snapshot?.mcps?.length ?? 0) > 0 || (snapshot?.skills?.length ?? 0) > 0;
      const capabilityDrivesArtifact =
        !!capability?.value &&
        ['deep_solve', 'deep_question', 'deep_research', 'visualize'].includes(capability.value);
      const capabilityAsks = capability?.value === 'ask_questions';
      if ((shouldAsk || capabilityAsks) && !hasExtensions && !capabilityDrivesArtifact) {
        emit({
          ...turn,
          type: 'text',
          delta: '【模拟回复】收到你的问题。为了让回答更贴合你的教学场景，先确认两件事：\n\n',
        });
        const interaction1Id = `ask-1-${request.turnId.slice(0, 8)}`;
        emit({
          ...turn,
          type: 'wait-user',
          interaction: {
            interactionId: interaction1Id,
            intro: '为了让模拟回答更贴合场景，请确认以下偏好（本地演示，不访问真实服务）。',
            status: 'waiting',
            questions: [
              {
                questionId: 'q-style',
                prompt: '希望按什么方式讲解？',
                header: '讲解方式',
                options: [
                  { label: '按知识点讲解', description: '从概念到例题逐步展开' },
                  { label: '按题目场景讲解', description: '从具体题目切入' },
                ],
                multiSelect: false,
              },
              {
                questionId: 'q-materials',
                prompt: '希望回答中包含哪些内容？（可多选，也可补充说明）',
                header: '内容偏好',
                options: [
                  { label: '结合课标', description: '对齐课程标准' },
                  { label: '给出示例', description: '包含具体例子' },
                  { label: '提供练习', description: '附练习建议' },
                ],
                multiSelect: true,
                allowFreeText: true,
                placeholder: '补充说明（可选）',
              },
            ],
          },
        });
        const answers1 = await waitForReply(pendingReplies, interaction1Id, request.signal);
        const style = answers1.find((a) => a.questionId === 'q-style');
        const materials = answers1.find((a) => a.questionId === 'q-materials');
        emit({
          ...turn,
          type: 'text',
          delta: `已记录你的偏好：${describeAnswer(style, '讲解方式')}；${describeAnswer(materials, '内容偏好')}。\n\n【模拟回复】下面按以上偏好继续（本地模拟，内容随你的选择变化）：\n\n- 讲解主线已按你的选择组织\n- 内容模块按你的勾选生成\n\n在结束前再确认一件事：\n\n`,
        });
        const interaction2Id = `ask-2-${request.turnId.slice(0, 8)}`;
        emit({
          ...turn,
          type: 'wait-user',
          interaction: {
            interactionId: interaction2Id,
            intro: '最后一个确认（同一轮内的第二张追问卡）。',
            status: 'waiting',
            questions: [
              {
                questionId: 'q-summary',
                prompt: '需要在本轮结束时附一段小结吗？',
                header: '收尾方式',
                options: [
                  { label: '需要小结', description: '附三行要点小结' },
                  { label: '不需要', description: '直接结束本轮' },
                ],
                multiSelect: false,
              },
            ],
          },
        });
        const answers2 = await waitForReply(pendingReplies, interaction2Id, request.signal);
        const summary = answers2.find((a) => a.questionId === 'q-summary');
        const wantsSummary = summary?.labels.includes('需要小结');
        const materialLabels = materials?.labels.length
          ? materials.labels.join('、')
          : '未勾选内容模块';
        emit({
          ...turn,
          type: 'text',
          delta: `已收到收尾选择：${describeAnswer(summary, '收尾方式')}。\n\n【模拟回复】本轮续答完成（同 sessionId/turnId 继续，未新开轮次）。\n\n- 偏好回顾：${style?.labels[0] ?? '跳过'}｜${materialLabels}${summary?.freeText?.trim() ? `｜补充：${summary.freeText.trim()}` : ''}\n- 内容模块状态：${materialLabels}\n`,
        });
        if (wantsSummary)
          emit({
            ...turn,
            type: 'text',
            delta:
              '\n要点小结：\n1. 讲解方式已确认\n2. 内容模块已按勾选生成\n3. 本轮为同轮续答演示\n',
          });
        emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
        emit({ ...turn, type: 'end', finishReason: 'stop' });
        return;
      }

      // 技能上下文加载：明确的加载记录，不伪装成远程工具调用
      for (const [index, skill] of (snapshot?.skills ?? []).entries()) {
        const callId = `skill-${index + 1}-${skill.id}`;
        emit({
          ...turn,
          type: 'tool',
          call: { callId, kind: 'skill', name: skill.name, status: 'running' },
        });
        await sleep(chunkDelay, request.signal);
        emit({
          ...turn,
          type: 'tool',
          call: {
            callId,
            kind: 'skill',
            name: skill.name,
            status: 'done',
            note: '技能上下文已加载（模拟）',
            detail: `已将技能「${skill.name}」的说明作为上下文参考（本地模拟，未访问远程服务）。\n\n${skill.description || '暂无描述'}`,
          },
        });
      }

      // MCP 模拟工具调用：按选择顺序逐个执行，确定性输出
      for (const [index, mcp] of (snapshot?.mcps ?? []).entries()) {
        const callId = `mcp-${index + 1}-${mcp.id}`;
        emit({
          ...turn,
          type: 'tool',
          call: {
            callId,
            kind: 'mcp',
            name: mcp.name,
            status: 'running',
            note: '模拟工具调用 · 未连接真实服务',
          },
        });
        emit({
          ...turn,
          type: 'process',
          delta: `[模拟] 正在通过 ${mcp.name} 获取本地演示数据。`,
        });
        await sleep(chunkDelay, request.signal);
        if (shouldFail && index === 0) {
          emit({
            ...turn,
            type: 'tool',
            call: {
              callId,
              kind: 'mcp',
              name: mcp.name,
              status: 'error',
              note: '模拟工具调用 · 未连接真实服务',
              detail: '【模拟失败】该工具按脚本返回一次错误，可直接重试。',
            },
          });
          emit({
            ...turn,
            type: 'error',
            error: {
              code: 'MOCK_TOOL_ERROR',
              message: '模拟工具执行失败，可直接重试（沿用本轮扩展选择）。',
              retryable: true,
            },
          });
          return;
        }
        emit({
          ...turn,
          type: 'tool',
          call: {
            callId,
            kind: 'mcp',
            name: mcp.name,
            status: 'done',
            note: '模拟工具调用 · 未连接真实服务',
            detail: `【模拟工具】${mcp.name} 已在本地生成演示结果：\n\n- 输入：${question || '（无正文）'}\n- 输出：演示数据片段（与问题相关的本地示例内容）\n\n未连接真实服务，仅用于流程演示。`,
          },
        });
      }

      // S3 组合流（工具之后、能力分支之前）：同 sessionId/turnId 挂起→回答→继续，不另开轮。
      // 纯追问场景（无扩展且无产物型能力）已在上方的专用流程中结束，不会到达这里。
      if (shouldAsk && (hasExtensions || capabilityDrivesArtifact)) {
        const comboInteractionId = `ask-combo-${request.turnId.slice(0, 8)}`;
        emit({
          ...turn,
          type: 'wait-user',
          interaction: {
            interactionId: comboInteractionId,
            intro: '结合上面的扩展执行结果，请确认一个偏好（本地演示，同一轮内继续）。',
            status: 'waiting',
            questions: [
              {
                questionId: 'q-focus',
                prompt: '希望结果侧重哪个方向？',
                header: '产出侧重',
                options: [
                  { label: '侧重示例', description: '多给具体例子' },
                  { label: '侧重解析', description: '多给原理说明' },
                ],
                multiSelect: false,
              },
            ],
          },
        });
        const comboAnswers = await waitForReply(pendingReplies, comboInteractionId, request.signal);
        const focus = comboAnswers.find((a) => a.questionId === 'q-focus');
        emit({
          ...turn,
          type: 'text',
          delta: `已记录产出侧重：${describeAnswer(focus, '产出侧重')}。下面按该偏好在同一轮内继续生成结果。\n\n`,
        });
      }

      // ===== S4 能力专属阶段序列与产物（对照参考 manifest 阶段与结果结构）=====
      const shortQuestion = question.length > 40 ? `${question.slice(0, 40)}…` : question;
      // 阶段 helper：start→过程说明→（可选中工作）→end；阶段记录随消息持久化
      const runStage = async (
        stageId: string,
        label: string,
        note: string | null,
        work?: () => Promise<void>,
      ) => {
        emit({ ...turn, type: 'stage', stageId, label, phase: 'start' });
        if (note) emit({ ...turn, type: 'process', delta: note });
        await sleep(chunkDelay, request.signal);
        if (work) await work();
        emit({ ...turn, type: 'stage', stageId, label, phase: 'end' });
      };
      const streamText = async (text: string) => {
        for (const piece of chunkText(text)) {
          if (request.signal.aborted) throw new DOMException('aborted', 'AbortError');
          emit({ ...turn, type: 'text', delta: piece });
          await sleep(chunkDelay, request.signal);
        }
      };
      // S2 审查要求的能力轮正文复述：配置摘要 + 附件/知识"未读取/未检索"如实说明
      const composerNote = composerNotes.length
        ? `\n\n已按发送时冻结的完整配置执行（本地模拟）：\n${composerNotes.map((note) => `- ${note}`).join('\n')}`
        : '';
      // S4：能力轮部分失败演示——首个阶段完成后中断（阶段收口为 cancelled），
      // 错误可重试且沿用冻结配置；显式失败路径，不靠隐藏关键词
      const failCapabilityTurn = () => {
        emit({
          ...turn,
          type: 'error',
          error: {
            code: 'MOCK_CAPABILITY_ERROR',
            message: '已按你的要求模拟一次能力执行失败（阶段中断），可直接重试，沿用本轮冻结配置。',
            retryable: true,
          },
        });
      };

      if (capability?.value === 'deep_solve') {
        // 参考 manifest：planning→reasoning→writing（推理过程与正文分开呈现）
        await runStage(
          'planning',
          '规划解题路径',
          `[模拟] 分析「${shortQuestion}」的条件与求解目标，拆解为可执行的子步骤（本地演示，不访问真实推理服务）。`,
        );
        if (shouldFail) {
          failCapabilityTurn();
          return;
        }
        await runStage('reasoning', '逐步推理', null, async () => {
          const reasoning =
            '【模拟推理】按规划逐层推进：先整理已知量并确认约束，再选择对应方法代入推导，最后核对结论与题设一致。此过程为本地演示文本，不代表真实模型推理。';
          for (const piece of chunkText(reasoning)) {
            if (request.signal.aborted) throw new DOMException('aborted', 'AbortError');
            emit({ ...turn, type: 'reasoning', delta: piece });
            await sleep(chunkDelay, request.signal);
          }
        });
        await runStage('writing', '组织答案', null, async () => {
          const answer = `【模拟回复】深度求解（本地演示）\n\n## 已知与目标\n- 题面：${shortQuestion}\n\n## 解题步骤\n1. 【演示】明确条件与求解目标\n2. 【演示】选择方法并逐步代入\n3. 【演示】检验结果与题设一致性\n\n## 答案\n（演示占位：最终结论与检验说明）\n\n> 本轮为深度求解能力的结构演示，推理与答案均为本地演示内容。${composerNote}`;
          await streamText(answer);
        });
        emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
        emit({ ...turn, type: 'end', finishReason: 'stop' });
        return;
      }

      if (capability?.value === 'deep_question') {
        // 参考 manifest：exploring→planning→quizzing；每题一个 quiz_question_emitted 增量
        const cfg = (capability.config ?? {}) as Record<string, unknown>;
        const topic = typeof cfg.topic === 'string' ? cfg.topic.trim() : '';
        const num =
          typeof cfg.num_questions === 'number' &&
          Number.isFinite(cfg.num_questions) &&
          cfg.num_questions >= 1
            ? Math.min(Math.floor(cfg.num_questions), 10)
            : 3;
        const difficulty =
          typeof cfg.difficulty === 'string' && cfg.difficulty && cfg.difficulty !== 'auto'
            ? cfg.difficulty
            : '自动';
        const whitelist = Array.isArray(cfg.question_types)
          ? cfg.question_types.filter((x): x is string => typeof x === 'string')
          : [];
        const plan = planQuestionTypes(num, whitelist);
        const questions: QuizArtifactQuestion[] = [];
        const artifactId = `deep_question-${request.turnId.slice(0, 8)}`;
        await runStage(
          'exploring',
          '梳理相关知识点',
          `[模拟] 围绕主题「${topic || '（空）'}」梳理知识点范围（本地演示，不做真实检索）。`,
        );
        await runStage(
          'planning',
          '规划题型分布',
          `[模拟] 共 ${plan.length} 题，题型分布：${plan.map(quizTypeLabel).join('、')}；难度=${difficulty}。`,
        );
        if (shouldFail) {
          failCapabilityTurn();
          return;
        }
        await runStage('quizzing', '逐题生成', null, async () => {
          for (let i = 0; i < plan.length; i++) {
            emit({
              ...turn,
              type: 'process',
              delta: `[模拟] 生成第 ${i + 1}/${plan.length} 题（${quizTypeLabel(plan[i]!)}）…`,
            });
            questions.push(makeDemoQuestion(i, topic, plan[i]!, difficulty));
            // 每题增量更新产物（对照 quiz_question_emitted：按 id 幂等覆盖，题数递增）
            emit({
              ...turn,
              type: 'artifact',
              artifact: {
                id: artifactId,
                kind: 'quiz',
                title: '出题结果（模拟）',
                content: quizQuestionsToMarkdown(topic, questions),
                data: { topic, questions: [...questions] },
              },
            });
            await sleep(chunkDelay, request.signal);
          }
        });
        await streamText(
          `【模拟回复】已按配置生成 ${plan.length} 道演示题（主题「${topic || '（空）'}」）。在结果工作区打开「出题结果（模拟）」可作答并查看反馈；题目与解析为本地演示内容，可一键保存到题库。${composerNote}`,
        );
        emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
        emit({ ...turn, type: 'end', finishReason: 'stop' });
        return;
      }

      if (capability?.value === 'deep_research') {
        // 参考：rephrasing→decomposing→（大纲确认 outline_preview）→researching→reporting
        const cfg = (capability.config ?? {}) as Record<string, unknown>;
        const depth = typeof cfg.depth === 'string' ? cfg.depth : '';
        const mode = typeof cfg.mode === 'string' ? cfg.mode : '';
        const modeLabel =
          RESEARCH_MODE_LABELS.find((x) => x.value === mode)?.label ?? (mode || '（未选择）');
        const subCount =
          depth === 'manual' &&
          typeof cfg.manual_subtopics === 'number' &&
          cfg.manual_subtopics >= 2
            ? Math.min(Math.floor(cfg.manual_subtopics), 6)
            : depth === 'deep'
              ? 4
              : 3;
        const artifactId = `deep_research-${request.turnId.slice(0, 8)}`;
        await runStage(
          'rephrasing',
          '澄清研究问题',
          `[模拟] 研究问题：${shortQuestion}；产出类型=${modeLabel}。`,
        );
        if (shouldFail) {
          failCapabilityTurn();
          return;
        }
        let subtopics: string[] = [];
        await runStage('decomposing', '拆分子问题', null, async () => {
          subtopics = makeResearchSubtopics(question, subCount);
          emit({
            ...turn,
            type: 'process',
            delta: `[模拟] 大纲共 ${subtopics.length} 个子问题：${subtopics.join('；')}`,
          });
        });
        // 两段式：大纲确认（对照原版 outline_preview + 大纲编辑器；本地用追问卡确认/调整）
        const outlineInteractionId = `research-outline-${request.turnId.slice(0, 8)}`;
        emit({
          ...turn,
          type: 'wait-user',
          interaction: {
            interactionId: outlineInteractionId,
            intro:
              '已生成研究大纲（本地演示）。确认后开始逐题检索与撰写；如需调整，选择"调整后执行"并在补充栏说明。',
            status: 'waiting',
            questions: [
              {
                questionId: 'q-outline',
                prompt: `确认这份包含 ${subtopics.length} 个子问题的大纲？`,
                header: '研究大纲',
                options: [
                  { label: '确认大纲，按此执行', description: subtopics.join('；') },
                  { label: '调整后执行', description: '在补充栏说明调整意见' },
                ],
                multiSelect: false,
                allowFreeText: true,
                placeholder: '调整意见（选择"调整后执行"时填写）',
              },
            ],
          },
        });
        const outlineAnswers = await waitForReply(
          pendingReplies,
          outlineInteractionId,
          request.signal,
        );
        const outlineChoice = outlineAnswers.find((a) => a.questionId === 'q-outline');
        const adjustNote = outlineChoice?.freeText?.trim();
        await runStage('researching', '逐题检索演示资料', null, async () => {
          for (const [i, sub] of subtopics.entries()) {
            emit({
              ...turn,
              type: 'process',
              delta: `[模拟] 检索子问题 ${i + 1}/${subtopics.length}：${sub}（本地演示资料，不访问真实网络）`,
            });
            await sleep(chunkDelay, request.signal);
          }
        });
        const citations = makeResearchCitations(subtopics);
        const report = researchReportToMarkdown(
          question,
          adjustNote ? `${modeLabel}（调整备注：${adjustNote}）` : modeLabel,
          subtopics,
          citations,
        );
        await runStage('reporting', '撰写报告', null, async () => {
          await streamText(report);
        });
        emit({
          ...turn,
          type: 'artifact',
          artifact: {
            id: artifactId,
            kind: 'report',
            title: '研究报告（模拟）',
            content: report,
            data: { mode, depth, subtopics, citations },
          },
        });
        await streamText(
          `【模拟回复】研究报告已完成（本地演示）。在结果工作区可查看引用定位与全文，也可复制、下载或保存到笔记；研究资料为演示内容，不捏造真实检索结果。${composerNote}`,
        );
        emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
        emit({ ...turn, type: 'end', finishReason: 'stop' });
        return;
      }

      if (capability?.value === 'visualize') {
        // 参考：analyzing→generating→reviewing；manim 路由为六阶段（见下）
        const cfg = (capability.config ?? {}) as Record<string, unknown>;
        const renderMode =
          typeof cfg.render_mode === 'string' && cfg.render_mode ? cfg.render_mode : 'auto';
        const quality = typeof cfg.quality === 'string' ? cfg.quality : 'medium';
        const styleHint = typeof cfg.style_hint === 'string' ? cfg.style_hint.trim() : '';
        const modeLabel = (value: string) =>
          VISUALIZE_RENDER_LABELS.find((x) => x.value === value)?.label ?? value;
        // auto：按问题意图确定性解析（流程/关系→mermaid，图表/数据→chartjs，默认 svg）
        const resolved =
          renderMode === 'auto'
            ? /流程|关系|结构|层次/.test(question)
              ? 'mermaid'
              : /图表|数据|统计|占比|趋势/.test(question)
                ? 'chartjs'
                : 'svg'
            : renderMode;
        const artifactId = `visualize-${request.turnId.slice(0, 8)}`;
        const base = `本轮能力：${capability.label}（本地模拟）\n\n- 配置：${capabilitySummary}\n- 附件 ${snapshot?.attachments?.length ?? 0} 个（未读取内容）、知识来源 ${snapshot?.knowledge?.length ?? 0} 项（未真实检索）`;

        if (resolved === 'manim_video' || resolved === 'manim_image') {
          // 数学动画六阶段（对照参考 math_animator）；不假装执行 Manim——
          // 渲染服务未接入，不生成真实视频/图像文件，媒体产物为明确标识的演示内容
          const isImage = resolved === 'manim_image';
          await runStage(
            'concept_analysis',
            '概念分析',
            `[模拟] 明确「${shortQuestion}」要展示的数学概念与呈现形式（${isImage ? '分镜图片' : '动画视频'}）（本地演示）。`,
          );
          if (shouldFail) {
            failCapabilityTurn();
            return;
          }
          await runStage(
            'concept_design',
            '分镜设计',
            `[模拟] 设计分镜：概念引入 → 公式呈现 → 逐步变换 → 结论强调（演示分镜表，质量=${quality}${styleHint ? `、风格提示=${styleHint}` : ''}）。`,
          );
          const manimCode = [
            '# 演示 Manim Scene（未真实执行）',
            'from manim import *',
            '',
            'class DemoScene(Scene):',
            '    def construct(self):',
            '        # 本地演示代码：渲染服务未接入，不会生成真实视频/图像文件',
            '        title = Text("演示动画场景", font_size=36)',
            '        self.play(Write(title))',
            '        self.wait(1)',
            '',
          ].join('\n');
          await runStage('code_generation', '生成 Manim 代码', null, async () => {
            emit({
              ...turn,
              type: 'process',
              delta: '[模拟] 已生成 Scene 代码（本地演示，不执行 Manim）。',
            });
          });
          await runStage(
            'code_retry',
            '渲染重试',
            '[模拟] 演示重试历史：第 1 次渲染超时 → 已自动重试并放宽质量参数（对照原版 code_retry；本地不执行渲染）。',
          );
          await runStage(
            'summary',
            '总结',
            '[模拟] 动画要点：概念引入、变换过程、结论强调（演示总结）。',
          );
          let storyboard: string | null = null;
          await runStage('render_output', '渲染输出', null, async () => {
            if (isImage) {
              storyboard =
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" role="img" aria-label="演示分镜示意"><rect width="320" height="180" fill="#f8fafc"/><rect x="24" y="40" width="120" height="100" fill="#e2e8f0"/><rect x="176" y="40" width="120" height="100" fill="#e2e8f0"/><text x="24" y="28" font-size="12" fill="#334155">演示分镜示意（非真实渲染帧）</text><text x="40" y="95" font-size="11" fill="#475569">帧 1：概念引入</text><text x="192" y="95" font-size="11" fill="#475569">帧 2：结论强调</text></svg>';
              emit({
                ...turn,
                type: 'process',
                delta: '[模拟] 已生成分镜示意图（演示内容，非真实渲染帧）。',
              });
            } else {
              emit({
                ...turn,
                type: 'process',
                delta:
                  '[模拟] 视频渲染服务未接入：不生成真实视频文件，仅提供代码、分镜与总结（如实说明，不假装渲染）。',
              });
            }
          });
          emit({
            ...turn,
            type: 'artifact',
            artifact: {
              id: `${artifactId}-code`,
              kind: 'markdown',
              title: '数学动画（模拟）',
              content: `# 数学动画（模拟）\n\n${base}\n\n## 概念与分镜\n- 概念：${shortQuestion}\n- 分镜：概念引入 → 公式呈现 → 逐步变换 → 结论强调\n- 渲染质量：${quality}${styleHint ? `；风格提示：${styleHint}` : ''}\n- 重试历史：第 1 次渲染超时 → 已重试（演示记录）\n\n## Manim 代码（未真实执行）\n\`\`\`python\n${manimCode}\`\`\`\n\n> 【演示媒体说明】渲染服务未接入，${isImage ? '分镜为演示示意，非真实渲染帧' : '不生成真实视频文件'}；以上内容用于动画流程演示。\n`,
            },
          });
          if (storyboard)
            emit({
              ...turn,
              type: 'artifact',
              artifact: {
                id: `${artifactId}-storyboard`,
                kind: 'svg',
                title: '分镜示意（模拟）',
                content: storyboard,
              },
            });
          await streamText(
            `【模拟回复】数学动画流程已完成（${modeLabel(resolved)}，本地演示）。渲染服务未接入：${isImage ? '分镜为演示示意，非真实渲染帧' : '不生成真实视频文件'}；可在结果工作区查看代码与流程。`,
          );
          emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
          emit({ ...turn, type: 'end', finishReason: 'stop' });
          return;
        }

        await runStage(
          'analyzing',
          '分析可视化需求',
          `[模拟] 渲染模式=${renderMode === 'auto' ? `自动（按问题意图解析为 ${modeLabel(resolved)}）` : modeLabel(resolved)}、质量=${quality}${styleHint ? `、风格提示=${styleHint}` : ''}。`,
        );
        if (shouldFail) {
          failCapabilityTurn();
          return;
        }
        let kind: ChatArtifact['kind'] = 'svg';
        let content = '';
        let data: unknown;
        await runStage('generating', '生成渲染内容', null, async () => {
          if (resolved === 'chartjs') {
            kind = 'chart';
            const chartConfig = {
              type: 'bar',
              data: {
                labels: ['一月', '二月', '三月', '四月'],
                datasets: [{ label: '演示数据', data: [12, 19, 8, 15] }],
              },
              options: { responsive: true },
            };
            data = { config: chartConfig };
            content = JSON.stringify(chartConfig, null, 2);
            emit({
              ...turn,
              type: 'process',
              delta: '[模拟] 已生成 Chart.js 配置（预览由本地 Chart.js 渲染，数据为演示值）。',
            });
          } else if (resolved === 'mermaid') {
            kind = 'mermaid';
            content = [
              'flowchart TD',
              `  A["${shortQuestion}"] --> B{拆解}`,
              '  B --> C[要点一]',
              '  B --> D[要点二]',
              '  C --> E[演示结论]',
              '  D --> E',
            ].join('\n');
            data = { source: content };
            emit({
              ...turn,
              type: 'process',
              delta: '[模拟] 已生成 Mermaid 源码（预览由本地 Mermaid 渲染）。',
            });
          } else if (resolved === 'html') {
            kind = 'html';
            content =
              '<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>body{font-family:system-ui,sans-serif;padding:16px;color:#1e293b}h1{font-size:18px}li{margin:6px 0}</style></head><body><h1>演示页面（模拟）</h1><ul><li>本地演示 HTML：经 sandbox iframe 隔离渲染，不执行脚本。</li><li>内容为演示占位，不访问真实服务。</li></ul></body></html>';
            emit({
              ...turn,
              type: 'process',
              delta: '[模拟] 已生成静态 HTML（sandbox 隔离预览，禁脚本）。',
            });
          } else {
            kind = 'svg';
            content =
              '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" role="img" aria-label="模拟图表"><rect width="320" height="180" fill="#f8fafc"/><rect x="30" y="90" width="40" height="60" fill="#2563eb"/><rect x="90" y="60" width="40" height="90" fill="#3b82f6"/><rect x="150" y="100" width="40" height="50" fill="#60a5fa"/><rect x="210" y="40" width="40" height="110" fill="#93c5fd"/><text x="30" y="24" font-size="12" fill="#334155">模拟图表（本地演示，未访问渲染服务）</text></svg>';
            emit({ ...turn, type: 'process', delta: '[模拟] 已生成 SVG 图形（本地演示）。' });
          }
        });
        await runStage(
          'reviewing',
          '视觉审查',
          '[模拟] 审查结论：结构完整、标注清晰、比例正确（本地演示审查，对照原版 reviewing 阶段）。',
        );
        emit({
          ...turn,
          type: 'artifact',
          artifact: {
            id: artifactId,
            kind,
            title: '可视化结果（模拟）',
            content,
            ...(data !== undefined ? { data } : {}),
          },
        });
        await streamText(
          `【模拟回复】可视化已完成（渲染模式=${modeLabel(resolved)}，本地演示）。在结果工作区打开「可视化结果（模拟）」预览、复制或下载。${composerNote}`,
        );
        emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
        emit({ ...turn, type: 'end', finishReason: 'stop' });
        return;
      }

      if (shouldFail) {
        emit({ ...turn, type: 'text', delta: '【模拟回复】这段回答前半部分正常，' });
        emit({
          ...turn,
          type: 'error',
          error: {
            code: 'MOCK_ERROR',
            message: '已按你的要求模拟一次失败，可直接重试。',
            retryable: true,
          },
        });
        return;
      }

      const extensionNote =
        snapshot && (snapshot.mcps.length || snapshot.skills.length)
          ? `\n\n本轮过程来自本地模拟扩展（${snapshot.mcps.length} 个 MCP、${snapshot.skills.length} 个技能），未访问真实服务。`
          : '';
      const answer = `【模拟回复】已收到你的问题：「${shortQuestion}」。\n\n这是一段本地模拟回答，用于在未配置模型凭证时体验完整对话流程：流式分块输出、随时停止、失败重试与多会话管理均可正常使用；数据保存在独立存储，与真实问答相互隔离。\n\n- 不访问真实模型、MCP 或外部工具\n- 界面右上角可随时切回真实模式${extensionNote}${composerNote}`;
      // 组织阶段完成后再流式输出正文（阶段序列在活动区可见）
      if (!isCapabilityTurn)
        emit({ ...turn, type: 'stage', stageId: 'organize', label: '正在组织回答', phase: 'end' });
      for (const piece of chunkText(answer)) {
        if (request.signal.aborted) throw new DOMException('aborted', 'AbortError');
        emit({ ...turn, type: 'text', delta: piece });
        await sleep(chunkDelay, request.signal);
      }
      // 模拟服务没有真实计量：用量按未知展示，不算零费用
      emit({ ...turn, type: 'usage', usage: { inputTokens: null, outputTokens: null } });
      emit({ ...turn, type: 'end', finishReason: 'stop' });
    },
  };
}
