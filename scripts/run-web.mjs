import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
const cwd = fileURLToPath(new URL('../apps/web/', import.meta.url));
const require = createRequire(new URL('../apps/web/package.json', import.meta.url));
const mode = process.argv[2] ?? 'dev',
  port = process.argv[3] ?? '5173';
if (!['dev', 'start'].includes(mode) || !/^\d+$/.test(port))
  throw Error('Usage: node scripts/run-web.mjs dev|start [port]');
const cli = require.resolve('next/dist/bin/next');
process.chdir(cwd);
process.argv = [process.execPath, cli, mode, '--hostname', '127.0.0.1', '--port', port];
await import(pathToFileURL(cli).href);
