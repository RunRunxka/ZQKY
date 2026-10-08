import type { NextConfig } from 'next';
import path from 'node:path';

// 同源代理目标：仅本机回环的后端服务；Next 只代理 /api/v1，不实现业务 Route Handlers
const apiOrigin = process.env.ZQKY_API_ORIGIN ?? 'http://127.0.0.1:8000';

const config: NextConfig = {
  distDir: process.env.ZQKY_TEST_BUILD === '1' ? '.next-test' : '.next',
  reactStrictMode: true,
  devIndicators: false,
  turbopack: { root: path.resolve(import.meta.dirname, '../..') },
  experimental: {
    // Next 同源代理默认 30 秒无字节即 504（next 的 proxy-request.js `proxyTimeout || 30000`）：
    // 题库 AI 整理等同步长任务中途不发一个字节（真机 2026-10-08：6 批 ≈ 70 秒），
    // 前端只会看到"服务不可用"，任务其实已在服务端跑完。放宽到 10 分钟——仍有界；
    // 后端自身有 30 秒/300 秒的调用超时兜底，挂死连接不会无限占用代理。
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default config;
