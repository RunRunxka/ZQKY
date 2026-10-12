/**
 * 教学目标行编解码（知识/能力/思政）与教学重点/难点：可逆、容忍常见写法、不丢文本。
 */
import { describe, expect, it } from 'vitest';
import {
  readKeyPoints,
  readObjectives,
  writeKeyPoints,
  writeObjectives,
} from './objectives';

describe('教学目标行编解码', () => {
  it('识别「知识：/能力：/思政：」三行并可逆回写', () => {
    const text = '知识：梳理游踪与情感变化\n能力：赏析通感与叠词\n思政：体会知识分子的家国情怀';
    const view = readObjectives(text);
    expect(view.structured).toBe(true);
    expect(view.rows.knowledge).toBe('梳理游踪与情感变化');
    expect(view.rows.ability).toBe('赏析通感与叠词');
    expect(view.rows.ideological).toBe('体会知识分子的家国情怀');
    expect(writeObjectives(view)).toBe(text);
  });

  it('容忍 Markdown、编号与【】写法，并把续行归入当前行', () => {
    const view = readObjectives('**1. 知识目标**：识别比喻\n换行继续说\n【能力】梳理线索');
    expect(view.rows.knowledge).toBe('识别比喻\n换行继续说');
    expect(view.rows.ability).toBe('梳理线索');
    expect(view.rows.ideological).toBe('');
  });

  it('没有标签的旧整体文本停在 legacy（structured=false），一个字都不丢', () => {
    const legacy = '1. 语言建构与运用：品味语言之美。\n2. 思维发展与提升：梳理情感线索。';
    const view = readObjectives(legacy);
    expect(view.structured).toBe(false);
    expect(view.other).toEqual(legacy.split('\n'));
    expect(writeObjectives(view)).toBe(legacy);
  });

  it('标签前的无标签行进入 other 并保序保留', () => {
    const text = '教学目标如下\n知识：第一行\n能力：第二行';
    const view = readObjectives(text);
    expect(view.other).toEqual(['教学目标如下']);
    expect(writeObjectives(view)).toBe('知识：第一行\n能力：第二行\n教学目标如下');
    expect(view.rows.knowledge).toBe('第一行');
  });
});

describe('教学重点 / 难点编解码', () => {
  it('识别重点与难点并合成 keyPoints 行', () => {
    const view = readKeyPoints('教学重点：赏析第4—6段\n教学难点：理解喜悦与哀愁的交织');
    expect(view.key).toBe('赏析第4—6段');
    expect(view.difficulty).toBe('理解喜悦与哀愁的交织');
    expect(writeKeyPoints(view)).toBe('教学重点：赏析第4—6段\n教学难点：理解喜悦与哀愁的交织');
  });

  it('无标签文本整体保留', () => {
    const view = readKeyPoints('重点是通感');
    expect(view.other).toEqual(['重点是通感']);
    expect(writeKeyPoints(view)).toBe('重点是通感');
  });
});
