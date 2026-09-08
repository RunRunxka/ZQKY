/**
 * 轮级耗时（S3，对照参考 web/lib/trace-timing.ts 的设计）：
 * - 时长挂在单条回答的状态行上：流式进行中逐秒滴答，结束后冻结；
 * - 不在每个子过程卡上重复显示时长（参考明确“per-trace 时长让卡片嘈杂”）；
 * - 边界来自消息自身的 startedAt/finishedAt（持久化字段），刷新恢复后
 *   冻结值保持一致，不依赖易失的 React 状态。
 */
export function formatTurnDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  const remSeconds = total % 60;
  if (minutes < 60) {
    return remSeconds === 0 ? `${minutes}m` : `${minutes}m ${remSeconds}s`;
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return remMinutes === 0 ? `${hours}h` : `${hours}h ${remMinutes}m`;
}

/** 由开始/结束时间戳计算时长秒数；结束缺失时以当前时间滴答 */
export function turnDurationSeconds(startedAt: string, finishedAt?: string, nowMs = Date.now()): number {
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return 0;
  const end = finishedAt ? Date.parse(finishedAt) : nowMs;
  if (Number.isNaN(end)) return 0;
  return Math.max(0, (end - start) / 1000);
}
