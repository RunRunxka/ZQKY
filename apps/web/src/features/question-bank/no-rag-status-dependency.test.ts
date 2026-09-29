import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * 依赖闸门（RAG-QUALITY v1.1）：题库前端不得再依赖教材服务的概括模型状态接口
 * （上一批把 profileId 当本机模型名使用的那条错误通道）。
 *
 * 断言写成读源码的形式，避免以后有人把「本机模型名」的旧通道悄悄接回来。
 * 禁词在运行时拼装，测试文件自身不会把它写进源码。
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const QUESTION_BANK_API = join(HERE, '..', '..', 'services', 'question-bank-api.ts');

const FORBIDDEN_DEPENDENCIES = [
  ['summarization', 'model'].join('.'),
  ['/rag', 'status'].join('/'),
];

function sourceFiles(root: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(root)) {
    const full = join(root, entry);
    if (statSync(full).isDirectory()) {
      found.push(...sourceFiles(full));
      continue;
    }
    if (entry.endsWith('.ts') || entry.endsWith('.tsx')) found.push(full);
  }
  return found;
}

describe('题库前端不再依赖教材概括模型状态接口', () => {
  const sources = [...sourceFiles(HERE), QUESTION_BANK_API].map((path) => ({
    path,
    text: readFileSync(path, 'utf8'),
  }));

  it('题库源码（含 API 客户端）不出现旧依赖', () => {
    expect(sources.length).toBeGreaterThan(5);
    for (const needle of FORBIDDEN_DEPENDENCIES) {
      const offenders = sources.filter(({ text }) => text.includes(needle)).map(({ path }) => path);
      expect(offenders, `仍引用「${needle}」的文件`).toEqual([]);
    }
  });
});
