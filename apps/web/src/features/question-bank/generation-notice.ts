/**
 * AI 补题（生成）的错误码 → 用户可读文案（TEACHING-LOOP B3 · F10-QB 唯一一份）。
 *
 * 与整理器同一纪律（见 `organizer-notice.ts`）：任务级失败（认证/限流/上游/模型配置、
 * 模型漂移）指向**模型服务或模型配置**，不归因到题目内容；生成级校验失败说明
 * 「整批补题已失败，没有生成任何草稿」；`GENERATION_INPUT_INVALID` 是旧语义任务，
 * 要求重新发起（不自动恢复）。未知码优先原样转述服务端 message，前端不发明错误码。
 */

export const GENERATION_BATCH_FAILURE_CODES: readonly string[] = [
  'GENERATION_INVALID_JSON',
  'GENERATION_OUTPUT_TRUNCATED',
  'GENERATION_CANDIDATE_COUNT_MISMATCH',
  'GENERATION_UNKNOWN_KNOWLEDGE',
  'GENERATION_UNKNOWN_EVIDENCE',
  'GENERATION_FORBIDDEN_REFERENCE',
  'GENERATION_ASSET_INVALID',
  'GENERATION_ASSET_NOT_REGISTERED',
  'GENERATION_CONTENT_INVALID',
  'GENERATION_MATERIAL_INVALID',
  'GENERATION_KNOWLEDGE_UNAVAILABLE',
  'GENERATION_KNOWLEDGE_SUBJECT_CHANGED',
];

export const GENERATION_FAILURE_COPY: Record<string, string> = {
  // ----- 任务级：模型服务 / 模型配置（绝不归因到题目内容） -----
  AUTH_REQUIRED: '模型服务认证失败：请到「模型设置」检查该连接的凭证后重试。',
  RATE_LIMITED: '模型服务限流：请稍后重试，或改用其他聊天模型。',
  MODEL_NOT_CONFIGURED:
    '所选聊天模型当前不可调用：请到「模型设置」修复该连接后重试；不会自动改用其他模型。',
  MODEL_PROFILE_NOT_FOUND:
    '所选聊天模型配置已不存在：请到「模型设置」重新选择默认问答模型后再补题；不会自动改用其他模型。',
  MODEL_PURPOSE_MISMATCH:
    '所选模型的用途不是聊天：请到「模型设置」改选聊天模型；不会自动改用其他模型。',
  QUESTION_MODEL_NOT_CLOUD:
    '题库 AI 不使用本机模型，请选择云端模型档案：到「模型设置 → 模型与连接」把默认问答模型换成云端档案后重新补题（本次没有创建任务，也没有调用模型）。',
  UPSTREAM_UNAVAILABLE: '模型服务当前不可用（网络或上游故障）：请稍后重试，或改用其他聊天模型。',
  SERVICE_UNAVAILABLE: '后端题库补题服务未就绪：请确认后端服务已启动后重试。',
  MODEL_CONFIG_DRIFT:
    '该模型配置在执行前已变化（模型/地址/格式与冻结指纹不一致）：本次补题未调用模型、未生成草稿；请确认配置后用当前模型重新发起。',
  MODEL_FINGERPRINT_MISSING:
    '该补题任务缺少可核对的模型指纹（旧版本创建）：不会静默放行，请重新发起补题。',
  // ----- 旧语义未完成任务 -----
  GENERATION_INPUT_INVALID: '该补题任务由旧版语义创建，未自动执行：请重新发起 AI 补题。',
  // ----- 生成级：整批失败，零草稿 -----
  GENERATION_INVALID_JSON: 'AI 返回内容不是合法 JSON：整批补题已失败，没有生成任何草稿。',
  GENERATION_OUTPUT_TRUNCATED:
    '模型输出被截断（结束原因 length）：整批补题已失败，没有生成任何草稿；可提高该模型的输出上限或减少题数后重试。',
  GENERATION_CANDIDATE_COUNT_MISMATCH:
    'AI 返回的题数与请求数量不一致：整批补题已失败，没有生成任何草稿。',
  GENERATION_UNKNOWN_KNOWLEDGE:
    'AI 引用了输入之外的知识点：整批补题已失败，没有生成任何草稿。',
  GENERATION_UNKNOWN_EVIDENCE: 'AI 引用了输入之外的依据：整批补题已失败，没有生成任何草稿。',
  GENERATION_FORBIDDEN_REFERENCE:
    'AI 返回内容含网址或文件路径：整批补题已失败，没有生成任何草稿。',
  GENERATION_ASSET_INVALID: 'AI 返回的资产引用形状非法：整批补题已失败，没有生成任何草稿。',
  GENERATION_ASSET_NOT_REGISTERED:
    'AI 引用了未登记的资产：整批补题已失败，没有生成任何草稿。',
  GENERATION_CONTENT_INVALID:
    'AI 返回内容不符合题库契约：整批补题已失败，没有生成任何草稿。',
  GENERATION_MATERIAL_INVALID:
    '附带的证据材料不合法（空文本 / 含网址或路径 / 超出预算）：没有创建任务，模型未被调用。',
  GENERATION_KNOWLEDGE_UNAVAILABLE:
    '所选知识点在生成期间被归档或删除：整批补题已失败，没有生成任何草稿。',
  GENERATION_KNOWLEDGE_SUBJECT_CHANGED:
    '所选知识点的学科在生成期间发生变化：整批补题已失败，没有生成任何草稿。',
  // ----- 入口闸门（HTTP 错误） -----
  KNOWLEDGE_POINT_NOT_FOUND: '所选知识点不存在：请刷新知识点列表后重试。',
  KNOWLEDGE_POINT_ARCHIVED: '所选知识点已归档，不能用于补题：请改选在用知识点。',
  KNOWLEDGE_SUBJECT_MISMATCH: '所选知识点与学科不一致（或跨学科）：请只保留同一学科的知识点。',
};

export const GENERATION_FAILURE_FALLBACK =
  'AI 补题未能完成：请稍后重试，或到「模型设置」检查当前聊天模型后重试。';

/** 错误码 → 可读说明（未知码优先原样转述服务端 message，不编造）。 */
export function generationFailureText(
  code: string | null | undefined,
  serverMessage?: string | null,
): string {
  if (code && GENERATION_FAILURE_COPY[code]) return GENERATION_FAILURE_COPY[code];
  const message = serverMessage?.trim();
  if (message) return message;
  if (code) return `AI 补题失败（${code}）：${GENERATION_FAILURE_FALLBACK}`;
  return GENERATION_FAILURE_FALLBACK;
}

/** 补题的固定语义：只产待校对草稿，永不自动入库。 */
export const GENERATION_SUGGESTION_SEMANTICS =
  'AI 补题只生成待校对草稿（extraction_method=ai），永远不会自动入库；候选必须人工逐题校对后用确认接口入库。';

/** 取消语义：取消发生在发布前 → 零批次、零草稿；已发布的批次不受影响。 */
export const GENERATION_CANCELLED_NOTICE =
  '补题任务已取消：未发布时不会生成任何批次或草稿（模型可能已被调用，但结果不会落库）。';

/** 中断语义：重启遗留的 running 一律转 interrupted，不自动重新调用模型。 */
export const GENERATION_INTERRUPTED_NOTICE =
  '补题任务已中断（进程重启或无执行器在跑）：不会自动重新调用模型；点「重试补题」按新尝试继续（沿用冻结的模型与输入）。';

/** 重试不换模型：重试沿用任务冻结的模型与指纹；用户只能重新发起新任务才会换模型。 */
export const GENERATION_RETRY_SEMANTICS =
  '重试沿用任务冻结的模型与输入（服务端保留冻结输入与模型指纹），不会换成当前聊天模型。';
