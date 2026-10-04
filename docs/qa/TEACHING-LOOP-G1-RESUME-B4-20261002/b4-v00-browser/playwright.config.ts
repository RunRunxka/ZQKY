import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const folder=path.dirname(fileURLToPath(import.meta.url));
const run=process.env.ZQKY_B4_V00_RUN;
if(!run || !/^[a-z0-9-]+$/.test(run)) throw new Error('Explicit new B4-V00 run id required');
export default defineConfig({
  testDir:folder,testMatch:'real-browser.spec.ts',workers:1,fullyParallel:false,
  timeout:240_000,expect:{timeout:15_000},
  outputDir:path.join(folder,`browser-artifacts-${run}`),
  reporter:[['list'],['json',{outputFile:path.join(folder,`browser-results-${run}.json`)}]],
  use:{baseURL:'http://127.0.0.1:5174',viewport:{width:1440,height:900},
    ...(process.platform==='win32'?{channel:'msedge'}:{}),
    trace:'on',screenshot:'only-on-failure',acceptDownloads:true},
  // No webServer: CTRL owns only backend; frontend lifecycle belongs to user.
});
