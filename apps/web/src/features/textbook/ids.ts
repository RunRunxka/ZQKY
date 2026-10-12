/**
 * 提交幂等键：同一次用户意图（一次点击及其请求级重试）必须复用同一个 id，
 * 服务端据此识别重复提交；新的意图才生成新 id。
 */

export function newSubmissionId(): string {
  const cryptoApi = typeof globalThis.crypto === 'undefined' ? null : globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') return cryptoApi.randomUUID();
  if (cryptoApi && typeof cryptoApi.getRandomValues === 'function') {
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }
  // 最后兜底：仅用于无 WebCrypto 的环境，不用于安全用途
  return `sub-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
