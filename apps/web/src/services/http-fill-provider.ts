import type { FillProvider, FillProposal } from '@/features/lesson-plan/model/types';
import { validateData } from '@/features/lesson-plan/services/drafts';
import { emptyData } from '@/features/lesson-plan/model/defaults';
/** Optional host adapter. No backend or model connection is enabled by default. */
export class HttpFillProvider implements FillProvider {
  id = 'http';
  constructor(private endpoint = '/api/v1/lesson-plans/fill') {}
  async parse(input: string, signal?: AbortSignal): Promise<FillProposal> {
    const response = await fetch(this.endpoint, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input, template_id: 'teacher-standard-v1', schema_version: 1 }),
      signal: signal ?? AbortSignal.timeout(30000),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        typeof error.message === 'string'
          ? error.message
          : `填充服务请求失败（${response.status}）`,
      );
    }
    const result = await response.json();
    if (
      !result?.patch ||
      typeof result.patch !== 'object' ||
      Array.isArray(result.patch) ||
      !Array.isArray(result.warnings) ||
      result.warnings.some((s: unknown) => typeof s !== 'string')
    )
      throw Error('填充服务返回格式不正确');
    if (Object.keys(result.patch).some((k) => !Object.hasOwn(emptyData, k)))
      throw Error('填充服务返回了未知字段');
    validateData({ ...emptyData, ...result.patch });
    return { patch: result.patch, warnings: result.warnings, source: input };
  }
}
