const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { createStaticServer } = require('./serve');

(async () => {
  const remote = process.argv[2];
  const server = remote ? null : createStaticServer({ directory: path.resolve(__dirname, '..'), prefix: '/study/apps/recall-quiz/' });
  if (server) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = remote || `http://127.0.0.1:${server.address().port}/study/apps/recall-quiz/`;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.clock.setFixedTime(new Date());
    await page.goto(`${base}?screen=catalog&lesson=bookkeeping-chapter02`);
    await page.waitForFunction(() => document.querySelectorAll('.catalog-question').length === 22);
    assert.equal(await page.locator('.catalog-prompt').filter({ hasText: /とは何か？/ }).count(), 22);
    await page.locator('[data-study-type="exercise"]').click();
    assert.equal(new URL(page.url()).pathname, new URL(base).pathname);
    assert.equal(await page.locator('[data-open-lesson]').count(), 1);
    await page.locator('[data-open-lesson]').click();
    await page.waitForFunction(() => document.querySelectorAll('.catalog-question').length === 4);
    await page.locator('.catalog-question > summary').first().click();
    assert.ok(await page.locator('.catalog-question').first().locator('.accounting-blank').count() > 50);
    await page.locator('[data-deck]').click();
    await page.locator('.exercise-title').waitFor();
    assert.equal(await page.locator('.exercise-title').innerText(), '範例2-1');
    assert.equal(await page.locator('.quiz-timer').count(), 0);
    assert.equal(await page.locator('.main-nav').isVisible(), false);
    const input = page.locator('[data-draft-key] input').first();
    await input.fill('材料');
    await page.reload();
    await page.locator('.exercise-title').waitFor();
    assert.equal(await input.inputValue(), '材料');
    await page.clock.setFixedTime(new Date(Date.now() + 60000));
    await page.waitForTimeout(300);
    assert.equal(await page.locator('.answer').count(), 0);
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const button = page.locator('#quiz-controls [data-action="reveal"]');
      const before = await button.boundingBox();
      await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
      assert.deepEqual(await button.boundingBox(), before);
      assert.ok(before.y + before.height <= 844 && before.x >= 0);
      assert.equal(await page.locator('.exercise-question .accounting-table').evaluateAll(tables => tables.every(table => table.scrollWidth <= table.clientWidth + 2)), true);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.resolve(__dirname, '../output/exercise-question.png'), animations: 'disabled' });
    await page.locator('#quiz-controls [data-action="reveal"]').click();
    await page.locator('.answer').waitFor();
    assert.equal(await input.inputValue(), '材料');
    assert.equal(await page.locator('.answer .accounting-blank').count(), 0);
    assert.deepEqual(await page.locator('#quiz-controls .rating-symbol').allTextContents(), ['×', '△', '○']);
    await page.screenshot({ path: path.resolve(__dirname, '../output/exercise-answer.png'), animations: 'disabled' });
    for (let n = 1; n <= 4; n++) {
      assert.equal(await page.locator('.exercise-title').innerText(), `範例2-${n}`);
      if (n > 1) {
        assert.equal(await page.locator('.answer').count(), 0);
        assert.ok(await page.locator('.exercise-question .accounting-blank').count() >= 10);
        if (n === 3) assert.match(await page.locator('.exercise-question').innerText(), /12,000円/);
        if (n === 4) assert.match(await page.locator('.exercise-question').innerText(), /18,000円/);
        await page.locator('#quiz-controls [data-action="reveal"]').click();
        await page.locator('.answer').waitFor();
      }
      await page.locator('#quiz-controls [data-result="good"]').click();
      if (n < 4) await page.waitForFunction(n => document.querySelector('.exercise-title')?.textContent === `範例2-${n + 1}`, n);
    }
    await page.getByRole('heading', { name: '4問、おつかれさま。' }).waitFor();
    await page.locator('[data-screen="history"]').click();
    assert.equal(await page.locator('.history-question').count(), 4);
    await page.locator('[data-study-type="knowledge"]').click();
    assert.equal(await page.locator('.history-question').count(), 0);
    await page.locator('[data-screen="quiz"]').click();
    await page.getByRole('button', { name: '全教科から始める', exact: true }).click();
    await page.locator('.question').waitFor();
    assert.equal(await page.locator('.quiz-timer').count(), 1);
    const snapshot = await page.evaluate(async () => {
      const { state, deck } = window.RecallRuntime.boot();
      return { mode: state.session.mode, length: state.session.queue.length, mixed: deck.questions.some(q => q.promptBlocks), reviews: state.reviews.length, coins: state.garden.coins };
    });
    assert.equal(snapshot.mode, undefined);
    assert.equal(snapshot.length, 5);
    assert.equal(snapshot.mixed, false);
    assert.equal(snapshot.reviews, 4);
    assert.equal(snapshot.coins, 4);
    const oldPrompt = await page.evaluate(async () => {
      const runtime = window.RecallRuntime;
      const backup = await runtime.export();
      const old = (await runtime.loadDeck('bookkeeping-chapter02')).retiredQuestions[0];
      backup.state.reviews.push({ id: 'legacy-bookkeeping', deckId: 'bookkeeping-chapter02', questionId: old.id,
        questionVersion: old.version, result: 'uncertain', reviewedAt: new Date().toISOString() });
      backup.state.session = null;
      await runtime.restore(backup);
      return old.prompt;
    });
    await page.goto(`${base}?screen=history&studyType=knowledge`);
    await page.waitForFunction(prompt => document.querySelector('.history-question .math-text')?.textContent === prompt, oldPrompt);
    assert.equal(await page.locator('.history-question .catalog-prompt .math-text').innerText(), oldPrompt);
    await page.locator('.history-question > summary').click();
    assert.ok(await page.locator('.history-question .source-toggle').count() > 0);
    assert.equal(await page.locator('#coins').innerText(), '4');
    await page.locator('[data-study-type="exercise"]').click();
    assert.equal(new URL(page.url()).pathname, new URL(base).pathname);
    await page.reload();
    await page.waitForFunction(() => document.querySelectorAll('.history-question').length === 4);
    assert.deepEqual(errors, []);
    console.log('用語・知識22問と範例4問の分離、空欄入力、再読み込み、時間制限、固定ボタン、回答保存を確認しました。');
  } finally {
    await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
