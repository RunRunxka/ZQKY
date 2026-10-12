/** 失败原因的统一文案（带后端错误码，便于教师上报与排查；不吞掉原始信息）。 */
import { ApiError } from '@/services/api-client';

export function describeError(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}：${error.message}`;
  if (error instanceof Error) return error.message;
  return '未知错误';
}
