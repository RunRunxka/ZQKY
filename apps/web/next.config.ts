import type { NextConfig } from 'next';
import path from 'node:path';

// 同源代理目标：仅本机回环的后端服务；Next 只代理 /api/v1，不实现业务 Route Handlers
const apiOrigin = process.env.ZQKY_API_ORIGIN ?? 'http://127.0.0.1:8000';

const config: NextConfig = {
  distDir: process.env.ZQKY_TEST_BUILD === '1' ? '.next-test' : '.next',
  reactStrictMode: true,
  devIndicators: false,
  turbopack: { root: path.resolve(import.meta.dirname, '../..') },
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default config;
