import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const env = { ...process.env, ZQKY_TEST_BUILD: '1', ZQKY_API_ORIGIN: 'http://127.0.0.1:8001' };
async function run(args) {
  const child = spawn(process.execPath, args, { stdio: 'inherit', env, windowsHide: true });
  const code = await new Promise((resolve) => child.on('exit', resolve));
  if (code !== 0) process.exit(Number(code) || 1);
}
await run([require.resolve('next/dist/bin/next'), 'build', 'apps/web']);
await run([require.resolve('@playwright/test/cli'), 'test', '--config=playwright.chat.config.ts']);
