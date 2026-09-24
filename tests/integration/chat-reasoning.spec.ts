import { test, expect } from '@playwright/test';

for (const model of ['教学问答模型', 'Responses 模型', 'Anthropic 模型']) {
  test(`${model}：推理先显示，正文出现后折叠，公式与恢复正常`, async ({ page, request }, info) => {
    await page.goto('/chat');
    await page.getByRole('button', { name: '选择模型', exact: true }).click();
    await page.getByRole('dialog').getByRole('button').filter({ hasText: model }).click();
    await page.getByRole('textbox', { name: '输入问题' }).fill('推理验收');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    const toggle = page.getByRole('button', { name: '推理过程' });
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByRole('region', { name: '推理内容' })).toContainText('先分析公式');
    await expect(page.locator('.chat-reasoning-body .katex').first()).toBeVisible();
    await expect(page.locator('.chat-reasoning-fold')).toHaveCSS('opacity', '1');
    // UX-REGRESSION-FIX v1：公式在**流式过程中**就要显示，而不是只在结束后渲染。
    // 已闭合的块：反斜杠行内 1 处 + 两个块级公式（$$ 与 \[\]）各 1 处。
    await expect(page.locator('.chat-reasoning-body .katex')).toHaveCount(3);
    await expect(page.locator('.chat-reasoning-body .katex-display')).toHaveCount(2);
    // 代码里的美元符号保持原文，不解析成公式
    await expect(page.getByRole('region', { name: '推理内容' })).toContainText('$HOME 与 $((1+2))');
    // 未闭合的尾段暂以原文显示
    await expect(page.locator('.chat-reasoning-body .chat-reasoning-raw')).toContainText('$x + y');
    await expect(page.locator('.chat-reasoning-body .katex-error')).toHaveCount(0);
    expect((await (await request.get('http://127.0.0.1:8002/stats')).json()).first).toBeNull();
    await page.screenshot({ path: info.outputPath('reasoning-streaming.png') });
    // 补齐未闭合尾段的定界符 → 转为公式
    await request.get('http://127.0.0.1:8002/reasoning');
    await expect(page.locator('.chat-reasoning-body .katex')).toHaveCount(4);
    await expect(page.locator('.chat-reasoning-body .chat-reasoning-raw')).toHaveCount(0);
    await expect(page.locator('.chat-reasoning-body .katex-error')).toHaveCount(0);
    await request.get('http://127.0.0.1:8002/answer');
    await expect(page.getByText('第一段中文已经到达。', { exact: true })).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect((await (await request.get('http://127.0.0.1:8002/stats')).json()).last).toBeNull();
    const body = page.locator('.chat-bubble.assistant .chat-answer-content .answer-markdown');
    await expect(body.locator('.katex')).toHaveCount(2);
    await expect(body.locator('.katex-error')).toHaveCount(0);
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await request.get('http://127.0.0.1:8002/release');
    await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await page.reload();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.click();
    await expect(page.getByRole('region', { name: '推理内容' })).toContainText('先分析公式');
    await expect(page.locator('.chat-reasoning-fold')).toHaveCSS('opacity', '1');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: info.outputPath('reasoning-restored-mobile.png') });
  });
}

test('正文公式：text.delta 原文逐字保留并在流中、终态及刷新后渲染', async ({
  page,
  request,
}, info) => {
  await page.goto('/chat');
  await page.getByRole('button', { name: '选择模型', exact: true }).click();
  await page.getByRole('dialog').getByRole('button').filter({ hasText: '教学问答模型' }).click();
  await page.getByRole('textbox', { name: '输入问题' }).fill('正文公式验收');
  await page.getByRole('button', { name: '发送', exact: true }).click();

  const answer = page.locator('.chat-bubble.assistant');
  const body = answer.locator(':scope > .chat-answer-content');
  await expect(body).toContainText('正文闭合公式');
  await expect(body.locator('.katex')).toHaveCount(8);
  await expect(body.locator('.katex-display')).toHaveCount(2);
  await expect(body.locator('.katex-error')).toHaveCount(0);
  await expect(body.locator('.katex').nth(0)).toContainText('x2+y2=z2');
  await expect(body.locator('table')).toHaveCount(1);
  await expect(body.locator('pre code')).toContainText('$HOME $((1+2))');
  await expect(body).toContainText('$x+y');
  const streamDom = await body.evaluate((node) => ({
    rawText: (document.querySelector('.chat-answer-content') as HTMLElement).innerText,
    katex: node.querySelectorAll('.katex').length,
    display: node.querySelectorAll('.katex-display').length,
    errors: node.querySelectorAll('.katex-error').length,
    rawClass: node.querySelectorAll('.chat-answer-raw').length,
    css: getComputedStyle(node).display,
    font: getComputedStyle(node.querySelector('.katex')!).fontFamily,
  }));
  const upstream = await (await request.get('http://127.0.0.1:8002/stats')).json();
  await page.screenshot({ path: info.outputPath('body-math-streaming.png') });
  expect(upstream.bodyRaw).toContain('$x^2+y^2=z^2$');
  expect(upstream.bodyRaw).toContain(String.raw`\\(r^2\\)`);
  expect(upstream.bodyDeltas.join('')).toBe(upstream.bodyRaw);
  expect(streamDom.katex).toBe(8);
  expect(streamDom.errors).toBe(0);
  // 正文流中：未闭合尾段走 raw 呈现（证明正文用了流式分段，而非静态全文渲染）
  expect(streamDom.rawClass).toBe(1);
  expect(streamDom.css).not.toBe('none');
  expect(streamDom.font).toContain('KaTeX');

  await request.get('http://127.0.0.1:8002/content');
  await expect(body.locator('.katex')).toHaveCount(11);
  await expect(body.locator('.chat-answer-raw')).toHaveCount(0);
  await expect(body).not.toContainText(String.raw`\\(r^2\\)`);
  await expect(body.locator('.katex-error')).toHaveCount(0);
  await expect(body.locator('.katex').filter({ hasText: 'x+y=z' })).toHaveCount(1);
  await request.get('http://127.0.0.1:8002/release');
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible();
  const finalUpstream = await (await request.get('http://127.0.0.1:8002/stats')).json();
  expect(streamDom.rawText).toContain('公式');
  expect(finalUpstream.bodyDeltas.join('')).toBe(finalUpstream.bodyRaw);
  expect(finalUpstream.bodyRaw).toContain('正文闭合公式 $x^2+y^2=z^2$');
  expect(finalUpstream.bodyRaw).toContain(' = z$ 已补齐。');
  const persisted = await page.evaluate(async (expectedRaw) => {
    const databases = await indexedDB.databases();
    const database = databases.find((entry) => entry.name === 'zhiqikeyuan-chat');
    if (!database?.name) return false;
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      const open = indexedDB.open(database.name!);
      open.onsuccess = () => resolve(open.result);
      open.onerror = () => reject(open.error);
    });
    const conversations = await new Promise<Array<{ messages: Array<{ content: string }> }>>(
      (resolve, reject) => {
        const request = db
          .transaction('conversations', 'readonly')
          .objectStore('conversations')
          .getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      },
    );
    db.close();
    return conversations.some((conversation) =>
      conversation.messages.some((message) => message.content === expectedRaw),
    );
  }, finalUpstream.bodyRaw as string);
  expect(persisted).toBe(true);
  await page.screenshot({ path: info.outputPath('body-math-terminal.png') });
  await page.reload();
  const restored = page.locator('.chat-bubble.assistant .chat-answer-content > .answer-markdown');
  await expect(restored.locator('.katex')).toHaveCount(11);
  await expect(restored.locator('.katex-error')).toHaveCount(0);
  await page.screenshot({ path: info.outputPath('body-math-restored.png') });
});

test('正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占', async ({
  page,
  request,
}, info) => {
  await page.goto('/chat');
  await page.getByRole('button', { name: '选择模型', exact: true }).click();
  await page.getByRole('dialog').getByRole('button').filter({ hasText: '教学问答模型' }).click();
  await page.getByRole('textbox', { name: '输入问题' }).fill('正文后继续推理验收');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  const toggle = page.getByRole('button', { name: '推理过程' });
  await expect(page.getByText('正文已开始，推理仍在继续。', { exact: true })).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  const inner = page.locator('.chat-reasoning-body');
  await expect(page.getByText('正文后推理行 40：', { exact: false })).toBeVisible();
  const sample = await inner.evaluate((el) => ({
    top: el.scrollTop,
    height: el.clientHeight,
    total: el.scrollHeight,
    gap: el.scrollHeight - el.scrollTop - el.clientHeight,
  }));
  console.info('post-answer reasoning follow sample', JSON.stringify(sample));
  await page.screenshot({ path: info.outputPath('reasoning-post-answer-follow.png') });
  expect(sample.gap).toBeLessThan(32);
  const box = await inner.boundingBox();
  if (!box) throw new Error('推理滚动区域没有可见几何位置');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -120);
  await page.waitForTimeout(40);
  const paused = await inner.evaluate((el) => el.scrollTop);
  await page.waitForTimeout(300);
  const pausedAfter = await inner.evaluate((el) => ({
    top: el.scrollTop,
    total: el.scrollHeight,
    gap: el.scrollHeight - el.scrollTop - el.clientHeight,
  }));
  // 内容仍在增长（total 变大）且用户位置未被抢回（top 不变、距底拉开）
  expect(pausedAfter.total).toBeGreaterThan(sample.total);
  expect(pausedAfter.top).toBe(paused);
  expect(pausedAfter.gap).toBeGreaterThan(32);
  await page.mouse.wheel(0, 1200);
  await expect
    .poll(async () => inner.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight))
    .toBeLessThan(32);
  // 回到底部后恢复跟随：后续增量仍贴底
  await expect(page.getByText('正文后推理行 47：', { exact: false })).toBeVisible();
  await expect
    .poll(async () => inner.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight))
    .toBeLessThan(32);
  await page.screenshot({ path: info.outputPath('reasoning-post-answer-paused.png') });
  await request.get('http://127.0.0.1:8002/release');
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible();
});

for (const target of [20_000, 50_000]) {
  test(`性能：${target / 1000}k 推理 + 正文公式受控流`, async ({ page, request }, info) => {
    await page.goto('/chat');
    await page.getByRole('button', { name: '选择模型', exact: true }).click();
    await page.getByRole('dialog').getByRole('button').filter({ hasText: '教学问答模型' }).click();
    await page.getByRole('textbox', { name: '输入问题' }).fill(`性能验收${target / 1000}k`);
    await page.evaluate(() => {
      window.__chatPerf = {
        frames: [],
        longTasks: [],
        visibleAt: null,
        maxReasoningChars: 0,
        start: performance.now(),
      };
      try {
        new PerformanceObserver((list) => {
          window.__chatPerf.longTasks.push(...list.getEntries().map((entry) => entry.duration));
        }).observe({ entryTypes: ['longtask'] });
      } catch {}
      const tick = (previous) =>
        requestAnimationFrame((now) => {
          if (window.__chatPerf.done) return;
          window.__chatPerf.frames.push(now - previous);
          tick(now);
        });
      tick(performance.now());
      const observer = new MutationObserver(() => {
        const reasoningText = document.querySelector('.chat-reasoning-body')?.textContent ?? '';
        window.__chatPerf.maxReasoningChars = Math.max(
          window.__chatPerf.maxReasoningChars,
          reasoningText.length,
        );
        if (window.__chatPerf.visibleAt === null && reasoningText)
          window.__chatPerf.visibleAt = performance.now();
      });
      observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    });
    await page.getByRole('button', { name: '发送', exact: true }).click();
    const answer = page.locator('.chat-bubble.assistant');
    const reasoning = page.locator('.chat-reasoning-body');
    await expect(reasoning).toContainText('性能推理段落');
    await expect(answer.locator('.chat-answer-content .katex').first()).toBeVisible();
    await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible({
      timeout: 180000,
    });
    await page.waitForTimeout(500);
    await page.evaluate(() => {
      window.__chatPerf.done = true;
    });
    const result = await page.evaluate(() => {
      const p = window.__chatPerf;
      const frames = p.frames.filter((frame) => frame > 0).sort((a, b) => a - b);
      return {
        chars: p.maxReasoningChars,
        frameCount: frames.length,
        frameP50: frames[Math.floor(frames.length * 0.5)] ?? null,
        frameP95: frames[Math.min(frames.length - 1, Math.floor(frames.length * 0.95))] ?? null,
        frameMax: frames.at(-1) ?? null,
        over50: frames.filter((frame) => frame > 50).length,
        longTasks: p.longTasks.length,
        longTaskMax: Math.max(0, ...p.longTasks),
        firstVisibleMs: p.visibleAt === null ? null : p.visibleAt - p.start,
        katex: document.querySelectorAll('.chat-answer-content .katex').length,
        katexErrors: document.querySelectorAll('.chat-answer-content .katex-error').length,
      };
    });
    expect(result.chars).toBeGreaterThanOrEqual(target);
    const upstream = await (await request.get('http://127.0.0.1:8002/stats')).json();
    expect(upstream.reasoningRaw.length).toBe(target);
    expect(upstream.reasoningDeltas.join('')).toBe(upstream.reasoningRaw);
    expect(upstream.bodyDeltas.join('')).toBe(upstream.bodyRaw);
    result.streamMs = Math.round((upstream.last - upstream.first) * 1000) / 1000;
    expect(result.katexErrors).toBe(0);
    await page.screenshot({ path: info.outputPath(`performance-${target / 1000}k-terminal.png`) });
    console.info('synthetic perf sample', JSON.stringify({ target, result }));
    await request.get('http://127.0.0.1:8002/release');
  });
}

test('推理滚动：流式跟随、主动上滚暂停与回到底部恢复', async ({ page, request }, info) => {
  await page.goto('/chat');
  await page.getByRole('button', { name: '选择模型', exact: true }).click();
  await page.getByRole('dialog').getByRole('button').filter({ hasText: '教学问答模型' }).click();
  await page.getByRole('textbox', { name: '输入问题' }).fill('推理跟随验收');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  const inner = page.locator('.chat-reasoning-body');
  const outer = page.locator('.chat-messages');
  await expect(page.getByText('推理行 10：', { exact: false })).toBeVisible();
  const samples = [];
  for (let index = 0; index < 18; index += 1) {
    await expect(
      page.getByText(`推理行 ${String(index + 10).padStart(2, '0')}：`, { exact: false }),
    ).toBeVisible();
    const expectedLine = `推理行 ${String(index + 10).padStart(2, '0')}：`;
    const sample = await page.evaluate((latestLine) => {
      const innerNode = document.querySelector('.chat-reasoning-body')!;
      const outerNode = document.querySelector('.chat-messages')!;
      return {
        inner: {
          top: innerNode.scrollTop,
          height: innerNode.clientHeight,
          total: innerNode.scrollHeight,
          gap: innerNode.scrollHeight - innerNode.scrollTop - innerNode.clientHeight,
        },
        outer: {
          top: outerNode.scrollTop,
          height: outerNode.clientHeight,
          total: outerNode.scrollHeight,
          gap: outerNode.scrollHeight - outerNode.scrollTop - outerNode.clientHeight,
        },
        latestText: innerNode.textContent?.includes(latestLine) ?? false,
      };
    }, expectedLine);
    samples.push(sample);
    await page.waitForTimeout(100);
  }
  expect(samples.every((sample) => sample.inner.gap < 32 && sample.latestText)).toBe(true);
  const initial = samples[0];
  await page.screenshot({ path: info.outputPath('reasoning-follow-streaming.png') });
  console.info(
    'reasoning follow samples',
    JSON.stringify({ stage: 'uninterrupted-follow', samples }),
  );

  const box = await inner.boundingBox();
  if (!box) throw new Error('推理滚动区域没有可见几何位置');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -120);
  await page.waitForTimeout(50);
  const pausedAt = await inner.evaluate((el) => el.scrollTop);
  await expect
    .poll(async () => inner.evaluate((el) => el.scrollHeight))
    .toBeGreaterThan(initial.inner.total);
  await page.waitForTimeout(300);
  const pausedAfter = await inner.evaluate((el) => ({
    top: el.scrollTop,
    total: el.scrollHeight,
    bottomGap: el.scrollHeight - el.scrollTop - el.clientHeight,
  }));
  console.info(
    'reasoning follow sample',
    JSON.stringify({ stage: 'after user wheel', pausedAt, pausedAfter }),
  );
  await page.screenshot({ path: info.outputPath('reasoning-follow-paused.png') });

  await page.mouse.wheel(0, 1200);
  await expect
    .poll(async () => inner.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight))
    .toBeLessThan(32);
  const resumed = await inner.evaluate((el) => ({
    top: el.scrollTop,
    total: el.scrollHeight,
    bottomGap: el.scrollHeight - el.scrollTop - el.clientHeight,
  }));
  console.info(
    'reasoning follow sample',
    JSON.stringify({
      stage: 'user returned to latest',
      resumed,
      outer: await outer.evaluate((el) => ({
        top: el.scrollTop,
        height: el.clientHeight,
        total: el.scrollHeight,
      })),
    }),
  );
  await page.screenshot({ path: info.outputPath('reasoning-follow-resumed.png') });
  await request.get('http://127.0.0.1:8002/release');
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible();
});
