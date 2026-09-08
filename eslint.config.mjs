import { defineConfig, globalIgnores } from 'eslint/config';
import next from 'eslint-config-next/core-web-vitals';
import ts from 'eslint-config-next/typescript';
export default defineConfig([
  ...next,
  ...ts,
  globalIgnores(['**/.next/**', '**/node_modules/**', '_work/**', '教案模板部分/**']),
  {
    settings: { next: { rootDir: 'apps/web/' } },
    rules: { 'react-hooks/set-state-in-effect': 'off', 'react-hooks/refs': 'off' },
  },
]);
