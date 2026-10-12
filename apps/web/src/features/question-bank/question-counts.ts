/**
 * 知识点计数取数（R4-FE 2026-10-11）。
 *
 * 后端没有「按知识点统计题量」的接口，题库页用 `GET /questions?knowledgePointId=…&limit=1`
 * 的 `total` 作为每个知识点的题目数（真实数据，不猜造）。要点：
 *
 * - **并发受限**（默认 5 路）：知识点树可能有几十个节点，一次全量并发会打爆后端；
 * - **失败即未知**：单个节点读取失败只记入 `failedIds`，绝不当 0；整体被 abort（切页/卸载）
 *   时立即停止派发，已完成的计数由调用方按代次丢弃；
 * - 查询条件（难度/关键词）透传给每个节点，使节点计数与「点这个节点会得到多少条」一致。
 */

import type { Difficulty } from '@/contracts/question-bank';
import { listQuestions } from '@/services/question-bank-api';

export interface CountQueryBase {
  difficulty?: Difficulty;
  q?: string;
}

export interface QuestionCounts {
  /** 每个节点的自身题目数；缺键 = 该节点读取失败或未请求。 */
  own: Map<string, number>;
  /** 读取失败的节点 id（界面据此显示 `—` 与重试入口）。 */
  failedIds: string[];
}

/** 单次计数查询：`knowledgePointId` 为空表示不过滤（用于「全部题目」根节点）。 */
export async function fetchQuestionCount(
  knowledgePointId: string | undefined,
  base: CountQueryBase,
  signal?: AbortSignal,
): Promise<number> {
  const page = await listQuestions(
    {
      knowledgePointId: knowledgePointId || undefined,
      difficulty: base.difficulty || undefined,
      q: base.q || undefined,
      offset: 0,
      limit: 1,
    },
    signal,
  );
  return page.total;
}

/**
 * 批量取自身计数。返回时按输入顺序无关；失败的节点只出现在 `failedIds`。
 * 被 abort 时返回已完成的进度（调用方按观察代次决定是否采用）。
 */
export async function fetchQuestionCounts(
  ids: readonly string[],
  base: CountQueryBase,
  signal?: AbortSignal,
  concurrency = 5,
): Promise<QuestionCounts> {
  const own = new Map<string, number>();
  const failedIds: string[] = [];
  let cursor = 0;

  async function worker(): Promise<void> {
    for (;;) {
      if (signal?.aborted) return;
      const index = cursor;
      cursor += 1;
      if (index >= ids.length) return;
      const id = ids[index] as string;
      try {
        own.set(id, await fetchQuestionCount(id, base, signal));
      } catch {
        if (signal?.aborted) return;
        failedIds.push(id);
      }
    }
  }

  const workers = Array.from({ length: Math.max(1, Math.min(concurrency, ids.length)) }, () =>
    worker(),
  );
  await Promise.all(workers);
  return { own, failedIds };
}
