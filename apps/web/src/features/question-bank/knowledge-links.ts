/**
 * 题目/草稿的**正式知识点关联**读取与编辑纯逻辑（TEACHING-LOOP B3 · F10-QB）。
 *
 * 边界（与后端 `question_bank/service.py`、`knowledge_refs.py` 语义一一对应）：
 * - 正式关联是「知识点身份 + 内容修订 + 名称/学科快照」；界面**不猜造**引用：
 *   服务端没给 `knowledgeLinks` 字段时按「未提供」处理（区别于空数组 = 明确无关联）；
 *   形状不认识的条目丢弃并计数，不把损坏内容伪造成关联。
 * - 更新是**整表替换**（空数组 = 清空）：只有用户显式改动过关联才发送；
 *   学科未变且未改动时缺省不发送，服务端按「复制旧关联」处理（界面必须说明，不误导）。
 * - 学科变化时不得继承与新学科冲突的旧关联：服务端 422 `KNOWLEDGE_REFERENCE_INVALID`
 *   带 `details.issues[].field = knowledgeLinks[i].knowledgePointId`；没有 details 的错误
 *   （知识点不存在/已归档/学科不符的 404/422）按消息里出现的知识点 id 定位到对应行——
 *   这是按 id 逐字匹配，不是猜测。
 */

import type { ErrorIssue } from '@/contracts/api';
import type { DraftKnowledgeLinkInput, DraftKnowledgeLinkView } from '@/contracts/question-bank';
import { ApiError } from '@/services/api-client';

export type KnowledgeLinkRole = DraftKnowledgeLinkView['role'];

/** 来源只在**草稿**关联上由服务端给出（人工编辑 / AI 补题）；正式题修订关联没有该字段。 */
export type KnowledgeLinkSource = DraftKnowledgeLinkView['source'];

/**
 * 正式关联的读取视图：字段与冻结契约 `DraftKnowledgeLinkView` 同形（不复制第二份定义），
 * 差别只有 `source`——正式题修订关联没有该字段（服务端不返回时 undefined，界面不猜造）。
 */
export type KnowledgeLinkView = Omit<DraftKnowledgeLinkView, 'source'> & {
  source?: KnowledgeLinkSource;
};

/** 读取结果：`missing` = 服务端没有给这个字段（旧后端 / 旧数据），不是「无关联」。 */
export type KnowledgeLinksRead =
  | { status: 'provided'; links: KnowledgeLinkView[]; skipped: number }
  | { status: 'missing' };

export const KNOWLEDGE_LINKS_MISSING_NOTICE =
  '服务端没有返回知识点关联字段：本页不显示关联，也不会用旧标签或猜测补齐。';

export const KNOWLEDGE_LINKS_SKIPPED_NOTICE = (skipped: number): string =>
  `有 ${skipped} 条关联的形状无法识别，已按「不猜造」原则丢弃未显示；请刷新或检查服务端数据。`;

export function roleLabel(role: KnowledgeLinkRole): string {
  return role === 'primary' ? '主知识点' : '次要知识点';
}

export function linkSourceLabel(source: KnowledgeLinkSource | undefined): string {
  if (source === 'ai') return 'AI 补题关联';
  if (source === 'human') return '人工关联';
  return '来源未标注';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asRole(value: unknown): KnowledgeLinkRole | null {
  return value === 'primary' || value === 'secondary' ? value : null;
}

/** 一条关联：必要字段必须是字符串、role 必须是允许值；否则返回 null（丢弃）。 */
function asLink(value: unknown): KnowledgeLinkView | null {
  if (!isRecord(value)) return null;
  const role = asRole(value.role);
  if (role === null) return null;
  const pointId = value.knowledgePointId;
  const revisionId = value.knowledgeRevisionId;
  const name = value.knowledgeNameSnapshot;
  const subject = value.subjectIdSnapshot;
  if (typeof pointId !== 'string' || !pointId) return null;
  if (typeof revisionId !== 'string') return null;
  if (typeof name !== 'string') return null;
  if (typeof subject !== 'string') return null;
  const link: KnowledgeLinkView = {
    knowledgePointId: pointId,
    knowledgeRevisionId: revisionId,
    knowledgeNameSnapshot: name,
    subjectIdSnapshot: subject,
    role,
  };
  if (value.source === 'human' || value.source === 'ai') link.source = value.source;
  return link;
}

/**
 * 从视图对象（草稿 / 正式题详情）读取关联字段。
 * - 字段不存在或不是数组 → `missing`（不猜造、不补空数组）；
 * - 数组 → 逐条解析，形状不认识的丢弃并计数。
 */
export function readKnowledgeLinks(payload: unknown): KnowledgeLinksRead {
  if (!isRecord(payload) || !('knowledgeLinks' in payload)) return { status: 'missing' };
  const raw = payload.knowledgeLinks;
  if (!Array.isArray(raw)) return { status: 'missing' };
  const links: KnowledgeLinkView[] = [];
  let skipped = 0;
  for (const item of raw) {
    const parsed = asLink(item);
    if (parsed) links.push(parsed);
    else skipped += 1;
  }
  return { status: 'provided', links, skipped };
}

/** 关联 → PATCH 请求体的整表替换载荷（role 缺省 primary）。 */
export function linksToInputs(links: readonly KnowledgeLinkView[]): DraftKnowledgeLinkInput[] {
  return links.map((link) => ({
    knowledgePointId: link.knowledgePointId,
    role: link.role,
  }));
}

/** 两份输入载荷是否等价（整表替换语义：按知识点+角色比较，与顺序无关）。 */
export function sameLinkInputs(
  left: readonly DraftKnowledgeLinkInput[],
  right: readonly DraftKnowledgeLinkInput[],
): boolean {
  const key = (item: DraftKnowledgeLinkInput) =>
    `${item.knowledgePointId}\u0000${item.role ?? 'primary'}`;
  const a = left.map(key).sort();
  const b = right.map(key).sort();
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

export interface LinkIssueLocation {
  /** 关联行下标 → 可读错误（field 或消息里的知识点 id 命中）。 */
  byIndex: Map<number, string>;
  /** 无法定位到具体行的错误（整体性原因，照实显示）。 */
  general: string[];
}

function asIssues(error: ApiError): ErrorIssue[] {
  const issues = error.details?.issues;
  return Array.isArray(issues) ? issues : [];
}

const LINK_FIELD = /^knowledgeLinks\[(\d+)\](?:\.(\w+))?$/;

function issueText(issue: ErrorIssue): string {
  const where = issue.field ? `${issue.field}：` : '';
  return `${where}${issue.message || issue.code}`;
}

/**
 * 把写入错误定位到关联行：
 * 1. `details.issues[].field = knowledgeLinks[i].…`（B2-RV07 的逐条定位）；
 * 2. 没有 details 的错误（知识点不存在/已归档/学科不符）按消息里逐字出现的知识点 id 命中行；
 * 3. 其余作为整体错误原样返回（不静默失败）。
 */
export function locateLinkIssues(
  error: unknown,
  links: readonly KnowledgeLinkView[],
): LinkIssueLocation {
  const location: LinkIssueLocation = { byIndex: new Map(), general: [] };
  const apiError = error instanceof ApiError ? error : null;
  const message = apiError?.message ?? (error instanceof Error ? error.message : '');
  if (apiError) {
    for (const issue of asIssues(apiError)) {
      const matched = issue.field ? LINK_FIELD.exec(issue.field) : null;
      if (matched) {
        const index = Number(matched[1]);
        if (!location.byIndex.has(index)) location.byIndex.set(index, issueText(issue));
        continue;
      }
      location.general.push(issueText(issue));
    }
  }
  if (location.byIndex.size === 0 && location.general.length === 0 && message) {
    const hits: number[] = [];
    links.forEach((link, index) => {
      if (link.knowledgePointId && message.includes(link.knowledgePointId)) hits.push(index);
    });
    if (hits.length > 0) {
      for (const index of hits) location.byIndex.set(index, message);
    } else {
      location.general.push(message);
    }
  }
  return location;
}

export interface SubjectChangeState {
  changed: boolean;
  /** 新学科（trim 后）；空串表示用户把学科清空了。 */
  nextSubjectId: string;
  /** 旧关联中与**新学科**冲突（学科快照不一致）的行下标。 */
  conflictIndexes: number[];
  /** 学科已改且存在冲突（服务端会以 422 要求显式替换或清空）。 */
  blocked: boolean;
}

/**
 * 学科变化检测：新学科非空且旧关联的学科快照不一致 → 冲突行。
 * 新学科为空（或旧快照本身为空、无法判断）不算冲突：服务端也不做学科比对，界面不得虚构冲突。
 */
export function subjectChangeState(
  originalSubjectId: string,
  nextSubjectId: string,
  links: readonly KnowledgeLinkView[],
): SubjectChangeState {
  const next = nextSubjectId.trim();
  const changed = next !== originalSubjectId.trim();
  const conflictIndexes: number[] = [];
  if (changed && next) {
    links.forEach((link, index) => {
      if (link.subjectIdSnapshot && link.subjectIdSnapshot !== next) {
        conflictIndexes.push(index);
      }
    });
  }
  return {
    changed,
    nextSubjectId: next,
    conflictIndexes,
    blocked: changed && conflictIndexes.length > 0,
  };
}

/** 学科冲突的固定说明（界面文案唯一一份；不声称服务端一定会失败之外的任何事）。 */
export function subjectChangeNotice(state: SubjectChangeState, linksTouched: boolean): string | null {
  if (!state.changed) return null;
  if (state.conflictIndexes.length === 0) {
    return linksTouched
      ? '学科已修改：保存时会整表替换知识点关联（旧关联在旧修订上保留，不回溯改写）。'
      : '学科已修改；当前关联的学科快照与新学科一致，未改动关联时服务端会继承它们。';
  }
  return linksTouched
    ? '学科已修改：保存时会整表替换知识点关联；请确认新关联都属于新学科，否则服务端会以 422 拒绝。'
    : `学科已修改，而 ${state.conflictIndexes.length} 条旧关联属于原学科：未改动关联直接保存会被服务端以 422 拒绝（不会自动清空）。请在下面显式替换为新学科知识点，或显式清空后再保存。`;
}
