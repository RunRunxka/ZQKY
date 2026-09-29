/**
 * 题库 AI 整理的错误码 → 用户可读文案（RAG-QUALITY v1.1 唯一一份）。
 *
 * 归因纪律（任务卡 §5.1，与后端 `services/question_bank/organizer.py` 的分类一一对应）：
 * - **任务级**（认证 / 限流 / 网络 / 上游故障 / 模型配置）一律指向**模型服务**，
 *   不得说成「试题内容无效」一类的内容归因；模型配置类失败还要声明**不会自动改用其他模型**；
 * - **批级**（非法 JSON / 输出截断 / 未知来源块 / 内容不符 / 草稿被改）说明
 *   「该批未生成可应用建议，原文与草稿未被修改」，其余批次与既有建议照旧；
 * - **旧语义任务**（`ORGANIZER_MODEL_RESELECT_REQUIRED`）要求重新选择模型，并声明已生成的建议已保留；
 * - **取消**（任务状态 `cancelled`）说明在途未完成批次的建议不会保存。
 *
 * 本模块只做「错误码 → 中文说明」，不发请求、不判断建议是否可应用
 * （建议能否应用只看服务端返回的 `suggestions` 列表与服务端校验结果）。
 */

/** 批级失败码：该批不产生建议，原文保留、草稿不变，其余批次继续。 */
export const ORGANIZER_BATCH_FAILURE_CODES: readonly string[] = [
  'ORGANIZER_INVALID_JSON',
  'ORGANIZER_OUTPUT_TRUNCATED',
  'ORGANIZER_UNKNOWN_SOURCE_BLOCK',
  'ORGANIZER_INVALID_CONTENT',
  'ORGANIZER_BATCH_BUDGET_INVALID',
  'ORGANIZE_DRAFT_CHANGED',
  'ORGANIZE_TARGET_MISSING',
];

export function isOrganizerBatchFailure(code: string | null | undefined): boolean {
  return !!code && ORGANIZER_BATCH_FAILURE_CODES.includes(code);
}

/**
 * 错误码文案表。键与后端落库/上抛的 code 一致，新增 code 请先与后端确认，
 * 前端不自己发明错误码（未知码走服务端 message 兜底）。
 */
export const ORGANIZER_FAILURE_COPY: Record<string, string> = {
  // ----- 任务级：模型服务问题（绝不归因到题目内容） -----
  AUTH_REQUIRED: '模型服务认证失败：请到「模型设置」检查该连接的凭证后重试。',
  RATE_LIMITED: '模型服务限流：请稍后重试，或改用其他聊天模型。',
  UPSTREAM_UNAVAILABLE: '模型服务当前不可用（网络或上游故障）：请稍后重试，或改用其他聊天模型。',
  MODEL_NOT_CONFIGURED:
    '所选聊天模型当前不可调用：请到「模型设置」修复该连接后重试；不会自动改用其他模型。',
  MODEL_PROFILE_NOT_FOUND:
    '所选聊天模型配置已不存在：请到「模型设置」重新选择默认问答模型后再整理；不会自动改用其他模型。',
  MODEL_PURPOSE_MISMATCH:
    '所选模型的用途不是聊天：请到「模型设置」改选聊天模型；不会自动改用其他模型。',
  SERVICE_UNAVAILABLE: '后端题库整理服务未就绪：请确认后端服务已启动后重试。',
  // ----- 旧语义未完成任务：不自动恢复，建议保留 -----
  ORGANIZER_MODEL_RESELECT_REQUIRED:
    '该整理任务是在旧版本下创建的，需要重新选择模型后再发起；已生成的建议已保留。',
  // ----- 批级：该批无建议，原文与草稿不变 -----
  ORGANIZER_OUTPUT_TRUNCATED:
    '模型输出被截断（结束原因 length）：该批未生成可应用建议，原文与草稿未被修改；可提高该模型的输出上限或减少该批原文后重试。',
  ORGANIZER_INVALID_JSON: 'AI 返回内容不是合法 JSON：该批未生成可应用建议，原文与草稿未被修改。',
  ORGANIZER_INVALID_CONTENT:
    'AI 返回内容不符合题库契约：该批未生成可应用建议，原文与草稿未被修改。',
  ORGANIZER_UNKNOWN_SOURCE_BLOCK:
    'AI 引用了输入之外的来源块：该批未生成可应用建议，原文与草稿未被修改。',
  ORGANIZER_BATCH_BUDGET_INVALID:
    '原文块超出单批预算且无法安全切片：该批未生成可应用建议，原文与草稿未被修改。',
  ORGANIZE_DRAFT_CHANGED: '草稿在整理期间被编辑：该批建议未保存（不会覆盖你的修改），请重新整理。',
  ORGANIZE_TARGET_MISSING: '目标草稿已不存在：该批建议未保存，原文与草稿未被修改。',
  ORGANIZE_TARGET_EMPTY: '所选草稿没有可整理的原文块：请检查草稿来源区间后重试。',
  ORGANIZE_NO_SUGGESTION: '本次整理没有产生可应用建议：原文与草稿未被修改。',
  // ----- 导入闸门（organize 入口的 HTTP 错误） -----
  IMPORT_NOT_FOUND: '该导入批次不存在：请返回题库列表确认。',
  IMPORT_PARSE_FAILED: '该导入解析失败，不能进行 AI 整理：请重新导入文件。',
  IMPORT_CANCELLED: '该导入已取消，不能进行 AI 整理。',
  IMPORT_ALREADY_CONFIRMED: '该导入已确认入库，不能再次进行 AI 整理。',
};

/** 未知错误码时的兜底：只说事实与下一步，不猜测原因、不归因到题目内容。 */
export const ORGANIZER_FAILURE_FALLBACK =
  'AI 整理未能完成：请稍后重试，或到「模型设置」检查当前聊天模型后重试。';

/**
 * 错误码 → 可读说明。
 * 已知码用本模块文案；未知码优先原样转述服务端 message（不编造），最后才用兜底文案。
 */
export function organizerFailureText(
  code: string | null | undefined,
  serverMessage?: string | null,
): string {
  if (code && ORGANIZER_FAILURE_COPY[code]) return ORGANIZER_FAILURE_COPY[code];
  const message = serverMessage?.trim();
  if (message) return message;
  if (code) return `AI 整理失败（${code}）：${ORGANIZER_FAILURE_FALLBACK}`;
  return ORGANIZER_FAILURE_FALLBACK;
}

/** 取消语义（v1.1 变化）：在途未完成批次的建议不再落库，已完成批次的建议保留。 */
export const ORGANIZER_CANCELLED_NOTICE =
  '任务已取消：在途未完成批次的建议不会保存（已完成批次的建议仍保留在下方）。';

/** 建议的固定语义：只落 pending，应用与入库都要人工确认。 */
export const ORGANIZER_SUGGESTION_SEMANTICS =
  'AI 只给出待校对建议，永不直接覆盖人工草稿；应用建议需要重新校对后再入库，也不会自动入库。';

/** 建议基于的草稿修订已变化时的提示（应用会被服务端拒绝，先明说）。 */
export function organizerStaleSuggestionText(
  baseRevision: number,
  currentRevision: number | null,
): string {
  const target = currentRevision === null ? '草稿已不在批次中' : `当前 r${currentRevision}`;
  return `该建议基于的草稿修订已过期（草案 r${baseRevision} → ${target}）。应用会被服务端拒绝；请重新整理或先处理该草稿。`;
}
